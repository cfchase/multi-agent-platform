# Multi-Agent Platform Makefile

# Container Registry Operations
REGISTRY ?= quay.io/cfchase
TAG ?= latest

# Auto-detect container tool (docker preferred, then podman)
CONTAINER_TOOL ?= $(shell ./scripts/lib/detect-container-tool.sh)
export CONTAINER_TOOL

# Include modular makefiles
include makefiles/db.mk
include makefiles/services.mk
include makefiles/build.mk
include makefiles/deploy.mk
include makefiles/helm.mk
include makefiles/test.mk

.PHONY: help setup setup-frontend setup-backend dev dev-frontend dev-backend dev-2 dev-frontend-2 dev-backend-2
.PHONY: config-setup config-reset env-setup sync-version bump-version show-version health-backend health-frontend
.PHONY: clean clean-all fresh-start quick-start

# Default target
help: ## Show this help message
	@echo "Multi-Agent Platform - Available commands:"
	@echo ""
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

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
dev: ## Run frontend and backend (run services-start first)
	@if ./scripts/dev-oauth.sh status >/dev/null 2>&1; then \
		echo "OAuth running - access app at: http://localhost:4180"; \
	else \
		echo "WARNING: Services not running. Run 'make services-start' first."; \
	fi
	@echo ""
	npx concurrently --kill-others-on-fail "make dev-backend" "make dev-frontend"

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

# Config Setup (local by default, use config-setup-dev for cluster)
config-setup: ## Setup local config from examples
	@./scripts/generate-config.sh local

config-reset: ## Delete all local config (run config-setup after editing .env)
	@./scripts/generate-config.sh reset local

env-setup: config-setup ## Alias for config-setup

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
fresh-start: clean setup config-setup ## Clean setup for new development
	@echo "Fresh development environment ready!"

quick-start: setup config-setup dev ## Quick start for development
