#!/bin/bash

# Undeploy all components from OpenShift
# Usage: ./scripts/undeploy.sh [environment] [namespace]

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
echo "Undeploying All Components"
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

# Undeploy in reverse order
echo "Step 1/5: Uninstalling Langfuse..."
oc delete route langfuse -n "$NAMESPACE" 2>/dev/null || true
helm uninstall langfuse -n "$NAMESPACE" 2>/dev/null || echo "Langfuse not installed"
oc delete secret langfuse-credentials -n "$NAMESPACE" 2>/dev/null || true
echo ""

echo "Step 2/5: Removing MLFlow..."
oc delete route mlflow -n "$NAMESPACE" 2>/dev/null || true
helm uninstall mlflow -n "$NAMESPACE" 2>/dev/null || echo "MLFlow not installed via Helm"
# Fallback: Try Kustomize if Helm not used
oc delete -k "$PROJECT_ROOT/k8s/mlflow/overlays/$ENVIRONMENT" -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
oc delete secret mlflow-credentials mlflow-db-secret -n "$NAMESPACE" 2>/dev/null || true
echo ""

echo "Step 3/5: Removing LangFlow..."
oc delete route langflow -n "$NAMESPACE" 2>/dev/null || true
helm uninstall langflow -n "$NAMESPACE" 2>/dev/null || echo "LangFlow not installed via Helm"
# Fallback: Try Kustomize if Helm not used
oc delete -k "$PROJECT_ROOT/k8s/langflow/overlays/$ENVIRONMENT" -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
oc delete secret langflow-credentials -n "$NAMESPACE" 2>/dev/null || true
echo ""

echo "Step 4/5: Removing Multi-Agent Platform App..."
oc delete -k "$PROJECT_ROOT/k8s/app/overlays/$ENVIRONMENT" -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
echo ""

echo "Step 5/5: Removing PostgreSQL..."
oc delete -k "$PROJECT_ROOT/k8s/postgres/overlays/$ENVIRONMENT" -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
oc delete secret admin-credentials -n "$NAMESPACE" 2>/dev/null || true
echo ""

echo "==================================="
echo "All components removed!"
echo "==================================="
echo ""
echo "Note: PVCs may still exist. To fully clean up:"
echo "  oc delete pvc --all -n $NAMESPACE"
echo ""
echo "To delete the namespace entirely:"
echo "  oc delete namespace $NAMESPACE"
