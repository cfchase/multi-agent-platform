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
    local required_configs=(".env.backend" ".env.oauth-proxy" ".env.postgres")
    for cfg in "${required_configs[@]}"; do
        if [ ! -f "$config_dir/$cfg" ]; then
            log_error "Missing config: $config_dir/$cfg"
            log_error "Run: ./scripts/generate-config.sh $environment"
            exit 1
        fi
    done

    # Check OAuth credentials are not placeholder
    if grep -q "OAUTH_CLIENT_ID=your-client-id" "$config_dir/.env.oauth-proxy" 2>/dev/null; then
        log_error "OAuth credentials not configured in $config_dir/.env.oauth-proxy"
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
        echo "    3. Copy the Client ID and Secret into $config_dir/.env.oauth-proxy"
        echo "       and $config_dir/.env.backend"
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

# Generate all k8s secrets from config/dev/ before any component deploys
echo "Generating secrets from config/${ENVIRONMENT}/..."
"$SCRIPT_DIR/generate-config.sh" k8s --force
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

# Setup namespace admin group from config (for Langflow/MLflow OAuth access)
ADMINS_FILE="$PROJECT_ROOT/config/$ENVIRONMENT/namespace-admins.txt"
GROUP_NAME="${NAMESPACE}-admins"
if [ -f "$ADMINS_FILE" ]; then
    echo "Setting up namespace admin group: $GROUP_NAME"
    # Create group if it doesn't exist
    if ! oc get group "$GROUP_NAME" &> /dev/null 2>&1; then
        oc adm groups new "$GROUP_NAME"
        echo "Created group: $GROUP_NAME"
    fi
    # Add users from config file
    while IFS= read -r user || [ -n "$user" ]; do
        # Skip comments and empty lines
        [[ "$user" =~ ^#.*$ || -z "$user" ]] && continue
        user=$(echo "$user" | tr -d '[:space:]')
        if ! oc get group "$GROUP_NAME" -o jsonpath='{.users[*]}' 2>/dev/null | grep -qw "$user"; then
            oc adm groups add-users "$GROUP_NAME" "$user" 2>/dev/null && echo "  Added user: $user" || echo "  Warning: Could not add user: $user"
        else
            echo "  Already in group: $user"
        fi
    done < "$ADMINS_FILE"
    # Grant edit role on namespace
    oc adm policy add-role-to-group edit "$GROUP_NAME" -n "$NAMESPACE" 2>/dev/null
    echo "Granted edit role to $GROUP_NAME in $NAMESPACE"
else
    echo "No namespace-admins.txt found at $ADMINS_FILE - skipping group setup"
fi
echo ""

# Setup shared OAuth resources BEFORE individual service deploys
ensure_supporting_services_oauth "$NAMESPACE"
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

echo "Step 5/5: Deploying Multi-Agent Platform App..."
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
