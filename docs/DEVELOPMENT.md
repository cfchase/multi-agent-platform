# Development Guide

This guide covers development setup, daily workflows, and best practices for working with this full-stack template.

## Prerequisites

- **Node.js 18+** and npm
- **Python 3.11+**
- **UV** (Python package manager): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Docker** or **Podman** (for PostgreSQL container)
- **Make** (for automation)

## Initial Setup

```bash
# 1. Clone the repository
git clone <repository-url>
cd patternfly-full-stack-fastapi-template

# 2. Install all dependencies
make setup

# 3. Start PostgreSQL database
make db-start

# 4. Initialize database schema and seed data
make db-init && make db-seed

# 5. Start development servers
make dev
```

This starts:
- **Frontend**: http://localhost:8080 (Vite dev server)
- **Backend**: http://localhost:8000 (FastAPI with Uvicorn)
- **API Docs**: http://localhost:8000/docs (Swagger UI)

## Daily Development Workflow

### Starting Development

```bash
# 1. Start database (if not running)
make db-status  # Check status
make db-start   # Start if needed

# 2. Start both servers
make dev

# Or start individually:
make dev-frontend  # Port 8080
make dev-backend   # Port 8000
```

### Making Changes

**Frontend changes:**
- Edit files in `frontend/src/app/`
- Vite HMR applies changes instantly
- Check browser console for errors

**Backend changes:**
- Edit files in `backend/app/`
- Uvicorn auto-reloads on save
- Check terminal for errors

**Database changes:**
1. Update models in `backend/app/models.py`
2. Create migration: `cd backend && uv run alembic revision --autogenerate -m "description"`
3. Review migration file in `backend/alembic/versions/`
4. Apply: `cd backend && uv run alembic upgrade head`

### Testing

```bash
# Run all tests
make test

# Run specific test suites
make test-frontend     # Vitest
make test-backend      # pytest
make test-e2e          # Playwright

# With options
make test-backend-verbose    # Verbose output
make test-backend-coverage   # Coverage report
```

### Before Committing

```bash
# 1. Run all tests
make test

# 2. Check linting
make lint

# 3. TypeScript check (frontend)
cd frontend && npm run typecheck

# 4. Review changes
git diff
git status
```

## Environment Configuration

### Environment Files

```
.env                  # Root config (for docker-compose, etc.)
backend/.env          # Backend-specific
frontend/.env         # Frontend-specific
```

Copy from examples:
```bash
make env-setup  # Creates .env files from .env.example
```

### Key Variables

**Backend (`backend/.env`):**
```bash
POSTGRES_SERVER=localhost
POSTGRES_USER=app
POSTGRES_PASSWORD=changethis
POSTGRES_DB=app
POSTGRES_PORT=5432
```

**Frontend (`frontend/.env`):**
```bash
VITE_API_URL=/api  # Proxy handled by Vite
```

## Database Management

### Common Commands

```bash
make db-start      # Start PostgreSQL container
make db-stop       # Stop container (preserves data)
make db-status     # Check if running
make db-shell      # Open psql shell
make db-logs       # View container logs
make db-reset      # DESTRUCTIVE: Delete all data
```

### Migrations

```bash
# Create new migration
cd backend
uv run alembic revision --autogenerate -m "Add user table"

# Apply migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1

# View history
uv run alembic history
```

**CRITICAL**: Always review auto-generated migrations before applying!

### Seeding Data

```bash
make db-seed  # Populate with test data
```

## Project Structure

```
├── backend/
│   ├── main.py           # FastAPI entry point
│   ├── app/
│   │   ├── api/          # API routes
│   │   ├── models.py     # SQLModel models
│   │   └── core/         # Config, database
│   ├── alembic/          # Migrations
│   └── tests/            # Backend tests
├── frontend/
│   ├── src/
│   │   ├── app/          # Pages and components
│   │   ├── api/          # API client
│   │   └── services/     # Service layer
│   └── tests/            # Frontend tests
├── k8s/                  # Kubernetes manifests
└── docs/                 # Documentation
```

## Adding New Features

### New API Endpoint

1. Create route file: `backend/app/api/routes/v1/<feature>/<feature>.py`
2. Add router to `backend/app/api/routes/v1/router.py`
3. Write tests in `backend/tests/api/`
4. Run: `make test-backend`

### New Frontend Page

1. Create directory: `frontend/src/app/<PageName>/`
2. Create component: `<PageName>.tsx`
3. Add route to `frontend/src/app/routes.tsx`
4. Write tests: `<PageName>.test.tsx`
5. Run: `make test-frontend`

### New Database Model

1. Add model to `backend/app/models.py`
2. Create migration: `uv run alembic revision --autogenerate -m "Add model"`
3. Review migration file
4. Apply: `uv run alembic upgrade head`
5. Create API routes
6. Update frontend

## Troubleshooting

### Database Issues

```bash
# Database not starting?
make db-logs                    # Check logs
docker ps -a                    # Check container status

# Connection refused?
make db-status                  # Verify running
make db-start                   # Start if needed

# Reset everything
make db-reset                   # WARNING: Deletes all data
make db-start && make db-init && make db-seed
```

### API Not Working

```bash
# Check health endpoint
curl http://localhost:8000/api/v1/utils/health-check

# Check backend logs
# (visible in terminal running `make dev-backend`)

# Verify .env configuration
cat backend/.env
```

### Frontend Issues

```bash
# Clear cache
rm -rf frontend/node_modules/.vite
npm run dev

# Type errors?
npm run typecheck

# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install
```

### Test Failures

```bash
# Run specific test
cd frontend && npm test -- ItemBrowser.test.tsx
cd backend && uv run pytest tests/api/test_items.py -v

# Kill orphaned processes
pkill -f vitest
pkill -f pytest
```

## IDE Setup

### VS Code Extensions

- **Python**: Python language support
- **Pylance**: Python type checking
- **ESLint**: JavaScript/TypeScript linting
- **Prettier**: Code formatting
- **Vite**: Vite integration

### Recommended Settings

`.vscode/settings.json`:
```json
{
  "python.defaultInterpreterPath": "./backend/.venv/bin/python",
  "python.analysis.typeCheckingMode": "basic",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true
  }
}
```

## See Also

- [INCREMENTAL-WORKFLOW.md](INCREMENTAL-WORKFLOW.md) - Complex feature development
- [AUTONOMOUS-WORKFLOW.md](AUTONOMOUS-WORKFLOW.md) - Agent-based development
- [TESTING.md](TESTING.md) - Testing strategies
- [DATABASE.md](DATABASE.md) - Database details
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide
