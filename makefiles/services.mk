# Service Management Targets (LangFlow, Langfuse, MLFlow, OAuth)

.PHONY: langflow-start langflow-stop langflow-restart langflow-status langflow-logs langflow-import langflow-reset
.PHONY: langfuse-start langfuse-stop langfuse-status langfuse-logs langfuse-reset
.PHONY: mlflow-start mlflow-stop mlflow-status mlflow-logs mlflow-reset
.PHONY: oauth-start oauth-stop oauth-status oauth-logs
.PHONY: services-start services-stop services-status services-reset

# LangFlow
langflow-start: ## Start LangFlow development server
	@chmod +x scripts/dev-langflow.sh
	@./scripts/dev-langflow.sh start

langflow-stop: ## Stop LangFlow development server
	@./scripts/dev-langflow.sh stop

langflow-status: ## Check LangFlow status
	@./scripts/dev-langflow.sh status

langflow-logs: ## Show LangFlow logs
	@./scripts/dev-langflow.sh logs

langflow-import: ## Import flows from configured sources into LangFlow
	@uv run --with requests --with pyyaml python scripts/import_flows.py

langflow-reset: ## Reset LangFlow (removes all data, use FORCE=1 to skip prompt)
	@./scripts/dev-langflow.sh reset $(if $(filter 1 y yes true,$(FORCE)),-y,)

langflow-restart: ## Restart LangFlow (required after installing components)
	@./scripts/dev-langflow.sh restart

# Langfuse
langfuse-start: ## Start Langfuse development stack
	@chmod +x scripts/dev-langfuse.sh
	@./scripts/dev-langfuse.sh start

langfuse-stop: ## Stop Langfuse development stack
	@./scripts/dev-langfuse.sh stop

langfuse-status: ## Check Langfuse status
	@./scripts/dev-langfuse.sh status

langfuse-logs: ## Show Langfuse logs (use CONTAINER=web|worker|clickhouse|redis|minio)
	@./scripts/dev-langfuse.sh logs $(CONTAINER)

langfuse-reset: ## Reset Langfuse (removes all data, use FORCE=1 to skip prompt)
	@./scripts/dev-langfuse.sh reset $(if $(filter 1 y yes true,$(FORCE)),-y,)

# MLFlow
mlflow-start: ## Start MLFlow development server
	@chmod +x scripts/dev-mlflow.sh
	@./scripts/dev-mlflow.sh start

mlflow-stop: ## Stop MLFlow development server
	@./scripts/dev-mlflow.sh stop

mlflow-status: ## Check MLFlow status
	@./scripts/dev-mlflow.sh status

mlflow-logs: ## Show MLFlow logs
	@./scripts/dev-mlflow.sh logs

mlflow-reset: ## Reset MLFlow (removes all data, use FORCE=1 to skip prompt)
	@./scripts/dev-mlflow.sh reset $(if $(filter 1 y yes true,$(FORCE)),-y,)

# OAuth (optional - requires OAUTH_CLIENT_ID/SECRET in .env)
oauth-start: ## Start OAuth2 Proxy (requires OAuth credentials in backend/.env)
	@chmod +x scripts/dev-oauth.sh
	@./scripts/dev-oauth.sh start

oauth-stop: ## Stop local OAuth2 Proxy
	@./scripts/dev-oauth.sh stop

oauth-status: ## Check OAuth2 Proxy status
	@./scripts/dev-oauth.sh status

oauth-logs: ## Show OAuth2 Proxy logs
	@./scripts/dev-oauth.sh logs

# All Services
services-start: db-start db-init ## Start all services (db, langflow, langfuse, mlflow, oauth if configured)
	@echo "Starting all services..."
	@./scripts/dev-langflow.sh start
	@./scripts/dev-langfuse.sh start
	@./scripts/dev-mlflow.sh start
	@./scripts/dev-oauth.sh start
	@echo ""
	@echo "=============================================="
	@echo "All services started!"
	@echo "=============================================="
	@echo ""
	@echo "Service URLs:"
	@echo "  App:      http://localhost:8080 (after 'make dev')"
	@echo "  LangFlow: http://localhost:7860"
	@echo "  Langfuse: http://localhost:3000"
	@echo "  MLFlow:   http://localhost:5000"
	@echo ""
	@echo "Credentials:"
	@echo "  Langfuse: dev@localhost.local / devpassword123"
	@echo ""
	@echo "Run 'make dev' to start the frontend and backend."

services-stop: ## Stop all services
	@echo "Stopping all services..."
	@./scripts/dev-oauth.sh stop || true
	@./scripts/dev-mlflow.sh stop || true
	@./scripts/dev-langfuse.sh stop || true
	@./scripts/dev-langflow.sh stop || true
	@./scripts/dev-db.sh stop || true
	@echo "All services stopped!"

services-status: ## Check status of all services
	@echo "=== Database ===" && ./scripts/dev-db.sh status || true
	@echo ""
	@echo "=== LangFlow ===" && ./scripts/dev-langflow.sh status || true
	@echo ""
	@echo "=== Langfuse ===" && ./scripts/dev-langfuse.sh status || true
	@echo ""
	@echo "=== MLFlow ===" && ./scripts/dev-mlflow.sh status || true
	@echo ""
	@echo "=== OAuth Proxy ===" && ./scripts/dev-oauth.sh status || true

services-reset: ## Reset all services (removes all data, use FORCE=1 to skip prompts)
	@echo "Resetting all services..."
	@./scripts/dev-mlflow.sh reset $(if $(filter 1 y yes true,$(FORCE)),-y,)
	@./scripts/dev-langfuse.sh reset $(if $(filter 1 y yes true,$(FORCE)),-y,)
	@./scripts/dev-langflow.sh reset $(if $(filter 1 y yes true,$(FORCE)),-y,)
	@./scripts/dev-db.sh reset $(if $(filter 1 y yes true,$(FORCE)),-y,)
	@echo "All services reset!"
