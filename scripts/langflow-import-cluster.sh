#!/bin/bash

# Import flows into cluster Langflow via port-forward
# Usage: ./scripts/langflow-import-cluster.sh [environment] [namespace]
# Requires: oc login, Langflow pod running, config/ENV/flow-sources.yaml

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
source "$SCRIPT_DIR/lib/common.sh"

ENVIRONMENT=${1:-dev}
NAMESPACE=${2:-multi-agent-platform-${ENVIRONMENT}}
LOCAL_PORT=${LANGFLOW_IMPORT_PORT:-17860}
CONFIG_FILE="$PROJECT_ROOT/config/${ENVIRONMENT}/flow-sources.yaml"

# Validate environment
if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
    log_error "Environment must be 'dev' or 'prod', got: $ENVIRONMENT"
    exit 1
fi

# Print header
echo "==================================="
echo "Importing Flows to Cluster Langflow"
echo "==================================="
echo "Environment: $ENVIRONMENT"
echo "Namespace: $NAMESPACE"
echo ""

# Check prerequisites
check_oc_installed
check_openshift_login

# Check config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    log_error "Config file not found: $CONFIG_FILE"
    log_error "Copy from ${CONFIG_FILE}.example and customize for your environment."
    exit 1
fi

# Check Langflow pod is running
log_info "Checking Langflow pod status in $NAMESPACE..."
if ! oc get pods -l app=langflow-service -n "$NAMESPACE" --no-headers 2>/dev/null | grep -q Running; then
    log_error "Langflow pod is not running in $NAMESPACE"
    log_error "Deploy Langflow first: make deploy-langflow ENV=$ENVIRONMENT"
    exit 1
fi
log_info "Langflow pod is running"

# Start port-forward (use backend service — Helm chart separates frontend/backend)
log_info "Starting port-forward (localhost:$LOCAL_PORT -> langflow-service-backend:7860)..."
oc port-forward svc/langflow-service-backend "$LOCAL_PORT":7860 -n "$NAMESPACE" &
PF_PID=$!
trap "kill $PF_PID 2>/dev/null || true" EXIT

# Wait for port-forward to be ready
sleep 2
for i in $(seq 1 10); do
    if curl -s "http://localhost:$LOCAL_PORT/health" > /dev/null 2>&1; then
        log_info "Port-forward ready, Langflow accessible at localhost:$LOCAL_PORT"
        break
    fi
    if [ "$i" -eq 10 ]; then
        log_error "Port-forward failed or Langflow not responding after 10 attempts"
        exit 1
    fi
    sleep 2
done

# Run import
log_info "Cluster mode: components and MCP servers will be skipped (local filesystem only)"
log_info "Importing flows from $CONFIG_FILE..."
echo ""

LANGFLOW_CLUSTER_MODE=1 \
LANGFLOW_URL="http://localhost:$LOCAL_PORT" \
    uv run --with requests --with pyyaml \
    python "$PROJECT_ROOT/scripts/import_flows.py" "$CONFIG_FILE"

IMPORT_EXIT=$?

echo ""
echo "==================================="
if [ $IMPORT_EXIT -eq 0 ]; then
    echo "Cluster flow import complete!"
else
    echo "Cluster flow import failed! (exit code: $IMPORT_EXIT)"
fi
echo "==================================="
echo ""

exit $IMPORT_EXIT
