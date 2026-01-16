#!/bin/bash
# Common utilities for development scripts
# Source this file: source "$(dirname "$0")/lib/common.sh"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    if [ "${DEBUG:-false}" = "true" ]; then
        echo -e "${BLUE}[DEBUG]${NC} $1"
    fi
}

# Get the directory where this script is located
COMMON_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Auto-detect container tool using the shared detection script
autodetect_container_tool() {
    "$COMMON_SCRIPT_DIR/detect-container-tool.sh"
}

# Initialize container tool with priority:
# 1. First argument (if provided)
# 2. Environment variable CONTAINER_TOOL
# 3. Auto-detect using autodetect_container_tool
#
# Usage: init_container_tool [container_tool_arg]
init_container_tool() {
    local arg="${1:-}"

    # Priority 1: passed argument
    if [ -n "$arg" ]; then
        CONTAINER_TOOL="$arg"
        log_debug "Using CONTAINER_TOOL from argument: $CONTAINER_TOOL"
    # Priority 2: environment variable (already set)
    elif [ -n "$CONTAINER_TOOL" ]; then
        log_debug "Using CONTAINER_TOOL from environment: $CONTAINER_TOOL"
    # Priority 3: auto-detect
    else
        CONTAINER_TOOL=$(autodetect_container_tool) || return 1
        log_debug "Auto-detected container tool: $CONTAINER_TOOL"
    fi

    export CONTAINER_TOOL

    # Validate the container tool
    if [[ "$CONTAINER_TOOL" != "podman" && "$CONTAINER_TOOL" != "docker" ]]; then
        log_error "CONTAINER_TOOL must be either 'podman' or 'docker', got: $CONTAINER_TOOL"
        return 1
    fi

    if ! command -v "$CONTAINER_TOOL" &> /dev/null; then
        log_error "$CONTAINER_TOOL is not installed or not in PATH"
        return 1
    fi

    if ! $CONTAINER_TOOL info >/dev/null 2>&1; then
        log_error "$CONTAINER_TOOL is not running or not accessible"
        return 1
    fi

    log_debug "Container tool initialized: $CONTAINER_TOOL"
    return 0
}

# Check if a container exists (running or stopped)
container_exists() {
    local name="$1"
    $CONTAINER_TOOL ps -a --format '{{.Names}}' | grep -q "^${name}$"
}

# Check if a container is running
container_running() {
    local name="$1"
    $CONTAINER_TOOL ps --format '{{.Names}}' | grep -q "^${name}$"
}

# Wait for a container to be healthy
wait_for_healthy() {
    local name="$1"
    local timeout="${2:-30}"
    local interval="${3:-1}"

    log_info "Waiting for $name to be healthy (timeout: ${timeout}s)..."

    for ((i=0; i<timeout; i+=interval)); do
        local health=$($CONTAINER_TOOL inspect --format='{{.State.Health.Status}}' "$name" 2>/dev/null || echo "none")
        if [ "$health" = "healthy" ]; then
            log_info "$name is healthy"
            return 0
        fi
        sleep "$interval"
    done

    log_error "$name failed to become healthy within ${timeout}s"
    return 1
}

# ============================================
# OpenShift/Kubernetes Deployment Functions
# ============================================

# Check if oc is available
check_oc_installed() {
    if ! command -v oc &> /dev/null; then
        log_error "oc (OpenShift CLI) is not installed or not in PATH"
        exit 1
    fi
}

# Check if helm is available
check_helm_installed() {
    if ! command -v helm &> /dev/null; then
        log_error "helm is not installed or not in PATH"
        exit 1
    fi
}

# Check if logged in to OpenShift
check_openshift_login() {
    if ! oc whoami &> /dev/null; then
        log_error "Not logged in to OpenShift. Please run 'oc login' first."
        exit 1
    fi
}

# Check if a secret exists in the namespace
check_secret_exists() {
    local secret_name="$1"
    local namespace="$2"
    local error_msg="${3:-Secret $secret_name not found in namespace $namespace}"

    if ! oc get secret "$secret_name" -n "$namespace" &> /dev/null; then
        log_error "$error_msg"
        return 1
    fi
    return 0
}

# Create namespace if it doesn't exist
ensure_namespace() {
    local namespace="$1"
    log_info "Creating namespace if it doesn't exist..."
    oc create namespace "$namespace" --dry-run=client -o yaml | oc apply -f -
}

# Ensure a database exists in PostgreSQL
ensure_database() {
    local db_name="$1"
    local namespace="$2"

    log_info "Ensuring $db_name database exists..."
    oc exec -n "$namespace" deploy/postgres -- psql -U app -d postgres -tc \
        "SELECT 1 FROM pg_database WHERE datname = '$db_name'" 2>/dev/null | grep -q 1 || \
        oc exec -n "$namespace" deploy/postgres -- psql -U app -d postgres -c \
        "CREATE DATABASE $db_name;" 2>/dev/null || echo "Database may already exist"
}

# Wait for a Kubernetes deployment to be ready
wait_for_k8s_deployment() {
    local deployment_name="$1"
    local namespace="$2"
    local timeout="${3:-180s}"

    log_info "Waiting for $deployment_name to be ready..."
    oc rollout status deployment/"$deployment_name" -n "$namespace" --timeout="$timeout" || true
}

# Wait for a Kubernetes statefulset to be ready
wait_for_k8s_statefulset() {
    local statefulset_name="$1"
    local namespace="$2"
    local timeout="${3:-180s}"

    log_info "Waiting for $statefulset_name to be ready..."
    oc rollout status statefulset/"$statefulset_name" -n "$namespace" --timeout="$timeout" || true
}

# Create an OpenShift edge route if it doesn't exist
create_route() {
    local route_name="$1"
    local service_name="$2"
    local port="$3"
    local namespace="$4"

    log_info "Creating $route_name route..."
    oc create route edge "$route_name" --service="$service_name" --port="$port" -n "$namespace" 2>/dev/null || \
        echo "Route already exists"
}

# Get route URL
get_route_url() {
    local route_name="$1"
    local namespace="$2"

    oc get route "$route_name" -n "$namespace" -o jsonpath='{.spec.host}' 2>/dev/null || echo ""
}

# Standard deploy script header
print_deploy_header() {
    local component="$1"
    local environment="$2"
    local namespace="$3"

    echo "==================================="
    echo "Deploying $component"
    echo "==================================="
    echo "Environment: $environment"
    echo "Namespace: $namespace"
    echo ""
}

# Standard deploy script footer
print_deploy_footer() {
    local component="$1"
    local route_url="$2"

    echo ""
    echo "==================================="
    echo "$component deployment complete!"
    echo "==================================="
    if [[ -n "$route_url" ]]; then
        echo "$component URL: https://$route_url"
    fi
    echo ""
}
