#!/bin/bash

# Import flows from configured sources into LangFlow
# Usage: ./scripts/import-flows.sh [config-file]
#
# This script:
# 1. Reads flow sources from config (local dirs, git repos)
# 2. Clones/pulls git repositories
# 3. Imports flow JSON files into LangFlow via API
#
# Environment variables:
#   LANGFLOW_URL      - LangFlow API URL (default: http://localhost:7860)
#   LANGFLOW_API_KEY  - LangFlow API key (optional)
#   FLOW_SOURCE_PATH  - Simple mode: single local path to import
#   GITHUB_FLOW_TOKEN - Token for private git repos

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
CONFIG_FILE="${1:-$PROJECT_ROOT/config/flow-sources.yaml}"
LANGFLOW_URL="${LANGFLOW_URL:-http://localhost:7860}"
CACHE_DIR="${FLOW_CACHE_DIR:-/tmp/flow-cache}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Check if LangFlow is accessible
check_langflow() {
    log_info "Checking LangFlow connectivity at $LANGFLOW_URL..."
    if curl -s --fail "$LANGFLOW_URL/health" > /dev/null 2>&1; then
        log_info "LangFlow is accessible"
        return 0
    else
        log_error "Cannot connect to LangFlow at $LANGFLOW_URL"
        log_error "Make sure LangFlow is running (make langflow-start)"
        return 1
    fi
}

# Import a single flow JSON file to LangFlow
import_flow() {
    local json_file="$1"
    local flow_name=$(basename "$json_file" .json)

    log_info "Importing flow: $flow_name"

    # Build curl command with optional API key
    local auth_header=""
    if [[ -n "$LANGFLOW_API_KEY" ]]; then
        auth_header="-H \"Authorization: Bearer $LANGFLOW_API_KEY\""
    fi

    # Import via LangFlow API
    # Note: LangFlow API for importing flows may vary by version
    # This uses the /api/v1/flows endpoint
    local response
    response=$(curl -s -X POST "$LANGFLOW_URL/api/v1/flows/" \
        -H "Content-Type: application/json" \
        $auth_header \
        -d @"$json_file" 2>&1)

    if echo "$response" | grep -q '"id"'; then
        log_info "  ✓ Imported: $flow_name"
        return 0
    else
        # Check if flow already exists (might need update instead)
        log_warn "  Could not import $flow_name (may already exist)"
        log_warn "  Response: $response"
        return 1
    fi
}

# Scan a directory and import all flow JSON files
import_from_directory() {
    local dir="$1"
    local source_name="$2"

    if [[ ! -d "$dir" ]]; then
        log_warn "Directory not found: $dir"
        return 1
    fi

    log_info "Scanning directory: $dir"

    local count=0
    for json_file in "$dir"/*.json; do
        if [[ -f "$json_file" ]]; then
            import_flow "$json_file" && ((count++)) || true
        fi
    done

    log_info "Imported $count flows from $source_name"
}

# Clone or pull a git repository
sync_git_repo() {
    local url="$1"
    local branch="$2"
    local name="$3"
    local token="$4"

    local repo_dir="$CACHE_DIR/$name"
    mkdir -p "$CACHE_DIR"

    # Build authenticated URL if token provided
    local clone_url="$url"
    if [[ -n "$token" && "$url" == *"github.com"* ]]; then
        clone_url="${url/https:\/\/github.com/https:\/\/$token@github.com}"
    fi

    if [[ -d "$repo_dir/.git" ]]; then
        log_info "Pulling updates for $name..."
        (cd "$repo_dir" && git pull --ff-only) || log_warn "Pull failed, using cached version"
    else
        log_info "Cloning $url to $repo_dir..."
        git clone --branch "$branch" --depth 1 "$clone_url" "$repo_dir" || {
            log_error "Failed to clone $url"
            return 1
        }
    fi

    echo "$repo_dir"
}

# Parse YAML config and import flows
# Note: This is a simple parser - for complex configs, use Python
import_from_config() {
    local config_file="$1"

    if [[ ! -f "$config_file" ]]; then
        log_warn "Config file not found: $config_file"
        return 1
    fi

    log_info "Reading config: $config_file"

    # For now, just import from default examples
    # Full YAML parsing would require Python or yq
    log_warn "Full YAML config parsing not implemented in bash"
    log_info "Use Python import tool for advanced config: python scripts/import_flows.py"
}

# Simple mode: import from single path
import_simple() {
    local path="$1"

    if [[ -d "$path" ]]; then
        import_from_directory "$path" "local"
    else
        log_error "Path not found: $path"
        return 1
    fi
}

# Main
main() {
    echo "========================================"
    echo "LangFlow Flow Importer"
    echo "========================================"
    echo ""

    # Check LangFlow connectivity
    check_langflow || exit 1

    echo ""

    # Check for simple mode (FLOW_SOURCE_PATH env var)
    if [[ -n "$FLOW_SOURCE_PATH" ]]; then
        log_info "Simple mode: importing from $FLOW_SOURCE_PATH"
        import_simple "$FLOW_SOURCE_PATH"
        exit 0
    fi

    # Check for config file
    if [[ -f "$CONFIG_FILE" ]]; then
        import_from_config "$CONFIG_FILE"
    else
        # Default: import from built-in examples
        log_info "No config found, importing built-in examples..."
        import_from_directory "$PROJECT_ROOT/langflow-flows/examples" "examples"
    fi

    echo ""
    echo "========================================"
    echo "Import complete!"
    echo "========================================"
}

main "$@"
