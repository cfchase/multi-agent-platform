#!/bin/bash

# MLFlow Development Server Management Script
# This script manages an MLFlow container for local development
# Connects to the shared PostgreSQL database for metadata storage

set -e

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

# Initialize container tool (uses CONTAINER_TOOL env var from Makefile, or auto-detects)
init_container_tool || exit 1

# Configuration
MLFLOW_VERSION="${MLFLOW_VERSION:-latest}"
CONTAINER_NAME="app-mlflow-dev"
MLFLOW_PORT="${MLFLOW_PORT:-5000}"
PROJECT_ROOT="${SCRIPT_DIR}/.."
DATA_DIR="${PROJECT_ROOT}/.local/mlflow"

# Load config from centralized config directory
MLFLOW_CONFIG="$PROJECT_ROOT/config/local/.env.mlflow"
if [ -f "$MLFLOW_CONFIG" ]; then
    set -a; source "$MLFLOW_CONFIG"; set +a
fi
POSTGRES_CONFIG="$PROJECT_ROOT/config/local/.env.postgres"
if [ -f "$POSTGRES_CONFIG" ]; then
    set -a; source "$POSTGRES_CONFIG"; set +a
fi

# Database connection (connects to shared PostgreSQL)
DB_USER="${POSTGRES_USER:-app}"
DB_PASS="${POSTGRES_PASSWORD:-changethis}"
DB_NAME="${MLFLOW_DB:-mlflow}"
DB_PORT="${DB_PORT:-5432}"

# Determine host address for connecting to PostgreSQL on host
get_db_host() {
    if [ "$CONTAINER_TOOL" = "podman" ]; then
        echo "host.containers.internal"
    else
        echo "host.docker.internal"
    fi
}

DB_HOST=$(get_db_host)
BACKEND_STORE_URI="postgresql://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

case "$1" in
    start)
        log_info "Starting MLFlow development server..."
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
            log_info "Creating new MLFlow container..."

            # Create data directory
            mkdir -p "$DATA_DIR"

            # MLFlow server with PostgreSQL backend and local artifact storage
            # Install psycopg2-binary at startup (official image doesn't include it)
            # Then run mlflow server with PostgreSQL backend
            $CONTAINER_TOOL run -d \
                --name $CONTAINER_NAME \
                -p $MLFLOW_PORT:5000 \
                -v "${DATA_DIR}:/mlflow/artifacts" \
                --add-host=host.docker.internal:host-gateway \
                --add-host=host.containers.internal:host-gateway \
                ghcr.io/mlflow/mlflow:v2.19.0 \
                bash -c "pip install --quiet psycopg2-binary && mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri '$BACKEND_STORE_URI' --default-artifact-root /mlflow/artifacts"
        fi

        log_info "Waiting for MLFlow to be ready..."
        sleep 3

        # Wait for MLFlow to respond
        for i in {1..60}; do
            if curl -s "http://localhost:$MLFLOW_PORT/health" > /dev/null 2>&1; then
                log_info "MLFlow is ready!"
                log_info "UI available at: http://localhost:$MLFLOW_PORT"
                exit 0
            fi
            echo -n "."
            sleep 2
        done

        log_error "MLFlow failed to start within 120 seconds"
        log_info "Check logs with: $0 logs"
        exit 1
        ;;

    stop)
        log_info "Stopping MLFlow container..."
        $CONTAINER_TOOL stop $CONTAINER_NAME 2>/dev/null || log_warn "Container not running"
        log_info "Container stopped"
        ;;

    remove)
        log_warn "Removing MLFlow container (artifacts will be preserved in volume)..."
        $CONTAINER_TOOL rm -f $CONTAINER_NAME 2>/dev/null || true
        log_info "Container removed"
        ;;

    reset)
        if [[ "$2" == "-y" || "$2" == "--yes" ]]; then
            log_info "Removing container and data..."
            $CONTAINER_TOOL rm -f $CONTAINER_NAME 2>/dev/null || true
            rm -rf "$DATA_DIR" 2>/dev/null || true
            log_info "MLFlow completely reset"
        else
            log_warn "This will delete all MLFlow data including artifacts. Are you sure? (y/N)"
            read -r response
            if [[ "$response" == "y" || "$response" == "Y" ]]; then
                log_info "Removing container and data..."
                $CONTAINER_TOOL rm -f $CONTAINER_NAME 2>/dev/null || true
                rm -rf "$DATA_DIR" 2>/dev/null || true
                log_info "MLFlow completely reset"
            else
                log_info "Reset cancelled"
            fi
        fi
        ;;

    logs)
        if [ "$2" = "-f" ] || [ "$2" = "--follow" ]; then
            log_info "Streaming MLFlow logs (Ctrl+C to exit)..."
            $CONTAINER_TOOL logs -f $CONTAINER_NAME
        else
            log_info "Showing last 100 lines of MLFlow logs..."
            $CONTAINER_TOOL logs --tail 100 $CONTAINER_NAME
        fi
        ;;

    status)
        if container_running "$CONTAINER_NAME"; then
            log_info "MLFlow is running"
            $CONTAINER_TOOL ps --filter "name=^${CONTAINER_NAME}$"
            echo ""
            log_info "UI: http://localhost:$MLFLOW_PORT"
            log_info "Backend: $DB_NAME on PostgreSQL"
        else
            log_warn "MLFlow is not running"
            exit 1
        fi
        ;;

    shell)
        log_info "Opening shell in MLFlow container..."
        $CONTAINER_TOOL exec -it $CONTAINER_NAME /bin/bash
        ;;

    *)
        echo "Usage: $0 {start|stop|remove|reset|logs|status|shell}"
        echo ""
        echo "Commands:"
        echo "  start  - Start the MLFlow container"
        echo "  stop   - Stop the MLFlow container"
        echo "  remove - Remove container (keeps artifacts volume)"
        echo "  reset  - Remove container and all data"
        echo "  logs   - Show MLFlow logs (use -f to follow)"
        echo "  status - Check if MLFlow is running"
        echo "  shell  - Open shell in container"
        echo ""
        echo "Environment variables:"
        echo "  MLFLOW_VERSION      - MLFlow version (default: latest)"
        echo "  MLFLOW_PORT         - MLFlow port (default: 5000)"
        echo "  POSTGRES_USER       - Database user (default: app)"
        echo "  POSTGRES_PASSWORD   - Database password (default: changethis)"
        echo "  MLFLOW_DB           - Database name (default: mlflow)"
        echo ""
        echo "Prerequisites:"
        echo "  PostgreSQL must be running: make db-start"
        exit 1
        ;;
esac
