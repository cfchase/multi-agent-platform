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

# Install or upgrade LangFlow
RELEASE_NAME="langflow"
if helm status "$RELEASE_NAME" -n "$NAMESPACE" &>/dev/null; then
    echo "Upgrading LangFlow..."
    helm upgrade "$RELEASE_NAME" langflow/langflow-ide \
        --namespace "$NAMESPACE" \
        -f "$VALUES_FILE"
else
    echo "Installing LangFlow..."
    helm install "$RELEASE_NAME" langflow/langflow-ide \
        --namespace "$NAMESPACE" \
        --create-namespace \
        -f "$VALUES_FILE"
fi

# Create OpenShift route (Helm chart creates langflow-service for frontend on 8080)
echo "Creating LangFlow route..."
oc create route edge langflow --service="${RELEASE_NAME}-service" --port=8080 -n "$NAMESPACE" 2>/dev/null || \
    echo "Route already exists"

# Create langflow-credentials secret for app consumption (if it doesn't exist)
echo "Creating langflow-credentials secret for app..."
if ! oc get secret langflow-credentials -n "$NAMESPACE" &> /dev/null; then
    oc create secret generic langflow-credentials \
        --from-literal=LANGFLOW_URL="http://${RELEASE_NAME}-service-backend:7860" \
        -n "$NAMESPACE"
    echo "Created langflow-credentials secret"
else
    echo "langflow-credentials secret already exists"
fi

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
    echo "LangFlow URL: https://$ROUTE_URL"
fi
echo ""
echo "Login with admin credentials:"
echo "  make get-admin-credentials"
echo ""
echo "Check status: oc get pods -n $NAMESPACE -l app.kubernetes.io/instance=langflow"
echo ""
echo "NOTE: Restart the app to pick up langflow-credentials:"
echo "  oc rollout restart deployment/multi-agent-platform -n $NAMESPACE"
