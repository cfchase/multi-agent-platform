#!/bin/bash

# OAuth2 Proxy Development Script
# Runs oauth2-proxy locally for testing OAuth authentication flow
# Supports multiple providers (Google, GitHub, Keycloak) or mock OAuth for local dev
#
# When no OAuth credentials are configured, starts a mock OAuth server
# that allows login with any username/password.

set -e

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

# Initialize container tool
init_container_tool || exit 1

# Configuration
OAUTH_PROXY_CONTAINER="app-oauth-proxy-dev"
MOCK_OAUTH_CONTAINER="app-mock-oauth-dev"
OAUTH_PORT="${OAUTH_PORT:-4180}"
MOCK_OAUTH_PORT="${MOCK_OAUTH_PORT:-9099}"
OAUTH_PROXY_IMAGE="quay.io/oauth2-proxy/oauth2-proxy:v7.6.0"
MOCK_OAUTH_IMAGE="ghcr.io/navikt/mock-oauth2-server:2.1.10"

# Load OAuth config from backend/.env
ENV_FILE="${SCRIPT_DIR}/../backend/.env"
if [ -f "$ENV_FILE" ]; then
    OAUTH_CLIENT_ID="${OAUTH_CLIENT_ID:-$(grep -E '^OAUTH_CLIENT_ID=' "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '"' || true)}"
    OAUTH_CLIENT_SECRET="${OAUTH_CLIENT_SECRET:-$(grep -E '^OAUTH_CLIENT_SECRET=' "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '"' || true)}"
    OAUTH_ISSUER_URL="${OAUTH_ISSUER_URL:-$(grep -E '^OAUTH_ISSUER_URL=' "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '"' || true)}"
    OAUTH_COOKIE_SECRET="${OAUTH_COOKIE_SECRET:-$(grep -E '^OAUTH_COOKIE_SECRET=' "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '"' || true)}"

    # Legacy support: fall back to GOOGLE_* if OAUTH_* not set
    if [ -z "$OAUTH_CLIENT_ID" ]; then
        OAUTH_CLIENT_ID="${GOOGLE_CLIENT_ID:-$(grep -E '^GOOGLE_CLIENT_ID=' "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '"' || true)}"
        OAUTH_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET:-$(grep -E '^GOOGLE_CLIENT_SECRET=' "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '"' || true)}"
    fi
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

# Check if real OAuth is configured
is_oauth_configured() {
    if [ -z "$OAUTH_CLIENT_ID" ]; then
        return 1
    fi
    # Check for placeholder values
    if [ "$OAUTH_CLIENT_ID" = "your-client-id" ] || \
       [ "$OAUTH_CLIENT_ID" = "your-client-id.apps.googleusercontent.com" ]; then
        return 1
    fi
    if [ -z "$OAUTH_CLIENT_SECRET" ] || [ "$OAUTH_CLIENT_SECRET" = "your-client-secret" ]; then
        return 1
    fi
    return 0
}

# Start mock OAuth server
start_mock_oauth() {
    if container_running "$MOCK_OAUTH_CONTAINER"; then
        log_info "Mock OAuth server already running"
        return 0
    fi

    # Remove existing stopped container
    $CONTAINER_TOOL rm -f $MOCK_OAUTH_CONTAINER 2>/dev/null || true

    log_info "Starting mock OAuth server on port $MOCK_OAUTH_PORT..."

    $CONTAINER_TOOL run -d \
        --name $MOCK_OAUTH_CONTAINER \
        -p ${MOCK_OAUTH_PORT}:8080 \
        -e JSON_CONFIG='{"interactiveLogin": true}' \
        $MOCK_OAUTH_IMAGE

    # Wait for mock server to be ready
    for i in {1..30}; do
        if curl -s "http://localhost:${MOCK_OAUTH_PORT}/.well-known/openid-configuration" > /dev/null 2>&1; then
            log_info "Mock OAuth server ready"
            return 0
        fi
        sleep 1
    done

    log_error "Mock OAuth server failed to start"
    return 1
}

# Stop mock OAuth server
stop_mock_oauth() {
    $CONTAINER_TOOL stop $MOCK_OAUTH_CONTAINER 2>/dev/null || true
    $CONTAINER_TOOL rm $MOCK_OAUTH_CONTAINER 2>/dev/null || true
}

# Start OAuth2 Proxy with real provider
start_oauth_real() {
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
}

# Start OAuth2 Proxy with mock server
start_oauth_mock() {
    log_info "Starting OAuth2 Proxy with mock OAuth server"
    log_info "Upstream: http://${HOST_GATEWAY}:8080 (frontend)"

    # Mock OAuth server runs on host, proxy connects to it
    local mock_issuer="http://${HOST_GATEWAY}:${MOCK_OAUTH_PORT}/default"

    $CONTAINER_TOOL run -d \
        --name $OAUTH_PROXY_CONTAINER \
        --add-host=host.docker.internal:host-gateway \
        --add-host=host.containers.internal:host-gateway \
        -p ${OAUTH_PORT}:4180 \
        -e OAUTH2_PROXY_HTTP_ADDRESS="0.0.0.0:4180" \
        -e OAUTH2_PROXY_UPSTREAMS="http://${HOST_GATEWAY}:8080" \
        -e OAUTH2_PROXY_PROVIDER="oidc" \
        -e OAUTH2_PROXY_OIDC_ISSUER_URL="$mock_issuer" \
        -e OAUTH2_PROXY_CLIENT_ID="mock-client" \
        -e OAUTH2_PROXY_CLIENT_SECRET="mock-secret" \
        -e OAUTH2_PROXY_COOKIE_SECRET="$OAUTH_COOKIE_SECRET" \
        -e OAUTH2_PROXY_COOKIE_SECURE="false" \
        -e OAUTH2_PROXY_COOKIE_SAMESITE="lax" \
        -e OAUTH2_PROXY_EMAIL_DOMAINS="*" \
        -e OAUTH2_PROXY_PASS_USER_HEADERS="true" \
        -e OAUTH2_PROXY_SET_XAUTHREQUEST="true" \
        -e OAUTH2_PROXY_INSECURE_OIDC_ALLOW_UNVERIFIED_EMAIL="true" \
        -e OAUTH2_PROXY_REDIRECT_URL="http://localhost:${OAUTH_PORT}/oauth2/callback" \
        -e OAUTH2_PROXY_CODE_CHALLENGE_METHOD="S256" \
        $OAUTH_PROXY_IMAGE
}

start_oauth() {
    # Remove any existing proxy container
    $CONTAINER_TOOL rm -f $OAUTH_PROXY_CONTAINER 2>/dev/null || true

    if is_oauth_configured; then
        start_oauth_real
        echo ""
        if [ -n "$OAUTH_ISSUER_URL" ]; then
            log_info "OAuth2 Proxy started with OIDC provider"
        else
            log_info "OAuth2 Proxy started with Google provider"
        fi
    else
        start_mock_oauth || exit 1
        start_oauth_mock
        echo ""
        log_info "OAuth2 Proxy started with MOCK OAuth (any username/password works)"
        log_warn "Configure OAUTH_CLIENT_ID/SECRET in backend/.env for real OAuth"
    fi

    # Wait for proxy to be ready
    for i in {1..30}; do
        if curl -s "http://localhost:${OAUTH_PORT}/ping" > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done

    echo ""
    log_info "Access your app at: http://localhost:${OAUTH_PORT}"
}

stop_oauth() {
    log_info "Stopping OAuth services..."
    $CONTAINER_TOOL stop $OAUTH_PROXY_CONTAINER 2>/dev/null || true
    $CONTAINER_TOOL rm $OAUTH_PROXY_CONTAINER 2>/dev/null || true
    stop_mock_oauth
    log_info "OAuth services stopped"
}

status_oauth() {
    local running=0

    if container_running "$OAUTH_PROXY_CONTAINER"; then
        log_info "OAuth2 Proxy is running"
        $CONTAINER_TOOL ps --filter "name=$OAUTH_PROXY_CONTAINER" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        running=1
    fi

    if container_running "$MOCK_OAUTH_CONTAINER"; then
        log_info "Mock OAuth server is running"
        $CONTAINER_TOOL ps --filter "name=$MOCK_OAUTH_CONTAINER" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        running=1
    fi

    if [ $running -eq 0 ]; then
        log_warn "OAuth services are not running"
        return 1
    fi
    return 0
}

logs_oauth() {
    local container="${2:-$OAUTH_PROXY_CONTAINER}"
    if [ "$2" = "mock" ]; then
        container="$MOCK_OAUTH_CONTAINER"
    fi
    $CONTAINER_TOOL logs -f $container
}

show_help() {
    echo "Usage: $0 {start|stop|status|logs|help}"
    echo ""
    echo "Commands:"
    echo "  start             Start OAuth2 Proxy (uses mock if no credentials configured)"
    echo "  stop              Stop OAuth2 Proxy and mock server"
    echo "  status            Check OAuth service status"
    echo "  logs [mock]       Follow OAuth2 Proxy logs (or mock server logs)"
    echo "  help              Show this help message"
    echo ""
    echo "Environment variables in backend/.env:"
    echo "  OAUTH_CLIENT_ID     OAuth Client ID"
    echo "  OAUTH_CLIENT_SECRET OAuth Client Secret"
    echo "  OAUTH_ISSUER_URL    OIDC Issuer URL (optional, enables OIDC mode)"
    echo "  OAUTH_COOKIE_SECRET Random 32-byte base64 string (auto-generated if not set)"
    echo ""
    echo "Provider auto-detection:"
    echo "  - If OAUTH_ISSUER_URL is set: uses OIDC provider (Keycloak, Okta, etc.)"
    echo "  - If OAUTH_ISSUER_URL is not set: uses Google provider (default)"
    echo "  - If OAUTH_CLIENT_ID is not set: uses mock OAuth server"
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
        logs_oauth "$@"
        ;;
    help|*)
        show_help
        ;;
esac
