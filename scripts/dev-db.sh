#!/bin/bash

# PostgreSQL Development Database Management Script
# This script manages a PostgreSQL container for local development

set -e

# Configuration
POSTGRES_VERSION="${POSTGRES_VERSION:-15-alpine}"
CONTAINER_TOOL="${CONTAINER_TOOL:-docker}"
CONTAINER_NAME="app-postgres-dev"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${POSTGRES_USER:-app}"
DB_PASS="${POSTGRES_PASSWORD:-changethis}"
DB_NAME="${POSTGRES_DB:-app}"
VOLUME_NAME="app-db-data"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

case "$1" in
    start)
        log_info "Starting PostgreSQL development database..."

        # Check if container already exists (exact match)
        if $CONTAINER_TOOL ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
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

        log_info "Waiting for database to be ready..."
        sleep 3

        # Wait for database to be healthy
        for i in {1..30}; do
            if $CONTAINER_TOOL exec $CONTAINER_NAME pg_isready -U $DB_USER > /dev/null 2>&1; then
                log_info "Database is ready!"
                log_info "Connection string: postgresql://$DB_USER:$DB_PASS@localhost:$DB_PORT/$DB_NAME"
                exit 0
            fi
            echo -n "."
            sleep 1
        done

        log_error "Database failed to start within 30 seconds"
        exit 1
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
        if $CONTAINER_TOOL ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
            log_info "PostgreSQL is running"
            $CONTAINER_TOOL ps --filter "name=^${CONTAINER_NAME}$"
        else
            log_warn "PostgreSQL is not running"
            exit 1
        fi
        ;;

    *)
        echo "Usage: $0 {start|stop|remove|reset|logs|shell|status}"
        echo ""
        echo "Commands:"
        echo "  start  - Start the PostgreSQL container"
        echo "  stop   - Stop the PostgreSQL container"
        echo "  remove - Remove container (keeps data)"
        echo "  reset  - Remove container and all data"
        echo "  logs   - Show PostgreSQL logs"
        echo "  shell  - Open PostgreSQL shell"
        echo "  status - Check if PostgreSQL is running"
        echo ""
        echo "Environment variables:"
        echo "  POSTGRES_VERSION - PostgreSQL version (default: 15-alpine)"
        echo "  CONTAINER_TOOL   - Container tool to use (default: docker)"
        echo "  DB_PORT          - Database port (default: 5432)"
        echo "  POSTGRES_USER    - Database user (default: app)"
        echo "  POSTGRES_PASSWORD- Database password (default: changethis)"
        echo "  POSTGRES_DB      - Database name (default: app)"
        exit 1
        ;;
esac
