#!/bin/bash
# Generate Kubernetes secrets from backend/.env values
# Does NOT overwrite existing files - skips if they already exist

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."

# Source common utilities (logging functions, colors)
source "$SCRIPT_DIR/lib/common.sh"

# Source files
BACKEND_ENV="${PROJECT_ROOT}/backend/.env"

# Target files
OAUTH_SECRET_FILE="${PROJECT_ROOT}/k8s/app/overlays/dev/oauth-proxy-secret.env"
LANGFLOW_SECRET_FILE="${PROJECT_ROOT}/k8s/langflow/overlays/dev/langflow-secret.env"

# Load value from env file
get_env_value() {
    local file="$1"
    local key="$2"
    grep -E "^${key}=" "$file" 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'" || true
}

generate_oauth_secret() {
    if [ -f "$OAUTH_SECRET_FILE" ]; then
        log_warn "OAuth secret file already exists: $OAUTH_SECRET_FILE"
        log_warn "Skipping to avoid overwriting. Delete it first if you want to regenerate."
        return 0
    fi

    if [ ! -f "$BACKEND_ENV" ]; then
        log_error "Backend .env file not found: $BACKEND_ENV"
        log_error "Copy backend/.env.example to backend/.env first"
        return 1
    fi

    # Try OAUTH_* first, fall back to GOOGLE_* for legacy support
    local client_id=$(get_env_value "$BACKEND_ENV" "OAUTH_CLIENT_ID")
    local client_secret=$(get_env_value "$BACKEND_ENV" "OAUTH_CLIENT_SECRET")
    local cookie_secret=$(get_env_value "$BACKEND_ENV" "OAUTH_COOKIE_SECRET")

    # Legacy fallback
    if [ -z "$client_id" ]; then
        client_id=$(get_env_value "$BACKEND_ENV" "GOOGLE_CLIENT_ID")
    fi
    if [ -z "$client_secret" ]; then
        client_secret=$(get_env_value "$BACKEND_ENV" "GOOGLE_CLIENT_SECRET")
    fi

    # Validate we have values
    if [ -z "$client_id" ] || [ "$client_id" = "your-client-id" ]; then
        log_warn "OAUTH_CLIENT_ID not configured in backend/.env"
        log_warn "Using placeholder - you'll need to update the generated file"
        client_id="your-client-id"
    fi

    if [ -z "$client_secret" ] || [ "$client_secret" = "your-client-secret" ]; then
        log_warn "OAUTH_CLIENT_SECRET not configured in backend/.env"
        log_warn "Using placeholder - you'll need to update the generated file"
        client_secret="your-client-secret"
    fi

    # Generate cookie secret if not set or is placeholder
    if [ -z "$cookie_secret" ] || [ "$cookie_secret" = "changethis_generate_a_secure_random_key" ]; then
        cookie_secret=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)
        log_info "Generated new cookie secret"
    fi

    log_info "Generating OAuth secret file: $OAUTH_SECRET_FILE"

    cat > "$OAUTH_SECRET_FILE" <<EOF
# OAuth2-Proxy Secrets
# Generated from backend/.env on $(date)
# DO NOT commit this file to git!

client-id=${client_id}
client-secret=${client_secret}
cookie-secret=${cookie_secret}
EOF

    log_info "Created $OAUTH_SECRET_FILE"

    if [ "$client_id" = "your-client-id" ] || [ "$client_secret" = "your-client-secret" ]; then
        log_warn "Placeholder values used - update the file with real OAuth credentials before deploying"
    fi
}

generate_langflow_secret() {
    if [ -f "$LANGFLOW_SECRET_FILE" ]; then
        log_warn "LangFlow secret file already exists: $LANGFLOW_SECRET_FILE"
        log_warn "Skipping to avoid overwriting. Delete it first if you want to regenerate."
        return 0
    fi

    if [ ! -f "$BACKEND_ENV" ]; then
        log_error "Backend .env file not found: $BACKEND_ENV"
        return 1
    fi

    local pg_user=$(get_env_value "$BACKEND_ENV" "POSTGRES_USER")
    local pg_pass=$(get_env_value "$BACKEND_ENV" "POSTGRES_PASSWORD")

    # Use defaults if not set
    pg_user="${pg_user:-app}"
    pg_pass="${pg_pass:-changethis}"

    log_info "Generating LangFlow secret file: $LANGFLOW_SECRET_FILE"

    # Ensure directory exists
    mkdir -p "$(dirname "$LANGFLOW_SECRET_FILE")"

    cat > "$LANGFLOW_SECRET_FILE" <<EOF
# LangFlow Database Secret
# Generated from backend/.env on $(date)
# DO NOT commit this file to git!

database-url=postgresql://${pg_user}:${pg_pass}@postgres:5432/langflow
EOF

    log_info "Created $LANGFLOW_SECRET_FILE"
}

show_help() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  oauth     Generate OAuth proxy secrets"
    echo "  langflow  Generate LangFlow database secrets"
    echo "  all       Generate all secrets (default)"
    echo "  help      Show this help message"
    echo ""
    echo "Source: backend/.env"
    echo "Targets:"
    echo "  - k8s/app/overlays/dev/oauth-proxy-secret.env"
    echo "  - k8s/langflow/overlays/dev/langflow-secret.env"
    echo ""
    echo "Note: Existing files are NOT overwritten. Delete them first to regenerate."
}

case "${1:-all}" in
    oauth)
        generate_oauth_secret
        ;;
    langflow)
        generate_langflow_secret
        ;;
    all)
        log_info "Generating all Kubernetes secrets from backend/.env..."
        generate_oauth_secret
        generate_langflow_secret
        log_info "Done!"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
