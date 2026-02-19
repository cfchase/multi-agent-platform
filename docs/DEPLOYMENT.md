# Deployment Guide

## Overview

This template supports deployment to OpenShift/Kubernetes using:
- Docker/Podman for container builds
- Quay.io for container registry
- Kustomize for environment configuration
- OpenShift Routes for ingress

## Quick Reference

```bash
# Build containers
make build                     # Build with 'latest' tag
make build TAG=v1.0.0          # Build with specific tag
make build-prod                # Build with 'prod' tag

# Push to registry
make push                      # Push with 'latest' tag
make push TAG=v1.0.0           # Push with specific tag
make push-prod                 # Push with 'prod' tag

# Deploy
make deploy                    # Deploy to dev environment
make deploy-prod               # Deploy to prod environment
make undeploy                  # Remove dev deployment
make undeploy-prod             # Remove prod deployment
make verify-deploy             # Check deployment health

# Database in cluster
make db-init-cluster           # Run migrations + seed data
make db-migrate-cluster        # Run migrations only
make db-seed-cluster           # Run seed data only
```

## Container Builds

### Build Configuration

```makefile
# Default values (can be overridden)
REGISTRY ?= quay.io/cfchase
TAG ?= latest
CONTAINER_TOOL ?= docker  # or podman
```

### Building Images

```bash
# Build both frontend and backend
make build

# With custom registry and tag
make build REGISTRY=my-registry.io/myorg TAG=v1.0.0

# Using podman
make build CONTAINER_TOOL=podman
```

### Image Names

- **Frontend**: `${REGISTRY}/frontend:${TAG}`
- **Backend**: `${REGISTRY}/backend:${TAG}`

## Container Registry

### Quay.io Setup

1. Create account at quay.io
2. Create repositories: `frontend`, `backend`
3. Configure robot account or login:
   ```bash
   docker login quay.io
   # or
   podman login quay.io
   ```

### Pushing Images

```bash
# Push both images
make push

# Push with specific tag
make push TAG=v1.0.0

# Production push
make push-prod  # Uses TAG=prod
```

## Kubernetes Deployment

### Directory Structure

```
config/
├── local/                          # Local development configs
│   └── .env.example               # Consolidated config template
├── dev/                            # Cluster deployment configs
│   └── .env.example               # Consolidated config template
│
k8s/
├── app/                            # Deep Research app (Kustomize)
│   ├── base/
│   │   ├── kustomization.yaml
│   │   ├── deployment.yaml         # Combined pod (frontend+backend+oauth-proxy)
│   │   ├── service.yaml
│   │   ├── route.yaml
│   │   ├── serviceaccount.yaml
│   │   └── oauth2-proxy-config.yaml
│   └── overlays/
│       ├── dev/
│       │   ├── kustomization.yaml
│       │   ├── oauth-proxy.env
│       │   └── oauth-proxy-secret.env  # gitignored
│       └── prod/
├── postgres/                       # PostgreSQL database (Kustomize)
│   ├── base/
│   └── overlays/dev/
├── langflow/                       # Legacy Kustomize (reference only)
│   └── README.md                   # Points to Helm deployment
├── mlflow/                         # Legacy Kustomize (reference only)
│   └── README.md                   # Points to Helm deployment
│
helm/
├── langfuse/                       # Langfuse Helm values
│   ├── values-dev.yaml
│   └── secrets-dev.yaml            # Auto-generated (gitignored)
├── langflow/                       # LangFlow Helm values
│   ├── values-dev.yaml
│   └── post-renderer/              # Kustomize post-renderer for OAuth sidecar
└── mlflow/                         # MLFlow Helm values
    └── values-dev.yaml
│
scripts/                               # Called via make targets (not directly)
├── generate-config.sh              # make config-setup-cluster / config-generate
├── verify-deployment.sh            # make verify-deploy
├── deploy.sh                       # make deploy
├── deploy-db.sh                    # make deploy-db
├── deploy-app.sh                   # make deploy-app
├── deploy-langflow.sh              # make deploy-langflow
├── deploy-mlflow.sh                # make deploy-mlflow
├── deploy-langfuse.sh              # make deploy-langfuse
└── undeploy.sh                     # make undeploy
```

### Architecture

The application uses a **consolidated pod deployment** with multiple containers:

```
                    ┌─────────────────────┐
                    │   OpenShift Route   │
                    │  (External Access)  │
                    └──────────┬──────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                           App Pod                                │
│  ┌────────────────┐                                              │
│  │  OAuth2 Proxy  │◄── All external requests enter here          │
│  │  (Port 4180)   │                                              │
│  │                │    - Authenticates users                     │
│  │  ENTRY POINT   │    - Sets X-Forwarded-User headers           │
│  └───────┬────────┘    - Redirects to OAuth provider             │
│          │                                                       │
│          ▼                                                       │
│  ┌────────────────┐                                              │
│  │    Frontend    │    - Serves React static files               │
│  │  (Port 8080)   │    - Proxies /api/* to backend               │
│  │                │                                              │
│  │  Nginx Proxy   │                                              │
│  └───────┬────────┘                                              │
│          │                                                       │
│          ▼                                                       │
│  ┌────────────────┐                                              │
│  │    Backend     │    - FastAPI application                     │
│  │  (Port 8000)   │    - GraphQL + REST APIs                     │
│  │                │    - Admin panel                             │
│  │ INTERNAL ONLY  │◄── Cluster-internal, NOT directly exposed    │
│  └────────────────┘                                              │
│                                                                  │
│  Init Container: db-migration (runs alembic upgrade head)        │
└──────────────────────────────────────────────────────────────────┘
```

**Security Architecture:**
- **Backend is INTERNAL ONLY**: Not directly accessible from outside the cluster
- **All requests flow through OAuth2 Proxy**: Authentication is enforced
- **Frontend proxies API calls**: Backend only receives authenticated requests
- **X-Forwarded-User headers**: Set by OAuth2 Proxy, trusted by backend

**Key Features:**
- **Init Container**: Runs database migrations before app starts
- **OAuth2 Proxy Sidecar**: Handles authentication
- **Security Contexts**: runAsNonRoot, dropped capabilities
- **Resource Limits**: Defined for all containers

### Environment Overlays

**Development (`k8s/overlays/dev/`):**
- Uses `latest` image tag
- Includes in-cluster PostgreSQL deployment
- Lower resource limits
- OAuth2 proxy configured for dev

**Production (`k8s/overlays/prod/`):**
- Uses `prod` image tag
- Uses external/managed database
- Higher resource limits
- Production OAuth2 secrets

### OAuth2 Proxy Secret Setup

**CRITICAL**: Before deploying, you must configure OAuth credentials.

1. **Set up configuration:**
   ```bash
   # Generate config from template
   make config-setup-cluster

   # Or manually copy the consolidated config:
   cp config/dev/.env.example config/dev/.env
   ```

2. **Edit `config/dev/.env` with your OAuth provider credentials:**
   ```bash
   OAUTH_CLIENT_ID=your-oauth-client-id
   OAUTH_CLIENT_SECRET=your-oauth-client-secret
   ```

3. **Generate deployment artifacts** (secrets are auto-generated):
   ```bash
   make config-generate
   ```

4. **The `.env` file is gitignored** - never commit OAuth secrets!

See [AUTHENTICATION.md](AUTHENTICATION.md) for OAuth provider configuration details.

### Deploying

```bash
# Preview manifests
make kustomize-app       # Preview app manifests
make kustomize-postgres  # Preview postgres manifests
make kustomize-langflow  # Preview langflow manifests
make kustomize-mlflow    # Preview mlflow manifests

# Apply to cluster
make deploy          # Dev environment
make deploy-prod     # Prod environment

# Verify deployment health
make verify-deploy

# Remove deployment
make undeploy
make undeploy-prod
```

## AI/ML Infrastructure Services

The deployment includes three AI/ML services, all deployed via Helm:

| Service | Purpose | Authentication | Helm Chart |
|---------|---------|----------------|------------|
| **LangFlow** | Visual workflow builder | OpenShift OAuth (SAR-based) | `langflow/langflow-ide` |
| **Langfuse** | LLM observability | Built-in email/password | `langfuse/langfuse` |
| **MLFlow** | Experiment tracking | OpenShift OAuth (SAR-based) | `community-charts/mlflow` |

### Deployment

All services are deployed automatically with `make deploy`:

```bash
make deploy
```

At the end of deployment, credentials and URLs are displayed:

```
========================================
ADMIN CREDENTIALS
========================================
Email:    admin@localhost.local
Password: <auto-generated>

SERVICE URLS
========================================
Deep Research: https://multi-agent-platform-multi-agent-platform-dev.<cluster-domain>
LangFlow:      https://langflow-multi-agent-platform-dev.<cluster-domain>
Langfuse:      https://langfuse-multi-agent-platform-dev.<cluster-domain>
MLFlow:        https://mlflow-multi-agent-platform-dev.<cluster-domain>
========================================
```

### Retrieving Credentials

```bash
# Show credentials and URLs anytime
make get-admin-credentials
```

### Service Architecture

All AI/ML services are deployed via Helm and share the PostgreSQL database.

**LangFlow** (`langflow/langflow-ide`)
- StatefulSet deployment with frontend + backend
- Uses shared PostgreSQL for metadata
- External access via OpenShift OAuth proxy sidecar (SAR: namespace pods update)
- Internal backend access via `langflow-service-backend:7860` bypasses OAuth

**MLFlow** (`community-charts/mlflow`)
- Deployment with PostgreSQL backend store
- External access via OpenShift OAuth proxy sidecar (SAR: namespace pods update)
- Internal backend access via `mlflow:5000` bypasses OAuth

**Langfuse** (`langfuse/langfuse`)
- Includes Redis, ClickHouse, Zookeeper subcharts
- Uses shared PostgreSQL for application data
- Built-in authentication (email/password signup)
- Secrets auto-generated on first deploy

### Supporting Services OAuth Architecture

Langflow and MLflow are protected by OpenShift OAuth proxy sidecars that enforce namespace-scoped access control.

**Access Pattern:**
- External access (via Route) goes through OAuth proxy on port 4180
- Internal access (via ClusterIP Service) bypasses OAuth entirely
- SAR rule: `{"namespace":"<namespace>","resource":"pods","verb":"update"}` restricts access to namespace admins

**Dual Service Pattern:**
Each protected service has two Kubernetes Services:
- Internal: `langflow-service-backend:7860` / `mlflow:5000` (direct access, no auth)
- External: `langflow-external:4180` / `mlflow-external:4180` (OAuth proxy, Route points here)

**Shared Resources:**
- ServiceAccount: `supporting-services-proxy` (shared by all OAuth-protected services)
- Session Secret: `supporting-services-proxy-session` (preserves sessions across redeploys)
- OAuth redirect annotations on ServiceAccount for route-based callback URLs

### Individual Component Deployment

```bash
# Deploy individual components
make deploy-db        # PostgreSQL only
make deploy-app       # Deep Research app only
make deploy-langflow  # LangFlow only
make deploy-mlflow    # MLFlow only
make deploy-langfuse  # Langfuse only
```

### Helm Commands

```bash
# Langfuse management
make helm-langfuse-status    # Check status
make helm-langfuse-upgrade   # Upgrade release
make helm-langfuse-logs      # View logs
make helm-langfuse-uninstall # Remove

# LangFlow management
make helm-langflow-status    # Check status
make helm-langflow-logs      # View logs

# MLFlow management
make helm-mlflow-status      # Check status
make helm-mlflow-logs        # View logs
```

## Database in Cluster

### Initial Setup

After deploying, initialize the database:

```bash
# Option 1: Migrations + seed data (recommended for dev)
make db-init-cluster

# Option 2: Migrations only (for production)
make db-migrate-cluster

# Option 3: Seed data only (after migrations)
make db-seed-cluster
```

### Re-running Jobs

```bash
# Delete existing jobs first
oc delete job db-migration db-seed

# Then re-run
make db-init-cluster
```

### Production Database

For production, consider using a managed database:

1. Create managed PostgreSQL instance
2. Update secret in overlay:
   ```yaml
   # k8s/overlays/prod/postgres-secret.yaml
   apiVersion: v1
   kind: Secret
   metadata:
     name: postgres-secret
   stringData:
     username: produser
     password: securepassword
     database: proddb
     host: managed-postgres.example.com
     port: "5432"
   ```

3. Remove PostgreSQL deployment from prod overlay

## OpenShift Routes

### Automatic Route Creation

The base kustomization includes a Route resource:

```yaml
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: frontend-route
spec:
  to:
    kind: Service
    name: frontend
  port:
    targetPort: 8080
  tls:
    termination: edge
```

### Custom Domain

```yaml
# In overlay kustomization
patches:
  - target:
      kind: Route
      name: frontend-route
    patch: |
      - op: add
        path: /spec/host
        value: myapp.example.com
```

## Environment Variables

### Backend Environment

Required environment variables:

```yaml
env:
  - name: POSTGRES_SERVER
    valueFrom:
      secretKeyRef:
        name: postgres-secret
        key: host
  - name: POSTGRES_USER
    valueFrom:
      secretKeyRef:
        name: postgres-secret
        key: username
  - name: POSTGRES_PASSWORD
    valueFrom:
      secretKeyRef:
        name: postgres-secret
        key: password
  - name: POSTGRES_DB
    valueFrom:
      secretKeyRef:
        name: postgres-secret
        key: database
```

### Adding Custom Variables

Add to overlay:
```yaml
# k8s/overlays/prod/kustomization.yaml
configMapGenerator:
  - name: app-config
    literals:
      - LOG_LEVEL=INFO
      - FEATURE_FLAG=enabled

patches:
  - target:
      kind: Deployment
      name: backend
    patch: |
      - op: add
        path: /spec/template/spec/containers/0/envFrom/-
        value:
          configMapRef:
            name: app-config
```

## Health Checks

### Backend Health

The backend includes a health endpoint:
```
GET /api/v1/utils/health-check
```

Kubernetes probes:
```yaml
livenessProbe:
  httpGet:
    path: /api/v1/utils/health-check
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /api/v1/utils/health-check
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
oc get pods

# Check pod logs
oc logs <pod-name>

# Check events
oc get events --sort-by='.lastTimestamp'

# Describe pod
oc describe pod <pod-name>
```

### Database Connection Issues

```bash
# Verify postgres is running
oc get pods -l app=postgres

# Check postgres logs
oc logs -l app=postgres

# Verify secret
oc get secret postgres-secret -o yaml
```

### Image Pull Errors

```bash
# Check image pull secret
oc get secrets | grep pull

# Create pull secret if needed
oc create secret docker-registry quay-pull \
  --docker-server=quay.io \
  --docker-username=<user> \
  --docker-password=<password>
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Build and Deploy

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Login to Quay
        run: docker login quay.io -u ${{ secrets.QUAY_USER }} -p ${{ secrets.QUAY_TOKEN }}

      - name: Build and Push
        run: |
          make build TAG=${{ github.sha }}
          make push TAG=${{ github.sha }}

      - name: Deploy
        run: |
          # Update image tag in overlay
          # Apply to cluster
```

## See Also

- [DEVELOPMENT.md](DEVELOPMENT.md) - Local development
- [DATABASE.md](DATABASE.md) - Database configuration
- [../CLAUDE.md](../CLAUDE.md) - Project overview
