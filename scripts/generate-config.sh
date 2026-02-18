#!/bin/bash

# Unified config generation script
# Reads from config/ as source of truth, generates target-specific formats
#
# Usage: ./scripts/generate-config.sh [command]
# Commands: local, k8s, helm-langfuse, all, help

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

# envsubst with explicit variable list, or fallback if envsubst not available
envsubst_or_fallback() {
    local template="$1"
    local output="$2"
    local var_list="$3"

    if command -v envsubst &> /dev/null; then
        envsubst "$var_list" < "$template" > "$output"
    else
        log_warn "envsubst not found, using shell variable expansion fallback"
        # Read template and substitute variables using eval
        while IFS= read -r line; do
            eval "echo \"$line\""
        done < "$template" > "$output"
    fi
}

# ============================================
# Subcommands
# ============================================

# Setup local development config files from examples
cmd_local() {
    log_info "Setting up local development config..."

    # Copy all .env.*.example files to .env.* if they don't exist
    for example_file in "$CONFIG_LOCAL"/.env.*.example; do
        if [ -f "$example_file" ]; then
            local target="${example_file%.example}"
            copy_if_missing "$example_file" "$target"
        fi
    done

    # Copy flow-sources.yaml.example if present
    if [ -f "$CONFIG_LOCAL/flow-sources.yaml.example" ]; then
        copy_if_missing "$CONFIG_LOCAL/flow-sources.yaml.example" "$CONFIG_LOCAL/flow-sources.yaml"
    fi

    # Copy backend and frontend .env files if not present
    if [ -f "$CONFIG_LOCAL/.env.backend" ]; then
        copy_if_missing "$CONFIG_LOCAL/.env.backend" "$PROJECT_ROOT/backend/.env"
    fi
    if [ -f "$CONFIG_LOCAL/.env.frontend" ]; then
        copy_if_missing "$CONFIG_LOCAL/.env.frontend" "$PROJECT_ROOT/frontend/.env"
    fi

    log_info "Local config setup complete"
}

# Setup cluster dev config files from examples, auto-generating secrets
cmd_dev() {
    log_info "Setting up cluster dev config from examples..."

    local created=0

    # Copy all .env.*.example files to .env.* if they don't exist
    for example_file in "$CONFIG_DEV"/.env.*.example; do
        if [ -f "$example_file" ]; then
            local target="${example_file%.example}"
            if [ -f "$target" ]; then
                log_info "Already exists: $target"
            else
                cp "$example_file" "$target"
                created=$((created + 1))
                log_info "Created: $target"
            fi
        fi
    done

    # Copy non-.env example files (text configs)
    for example_file in "$CONFIG_DEV"/*.example; do
        if [ -f "$example_file" ]; then
            # Skip .env.* files (already handled above)
            case "$(basename "$example_file")" in
                .env.*) continue ;;
            esac
            local target="${example_file%.example}"
            if [ -f "$target" ]; then
                log_info "Already exists: $target"
            else
                cp "$example_file" "$target"
                created=$((created + 1))
                log_info "Created: $target"
            fi
        fi
    done

    if [ "$created" -eq 0 ]; then
        log_info "All config files already exist"
    fi

    # Auto-generate secrets (replaces placeholders — safe to re-run)
    log_info "Checking for placeholder secrets..."

    # POSTGRES_PASSWORD in .env.postgres, synced to .env.backend, .env.langfuse, .env.mlflow
    if [ -f "$CONFIG_DEV/.env.postgres" ]; then
        local pg_pass=""
        if grep -q "POSTGRES_PASSWORD=changethis" "$CONFIG_DEV/.env.postgres"; then
            pg_pass=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))" 2>/dev/null || openssl rand -base64 16)
            sed -i.bak "s|POSTGRES_PASSWORD=changethis|POSTGRES_PASSWORD=${pg_pass}|" "$CONFIG_DEV/.env.postgres"
            rm -f "$CONFIG_DEV/.env.postgres.bak"
            log_info "Generated POSTGRES_PASSWORD"
        else
            # Read existing password for syncing to other files
            pg_pass=$(grep "^POSTGRES_PASSWORD=" "$CONFIG_DEV/.env.postgres" | cut -d= -f2)
        fi

        # Sync POSTGRES_PASSWORD to all files that duplicate it
        if [ -n "$pg_pass" ]; then
            for sync_file in "$CONFIG_DEV/.env.backend" "$CONFIG_DEV/.env.langfuse" "$CONFIG_DEV/.env.mlflow"; do
                if [ -f "$sync_file" ] && grep -q "POSTGRES_PASSWORD=changethis" "$sync_file"; then
                    sed -i.bak "s|POSTGRES_PASSWORD=changethis|POSTGRES_PASSWORD=${pg_pass}|" "$sync_file"
                    rm -f "${sync_file}.bak"
                fi
            done
        fi
    fi

    # SECRET_KEY in .env.backend
    if [ -f "$CONFIG_DEV/.env.backend" ]; then
        local secret_key
        secret_key=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)
        sed -i.bak "s|SECRET_KEY=changethis_generate_a_secure_random_key|SECRET_KEY=${secret_key}|" "$CONFIG_DEV/.env.backend"
        rm -f "$CONFIG_DEV/.env.backend.bak"
        log_info "Generated SECRET_KEY"
    fi

    # TOKEN_ENCRYPTION_KEY in .env.backend
    if [ -f "$CONFIG_DEV/.env.backend" ]; then
        local token_key
        token_key=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || "")
        if [ -n "$token_key" ]; then
            sed -i.bak "s|TOKEN_ENCRYPTION_KEY=changethis_generate_a_fernet_key|TOKEN_ENCRYPTION_KEY=${token_key}|" "$CONFIG_DEV/.env.backend"
            rm -f "$CONFIG_DEV/.env.backend.bak"
            log_info "Generated TOKEN_ENCRYPTION_KEY"
        else
            log_warn "Could not auto-generate TOKEN_ENCRYPTION_KEY (cryptography package not available)"
        fi
    fi

    # Langfuse secrets in .env.langfuse
    if [ -f "$CONFIG_DEV/.env.langfuse" ]; then
        # ENCRYPTION_KEY - 64-char hex
        local enc_key
        enc_key=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)
        sed -i.bak "s|ENCRYPTION_KEY=generate-random-hex-64-chars|ENCRYPTION_KEY=${enc_key}|" "$CONFIG_DEV/.env.langfuse"
        rm -f "$CONFIG_DEV/.env.langfuse.bak"

        # NEXTAUTH_SECRET, SALT, passwords
        for placeholder_var in NEXTAUTH_SECRET SALT CLICKHOUSE_PASSWORD REDIS_PASSWORD MINIO_ROOT_PASSWORD LANGFUSE_INIT_USER_PASSWORD; do
            local gen_val
            gen_val=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))" 2>/dev/null || openssl rand -base64 24)
            sed -i.bak "s|${placeholder_var}=generate-random-value|${placeholder_var}=${gen_val}|" "$CONFIG_DEV/.env.langfuse"
            rm -f "$CONFIG_DEV/.env.langfuse.bak"
            sed -i.bak "s|${placeholder_var}=generate-secure-password|${placeholder_var}=${gen_val}|" "$CONFIG_DEV/.env.langfuse"
            rm -f "$CONFIG_DEV/.env.langfuse.bak"
        done

        log_info "Generated Langfuse secrets"

        # Generate Langfuse API keys (pk-/sk- prefixed) if still placeholders
        if grep -q "LANGFUSE_INIT_PROJECT_PUBLIC_KEY=pk-your-public-key" "$CONFIG_DEV/.env.langfuse"; then
            local pk_suffix
            pk_suffix=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))" 2>/dev/null || openssl rand -base64 24 | tr '+/' '-_' | tr -d '=')
            sed -i.bak "s|LANGFUSE_INIT_PROJECT_PUBLIC_KEY=pk-your-public-key|LANGFUSE_INIT_PROJECT_PUBLIC_KEY=pk-${pk_suffix}|" "$CONFIG_DEV/.env.langfuse"
            rm -f "$CONFIG_DEV/.env.langfuse.bak"
            log_info "Generated LANGFUSE_INIT_PROJECT_PUBLIC_KEY"
        fi
        if grep -q "LANGFUSE_INIT_PROJECT_SECRET_KEY=sk-your-secret-key" "$CONFIG_DEV/.env.langfuse"; then
            local sk_suffix
            sk_suffix=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))" 2>/dev/null || openssl rand -base64 24 | tr '+/' '-_' | tr -d '=')
            sed -i.bak "s|LANGFUSE_INIT_PROJECT_SECRET_KEY=sk-your-secret-key|LANGFUSE_INIT_PROJECT_SECRET_KEY=sk-${sk_suffix}|" "$CONFIG_DEV/.env.langfuse"
            rm -f "$CONFIG_DEV/.env.langfuse.bak"
            log_info "Generated LANGFUSE_INIT_PROJECT_SECRET_KEY"
        fi
    fi

    # Sync Langfuse API keys from .env.langfuse into .env.langflow
    if [ -f "$CONFIG_DEV/.env.langfuse" ] && [ -f "$CONFIG_DEV/.env.langflow" ]; then
        local lf_pk lf_sk
        lf_pk=$(grep "^LANGFUSE_INIT_PROJECT_PUBLIC_KEY=" "$CONFIG_DEV/.env.langfuse" | cut -d= -f2-)
        lf_sk=$(grep "^LANGFUSE_INIT_PROJECT_SECRET_KEY=" "$CONFIG_DEV/.env.langfuse" | cut -d= -f2-)

        local synced=0
        if [ -n "$lf_pk" ] && [ "$lf_pk" != "pk-your-public-key" ]; then
            sed -i.bak "s|^LANGFUSE_PUBLIC_KEY=.*|LANGFUSE_PUBLIC_KEY=${lf_pk}|" "$CONFIG_DEV/.env.langflow"
            rm -f "$CONFIG_DEV/.env.langflow.bak"
            synced=1
        fi
        if [ -n "$lf_sk" ] && [ "$lf_sk" != "sk-your-secret-key" ]; then
            sed -i.bak "s|^LANGFUSE_SECRET_KEY=.*|LANGFUSE_SECRET_KEY=${lf_sk}|" "$CONFIG_DEV/.env.langflow"
            rm -f "$CONFIG_DEV/.env.langflow.bak"
            synced=1
        fi

        # Ensure LANGFUSE_HOST is uncommented and set
        if grep -q "^# LANGFUSE_HOST=" "$CONFIG_DEV/.env.langflow"; then
            sed -i.bak "s|^# LANGFUSE_HOST=.*|LANGFUSE_HOST=http://langfuse-web:3000|" "$CONFIG_DEV/.env.langflow"
            rm -f "$CONFIG_DEV/.env.langflow.bak"
            synced=1
        fi

        if [ "$synced" -eq 1 ]; then
            log_info "Synced Langfuse keys to .env.langflow"
        else
            log_warn "Langfuse keys not yet generated - skipping sync to .env.langflow"
        fi
    fi

    # OAUTH_COOKIE_SECRET in .env.oauth-proxy
    if [ -f "$CONFIG_DEV/.env.oauth-proxy" ]; then
        local cookie_secret
        cookie_secret=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)
        sed -i.bak "s|OAUTH_COOKIE_SECRET=changethis_generate_a_secure_random_key|OAUTH_COOKIE_SECRET=${cookie_secret}|" "$CONFIG_DEV/.env.oauth-proxy"
        rm -f "$CONFIG_DEV/.env.oauth-proxy.bak"
        log_info "Generated OAUTH_COOKIE_SECRET"
    fi

    log_info "Dev config setup complete"
    echo ""
    echo "Files created in config/dev/. You still need to set:"
    echo "  .env.oauth-proxy   - OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET (Google OAuth)"
    echo "  .env.backend       - GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET (Google Drive integration, optional)"
    echo "  .env.langflow      - OPENAI_API_KEY (or other LLM keys)"
    echo "  allowed-emails.txt - Email addresses for main app access"
    echo "  namespace-admins.txt - OpenShift usernames for Langflow/MLflow access"
}

# Generate Kubernetes secret .env files from config/dev/
cmd_k8s() {
    local force="${1:-}"

    log_info "Generating Kubernetes secret files from config/dev/..."

    # --- Pre-generate passwords that must be consistent across sections ---
    local _generated_postgres_password=""
    if [ -f "$CONFIG_DEV/.env.postgres" ]; then
        load_env "$CONFIG_DEV/.env.postgres"
        if [ -z "$POSTGRES_PASSWORD" ] || [ "$POSTGRES_PASSWORD" = "changethis" ]; then
            _generated_postgres_password=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))" 2>/dev/null || openssl rand -base64 16)
            log_info "Auto-generated POSTGRES_PASSWORD"
        fi
    fi

    # --- OAuth Proxy Secret ---
    local oauth_target="$PROJECT_ROOT/k8s/app/overlays/dev/oauth-proxy-secret.env"
    if [ -f "$oauth_target" ] && [ "$force" != "--force" ]; then
        log_info "Already exists: $oauth_target (use --force to overwrite)"
    else
        if [ ! -f "$CONFIG_DEV/.env.oauth-proxy" ]; then
            log_warn "Config not found: $CONFIG_DEV/.env.oauth-proxy - skipping OAuth secret"
        else
            load_env "$CONFIG_DEV/.env.oauth-proxy"

            # Generate cookie secret if still placeholder
            if [ -z "$OAUTH_COOKIE_SECRET" ] || [ "$OAUTH_COOKIE_SECRET" = "changethis_generate_a_secure_random_key" ]; then
                OAUTH_COOKIE_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)
            fi

            mkdir -p "$(dirname "$oauth_target")"
            cat > "$oauth_target" <<EOF
# OAuth2-Proxy Secrets
# Generated from config/dev/.env.oauth-proxy by generate-config.sh
# DO NOT commit this file to git!

client-id=${OAUTH_CLIENT_ID}
client-secret=${OAUTH_CLIENT_SECRET}
cookie-secret=${OAUTH_COOKIE_SECRET}
EOF
            log_info "Created: $oauth_target"
        fi
    fi

    # --- LangFlow Secret ---
    local langflow_target="$PROJECT_ROOT/k8s/langflow/overlays/dev/langflow-secret.env"
    if [ -f "$langflow_target" ] && [ "$force" != "--force" ]; then
        log_info "Already exists: $langflow_target (use --force to overwrite)"
    else
        if [ ! -f "$CONFIG_DEV/.env.langflow" ] || [ ! -f "$CONFIG_DEV/.env.postgres" ]; then
            log_warn "Config not found: $CONFIG_DEV/.env.langflow or .env.postgres - skipping LangFlow secret"
        else
            load_env "$CONFIG_DEV/.env.postgres"
            [ -n "$_generated_postgres_password" ] && POSTGRES_PASSWORD="$_generated_postgres_password"
            load_env "$CONFIG_DEV/.env.langflow"

            local langflow_db="${LANGFLOW_DB:-langflow}"

            mkdir -p "$(dirname "$langflow_target")"
            cat > "$langflow_target" <<EOF
# LangFlow Database Secret
# Generated from config/dev/.env.langflow + .env.postgres by generate-config.sh
# DO NOT commit this file to git!

database-url=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:${POSTGRES_PORT}/${langflow_db}
EOF
            log_info "Created: $langflow_target"
        fi
    fi

    # --- PostgreSQL Secret ---
    local postgres_target="$PROJECT_ROOT/k8s/postgres/overlays/dev/postgres-secret.env"
    if [ -f "$postgres_target" ] && [ "$force" != "--force" ]; then
        log_info "Already exists: $postgres_target (use --force to overwrite)"
    else
        if [ ! -f "$CONFIG_DEV/.env.postgres" ]; then
            log_warn "Config not found: $CONFIG_DEV/.env.postgres - skipping PostgreSQL secret"
        else
            load_env "$CONFIG_DEV/.env.postgres"
            [ -n "$_generated_postgres_password" ] && POSTGRES_PASSWORD="$_generated_postgres_password"

            mkdir -p "$(dirname "$postgres_target")"
            cat > "$postgres_target" <<EOF
# PostgreSQL Secret
# Generated from config/dev/.env.postgres by generate-config.sh
# DO NOT commit this file to git!

POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=${POSTGRES_DB}
POSTGRES_SERVER=postgres
POSTGRES_PORT=${POSTGRES_PORT}
EOF
            log_info "Created: $postgres_target"
        fi
    fi

    # --- Backend Config Secret ---
    local backend_target="$PROJECT_ROOT/k8s/app/overlays/dev/backend-config.env"
    if [ -f "$backend_target" ] && [ "$force" != "--force" ]; then
        log_info "Already exists: $backend_target (use --force to overwrite)"
    else
        if [ ! -f "$CONFIG_DEV/.env.backend" ]; then
            log_warn "Config not found: $CONFIG_DEV/.env.backend - skipping backend config"
        else
            load_env "$CONFIG_DEV/.env.backend"

            # Auto-generate SECRET_KEY if empty, unset, or placeholder
            if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "changethis_generate_a_secure_random_key" ]; then
                SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)
                log_info "Auto-generated SECRET_KEY"
            fi

            # Auto-generate TOKEN_ENCRYPTION_KEY if empty, unset, or placeholder
            if [ -z "$TOKEN_ENCRYPTION_KEY" ] || [ "$TOKEN_ENCRYPTION_KEY" = "changethis_generate_a_fernet_key" ]; then
                TOKEN_ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "")
                if [ -z "$TOKEN_ENCRYPTION_KEY" ]; then
                    log_warn "Could not auto-generate TOKEN_ENCRYPTION_KEY (cryptography package not available)"
                else
                    log_info "Auto-generated TOKEN_ENCRYPTION_KEY"
                fi
            fi

            mkdir -p "$(dirname "$backend_target")"
            {
                echo "# Backend Configuration Secret"
                echo "# Generated from config/dev/.env.backend by generate-config.sh"
                echo "# DO NOT commit this file to git!"
                echo ""
                echo "ENVIRONMENT=${ENVIRONMENT}"
                echo "SECRET_KEY=${SECRET_KEY}"
                [ -n "$FRONTEND_HOST" ] && echo "FRONTEND_HOST=${FRONTEND_HOST}"
                [ -n "$BACKEND_CORS_ORIGINS" ] && echo "BACKEND_CORS_ORIGINS=${BACKEND_CORS_ORIGINS}"
                [ -n "$TOKEN_ENCRYPTION_KEY" ] && echo "TOKEN_ENCRYPTION_KEY=${TOKEN_ENCRYPTION_KEY}"
                [ -n "$LANGFLOW_URL" ] && echo "LANGFLOW_URL=${LANGFLOW_URL}"
                [ -n "$LANGFLOW_DEFAULT_FLOW" ] && echo "LANGFLOW_DEFAULT_FLOW=${LANGFLOW_DEFAULT_FLOW}"
                [ -n "$GOOGLE_CLIENT_ID" ] && echo "GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}"
                [ -n "$GOOGLE_CLIENT_SECRET" ] && echo "GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}"
                [ -n "$DATAVERSE_AUTH_URL" ] && echo "DATAVERSE_AUTH_URL=${DATAVERSE_AUTH_URL}"
            } > "$backend_target"
            log_info "Created: $backend_target"
        fi
    fi

    # --- Email Allowlist ---
    local emails_target="$PROJECT_ROOT/k8s/app/overlays/dev/allowed-emails.txt"
    if [ -f "$emails_target" ] && [ "$force" != "--force" ]; then
        log_info "Already exists: $emails_target (use --force to overwrite)"
    else
        if [ ! -f "$CONFIG_DEV/allowed-emails.txt" ]; then
            log_warn "Config not found: $CONFIG_DEV/allowed-emails.txt - skipping email allowlist"
        else
            # Copy, stripping comment lines
            grep -v '^#' "$CONFIG_DEV/allowed-emails.txt" | grep -v '^$' > "$emails_target"
            log_info "Created: $emails_target"
        fi
    fi

    log_info "K8s secret generation complete"
}

# Generate Langfuse Helm secrets from config/dev/
cmd_helm_langfuse() {
    local force="${1:-}"

    log_info "Generating Langfuse Helm secrets from config/dev/..."

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

    if [ ! -f "$CONFIG_DEV/.env.langfuse" ]; then
        log_error "Config not found: $CONFIG_DEV/.env.langfuse"
        return 1
    fi

    load_env "$CONFIG_DEV/.env.langfuse"

    # Use selective envsubst to avoid replacing stray $ in YAML
    local var_list='$REDIS_PASSWORD $CLICKHOUSE_PASSWORD $SALT $ENCRYPTION_KEY $LANGFUSE_NEXTAUTH_URL $NEXTAUTH_SECRET $LANGFUSE_INIT_PROJECT_PUBLIC_KEY $LANGFUSE_INIT_PROJECT_SECRET_KEY $LANGFUSE_INIT_USER_EMAIL $LANGFUSE_INIT_USER_NAME $LANGFUSE_INIT_USER_PASSWORD $LANGFUSE_INIT_ORG_ID $LANGFUSE_INIT_ORG_NAME $LANGFUSE_INIT_PROJECT_ID $LANGFUSE_INIT_PROJECT_NAME'

    envsubst_or_fallback "$template" "$output" "$var_list"

    log_info "Created: $output"
}

# Delete all generated config files so they can be regenerated fresh
# Usage: cmd_reset <environment>  (currently only "dev" supported)
cmd_reset() {
    local environment="${1:-dev}"

    if [[ "$environment" != "dev" ]]; then
        log_error "Reset only supports 'dev' environment currently"
        exit 1
    fi

    log_info "Removing generated config files for $environment..."

    # config/dev/ — remove non-example files
    for f in "$CONFIG_DEV"/.env.*; do
        [ -f "$f" ] || continue
        case "$f" in *.example) continue ;; esac
        rm -f "$f"
        log_info "Removed: $f"
    done
    for f in allowed-emails.txt namespace-admins.txt flow-sources.yaml; do
        if [ -f "$CONFIG_DEV/$f" ]; then
            rm -f "$CONFIG_DEV/$f"
            log_info "Removed: $CONFIG_DEV/$f"
        fi
    done

    # k8s overlay generated secrets
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

    log_info "Reset complete. Run './scripts/generate-config.sh dev' to regenerate."
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
    echo "Reads from config/ as source of truth, generates target-specific formats."
    echo ""
    echo "Commands:"
    echo "  local          Setup local development config (copy .example files)"
    echo "  dev            Setup cluster dev config (copy .example files, auto-generate secrets)"
    echo "  k8s            Generate Kubernetes secret .env files from config/dev/"
    echo "  helm-langfuse  Generate Langfuse Helm secrets YAML from config/dev/"
    echo "  all            Run k8s + helm-langfuse"
    echo "  reset [env]    Delete all generated config for environment (default: dev)"
    echo "                 Use when moving to a new cluster to start fresh"
    echo "  help           Show this help message"
    echo ""
    echo "Options:"
    echo "  --force        Overwrite existing generated files"
    echo ""
    echo "Source directories:"
    echo "  config/local/  Local development config (.env.*.example templates)"
    echo "  config/dev/    Cluster/dev deployment config"
    echo ""
    echo "Generated targets:"
    echo "  k8s/app/overlays/dev/oauth-proxy-secret.env"
    echo "  k8s/app/overlays/dev/backend-config.env"
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
        cmd_reset "${2:-dev}"
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
