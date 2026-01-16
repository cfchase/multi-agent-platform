#!/bin/bash

# OAuth2 Proxy Development Script
# Runs oauth2-proxy locally for testing OAuth authentication flow
# Proxies requests to frontend (8080) which proxies /api to backend (8000)

set -e

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

# Initialize container tool
init_container_tool || exit 1

# Configuration
CONTAINER_NAME="app-oauth-proxy-dev"
OAUTH_PORT="${OAUTH_PORT:-4180}"
OAUTH_IMAGE="quay.io/oauth2-proxy/oauth2-proxy:v7.6.0"

# Load OAuth secrets from backend/.env (source of truth for server config)
ENV_FILE="${SCRIPT_DIR}/../backend/.env"
if [ -f "$ENV_FILE" ]; then
    # Only extract OAuth-related variables (safer than sourcing entire file)
    GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-$(grep -E '^GOOGLE_CLIENT_ID=' "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '"' || true)}"
    GOOGLE_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET:-$(grep -E '^GOOGLE_CLIENT_SECRET=' "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '"' || true)}"
    OAUTH_COOKIE_SECRET="${OAUTH_COOKIE_SECRET:-$(grep -E '^OAUTH_COOKIE_SECRET=' "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '"' || true)}"
fi

# Ensure variables are set (even if empty)
GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-}"
GOOGLE_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET:-}"
OAUTH_COOKIE_SECRET="${OAUTH_COOKIE_SECRET:-}"

check_required_vars() {
    local missing=0
    if [ -z "$GOOGLE_CLIENT_ID" ]; then
        log_error "GOOGLE_CLIENT_ID is not set"
        missing=1
    fi
    if [ -z "$GOOGLE_CLIENT_SECRET" ]; then
        log_error "GOOGLE_CLIENT_SECRET is not set"
        missing=1
    fi
    if [ -z "$OAUTH_COOKIE_SECRET" ]; then
        log_warn "OAUTH_COOKIE_SECRET not set, generating random one..."
        OAUTH_COOKIE_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
    fi
    if [ $missing -eq 1 ]; then
        log_error "Add these to backend/.env:"
        echo "  GOOGLE_CLIENT_ID=your-id.apps.googleusercontent.com"
        echo "  GOOGLE_CLIENT_SECRET=your-secret"
        echo "  OAUTH_COOKIE_SECRET=\$(python -c \"import secrets; print(secrets.token_urlsafe(32))\")"
        exit 1
    fi
}

start_oauth() {
    check_required_vars

    if $CONTAINER_TOOL ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${CONTAINER_NAME}$" || \
       $CONTAINER_TOOL ps -a --format '{{.Names}}' 2>/dev/null | grep -q "${CONTAINER_NAME}"; then
        log_info "Removing existing container..."
        $CONTAINER_TOOL rm -f $CONTAINER_NAME > /dev/null 2>&1 || true
    fi

    log_info "Starting OAuth2 Proxy on port $OAUTH_PORT..."
    log_info "Upstream: http://host.docker.internal:8080 (frontend)"

    # Determine host gateway for container to reach host services
    if [ "$CONTAINER_TOOL" = "podman" ]; then
        HOST_GATEWAY="host.containers.internal"
    else
        HOST_GATEWAY="host.docker.internal"
    fi

    $CONTAINER_TOOL run -d \
        --name $CONTAINER_NAME \
        --add-host=host.docker.internal:host-gateway \
        --add-host=host.containers.internal:host-gateway \
        -p ${OAUTH_PORT}:4180 \
        -e OAUTH2_PROXY_HTTP_ADDRESS="0.0.0.0:4180" \
        -e OAUTH2_PROXY_UPSTREAMS="http://${HOST_GATEWAY}:8080" \
        -e OAUTH2_PROXY_PROVIDER="google" \
        -e OAUTH2_PROXY_CLIENT_ID="$GOOGLE_CLIENT_ID" \
        -e OAUTH2_PROXY_CLIENT_SECRET="$GOOGLE_CLIENT_SECRET" \
        -e OAUTH2_PROXY_COOKIE_SECRET="$OAUTH_COOKIE_SECRET" \
        -e OAUTH2_PROXY_COOKIE_SECURE="false" \
        -e OAUTH2_PROXY_COOKIE_SAMESITE="lax" \
        -e OAUTH2_PROXY_EMAIL_DOMAINS="*" \
        -e OAUTH2_PROXY_PASS_USER_HEADERS="true" \
        -e OAUTH2_PROXY_SET_XAUTHREQUEST="true" \
        -e OAUTH2_PROXY_SKIP_PROVIDER_BUTTON="true" \
        -e OAUTH2_PROXY_REDIRECT_URL="http://localhost:${OAUTH_PORT}/oauth2/callback" \
        $OAUTH_IMAGE

    log_info "OAuth2 Proxy started!"
    echo ""
    log_info "Access your app at: http://localhost:${OAUTH_PORT}"
    echo ""
    log_warn "Make sure you have these in your Google OAuth credentials:"
    echo "  - Authorized JavaScript origins: http://localhost:${OAUTH_PORT}"
    echo "  - Authorized redirect URIs: http://localhost:${OAUTH_PORT}/oauth2/callback"
}

stop_oauth() {
    log_info "Stopping OAuth2 Proxy..."
    $CONTAINER_TOOL stop $CONTAINER_NAME 2>/dev/null || true
    $CONTAINER_TOOL rm $CONTAINER_NAME 2>/dev/null || true
    log_info "OAuth2 Proxy stopped"
}

status_oauth() {
    if $CONTAINER_TOOL ps --format '{{.Names}}' 2>/dev/null | grep -q "^${CONTAINER_NAME}$" || \
       $CONTAINER_TOOL ps --format '{{.Names}}' 2>/dev/null | grep -q "${CONTAINER_NAME}"; then
        log_info "OAuth2 Proxy is running"
        $CONTAINER_TOOL ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    else
        log_warn "OAuth2 Proxy is not running"
        return 1
    fi
}

logs_oauth() {
    $CONTAINER_TOOL logs -f $CONTAINER_NAME
}

show_help() {
    echo "Usage: $0 {start|stop|status|logs|help}"
    echo ""
    echo "Commands:"
    echo "  start   Start OAuth2 Proxy (requires Google credentials in backend/.env)"
    echo "  stop    Stop OAuth2 Proxy"
    echo "  status  Check if OAuth2 Proxy is running"
    echo "  logs    Follow OAuth2 Proxy logs"
    echo "  help    Show this help message"
    echo ""
    echo "Required variables in backend/.env:"
    echo "  GOOGLE_CLIENT_ID       Google OAuth Client ID"
    echo "  GOOGLE_CLIENT_SECRET   Google OAuth Client Secret"
    echo "  OAUTH_COOKIE_SECRET    Random 32-byte base64 string (auto-generated if not set)"
    echo ""
    echo "Google OAuth Setup:"
    echo "  1. Go to https://console.cloud.google.com/apis/credentials"
    echo "  2. Create OAuth 2.0 Client ID (Web application)"
    echo "  3. Add authorized JavaScript origin: http://localhost:4180"
    echo "  4. Add authorized redirect URI: http://localhost:4180/oauth2/callback"
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
