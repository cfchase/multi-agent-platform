# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**IMPORTANT**: This is the root project guide. For domain-specific details:
- **Frontend work**: See [frontend/CLAUDE.md](frontend/CLAUDE.md) for React/PatternFly specifics
- **Backend work**: See [backend/CLAUDE.md](backend/CLAUDE.md) for FastAPI/Python specifics
- **Detailed docs**: See [docs/](docs/) for comprehensive guides

## Repository Overview

This is a PatternFly FastAPI template for building full-stack applications with React frontend (Vite + PatternFly UI) and FastAPI backend, designed for deployment to OpenShift using Docker containers and Kustomize.

## Quick Decision Guide

**New to the project?**
```bash
make setup && make db-start && make db-init && make db-seed && make dev
```

**Making code changes?**
- Run `make dev` (runs frontend + backend with hot reload)
- Frontend changes: Files in `frontend/src/app/` auto-reload
- Backend changes: FastAPI auto-reloads on save

**Changing database models?**
1. Update models in `backend/app/models/` (user.py, item.py, or create new files)
2. Export new models in `backend/app/models/__init__.py`
3. Create migration: `cd backend && uv run alembic revision --autogenerate -m "description"`
4. Review auto-generated migration file (CRITICAL!)
5. Apply: `cd backend && uv run alembic upgrade head`

**Need to test?**
- All tests: `make test`
- Frontend only: `make test-frontend`
- Backend only: `make test-backend`
- E2E tests: `make test-e2e`

**Ready to deploy?**
- Build and push: `make build && make push`
- Deploy to dev: `make deploy`
- Deploy to prod: `make deploy-prod`

**Troubleshooting:**
- API not working? Check `/api/v1/utils/health-check` → Verify `.env` files → Check CORS settings
- Database issues? `make db-status` → `make db-logs` → `make db-shell`

## Project Structure

```
├── backend/              # FastAPI backend
│   ├── app/             # Application code
│   │   ├── main.py     # FastAPI application entry point
│   │   ├── api/        # API routes (versioned: /api/v1/...)
│   │   ├── models/     # SQLModel database models (package)
│   │   └── core/       # Config, logging, middleware
│   ├── pyproject.toml   # Python dependencies (managed by uv)
│   └── Dockerfile       # Backend container
├── frontend/            # React frontend with Vite + PatternFly
│   ├── src/
│   │   └── app/        # App components and pages
│   ├── package.json    # Node.js dependencies
│   ├── vite.config.ts  # Vite configuration with /api proxy
│   └── Dockerfile      # Frontend container (nginx-based)
├── k8s/                # Kubernetes/OpenShift manifests
│   ├── base/          # Base kustomize resources
│   └── overlays/      # Environment-specific overlays (dev/prod)
├── docs/              # Developer documentation
└── scripts/           # Deployment automation scripts
```

## File Organization Conventions

### Backend (FastAPI)

**Directory structure:**
- `backend/app/models/` - SQLModel database models (package with user.py, item.py, etc.)
- `backend/app/api/routes/v1/<feature>/` - API route handlers
- `backend/app/core/` - Config, logging, middleware, database connection
- `backend/app/alembic/versions/` - Auto-generated migration files
- `backend/tests/` - Test files mirroring `app/` structure

**Naming conventions:**
- Model classes: Singular PascalCase (e.g., `User`, `Item`)
- Route paths: Plural lowercase (e.g., `/items/`, `/users/`)
- Python files: Snake case (e.g., `item_service.py`)

### Frontend (React + Vite)

**Directory structure:**
- `frontend/src/app/<PageName>/` - One directory per page/feature (PascalCase)
- `frontend/src/app/<PageName>/<ComponentName>.tsx` - Page-specific components
- `frontend/src/components/` - Reusable components used across multiple pages
- `frontend/src/api/` - Axios API client and TypeScript types
- Tests: Co-located with components (`<ComponentName>.test.tsx`)

**Naming conventions:**
- Components: PascalCase (e.g., `ItemBrowser.tsx`, `UserCard.tsx`)
- Utilities/services: camelCase (e.g., `apiClient.ts`, `itemService.ts`)
- Test files: Match component name with `.test.tsx` suffix

**When to create new files:**
- **New database table** → Model + Migration + API route + Frontend page
- **New API endpoint** → Route file in `backend/app/api/routes/v1/<feature>/`
- **New UI page** → Directory in `frontend/src/app/` + add route in `routes.tsx`
- **Reusable component** → Move to `frontend/src/components/` if used in 2+ pages

## Development Commands

### Local Development
```bash
make setup             # Install all dependencies
make dev              # Run both frontend and backend
make dev-frontend     # Run React dev server (port 8080)
make dev-backend      # Run FastAPI server (port 8000)
make help             # Show all available commands
```

### Database Management (PostgreSQL)
```bash
make db-start         # Start PostgreSQL development container
make db-stop          # Stop PostgreSQL container
make db-status        # Check if PostgreSQL is running
make db-init          # Run Alembic migrations to create database schema
make db-seed          # Populate database with test data
make db-shell         # Open PostgreSQL shell (psql)
make db-logs          # Show PostgreSQL logs
make db-reset         # Remove container and delete all data (destructive)
```

**Database Configuration:**
- Container: `app-postgres-dev`
- Volume: `app-db-data` (persistent storage)
- Default credentials: `app/changethis`
- Default database: `app`
- Port: `5432`
- PostgreSQL version: 15-alpine
- ORM: SQLModel with Alembic migrations

### Testing
```bash
make test                    # Run all tests (frontend and backend)
make test-frontend           # Run Vitest tests
make test-backend            # Run pytest tests
make test-backend-verbose    # Run pytest with verbose output
make test-backend-coverage   # Run pytest with coverage report
make test-e2e                # Run Playwright E2E tests
make lint                    # Run ESLint on frontend
```

**E2E Test Prerequisites:**
```bash
make db-start && make db-init && make db-seed  # Start database with test data
make dev-backend                                # Start backend API server
# Frontend is started automatically by Playwright
```

### Building & Deployment
```bash
make build                 # Build frontend and container images
make push                  # Push images to registry
make deploy               # Deploy to development
make deploy-prod          # Deploy to production
make undeploy             # Remove development deployment
```

## Architecture

### Frontend (React + Vite + PatternFly)
- **UI Framework**: PatternFly React components for enterprise-ready UI
- **TypeScript** for type safety
- **Vite** for fast development and building
- **React Router** for client-side routing
- **React Query** (TanStack Query) for server state management
- **Vitest** for unit testing
- **Axios** for API communication with 401 interceptor
- **Proxy Configuration**:
  - Local dev: Vite proxies `/api/` to `http://localhost:8000`
  - Production: Nginx proxies `/api/` to backend service

### Backend (FastAPI)
- **Python 3.11+** with FastAPI framework
- **Uvicorn** as ASGI server
- **UV Package Manager**: Fast, reliable dependency management
- **Database**: PostgreSQL with SQLModel ORM
- **Alembic** for database migrations
- **API Structure**: Versioned routing (`/api/v1/...`)
- **Testing**: pytest with async support

### Deployment
- Docker containers for both services
- OpenShift Routes for external access
- Kustomize for environment-specific configuration
- Quay.io as container registry

## API Endpoints

**Base URL**: All API endpoints prefixed with `/api/v1/`

**System:**
- `GET /` - Root endpoint
- `GET /api/v1/utils/health-check` - Health check with database connectivity

**Users API:**
- `GET /api/v1/users/me` - Get current authenticated user

**Items API (REST):**
- `GET /api/v1/items/` - List items with pagination, search, and sorting
- `GET /api/v1/items/{id}` - Get item by ID
- `POST /api/v1/items/` - Create new item (authenticated)
- `PUT /api/v1/items/{id}` - Update item (owner or admin only)
- `DELETE /api/v1/items/{id}` - Delete item (owner or admin only)

## GraphQL API

**Endpoint:** `/graphql`

The application uses **Strawberry GraphQL** for complex queries with relationships. The frontend uses GraphQL for all read operations, while REST is used for mutations (create, update, delete).

**Architecture:**
- **REST for mutations** - Simple CRUD operations without relationships
- **GraphQL for reads** - Queries that need relationships (e.g., Items with Owner)

**Key Features:**
- DataLoaders for N+1 query prevention
- Security extensions (QueryDepthLimiter, MaxTokensLimiter)
- Full type safety with Strawberry types

**Example Query:**
```graphql
query Items($skip: Int, $limit: Int, $search: String) {
  items(skip: $skip, limit: $limit, search: $search) {
    id
    title
    description
    owner {
      id
      username
      email
    }
  }
  itemsCount(search: $search)
}
```

**Frontend Integration:**
- Uses `graphql-request` with React Query
- GraphQL client in `frontend/src/app/graphql/client.ts`
- Queries in `frontend/src/app/graphql/queries.ts`
- Types in `frontend/src/app/graphql/types.ts`

## Authentication

This application uses **OAuth2 Proxy** for authentication. See [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md) for full setup guide.

**Local Development:**
- Set `ENVIRONMENT=local` in `.env` for development without OAuth
- A default "dev-user" is used for all requests in local mode

**Production:**
- OAuth2 Proxy runs as a sidecar container
- Supports Keycloak, Google, and GitHub OAuth providers
- Users are auto-created on first login from OAuth headers

**Frontend:**
- User menu with logout in the header
- API client automatically handles 401 responses
- Redirects to `/oauth2/sign_out` for logout

## Common Pitfalls

**CRITICAL: This section documents project-specific gotchas.**

### Database (CRITICAL)

- ❌ **NEVER add `cascade="all, delete"` to many-to-many relationships** → Will delete related entities, not just join table entries
- ❌ Modifying database models without creating a migration → **ALWAYS** run `alembic revision --autogenerate`
- ❌ Not reviewing auto-generated migrations → **CRITICAL**: Check SQL before applying (migrations can drop data!)
- ❌ Running migrations in wrong environment → Double-check before applying

### API Development

- ❌ Missing CORS configuration → Add origins to `backend/app/core/config.py`
- ❌ Not using Pydantic models for validation → **ALWAYS** define request/response schemas
- ❌ Hardcoding URLs or sensitive values → Use environment variables (`.env` files)
- ❌ Wrong HTTP status codes → 400 (bad input) vs 404 (not found) vs 409 (conflict)

### Frontend (React/PatternFly)

- ❌ **NEVER use inline styles (`style={{...}}`**) → Use PatternFly components (Stack/Flex/Grid)
- ❌ Hardcoding colors → Use PatternFly CSS variables (`var(--pf-v6-global--...)`)
- ❌ Not handling loading/error states → Show EmptyState component
- ❌ Using `any` type in TypeScript → Be specific with types

### Testing

- ❌ Pushing without running tests → **ALWAYS** run `make test` before committing
- ❌ Not testing error cases → Test both success and error scenarios
- ❌ **Leaving dangling test processes** → Kill orphaned processes: `pkill -f vitest`

### Git/Commits

- ❌ Not following Conventional Commits → Use `feat:`, `fix:`, `refactor:`, etc.
- ❌ Committing `.env` files with secrets → Use `.env.example` templates

## Development Workflow

### Initial Setup
1. Install dependencies: `make setup`
2. Start database: `make db-start`
3. Initialize database: `make db-init && make db-seed`
4. Start development servers: `make dev`

### Daily Development
1. Start database: `make db-start` (if not already running)
2. Make changes to frontend or backend
3. Test locally with `make dev`
4. Run tests: `make test`

### Incremental Development Workflow

For complex features with multiple steps (5+ file changes), use the incremental approach:

1. Create feature branch (`feature/<name>`, `refactor/<name>`, or `fix/<name>`)
2. Write implementation plan to `.tmp/<feature>-implementation-plan.md`
3. Track with status markers: ⏳ Pending → 🚧 In Progress → ✅ Complete → ⏸️ Awaiting Review → 🎉 Approved
4. Per step: Implement → Test (>80% coverage) → Commit → Review → Approve
5. Use Conventional Commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`

**📖 See**: [docs/INCREMENTAL-WORKFLOW.md](docs/INCREMENTAL-WORKFLOW.md) for detailed process.

### Autonomous Agent Workflow

For extended autonomous work with verification checkpoints:

1. Create progress directory at `.tmp/{feature-name}/`
2. Write plan.md, progress.md, current-step.md
3. Spawn verification agents at checkpoints
4. Handle errors with 3-attempt retry logic
5. Escalate to user if blocked

**📖 See**: [docs/AUTONOMOUS-WORKFLOW.md](docs/AUTONOMOUS-WORKFLOW.md) for detailed process.

## Additional Resources

**Developer Documentation (`docs/`):**
- [AUTHENTICATION.md](docs/AUTHENTICATION.md) - OAuth2 Proxy setup and configuration
- [DEVELOPMENT.md](docs/DEVELOPMENT.md) - Development setup and workflows
- [INCREMENTAL-WORKFLOW.md](docs/INCREMENTAL-WORKFLOW.md) - Step-by-step development for complex features
- [AUTONOMOUS-WORKFLOW.md](docs/AUTONOMOUS-WORKFLOW.md) - Self-running agents with verification
- [TESTING.md](docs/TESTING.md) - Testing frameworks, patterns, coverage goals
- [DATABASE.md](docs/DATABASE.md) - Schema, migrations, relationships
- [DEPLOYMENT.md](docs/DEPLOYMENT.md) - Container builds, GitOps, environments

**Domain-Specific Guides:**
- [frontend/CLAUDE.md](frontend/CLAUDE.md) - React/PatternFly patterns
- [backend/CLAUDE.md](backend/CLAUDE.md) - FastAPI/Python patterns

## Git Commit Guidelines

This project follows [Conventional Commits v1.0.0](https://www.conventionalcommits.org/).

**Format**: `<type>: <description>`

**Types**:
- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code refactoring
- `test:` - Adding tests
- `docs:` - Documentation
- `chore:` - Build/dependencies

**Guidelines**:
- Use imperative mood ("add" not "added")
- Keep under 72 characters
- Do NOT include AI assistant attribution
