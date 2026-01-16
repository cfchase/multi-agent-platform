# Development Guide

This guide covers development setup, daily workflows, and best practices for working with this full-stack template.

## Prerequisites

- **Node.js 22+** and npm
- **Python 3.11+**
- **UV** (Python package manager): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Docker** or **Podman** (for PostgreSQL container)
- **Make** (for automation)

## Initial Setup

```bash
# 1. Clone the repository
git clone https://github.com/cfchase/deep-research
cd deep-research

# 2. Install all dependencies
make setup

# 3. Configure environment
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# Edit backend/.env: set ENVIRONMENT=local to bypass OAuth

# 4. Start PostgreSQL database
make db-start

# 5. Initialize database schema and seed data
make db-init && make db-seed

# 6. Start development servers
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
backend/.env          # Backend configuration
frontend/.env         # Frontend configuration
```

Copy from examples:
```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

### Authentication Modes

**Local Mode (recommended for development):**
```bash
# In backend/.env
ENVIRONMENT=local
```
- No OAuth required
- Uses a default "dev-user" for all requests
- Simplest setup for local development

**OAuth Mode (production-like):**
```bash
# In backend/.env
ENVIRONMENT=development
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
OAUTH_COOKIE_SECRET=generate-a-random-key
```
- Requires Google OAuth credentials
- Run `make dev` to start with OAuth proxy on port 4180
- See [AUTHENTICATION.md](AUTHENTICATION.md) for setup

### Key Variables

**Backend (`backend/.env`):**
```bash
ENVIRONMENT=local              # local (no auth) or development (OAuth)
POSTGRES_SERVER=localhost
POSTGRES_USER=app
POSTGRES_PASSWORD=changethis
POSTGRES_DB=deep-research
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

## AI/ML Infrastructure Services

The project includes three AI/ML services for local development:

| Service | Purpose | Port | UI |
|---------|---------|------|-----|
| **LangFlow** | Visual workflow builder for LLM apps | 7860 | http://localhost:7860 |
| **Langfuse** | LLM observability and tracing | 3000 | http://localhost:3000 |
| **MLFlow** | Experiment tracking and model registry | 5000 | http://localhost:5000 |

### Starting AI/ML Services

```bash
# Start all AI/ML services (requires db-start first)
make services-start

# Or start individually:
make langflow-start    # LangFlow on port 7860
make langfuse-start    # Langfuse on port 3000
make mlflow-start      # MLFlow on port 5000

# Check status
make langflow-status
make langfuse-status
make mlflow-status

# View logs
make langflow-logs
make langfuse-logs
make mlflow-logs

# Stop services
make services-stop     # Stop all
make langflow-stop
make langfuse-stop
make mlflow-stop
```

### Service Details

**LangFlow** - Visual workflow builder
- Connects to PostgreSQL for persistence
- Default credentials: Set via environment
- Useful for prototyping LLM pipelines

**Langfuse** - LLM observability
- Full stack: Redis, ClickHouse, MinIO, PostgreSQL
- Access at http://localhost:3000
- Create account on first visit

**MLFlow** - Experiment tracking
- PostgreSQL backend for metadata
- Local volume for artifact storage
- No authentication (development mode)

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

- [TESTING.md](TESTING.md) - Testing strategies
- [DATABASE.md](DATABASE.md) - Database details
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide
