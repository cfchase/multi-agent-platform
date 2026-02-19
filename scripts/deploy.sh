#!/bin/bash

# Deploy all components to OpenShift
# Usage: ./scripts/deploy.sh [environment] [namespace]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
source "$SCRIPT_DIR/lib/common.sh"

ENVIRONMENT=${1:-dev}
NAMESPACE=${2:-multi-agent-platform-${ENVIRONMENT}}

if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
    echo "Error: Environment must be 'dev' or 'prod'"
    exit 1
fi

# Validate all prerequisites before any deployment starts
check_deploy_prerequisites() {
    local environment="$1"
    local config_dir="$PROJECT_ROOT/config/$environment"

    # CLI tools
    check_oc_installed
    check_helm_installed
    check_openshift_login

    # Config files
    local required_configs=(".env")
    for cfg in "${required_configs[@]}"; do
        if [ ! -f "$config_dir/$cfg" ]; then
            log_error "Missing config: $config_dir/$cfg"
            log_error "Run: cp $config_dir/.env.example $config_dir/.env"
            exit 1
        fi
    done

    # Check OAuth credentials are not placeholder
    if grep -q "OAUTH_CLIENT_ID=your-client-id" "$config_dir/.env" 2>/dev/null; then
        log_error "OAuth credentials not configured in $config_dir/.env"
        echo ""
        echo "  To set up Google OAuth:"
        echo "    1. Go to https://console.cloud.google.com/apis/credentials"
        echo "    2. Create an OAuth 2.0 Client ID (Web application)"
        echo ""
        # Compute the app route URL from the cluster's ingress domain
        local apps_domain
        apps_domain=$(oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}' 2>/dev/null || echo "")
        if [[ -n "$apps_domain" ]]; then
            local route_host="multi-agent-platform-${NAMESPACE}.${apps_domain}"
            echo "  Configure these in the Google Cloud Console:"
            echo "    Authorized JavaScript origin:  https://${route_host}"
            echo "    Authorized redirect URI:       https://${route_host}/oauth2/callback"
        else
            echo "  Configure these in the Google Cloud Console (substitute your route host):"
            echo "    Authorized JavaScript origin:  https://<app-route>"
            echo "    Authorized redirect URI:       https://<app-route>/oauth2/callback"
        fi
        echo ""
        echo "    3. Copy the Client ID and Secret into $config_dir/.env"
        echo ""
        echo "  See docs/AUTHENTICATION.md for detailed walkthrough"
        exit 1
    fi

    log_info "All prerequisites verified"
}

check_deploy_prerequisites "$ENVIRONMENT"

# Create shared OAuth resources for supporting services (Langflow, MLflow)
ensure_supporting_services_oauth() {
    local namespace="$1"

    echo "Setting up shared OAuth resources for supporting services..."

    # ServiceAccount (shared by Langflow and MLflow OAuth proxies)
    if ! oc get sa supporting-services-proxy -n "$namespace" &>/dev/null; then
        log_info "Creating ServiceAccount supporting-services-proxy..."
        oc create sa supporting-services-proxy -n "$namespace"
    else
        echo "ServiceAccount supporting-services-proxy already exists"
    fi

    # OAuth redirect annotations for both services (idempotent with --overwrite)
    oc annotate sa supporting-services-proxy -n "$namespace" --overwrite \
        "serviceaccounts.openshift.io/oauth-redirectreference.mlflow={\"kind\":\"OAuthRedirectReference\",\"apiVersion\":\"v1\",\"reference\":{\"kind\":\"Route\",\"name\":\"mlflow\"}}" \
        "serviceaccounts.openshift.io/oauth-redirectreference.langflow={\"kind\":\"OAuthRedirectReference\",\"apiVersion\":\"v1\",\"reference\":{\"kind\":\"Route\",\"name\":\"langflow\"}}"

    # Session secret (preserves existing sessions across deploys)
    if ! oc get secret supporting-services-proxy-session -n "$namespace" &>/dev/null; then
        log_info "Creating session secret..."
        local session_secret
        session_secret=$(openssl rand -base64 32 | head -c 43)
        oc create secret generic supporting-services-proxy-session \
            --from-literal=session_secret="$session_secret" \
            -n "$namespace"
    else
        echo "Session secret supporting-services-proxy-session already exists"
    fi
}

echo "==================================="
echo "Deploying All Components"
echo "==================================="
echo "Environment: $ENVIRONMENT"
echo "Namespace: $NAMESPACE"
echo ""

# Deploy in dependency order:
# 1. Namespace + secrets/credentials/OAuth (prerequisites)
# 2. PostgreSQL (database — needed by all services)
# 3. Langfuse (tracing — generates API keys needed by Langflow)
# 4. MLflow (experiment tracking — independent)
# 5. Langflow (workflow engine — depends on Langfuse keys)
# 6. App (frontend/backend — depends on all service credentials)

# Step 1: Ensure namespace exists, generate secrets, set up cluster prerequisites
echo "Ensuring namespace $NAMESPACE exists..."
oc create namespace "$NAMESPACE" --dry-run=client -o yaml | oc apply -f -
echo ""

echo "Generating k8s secrets from config/${ENVIRONMENT}/..."
"$SCRIPT_DIR/generate-config.sh" k8s --force
echo ""

# Admin credentials (shared by LangFlow and Langfuse)
# Uses LANGFUSE_INIT_USER_PASSWORD from user's .env or auto-generates
echo "Generating admin credentials if needed..."
if ! oc get secret admin-credentials -n "$NAMESPACE" &> /dev/null; then
    CONFIG_ENV="$PROJECT_ROOT/config/$ENVIRONMENT/.env"

    # Resolve admin password: user .env > auto-generate
    ADMIN_PASS=""
    if [ -f "$CONFIG_ENV" ]; then
        ADMIN_PASS=$(grep -E "^LANGFUSE_INIT_USER_PASSWORD=" "$CONFIG_ENV" 2>/dev/null | cut -d= -f2- | sed 's/^["'"'"']//;s/["'"'"']$//')
    fi
    if [ -z "$ADMIN_PASS" ]; then
        echo "No LANGFUSE_INIT_USER_PASSWORD found in .env — auto-generating admin password"
        ADMIN_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))" 2>/dev/null || openssl rand -base64 16 2>/dev/null || "")
        if [ -z "$ADMIN_PASS" ]; then
            echo "Error: Cannot auto-generate admin password (need python3 or openssl)"
            echo "  Set LANGFUSE_INIT_USER_PASSWORD in config/$ENVIRONMENT/.env instead"
            exit 1
        fi
    fi

    # Resolve admin email from user .env or default
    ADMIN_EMAIL=""
    if [ -f "$CONFIG_ENV" ]; then
        ADMIN_EMAIL=$(grep -E "^LANGFUSE_INIT_USER_EMAIL=" "$CONFIG_ENV" 2>/dev/null | cut -d= -f2- | sed 's/^["'"'"']//;s/["'"'"']$//')
    fi
    ADMIN_EMAIL="${ADMIN_EMAIL:-admin@localhost.local}"

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

# Namespace admin group (for Langflow/MLflow OAuth access)
ADMINS_FILE="$PROJECT_ROOT/config/$ENVIRONMENT/namespace-admins.txt"
GROUP_NAME="${NAMESPACE}-admins"
if [ -f "$ADMINS_FILE" ]; then
    echo "Setting up namespace admin group: $GROUP_NAME"
    if ! oc get group "$GROUP_NAME" &> /dev/null 2>&1; then
        oc adm groups new "$GROUP_NAME"
        echo "Created group: $GROUP_NAME"
    fi
    while IFS= read -r user || [ -n "$user" ]; do
        [[ "$user" =~ ^#.*$ || -z "$user" ]] && continue
        user=$(echo "$user" | tr -d '[:space:]')
        if ! oc get group "$GROUP_NAME" -o jsonpath='{.users[*]}' 2>/dev/null | grep -qw "$user"; then
            oc adm groups add-users "$GROUP_NAME" "$user" 2>/dev/null && echo "  Added user: $user" || echo "  Warning: Could not add user: $user"
        else
            echo "  Already in group: $user"
        fi
    done < "$ADMINS_FILE"
    if ! oc adm policy add-role-to-group edit "$GROUP_NAME" -n "$NAMESPACE" 2>&1; then
        echo "Warning: Failed to grant edit role to $GROUP_NAME in $NAMESPACE"
        echo "  You may need cluster-admin permissions to assign roles"
    else
        echo "Granted edit role to $GROUP_NAME in $NAMESPACE"
    fi
else
    echo "No namespace-admins.txt found at $ADMINS_FILE - skipping group setup"
fi
echo ""

# Shared OAuth resources (ServiceAccount, session secret)
ensure_supporting_services_oauth "$NAMESPACE"
echo ""

# Step 2: PostgreSQL (all services depend on this)
echo "Step 2/6: Deploying PostgreSQL..."
"$SCRIPT_DIR/deploy-db.sh" "$ENVIRONMENT" "$NAMESPACE"
echo ""

# Step 3: Langfuse (generates secrets-dev.yaml with API keys needed by Langflow)
echo "Step 3/6: Deploying Langfuse..."
"$SCRIPT_DIR/deploy-langfuse.sh" "$ENVIRONMENT" "$NAMESPACE"
echo ""

# Step 4: MLflow (independent)
echo "Step 4/6: Deploying MLFlow..."
"$SCRIPT_DIR/deploy-mlflow.sh" "$ENVIRONMENT" "$NAMESPACE"
echo ""

# Step 5: Langflow (reads Langfuse API keys from secrets-dev.yaml)
echo "Step 5/6: Deploying LangFlow..."
"$SCRIPT_DIR/deploy-langflow.sh" "$ENVIRONMENT" "$NAMESPACE"
echo ""

# Step 6: App (depends on all service credentials)
echo "Step 6/6: Deploying Multi-Agent Platform App..."
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
