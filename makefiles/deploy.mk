# Kubernetes/OpenShift Deployment Targets

.PHONY: kustomize-app kustomize-postgres kustomize-langflow kustomize-mlflow
.PHONY: deploy deploy-prod undeploy undeploy-prod
.PHONY: deploy-db deploy-app deploy-langflow deploy-mlflow deploy-langfuse
.PHONY: generate-k8s-secrets generate-k8s-secrets-dev generate-k8s-secrets-prod
.PHONY: generate-langfuse-secrets-dev generate-admin-secret-dev get-admin-credentials

# Generate K8s secrets from backend/.env (if they don't exist)
generate-k8s-secrets-dev:
	@./scripts/generate-k8s-secrets.sh

generate-k8s-secrets-prod:
	@if [ ! -f k8s/app/overlays/prod/oauth-proxy-secret.env ]; then \
		echo "Warning: k8s/app/overlays/prod/oauth-proxy-secret.env not found"; \
		echo "Copy from example and configure."; \
	else \
		echo "k8s/app/overlays/prod/oauth-proxy-secret.env exists"; \
	fi

generate-k8s-secrets: generate-k8s-secrets-dev generate-k8s-secrets-prod ## Generate K8s OAuth secrets from backend/.env

# Generate shared admin secret for LangFlow, Langfuse, MLFlow
generate-admin-secret-dev:
	@if ! kubectl get secret admin-credentials -n multi-agent-platform-dev >/dev/null 2>&1; then \
		echo "Generating shared admin credentials..."; \
		ADMIN_EMAIL="admin@localhost.local"; \
		ADMIN_PASS=$$(python3 -c "import secrets; print(secrets.token_urlsafe(16))"); \
		kubectl create secret generic admin-credentials \
			--from-literal=email="$$ADMIN_EMAIL" \
			--from-literal=password="$$ADMIN_PASS" \
			-n multi-agent-platform-dev; \
		echo ""; \
		echo "========================================"; \
		echo "ADMIN CREDENTIALS (save these!)"; \
		echo "========================================"; \
		echo "Email:    $$ADMIN_EMAIL"; \
		echo "Password: $$ADMIN_PASS"; \
		echo "========================================"; \
		echo ""; \
	else \
		echo "admin-credentials secret already exists"; \
	fi

# Show admin credentials and service URLs
get-admin-credentials: ## Show admin credentials and URLs for LangFlow/Langfuse/MLFlow
	@echo "========================================"
	@echo "ADMIN CREDENTIALS"
	@echo "========================================"
	@echo "Email:    $$(kubectl get secret admin-credentials -n multi-agent-platform-dev -o jsonpath='{.data.email}' | base64 -d)"
	@echo "Password: $$(kubectl get secret admin-credentials -n multi-agent-platform-dev -o jsonpath='{.data.password}' | base64 -d)"
	@echo ""
	@echo "SERVICE URLS"
	@echo "========================================"
	@APPS_DOMAIN=$$(oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}' 2>/dev/null || echo ""); \
	if [ -n "$$APPS_DOMAIN" ]; then \
		echo "Platform:      https://multi-agent-platform-route-multi-agent-platform-dev.$$APPS_DOMAIN"; \
		echo "LangFlow:      https://langflow-multi-agent-platform-dev.$$APPS_DOMAIN"; \
		echo "Langfuse:      https://langfuse-multi-agent-platform-dev.$$APPS_DOMAIN"; \
		echo "MLFlow:        https://mlflow-multi-agent-platform-dev.$$APPS_DOMAIN"; \
	else \
		echo "Run 'kubectl get routes -n multi-agent-platform-dev' to see URLs"; \
	fi
	@echo "========================================"

# Generate Langfuse Helm secrets (if they don't exist)
generate-langfuse-secrets-dev:
	@./scripts/generate-langfuse-secrets.sh

# Individual component deployment targets
deploy-db: ## Deploy PostgreSQL database only
	@./scripts/deploy-db.sh dev

deploy-app: ## Deploy Multi-Agent Platform app only (requires postgres-secret)
	@./scripts/deploy-app.sh dev

deploy-langflow: ## Deploy LangFlow (requires postgres-secret, admin-credentials)
	@./scripts/deploy-langflow.sh dev

deploy-mlflow: ## Deploy MLFlow (requires postgres-secret)
	@./scripts/deploy-mlflow.sh dev

deploy-langfuse: ## Deploy Langfuse via Helm (requires postgres-secret, admin-credentials)
	@./scripts/deploy-langfuse.sh dev

# Preview kustomize manifests
kustomize-app: ## Preview app deployment manifests
	kustomize build k8s/app/overlays/dev

kustomize-postgres: ## Preview postgres deployment manifests
	kustomize build k8s/postgres/overlays/dev

kustomize-langflow: ## Preview langflow deployment manifests
	kustomize build k8s/langflow/overlays/dev

kustomize-mlflow: ## Preview mlflow deployment manifests
	kustomize build k8s/mlflow/overlays/dev

# Full deployment targets
deploy: generate-admin-secret-dev ## Deploy all components to development environment
	@./scripts/deploy.sh dev
	@echo ""
	@$(MAKE) get-admin-credentials

deploy-prod: ## Deploy all components to production environment
	@./scripts/deploy.sh prod

undeploy: ## Remove all development deployments
	@./scripts/undeploy.sh dev

undeploy-prod: ## Remove all production deployments
	@./scripts/undeploy.sh prod
