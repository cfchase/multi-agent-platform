#!/bin/bash

# Deploy Langfuse to OpenShift via Helm
# Usage: ./scripts/deploy-langfuse.sh [environment] [namespace]
# Requires: postgres-secret, admin-credentials must exist

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

ENVIRONMENT=${1:-dev}
NAMESPACE=${2:-deep-research-${ENVIRONMENT}}

if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
    echo "Error: Environment must be 'dev' or 'prod'"
    exit 1
fi

echo "==================================="
echo "Deploying Langfuse"
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

# Generate secrets file if it doesn't exist
SECRETS_FILE="$PROJECT_ROOT/helm/langfuse/secrets-${ENVIRONMENT}.yaml"
if [[ ! -f "$SECRETS_FILE" ]]; then
    echo "Generating Langfuse secrets..."
    "$SCRIPT_DIR/generate-langfuse-secrets.sh"
fi

# Check secrets file exists
if [[ ! -f "$SECRETS_FILE" ]]; then
    echo "Error: Langfuse secrets file not found at $SECRETS_FILE"
    exit 1
fi

VALUES_FILE="$PROJECT_ROOT/helm/langfuse/values-${ENVIRONMENT}.yaml"
if [[ ! -f "$VALUES_FILE" ]]; then
    echo "Error: Langfuse values file not found at $VALUES_FILE"
    exit 1
fi

# Add Helm repo
echo "Adding Langfuse Helm repository..."
helm repo add langfuse https://langfuse.github.io/langfuse-k8s 2>/dev/null || true
helm repo update

# Ensure langfuse database exists
echo "Ensuring langfuse database exists..."
oc exec -n "$NAMESPACE" deploy/postgres -- psql -U app -d postgres -tc \
    "SELECT 1 FROM pg_database WHERE datname = 'langfuse'" 2>/dev/null | grep -q 1 || \
    oc exec -n "$NAMESPACE" deploy/postgres -- psql -U app -d postgres -c \
    "CREATE DATABASE langfuse;" 2>/dev/null || echo "Database may already exist"

# Install or upgrade Langfuse
RELEASE_NAME="langfuse"
if helm status "$RELEASE_NAME" -n "$NAMESPACE" &>/dev/null; then
    echo "Upgrading Langfuse..."
    helm upgrade "$RELEASE_NAME" langfuse/langfuse \
        --namespace "$NAMESPACE" \
        -f "$VALUES_FILE" \
        -f "$SECRETS_FILE"
else
    echo "Installing Langfuse..."
    helm install "$RELEASE_NAME" langfuse/langfuse \
        --namespace "$NAMESPACE" \
        --create-namespace \
        -f "$VALUES_FILE" \
        -f "$SECRETS_FILE"
fi

# Create OpenShift route
echo "Creating Langfuse route..."
oc create route edge langfuse --service="${RELEASE_NAME}-web" --port=3000 -n "$NAMESPACE" 2>/dev/null || \
    echo "Route already exists"

# Create langfuse-credentials secret for app consumption (if it doesn't exist)
echo "Creating langfuse-credentials secret for app..."
if ! oc get secret langfuse-credentials -n "$NAMESPACE" &> /dev/null; then
    # Get the route URL for external access
    ROUTE_URL=$(oc get route langfuse -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null || echo "")

    # Note: For proper API key generation, you'd need to call Langfuse API after it's running
    # For now, we set the internal URL - API keys need to be created via Langfuse UI
    oc create secret generic langfuse-credentials \
        --from-literal=LANGFUSE_HOST="http://${RELEASE_NAME}-web:3000" \
        -n "$NAMESPACE"
    echo "Created langfuse-credentials secret"
    echo ""
    echo "NOTE: To get API keys for the app:"
    echo "  1. Log into Langfuse UI"
    echo "  2. Go to Settings > API Keys"
    echo "  3. Create a new API key"
    echo "  4. Update the secret:"
    echo "     oc patch secret langfuse-credentials -n $NAMESPACE -p '{\"stringData\":{\"LANGFUSE_PUBLIC_KEY\":\"pk-...\",\"LANGFUSE_SECRET_KEY\":\"sk-...\"}}'"
else
    echo "langfuse-credentials secret already exists"
fi

# Wait for Langfuse to be ready
echo "Waiting for Langfuse to be ready..."
oc rollout status deployment/${RELEASE_NAME}-web -n "$NAMESPACE" --timeout=300s || true

# Get route URL
ROUTE_URL=$(oc get route langfuse -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null || echo "")

echo ""
echo "==================================="
echo "Langfuse deployment complete!"
echo "==================================="
if [[ -n "$ROUTE_URL" ]]; then
    echo "Langfuse URL: https://$ROUTE_URL"
fi
echo ""
echo "Login with admin credentials:"
echo "  make get-admin-credentials"
echo ""
echo "Check status: oc get pods -n $NAMESPACE -l app.kubernetes.io/instance=langfuse"
echo ""
echo "NOTE: Restart the app to pick up langfuse-credentials:"
echo "  oc rollout restart deployment/deep-research -n $NAMESPACE"
