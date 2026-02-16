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

# Shared OAuth resources — created by deploy.sh orchestrator
# If running standalone, ensure they exist
if ! oc get sa supporting-services-proxy -n "$NAMESPACE" &>/dev/null; then
    echo "Warning: supporting-services-proxy SA not found. Run deploy.sh for full setup."
    echo "Creating basic OAuth resources for standalone deployment..."
    oc create sa supporting-services-proxy -n "$NAMESPACE"
    oc annotate sa supporting-services-proxy -n "$NAMESPACE" --overwrite \
        "serviceaccounts.openshift.io/oauth-redirectreference.mlflow={\"kind\":\"OAuthRedirectReference\",\"apiVersion\":\"v1\",\"reference\":{\"kind\":\"Route\",\"name\":\"mlflow\"}}"
    if ! oc get secret supporting-services-proxy-session -n "$NAMESPACE" &>/dev/null; then
        SESSION_SECRET=$(openssl rand -base64 32 | head -c 43)
        oc create secret generic supporting-services-proxy-session \
            --from-literal=session_secret="$SESSION_SECRET" -n "$NAMESPACE"
    fi
fi

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
# Also substitute namespace placeholder for OAuth SAR configuration
TEMP_SECRETS=$(mktemp)
TEMP_VALUES=$(mktemp)
trap "rm -f $TEMP_SECRETS $TEMP_VALUES" EXIT

cat > "$TEMP_SECRETS" <<EOF
backendStore:
  postgres:
    user: "$PG_USER"
    password: "$PG_PASS"
EOF

# Substitute namespace placeholder in values file for SAR configuration
sed "s/NAMESPACE_PLACEHOLDER/$NAMESPACE/g" "$VALUES_FILE" > "$TEMP_VALUES"

# Add Helm repo (community-charts)
echo "Adding MLFlow Helm repository..."
helm repo add community-charts https://community-charts.github.io/helm-charts 2>/dev/null || true
helm repo update

# Render and apply MLFlow manifests
RELEASE_NAME="mlflow"
echo "Rendering and applying MLFlow manifests..."
helm template "$RELEASE_NAME" community-charts/mlflow \
    --namespace "$NAMESPACE" \
    --version 1.8.1 \
    --set podSecurityContext.fsGroup=null \
    --set securityContext.runAsUser=null \
    --set securityContext.runAsGroup=null \
    -f "$TEMP_VALUES" \
    -f "$TEMP_SECRETS" \
    | oc apply -n "$NAMESPACE" -f -

# Apply kustomize manifests for Route and external Service
echo "Applying MLFlow Route and external Service..."
oc apply -f "$PROJECT_ROOT/k8s/mlflow/base/service.yaml" -n "$NAMESPACE"
oc apply -f "$PROJECT_ROOT/k8s/mlflow/base/route.yaml" -n "$NAMESPACE"

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
    echo ""
    echo "Authentication: Protected by OpenShift OAuth"
    echo "Access requires namespace edit permission (pods update verb)"
fi
echo ""
echo "Check status: oc get pods -n $NAMESPACE -l app.kubernetes.io/instance=mlflow"
echo "  (Should show 2/2 containers ready: mlflow + oauth-proxy)"
echo ""
echo "NOTE: Backend reads MLflow URI from backend-config secret."
echo "  Ensure config/dev/.env.backend has MLFLOW_TRACKING_URI set correctly."
