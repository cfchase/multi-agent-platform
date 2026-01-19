# Multi-Agent Platform

A platform for hosting and orchestrating multiple LangFlow workflows, built on Red Hat technologies.

## Architecture

```text
         ┌───────┐                             
         │ Users │                             
         └───┬───┘                             
             │                                 
  ┌──────────┼──────────┐        ┌────────────┐
  │    ┌─────▼─────┐    │        │            │
  │    │ Frontend  │    │        │ PostgreSQL │
  │    └─────┬─────┘    │        │            │
  │    ┌─────▼─────┐    │        │     ▲      │
  │    │  Backend  ├────┼────────►     │      │
  │    └─────┬─────┘    │        └─────┼──────┘
  └──────────┼──────────┘              │       
       ┌─────┼─────┐                   │       
       ▼     ▼     ▼                   │       
┌────────┬────────┬────────┐           │       
│LangFlow│Langfuse│ MLflow │───────────┘       
└────────┴────────┴────────┘                   
```

- **Frontend/Backend**: User-facing app for running workflows
- **LangFlow**: Visual workflow builder (developers only)
- **Langfuse/MLflow**: Observability and experiment tracking
- **PostgreSQL**: Shared database for all services

## Components

| Component | Purpose | Access |
|-----------|---------|--------|
| **Multi-Agent Platform** | User-facing UI that executes research workflows | Users |
| **LangFlow** | Visual workflow builder for multi-agent orchestration | Developers/Admins |
| **Langfuse** | LLM observability, tracing, and evaluation | Developers/Admins |
| **MLFlow** | Experiment tracking and model registry | Developers/Admins |
| **PostgreSQL** | Shared database for all services | Internal |

## Quick Start

### Prerequisites

- Docker or Podman
- Node.js 22+ and Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- OpenShift CLI (`oc`) and Helm 3 (for cluster deployment)

### Local Development

```bash
git clone https://github.com/cfchase/multi-agent-platform
cd multi-agent-platform
make setup
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
make services-start
make db-seed  # optional: load sample data
make dev
```

Access locally:

- **App**: <http://localhost:8080>
- **LangFlow**: <http://localhost:7860>
- **MLFlow**: <http://localhost:5000>
- **Langfuse**: <http://localhost:3000>

### Authentication

OAuth is always enabled. Access app at <http://localhost:4180>.

- **No OAuth credentials**: Uses mock OAuth server (any username/password works)
- **With OAuth credentials**: Uses configured provider (Google, GitHub, Keycloak)

Configure OAuth in `backend/.env`:

```bash
OAUTH_CLIENT_ID=your-client-id
OAUTH_CLIENT_SECRET=your-secret
OAUTH_ISSUER_URL=https://...       # Optional: set for OIDC providers (Keycloak, etc.)
```

For setup details, see [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md).

### Deploy to OpenShift

> **Important:** Configure OAuth credentials before deploying. See [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md#openshift-deployment).

```bash
# Login to your cluster
oc login --server=https://your-cluster

# Configure OAuth secret (required)
cp k8s/app/overlays/dev/oauth-proxy-secret.env.example k8s/app/overlays/dev/oauth-proxy-secret.env
# Edit with your OAuth credentials

# Deploy everything
make deploy
```

This deploys PostgreSQL, LangFlow, MLFlow, Langfuse, and the Multi-Agent Platform app.

**Get credentials and URLs:**
```bash
make get-admin-credentials
```

## Deployment Commands

```bash
# Full deployment
make deploy              # Deploy all components
make undeploy            # Remove all components

# Individual components
make deploy-db           # PostgreSQL only
make deploy-app          # Multi-Agent Platform app only
make deploy-langflow     # LangFlow only
make deploy-mlflow       # MLFlow only
make deploy-langfuse     # Langfuse only

# Status and logs
make get-admin-credentials    # Show credentials and URLs
make helm-langflow-status     # LangFlow status
make helm-mlflow-status       # MLFlow status
make helm-langfuse-status     # Langfuse status
```

## Project Structure

```text
├── backend/              # FastAPI backend
├── frontend/             # React + PatternFly frontend
├── langflow-flows/       # LangFlow flow definitions
│   └── examples/        # Example flows included with platform
├── config/              # Configuration templates
│   └── flow-sources.yaml.example  # Flow source configuration
├── k8s/
│   ├── app/             # App deployment (Kustomize)
│   ├── postgres/        # Database deployment (Kustomize)
│   ├── langflow/        # Legacy manifests (reference)
│   └── mlflow/          # Legacy manifests (reference)
├── helm/
│   ├── langflow/        # LangFlow Helm values
│   ├── mlflow/          # MLFlow Helm values
│   └── langfuse/        # Langfuse Helm values
├── scripts/             # Deployment and dev scripts
└── docs/                # Detailed documentation
```

## LangFlow Flows

Flows can be imported from multiple sources (local directories, git repos). See [langflow-flows/README.md](langflow-flows/README.md) for configuration details.

```bash
# Import flows from configured sources
make langflow-import
```

## Documentation

- [DEPLOYMENT.md](docs/DEPLOYMENT.md) - Detailed deployment guide
- [DEVELOPMENT.md](docs/DEVELOPMENT.md) - Local development setup
- [AUTHENTICATION.md](docs/AUTHENTICATION.md) - OAuth2 configuration
- [CLAUDE.md](CLAUDE.md) - AI assistant development guide
- [langflow-flows/](langflow-flows/) - Flow architecture documentation

## Authentication

| Service | Access | Method | Credentials |
|---------|--------|--------|-------------|
| Multi-Agent Platform | Users | OAuth2 (Google/GitHub) | Configure in OAuth provider |
| LangFlow | Developers/Admins | Built-in auth | `admin-credentials` secret |
| MLFlow | Developers/Admins | HTTP Basic | `admin-credentials` secret |
| Langfuse | Developers/Admins | Email/Password | Self-registration |

## Technology Stack

- **Frontend**: React, TypeScript, Vite, PatternFly
- **Backend**: FastAPI, Python, SQLModel, Alembic
- **Database**: PostgreSQL 15
- **Deployment**: OpenShift, Kubernetes, Kustomize, Helm
- **AI/ML**: LangFlow, Langfuse, MLFlow
- **Auth**: OAuth2 Proxy

## License

Apache License 2.0
