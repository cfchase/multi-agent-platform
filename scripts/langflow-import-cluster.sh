#!/bin/bash

# Full cluster import: stage components/MCP locally, copy to pod, import flows
# Usage: ./scripts/langflow-import-cluster.sh [environment] [namespace]
# Requires: oc login, Langflow pod running, config/ENV/flow-sources.yaml

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
source "$SCRIPT_DIR/lib/common.sh"

ENVIRONMENT=${1:-dev}
NAMESPACE=${2:-multi-agent-platform-${ENVIRONMENT}}
LOCAL_PORT=${LANGFLOW_IMPORT_PORT:-17860}
CONFIG_FILE="$PROJECT_ROOT/config/${ENVIRONMENT}/flow-sources.yaml"
CONTAINER="langflow-ide"
POD_CONFIG_DIR="/tmp/langflow"
POD_PACKAGES_DIR="$POD_CONFIG_DIR/packages"
POD_COMPONENTS_DIR="$POD_CONFIG_DIR/components"
STATEFULSET="langflow-service"

# Staging directory (cleaned up on exit)
STAGING_DIR=""

cleanup() {
    if [ -n "$STAGING_DIR" ] && [ -d "$STAGING_DIR" ]; then
        rm -rf "$STAGING_DIR"
    fi
    # Kill port-forward if running
    if [ -n "${PF_PID:-}" ]; then
        kill "$PF_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Validate environment
if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
    log_error "Environment must be 'dev' or 'prod', got: $ENVIRONMENT"
    exit 1
fi

# Print header
echo "==========================================="
echo "Full Cluster Import (Components + MCP + Flows)"
echo "==========================================="
echo "Environment: $ENVIRONMENT"
echo "Namespace: $NAMESPACE"
echo ""

# --- Step 1: Validate prerequisites ---
check_oc_installed
check_openshift_login

if [ ! -f "$CONFIG_FILE" ]; then
    log_error "Config file not found: $CONFIG_FILE"
    log_error "Copy from ${CONFIG_FILE}.example and customize for your environment."
    exit 1
fi

# --- Step 2: Find Langflow pod ---
log_info "Checking Langflow pod status in $NAMESPACE..."
POD_NAME=$(oc get pods -l app=$STATEFULSET -n "$NAMESPACE" --no-headers -o custom-columns=":metadata.name" 2>/dev/null | grep Running -m1 || true)

if [ -z "$POD_NAME" ]; then
    # Try getting pod name without status filter (status is in a different column)
    POD_NAME=$(oc get pods -l app=$STATEFULSET -n "$NAMESPACE" --no-headers 2>/dev/null | grep Running | awk '{print $1}' | head -1)
fi

if [ -z "$POD_NAME" ]; then
    log_error "Langflow pod is not running in $NAMESPACE"
    log_error "Deploy Langflow first: make deploy-langflow ENV=$ENVIRONMENT"
    exit 1
fi
log_info "Found Langflow pod: $POD_NAME"

# --- Step 3: Stage locally ---
STAGING_DIR=$(mktemp -d)
log_info "Staging components and MCP configs to $STAGING_DIR..."

uv run --with requests --with pyyaml \
    python "$PROJECT_ROOT/scripts/import_flows.py" \
    --stage "$STAGING_DIR" "$CONFIG_FILE" \
    --pod-packages-dir "$POD_PACKAGES_DIR"

STAGE_EXIT=$?
if [ $STAGE_EXIT -ne 0 ]; then
    log_error "Staging failed (exit code: $STAGE_EXIT)"
    exit 1
fi

# --- Step 4: Read manifest ---
MANIFEST="$STAGING_DIR/manifest.json"
if [ ! -f "$MANIFEST" ]; then
    log_error "Manifest not found at $MANIFEST"
    exit 1
fi

# Parse manifest using python (portable JSON parsing)
HAS_COMPONENTS=$(python3 -c "
import json, sys
m = json.load(open('$MANIFEST'))
print('yes' if m.get('components', {}).get('categories') else 'no')
")

HAS_MCP=$(python3 -c "
import json, sys
m = json.load(open('$MANIFEST'))
print('yes' if m.get('mcp_servers') else 'no')
")

PIP_DEPS=$(python3 -c "
import json
m = json.load(open('$MANIFEST'))
deps = m.get('pip_dependencies', [])
print(' '.join(deps) if deps else '')
")

NEEDS_RESTART="no"
NEEDS_PYTHONPATH=""  # "set" or "append" — deferred until after all oc exec calls
NEEDS_COMPONENTS_PATH=""  # "set" — deferred until after all oc exec calls

# --- Step 5: Copy components to pod ---
if [ "$HAS_COMPONENTS" = "yes" ]; then
    log_info ""
    log_info "=== Copying Components to Pod ==="

    # Ensure components directory exists on pod
    oc exec "$POD_NAME" -c "$CONTAINER" -n "$NAMESPACE" -- \
        mkdir -p "$POD_COMPONENTS_DIR"

    # Copy each category directory
    CATEGORIES=$(python3 -c "
import json
m = json.load(open('$MANIFEST'))
print(' '.join(m.get('components', {}).get('categories', [])))
")

    for category in $CATEGORIES; do
        STAGING_CAT="$STAGING_DIR/components/$category"
        if [ -d "$STAGING_CAT" ]; then
            log_info "Copying components/$category/ to pod..."
            # Copy to parent dir so oc cp creates components/{category}/ (not {category}/{category}/)
            oc cp "$STAGING_CAT" "$POD_NAME:$POD_COMPONENTS_DIR/" \
                -c "$CONTAINER" -n "$NAMESPACE"
        fi
    done

    NEEDS_RESTART="yes"
    log_info "Components copied to pod"
fi

# --- Step 5b: Install pip dependencies on pod ---
if [ -n "$PIP_DEPS" ]; then
    log_info ""
    log_info "=== Installing pip Dependencies on Pod ==="

    # Ensure packages directory exists
    oc exec "$POD_NAME" -c "$CONTAINER" -n "$NAMESPACE" -- \
        mkdir -p "$POD_PACKAGES_DIR"

    log_info "Installing: $PIP_DEPS"
    oc exec "$POD_NAME" -c "$CONTAINER" -n "$NAMESPACE" -- \
        pip install --target "$POD_PACKAGES_DIR" --upgrade --quiet $PIP_DEPS

    # Clean up shadowed packages
    log_info "Cleaning up shadowed packages..."
    oc exec "$POD_NAME" -c "$CONTAINER" -n "$NAMESPACE" -- \
        python3 -c "
import json, shutil, os

manifest = json.load(open('$POD_CONFIG_DIR/manifest.json')) if os.path.exists('$POD_CONFIG_DIR/manifest.json') else {}
# Use inline list if manifest not on pod
provided = set($(python3 -c "
import json
m = json.load(open('$MANIFEST'))
print(repr(m.get('langflow_provided_packages', [])))
"))

target = '$POD_PACKAGES_DIR'
removed = []
for item in os.listdir(target):
    path = os.path.join(target, item)
    base = item.split('-')[0].replace('.dist', '').replace('.py', '')
    if item.endswith('.so'):
        base = item.split('.')[0]
    if base.lower() in provided or base.lstrip('_') in provided:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.unlink(path)
        removed.append(item)
if removed:
    print(f'Cleaned {len(removed)} shadowed package(s)')
"

    # Check if PYTHONPATH needs updating (deferred to step 7 to avoid
    # triggering a StatefulSet rollout while we still need the current pod)
    CURRENT_PYTHONPATH=$(oc get statefulset "$STATEFULSET" -n "$NAMESPACE" \
        -o jsonpath='{.spec.template.spec.containers[?(@.name=="'"$CONTAINER"'")].env[?(@.name=="PYTHONPATH")].value}' 2>/dev/null || echo "")

    if [ -z "$CURRENT_PYTHONPATH" ]; then
        NEEDS_PYTHONPATH="set"
    elif [[ "$CURRENT_PYTHONPATH" != *"$POD_PACKAGES_DIR"* ]]; then
        NEEDS_PYTHONPATH="append"
    else
        log_info "PYTHONPATH already includes $POD_PACKAGES_DIR"
    fi

    NEEDS_RESTART="yes"
fi

# Check if LANGFLOW_COMPONENTS_PATH needs setting (deferred to step 7)
if [ "$HAS_COMPONENTS" = "yes" ]; then
    CURRENT_COMPONENTS_PATH=$(oc get statefulset "$STATEFULSET" -n "$NAMESPACE" \
        -o jsonpath='{.spec.template.spec.containers[?(@.name=="'"$CONTAINER"'")].env[?(@.name=="LANGFLOW_COMPONENTS_PATH")].value}' 2>/dev/null || echo "")

    if [ -z "$CURRENT_COMPONENTS_PATH" ]; then
        NEEDS_COMPONENTS_PATH="set"
    elif [[ "$CURRENT_COMPONENTS_PATH" != *"$POD_COMPONENTS_DIR"* ]]; then
        NEEDS_COMPONENTS_PATH="set"
    else
        log_info "LANGFLOW_COMPONENTS_PATH already includes $POD_COMPONENTS_DIR"
    fi
fi

# --- Step 6: Register MCP servers on pod ---
if [ "$HAS_MCP" = "yes" ]; then
    log_info ""
    log_info "=== Registering MCP Servers on Pod ==="

    # Read MCP entries from manifest and merge into project config files on pod
    MCP_JSON=$(python3 -c "
import json
m = json.load(open('$MANIFEST'))
print(json.dumps(m.get('mcp_servers', {})))
")

    oc exec "$POD_NAME" -c "$CONTAINER" -n "$NAMESPACE" -- \
        python3 -c "
import json, glob, os

mcp_servers = json.loads('$MCP_JSON')
config_dir = '$POD_CONFIG_DIR'

# Find all per-project MCP config files
pattern = os.path.join(config_dir, '*', '_mcp_servers_*.json')
config_files = glob.glob(pattern)

if not config_files:
    print('No MCP config files found - servers will need manual registration')
else:
    added_total = 0
    for cf in config_files:
        try:
            data = json.load(open(cf))
            servers = data.setdefault('mcpServers', {})
            added = 0
            for name, entry in mcp_servers.items():
                if name not in servers:
                    servers[name] = entry
                    added += 1
            if added > 0:
                json.dump(data, open(cf, 'w'), indent=4)
                added_total += added
                print(f'Added {added} server(s) to {os.path.basename(cf)}')
        except Exception as e:
            print(f'Failed to update {cf}: {e}')
    if added_total > 0:
        print(f'Registered {added_total} MCP server(s) total')
    else:
        print('All MCP servers already registered')
"
    NEEDS_RESTART="yes"
fi

# --- Step 7: Restart pod if needed ---
if [ "$NEEDS_RESTART" = "yes" ]; then
    log_info ""
    log_info "=== Restarting Langflow Pod ==="

    # Apply deferred env var updates — oc set env mutates the StatefulSet
    # spec, which triggers a rollout automatically (new pod replaces old one).
    ENV_CHANGED="no"

    if [ "$NEEDS_PYTHONPATH" = "set" ]; then
        log_info "Setting PYTHONPATH=$POD_PACKAGES_DIR on StatefulSet..."
        oc set env statefulset/"$STATEFULSET" -c "$CONTAINER" -n "$NAMESPACE" \
            "PYTHONPATH=$POD_PACKAGES_DIR"
        ENV_CHANGED="yes"
    elif [ "$NEEDS_PYTHONPATH" = "append" ]; then
        log_info "Updating PYTHONPATH to include $POD_PACKAGES_DIR..."
        oc set env statefulset/"$STATEFULSET" -c "$CONTAINER" -n "$NAMESPACE" \
            "PYTHONPATH=$CURRENT_PYTHONPATH:$POD_PACKAGES_DIR"
        ENV_CHANGED="yes"
    fi

    if [ "$NEEDS_COMPONENTS_PATH" = "set" ]; then
        log_info "Setting LANGFLOW_COMPONENTS_PATH=$POD_COMPONENTS_DIR on StatefulSet..."
        oc set env statefulset/"$STATEFULSET" -c "$CONTAINER" -n "$NAMESPACE" \
            "LANGFLOW_COMPONENTS_PATH=$POD_COMPONENTS_DIR"
        ENV_CHANGED="yes"
    fi

    if [ "$ENV_CHANGED" = "no" ]; then
        # No env change needed — delete pod explicitly to pick up new components
        log_info "Deleting pod $POD_NAME (StatefulSet will recreate it)..."
        oc delete pod "$POD_NAME" -n "$NAMESPACE"
    fi

    log_info "Waiting for StatefulSet rollout..."
    wait_for_k8s_statefulset "$STATEFULSET" "$NAMESPACE" "300s"

    # Get new pod name after restart
    log_info "Waiting for new pod to be ready..."
    for i in $(seq 1 30); do
        NEW_POD=$(oc get pods -l app=$STATEFULSET -n "$NAMESPACE" --no-headers 2>/dev/null | grep Running | awk '{print $1}' | head -1)
        if [ -n "$NEW_POD" ]; then
            POD_NAME="$NEW_POD"
            log_info "New pod ready: $POD_NAME"
            break
        fi
        if [ "$i" -eq 30 ]; then
            log_error "New pod did not become ready"
            exit 1
        fi
        sleep 5
    done

    # Wait for Langflow health endpoint
    log_info "Waiting for Langflow to be healthy..."
    for i in $(seq 1 30); do
        HEALTH=$(oc exec "$POD_NAME" -c "$CONTAINER" -n "$NAMESPACE" -- \
            curl -s -o /dev/null -w '%{http_code}' http://localhost:7860/health 2>/dev/null || echo "000")
        if [ "$HEALTH" = "200" ]; then
            log_info "Langflow is healthy"
            break
        fi
        if [ "$i" -eq 30 ]; then
            log_error "Langflow did not become healthy"
            exit 1
        fi
        sleep 5
    done
fi

# --- Step 8: Port-forward and import flows ---
log_info ""
log_info "=== Importing Flows ==="
log_info "Starting port-forward (localhost:$LOCAL_PORT -> langflow-service-backend:7860)..."
oc port-forward svc/langflow-service-backend "$LOCAL_PORT":7860 -n "$NAMESPACE" &
PF_PID=$!

# Wait for port-forward to be ready
sleep 2
for i in $(seq 1 10); do
    if curl -s "http://localhost:$LOCAL_PORT/health" > /dev/null 2>&1; then
        log_info "Port-forward ready, Langflow accessible at localhost:$LOCAL_PORT"
        break
    fi
    if [ "$i" -eq 10 ]; then
        log_error "Port-forward failed or Langflow not responding after 10 attempts"
        exit 1
    fi
    sleep 2
done

# Import flows only (components and MCP already handled above)
log_info "Importing flows from $CONFIG_FILE..."
echo ""

LANGFLOW_CLUSTER_MODE=1 \
LANGFLOW_URL="http://localhost:$LOCAL_PORT" \
    uv run --with requests --with pyyaml \
    python "$PROJECT_ROOT/scripts/import_flows.py" "$CONFIG_FILE"

IMPORT_EXIT=$?

echo ""
echo "==========================================="
if [ $IMPORT_EXIT -eq 0 ]; then
    echo "Cluster import complete!"
    if [ "$NEEDS_RESTART" = "yes" ]; then
        echo "  - Components and/or MCP servers were installed on the pod"
    fi
    echo "  - Flows imported via API"
else
    echo "Cluster import failed! (exit code: $IMPORT_EXIT)"
fi
echo "==========================================="
echo ""

exit $IMPORT_EXIT
