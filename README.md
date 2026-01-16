# Multi-Agent Platform

A platform for hosting and orchestrating multiple LangFlow workflows, built on Red Hat technologies. This project experiments with agentic AI patterns that iteratively plan, gather, critique, and synthesize information—mimicking how a human researcher works.

## Vision

Unlike a standard RAG chatbot that retrieves once and answers, Multi-Agent Platform uses a **System of Agents** orchestrated to perform long-horizon tasks:

1. **Planner** decomposes complex queries into sub-questions
2. **Researcher** gathers evidence using search and vector stores
3. **Reviewer** critiques findings for gaps and hallucinations
4. **Writer** synthesizes approved research into cohesive reports

This Supervisor-Worker pattern with reflection loops enables comprehensive, validated research outputs.

## Architecture

```
    ┌───────────┐                                                        
    │           │                                                        
    │   Users   │                                                        
    │           │                                                        
    └─────┬─────┘                                                        
          │                                                              
          │                                                              
          │                                                              
┌─────────┼──────────────────────────┐                    ┌────────────┐ 
│         │                          │                    │            │ 
│         │                          │                    │            │ 
│         │                          │                    │            │ 
│   ┌─────▼────┐   ┌──────────┐      │                    │            │ 
│   │          │   │          │      │                    │ PostgreSQL │ 
│   │ Frontend ┼───► Backend  ┼──────┼────────────────────►            │ 
│   │          │   │          │      │                    │            │ 
│   └──────────┘   └────┬─────┘      │                    │            │ 
│                       │            │                    │            │ 
│                       │            │                    │     ▲      │ 
└───────────────────────┼────────────┘                    └─────┼──────┘ 
                        │                                       │        
                        │                                       │        
                        │                                       │        
      ┌─────────────────┼─────────────────┐                     │        
      │                 │                 │                     │        
┌─────▼─────┐     ┌─────▼─────┐     ┌─────▼─────┐               │        
│           │     │           │     │           │               │        
│           │     │           │     │           │               │        
│ LangFlow  │     │  LangFuse │     │  MLflow   │               │        
│           │     │           │     │           │               │        
│           │     │           │     │           │               │        
└─────┬─────┘     └─────┬─────┘     └─────┬─────┘               │        
      │                 │                 │                     │        
      └─────────────────┴─────────────────┴─────────────────────┘                             

```

**User Flow**: Users interact with the Multi-Agent Platform, which executes LangFlow workflows via API to perform multi-agent research tasks.

**Observability**: Workflow executions send traces to Langfuse (LLM tracing) and MLFlow (experiment tracking) for monitoring and evaluation.

**Shared Database**: All components use PostgreSQL with separate databases for isolation.

**Developer/Admin Tools**: LangFlow, Langfuse, and MLFlow are accessible only to developers and administrators.

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
- OpenShift CLI (`oc`) and Helm 3 (for cluster deployment)

```bash
git clone https://github.com/cfchase/multi-agent-platform
cd multi-agent-platform
make setup

# Configure environment
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

### Authentication Setup

> **Note:** Full functionality (user sessions, document access, personalized research) requires OAuth authentication. See [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md) for complete setup instructions.

**Option A: No Auth (Quick Start)**
```bash
# Edit backend/.env
ENVIRONMENT=local
```
- Uses a default "dev-user" for all requests
- Good for initial exploration and UI development
- Some features requiring user identity won't work

**Option B: Google OAuth (Recommended)**
```bash
# Edit backend/.env with your Google OAuth credentials
ENVIRONMENT=development
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
OAUTH_COOKIE_SECRET=<generate-random-key>
```
- Requires [Google Cloud OAuth setup](docs/AUTHENTICATION.md#google-oauth-setup)
- Enables full user authentication and sessions
- Required for production-like development

### Local Development

```bash
# Start database and run app
make db-start && make db-init
make dev
```

Access locally:
- **App**: http://localhost:8080 (or http://localhost:4180 with OAuth)
- **LangFlow**: http://localhost:7860
- **MLFlow**: http://localhost:5000
- **Langfuse**: http://localhost:3000

**Optional: Run AI services locally**
```bash
./scripts/dev-langflow.sh start
./scripts/dev-langfuse.sh start
./scripts/dev-mlflow.sh start
```

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

```
├── backend/              # FastAPI backend
├── frontend/             # React + PatternFly frontend
├── langflow-flows/       # LangFlow flow definitions and docs
│   ├── docs/            # Flow architecture documentation
│   ├── flows/           # Exported flow JSON files
│   └── prompts/         # Prompt templates
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

The platform supports multiple flows for different use cases:

| Flow | Description | Status |
|------|-------------|--------|
| [Basic Chat](langflow-flows/docs/basic-flow.md) | Simple Q&A with Gemini model | Phase 2A |
| [Analyze](langflow-flows/docs/analyze-flow.md) | Enterprise data analysis (agents-python port) | Phase 3 |
| [Deep Research](langflow-flows/docs/deep-research-flow.md) | Multi-agent research with validation | Future |

See [langflow-flows/README.md](langflow-flows/README.md) for full flow documentation.

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
