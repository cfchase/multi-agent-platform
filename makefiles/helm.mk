# Helm Deployment Targets

.PHONY: helm-repos helm-langfuse-install helm-langfuse-upgrade helm-langfuse-uninstall helm-langfuse-status
.PHONY: helm-langflow-status helm-langflow-logs helm-mlflow-status helm-mlflow-logs

HELM_NAMESPACE ?= deep-research-dev
LANGFUSE_RELEASE ?= langfuse
LANGFLOW_RELEASE ?= langflow
MLFLOW_RELEASE ?= mlflow

# Add Helm repositories
helm-repos: ## Add required Helm repositories
	@echo "Adding Helm repositories..."
	helm repo add langfuse https://langfuse.github.io/langfuse-k8s 2>/dev/null || true
	helm repo add langflow https://langflow-ai.github.io/langflow-helm-charts 2>/dev/null || true
	helm repo add community-charts https://community-charts.github.io/helm-charts 2>/dev/null || true
	helm repo update

# Generate secrets file using the generate script
helm/langfuse/secrets-dev.yaml:
	@./scripts/generate-langfuse-secrets.sh

# Install Langfuse via Helm
helm-langfuse-install: helm-repos helm/langfuse/secrets-dev.yaml ## Install Langfuse using Helm
	@echo "Ensuring langfuse database exists..."
	@kubectl exec -n $(HELM_NAMESPACE) deploy/postgres -- psql -U app -d postgres -tc \
		"SELECT 1 FROM pg_database WHERE datname = 'langfuse'" 2>/dev/null | grep -q 1 || \
		kubectl exec -n $(HELM_NAMESPACE) deploy/postgres -- psql -U app -d postgres -c \
		"CREATE DATABASE langfuse;" 2>/dev/null || echo "Database may already exist or postgres not ready"
	@echo "Installing Langfuse to namespace $(HELM_NAMESPACE)..."
	@if [ ! -f helm/langfuse/secrets-dev.yaml ]; then \
		echo "Error: helm/langfuse/secrets-dev.yaml not found. Copy from secrets-dev.yaml.example and edit."; \
		exit 1; \
	fi
	helm install $(LANGFUSE_RELEASE) langfuse/langfuse \
		--namespace $(HELM_NAMESPACE) \
		--create-namespace \
		-f helm/langfuse/values-dev.yaml \
		-f helm/langfuse/secrets-dev.yaml
	@echo ""
	@echo "Creating Langfuse route..."
	@oc create route edge langfuse --service=$(LANGFUSE_RELEASE)-web --port=3000 -n $(HELM_NAMESPACE) 2>/dev/null || \
		echo "Route already exists or could not be created"
	@echo ""
	@echo "Langfuse installed!"
	@echo "URL: https://langfuse-$(HELM_NAMESPACE).$$(oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}' 2>/dev/null || echo '<cluster-apps-domain>')"

# Upgrade Langfuse
helm-langfuse-upgrade: ## Upgrade Langfuse Helm release
	@echo "Upgrading Langfuse..."
	helm upgrade $(LANGFUSE_RELEASE) langfuse/langfuse \
		--namespace $(HELM_NAMESPACE) \
		-f helm/langfuse/values-dev.yaml \
		-f helm/langfuse/secrets-dev.yaml

# Uninstall Langfuse
helm-langfuse-uninstall: ## Uninstall Langfuse Helm release
	@echo "Uninstalling Langfuse..."
	@oc delete route langfuse -n $(HELM_NAMESPACE) 2>/dev/null || true
	helm uninstall $(LANGFUSE_RELEASE) --namespace $(HELM_NAMESPACE) || true
	@echo "Note: PVCs are not deleted. To fully clean up:"
	@echo "  kubectl delete pvc -l app.kubernetes.io/instance=$(LANGFUSE_RELEASE) -n $(HELM_NAMESPACE)"

# Check Langfuse status
helm-langfuse-status: ## Check Langfuse Helm release status
	@echo "Langfuse Helm release status:"
	@helm status $(LANGFUSE_RELEASE) --namespace $(HELM_NAMESPACE) 2>/dev/null || echo "Langfuse not installed"
	@echo ""
	@echo "Pods:"
	@kubectl get pods -l app.kubernetes.io/instance=$(LANGFUSE_RELEASE) -n $(HELM_NAMESPACE) 2>/dev/null || true
	@echo ""
	@echo "Routes:"
	@kubectl get routes -l app.kubernetes.io/instance=$(LANGFUSE_RELEASE) -n $(HELM_NAMESPACE) 2>/dev/null || true

# Show Langfuse logs
helm-langfuse-logs: ## Show Langfuse web logs
	kubectl logs -l app.kubernetes.io/component=web,app.kubernetes.io/instance=$(LANGFUSE_RELEASE) -n $(HELM_NAMESPACE) --tail=100

# LangFlow status
helm-langflow-status: ## Check LangFlow Helm release status
	@echo "LangFlow Helm release status:"
	@helm status $(LANGFLOW_RELEASE) --namespace $(HELM_NAMESPACE) 2>/dev/null || echo "LangFlow not installed"
	@echo ""
	@echo "Pods:"
	@kubectl get pods -l app.kubernetes.io/instance=$(LANGFLOW_RELEASE) -n $(HELM_NAMESPACE) 2>/dev/null || true

# Show LangFlow logs
helm-langflow-logs: ## Show LangFlow logs
	kubectl logs -l app.kubernetes.io/instance=$(LANGFLOW_RELEASE) -n $(HELM_NAMESPACE) --tail=100

# MLFlow status
helm-mlflow-status: ## Check MLFlow Helm release status
	@echo "MLFlow Helm release status:"
	@helm status $(MLFLOW_RELEASE) --namespace $(HELM_NAMESPACE) 2>/dev/null || echo "MLFlow not installed"
	@echo ""
	@echo "Pods:"
	@kubectl get pods -l app.kubernetes.io/instance=$(MLFLOW_RELEASE) -n $(HELM_NAMESPACE) 2>/dev/null || true

# Show MLFlow logs
helm-mlflow-logs: ## Show MLFlow logs
	kubectl logs -l app.kubernetes.io/instance=$(MLFLOW_RELEASE) -n $(HELM_NAMESPACE) --tail=100
