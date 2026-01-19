#!/bin/bash

# LangFlow Development Server Management Script
# This script manages a LangFlow container for local development
# Connects to the shared PostgreSQL database

set -e

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

# Initialize container tool (uses CONTAINER_TOOL env var from Makefile, or auto-detects)
init_container_tool || exit 1

# Configuration
LANGFLOW_VERSION="${LANGFLOW_VERSION:-latest}"
CONTAINER_NAME="app-langflow-dev"
LANGFLOW_PORT="${LANGFLOW_PORT:-7860}"
PROJECT_ROOT="${SCRIPT_DIR}/.."
DATA_DIR="${PROJECT_ROOT}/.local/langflow"

# Database connection (connects to shared PostgreSQL)
DB_USER="${POSTGRES_USER:-app}"
DB_PASS="${POSTGRES_PASSWORD:-changethis}"
DB_NAME="${LANGFLOW_DB:-langflow}"
DB_PORT="${DB_PORT:-5432}"

# Determine host address for connecting to PostgreSQL on host
get_db_host() {
    if [ "$CONTAINER_TOOL" = "podman" ]; then
        # Podman uses host.containers.internal to reach host network
        echo "host.containers.internal"
    else
        # Docker uses host.docker.internal
        echo "host.docker.internal"
    fi
}

DB_HOST=$(get_db_host)
DATABASE_URL="postgresql://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

case "$1" in
    start)
        log_info "Starting LangFlow development server..."
        log_info "Using container tool: $CONTAINER_TOOL"

        # Check if PostgreSQL is running
        if ! $CONTAINER_TOOL ps --format '{{.Names}}' | grep -q "^app-postgres-dev$"; then
            log_error "PostgreSQL is not running. Start it first with: make db-start"
            exit 1
        fi

        # Check if container is already running
        if container_running "$CONTAINER_NAME"; then
            log_info "Container $CONTAINER_NAME is already running"
        elif container_exists "$CONTAINER_NAME"; then
            log_info "Starting existing container $CONTAINER_NAME..."
            $CONTAINER_TOOL start $CONTAINER_NAME
        else
            log_info "Creating new LangFlow container..."

            # Create data directory with write permissions
            mkdir -p "$DATA_DIR"

            # Generate a secret key to avoid file permission issues
            SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)

            $CONTAINER_TOOL run -d \
                --name $CONTAINER_NAME \
                -e LANGFLOW_DATABASE_URL="$DATABASE_URL" \
                -e LANGFLOW_CONFIG_DIR=/app/langflow \
                -e LANGFLOW_SECRET_KEY="$SECRET_KEY" \
                -e LANGFLOW_AUTO_LOGIN=true \
                -e LANGFLOW_LOG_LEVEL=info \
                -e LANGFLOW_PORT=7860 \
                -p $LANGFLOW_PORT:7860 \
                -v "${DATA_DIR}:/app/langflow" \
                --add-host=host.docker.internal:host-gateway \
                --add-host=host.containers.internal:host-gateway \
                docker.io/langflowai/langflow:$LANGFLOW_VERSION
        fi

        log_info "Waiting for LangFlow to be ready..."
        sleep 5

        # Wait for LangFlow to respond
        for i in {1..60}; do
            if curl -s "http://localhost:$LANGFLOW_PORT" > /dev/null 2>&1; then
                log_info "LangFlow is ready!"
                log_info "UI available at: http://localhost:$LANGFLOW_PORT"
                exit 0
            fi
            echo -n "."
            sleep 2
        done

        log_error "LangFlow failed to start within 120 seconds"
        log_info "Check logs with: $0 logs"
        exit 1
        ;;

    stop)
        log_info "Stopping LangFlow container..."
        $CONTAINER_TOOL stop $CONTAINER_NAME 2>/dev/null || log_warn "Container not running"
        log_info "Container stopped"
        ;;

    remove)
        log_warn "Removing LangFlow container (data will be preserved in .local/langflow)..."
        $CONTAINER_TOOL rm -f $CONTAINER_NAME 2>/dev/null || true
        log_info "Container removed"
        ;;

    reset)
        if [[ "$2" == "-y" || "$2" == "--yes" ]]; then
            log_info "Removing container and data..."
            $CONTAINER_TOOL rm -f $CONTAINER_NAME 2>/dev/null || true
            rm -rf "$DATA_DIR" 2>/dev/null || true
            log_info "LangFlow completely reset"
        else
            log_warn "This will delete all LangFlow data. Are you sure? (y/N)"
            read -r response
            if [[ "$response" == "y" || "$response" == "Y" ]]; then
                log_info "Removing container and data..."
                $CONTAINER_TOOL rm -f $CONTAINER_NAME 2>/dev/null || true
                rm -rf "$DATA_DIR" 2>/dev/null || true
                log_info "LangFlow completely reset"
            else
                log_info "Reset cancelled"
            fi
        fi
        ;;

    logs)
        if [ "$2" = "-f" ] || [ "$2" = "--follow" ]; then
            log_info "Streaming LangFlow logs (Ctrl+C to exit)..."
            $CONTAINER_TOOL logs -f $CONTAINER_NAME
        else
            log_info "Showing last 100 lines of LangFlow logs..."
            $CONTAINER_TOOL logs --tail 100 $CONTAINER_NAME
        fi
        ;;

    status)
        if container_running "$CONTAINER_NAME"; then
            log_info "LangFlow is running"
            $CONTAINER_TOOL ps --filter "name=^${CONTAINER_NAME}$"
            echo ""
            log_info "UI: http://localhost:$LANGFLOW_PORT"
            log_info "Database: $DB_NAME on PostgreSQL"
        else
            log_warn "LangFlow is not running"
            exit 1
        fi
        ;;

    shell)
        log_info "Opening shell in LangFlow container..."
        $CONTAINER_TOOL exec -it $CONTAINER_NAME /bin/bash
        ;;

    *)
        echo "Usage: $0 {start|stop|remove|reset|logs|status|shell}"
        echo ""
        echo "Commands:"
        echo "  start  - Start the LangFlow container"
        echo "  stop   - Stop the LangFlow container"
        echo "  remove - Remove container (keeps data in .local/langflow)"
        echo "  reset  - Remove container and all data"
        echo "  logs   - Show LangFlow logs (use -f to follow)"
        echo "  status - Check if LangFlow is running"
        echo "  shell  - Open shell in container"
        echo ""
        echo "Environment variables:"
        echo "  LANGFLOW_VERSION  - LangFlow version (default: latest)"
        echo "  LANGFLOW_PORT     - LangFlow port (default: 7860)"
        echo "  POSTGRES_USER     - Database user (default: app)"
        echo "  POSTGRES_PASSWORD - Database password (default: changethis)"
        echo "  LANGFLOW_DB       - Database name (default: langflow)"
        echo ""
        echo "Prerequisites:"
        echo "  PostgreSQL must be running: make db-start"
        exit 1
        ;;
esac
