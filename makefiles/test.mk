# Testing Targets

.PHONY: test test-frontend test-backend test-e2e test-e2e-ui test-e2e-headed update-tests lint

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
