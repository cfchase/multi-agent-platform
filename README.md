# PatternFly FastAPI Template

A production-ready full-stack application template with React frontend (Vite + PatternFly UI) and FastAPI backend, featuring PostgreSQL database, comprehensive testing, and OpenShift deployment.

## Features

- **Frontend**: React with TypeScript, Vite, and PatternFly UI components
- **Backend**: FastAPI with Python 3.11+, SQLModel ORM, and Alembic migrations
- **Database**: PostgreSQL 15 with container-based local development
- **Testing**: Vitest for unit tests, Playwright for end-to-end tests
- **Containerization**: Docker/Podman with multi-stage builds
- **Deployment**: OpenShift/Kubernetes with Kustomize
- **Developer Experience**: Comprehensive Makefile with 30+ commands

## Architecture

### Frontend
- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite for fast development and optimized production builds
- **UI Library**: PatternFly React components for enterprise-ready UI
- **Routing**: React Router with nested route support
- **API Client**: Axios with TypeScript types
- **Testing**: Vitest for unit tests, Playwright for E2E tests

### Backend
- **Framework**: FastAPI with async support
- **Database ORM**: SQLModel (combines SQLAlchemy and Pydantic)
- **Migrations**: Alembic for database schema versioning
- **Package Manager**: UV for fast, reliable Python dependency management
- **Validation**: Pydantic schemas with automatic OpenAPI documentation
- **Testing**: pytest with async support

### Database
- **Local Development**: PostgreSQL 15 in Docker/Podman container
- **Production**: PostgreSQL with persistent storage in Kubernetes
- **Migrations**: Alembic-managed schema migrations
- **Seeding**: Test data generation scripts for development

## Quick Start

### Prerequisites

- Node.js 22+
- Python 3.11+
- UV (Python package manager) - `pip install uv`
- Docker or Podman
- OpenShift CLI (`oc`) or kubectl
- Kustomize

### Local Development

1. **Clone and install dependencies**:
   ```bash
   git clone https://github.com/cfchase/patternfly-full-stack-fastapi-template
   cd patternfly-full-stack-fastapi-template
   make setup
   ```

2. **Start PostgreSQL database**:
   ```bash
   make db-start    # Start PostgreSQL container
   make db-init     # Run Alembic migrations
   make db-seed     # Populate with test data (optional)
   ```

3. **Run development servers**:
   ```bash
   make dev         # Run both frontend and backend
   ```

   Access the application:
   - Frontend: http://localhost:8080
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

4. **Run tests**:
   ```bash
   make test        # Run all tests
   make test-e2e    # Run E2E tests only
   ```

## Project Structure

```
├── backend/                    # FastAPI backend
│   ├── main.py                # Main application entry point
│   ├── app/
│   │   ├── api/              # API routes (versioned: /api/v1/...)
│   │   │   ├── deps.py       # Dependency injection (database sessions)
│   │   │   └── routes/       # API endpoints
│   │   ├── core/             # Core configuration
│   │   │   ├── config.py     # Settings and environment variables
│   │   │   └── db.py         # Database connection and engine
│   │   ├── models.py         # SQLModel database models and schemas
│   │   └── alembic/          # Database migrations
│   ├── scripts/              # Utility scripts (seed data, etc.)
│   ├── pyproject.toml        # Python dependencies (UV format)
│   ├── alembic.ini           # Alembic configuration
│   └── Dockerfile            # Backend container image
├── frontend/                  # React frontend
│   ├── src/
│   │   └── app/              # Application components
│   │       ├── Items/        # Item Browser (full CRUD example)
│   │       ├── services/     # API service layer
│   │       └── routeConfig.tsx  # Route configuration
│   ├── e2e/                  # Playwright E2E tests
│   ├── playwright.config.ts  # Playwright configuration
│   ├── package.json          # Node dependencies
│   ├── vite.config.ts        # Vite configuration with API proxy
│   ├── Dockerfile            # Frontend container (nginx-based)
│   └── nginx.conf            # Production nginx configuration
├── k8s/                      # Kubernetes/OpenShift manifests
│   ├── base/                 # Base Kustomize resources
│   │   ├── postgres-*.yaml   # PostgreSQL deployment, service, PVC
│   │   ├── db-migration-job.yaml    # Schema migration job
│   │   ├── db-seed-job.yaml         # Test data seeding job
│   │   ├── backend-*.yaml    # Backend deployment, service
│   │   └── frontend-*.yaml   # Frontend deployment, service, route
│   └── overlays/             # Environment-specific configurations
│       ├── dev/              # Development environment
│       └── prod/             # Production environment
├── scripts/                  # Automation scripts
│   ├── dev-db.sh            # PostgreSQL container management
│   ├── build-images.sh      # Container image building
│   ├── push-images.sh       # Container image pushing
│   └── deploy.sh            # Deployment automation
├── Makefile                  # Comprehensive command reference (30+ commands)
├── CLAUDE.md                 # Developer documentation (for AI assistants)
└── E2E_TESTING.md           # End-to-end testing guide
```

## Database Management

### Local Development Database

The project includes scripts for managing a PostgreSQL development database in a container:

```bash
# Start/Stop Database
make db-start       # Start PostgreSQL container (creates if needed)
make db-stop        # Stop PostgreSQL container
make db-status      # Check if database is running

# Database Operations
make db-init        # Run Alembic migrations to create/update schema
make db-seed        # Populate database with test data (3 users, 8 items)
make db-shell       # Open PostgreSQL shell (psql)
make db-logs        # Show PostgreSQL logs

# Maintenance
make db-reset       # Remove container and delete all data (destructive!)
```

**Database Configuration:**
- Container: `app-postgres-dev`
- Volume: `app-db-data` (persistent storage)
- Default credentials: `app` / `changethis`
- Port: `5432`

### Cluster Database

For database operations in OpenShift/Kubernetes:

```bash
make db-migrate-cluster    # Run Alembic migrations in cluster
make db-seed-cluster       # Seed test data in cluster
make db-init-cluster       # Run both migrations and seeding
```

## Development Commands

### Setup and Installation
```bash
make setup              # Install all dependencies (frontend + backend)
make setup-frontend     # Install frontend dependencies only
make setup-backend      # Install backend dependencies only
make env-setup          # Create .env files from examples
```

### Running Development Servers
```bash
make dev                # Run both frontend and backend
make dev-frontend       # Run React dev server (port 8080)
make dev-backend        # Run FastAPI server with auto-reload (port 8000)
```

### Testing
```bash
make test                              # Run all tests (frontend + backend)
make test-frontend                     # Run lint, type checking, and Vitest tests
make test-backend                      # Run pytest tests (syncs deps first)
make test-backend VERBOSE=1            # Verbose output
make test-backend COVERAGE=1           # With coverage report
make test-backend FILE=tests/api/test_items.py  # Specific test file
make test-backend VERBOSE=1 COVERAGE=1 # Combine options
make test-e2e                # Run Playwright E2E tests
make test-e2e-ui             # Run E2E tests with Playwright UI (interactive)
make test-e2e-headed         # Run E2E tests in headed mode (visible browser)
make update-tests            # Update frontend test snapshots
make lint                    # Run ESLint on frontend
```

**E2E Test Prerequisites:**
```bash
# Before running E2E tests, ensure these services are running:
make db-start && make db-init && make db-seed  # Start database with test data
make dev-backend                                # Start backend API
# Frontend is started automatically by Playwright
```

### Building
```bash
make build-frontend     # Build frontend for production
make build              # Build frontend and container images (latest tag)
make build-prod         # Build with prod tag for production deployment
```

### Container Registry
```bash
make push               # Push images with latest tag
make push-prod          # Push images with prod tag
make TAG=v1.0.0 build  # Build with custom tag
make CONTAINER_TOOL=podman build  # Use podman instead of docker
```

## API Endpoints

### Current Endpoints

**Health and Utils:**
- `GET /` - Root endpoint
- `GET /api/v1/utils/health-check` - Health check with database connectivity

**Items API (Simplified - No Authentication):**
- `GET /api/v1/items/` - List all items (with pagination)
- `GET /api/v1/items/{id}` - Get item by ID
- `POST /api/v1/items/` - Create new item
- `PUT /api/v1/items/{id}` - Update item
- `DELETE /api/v1/items/{id}` - Delete item

**API Documentation:**
- Interactive docs: http://localhost:8000/docs
- OpenAPI spec: http://localhost:8000/openapi.json

### Database Models

**User Model:**
- `id`: UUID (primary key)
- `email`: EmailStr (unique, indexed)
- `hashed_password`: str
- `full_name`: str | None
- `is_active`: bool (default: True)
- `is_superuser`: bool (default: False)
- `items`: Relationship to Item model

**Item Model:**
- `id`: UUID (primary key)
- `title`: str (required, max 255 chars)
- `description`: str | None (max 255 chars)
- `owner_id`: UUID (foreign key to User)
- `owner`: Relationship to User model

## Deployment

### Build and Push Images

```bash
# For development (uses latest tag)
make build
make push

# For production (uses prod tag)
make build-prod
make push-prod
```

**Important**: The k8s overlays expect specific image tags:
- Development environment: `latest` tag
- Production environment: `prod` tag

### Deploy to OpenShift/Kubernetes

1. **Login to cluster**:
   ```bash
   oc login --server=https://your-openshift-cluster
   # or
   kubectl config use-context your-context
   ```

2. **Deploy application**:
   ```bash
   make deploy          # Deploy to development
   make deploy-prod     # Deploy to production
   ```

3. **Initialize database** (first time only):
   ```bash
   make db-init-cluster    # Run migrations and seed test data
   # or separately:
   make db-migrate-cluster # Just run migrations
   make db-seed-cluster    # Just seed test data
   ```

4. **Preview manifests**:
   ```bash
   make kustomize       # Preview development manifests
   make kustomize-prod  # Preview production manifests
   ```

5. **Remove deployment**:
   ```bash
   make undeploy        # Remove development deployment
   make undeploy-prod   # Remove production deployment
   ```

### Deployment Architecture

The deployment includes:
- **PostgreSQL**: StatefulSet with PersistentVolumeClaim (1Gi)
- **Backend**: Deployment with database connection
- **Frontend**: Deployment with nginx serving static files
- **Services**: ClusterIP services for internal communication
- **Route/Ingress**: External access to frontend
- **Jobs**: Database migration and seeding jobs
- **Secret**: Database credentials

### CI/CD GitHub Secrets

The GitHub Actions workflow requires the following secrets for building and pushing container images:

| Secret | Description |
|--------|-------------|
| `QUAY_USERNAME` | Quay.io username or robot account name |
| `QUAY_PASSWORD` | Quay.io password or robot account token |

**Setup Instructions:**

1. **Create a Quay.io robot account** (recommended):
   - Go to your Quay.io organization → Robot Accounts
   - Create a new robot account with write permissions to your repositories
   - Copy the robot name and token

2. **Add secrets to GitHub**:
   - Go to your GitHub repository → Settings → Secrets and variables → Actions
   - Add `QUAY_USERNAME` (e.g., `myorg+robot_name`)
   - Add `QUAY_PASSWORD` (the robot account token)

**Note**: Without these secrets, the CI will run tests but skip the image build/push step.

## Configuration

### Backend Environment Variables

Create `backend/.env` (copy from `backend/.env.example`):

```env
# Database Configuration
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=app
POSTGRES_PASSWORD=changethis
POSTGRES_DB=app

# Application Settings
ENVIRONMENT=local
PROJECT_NAME=PatternFly FastAPI Template
FRONTEND_HOST=http://localhost:8080
```

### Frontend Environment Variables

Create `frontend/.env` (copy from `frontend/.env.example`):

```env
VITE_API_URL=http://localhost:8000
```

## Testing

### Unit Tests

**Backend (pytest):**
```bash
cd backend
uv run pytest                    # Run all tests
uv run pytest -v                 # Verbose output
uv run pytest --cov=app          # With coverage
uv run pytest tests/test_*.py    # Specific test file
```

**Frontend (Vitest):**
```bash
cd frontend
npm run test                     # Run all tests
npm run test -- --ui             # Run with UI
```

### End-to-End Tests

See [E2E_TESTING.md](E2E_TESTING.md) for complete E2E testing documentation.

```bash
make test-e2e           # Run all E2E tests
make test-e2e-ui        # Run with Playwright UI (debug mode)
make test-e2e-headed    # Run with visible browser
```

**E2E Test Coverage:**
- Item CRUD operations (Create, Read, Update, Delete)
- Search and filtering
- Drawer navigation
- Empty states
- Error handling

## Development Workflow

### Initial Setup
```bash
make setup           # Install dependencies
make db-start        # Start PostgreSQL
make db-init         # Run migrations
make db-seed         # Add test data (optional)
make env-setup       # Create .env files
make dev             # Start development servers
```

### Daily Development
```bash
make db-start        # Ensure database is running
make dev             # Start both servers
# Make changes to code...
make test            # Run tests
make test-e2e        # Run E2E tests
```

### Adding Database Changes
```bash
# 1. Modify models in backend/app/models.py
# 2. Generate migration
cd backend
uv run alembic revision --autogenerate -m "description"
# 3. Review and edit migration in app/alembic/versions/
# 4. Apply migration
make db-init
```

### Deployment Workflow
```bash
# 1. Build and push images
make build && make push              # For dev
# or
make build-prod && make push-prod    # For prod

# 2. Deploy
make deploy          # Deploy to dev
# or
make deploy-prod     # Deploy to prod

# 3. Initialize database (first time only)
make db-init-cluster
```

## Adding New Features

### Adding API Endpoints
1. Create route file in `backend/app/api/routes/v1/<feature>/`
2. Define router with endpoints
3. Import router in `backend/app/api/routes/v1/router.py`
4. Available at `/api/v1/<feature>/...`

### Adding Frontend Pages
1. Create component in `frontend/src/app/<PageName>/`
2. Add route to `frontend/src/app/routeConfig.tsx`
3. Route appears in navigation if `label` is provided

### Adding Database Models
1. Add model to `backend/app/models.py`
2. Generate migration: `cd backend && uv run alembic revision --autogenerate -m "Add <model>"`
3. Review migration in `backend/app/alembic/versions/`
4. Apply: `make db-init`

## Customization

### Update Container Registry
1. Update `REGISTRY` in Makefile (default: `quay.io/cfchase`)
2. Update image references in `k8s/base/kustomization.yaml`
3. Update references in overlay files

### Update Application Name
1. Update `PROJECT_NAME` in `backend/app/core/config.py`
2. Update page titles in `frontend/src/app/routeConfig.tsx`
3. Update README and documentation

### Update Database Credentials
1. Update `backend/.env` for local development
2. Update `k8s/base/postgres-secret.yaml` for cluster deployment
3. Ensure secrets are not committed to git

## Health Checks

### Manual Health Checks
```bash
make health-backend     # Check backend API
make health-frontend    # Check frontend server
```

### API Health Check
```bash
curl http://localhost:8000/api/v1/utils/health-check
# Response: {"status": "healthy", "database": "connected"}
```

## Troubleshooting

### Database Connection Issues
```bash
make db-status          # Check if database is running
make db-logs            # Check database logs
make db-reset           # Reset database (removes all data!)
```

### Frontend Not Loading
```bash
# Check if backend is running
make health-backend

# Check Vite proxy configuration
cat frontend/vite.config.ts
```

### E2E Tests Failing
```bash
# Ensure database has test data
make db-seed

# Ensure backend is running
make dev-backend

# Run tests with visible browser for debugging
make test-e2e-headed
```

### Cluster Deployment Issues
```bash
# Check pod status
oc get pods
kubectl get pods

# Check logs
oc logs deployment/backend
oc logs deployment/frontend
oc logs deployment/postgres

# Check migration job
oc logs job/db-migration
```

## Additional Documentation

- **CLAUDE.md**: Comprehensive developer guide (optimized for AI assistants)
- **E2E_TESTING.md**: End-to-end testing documentation
- **API Documentation**: http://localhost:8000/docs (when running locally)

## Roadmap

- [x] PostgreSQL database with SQLModel ORM
- [x] Alembic database migrations
- [x] Item CRUD API and UI
- [x] End-to-end testing with Playwright
- [x] OpenShift/Kubernetes deployment
- [ ] JWT authentication (Phase 3)
- [ ] OAuth2 with Google & GitHub (Phase 5)
- [ ] Email-based password recovery (Phase 9)
- [ ] User management UI (Phase 7)

## License

Apache License 2.0
