#!/bin/bash
# Verify deployment health after deploy
# Usage: ./scripts/verify-deployment.sh [environment] [namespace]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
source "$SCRIPT_DIR/lib/common.sh"

ENVIRONMENT=${1:-dev}
NAMESPACE=${2:-multi-agent-platform-${ENVIRONMENT}}
FAILURES=0

# --- Check Functions ---

check_pod_health() {
    local label="$1"
    local expected_containers="$2"
    local namespace="$3"
    local component_name="$4"

    local pod_info
    pod_info=$(oc get pods -l "$label" -n "$namespace" --no-headers 2>/dev/null)

    if [ -z "$pod_info" ]; then
        echo -e "  ${RED}FAIL${NC} $component_name: No pods found with label $label"
        return 1
    fi

    local pod_name
    pod_name=$(echo "$pod_info" | head -1 | awk '{print $1}')
    local ready
    ready=$(echo "$pod_info" | head -1 | awk '{print $2}')
    local status
    status=$(echo "$pod_info" | head -1 | awk '{print $3}')

    local ready_count
    ready_count=$(echo "$ready" | cut -d/ -f1)
    local total_count
    total_count=$(echo "$ready" | cut -d/ -f2)

    if [ "$total_count" -ne "$expected_containers" ]; then
        echo -e "  ${RED}FAIL${NC} $component_name: Expected $expected_containers containers, found $total_count ($ready)"
        return 1
    fi

    if [ "$ready_count" -ne "$total_count" ]; then
        echo -e "  ${RED}FAIL${NC} $component_name: Not all containers ready ($ready) - Status: $status"
        return 1
    fi

    if [ "$status" != "Running" ]; then
        echo -e "  ${RED}FAIL${NC} $component_name: Pod status is $status (expected Running)"
        return 1
    fi

    echo -e "  ${GREEN}PASS${NC} $component_name: $ready containers ready ($pod_name)"
    return 0
}

check_route_accessible() {
    local route_name="$1"
    local namespace="$2"

    local host
    host=$(oc get route "$route_name" -n "$namespace" -o jsonpath='{.spec.host}' 2>/dev/null)

    if [ -z "$host" ]; then
        echo -e "  ${RED}FAIL${NC} Route $route_name: Not found"
        return 1
    fi

    local http_code
    http_code=$(curl -sI -o /dev/null -w '%{http_code}' --max-time 10 "https://$host" 2>/dev/null || echo "000")

    # 200=direct, 302=OAuth redirect, 403=auth required but proxy working
    if [[ "$http_code" == "200" || "$http_code" == "302" || "$http_code" == "403" ]]; then
        echo -e "  ${GREEN}PASS${NC} Route $route_name: https://$host (HTTP $http_code)"
        return 0
    else
        echo -e "  ${RED}FAIL${NC} Route $route_name: https://$host (HTTP $http_code)"
        return 1
    fi
}

check_secret_exists_verify() {
    local secret_name="$1"
    local namespace="$2"

    if oc get secret "$secret_name" -n "$namespace" &>/dev/null; then
        echo -e "  ${GREEN}PASS${NC} Secret $secret_name exists"
        return 0
    else
        echo -e "  ${RED}FAIL${NC} Secret $secret_name not found"
        return 1
    fi
}

# --- Main Verification ---

echo "==================================="
echo "Deployment Verification"
echo "==================================="
echo "Namespace: $NAMESPACE"
echo ""

echo "--- Pod Health ---"
# App pod: 3 containers (oauth-proxy, frontend, backend)
check_pod_health "app=multi-agent-platform" 3 "$NAMESPACE" "Multi-Agent Platform" || FAILURES=$((FAILURES + 1))

# PostgreSQL: 1 container
check_pod_health "app=postgres" 1 "$NAMESPACE" "PostgreSQL" || FAILURES=$((FAILURES + 1))

# Langflow: 2 containers (langflow-ide, oauth-proxy)
check_pod_health "app=langflow-service" 2 "$NAMESPACE" "Langflow" || FAILURES=$((FAILURES + 1))

# MLflow: 2 containers (mlflow, oauth-proxy)
check_pod_health "app.kubernetes.io/instance=mlflow" 2 "$NAMESPACE" "MLflow" || FAILURES=$((FAILURES + 1))

# Langfuse: 1 container (check main web pod only)
check_pod_health "app.kubernetes.io/name=langfuse,app=web" 1 "$NAMESPACE" "Langfuse" || FAILURES=$((FAILURES + 1))

echo ""
echo "--- Route Accessibility ---"
check_route_accessible "multi-agent-platform" "$NAMESPACE" || FAILURES=$((FAILURES + 1))
check_route_accessible "langflow" "$NAMESPACE" || FAILURES=$((FAILURES + 1))
check_route_accessible "mlflow" "$NAMESPACE" || FAILURES=$((FAILURES + 1))
check_route_accessible "langfuse" "$NAMESPACE" || FAILURES=$((FAILURES + 1))

echo ""
echo "--- Deployments/StatefulSets ---"
# Check all deployments in namespace are available
while IFS= read -r line; do
    name=$(echo "$line" | awk '{print $1}')
    ready=$(echo "$line" | awk '{print $2}')
    available=$(echo "$line" | awk '{print $4}')
    desired=$(echo "$ready" | cut -d/ -f2)
    if [ "$available" = "0" ] || [ "$available" = "" ]; then
        echo -e "  ${RED}FAIL${NC} Deployment $name: not available ($ready ready)"
        FAILURES=$((FAILURES + 1))
    else
        echo -e "  ${GREEN}PASS${NC} Deployment $name: $ready ready"
    fi
done < <(oc get deployments -n "$NAMESPACE" --no-headers 2>/dev/null)

# Check all statefulsets in namespace are ready
while IFS= read -r line; do
    [ -z "$line" ] && continue
    name=$(echo "$line" | awk '{print $1}')
    ready=$(echo "$line" | awk '{print $2}')
    ready_count=$(echo "$ready" | cut -d/ -f1)
    desired_count=$(echo "$ready" | cut -d/ -f2)
    if [ "$ready_count" != "$desired_count" ]; then
        echo -e "  ${RED}FAIL${NC} StatefulSet $name: $ready ready"
        FAILURES=$((FAILURES + 1))
    else
        echo -e "  ${GREEN}PASS${NC} StatefulSet $name: $ready ready"
    fi
done < <(oc get statefulsets -n "$NAMESPACE" --no-headers 2>/dev/null)

echo ""
echo "--- Failing Pods ---"
# Check for any pods not in Running state
failing_pods=$(oc get pods -n "$NAMESPACE" --no-headers 2>/dev/null | grep -v "Running\|Completed" || true)
if [ -n "$failing_pods" ]; then
    while IFS= read -r line; do
        pod_name=$(echo "$line" | awk '{print $1}')
        pod_status=$(echo "$line" | awk '{print $3}')
        echo -e "  ${RED}FAIL${NC} Pod $pod_name: $pod_status"
        FAILURES=$((FAILURES + 1))
    done <<< "$failing_pods"
else
    echo -e "  ${GREEN}PASS${NC} No failing pods"
fi

# Check for pods that can't be created (e.g., SCC violations)
failed_events=$(oc get events -n "$NAMESPACE" --field-selector type=Warning,reason=FailedCreate --no-headers 2>/dev/null | tail -5 || true)
if [ -n "$failed_events" ]; then
    echo ""
    echo "--- Recent FailedCreate Events ---"
    while IFS= read -r line; do
        object=$(echo "$line" | awk '{print $4}')
        message=$(echo "$line" | cut -d' ' -f6-)
        # Truncate long messages
        if [ ${#message} -gt 120 ]; then
            message="${message:0:120}..."
        fi
        echo -e "  ${RED}WARN${NC} $object: $message"
    done <<< "$failed_events"
fi

echo ""
echo "--- Required Secrets ---"
check_secret_exists_verify "postgres-secret" "$NAMESPACE" || FAILURES=$((FAILURES + 1))
check_secret_exists_verify "admin-credentials" "$NAMESPACE" || FAILURES=$((FAILURES + 1))
check_secret_exists_verify "backend-config" "$NAMESPACE" || FAILURES=$((FAILURES + 1))
check_secret_exists_verify "supporting-services-proxy-session" "$NAMESPACE" || FAILURES=$((FAILURES + 1))

echo ""
echo "==================================="
if [ "$FAILURES" -eq 0 ]; then
    echo "All checks PASSED"
else
    echo "$FAILURES check(s) FAILED"
fi
echo "==================================="

exit $FAILURES
