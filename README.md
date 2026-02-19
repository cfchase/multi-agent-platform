# Multi-Agent Platform

A platform for hosting and orchestrating multiple LangFlow workflows, built on Red Hat technologies.

## Architecture

```text
         ┌───────┐                             
         │ Users │                             
         └───┬───┘                             
             │                                 
  ┌──────────┼──────────┐                      
  │  ┌───────▼───────┐  │                      
  │  │ OAuth2 Proxy  │  │                      
  │  └───────┬───────┘  │                      
  │  ┌───────▼───────┐  │        ┌────────────┐
  │  │   Frontend    │  │        │            │
  │  └───────┬───────┘  │        │ PostgreSQL │
  │  ┌───────▼───────┐  │        │            │
  │  │    Backend    ┼──┼────────►            │
  │  └───────┬───────┘  │        └─────▲──────┘
  └──────────┼──────────┘              │       
       ┌─────┼─────┐                   │       
       ▼     ▼     ▼                   │       
┌────────┬────────┬────────┐           │       
│LangFlow│Langfuse│ MLflow │───────────┘       
└────────┴────────┴────────┘                   
```

- **OAuth2 Proxy**: Authentication gateway (mock server for local dev)
- **Frontend/Backend**: User-facing app for running workflows
- **LangFlow**: Visual workflow builder (developers only)
- **Langfuse/MLflow**: Observability and experiment tracking
- **PostgreSQL**: Shared database for all services

## Components

| Component | Purpose | Access |
|-----------|---------|--------|
| **OAuth2 Proxy** | Authentication gateway (uses mock server locally) | Entry point |
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
make config-setup           # Copy config from config/local/
make services-start
make db-seed  # optional: load sample data
make dev
```

Access locally:

- **App**: <http://localhost:4180> (via OAuth proxy)
- **LangFlow**: <http://localhost:7860>
- **MLFlow**: <http://localhost:5000>
- **Langfuse**: <http://localhost:3000>

### Authentication

OAuth is enabled by default. Access app at <http://localhost:4180>.

- **No OAuth credentials**: Uses mock OAuth server (any username/password works)
- **With OAuth credentials**: Uses configured provider (Google, GitHub, Keycloak)

Configure OAuth in `config/local/.env` (local) or `config/dev/.env` (cluster):

```bash
OAUTH_CLIENT_ID=your-client-id
OAUTH_CLIENT_SECRET=your-secret
OAUTH_ISSUER_URL=https://...       # Optional: set for OIDC providers (Keycloak, etc.)
```

For setup details, see [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md).

### Deploy to OpenShift

> **Prerequisites:** OpenShift CLI (`oc`), Helm 3, and valid cluster login.
> Configure Google OAuth credentials before deploying. See [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md).

```bash
# 1. Login to your cluster
oc login --server=https://your-cluster

# 2. Set up deployment config (creates config/dev/ files)
make config-setup-cluster

# 3. Configure credentials (required)
#    Edit config/dev/.env with OAuth, LLM keys, etc.
#    Edit config/dev/allowed-emails.txt with authorized email addresses
#    Edit config/dev/namespace-admins.txt with OpenShift usernames for admin access

# 4. Generate deployment artifacts and deploy
make config-generate
make deploy

# 5. Verify deployment
make verify-deploy
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

# Verification
make verify-deploy       # Check deployment health

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

## Service Credentials

| Service | Access | Method | Credentials |
|---------|--------|--------|-------------|
| Multi-Agent Platform | Users | Google OAuth | Configured OAuth provider |
| LangFlow | Admins | OpenShift OAuth | OpenShift cluster credentials |
| MLFlow | Admins | OpenShift OAuth | OpenShift cluster credentials |
| Langfuse | Admins | Built-in auth | `admin-credentials` secret (`make get-admin-credentials`) |

## Technology Stack

- **Frontend**: React, TypeScript, Vite, PatternFly
- **Backend**: FastAPI, Python, SQLModel, Alembic
- **Database**: PostgreSQL 15
- **Deployment**: OpenShift, Kubernetes, Kustomize, Helm
- **AI/ML**: LangFlow, Langfuse, MLFlow
- **Auth**: OAuth2 Proxy

## License

Apache License 2.0
