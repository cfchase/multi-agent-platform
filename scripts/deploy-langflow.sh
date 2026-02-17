#!/bin/bash

# Deploy LangFlow to OpenShift via Helm
# Usage: ./scripts/deploy-langflow.sh [environment] [namespace]
# Requires: postgres-secret, admin-credentials must exist

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

ENVIRONMENT=${1:-dev}
NAMESPACE=${2:-multi-agent-platform-${ENVIRONMENT}}

if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
    echo "Error: Environment must be 'dev' or 'prod'"
    exit 1
fi

echo "==================================="
echo "Deploying LangFlow"
echo "==================================="
echo "Environment: $ENVIRONMENT"
echo "Namespace: $NAMESPACE"
echo ""

# Check if oc is available
if ! command -v oc &> /dev/null; then
    echo "Error: oc (OpenShift CLI) is not installed or not in PATH"
    exit 1
fi

# Check if helm is available
if ! command -v helm &> /dev/null; then
    echo "Error: helm is not installed or not in PATH"
    exit 1
fi

# Check if logged in to OpenShift
if ! oc whoami &> /dev/null; then
    echo "Error: Not logged in to OpenShift. Please run 'oc login' first."
    exit 1
fi

# Check prerequisites
if ! oc get secret postgres-secret -n "$NAMESPACE" &> /dev/null; then
    echo "Error: postgres-secret not found in namespace $NAMESPACE"
    echo "Please run deploy-db.sh first."
    exit 1
fi

if ! oc get secret admin-credentials -n "$NAMESPACE" &> /dev/null; then
    echo "Error: admin-credentials not found in namespace $NAMESPACE"
    echo "Please run: make generate-admin-secret-dev"
    exit 1
fi

VALUES_FILE="$PROJECT_ROOT/helm/langflow/values-${ENVIRONMENT}.yaml"
if [[ ! -f "$VALUES_FILE" ]]; then
    echo "Error: LangFlow values file not found at $VALUES_FILE"
    exit 1
fi

# Create langflow-credentials secret from config/dev/.env.langflow
# Contains LLM API keys and tracing config — loaded via envFrom in the post-renderer patch
LANGFLOW_ENV_FILE="$PROJECT_ROOT/config/$ENVIRONMENT/.env.langflow"
if [[ -f "$LANGFLOW_ENV_FILE" ]]; then
    # Filter to non-empty, non-comment key=value lines
    LANGFLOW_CREDS=$(grep -v '^\s*#' "$LANGFLOW_ENV_FILE" | grep -v '^\s*$' | grep '=.' || true)
    if [[ -n "$LANGFLOW_CREDS" ]]; then
        # Build --from-literal args for each non-empty key
        LITERAL_ARGS=()
        while IFS= read -r line; do
            key="${line%%=*}"
            value="${line#*=}"
            [[ -z "$key" || -z "$value" ]] && continue
            LITERAL_ARGS+=("--from-literal=${key}=${value}")
        done <<< "$LANGFLOW_CREDS"

        if [[ ${#LITERAL_ARGS[@]} -gt 0 ]]; then
            if oc get secret langflow-credentials -n "$NAMESPACE" &>/dev/null; then
                oc delete secret langflow-credentials -n "$NAMESPACE"
            fi
            oc create secret generic langflow-credentials \
                "${LITERAL_ARGS[@]}" -n "$NAMESPACE"
            echo "Created langflow-credentials secret (${#LITERAL_ARGS[@]} keys)"
        fi
    else
        echo "No non-empty values in $LANGFLOW_ENV_FILE — skipping langflow-credentials secret"
    fi
else
    echo "Warning: $LANGFLOW_ENV_FILE not found — langflow-credentials secret not created"
fi

# Add Helm repo
echo "Adding LangFlow Helm repository..."
helm repo add langflow https://langflow-ai.github.io/langflow-helm-charts 2>/dev/null || true
helm repo update

# Ensure langflow database exists
echo "Ensuring langflow database exists..."
oc exec -n "$NAMESPACE" deploy/postgres -- psql -U app -d postgres -tc \
    "SELECT 1 FROM pg_database WHERE datname = 'langflow'" 2>/dev/null | grep -q 1 || \
    oc exec -n "$NAMESPACE" deploy/postgres -- psql -U app -d postgres -c \
    "CREATE DATABASE langflow;" 2>/dev/null || echo "Database may already exist"

# Shared OAuth resources — created by deploy.sh orchestrator
# If running standalone, ensure they exist
if ! oc get sa supporting-services-proxy -n "$NAMESPACE" &>/dev/null; then
    echo "Warning: supporting-services-proxy SA not found. Run deploy.sh for full setup."
    echo "Creating basic OAuth resources for standalone deployment..."
    oc create sa supporting-services-proxy -n "$NAMESPACE"
    oc annotate sa supporting-services-proxy -n "$NAMESPACE" --overwrite \
        "serviceaccounts.openshift.io/oauth-redirectreference.langflow={\"kind\":\"OAuthRedirectReference\",\"apiVersion\":\"v1\",\"reference\":{\"kind\":\"Route\",\"name\":\"langflow\"}}"
    if ! oc get secret supporting-services-proxy-session -n "$NAMESPACE" &>/dev/null; then
        SESSION_SECRET=$(openssl rand -base64 32 | head -c 43)
        oc create secret generic supporting-services-proxy-session \
            --from-literal=session_secret="$SESSION_SECRET" -n "$NAMESPACE"
    fi
fi

# Substitute namespace placeholder in post-renderer patch
POST_RENDERER_DIR="$PROJECT_ROOT/helm/langflow/post-renderer"
PATCH_TEMPLATE="$POST_RENDERER_DIR/oauth-proxy-patch.yaml"
PATCH_BACKUP=$(mktemp)
trap "cp '$PATCH_BACKUP' '$PATCH_TEMPLATE'; rm -f '$PATCH_BACKUP' '$POST_RENDERER_DIR/helm-output.yaml'" EXIT

# Save original and substitute namespace
cp "$PATCH_TEMPLATE" "$PATCH_BACKUP"
sed -i.bak "s/NAMESPACE_PLACEHOLDER/$NAMESPACE/g" "$PATCH_TEMPLATE"
rm -f "${PATCH_TEMPLATE}.bak"

# Render and apply LangFlow with Kustomize post-renderer for OAuth proxy sidecar
# Pipeline: helm template → kustomize patch (adds OAuth proxy) → oc apply
# See helm/langflow/post-renderer/ for the Kustomize-based patches.
RELEASE_NAME="langflow"
echo "Rendering and applying LangFlow manifests..."
helm template "$RELEASE_NAME" langflow/langflow-ide \
    --namespace "$NAMESPACE" \
    --version 0.1.1 \
    -f "$VALUES_FILE" \
    | "$POST_RENDERER_DIR/kustomize.sh" \
    | oc apply -n "$NAMESPACE" -f -

# Apply updated Route and external Service (replaces the old oc create route command)
echo "Applying Langflow Route and external Service..."
oc apply -f "$PROJECT_ROOT/k8s/langflow/base/service.yaml" -n "$NAMESPACE"
oc apply -f "$PROJECT_ROOT/k8s/langflow/base/route.yaml" -n "$NAMESPACE"

# Wait for LangFlow to be ready (Helm chart creates a StatefulSet, not Deployment)
echo "Waiting for LangFlow to be ready (this may take a few minutes)..."
oc rollout status statefulset/${RELEASE_NAME}-service -n "$NAMESPACE" --timeout=300s || true

# Get route URL
ROUTE_URL=$(oc get route langflow -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null || echo "")

echo ""
echo "==================================="
echo "LangFlow deployment complete!"
echo "==================================="
if [[ -n "$ROUTE_URL" ]]; then
    echo "LangFlow URL (OAuth protected): https://$ROUTE_URL"
fi
echo ""
echo "Access requires OpenShift OAuth login with namespace edit permission."
echo "Internal backend access via langflow-service-backend:7860 bypasses OAuth."
echo ""
echo "Check status: oc get pods -n $NAMESPACE -l app=langflow-service"
echo ""
echo "NOTE: Backend reads Langflow URL from backend-config secret."
echo "  Ensure config/dev/.env.backend has LANGFLOW_URL set correctly."
