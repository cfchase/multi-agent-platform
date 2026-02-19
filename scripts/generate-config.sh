#!/bin/bash

# Unified config generation script
# Reads from config/ as source of truth, generates target-specific formats
#
# Usage: ./scripts/generate-config.sh [command]
# Commands: local, dev, k8s, helm-langfuse, all, reset, help

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/.."
source "$SCRIPT_DIR/lib/common.sh"

CONFIG_LOCAL="$PROJECT_ROOT/config/local"
CONFIG_DEV="$PROJECT_ROOT/config/dev"

# ============================================
# Helper Functions
# ============================================

# Source an env file, exporting all variables
load_env() {
    local file="$1"
    if [ ! -f "$file" ]; then
        log_error "Config file not found: $file"
        return 1
    fi
    set -a
    source "$file"
    set +a
}

# Copy file if target doesn't exist
copy_if_missing() {
    local src="$1"
    local dest="$2"
    if [ -f "$dest" ]; then
        log_info "Already exists: $dest"
    else
        cp "$src" "$dest"
        log_info "Created: $dest"
    fi
}

# Copy source to dest, warning if dest exists and differs
warn_on_diff() {
    local src="$1"
    local dest="$2"
    local label="${3:-$dest}"
    if [ ! -f "$dest" ]; then
        cp "$src" "$dest"
        log_info "Created: $label"
    elif diff -q "$src" "$dest" >/dev/null 2>&1; then
        log_info "Up to date: $label"
    else
        log_warn "File differs from source: $label"
        diff --color "$src" "$dest" 2>/dev/null || diff "$src" "$dest" || true
        log_warn "To update: cp $src $dest"
    fi
}

# Validate access control files for cluster deployment
validate_access_control_files() {
    local config_dir="$1"
    local warnings=0

    local emails_file="$config_dir/allowed-emails.txt"
    if [ ! -f "$emails_file" ]; then
        log_warn "Missing: $emails_file (no users will be able to log in)"
        warnings=$((warnings + 1))
    else
        local email_count
        email_count=$(grep -cv '^\s*#\|^\s*$' "$emails_file" 2>/dev/null || echo 0)
        if [ "$email_count" -eq 0 ]; then
            log_warn "Empty: $emails_file (no users will be able to log in)"
            warnings=$((warnings + 1))
        elif grep -q "example.com" "$emails_file"; then
            log_warn "Placeholder emails in: $emails_file — replace with real addresses before deploying"
            warnings=$((warnings + 1))
        fi
    fi

    local admins_file="$config_dir/namespace-admins.txt"
    if [ ! -f "$admins_file" ]; then
        log_warn "Missing: $admins_file (no admin access to Langflow/MLflow)"
        warnings=$((warnings + 1))
    else
        local admin_count
        admin_count=$(grep -cv '^\s*#\|^\s*$' "$admins_file" 2>/dev/null || echo 0)
        if [ "$admin_count" -eq 0 ]; then
            log_warn "Empty: $admins_file (no admin access to Langflow/MLflow)"
            warnings=$((warnings + 1))
        elif grep -q "^user[12]$" "$admins_file"; then
            log_warn "Placeholder usernames in: $admins_file — replace with real OpenShift usernames before deploying"
            warnings=$((warnings + 1))
        fi
    fi

    return $warnings
}

# Get secret value: user-provided > existing artifact > generate new
# Implements idempotent secret generation — re-runs preserve existing values
get_or_generate_secret() {
    local user_val="$1"        # Value from user's .env (may be empty/placeholder)
    local artifact_file="$2"   # Path to existing artifact
    local artifact_key="$3"    # Grep key in artifact (e.g., "POSTGRES_PASSWORD" or "cookie-secret")
    local placeholder="$4"     # Placeholder string to detect
    local gen_cmd="$5"         # Command to generate new value

    # 1. User explicitly set a non-placeholder value
    if [ -n "$user_val" ] && [ "$user_val" != "$placeholder" ]; then
        echo "$user_val"
        return
    fi

    # 2. Reuse from existing artifact (idempotent)
    if [ -f "$artifact_file" ]; then
        local existing
        existing=$(grep "^${artifact_key}=" "$artifact_file" 2>/dev/null | head -1 | cut -d= -f2-)
        if [ -n "$existing" ] && [ "$existing" != "$placeholder" ]; then
            echo "$existing"
            return
        fi
    fi

    # 3. Generate new value
    local generated
    generated=$(eval "$gen_cmd" 2>/dev/null) || true
    if [ -z "$generated" ]; then
        log_error "Failed to generate value for $artifact_key"
        return 1
    fi
    echo "$generated"
}

# Extract a value from YAML artifact by searching for "name: KEY" then grabbing next "value:" line
# Used for idempotent Langfuse secret reuse from secrets-dev.yaml
get_yaml_env_value() {
    local yaml_file="$1"
    local env_name="$2"
    if [ ! -f "$yaml_file" ]; then
        echo ""
        return
    fi
    # Find line with "name: ENV_NAME" and get the value from the next line
    local value
    value=$(awk "/name: ${env_name}\$/{getline; gsub(/.*value: *\"?/,\"\"); gsub(/\"? *$/,\"\"); print; exit}" "$yaml_file" 2>/dev/null || echo "")
    echo "$value"
}

# Extract simple YAML value by key path (e.g., "password:" under a specific section)
# Returns first match — use for unique keys only
get_yaml_simple_value() {
    local yaml_file="$1"
    local key="$2"  # e.g., "password:" — matches first occurrence
    if [ ! -f "$yaml_file" ]; then
        echo ""
        return
    fi
    local value
    value=$(grep "${key}" "$yaml_file" 2>/dev/null | head -1 | sed 's/.*: *"\{0,1\}\([^"]*\)"\{0,1\} *$/\1/')
    echo "$value"
}

# envsubst with explicit variable list, or fallback if envsubst not available
envsubst_or_fallback() {
    local template="$1"
    local output="$2"
    local var_list="$3"

    if command -v envsubst &> /dev/null; then
        envsubst "$var_list" < "$template" > "$output"
    else
        log_error "envsubst is required but not found. Install gettext-base (apt) or gettext (brew)."
        return 1
    fi
}

# ============================================
# Subcommands
# ============================================

# Setup local development config files from examples
cmd_local() {
    log_info "Setting up local development config..."

    # Copy consolidated .env.example to .env if it doesn't exist
    copy_if_missing "$CONFIG_LOCAL/.env.example" "$CONFIG_LOCAL/.env"

    # Copy flow-sources.yaml.example if present
    if [ -f "$CONFIG_LOCAL/flow-sources.yaml.example" ]; then
        copy_if_missing "$CONFIG_LOCAL/flow-sources.yaml.example" "$CONFIG_LOCAL/flow-sources.yaml"
    fi

    # Always sync config/local/.env to backend/.env (source of truth is config/local/.env)
    if [ -f "$CONFIG_LOCAL/.env" ]; then
        cp "$CONFIG_LOCAL/.env" "$PROJECT_ROOT/backend/.env"
        log_info "Synced: backend/.env ← config/local/.env"
    fi

    # Create minimal frontend/.env if it doesn't exist
    if [ -f "$PROJECT_ROOT/frontend/.env" ]; then
        log_info "Already exists: frontend/.env"
    else
        echo "VITE_API_URL=http://localhost:8000" > "$PROJECT_ROOT/frontend/.env"
        log_info "Created: frontend/.env (VITE_API_URL=http://localhost:8000)"
    fi

    echo ""
    log_info "Local config setup complete"
    echo "  config/local/.env  - Set LLM keys and any overrides"
    echo "  backend/.env       - Copied from config/local/.env"
    echo "  frontend/.env      - VITE_API_URL (defaults to localhost:8000)"
}

# Setup cluster dev config files from examples (no secret generation, no mutation)
cmd_dev() {
    log_info "Setting up cluster dev config from examples..."

    # Copy consolidated .env.example to .env if it doesn't exist
    if [ ! -f "$CONFIG_DEV/.env" ]; then
        if [ -f "$CONFIG_DEV/.env.example" ]; then
            cp "$CONFIG_DEV/.env.example" "$CONFIG_DEV/.env"
            log_info "Created: config/dev/.env"
        else
            log_error "config/dev/.env.example not found — cannot initialize config"
            exit 1
        fi
    else
        log_info "Already exists: config/dev/.env"
    fi

    # Copy access control and flow-sources example files if missing
    copy_if_missing "$CONFIG_DEV/allowed-emails.txt.example" "$CONFIG_DEV/allowed-emails.txt"
    copy_if_missing "$CONFIG_DEV/namespace-admins.txt.example" "$CONFIG_DEV/namespace-admins.txt"
    if [ -f "$CONFIG_DEV/flow-sources.yaml.example" ]; then
        copy_if_missing "$CONFIG_DEV/flow-sources.yaml.example" "$CONFIG_DEV/flow-sources.yaml"
    fi

    # Validate access control files
    validate_access_control_files "$CONFIG_DEV" || true

    log_info "Dev config setup complete"
    echo ""
    echo "Configure these files before deploying:"
    echo "  config/dev/.env            - Set OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET, LLM keys"
    echo "  config/dev/allowed-emails.txt     - Email addresses for main app access"
    echo "  config/dev/namespace-admins.txt   - OpenShift usernames for Langflow/MLflow access"
    echo ""
    echo "Then run: make config-generate   (generates deployment artifacts with auto-generated secrets)"
}

# Generate Kubernetes secret .env files from config/dev/.env (single source)
cmd_k8s() {
    local force="${1:-}"

    log_info "Generating Kubernetes secret files from config/dev/.env..."

    if [ ! -f "$CONFIG_DEV/.env" ]; then
        log_error "Config not found: config/dev/.env — run 'generate-config.sh dev' first"
        exit 1
    fi

    load_env "$CONFIG_DEV/.env"

    # --- Artifact file paths ---
    local oauth_target="$PROJECT_ROOT/k8s/app/overlays/dev/oauth-proxy-secret.env"
    local postgres_target="$PROJECT_ROOT/k8s/postgres/overlays/dev/postgres-secret.env"
    local langflow_target="$PROJECT_ROOT/k8s/langflow/overlays/dev/langflow-secret.env"
    local backend_target="$PROJECT_ROOT/k8s/app/overlays/dev/backend-config.env"
    local emails_target="$PROJECT_ROOT/k8s/app/overlays/dev/allowed-emails.txt"

    # --- Compute secrets (idempotent: user-provided > existing artifact > generate) ---

    local pg_password
    pg_password=$(get_or_generate_secret \
        "${POSTGRES_PASSWORD:-}" "$postgres_target" "POSTGRES_PASSWORD" "changethis" \
        "python3 -c \"import secrets; print(secrets.token_urlsafe(16))\" 2>/dev/null || openssl rand -base64 16")

    local pg_user="${POSTGRES_USER:-app}"
    local pg_db="${POSTGRES_DB:-app}"
    local pg_port="${POSTGRES_PORT:-5432}"

    local secret_key
    secret_key=$(get_or_generate_secret \
        "${SECRET_KEY:-}" "$backend_target" "SECRET_KEY" "" \
        "python3 -c \"import secrets; print(secrets.token_urlsafe(32))\" 2>/dev/null || openssl rand -base64 32")

    local token_enc_key
    token_enc_key=$(get_or_generate_secret \
        "${TOKEN_ENCRYPTION_KEY:-}" "$backend_target" "TOKEN_ENCRYPTION_KEY" "" \
        "python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\" 2>/dev/null || echo ''")
    if [ -z "$token_enc_key" ]; then
        log_warn "Could not auto-generate TOKEN_ENCRYPTION_KEY (cryptography package not available)"
    fi

    local cookie_secret
    cookie_secret=$(get_or_generate_secret \
        "${OAUTH_COOKIE_SECRET:-}" "$oauth_target" "cookie-secret" "" \
        "python3 -c \"import secrets; print(secrets.token_urlsafe(32))\" 2>/dev/null || openssl rand -base64 32")

    # --- OAuth Proxy Secret ---
    if [ -f "$oauth_target" ] && [ "$force" != "--force" ]; then
        log_info "Already exists: $oauth_target (use --force to overwrite)"
    else
        mkdir -p "$(dirname "$oauth_target")"
        cat > "$oauth_target" <<EOF
# OAuth2-Proxy Secrets
# Generated from config/dev/.env by generate-config.sh
# DO NOT commit this file to git!

client-id=${OAUTH_CLIENT_ID:-}
client-secret=${OAUTH_CLIENT_SECRET:-}
cookie-secret=${cookie_secret}
EOF
        log_info "Created: $oauth_target"
    fi

    # --- PostgreSQL Secret ---
    if [ -f "$postgres_target" ] && [ "$force" != "--force" ]; then
        log_info "Already exists: $postgres_target (use --force to overwrite)"
    else
        mkdir -p "$(dirname "$postgres_target")"
        cat > "$postgres_target" <<EOF
# PostgreSQL Secret
# Generated from config/dev/.env by generate-config.sh
# DO NOT commit this file to git!

POSTGRES_USER=${pg_user}
POSTGRES_PASSWORD=${pg_password}
POSTGRES_DB=${pg_db}
POSTGRES_SERVER=postgres
POSTGRES_PORT=${pg_port}
EOF
        log_info "Created: $postgres_target"
    fi

    # --- LangFlow Secret (database URL) ---
    if [ -f "$langflow_target" ] && [ "$force" != "--force" ]; then
        log_info "Already exists: $langflow_target (use --force to overwrite)"
    else
        mkdir -p "$(dirname "$langflow_target")"
        cat > "$langflow_target" <<EOF
# LangFlow Database Secret
# Generated from config/dev/.env by generate-config.sh
# DO NOT commit this file to git!

database-url=postgresql://${pg_user}:${pg_password}@postgres:${pg_port}/langflow
EOF
        log_info "Created: $langflow_target"
    fi

    # --- Backend Config Secret ---
    if [ -f "$backend_target" ] && [ "$force" != "--force" ]; then
        log_info "Already exists: $backend_target (use --force to overwrite)"
    else
        local environment="${ENVIRONMENT:-development}"
        local langflow_url="${LANGFLOW_URL:-http://langflow-service-backend:7860}"

        mkdir -p "$(dirname "$backend_target")"
        {
            echo "# Backend Configuration Secret"
            echo "# Generated from config/dev/.env by generate-config.sh"
            echo "# DO NOT commit this file to git!"
            echo ""
            echo "ENVIRONMENT=${environment}"
            echo "SECRET_KEY=${secret_key}"
            [ -n "$token_enc_key" ] && echo "TOKEN_ENCRYPTION_KEY=${token_enc_key}"
            echo "LANGFLOW_URL=${langflow_url}"
            [ -n "${LANGFLOW_DEFAULT_FLOW:-}" ] && echo "LANGFLOW_DEFAULT_FLOW=${LANGFLOW_DEFAULT_FLOW}"
            [ -n "${FRONTEND_HOST:-}" ] && echo "FRONTEND_HOST=${FRONTEND_HOST}"
            [ -n "${BACKEND_CORS_ORIGINS:-}" ] && echo "BACKEND_CORS_ORIGINS=${BACKEND_CORS_ORIGINS}"
            [ -n "${GOOGLE_CLIENT_ID:-}" ] && echo "GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}"
            [ -n "${GOOGLE_CLIENT_SECRET:-}" ] && echo "GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}"
            [ -n "${DATAVERSE_AUTH_URL:-}" ] && echo "DATAVERSE_AUTH_URL=${DATAVERSE_AUTH_URL}"
        } > "$backend_target"
        log_info "Created: $backend_target"
    fi

    # --- Email Allowlist ---
    if [ -f "$emails_target" ] && [ "$force" != "--force" ]; then
        log_info "Already exists: $emails_target (use --force to overwrite)"
    else
        if [ ! -f "$CONFIG_DEV/allowed-emails.txt" ]; then
            log_warn "Config not found: $CONFIG_DEV/allowed-emails.txt - skipping email allowlist"
        else
            # Copy, stripping comment lines
            grep -v '^#' "$CONFIG_DEV/allowed-emails.txt" | grep -v '^$' > "$emails_target" || true
            log_info "Created: $emails_target"
        fi
    fi

    log_info "K8s secret generation complete"
}

# Generate Langfuse Helm secrets from config/dev/.env (single source)
cmd_helm_langfuse() {
    local force="${1:-}"

    log_info "Generating Langfuse Helm secrets from config/dev/.env..."

    local template="$PROJECT_ROOT/helm/langfuse/secrets-dev.yaml.template"
    local output="$PROJECT_ROOT/helm/langfuse/secrets-dev.yaml"

    if [ -f "$output" ] && [ "$force" != "--force" ]; then
        log_info "Already exists: $output (use --force to overwrite)"
        return 0
    fi

    if [ ! -f "$template" ]; then
        log_error "Template not found: $template"
        return 1
    fi

    # Load user-settable values from single .env
    if [ -f "$CONFIG_DEV/.env" ]; then
        load_env "$CONFIG_DEV/.env"
    fi

    # Helper: generate or reuse a secret
    # Priority: user .env value > existing YAML artifact value > generate new
    _langfuse_secret() {
        local user_val="$1"
        local yaml_key="$2"      # YAML env name or simple key for extraction
        local placeholder="$3"
        local gen_cmd="$4"
        local yaml_type="${5:-env}"  # "env" for additionalEnv, "simple" for direct YAML value

        # 1. User-provided non-placeholder value
        if [ -n "$user_val" ] && [ "$user_val" != "$placeholder" ]; then
            echo "$user_val"
            return
        fi

        # 2. Reuse from existing artifact
        if [ -f "$output" ]; then
            local existing=""
            if [ "$yaml_type" = "env" ]; then
                existing=$(get_yaml_env_value "$output" "$yaml_key")
            else
                existing=$(get_yaml_simple_value "$output" "$yaml_key")
            fi
            if [ -n "$existing" ] && [ "$existing" != "$placeholder" ] && [ "$existing" != '${'"$yaml_key"'}' ]; then
                echo "$existing"
                return
            fi
        fi

        # 3. Generate new
        local generated
        generated=$(eval "$gen_cmd" 2>/dev/null) || true
        if [ -z "$generated" ]; then
            log_error "Failed to generate Langfuse secret for $yaml_key"
            return 1
        fi
        echo "$generated"
    }

    # Generate or reuse Langfuse internal secrets (idempotent)
    local gen_secret="python3 -c \"import secrets; print(secrets.token_urlsafe(24))\" 2>/dev/null || openssl rand -base64 24"
    local gen_hex="python3 -c \"import secrets; print(secrets.token_hex(32))\" 2>/dev/null || openssl rand -hex 32"

    export REDIS_PASSWORD
    REDIS_PASSWORD=$(_langfuse_secret "${REDIS_PASSWORD:-}" "redis" "" "$gen_secret" "simple")

    export CLICKHOUSE_PASSWORD
    CLICKHOUSE_PASSWORD=$(_langfuse_secret "${CLICKHOUSE_PASSWORD:-}" "clickhouse" "" "$gen_secret" "simple")

    export ENCRYPTION_KEY
    ENCRYPTION_KEY=$(_langfuse_secret "${ENCRYPTION_KEY:-}" "encryptionKey" "" "$gen_hex" "simple")

    export SALT
    SALT=$(_langfuse_secret "${SALT:-}" "salt" "" "$gen_secret" "simple")

    export NEXTAUTH_SECRET
    NEXTAUTH_SECRET=$(_langfuse_secret "${NEXTAUTH_SECRET:-}" "secret" "" "$gen_secret" "simple")

    export LANGFUSE_INIT_USER_PASSWORD
    LANGFUSE_INIT_USER_PASSWORD=$(_langfuse_secret "${LANGFUSE_INIT_USER_PASSWORD:-}" "LANGFUSE_INIT_USER_PASSWORD" "" "$gen_secret" "env")

    # Langfuse API keys (pk-/sk- prefixed)
    local gen_pk="echo pk-\$(python3 -c \"import secrets; print(secrets.token_urlsafe(24))\" 2>/dev/null || openssl rand -base64 24 | tr '+/' '-_' | tr -d '=')"
    local gen_sk="echo sk-\$(python3 -c \"import secrets; print(secrets.token_urlsafe(24))\" 2>/dev/null || openssl rand -base64 24 | tr '+/' '-_' | tr -d '=')"

    export LANGFUSE_INIT_PROJECT_PUBLIC_KEY
    LANGFUSE_INIT_PROJECT_PUBLIC_KEY=$(_langfuse_secret "${LANGFUSE_INIT_PROJECT_PUBLIC_KEY:-}" "LANGFUSE_INIT_PROJECT_PUBLIC_KEY" "pk-your-public-key" "$gen_pk" "env")

    export LANGFUSE_INIT_PROJECT_SECRET_KEY
    LANGFUSE_INIT_PROJECT_SECRET_KEY=$(_langfuse_secret "${LANGFUSE_INIT_PROJECT_SECRET_KEY:-}" "LANGFUSE_INIT_PROJECT_SECRET_KEY" "sk-your-secret-key" "$gen_sk" "env")

    # Defaults for non-user variables
    export LANGFUSE_NEXTAUTH_URL="${LANGFUSE_NEXTAUTH_URL:-auto-calculated-by-deploy-script}"
    export LANGFUSE_INIT_USER_EMAIL="${LANGFUSE_INIT_USER_EMAIL:-admin@your-domain.com}"
    export LANGFUSE_INIT_USER_NAME="${LANGFUSE_INIT_USER_NAME:-Admin}"
    export LANGFUSE_INIT_ORG_ID="${LANGFUSE_INIT_ORG_ID:-multi-agent-platform}"
    export LANGFUSE_INIT_ORG_NAME="${LANGFUSE_INIT_ORG_NAME:-Multi-Agent Platform}"
    export LANGFUSE_INIT_PROJECT_ID="${LANGFUSE_INIT_PROJECT_ID:-default}"
    export LANGFUSE_INIT_PROJECT_NAME="${LANGFUSE_INIT_PROJECT_NAME:-Default Project}"

    # Use selective envsubst to avoid replacing stray $ in YAML
    local var_list='$REDIS_PASSWORD $CLICKHOUSE_PASSWORD $SALT $ENCRYPTION_KEY $LANGFUSE_NEXTAUTH_URL $NEXTAUTH_SECRET $LANGFUSE_INIT_PROJECT_PUBLIC_KEY $LANGFUSE_INIT_PROJECT_SECRET_KEY $LANGFUSE_INIT_USER_EMAIL $LANGFUSE_INIT_USER_NAME $LANGFUSE_INIT_USER_PASSWORD $LANGFUSE_INIT_ORG_ID $LANGFUSE_INIT_ORG_NAME $LANGFUSE_INIT_PROJECT_ID $LANGFUSE_INIT_PROJECT_NAME'

    envsubst_or_fallback "$template" "$output" "$var_list"

    log_info "Created: $output"
}

# Delete copied/generated config files so they can be regenerated fresh
# Source .env files are preserved (user's config); created from .env.example if missing.
# Usage: cmd_reset <environment>  ("local", "dev", or "all"; default: "all")
cmd_reset() {
    local environment="${1:-all}"

    if [[ "$environment" != "local" && "$environment" != "dev" && "$environment" != "all" ]]; then
        log_error "Unknown environment: $environment (use 'local', 'dev', or omit for both)"
        exit 1
    fi

    if [[ "$environment" == "local" || "$environment" == "all" ]]; then
        log_info "Removing copied config files for local..."

        # Remove service directory copies (generated from config/local/.env)
        for f in "$PROJECT_ROOT/backend/.env" "$PROJECT_ROOT/frontend/.env"; do
            if [ -f "$f" ]; then
                rm -f "$f"
                log_info "Removed: $(basename $(dirname $f))/$(basename $f)"
            fi
        done

        # Ensure source .env exists (create from example if missing)
        copy_if_missing "$CONFIG_LOCAL/.env.example" "$CONFIG_LOCAL/.env"
    fi

    if [[ "$environment" == "dev" || "$environment" == "all" ]]; then
        log_info "Removing generated config files for dev..."

        # Remove generated deployment artifacts
        local k8s_generated=(
            "$PROJECT_ROOT/k8s/app/overlays/dev/oauth-proxy-secret.env"
            "$PROJECT_ROOT/k8s/app/overlays/dev/backend-config.env"
            "$PROJECT_ROOT/k8s/app/overlays/dev/allowed-emails.txt"
            "$PROJECT_ROOT/k8s/langflow/overlays/dev/langflow-secret.env"
            "$PROJECT_ROOT/k8s/postgres/overlays/dev/postgres-secret.env"
        )
        for f in "${k8s_generated[@]}"; do
            if [ -f "$f" ]; then
                rm -f "$f"
                log_info "Removed: $f"
            fi
        done

        # Helm generated secrets
        if [ -f "$PROJECT_ROOT/helm/langfuse/secrets-dev.yaml" ]; then
            rm -f "$PROJECT_ROOT/helm/langfuse/secrets-dev.yaml"
            log_info "Removed: helm/langfuse/secrets-dev.yaml"
        fi

        # Ensure source .env exists (create from example if missing)
        copy_if_missing "$CONFIG_DEV/.env.example" "$CONFIG_DEV/.env"
    fi

    log_info "Reset complete. Run 'make config-setup' or 'make config-setup-cluster' to sync."
}

# Run all generation commands
cmd_all() {
    local force="${1:-}"
    cmd_k8s "$force"
    cmd_helm_langfuse "$force"
    log_info "All config generation complete"
}

# Show usage
cmd_help() {
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Unified config generation script."
    echo "Reads single .env per environment, generates deployment artifacts."
    echo "User config files are NEVER modified by this script."
    echo ""
    echo "Commands:"
    echo "  local          Setup local dev config (copy .env.example, create backend/.env)"
    echo "  dev            Setup cluster dev config (copy .env.example + access control files)"
    echo "  k8s            Generate K8s secret files from config/dev/.env"
    echo "  helm-langfuse  Generate Langfuse Helm secrets from config/dev/.env"
    echo "  all            Run k8s + helm-langfuse (generates all deployment artifacts)"
    echo "  reset [env]    Delete generated config (default: all; options: local, dev, all)"
    echo "                 Use to start fresh with config from examples"
    echo "  help           Show this help message"
    echo ""
    echo "Options:"
    echo "  --force        Overwrite existing generated files"
    echo ""
    echo "Source directories:"
    echo "  config/local/.env    Local development config"
    echo "  config/dev/.env      Cluster/dev deployment config"
    echo ""
    echo "Generated targets (from config/dev/.env):"
    echo "  k8s/app/overlays/dev/oauth-proxy-secret.env"
    echo "  k8s/app/overlays/dev/backend-config.env"
    echo "  k8s/app/overlays/dev/allowed-emails.txt"
    echo "  k8s/langflow/overlays/dev/langflow-secret.env"
    echo "  k8s/postgres/overlays/dev/postgres-secret.env"
    echo "  helm/langfuse/secrets-dev.yaml"
}

# ============================================
# Main
# ============================================

case "${1:-help}" in
    local)
        cmd_local
        ;;
    dev)
        cmd_dev
        ;;
    k8s)
        cmd_k8s "${2:-}"
        ;;
    helm-langfuse)
        cmd_helm_langfuse "${2:-}"
        ;;
    all)
        cmd_all "${2:-}"
        ;;
    reset)
        cmd_reset "${2:-all}"
        ;;
    help|--help|-h)
        cmd_help
        ;;
    *)
        log_error "Unknown command: $1"
        cmd_help
        exit 1
        ;;
esac
