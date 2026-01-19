# Multi-Agent Platform - System Architecture

## Overview

Multi-Agent Platform is a hosted platform for orchestrating LangFlow workflows that provides AI-powered comprehensive research capabilities through a conversational interface. The system integrates:

- **LangFlow**: Visual agent orchestration layer
- **Langfuse**: LLM tracing and observability
- **MLFlow**: Experiment tracking and model versioning
- **FastAPI + React**: Full-stack web application

Users submit research queries through a chat interface, and the system executes a multi-agent workflow to gather, analyze, and synthesize information into comprehensive research reports.

---

## System Architecture Diagram

```
+-----------------------------------------------------------------------------------+
|                              OPENSHIFT/KUBERNETES                                  |
|  +-------------------------------------------------------------------------------+ |
|  |                    INGRESS / ROUTE (OAuth2 Proxy)                             | |
|  +-------------------------------------------------------------------------------+ |
|        |                    |                    |                    |            |
|        v                    v                    v                    v            |
|  +----------------+   +----------------+   +----------------+   +----------------+ |
|  |   FRONTEND     |   |   BACKEND      |   |   LANGFLOW     |   | OBSERVABILITY  | |
|  |   React/PF     |   |   FastAPI      |   |   Orchestrator |   | Langfuse:3000  | |
|  |   :8080        |   |   :8000        |   |   :7860        |   | MLFlow:5000    | |
|  +----------------+   +----------------+   +----------------+   +----------------+ |
|        |                    |                    |                    |            |
|        +--------------------+--------------------+--------------------+            |
|                             |                                                      |
|                             v                                                      |
|  +-------------------------------------------------------------------------------+ |
|  |                 POSTGRESQL DATABASES                                          | |
|  |              app | langflow | langfuse | mlflow                               | |
|  +-------------------------------------------------------------------------------+ |
+-----------------------------------------------------------------------------------+
```

---

## Component Details

### Frontend (React + PatternFly)

**Purpose**: Chat-based research interface for users

**Key Features**:
- Conversational UI for submitting research queries
- Real-time streaming of agent progress via SSE
- Markdown rendering for research reports
- Session history and report library

**Technology Stack**:
- React 18 with TypeScript
- PatternFly v6 UI components
- Vite build tooling
- Server-Sent Events (SSE) for streaming

### Backend (FastAPI)

**Purpose**: API layer and orchestration coordinator

**Key Features**:
- Research session management (CRUD)
- LangFlow API proxy with authentication
- SSE streaming endpoints for real-time updates
- Langfuse/MLFlow integration for observability

**Technology Stack**:
- FastAPI with async support
- SQLModel ORM with PostgreSQL
- SSE via sse-starlette
- Strawberry GraphQL

### LangFlow (Agent Orchestration)

**Purpose**: Visual workflow engine for multi-agent research

**Key Features**:
- Pre-configured deep research flow
- 5-agent supervisor-worker pattern
- Built-in Langfuse integration for tracing
- Streaming response support

**Technology Stack**:
- LangFlow 1.7+
- LangGraph state machine
- Multiple LLM providers (Claude, GPT-4)

### Observability Stack

**Langfuse** (LLM Tracing):
- Trace all LLM calls and agent interactions
- Evaluate response quality
- Debug agent workflows
- Cost tracking

**MLFlow** (Experiment Tracking):
- Track research query parameters
- Log agent performance metrics
- Version flow configurations
- Compare research run outcomes

---

## Agent Architecture (Supervisor-Worker Pattern)

The deep research workflow uses a supervisor-worker pattern with 5 specialized agents:

```
User Query --> [SUPERVISOR] --> [PLANNER] --> [SOURCE FINDER] --> [SUMMARIZER]
                    |                                                    |
                    +<------------- [REVIEWER] <-------------------------+
                    |
                    v
              [RESEARCH WRITER] --> Final Report
```

### Agent Specifications

| Agent | Model | Role | Input | Output |
|-------|-------|------|-------|--------|
| **Supervisor** | Claude Opus 4 | Orchestrates workflow | User query | Task delegation |
| **Planner** | Claude 3.5 Sonnet | Decomposes query | Query | Sub-questions (3-7) |
| **Source Finder** | Claude 3.5 Sonnet | Gathers sources |  Sub-question | URLs, snippets |
| **Summarizer** | Claude 3.5 Haiku | Extracts facts | Source content | Key facts, claims |
| **Reviewer** | Claude 3.5 Sonnet | Validates & identifies gaps | All facts | Gaps, recommendations |
| **Writer** | Claude Opus 4 | Synthesizes report | Facts, sources | Markdown report |

### Workflow States

1. **Planning**: Supervisor delegates to Planner to break down the query
2. **Gathering**: Source Finder searches for relevant information
3. **Analyzing**: Summarizer extracts key facts from sources
4. **Reviewing**: Reviewer validates findings and identifies gaps
5. **Iterating**: If gaps exist, loop back to Gathering (max 3 iterations)
6. **Writing**: Writer synthesizes final comprehensive report

---

## Data Flow

### Research Query Flow

```
[User]
   |
   | POST /api/v1/research/sessions/{id}/query
   v
[FastAPI Backend]
   |
   | 1. Create message record
   | 2. Start Langfuse trace
   | 3. Start MLFlow run
   |
   | POST /api/v1/run/{flow_id}?stream=true
   v
[LangFlow]
   |
   | Execute research flow
   | Stream agent events
   |
   | SSE events (message, progress, report)
   v
[FastAPI Backend]
   |
   | 1. Parse events
   | 2. Store messages
   | 3. Log to Langfuse/MLFlow
   |
   | SSE stream
   v
[Frontend]
   |
   | Display messages, progress, report
   v
[User]
```

### Event Types

| Event | Description | Payload |
|-------|-------------|---------|
| `message` | Agent chat message | `{role, content, agentName}` |
| `progress` | Agent status update | `{agent, status}` |
| `report` | Report chunk (streaming) | `{chunk}` |
| `complete` | Research finished | `{sessionId}` |
| `error` | Error occurred | `{error}` |

---

## Database Schema

### Core Tables

**research_sessions**
```sql
id              UUID PRIMARY KEY
title           VARCHAR(255)
status          ENUM('pending', 'in_progress', 'completed', 'failed', 'cancelled')
owner_id        UUID REFERENCES users(id)
langflow_run_id VARCHAR(255)
langfuse_trace_id VARCHAR(255)
mlflow_run_id   VARCHAR(255)
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

**research_messages**
```sql
id              UUID PRIMARY KEY
session_id      UUID REFERENCES research_sessions(id)
role            ENUM('user', 'assistant', 'system', 'agent')
content         TEXT
agent_name      VARCHAR(255)
token_count     INTEGER
latency_ms      INTEGER
created_at      TIMESTAMP
```

**research_reports**
```sql
id              UUID PRIMARY KEY
session_id      UUID REFERENCES research_sessions(id)
title           VARCHAR(255)
content_markdown TEXT
content_html    TEXT
sources         JSONB
created_at      TIMESTAMP
```

---

## Infrastructure

### Container Architecture

| Container | Image | Port | Resources |
|-----------|-------|------|-----------|
| frontend | app-frontend | 8080 | 256Mi / 200m |
| backend | app-backend | 8000 | 512Mi / 500m |
| langflow | langflowai/langflow:1.7.1 | 7860 | 2Gi / 1000m |
| langfuse | langfuse/langfuse:latest | 3000 | 1Gi / 500m |
| mlflow | ghcr.io/mlflow/mlflow:v2.16.0 | 5000 | 1Gi / 500m |
| postgres | postgres:15-alpine | 5432 | 512Mi / 500m |

### Databases

| Database | Purpose | Size Estimate |
|----------|---------|---------------|
| app | Application data (sessions, messages, reports) | 10Gi |
| langflow | Flow definitions, run history | 5Gi |
| langfuse | Traces, evaluations | 20Gi |
| mlflow | Experiments, metrics | 5Gi |

### Persistent Volumes

| PVC | Purpose | Size |
|-----|---------|------|
| langflow-flows-pvc | Flow JSON definitions | 1Gi |
| mlflow-artifacts-pvc | Experiment artifacts | 10Gi |

---

## Security

### Authentication

The platform uses OAuth2 Proxy as the authentication gateway for all external traffic.

**Architecture:**

```text
Users → OAuth2 Proxy (4180) → Frontend (8080) → Backend (8000)
              │
              └── Authenticates with:
                  - Mock OAuth server (local development)
                  - Google OAuth (default production provider)
                  - OIDC providers (Keycloak, Okta, etc.)
```

**Local Development:**

- **Mock OAuth Server**: Uses [mock-oauth2-server](https://github.com/navikt/mock-oauth2-server) for local development
- Starts automatically when no real OAuth credentials are configured
- Login with any username/password (credentials are not validated)
- Full OAuth flow with proper user headers

**Production:**

- **OAuth2 Proxy**: Runs as a sidecar container, authenticating all requests
- **Provider Support**: Google (default), GitHub, Keycloak, or any OIDC provider
- **User Headers**: Sets `X-Forwarded-User`, `X-Forwarded-Email` for downstream services

**Internal Communication:**

- **Service Accounts**: Internal services communicate via K8s service accounts
- **API Keys**: LangFlow API protected by API key stored in K8s secret

### Authorization

- Research sessions scoped to user ownership
- Reports accessible only to session owner
- Admin users can view all sessions (for debugging)

### Secrets Management

| Secret | Contents |
|--------|----------|
| postgres-secret | Database credentials |
| langflow-secret | API key, cookie secret |
| langfuse-secret | Public/secret keys |
| mlflow-secret | Backend store credentials |
| oauth-proxy-secret | OAuth client credentials |

---

## Configuration

### Environment Variables

```bash
# LangFlow
LANGFLOW_URL=http://langflow:7860
LANGFLOW_API_KEY=<secret>
RESEARCH_FLOW_ID=<flow-uuid>

# Langfuse
LANGFUSE_PUBLIC_KEY=<key>
LANGFUSE_SECRET_KEY=<secret>
LANGFUSE_HOST=http://langfuse:3000

# MLFlow
MLFLOW_TRACKING_URI=http://mlflow:5000
MLFLOW_EXPERIMENT_NAME=app

# LLM Providers (configured in LangFlow)
ANTHROPIC_API_KEY=<secret>
OPENAI_API_KEY=<secret>
```

---

## Scalability Considerations

### Horizontal Scaling

- **Frontend/Backend**: Stateless, can scale horizontally
- **LangFlow**: Stateless workers, scale based on concurrent research jobs
- **PostgreSQL**: Consider managed service (RDS, CloudSQL) for production

### Performance Optimization

- SSE connection pooling
- LangFlow flow caching
- Report content caching
- Database connection pooling

### Rate Limiting

- Research queries: 10/minute per user
- Concurrent sessions: 3 per user
- Report generation: 100/hour per user

---

## Monitoring

### Metrics

- Research session success/failure rates
- Average research completion time
- Agent latency per step
- LLM token usage and costs
- Error rates by agent

### Dashboards

- **Langfuse**: LLM traces, evaluations, cost tracking
- **MLFlow**: Experiment comparison, model versioning
- **Grafana** (optional): Infrastructure metrics, custom dashboards
