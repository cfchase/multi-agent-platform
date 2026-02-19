#!/bin/bash

# Langfuse Development Stack Management Script
# This script manages Langfuse v3 containers for local development
# Components: ClickHouse, Redis, MinIO, Langfuse Web, Langfuse Worker
# Connects to the shared PostgreSQL database

set -e

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

# Initialize container tool (uses CONTAINER_TOOL env var from Makefile, or auto-detects)
init_container_tool || exit 1

# Configuration
PROJECT_ROOT="${SCRIPT_DIR}/.."

# Load consolidated config
CONFIG_FILE="$PROJECT_ROOT/config/local/.env"
if [ -f "$CONFIG_FILE" ]; then
    set -a; source "$CONFIG_FILE"; set +a
fi

LANGFUSE_VERSION="${LANGFUSE_VERSION:-3}"
LANGFUSE_WEB_PORT="${LANGFUSE_WEB_PORT:-3000}"
LANGFUSE_WORKER_PORT="${LANGFUSE_WORKER_PORT:-3030}"
DATA_DIR="${PROJECT_ROOT}/.local/langfuse"

# Container names
CLICKHOUSE_CONTAINER="app-langfuse-clickhouse"
REDIS_CONTAINER="app-langfuse-redis"
MINIO_CONTAINER="app-langfuse-minio"
WEB_CONTAINER="app-langfuse-web"
WORKER_CONTAINER="app-langfuse-worker"

# Data directories
CLICKHOUSE_DATA="${DATA_DIR}/clickhouse"
MINIO_DATA="${DATA_DIR}/minio"
REDIS_DATA="${DATA_DIR}/redis"

# Credentials (development only - change for production)
CLICKHOUSE_USER="${CLICKHOUSE_USER:-default}"
CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD:-clickhouse}"
REDIS_PASSWORD="${REDIS_PASSWORD:-redis}"
MINIO_ROOT_USER="${MINIO_ROOT_USER:-minio}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-miniosecret}"
ENCRYPTION_KEY="${ENCRYPTION_KEY:-0000000000000000000000000000000000000000000000000000000000000000}"
NEXTAUTH_SECRET="${NEXTAUTH_SECRET:-mysecret}"
SALT="${SALT:-saltysaltysaltysaltysaltysaltysalty}"

# Database connection (connects to shared PostgreSQL)
DB_USER="${POSTGRES_USER:-app}"
DB_PASS="${POSTGRES_PASSWORD:-changethis}"
DB_NAME="${LANGFUSE_DB:-langfuse}"
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
DATABASE_URL="postgresql://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

# Network name for container communication
NETWORK_NAME="app-langfuse-network"

ensure_network() {
    if ! $CONTAINER_TOOL network inspect $NETWORK_NAME >/dev/null 2>&1; then
        log_info "Creating network $NETWORK_NAME..."
        $CONTAINER_TOOL network create $NETWORK_NAME
    fi
}

start_clickhouse() {
    if container_running "$CLICKHOUSE_CONTAINER"; then
        log_info "ClickHouse already running"
        return 0
    fi

    if container_exists "$CLICKHOUSE_CONTAINER"; then
        log_info "Starting existing ClickHouse container..."
        $CONTAINER_TOOL start $CLICKHOUSE_CONTAINER
    else
        log_info "Creating ClickHouse container..."
        mkdir -p "$CLICKHOUSE_DATA"
        $CONTAINER_TOOL run -d \
            --name $CLICKHOUSE_CONTAINER \
            --network $NETWORK_NAME \
            -e CLICKHOUSE_USER=$CLICKHOUSE_USER \
            -e CLICKHOUSE_PASSWORD=$CLICKHOUSE_PASSWORD \
            -v "${CLICKHOUSE_DATA}:/var/lib/clickhouse" \
            -p 127.0.0.1:8123:8123 \
            -p 127.0.0.1:9000:9000 \
            docker.io/clickhouse/clickhouse-server
    fi
}

start_redis() {
    if container_running "$REDIS_CONTAINER"; then
        log_info "Redis already running"
        return 0
    fi

    if container_exists "$REDIS_CONTAINER"; then
        log_info "Starting existing Redis container..."
        $CONTAINER_TOOL start $REDIS_CONTAINER
    else
        log_info "Creating Redis container..."
        mkdir -p "$REDIS_DATA"
        $CONTAINER_TOOL run -d \
            --name $REDIS_CONTAINER \
            --network $NETWORK_NAME \
            -v "${REDIS_DATA}:/data" \
            -p 127.0.0.1:6379:6379 \
            docker.io/redis:7 \
            redis-server --requirepass $REDIS_PASSWORD
    fi
}

start_minio() {
    if container_running "$MINIO_CONTAINER"; then
        log_info "MinIO already running"
        return 0
    fi

    if container_exists "$MINIO_CONTAINER"; then
        log_info "Starting existing MinIO container..."
        $CONTAINER_TOOL start $MINIO_CONTAINER
    else
        log_info "Creating MinIO container..."
        mkdir -p "$MINIO_DATA"
        $CONTAINER_TOOL run -d \
            --name $MINIO_CONTAINER \
            --network $NETWORK_NAME \
            -e MINIO_ROOT_USER=$MINIO_ROOT_USER \
            -e MINIO_ROOT_PASSWORD=$MINIO_ROOT_PASSWORD \
            -v "${MINIO_DATA}:/data" \
            -p 9090:9000 \
            -p 127.0.0.1:9091:9001 \
            docker.io/minio/minio:latest \
            server /data --console-address ":9001"
    fi

    # Wait for MinIO to be ready and create bucket
    sleep 3
    log_info "Creating langfuse bucket in MinIO..."
    $CONTAINER_TOOL exec $MINIO_CONTAINER mc alias set local http://localhost:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD 2>/dev/null || true
    $CONTAINER_TOOL exec $MINIO_CONTAINER mc mb local/langfuse --ignore-existing 2>/dev/null || true
}

start_langfuse_web() {
    if container_running "$WEB_CONTAINER"; then
        log_info "Langfuse web already running"
        return 0
    fi

    if container_exists "$WEB_CONTAINER"; then
        log_info "Starting existing Langfuse web container..."
        $CONTAINER_TOOL start $WEB_CONTAINER
    else
        log_info "Creating Langfuse web container..."
        $CONTAINER_TOOL run -d \
            --name $WEB_CONTAINER \
            --network $NETWORK_NAME \
            --add-host=host.docker.internal:host-gateway \
            --add-host=host.containers.internal:host-gateway \
            -e DATABASE_URL="$DATABASE_URL" \
            -e NEXTAUTH_URL="http://localhost:${LANGFUSE_WEB_PORT}" \
            -e NEXTAUTH_SECRET="$NEXTAUTH_SECRET" \
            -e ENCRYPTION_KEY="$ENCRYPTION_KEY" \
            -e CLICKHOUSE_URL="http://${CLICKHOUSE_CONTAINER}:8123" \
            -e CLICKHOUSE_MIGRATION_URL="clickhouse://${CLICKHOUSE_CONTAINER}:9000" \
            -e CLICKHOUSE_USER="$CLICKHOUSE_USER" \
            -e CLICKHOUSE_PASSWORD="$CLICKHOUSE_PASSWORD" \
            -e CLICKHOUSE_CLUSTER_ENABLED="false" \
            -e REDIS_HOST="$REDIS_CONTAINER" \
            -e REDIS_PORT="6379" \
            -e REDIS_AUTH="$REDIS_PASSWORD" \
            -e REDIS_CONNECTION_STRING="redis://:${REDIS_PASSWORD}@${REDIS_CONTAINER}:6379" \
            -e SALT="$SALT" \
            -e LANGFUSE_S3_EVENT_UPLOAD_ENABLED="true" \
            -e LANGFUSE_S3_EVENT_UPLOAD_BUCKET="langfuse" \
            -e LANGFUSE_S3_EVENT_UPLOAD_REGION="auto" \
            -e LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT="http://${MINIO_CONTAINER}:9000" \
            -e LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID="$MINIO_ROOT_USER" \
            -e LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY="$MINIO_ROOT_PASSWORD" \
            -e LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE="true" \
            -e LANGFUSE_INIT_ORG_ID="multi-agent-platform" \
            -e LANGFUSE_INIT_ORG_NAME="Multi-Agent Platform" \
            -e LANGFUSE_INIT_PROJECT_ID="default" \
            -e LANGFUSE_INIT_PROJECT_NAME="Default Project" \
            -e LANGFUSE_INIT_PROJECT_PUBLIC_KEY="pk-dev-public-key" \
            -e LANGFUSE_INIT_PROJECT_SECRET_KEY="sk-dev-secret-key" \
            -e LANGFUSE_INIT_USER_EMAIL="dev@localhost.local" \
            -e LANGFUSE_INIT_USER_NAME="Developer" \
            -e LANGFUSE_INIT_USER_PASSWORD="devpassword123" \
            -p ${LANGFUSE_WEB_PORT}:3000 \
            docker.io/langfuse/langfuse:${LANGFUSE_VERSION}
    fi
}

start_langfuse_worker() {
    if container_running "$WORKER_CONTAINER"; then
        log_info "Langfuse worker already running"
        return 0
    fi

    if container_exists "$WORKER_CONTAINER"; then
        log_info "Starting existing Langfuse worker container..."
        $CONTAINER_TOOL start $WORKER_CONTAINER
    else
        log_info "Creating Langfuse worker container..."
        $CONTAINER_TOOL run -d \
            --name $WORKER_CONTAINER \
            --network $NETWORK_NAME \
            --add-host=host.docker.internal:host-gateway \
            --add-host=host.containers.internal:host-gateway \
            -e DATABASE_URL="$DATABASE_URL" \
            -e ENCRYPTION_KEY="$ENCRYPTION_KEY" \
            -e CLICKHOUSE_URL="http://${CLICKHOUSE_CONTAINER}:8123" \
            -e CLICKHOUSE_MIGRATION_URL="clickhouse://${CLICKHOUSE_CONTAINER}:9000" \
            -e CLICKHOUSE_USER="$CLICKHOUSE_USER" \
            -e CLICKHOUSE_PASSWORD="$CLICKHOUSE_PASSWORD" \
            -e CLICKHOUSE_CLUSTER_ENABLED="false" \
            -e REDIS_HOST="$REDIS_CONTAINER" \
            -e REDIS_PORT="6379" \
            -e REDIS_AUTH="$REDIS_PASSWORD" \
            -e REDIS_CONNECTION_STRING="redis://:${REDIS_PASSWORD}@${REDIS_CONTAINER}:6379" \
            -e SALT="$SALT" \
            -e LANGFUSE_S3_EVENT_UPLOAD_ENABLED="true" \
            -e LANGFUSE_S3_EVENT_UPLOAD_BUCKET="langfuse" \
            -e LANGFUSE_S3_EVENT_UPLOAD_REGION="auto" \
            -e LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT="http://${MINIO_CONTAINER}:9000" \
            -e LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID="$MINIO_ROOT_USER" \
            -e LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY="$MINIO_ROOT_PASSWORD" \
            -e LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE="true" \
            -p 127.0.0.1:${LANGFUSE_WORKER_PORT}:3030 \
            docker.io/langfuse/langfuse-worker:${LANGFUSE_VERSION}
    fi
}

stop_container() {
    local name="$1"
    if container_running "$name"; then
        $CONTAINER_TOOL stop $name 2>/dev/null || true
    fi
}

remove_container() {
    local name="$1"
    if container_exists "$name"; then
        $CONTAINER_TOOL rm -f $name 2>/dev/null || true
    fi
}

case "$1" in
    start)
        log_info "Starting Langfuse development stack..."
        log_info "Using container tool: $CONTAINER_TOOL"

        # Check if PostgreSQL is running
        if ! $CONTAINER_TOOL ps --format '{{.Names}}' | grep -q "^app-postgres-dev$"; then
            log_error "PostgreSQL is not running. Start it first with: make db-start"
            exit 1
        fi

        ensure_network
        start_clickhouse
        start_redis
        start_minio

        log_info "Waiting for infrastructure services..."
        sleep 5

        start_langfuse_web
        start_langfuse_worker

        log_info "Waiting for Langfuse to be ready..."
        sleep 10

        # Wait for web UI to respond
        for i in {1..60}; do
            if curl -s "http://localhost:$LANGFUSE_WEB_PORT" > /dev/null 2>&1; then
                log_info "Langfuse is ready!"
                echo ""
                log_info "Web UI: http://localhost:$LANGFUSE_WEB_PORT"
                log_info "Login: dev@localhost.local / devpassword123"
                log_info "Public Key: pk-dev-public-key"
                log_info "Secret Key: sk-dev-secret-key"
                exit 0
            fi
            echo -n "."
            sleep 2
        done

        log_error "Langfuse failed to start within 120 seconds"
        log_info "Check logs with: $0 logs"
        exit 1
        ;;

    stop)
        log_info "Stopping Langfuse stack..."
        stop_container $WORKER_CONTAINER
        stop_container $WEB_CONTAINER
        stop_container $MINIO_CONTAINER
        stop_container $REDIS_CONTAINER
        stop_container $CLICKHOUSE_CONTAINER
        log_info "Langfuse stack stopped"
        ;;

    remove)
        log_warn "Removing Langfuse containers (data will be preserved in .local/langfuse)..."
        remove_container $WORKER_CONTAINER
        remove_container $WEB_CONTAINER
        remove_container $MINIO_CONTAINER
        remove_container $REDIS_CONTAINER
        remove_container $CLICKHOUSE_CONTAINER
        log_info "Containers removed"
        ;;

    reset)
        if [[ "$2" == "-y" || "$2" == "--yes" ]]; then
            log_info "Removing containers and data..."
            remove_container $WORKER_CONTAINER
            remove_container $WEB_CONTAINER
            remove_container $MINIO_CONTAINER
            remove_container $REDIS_CONTAINER
            remove_container $CLICKHOUSE_CONTAINER
            rm -rf "$DATA_DIR" 2>/dev/null || true
            $CONTAINER_TOOL network rm $NETWORK_NAME 2>/dev/null || true
            log_info "Langfuse completely reset"
        else
            log_warn "This will delete all Langfuse data. Are you sure? (y/N)"
            read -r response
            if [[ "$response" == "y" || "$response" == "Y" ]]; then
                log_info "Removing containers and data..."
                remove_container $WORKER_CONTAINER
                remove_container $WEB_CONTAINER
                remove_container $MINIO_CONTAINER
                remove_container $REDIS_CONTAINER
                remove_container $CLICKHOUSE_CONTAINER
                rm -rf "$DATA_DIR" 2>/dev/null || true
                $CONTAINER_TOOL network rm $NETWORK_NAME 2>/dev/null || true
                log_info "Langfuse completely reset"
            else
                log_info "Reset cancelled"
            fi
        fi
        ;;

    logs)
        CONTAINER="${2:-web}"
        case "$CONTAINER" in
            web) TARGET=$WEB_CONTAINER ;;
            worker) TARGET=$WORKER_CONTAINER ;;
            clickhouse) TARGET=$CLICKHOUSE_CONTAINER ;;
            redis) TARGET=$REDIS_CONTAINER ;;
            minio) TARGET=$MINIO_CONTAINER ;;
            *)
                log_error "Unknown container: $CONTAINER"
                echo "Available: web, worker, clickhouse, redis, minio"
                exit 1
                ;;
        esac

        if [ "$3" = "-f" ] || [ "$3" = "--follow" ]; then
            log_info "Streaming $CONTAINER logs (Ctrl+C to exit)..."
            $CONTAINER_TOOL logs -f $TARGET
        else
            log_info "Showing last 100 lines of $CONTAINER logs..."
            $CONTAINER_TOOL logs --tail 100 $TARGET
        fi
        ;;

    status)
        echo ""
        log_info "Langfuse Stack Status:"
        echo "----------------------------------------"

        RUNNING=0
        TOTAL=5

        for container in $CLICKHOUSE_CONTAINER $REDIS_CONTAINER $MINIO_CONTAINER $WEB_CONTAINER $WORKER_CONTAINER; do
            if container_running "$container"; then
                echo -e "${GREEN}[RUNNING]${NC} $container"
                ((RUNNING++))
            elif container_exists "$container"; then
                echo -e "${YELLOW}[STOPPED]${NC} $container"
            else
                echo -e "${RED}[MISSING]${NC} $container"
            fi
        done

        echo "----------------------------------------"
        echo "$RUNNING / $TOTAL containers running"

        if [ $RUNNING -eq $TOTAL ]; then
            echo ""
            log_info "Web UI: http://localhost:$LANGFUSE_WEB_PORT"
            log_info "Login: dev@localhost.local / devpassword123"
            exit 0
        else
            exit 1
        fi
        ;;

    *)
        echo "Usage: $0 {start|stop|remove|reset|logs|status}"
        echo ""
        echo "Commands:"
        echo "  start  - Start the Langfuse stack (5 containers)"
        echo "  stop   - Stop all Langfuse containers"
        echo "  remove - Remove containers (keeps data volumes)"
        echo "  reset  - Remove containers and all data"
        echo "  logs   - Show logs (usage: logs [web|worker|clickhouse|redis|minio] [-f])"
        echo "  status - Check if Langfuse stack is running"
        echo ""
        echo "Environment variables:"
        echo "  LANGFUSE_VERSION     - Langfuse version (default: 3)"
        echo "  LANGFUSE_WEB_PORT    - Web UI port (default: 3000)"
        echo "  POSTGRES_USER        - Database user (default: app)"
        echo "  POSTGRES_PASSWORD    - Database password (default: changethis)"
        echo "  LANGFUSE_DB          - Database name (default: langfuse)"
        echo ""
        echo "Default credentials:"
        echo "  Web UI: dev@localhost.local / devpassword123"
        echo "  API Keys: pk-dev-public-key / sk-dev-secret-key"
        echo ""
        echo "Prerequisites:"
        echo "  PostgreSQL must be running: make db-start"
        exit 1
        ;;
esac
