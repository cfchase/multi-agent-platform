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
k8s/
├── base/                           # Base resources (app deployment)
│   ├── kustomization.yaml          # Main kustomization
│   ├── deployment.yaml             # Combined app pod (frontend+backend+oauth-proxy)
│   ├── service.yaml                # Service exposing the app
│   ├── route.yaml                  # OpenShift route
│   ├── serviceaccount.yaml         # Service account for OAuth proxy
│   └── oauth2-proxy-config.yaml    # OAuth2 proxy configuration
├── overlays/
│   ├── dev/                        # Development environment
│   │   ├── kustomization.yaml      # Dev overlay (includes in-cluster postgres)
│   │   ├── deployment-patch.yaml   # Dev-specific patches
│   │   ├── oauth-proxy.env         # OAuth config (non-secret)
│   │   └── oauth-proxy-secret.env  # OAuth secrets (gitignored)
│   └── prod/                       # Production environment
│       ├── kustomization.yaml      # Prod overlay
│       ├── deployment-patch.yaml   # Prod-specific patches
│       └── oauth-proxy-secret.env  # OAuth secrets (gitignored)
└── postgres/
    └── database/
        ├── base/                   # Base postgres kustomization
        └── in-cluster/             # In-cluster PostgreSQL deployment
            ├── kustomization.yaml
            ├── postgres-deployment.yaml
            ├── postgres-pvc.yaml
            ├── postgres-secret.yaml
            └── postgres-service.yaml
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
│                           App Pod                                 │
│  ┌────────────────┐                                              │
│  │  OAuth2 Proxy  │◄── All external requests enter here         │
│  │  (Port 4180)   │                                              │
│  │                │    - Authenticates users                     │
│  │  ENTRY POINT   │    - Sets X-Forwarded-User headers           │
│  └───────┬────────┘    - Redirects to OAuth provider             │
│          │                                                        │
│          ▼                                                        │
│  ┌────────────────┐                                              │
│  │    Frontend    │    - Serves React static files               │
│  │  (Port 8080)   │    - Proxies /api/* to backend               │
│  │                │                                              │
│  │  Nginx Proxy   │                                              │
│  └───────┬────────┘                                              │
│          │                                                        │
│          ▼                                                        │
│  ┌────────────────┐                                              │
│  │    Backend     │    - FastAPI application                     │
│  │  (Port 8000)   │    - GraphQL + REST APIs                     │
│  │                │    - Admin panel                             │
│  │ INTERNAL ONLY  │◄── Cluster-internal, NOT directly exposed   │
│  └────────────────┘                                              │
│                                                                   │
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

**CRITICAL**: Before deploying, you must create the OAuth2 proxy secret file.

1. **Copy the example file:**
   ```bash
   # For development
   cp k8s/overlays/dev/oauth-proxy-secret.env.example k8s/overlays/dev/oauth-proxy-secret.env

   # For production
   cp k8s/overlays/prod/oauth-proxy-secret.env.example k8s/overlays/prod/oauth-proxy-secret.env
   ```

2. **Generate a cookie secret:**
   ```bash
   openssl rand -base64 32 | tr -- '+/' '-_'
   ```

3. **Edit the secret file with your OAuth provider credentials:**
   ```bash
   # oauth-proxy-secret.env
   client-id=your-oauth-client-id
   client-secret=your-oauth-client-secret
   cookie-secret=<generated-cookie-secret>
   ```

4. **The secret file is gitignored** - never commit OAuth secrets!

See [AUTHENTICATION.md](AUTHENTICATION.md) for OAuth provider configuration details.

### Deploying

```bash
# Preview manifests
make kustomize       # Dev environment
make kustomize-prod  # Prod environment

# Apply to cluster
make deploy          # Dev environment
make deploy-prod     # Prod environment

# Remove deployment
make undeploy
make undeploy-prod
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
