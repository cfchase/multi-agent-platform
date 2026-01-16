#!/bin/bash

# Deploy PostgreSQL to OpenShift
# Usage: ./scripts/deploy-db.sh [environment] [namespace]

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
echo "Deploying PostgreSQL"
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

# Create namespace if it doesn't exist
echo "Creating namespace if it doesn't exist..."
oc create namespace "$NAMESPACE" --dry-run=client -o yaml | oc apply -f -

# Apply postgres kustomize configuration
echo "Applying PostgreSQL configuration..."
oc apply -k "$PROJECT_ROOT/k8s/postgres/overlays/$ENVIRONMENT" -n "$NAMESPACE"

# Wait for postgres to be ready
echo "Waiting for PostgreSQL to be ready..."
oc rollout status deployment/postgres -n "$NAMESPACE" --timeout=120s || true

echo ""
echo "==================================="
echo "PostgreSQL deployment complete!"
echo "==================================="
echo "Check status: oc get pods -n $NAMESPACE -l app=postgres"
