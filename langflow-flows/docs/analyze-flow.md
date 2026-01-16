# Analyze Flow

## Overview

The Analyze Flow is a port of the [agents-python Analyze app](https://gitlab.com/redhat/clt/agents-python) to LangFlow. It replicates the three-phase orchestration pattern (Plan → Execute → Synthesize) for enterprise data analysis across departments.

**Status:** Phase 3
**Complexity:** High (Multi-agent orchestration)
**Use Case:** Enterprise data analysis, cross-departmental queries, business intelligence

---

## Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Analyze Flow                                      │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                         PLAN PHASE                                    │  │
│   │   ┌─────────────┐    ┌─────────────────────┐                         │  │
│   │   │ User Query  │───►│  Agentic Planner    │                         │  │
│   │   └─────────────┘    │  (Capability Select)│                         │  │
│   │                      └──────────┬──────────┘                         │  │
│   └─────────────────────────────────┼────────────────────────────────────┘  │
│                                     │                                        │
│   ┌─────────────────────────────────▼────────────────────────────────────┐  │
│   │                       EXECUTE PHASE                                   │  │
│   │   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐               │  │
│   │   │ Department  │   │ Dataverse   │   │  External   │               │  │
│   │   │   Agents    │   │   Marts     │   │   Tools     │               │  │
│   │   │ (Documents) │   │   (SQL)     │   │ (Web/APIs)  │               │  │
│   │   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘               │  │
│   │          └─────────────────┼─────────────────┘                       │  │
│   └────────────────────────────┼─────────────────────────────────────────┘  │
│                                │                                             │
│   ┌────────────────────────────▼─────────────────────────────────────────┐  │
│   │                      SYNTHESIZE PHASE                                 │  │
│   │   ┌──────────────────┐    ┌──────────────────┐                       │  │
│   │   │    Synthesizer   │───►│  Citation Filter │───► Final Response   │  │
│   │   │ (Combine Results)│    │ (Source Mapping) │                       │  │
│   │   └──────────────────┘    └──────────────────┘                       │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Three-Phase Orchestration

### Phase 1: Planning (AgenticPlanner)

The Planner analyzes the user query and determines which capabilities to invoke.

**Capabilities:**
- **Departments**: Document search within organizational units (Finance, Legal, Engineering, etc.)
- **Dataverse Marts**: SQL queries against structured data sources
- **External Tools**: Web search, URL fetching, API calls

**Two-Stage Selection:**
1. **Stage 1**: Determine which capabilities are relevant
2. **Stage 2**: Generate optimized sub-questions for each capability

```
User Query: "What were Q3 sales and any legal issues with the Johnson contract?"

Planner Output:
├── Finance Department → "Q3 sales figures and trends"
├── Legal Department → "Johnson contract issues and status"
└── Dataverse: Sales Mart → "SELECT revenue FROM sales WHERE quarter='Q3'"
```

### Phase 2: Execution (Parallel Workers)

Capabilities execute in bounded parallelism:

| Capability Type | Parallelism | Semaphore |
|-----------------|-------------|-----------|
| Departments | Full parallel | None |
| Dataverse Marts | Bounded | 3 concurrent |
| External Tools | Full parallel | None |

Each capability returns:
- Result content
- Citations (source, URL, snippet)
- Confidence score

### Phase 3: Synthesis

The Synthesizer combines results with proper citation management:

1. **Pre-merge citations**: Assign sequential IDs before AI generation
2. **Classify sources**:
   - **Data**: Raw query results (never consolidated)
   - **Primary**: Top document sources
   - **Supporting**: Additional context
3. **Generate response**: Combine findings with citations
4. **Filter citations**: Only include sources actually referenced

---

## Agent Specifications

| Agent | Model | Role | Tools |
|-------|-------|------|-------|
| **Supervisor** | Gemini 2.5 Flash | Orchestrates pipeline | Planner, Executor, Synthesizer |
| **Planner** | Gemini 2.5 Flash | Capability selection | MCP Discovery |
| **Department Agent** | Gemini 2.5 Pro | Document search | Vector Store Retriever |
| **Dataverse Agent** | Gemini 2.5 Flash | SQL generation | SQL Executor |
| **Synthesizer** | Claude Opus 4.5 | Response generation | Citation Mapper |

### Model Selection Rationale

- **Fast models (Gemini Flash)**: Planning, routing, SQL generation
- **Capable models (Gemini Pro, Claude Opus)**: Document understanding, synthesis

---

## Data Isolation Pattern

Each department has isolated data access:

```
┌─────────────────────────────────────────────────────────────┐
│                    Department Vector Stores                  │
│                                                              │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐       │
│   │   Finance   │   │    Legal    │   │ Engineering │       │
│   │  Documents  │   │  Documents  │   │  Documents  │       │
│   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘       │
│          │                 │                 │               │
│   ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐       │
│   │  Finance    │   │   Legal     │   │ Engineering │       │
│   │   Agent     │   │   Agent     │   │   Agent     │       │
│   └─────────────┘   └─────────────┘   └─────────────┘       │
│                                                              │
│   ⚠️ Agents ONLY access their department's data             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Citation Management

### Citation Flow

```
Department Agent Returns:
  "Revenue was $5B [1]"
  Citations: [{id: 1, source: "Q3 Report", url: "..."}]
           │
           ▼
Pre-Merge (before synthesis):
  Assign global IDs: [1] → [3] (if previous agents used 1-2)
  Remap text: "Revenue was $5B [3]"
           │
           ▼
Synthesizer Output:
  "Based on Q3 data, revenue reached $5B [3]..."
  Sources: [{id: 3, source: "Q3 Report", type: "Primary"}]
           │
           ▼
Citation Filter:
  Remove unreferenced sources
  Final output with clean citation list
```

### Citation Types

| Type | Description | Consolidation |
|------|-------------|---------------|
| **Data** | Raw SQL/query results | Never consolidated |
| **Primary** | Main document sources | Consolidated to best |
| **Supporting** | Additional context | Passed through |

---

## LangFlow Implementation

### Building Department Agents

1. Create an **Agent Component** for each department
2. Attach department-specific **Vector Store Retriever**
3. Enable **Tool Mode** to make callable by Supervisor

```
┌─────────────────────────────────────┐
│ Finance Agent (Tool Mode: ON)        │
│                                      │
│ System Prompt:                       │
│ "You are the Finance department     │
│  expert. Search documents to answer │
│  questions about financial data."   │
│                                      │
│ Tools:                               │
│ ├── Finance Vector Store Retriever  │
│ └── Calculator                       │
└─────────────────────────────────────┘
```

### Building the Supervisor

```
┌─────────────────────────────────────┐
│ Supervisor Agent                     │
│                                      │
│ System Prompt:                       │
│ "You are an analyst orchestrator.   │
│  Break queries into department      │
│  tasks. Call the appropriate        │
│  department agents. Synthesize      │
│  results with citations."           │
│                                      │
│ Tools (other agents in Tool Mode):  │
│ ├── Finance Agent                    │
│ ├── Legal Agent                      │
│ ├── Engineering Agent                │
│ └── External Search                  │
└─────────────────────────────────────┘
```

---

## Observability

### Langfuse Trace Hierarchy

```
Trace: analyze-query-{session_id}
  ├─ Span: planner:root
  │    └─ Generation: llm:planner
  ├─ Span: executor
  │    ├─ Span: department:finance
  │    │    └─ Generation: llm:finance-agent
  │    ├─ Span: department:legal
  │    │    └─ Generation: llm:legal-agent
  │    └─ Span: dataverse:sales
  │         └─ Generation: sql-generator
  └─ Span: synthesizer
       ├─ Generation: llm:synthesizer
       └─ Span: citation-filter
```

### Key Metrics

| Metric | Description |
|--------|-------------|
| Total latency | End-to-end query time |
| Planning time | Time to select capabilities |
| Execution time (per agent) | Time for each department |
| Synthesis time | Time to combine results |
| Token usage (per model) | Cost tracking |

---

## Configuration

### Environment Variables

```bash
# LLM Providers
GOOGLE_API_KEY=<gemini-key>
ANTHROPIC_API_KEY=<claude-key>

# Vector Stores (per department)
FINANCE_VECTORSTORE_URL=<url>
LEGAL_VECTORSTORE_URL=<url>

# External Tools
TAVILY_API_KEY=<search-key>

# Observability
LANGFUSE_PUBLIC_KEY=<key>
LANGFUSE_SECRET_KEY=<secret>
```

---

## Migration from agents-python

| agents-python Component | LangFlow Implementation |
|-------------------------|-------------------------|
| CLI interface (`./analyze`) | FastAPI REST + Chat UI |
| Department agents | LangFlow Agent Components (Tool Mode) |
| Claude Opus orchestrator | Supervisor agent with Gemini |
| Depth-first delegation | Sequential flow with conditional routing |
| Dataverse/Snowflake connectors | Custom Tool components |
| LiteLLM | LangFlow multi-model support |
| Langfuse decorators | Native LangFlow-Langfuse integration |

---

## Limitations

- **Cold start**: First query initializes all agent contexts
- **Token limits**: Large cross-department queries may exceed context
- **Latency**: Multi-agent orchestration adds overhead vs. single model

---

## When to Use

**Good for:**
- Cross-departmental business queries
- Queries requiring both documents and structured data
- Audit trails with full citation tracking
- Enterprise compliance requirements

**Not suitable for:**
- Simple Q&A (use Basic Flow)
- Pure research without enterprise data (use Deep Research Flow)
- Real-time low-latency requirements
