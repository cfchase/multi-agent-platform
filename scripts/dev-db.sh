#!/bin/bash

# PostgreSQL Development Database Management Script
# This script manages a PostgreSQL container for local development
# Supports multiple databases for the app and supporting services

set -e

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

# Initialize container tool (uses CONTAINER_TOOL env var from Makefile, or auto-detects)
init_container_tool || exit 1

# Configuration
POSTGRES_VERSION="${POSTGRES_VERSION:-15-alpine}"
CONTAINER_NAME="app-postgres-dev"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${POSTGRES_USER:-app}"
DB_PASS="${POSTGRES_PASSWORD:-changethis}"
DB_NAME="${POSTGRES_DB:-deep-research}"
VOLUME_NAME="app-db-data"

# Additional databases for supporting services
# These are created automatically on startup
ADDITIONAL_DBS="${ADDITIONAL_DBS:-langflow langfuse mlflow}"

# Create additional databases in the running container
create_additional_dbs() {
    log_info "Creating additional databases..."
    for db in $ADDITIONAL_DBS; do
        # Check if database already exists (connect to primary db)
        if $CONTAINER_TOOL exec $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME -lqt | cut -d \| -f 1 | grep -qw "$db"; then
            log_info "Database '$db' already exists"
        else
            log_info "Creating database '$db'..."
            $CONTAINER_TOOL exec $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME -c "CREATE DATABASE \"$db\";" > /dev/null
            log_info "Database '$db' created"
        fi
    done
}

# Wait for database to be ready
wait_for_db() {
    log_info "Waiting for database to be ready..."
    sleep 3

    for i in {1..30}; do
        if $CONTAINER_TOOL exec $CONTAINER_NAME pg_isready -U $DB_USER > /dev/null 2>&1; then
            return 0
        fi
        echo -n "."
        sleep 1
    done

    log_error "Database failed to start within 30 seconds"
    return 1
}

case "$1" in
    start)
        log_info "Starting PostgreSQL development database..."
        log_info "Using container tool: $CONTAINER_TOOL"

        # Check if container already exists (exact match)
        if container_exists "$CONTAINER_NAME"; then
            log_warn "Container $CONTAINER_NAME already exists. Starting it..."
            $CONTAINER_TOOL start $CONTAINER_NAME
        else
            log_info "Creating new PostgreSQL container..."
            $CONTAINER_TOOL run -d \
                --name $CONTAINER_NAME \
                -e POSTGRES_USER=$DB_USER \
                -e POSTGRES_PASSWORD=$DB_PASS \
                -e POSTGRES_DB=$DB_NAME \
                -p $DB_PORT:5432 \
                -v $VOLUME_NAME:/var/lib/postgresql/data \
                --health-cmd="pg_isready -U $DB_USER" \
                --health-interval=10s \
                --health-timeout=5s \
                --health-retries=5 \
                postgres:$POSTGRES_VERSION
        fi

        if wait_for_db; then
            log_info "Database is ready!"

            # Create additional databases for services
            create_additional_dbs

            log_info "Connection string: postgresql://$DB_USER:$DB_PASS@localhost:$DB_PORT/$DB_NAME"
            log_info "Available databases: $DB_NAME $ADDITIONAL_DBS"
        else
            exit 1
        fi
        ;;

    stop)
        log_info "Stopping PostgreSQL container..."
        $CONTAINER_TOOL stop $CONTAINER_NAME
        log_info "Container stopped"
        ;;

    remove)
        log_warn "Removing PostgreSQL container (data will be preserved)..."
        $CONTAINER_TOOL rm -f $CONTAINER_NAME
        log_info "Container removed"
        ;;

    reset)
        log_warn "This will delete all database data. Are you sure? (y/N)"
        read -r response
        if [[ "$response" == "y" || "$response" == "Y" ]]; then
            log_info "Removing container and data..."
            $CONTAINER_TOOL rm -f $CONTAINER_NAME 2>/dev/null || true
            $CONTAINER_TOOL volume rm $VOLUME_NAME 2>/dev/null || true
            log_info "Database completely reset"
        else
            log_info "Reset cancelled"
        fi
        ;;

    logs)
        log_info "Showing PostgreSQL logs (Ctrl+C to exit)..."
        $CONTAINER_TOOL logs -f $CONTAINER_NAME
        ;;

    shell)
        log_info "Connecting to PostgreSQL shell..."
        $CONTAINER_TOOL exec -it $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME
        ;;

    status)
        if container_running "$CONTAINER_NAME"; then
            log_info "PostgreSQL is running"
            $CONTAINER_TOOL ps --filter "name=^${CONTAINER_NAME}$"
            echo ""
            log_info "Databases:"
            $CONTAINER_TOOL exec $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME -c "\l" 2>/dev/null | grep -E "^\s+\w+" | head -10 || true
        else
            log_warn "PostgreSQL is not running"
            exit 1
        fi
        ;;

    create-dbs)
        if container_running "$CONTAINER_NAME"; then
            create_additional_dbs
        else
            log_error "PostgreSQL is not running. Start it first with: $0 start"
            exit 1
        fi
        ;;

    list-dbs)
        if container_running "$CONTAINER_NAME"; then
            log_info "Listing databases..."
            $CONTAINER_TOOL exec $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME -c "\l"
        else
            log_error "PostgreSQL is not running. Start it first with: $0 start"
            exit 1
        fi
        ;;

    *)
        echo "Usage: $0 {start|stop|remove|reset|logs|shell|status|create-dbs|list-dbs}"
        echo ""
        echo "Commands:"
        echo "  start      - Start the PostgreSQL container and create all databases"
        echo "  stop       - Stop the PostgreSQL container"
        echo "  remove     - Remove container (keeps data)"
        echo "  reset      - Remove container and all data"
        echo "  logs       - Show PostgreSQL logs"
        echo "  shell      - Open PostgreSQL shell"
        echo "  status     - Check if PostgreSQL is running and list databases"
        echo "  create-dbs - Create additional databases (langflow, mlflow)"
        echo "  list-dbs   - List all databases"
        echo ""
        echo "Environment variables:"
        echo "  POSTGRES_VERSION  - PostgreSQL version (default: 15-alpine)"
        echo "  CONTAINER_TOOL    - Container tool (auto-detected: podman or docker)"
        echo "  DB_PORT           - Database port (default: 5432)"
        echo "  POSTGRES_USER     - Database user (default: app)"
        echo "  POSTGRES_PASSWORD - Database password (default: changethis)"
        echo "  POSTGRES_DB       - Primary database name (default: deep-research)"
        echo "  ADDITIONAL_DBS    - Space-separated additional databases (default: langflow langfuse mlflow)"
        exit 1
        ;;
esac
