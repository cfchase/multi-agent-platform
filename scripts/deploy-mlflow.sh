#!/bin/bash

# Deploy MLFlow to OpenShift via Helm
# Usage: ./scripts/deploy-mlflow.sh [environment] [namespace]
# Requires: postgres-secret must exist

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
echo "Deploying MLFlow"
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

VALUES_FILE="$PROJECT_ROOT/helm/mlflow/values-${ENVIRONMENT}.yaml"
if [[ ! -f "$VALUES_FILE" ]]; then
    echo "Error: MLFlow values file not found at $VALUES_FILE"
    exit 1
fi

# Create namespace if it doesn't exist
echo "Creating namespace if it doesn't exist..."
oc create namespace "$NAMESPACE" --dry-run=client -o yaml | oc apply -f -

# Ensure mlflow database exists
echo "Ensuring mlflow database exists..."
oc exec -n "$NAMESPACE" deploy/postgres -- psql -U app -d postgres -tc \
    "SELECT 1 FROM pg_database WHERE datname = 'mlflow'" 2>/dev/null | grep -q 1 || \
    oc exec -n "$NAMESPACE" deploy/postgres -- psql -U app -d postgres -c \
    "CREATE DATABASE mlflow;" 2>/dev/null || echo "Database may already exist"

# Get PostgreSQL credentials from secret
echo "Reading PostgreSQL credentials..."
PG_USER=$(oc get secret postgres-secret -n "$NAMESPACE" -o jsonpath='{.data.POSTGRES_USER}' | base64 -d)
PG_PASS=$(oc get secret postgres-secret -n "$NAMESPACE" -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)

# Create temporary values file with secrets (avoids exposing password in process list)
TEMP_SECRETS=$(mktemp)
trap "rm -f $TEMP_SECRETS" EXIT
cat > "$TEMP_SECRETS" <<EOF
backendStore:
  postgres:
    user: "$PG_USER"
    password: "$PG_PASS"
auth:
  postgres:
    user: "$PG_USER"
    password: "$PG_PASS"
EOF

# Add Helm repo (community-charts)
echo "Adding MLFlow Helm repository..."
helm repo add community-charts https://community-charts.github.io/helm-charts 2>/dev/null || true
helm repo update

# Install or upgrade MLFlow
RELEASE_NAME="mlflow"

if helm status "$RELEASE_NAME" -n "$NAMESPACE" &>/dev/null; then
    echo "Upgrading MLFlow..."
    helm upgrade "$RELEASE_NAME" community-charts/mlflow \
        --namespace "$NAMESPACE" \
        --set podSecurityContext.fsGroup=null \
        --set securityContext.runAsUser=null \
        --set securityContext.runAsGroup=null \
        -f "$VALUES_FILE" \
        -f "$TEMP_SECRETS"
else
    echo "Installing MLFlow..."
    helm install "$RELEASE_NAME" community-charts/mlflow \
        --namespace "$NAMESPACE" \
        --create-namespace \
        --set podSecurityContext.fsGroup=null \
        --set securityContext.runAsUser=null \
        --set securityContext.runAsGroup=null \
        -f "$VALUES_FILE" \
        -f "$TEMP_SECRETS"
fi

# Create OpenShift route
echo "Creating MLFlow route..."
oc create route edge mlflow --service="${RELEASE_NAME}" --port=5000 -n "$NAMESPACE" 2>/dev/null || \
    echo "Route already exists"

# Create mlflow-credentials secret for app consumption (if it doesn't exist)
echo "Creating mlflow-credentials secret for app..."
if ! oc get secret mlflow-credentials -n "$NAMESPACE" &> /dev/null; then
    oc create secret generic mlflow-credentials \
        --from-literal=MLFLOW_TRACKING_URI="http://${RELEASE_NAME}:5000" \
        --from-literal=MLFLOW_EXPERIMENT_NAME="multi-agent-platform" \
        -n "$NAMESPACE"
    echo "Created mlflow-credentials secret"
else
    echo "mlflow-credentials secret already exists"
fi

# Wait for MLFlow to be ready
echo "Waiting for MLFlow to be ready..."
oc rollout status deployment/${RELEASE_NAME} -n "$NAMESPACE" --timeout=180s || true

# Get route URL
ROUTE_URL=$(oc get route mlflow -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null || echo "")

echo ""
echo "==================================="
echo "MLFlow deployment complete!"
echo "==================================="
if [[ -n "$ROUTE_URL" ]]; then
    echo "MLFlow URL: https://$ROUTE_URL"
fi
echo ""
echo "Check status: oc get pods -n $NAMESPACE -l app.kubernetes.io/instance=mlflow"
echo ""
echo "NOTE: Restart the app to pick up mlflow-credentials:"
echo "  oc rollout restart deployment/multi-agent-platform -n $NAMESPACE"
