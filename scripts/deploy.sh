#!/bin/bash

# Deploy all components to OpenShift
# Usage: ./scripts/deploy.sh [environment] [namespace]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ENVIRONMENT=${1:-dev}
NAMESPACE=${2:-deep-research-${ENVIRONMENT}}

if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
    echo "Error: Environment must be 'dev' or 'prod'"
    exit 1
fi

echo "==================================="
echo "Deploying All Components"
echo "==================================="
echo "Environment: $ENVIRONMENT"
echo "Namespace: $NAMESPACE"
echo ""

# Deploy components in order
# Note: App deploys LAST so it picks up all credential secrets from AI tools

echo "Step 1/5: Deploying PostgreSQL..."
"$SCRIPT_DIR/deploy-db.sh" "$ENVIRONMENT" "$NAMESPACE"
echo ""

# Generate admin credentials (required by LangFlow and Langfuse)
echo "Generating admin credentials if needed..."
if ! oc get secret admin-credentials -n "$NAMESPACE" &> /dev/null; then
    ADMIN_EMAIL="admin@localhost.local"
    ADMIN_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
    oc create secret generic admin-credentials \
        --from-literal=email="$ADMIN_EMAIL" \
        --from-literal=password="$ADMIN_PASS" \
        -n "$NAMESPACE"
    echo "Created admin-credentials secret"
    echo "  Email: $ADMIN_EMAIL"
    echo "  Password: $ADMIN_PASS"
else
    echo "admin-credentials already exists"
fi
echo ""

echo "Step 2/5: Deploying LangFlow..."
"$SCRIPT_DIR/deploy-langflow.sh" "$ENVIRONMENT" "$NAMESPACE"
echo ""

echo "Step 3/5: Deploying MLFlow..."
"$SCRIPT_DIR/deploy-mlflow.sh" "$ENVIRONMENT" "$NAMESPACE"
echo ""

echo "Step 4/5: Deploying Langfuse..."
"$SCRIPT_DIR/deploy-langfuse.sh" "$ENVIRONMENT" "$NAMESPACE"
echo ""

echo "Step 5/5: Deploying Deep Research App..."
"$SCRIPT_DIR/deploy-app.sh" "$ENVIRONMENT" "$NAMESPACE"
echo ""

echo "==================================="
echo "All components deployed!"
echo "==================================="
echo ""
echo "Check status:"
echo "  oc get pods -n $NAMESPACE"
echo "  oc get routes -n $NAMESPACE"
echo ""
echo "Get admin credentials:"
echo "  make get-admin-credentials"
