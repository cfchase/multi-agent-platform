#!/bin/bash

# Undeploy all components from OpenShift
# Usage: ./scripts/undeploy.sh [environment] [--clean]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
source "$SCRIPT_DIR/lib/common.sh"

# Parse args: extract --clean flag, positional args for environment
CLEAN=false
ENVIRONMENT="dev"
for arg in "$@"; do
    case "$arg" in
        --clean) CLEAN=true ;;
        *) ENVIRONMENT="$arg" ;;
    esac
done
NAMESPACE="multi-agent-platform-${ENVIRONMENT}"

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

# Undeploy in reverse dependency order (opposite of deploy.sh):
# Deploy: namespace → postgres → langfuse → mlflow → langflow → app
# Undeploy: app → langflow → mlflow → langfuse → shared resources → postgres
echo "Step 1/5: Removing Multi-Agent Platform App..."
oc delete -k "$PROJECT_ROOT/k8s/app/overlays/$ENVIRONMENT" -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
oc delete secret backend-config -n "$NAMESPACE" 2>/dev/null || true
echo ""

echo "Step 2/5: Removing LangFlow..."
oc delete route langflow -n "$NAMESPACE" 2>/dev/null || true
oc delete service langflow-external -n "$NAMESPACE" 2>/dev/null || true
oc delete statefulset -l release=langflow -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
oc delete all,configmap,secret,serviceaccount -l release=langflow -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
oc delete -k "$PROJECT_ROOT/k8s/langflow/overlays/$ENVIRONMENT" -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
echo ""

echo "Step 3/5: Removing MLFlow..."
oc delete route mlflow -n "$NAMESPACE" 2>/dev/null || true
oc delete service mlflow-external -n "$NAMESPACE" 2>/dev/null || true
oc delete all,configmap,secret,serviceaccount -l app.kubernetes.io/instance=mlflow -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
oc delete -k "$PROJECT_ROOT/k8s/mlflow/overlays/$ENVIRONMENT" -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
echo ""

echo "Step 4/5: Removing Langfuse..."
oc delete route langfuse -n "$NAMESPACE" 2>/dev/null || true
oc delete statefulset -l app.kubernetes.io/instance=langfuse -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
oc delete all,configmap,secret,serviceaccount,role,rolebinding -l app.kubernetes.io/instance=langfuse -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
echo ""

echo "Removing shared OAuth resources and admin credentials..."
oc delete sa supporting-services-proxy -n "$NAMESPACE" 2>/dev/null || true
oc delete secret supporting-services-proxy-session -n "$NAMESPACE" 2>/dev/null || true
oc delete secret admin-credentials -n "$NAMESPACE" 2>/dev/null || true
echo ""

echo "Step 5/5: Removing PostgreSQL..."
oc delete -k "$PROJECT_ROOT/k8s/postgres/overlays/$ENVIRONMENT" -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
echo ""

echo "==================================="
echo "All components removed!"
echo "==================================="

# Clean mode: delete PVCs and namespace
if [[ "$CLEAN" == "true" ]]; then
    echo ""
    echo "Waiting for pods to terminate..."
    oc wait --for=delete pod --all -n "$NAMESPACE" --timeout=60s 2>/dev/null || true

    echo "Cleaning up PVCs..."
    oc delete pvc --all -n "$NAMESPACE" 2>/dev/null || true

    GROUP_NAME="${NAMESPACE}-admins"
    echo "Removing admin group $GROUP_NAME..."
    oc delete group "$GROUP_NAME" 2>/dev/null || true

    echo "Deleting namespace $NAMESPACE..."
    oc delete namespace "$NAMESPACE" 2>/dev/null || true

    echo ""
    echo "Full cleanup complete (PVCs, admin group, and namespace deleted)"
else
    echo ""
    echo "Note: PVCs still exist. To fully clean up:"
    echo "  oc delete pvc --all -n $NAMESPACE"
    echo "  oc delete namespace $NAMESPACE"
    echo "Or use: make undeploy-clean"
fi
