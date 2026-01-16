# Build and Push Targets

.PHONY: build-frontend build build-prod push push-prod

build-frontend: ## Build frontend for production
	cd frontend && npm run build

build: build-frontend ## Build frontend and container images
	@echo "Building container images for $(REGISTRY) with tag $(TAG) using $(CONTAINER_TOOL)..."
	./scripts/build-images.sh $(TAG) $(REGISTRY) $(CONTAINER_TOOL)

build-prod: build-frontend ## Build frontend and container images for production
	@echo "Building container images for $(REGISTRY) with tag prod using $(CONTAINER_TOOL)..."
	./scripts/build-images.sh prod $(REGISTRY) $(CONTAINER_TOOL)

push: ## Push container images to registry
	@echo "Pushing images to $(REGISTRY) with tag $(TAG) using $(CONTAINER_TOOL)..."
	./scripts/push-images.sh $(TAG) $(REGISTRY) $(CONTAINER_TOOL)

push-prod: ## Push container images to registry with prod tag
	@echo "Pushing images to $(REGISTRY) with tag prod using $(CONTAINER_TOOL)..."
	./scripts/push-images.sh prod $(REGISTRY) $(CONTAINER_TOOL)
