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

# Create langflow-credentials secret from consolidated .env
# Contains LLM API keys and tracing config — loaded via envFrom in the post-renderer patch
# Only extract Langflow-relevant keys (LLM API keys, search APIs)
LANGFLOW_ENV_FILE="$PROJECT_ROOT/config/$ENVIRONMENT/.env"
LANGFLOW_KEYS="OPENAI_API_KEY|GEMINI_API_KEY|ANTHROPIC_API_KEY|OLLAMA_BASE_URL|TAVILY_API_KEY|GOOGLE_API_KEY|GOOGLE_CSE_ID|LANGFLOW_VARIABLES_TO_GET_FROM_ENVIRONMENT"

LITERAL_ARGS=()
if [[ -f "$LANGFLOW_ENV_FILE" ]]; then
    # Filter to Langflow-relevant, non-empty, non-comment key=value lines
    LANGFLOW_CREDS=$(grep -v '^\s*#' "$LANGFLOW_ENV_FILE" | grep -v '^\s*$' | grep -E "^(${LANGFLOW_KEYS})=." || true)
    if [[ -n "$LANGFLOW_CREDS" ]]; then
        while IFS= read -r line; do
            key="${line%%=*}"
            value="${line#*=}"
            [[ -z "$key" || -z "$value" ]] && continue
            LITERAL_ARGS+=("--from-literal=${key}=${value}")
        done <<< "$LANGFLOW_CREDS"
    fi
else
    echo "Warning: $LANGFLOW_ENV_FILE not found"
fi

# Inject Langfuse tracing keys from generated secrets-dev.yaml
# These are auto-generated API keys, not user-settable, so read from the artifact
LANGFUSE_SECRETS="$PROJECT_ROOT/helm/langfuse/secrets-${ENVIRONMENT}.yaml"
if [[ -f "$LANGFUSE_SECRETS" ]]; then
    # Extract additionalEnv value by name from YAML (e.g., "- name: KEY\n  value: VAL")
    _yaml_env_val() { awk "/name: ${1}\$/{getline; gsub(/.*value: *\"?/,\"\"); gsub(/\"? *$/,\"\"); print; exit}" "$2" 2>/dev/null; }
    LF_PK=$(_yaml_env_val "LANGFUSE_INIT_PROJECT_PUBLIC_KEY" "$LANGFUSE_SECRETS")
    LF_SK=$(_yaml_env_val "LANGFUSE_INIT_PROJECT_SECRET_KEY" "$LANGFUSE_SECRETS")
    if [[ -n "$LF_PK" ]]; then
        LITERAL_ARGS+=("--from-literal=LANGFUSE_PUBLIC_KEY=${LF_PK}")
    fi
    if [[ -n "$LF_SK" ]]; then
        LITERAL_ARGS+=("--from-literal=LANGFUSE_SECRET_KEY=${LF_SK}")
    fi
    if [[ -z "$LF_PK" || -z "$LF_SK" ]]; then
        echo "Warning: Could not extract Langfuse API keys from $LANGFUSE_SECRETS"
        echo "  LANGFUSE_PUBLIC_KEY: ${LF_PK:-(empty)}"
        echo "  LANGFUSE_SECRET_KEY: ${LF_SK:-(empty)}"
        echo "  Langflow tracing may not work. Verify secrets-${ENVIRONMENT}.yaml format."
    else
        echo "Added Langfuse tracing keys from secrets-${ENVIRONMENT}.yaml"
    fi
    # Langfuse internal service URL (Helm release "langfuse", service "langfuse-web" on port 3000)
    LITERAL_ARGS+=("--from-literal=LANGFUSE_HOST=http://langfuse-web:3000")
else
    echo "Warning: $LANGFUSE_SECRETS not found — Langfuse tracing not configured"
fi

if [[ ${#LITERAL_ARGS[@]} -gt 0 ]]; then
    if oc get secret langflow-credentials -n "$NAMESPACE" &>/dev/null; then
        if ! oc delete secret langflow-credentials -n "$NAMESPACE"; then
            echo "Error: Failed to delete existing langflow-credentials secret."
            echo "  Check RBAC permissions: oc auth can-i delete secrets -n $NAMESPACE"
            exit 1
        fi
    fi
    oc create secret generic langflow-credentials \
        "${LITERAL_ARGS[@]}" -n "$NAMESPACE"
    echo "Created langflow-credentials secret (${#LITERAL_ARGS[@]} keys)"
else
    echo "No credentials to configure — skipping langflow-credentials secret"
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
    oc create sa supporting-services-proxy -n "$NAMESPACE" 2>/dev/null || true
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
if ! oc rollout status statefulset/${RELEASE_NAME}-service -n "$NAMESPACE" --timeout=300s; then
    echo ""
    echo "Warning: LangFlow did not become ready within 300s"
    echo "  Check pod status: oc get pods -n $NAMESPACE -l app=langflow-service"
    echo "  Check logs: oc logs -n $NAMESPACE -l app=langflow-service --tail=50"
    echo "  Continuing with remaining deployments..."
fi

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
echo "Backend connects to Langflow via internal service URL (langflow-service-backend:7860, auto-configured)."
