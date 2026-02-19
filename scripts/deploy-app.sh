#!/bin/bash

# Deploy Multi-Agent Platform App to OpenShift
# Usage: ./scripts/deploy-app.sh [environment] [namespace]
# Requires: postgres-secret must exist (run deploy-db.sh first)

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
echo "Deploying Multi-Agent Platform App"
echo "==================================="
echo "Environment: $ENVIRONMENT"
echo "Namespace: $NAMESPACE"
echo ""

# Check if oc is available
if ! command -v oc &> /dev/null; then
    echo "Error: oc (OpenShift CLI) is not installed or not in PATH"
    exit 1
fi

# Check if logged in to OpenShift
if ! oc whoami &> /dev/null; then
    echo "Error: Not logged in to OpenShift. Please run 'oc login' first."
    exit 1
fi

# Check if postgres-secret exists
if ! oc get secret postgres-secret -n "$NAMESPACE" &> /dev/null; then
    echo "Error: postgres-secret not found in namespace $NAMESPACE"
    echo "Please run deploy-db.sh first to create the database."
    exit 1
fi

# Check if oauth-proxy-secret.env exists
OAUTH_SECRET_FILE="$PROJECT_ROOT/k8s/app/overlays/$ENVIRONMENT/oauth-proxy-secret.env"
if [[ ! -f "$OAUTH_SECRET_FILE" ]]; then
    echo "Error: OAuth secret file not found at $OAUTH_SECRET_FILE"
    echo "Please copy oauth-proxy-secret.env.example and configure it."
    exit 1
fi

# Check if backend config source exists
BACKEND_CONFIG_SOURCE="$PROJECT_ROOT/config/dev/.env"
if [[ ! -f "$BACKEND_CONFIG_SOURCE" ]]; then
    echo "Error: Backend config not found at $BACKEND_CONFIG_SOURCE"
    echo "Please copy config/dev/.env.example to config/dev/.env and configure it."
    exit 1
fi

# Verify backend-config was generated (deploy.sh runs generate-config.sh k8s upfront)
BACKEND_CONFIG_FILE="$PROJECT_ROOT/k8s/app/overlays/$ENVIRONMENT/backend-config.env"
if [[ ! -f "$BACKEND_CONFIG_FILE" ]]; then
    echo "Error: Failed to generate backend config at $BACKEND_CONFIG_FILE"
    echo "Please run: ./scripts/generate-config.sh k8s"
    exit 1
fi

# Create namespace if it doesn't exist
echo "Creating namespace if it doesn't exist..."
oc create namespace "$NAMESPACE" --dry-run=client -o yaml | oc apply -f -

# Auto-detect FRONTEND_HOST from Route if not already set in backend-config
ROUTE_HOST=$(oc get route multi-agent-platform -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
if [[ -n "$ROUTE_HOST" ]] && ! grep -q "^FRONTEND_HOST=" "$BACKEND_CONFIG_FILE" 2>/dev/null; then
    echo "Auto-detected Route: https://$ROUTE_HOST"
    echo "FRONTEND_HOST=https://$ROUTE_HOST" >> "$BACKEND_CONFIG_FILE"
    echo "BACKEND_CORS_ORIGINS=https://$ROUTE_HOST" >> "$BACKEND_CONFIG_FILE"
fi

# Apply app kustomize configuration
echo "Applying Multi-Agent Platform App configuration..."
oc apply -k "$PROJECT_ROOT/k8s/app/overlays/$ENVIRONMENT" -n "$NAMESPACE"

# Wait for app to be ready
echo "Waiting for app to be ready..."
oc rollout status deployment/multi-agent-platform -n "$NAMESPACE" --timeout=180s || true

# Get route URL
ROUTE_URL=$(oc get route multi-agent-platform -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null || echo "")

echo ""
echo "==================================="
echo "Multi-Agent Platform App deployment complete!"
echo "==================================="
if [[ -n "$ROUTE_URL" ]]; then
    echo "App URL: https://$ROUTE_URL"
fi
echo ""
echo "Check status: oc get pods -n $NAMESPACE -l app=multi-agent-platform"
