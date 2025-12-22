# React FastAPI Template Makefile

# Container Registry Operations
REGISTRY ?= quay.io/cfchase
TAG ?= latest

# Auto-detect container tool (check which daemon is actually running, podman preferred)
CONTAINER_TOOL ?= $(shell if podman info >/dev/null 2>&1; then echo podman; elif docker info >/dev/null 2>&1; then echo docker; else echo docker; fi)


.PHONY: help setup dev dev-2 build build-prod test test-frontend test-backend test-e2e test-e2e-ui test-e2e-headed update-tests lint clean push push-prod deploy deploy-prod undeploy undeploy-prod kustomize kustomize-prod db-start db-stop db-reset db-shell db-logs db-status db-init db-seed

# Default target
help: ## Show this help message
	@echo "React FastAPI Template - Available commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Setup and Installation
setup: ## Install all dependencies
	@echo "Installing frontend dependencies..."
	cd frontend && npm install
	@echo "Installing backend dependencies (including dev dependencies)..."
	cd backend && uv sync --extra dev
	@echo "Setup complete!"

setup-frontend: ## Install frontend dependencies only
	cd frontend && npm install

setup-backend: ## Install backend dependencies only
	cd backend && uv sync --extra dev

# Development
dev: ## Run both frontend and backend in development mode
	@echo "Starting development servers..."
	npx concurrently "make dev-backend" "make dev-frontend"

dev-frontend: ## Run frontend development server
	cd frontend && npm run dev

dev-backend: ## Run backend development server
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-2: ## Run second instance for parallel development (frontend:8081, backend:8001)
	@echo "Starting second development instance..."
	npx concurrently "make dev-backend-2" "make dev-frontend-2"

dev-frontend-2: ## Run second frontend instance (port 8081)
	cd frontend && VITE_PORT=8081 VITE_BACKEND_PORT=8001 npm run dev -- --port 8081

dev-backend-2: ## Run second backend instance (port 8001)
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Database Management
db-start: ## Start PostgreSQL development database
	@chmod +x scripts/dev-db.sh
	@./scripts/dev-db.sh start

db-stop: ## Stop PostgreSQL development database
	@./scripts/dev-db.sh stop

db-reset: ## Reset PostgreSQL database (removes all data)
	@./scripts/dev-db.sh reset

db-shell: ## Open PostgreSQL shell
	@./scripts/dev-db.sh shell

db-logs: ## Show PostgreSQL logs
	@./scripts/dev-db.sh logs

db-status: ## Check PostgreSQL database status
	@./scripts/dev-db.sh status

db-init: ## Initialize database schema with Alembic migrations
	@echo "Running database migrations..."
	@cd backend && POSTGRES_SERVER=localhost POSTGRES_USER=app POSTGRES_PASSWORD=changethis POSTGRES_DB=app uv run alembic upgrade head
	@echo "Database initialized!"

db-migrate-create: ## Create a new Alembic migration (usage: make db-migrate-create MSG="description")
	@if [ -z "$(MSG)" ]; then echo "Error: MSG is required. Usage: make db-migrate-create MSG=\"description\""; exit 1; fi
	@cd backend && POSTGRES_SERVER=localhost POSTGRES_USER=app POSTGRES_PASSWORD=changethis POSTGRES_DB=app uv run alembic revision --autogenerate -m "$(MSG)"
	@echo "Migration created! Review the file in backend/alembic/versions/"

db-migrate-upgrade: ## Apply all pending migrations
	@echo "Applying migrations..."
	@cd backend && POSTGRES_SERVER=localhost POSTGRES_USER=app POSTGRES_PASSWORD=changethis POSTGRES_DB=app uv run alembic upgrade head

db-migrate-downgrade: ## Rollback one migration
	@echo "Rolling back one migration..."
	@cd backend && POSTGRES_SERVER=localhost POSTGRES_USER=app POSTGRES_PASSWORD=changethis POSTGRES_DB=app uv run alembic downgrade -1

db-migrate-history: ## Show migration history
	@cd backend && POSTGRES_SERVER=localhost POSTGRES_USER=app POSTGRES_PASSWORD=changethis POSTGRES_DB=app uv run alembic history

db-migrate-current: ## Show current migration revision
	@cd backend && POSTGRES_SERVER=localhost POSTGRES_USER=app POSTGRES_PASSWORD=changethis POSTGRES_DB=app uv run alembic current

db-seed: ## Seed database with test data (users and items)
	@echo "Seeding database with test data..."
	@cd backend && POSTGRES_SERVER=localhost POSTGRES_USER=app POSTGRES_PASSWORD=changethis POSTGRES_DB=app uv run python scripts/seed_test_data.py
	@echo "Test data created!"

# Building
build-frontend: ## Build frontend for production
	cd frontend && npm run build

build: build-frontend ## Build frontend and container images
	@echo "Building container images for $(REGISTRY) with tag $(TAG) using $(CONTAINER_TOOL)..."
	./scripts/build-images.sh $(TAG) $(REGISTRY) $(CONTAINER_TOOL)

build-prod: build-frontend ## Build frontend and container images for production
	@echo "Building container images for $(REGISTRY) with tag prod using $(CONTAINER_TOOL)..."
	./scripts/build-images.sh prod $(REGISTRY) $(CONTAINER_TOOL)

# Testing
test: test-frontend test-backend ## Run all tests (frontend and backend)

test-frontend: lint ## Run frontend linting, type checking, and tests
	@echo "Running TypeScript type checking..."
	cd frontend && npx tsc --noEmit
	@echo "Running frontend tests..."
	cd frontend && npm run test

test-backend: ## Run backend tests (use VERBOSE=1, COVERAGE=1, FILE=path as needed)
	@echo "Syncing backend dependencies..."
	@cd backend && uv sync --extra dev
	@echo "Running backend tests..."
	@PYTEST_ARGS=""; \
	if [ "$(VERBOSE)" = "1" ]; then PYTEST_ARGS="$$PYTEST_ARGS -v"; fi; \
	if [ "$(COVERAGE)" = "1" ]; then PYTEST_ARGS="$$PYTEST_ARGS --cov=app --cov-report=term-missing"; fi; \
	if [ -n "$(FILE)" ]; then PYTEST_ARGS="$$PYTEST_ARGS $(FILE)"; fi; \
	cd backend && uv run pytest $$PYTEST_ARGS

test-e2e: ## Run end-to-end tests with Playwright
	@echo "Running E2E tests..."
	cd frontend && npm run test:e2e

test-e2e-ui: ## Run E2E tests with Playwright UI
	cd frontend && npm run test:e2e:ui

test-e2e-headed: ## Run E2E tests in headed mode (visible browser)
	cd frontend && npm run test:e2e:headed

update-tests: ## Update frontend test snapshots
	@echo "Updating frontend test snapshots..."
	cd frontend && npm run test -- -u
	@echo "Test snapshots updated! Remember to commit the updated snapshots."

lint: ## Run linting on frontend
	cd frontend && npm run lint

push: ## Push container images to registry
	@echo "Pushing images to $(REGISTRY) with tag $(TAG) using $(CONTAINER_TOOL)..."
	./scripts/push-images.sh $(TAG) $(REGISTRY) $(CONTAINER_TOOL)

push-prod: ## Push container images to registry with prod tag
	@echo "Pushing images to $(REGISTRY) with tag prod using $(CONTAINER_TOOL)..."
	./scripts/push-images.sh prod $(REGISTRY) $(CONTAINER_TOOL)

# OpenShift/Kubernetes Deployment
kustomize: ## Preview development deployment manifests
	kustomize build k8s/overlays/dev

kustomize-prod: ## Preview production deployment manifests
	kustomize build k8s/overlays/prod

deploy: ## Deploy to development environment
	@echo "Deploying to development..."
	./scripts/deploy.sh dev

deploy-prod: ## Deploy to production environment
	@echo "Deploying to production..."
	./scripts/deploy.sh prod

undeploy: ## Remove development deployment
	@echo "Removing development deployment..."
	./scripts/undeploy.sh dev

undeploy-prod: ## Remove production deployment
	@echo "Removing production deployment..."
	./scripts/undeploy.sh prod

# Environment Setup
env-setup: ## Copy environment example files
	@echo "Setting up environment files..."
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env (root)"; fi
	@if [ ! -f backend/.env ]; then cp backend/.env.example backend/.env; echo "Created backend/.env"; fi
	@if [ ! -f frontend/.env ]; then cp frontend/.env.example frontend/.env; echo "Created frontend/.env"; fi

# Version Management
sync-version: ## Sync VERSION to pyproject.toml and package.json
	@./scripts/sync-version.sh

bump-version: ## Bump version (usage: make bump-version TYPE=patch|minor|major)
	@if [ -z "$(TYPE)" ]; then echo "Error: TYPE is required. Usage: make bump-version TYPE=patch|minor|major"; exit 1; fi
	@./scripts/bump-version.sh $(TYPE)

show-version: ## Show current version
	@cat VERSION

# Health Checks
health-backend: ## Check backend health
	@echo "Checking backend health..."
	@curl -f http://localhost:8000/api/v1/utils/health-check || echo "Backend not responding"

health-frontend: ## Check if frontend is running
	@echo "Checking frontend..."
	@curl -f http://localhost:8080 || echo "Frontend not responding"

# Cleanup
clean: ## Clean build artifacts and dependencies
	@echo "Cleaning build artifacts..."
	rm -rf frontend/dist
	rm -rf frontend/node_modules
	rm -rf backend/__pycache__
	rm -rf backend/.pytest_cache

clean-all: clean ## Clean everything

# Development Workflow
fresh-start: clean setup env-setup ## Clean setup for new development
	@echo "Fresh development environment ready!"

quick-start: setup env-setup dev ## Quick start for development

