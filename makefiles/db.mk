# Database Management Targets

.PHONY: db-start db-stop db-reset db-shell db-logs db-status db-init db-seed db-migrate-create db-migrate-upgrade db-migrate-downgrade db-migrate-history db-migrate-current

db-start: ## Start PostgreSQL development database
	@chmod +x scripts/dev-db.sh
	@./scripts/dev-db.sh start

db-stop: ## Stop PostgreSQL development database
	@./scripts/dev-db.sh stop

db-reset: ## Reset PostgreSQL database (removes all data, use FORCE=1 to skip prompt)
	@./scripts/dev-db.sh reset $(if $(filter 1 y yes true,$(FORCE)),-y,)

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
