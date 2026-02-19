#!/bin/bash

# OAuth2 Proxy Development Script
# Runs oauth2-proxy locally for testing OAuth authentication flow
# Supports Google OAuth (default) or OIDC providers (Keycloak, Okta, etc.)
#
# Requires OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET in config/local/.env

set -e

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

# Initialize container tool
init_container_tool || exit 1

# Configuration
OAUTH_PROXY_CONTAINER="app-oauth-proxy-dev"
OAUTH_PORT="${OAUTH_PORT:-4180}"
OAUTH_PROXY_IMAGE="quay.io/oauth2-proxy/oauth2-proxy:v7.6.0"

# Load consolidated config
CONFIG_FILE="${SCRIPT_DIR}/../config/local/.env"
if [ -f "$CONFIG_FILE" ]; then
    set -a; source "$CONFIG_FILE"; set +a
fi

# Ensure cookie secret exists
if [ -z "$OAUTH_COOKIE_SECRET" ] || [ "$OAUTH_COOKIE_SECRET" = "changethis_generate_a_secure_random_key" ]; then
    OAUTH_COOKIE_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)
fi

# Determine host gateway for container networking
get_host_gateway() {
    if [ "$CONTAINER_TOOL" = "podman" ]; then
        echo "host.containers.internal"
    else
        echo "host.docker.internal"
    fi
}

HOST_GATEWAY=$(get_host_gateway)

# Check if OAuth is configured
is_oauth_configured() {
    if [ -z "$OAUTH_CLIENT_ID" ] || [ "$OAUTH_CLIENT_ID" = "your-client-id" ]; then
        return 1
    fi
    if [ -z "$OAUTH_CLIENT_SECRET" ] || [ "$OAUTH_CLIENT_SECRET" = "your-client-secret" ]; then
        return 1
    fi
    return 0
}

start_oauth() {
    if ! is_oauth_configured; then
        log_warn "OAuth not configured - skipping OAuth2 Proxy"
        log_info "To enable OAuth, set OAUTH_CLIENT_ID/SECRET in config/local/.env"
        log_info "Using ENVIRONMENT=local with dev-user for local development"
        return 0
    fi

    # Remove any existing proxy container
    $CONTAINER_TOOL rm -f $OAUTH_PROXY_CONTAINER 2>/dev/null || true

    # Auto-detect provider: OIDC if issuer URL set, otherwise Google
    local provider_args=""
    local provider_name=""

    if [ -n "$OAUTH_ISSUER_URL" ]; then
        provider_name="OIDC ($OAUTH_ISSUER_URL)"
        provider_args="-e OAUTH2_PROXY_PROVIDER=oidc -e OAUTH2_PROXY_OIDC_ISSUER_URL=$OAUTH_ISSUER_URL"
    else
        provider_name="Google"
        provider_args="-e OAUTH2_PROXY_PROVIDER=google"
    fi

    log_info "Starting OAuth2 Proxy with provider: $provider_name"
    log_info "Upstream: http://${HOST_GATEWAY}:8080 (frontend)"

    $CONTAINER_TOOL run -d \
        --name $OAUTH_PROXY_CONTAINER \
        --add-host=host.docker.internal:host-gateway \
        --add-host=host.containers.internal:host-gateway \
        -p ${OAUTH_PORT}:4180 \
        -e OAUTH2_PROXY_HTTP_ADDRESS="0.0.0.0:4180" \
        -e OAUTH2_PROXY_UPSTREAMS="http://${HOST_GATEWAY}:8080" \
        $provider_args \
        -e OAUTH2_PROXY_CLIENT_ID="$OAUTH_CLIENT_ID" \
        -e OAUTH2_PROXY_CLIENT_SECRET="$OAUTH_CLIENT_SECRET" \
        -e OAUTH2_PROXY_COOKIE_SECRET="$OAUTH_COOKIE_SECRET" \
        -e OAUTH2_PROXY_COOKIE_SECURE="false" \
        -e OAUTH2_PROXY_COOKIE_SAMESITE="lax" \
        -e OAUTH2_PROXY_EMAIL_DOMAINS="*" \
        -e OAUTH2_PROXY_PASS_USER_HEADERS="true" \
        -e OAUTH2_PROXY_SET_XAUTHREQUEST="true" \
        -e OAUTH2_PROXY_SKIP_PROVIDER_BUTTON="true" \
        -e OAUTH2_PROXY_REDIRECT_URL="http://localhost:${OAUTH_PORT}/oauth2/callback" \
        $OAUTH_PROXY_IMAGE

    # Wait for proxy to be ready
    for i in {1..30}; do
        if curl -s "http://localhost:${OAUTH_PORT}/ping" > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    echo ""
    log_info "OAuth2 Proxy started with $provider_name provider"
    log_info "Access your app at: http://localhost:${OAUTH_PORT}"
}

stop_oauth() {
    log_info "Stopping OAuth2 Proxy..."
    $CONTAINER_TOOL stop $OAUTH_PROXY_CONTAINER 2>/dev/null || true
    $CONTAINER_TOOL rm $OAUTH_PROXY_CONTAINER 2>/dev/null || true
    log_info "OAuth2 Proxy stopped"
}

status_oauth() {
    if container_running "$OAUTH_PROXY_CONTAINER"; then
        log_info "OAuth2 Proxy is running"
        $CONTAINER_TOOL ps --filter "name=$OAUTH_PROXY_CONTAINER" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        return 0
    else
        log_warn "OAuth2 Proxy is not running"
        return 1
    fi
}

logs_oauth() {
    $CONTAINER_TOOL logs -f $OAUTH_PROXY_CONTAINER
}

show_help() {
    echo "Usage: $0 {start|stop|status|logs|help}"
    echo ""
    echo "Commands:"
    echo "  start   Start OAuth2 Proxy (requires credentials in config/local/.env)"
    echo "  stop    Stop OAuth2 Proxy"
    echo "  status  Check OAuth2 Proxy status"
    echo "  logs    Follow OAuth2 Proxy logs"
    echo "  help    Show this help message"
    echo ""
    echo "Required environment variables in config/local/.env:"
    echo "  OAUTH_CLIENT_ID      OAuth Client ID"
    echo "  OAUTH_CLIENT_SECRET  OAuth Client Secret"
    echo ""
    echo "Optional environment variables:"
    echo "  OAUTH_ISSUER_URL     OIDC Issuer URL (enables OIDC mode for Keycloak, Okta, etc.)"
    echo "  OAUTH_COOKIE_SECRET  Random 32-byte base64 string (auto-generated if not set)"
    echo ""
    echo "Provider auto-detection:"
    echo "  - If OAUTH_ISSUER_URL is set: uses OIDC provider"
    echo "  - If OAUTH_ISSUER_URL is not set: uses Google provider (default)"
    echo ""
    echo "For local development without OAuth:"
    echo "  Set ENVIRONMENT=local in backend/.env"
}

case "${1:-help}" in
    start)
        start_oauth
        ;;
    stop)
        stop_oauth
        ;;
    status)
        status_oauth
        ;;
    logs)
        logs_oauth
        ;;
    help|*)
        show_help
        ;;
esac
