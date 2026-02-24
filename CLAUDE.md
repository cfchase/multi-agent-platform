# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**IMPORTANT**: This is the root project guide. For domain-specific details:
- **Frontend work**: See [frontend/CLAUDE.md](frontend/CLAUDE.md) for React/PatternFly specifics
- **Backend work**: See [backend/CLAUDE.md](backend/CLAUDE.md) for FastAPI/Python specifics
- **Detailed docs**: See [docs/](docs/) for comprehensive guides

## Repository Overview

Multi-Agent Platform is a full-stack application with React frontend (Vite + PatternFly UI) and FastAPI backend, designed for deployment to OpenShift using Docker containers and Kustomize.

## Quick Decision Guide

**New to the project?**
```bash
make setup && make services-start && make db-seed && make dev
```

**Making code changes?**
- Run `make dev` (runs frontend + backend with hot reload)
- Frontend changes: Files in `frontend/src/app/` auto-reload
- Backend changes: FastAPI auto-reloads on save

**Changing database models?**
1. Update models in `backend/app/models/` (user.py, item.py, chat.py, chat_message.py)
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
- API not working? Check `/api/v1/utils/health-check` → Verify `config/local/.env` → Check CORS settings
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
├── config/              # Centralized configuration (source of truth)
│   ├── local/          # Local development config (.env.example)
│   └── dev/            # Cluster deployment config (.env.example)
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
make config-setup      # Copy config/local/.env.example to config/local/.env
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

**Chats API (REST):**
- `GET /api/v1/chats/` - List user's chats with pagination
- `GET /api/v1/chats/{id}` - Get chat by ID (ownership check)
- `POST /api/v1/chats/` - Create new chat
- `PUT /api/v1/chats/{id}` - Update chat title and/or flow_name
- `DELETE /api/v1/chats/{id}` - Delete chat (cascades to messages)

**Chat Messages API (REST):**
- `GET /api/v1/chats/{chat_id}/messages/` - List messages in a chat
- `POST /api/v1/chats/{chat_id}/messages/` - Create message (non-streaming)
- `POST /api/v1/chats/{chat_id}/messages/stream` - Stream AI response via SSE (locks flow_name on first message)

**Flows API (REST):**
- `GET /api/v1/flows/` - List available Langflow flows (includes `default_flow` from LANGFLOW_DEFAULT_FLOW)

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
- Default: `ENVIRONMENT=development` uses OAuth (mock or real provider via `make services-start`)
- Access the app at `http://localhost:4180` (OAuth proxy port)
- Set `ENVIRONMENT=local` to bypass OAuth entirely (uses dev-user, access at `http://localhost:8080`)

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
- ❌ Hardcoding URLs or sensitive values → Use environment variables (`config/local/.env` for local dev)
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
- ❌ Committing `.env` files with secrets → Use `config/local/.env.example` template

## Development Workflow

### Initial Setup
1. Install dependencies: `make setup`
2. Configure environment: `make config-setup` (copies from `config/local/.env.example`)
3. Start all services: `make services-start`
4. Seed test data: `make db-seed`
5. Start development servers: `make dev`

### Daily Development
1. Start services: `make services-start` (starts db + langflow + langfuse + mlflow)
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

**📖 See**: [claude-extras/incremental-workflow.md](claude-extras/incremental-workflow.md) for detailed process.

### Autonomous Agent Workflow

For extended autonomous work with verification checkpoints:

1. Create progress directory at `.tmp/{feature-name}/`
2. Write plan.md, progress.md, current-step.md
3. Spawn verification agents at checkpoints
4. Handle errors with 3-attempt retry logic
5. Escalate to user if blocked

**📖 See**: [claude-extras/autonomous-workflow.md](claude-extras/autonomous-workflow.md) for detailed process.

## LangFlow Integration

### Flow Management

Flows, components, and MCP servers are managed via `flow-sources.yaml` (gitignored — local config with machine-specific paths). See `config/dev/flow-sources.yaml` for the cluster variant.

**Import pipeline:**
1. `scripts/import_flows.py` reads `flow-sources.yaml` entries
2. Components staged to temp dir, copied to LangFlow container
3. MCP servers registered via PVC JSON config files
4. Flows imported via LangFlow REST API with replace-on-import (find by name, delete, recreate)

**Key scripts:**
| Script | Purpose |
|--------|---------|
| `scripts/dev-langflow.sh` | Start LangFlow container (stock or custom image mode) |
| `scripts/import_flows.py` | Import components, MCP servers, and flows |
| `scripts/langflow-import-cluster.sh` | Cluster-mode import (staging + pod copy + API import) |
| `scripts/deploy-langflow.sh` | Deploy LangFlow to K8s/OpenShift via Helm |

**Custom image mode** (`dev-langflow.sh`):
- Uses custom-built image with `redhat_agents` pre-installed
- Connects to shared PostgreSQL (same as stock mode)
- Mounts data at `/data/langflow` instead of `/app/langflow` (avoids overwriting the editable install)
- Forwards additional env vars not needed by stock image: GCP credentials, Google OAuth client, and Granite Guardian settings
- Set `LANGFLOW_LAZY_LOAD_COMPONENTS=false` for custom components to appear fully loaded

### User Settings / Tweaks Injection

Platform injects per-user credentials and app settings to LangFlow components via tweaks:

```python
tweaks = {
    "User Settings": {"settings_data": {"google_drive_token": "...", "dataverse_token": "..."}},
    "App Settings": {"settings_data": {"features": {...}}},
}
```

**CRITICAL:** Tweaks match by `display_name` (e.g., `"User Settings"` with space), NOT component `name` attribute (`"UserSettings"`). Components MUST declare inputs — `inputs = []` causes tweaks to be silently dropped.

**Backend injection:**
- `build_app_settings_data()` returns non-secret app context (feature flags, app name). API keys reach LangFlow via environment variables, not tweaks.
- `build_user_settings_data()` injects per-user OAuth tokens (from OAuth proxy headers → backend → LangFlow API)
- `build_generic_tweaks()` assembles both into the tweaks dict sent to LangFlow

### Helm Charts & Deployment

```
helm/
├── langflow/
│   ├── values-dev.yaml              # Custom image, env vars, resources
│   └── post-renderer/
│       ├── kustomization.yaml       # Kustomize patch references
│       ├── oauth-proxy-patch.yaml   # OAuth2 Proxy sidecar for authentication
│       ├── dept-toolserver-sidecar-patch.yaml  # dept-toolserver sidecar container
│       ├── langflow-credentials-patch.yaml     # Secret env injection
│       ├── langflow-data-pvc-patch.yaml        # Persistent volume for data
│       └── security-context-patch.yaml         # Pod security context
├── langfuse/                        # Observability (Langfuse + ClickHouse + Redis)
└── mlflow/                          # ML experiment tracking
```

**dept-toolserver sidecar:**
- MCP server for department tree navigation (port 8086)
- Added to langflow StatefulSet via strategic merge patch
- Uses `tcpSocket` probes (MCP protocol uses POST; GET returns 406)
- Image from OpenShift internal registry

### Environment Variables

LangFlow env vars configured in `config/local/.env` and forwarded by `dev-langflow.sh`:
- `LANGFLOW_FALLBACK_TO_ENV_VAR=true` — enables env vars as global variable values
- `LANGFLOW_LAZY_LOAD_COMPONENTS=false` — required for custom components
- GCP credentials: `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- Granite Guardian: `GRANITE_GUARDIAN_ENDPOINT`, `GRANITE_GUARDIAN_API_KEY`, `GRANITE_CA_BUNDLE`
- Langfuse: `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_HOST`

### Related Repos

| Repo | Purpose | Branch |
|------|---------|--------|
| agents-python | Enterprise agent components and `redhat_agents` library | `feature/platform-multi-user` |
| langflow-examples | Shared example flows, platform components (UserSettings, AppSettings) | `feature/enterprise-agent-migration` |
| analyze-flow | Historical — enterprise agent stubs and planning docs | `feature/enterprise-agent-migration` |

## Additional Resources

**Claude Agent Workflows (`claude-extras/`):**
- [autonomous-workflow.md](claude-extras/autonomous-workflow.md) - Extended autonomous work with verification
- [incremental-workflow.md](claude-extras/incremental-workflow.md) - Step-by-step with human review

**Developer Documentation (`docs/`):**
- [AUTHENTICATION.md](docs/AUTHENTICATION.md) - OAuth2 Proxy setup and configuration
- [DEVELOPMENT.md](docs/DEVELOPMENT.md) - Development setup and workflows
- [TESTING.md](docs/TESTING.md) - Testing frameworks, patterns, coverage goals
- [DATABASE.md](docs/DATABASE.md) - Schema, migrations, relationships
- [DEPLOYMENT.md](docs/DEPLOYMENT.md) - Container builds, GitOps, environments

**Domain-Specific Guides:**
- [frontend/CLAUDE.md](frontend/CLAUDE.md) - React/PatternFly patterns
- [backend/CLAUDE.md](backend/CLAUDE.md) - FastAPI/Python patterns

## Git Commit Guidelines

This project follows [Conventional Commits v1.0.0](https://www.conventionalcommits.org/).

**Format**: `<type>: <description>`

**Types**: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`

**Guidelines**:
- Keep messages concise - focus on **what** changed and **why**
- Use imperative mood ("add" not "added")
- First line under 72 characters
- Skip bullet lists of individual file changes
- Do NOT include AI assistant attribution

**Examples**:
- `feat: add user authentication with OAuth2`
- `fix: resolve race condition in data fetching`
- `refactor: extract auth module from user service`
