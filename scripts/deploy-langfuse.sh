#!/bin/bash

# Deploy Langfuse to OpenShift via Helm
# Usage: ./scripts/deploy-langfuse.sh [environment] [namespace]
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

# Auto-calculate LANGFUSE_NEXTAUTH_URL from OpenShift apps domain
# Exported as env var for generate-config.sh envsubst pipeline (never written to user config files)
APPS_DOMAIN_ERR=$(mktemp)
APPS_DOMAIN=$(oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}' 2>"$APPS_DOMAIN_ERR" || echo "")
if [[ -n "$APPS_DOMAIN" ]]; then
    export LANGFUSE_NEXTAUTH_URL="https://langfuse-${NAMESPACE}.${APPS_DOMAIN}"
    echo "Auto-calculated LANGFUSE_NEXTAUTH_URL=${LANGFUSE_NEXTAUTH_URL}"
else
    echo "Warning: Could not detect OpenShift apps domain."
    if [[ -s "$APPS_DOMAIN_ERR" ]]; then
        echo "  Reason: $(cat "$APPS_DOMAIN_ERR")"
    fi
    # Check if LANGFUSE_NEXTAUTH_URL is set from consolidated .env
    LANGFUSE_ENV_FILE="$PROJECT_ROOT/config/${ENVIRONMENT}/.env"
    if [[ -f "$LANGFUSE_ENV_FILE" ]]; then
        set -a; source "$LANGFUSE_ENV_FILE"; set +a
    fi
    if [[ -z "$LANGFUSE_NEXTAUTH_URL" || "$LANGFUSE_NEXTAUTH_URL" == "auto-calculated-by-deploy-script" ]]; then
        echo "Error: LANGFUSE_NEXTAUTH_URL cannot be auto-calculated and is not set in config/${ENVIRONMENT}/.env"
        echo "Please set it manually in config/${ENVIRONMENT}/.env"
        echo "Example: LANGFUSE_NEXTAUTH_URL=https://langfuse-${NAMESPACE}.apps.your-cluster.example.com"
        rm -f "$APPS_DOMAIN_ERR"
        exit 1
    fi
    echo "Using LANGFUSE_NEXTAUTH_URL from config/${ENVIRONMENT}/.env"
fi
rm -f "$APPS_DOMAIN_ERR"

# Always regenerate secrets from source of truth (config/dev/.env)
SECRETS_FILE="$PROJECT_ROOT/helm/langfuse/secrets-${ENVIRONMENT}.yaml"
echo "Generating Langfuse secrets..."
"$SCRIPT_DIR/generate-config.sh" helm-langfuse --force

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

# Render and apply Langfuse manifests
RELEASE_NAME="langfuse"
echo "Rendering and applying Langfuse manifests..."
helm template "$RELEASE_NAME" langfuse/langfuse \
    --namespace "$NAMESPACE" \
    --version 1.5.19 \
    -f "$VALUES_FILE" \
    -f "$SECRETS_FILE" \
    | oc apply -n "$NAMESPACE" -f -

# Create OpenShift route
echo "Creating Langfuse route..."
oc create route edge langfuse --service="${RELEASE_NAME}-web" --port=3000 -n "$NAMESPACE" 2>/dev/null || \
    echo "Route already exists"

# Wait for Langfuse to be ready
echo "Waiting for Langfuse to be ready..."
if ! oc rollout status deployment/${RELEASE_NAME}-web -n "$NAMESPACE" --timeout=300s; then
    echo ""
    echo "Warning: Langfuse did not become ready within 300s"
    echo "  Check pod status: oc get pods -n $NAMESPACE -l app.kubernetes.io/instance=langfuse"
    echo "  Check logs: oc logs -n $NAMESPACE -l app.kubernetes.io/name=langfuse-web --tail=50"
    echo "  Continuing with remaining deployments..."
fi

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
echo "Backend connects to Langfuse via internal service URL (langfuse-web:3000, auto-configured)."
