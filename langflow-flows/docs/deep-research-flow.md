# Deep Research Flow

## Overview

The Deep Research Flow implements a Supervisor-Worker pattern with reflection loops, designed for comprehensive research tasks. It mimics a human researcher's workflow: breaking complex queries into sub-questions, gathering evidence, validating findings, and synthesizing reports.

**Status:** Future (Post-Phase 3)
**Complexity:** High (Multi-agent with cycles)
**Use Case:** Open-ended research, report generation, web research with validation

---

## Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Deep Research Flow                                   │
│                                                                              │
│                        ┌─────────────────┐                                   │
│                        │   User Query    │                                   │
│                        └────────┬────────┘                                   │
│                                 │                                            │
│                                 ▼                                            │
│                        ┌─────────────────┐                                   │
│                        │   SUPERVISOR    │◄──────────────────────┐           │
│                        │  (Orchestrator) │                       │           │
│                        └────────┬────────┘                       │           │
│                                 │                                │           │
│              ┌──────────────────┼──────────────────┐            │           │
│              │                  │                  │            │           │
│              ▼                  ▼                  ▼            │           │
│     ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │           │
│     │   PLANNER   │    │ RESEARCHER  │    │   WRITER    │       │           │
│     │             │    │             │    │             │       │           │
│     │ Decompose   │    │ Gather      │    │ Synthesize  │       │           │
│     │ Query       │    │ Evidence    │    │ Report      │       │           │
│     └─────────────┘    └──────┬──────┘    └─────────────┘       │           │
│                               │                                  │           │
│                               ▼                                  │           │
│                        ┌─────────────┐                          │           │
│                        │  REVIEWER   │──────────────────────────┘           │
│                        │             │     (If gaps found,                  │
│                        │ Validate &  │      loop back to                    │
│                        │ Critique    │      Supervisor)                     │
│                        └─────────────┘                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## The Supervisor-Worker Pattern

### Why This Pattern?

Unlike the Analyze Flow (which queries existing enterprise data), Deep Research performs **open-ended investigation**:

- Queries are exploratory ("What is the impact of AI on healthcare?")
- Sources are external (web, public databases)
- Quality validation is critical (hallucination risk)
- Iteration is expected (research often requires multiple passes)

### Key Characteristics

| Feature | Description |
|---------|-------------|
| **Cyclic Graph** | Reviewer can loop back to Researcher |
| **Reflection Loop** | Quality gate before final output |
| **Max Iterations** | Prevents infinite loops (default: 3) |
| **State Persistence** | Tracks what's been researched |

---

## Agent Specifications

### Supervisor (Orchestrator)

**Role:** Central coordinator, maintains research state

**Model:** Claude Opus 4.5 or Gemini Pro (high reasoning capability)

**Responsibilities:**
- Receive user query
- Delegate to Planner for decomposition
- Route tasks to Researcher
- Send findings to Reviewer
- Trigger Writer when complete

**System Prompt:**
```
You are a Research Manager. Your goal is to answer the user's question
comprehensively. You have access to Planner, Researcher, Reviewer, and
Writer tools.

DO NOT answer from your own knowledge.

Workflow:
1. Call Planner to break down the query
2. Call Researcher for each sub-question
3. Call Reviewer to validate findings
4. If Reviewer finds gaps, call Researcher again
5. When all validated, call Writer for final report
```

### Planner

**Role:** Query decomposition

**Model:** Claude 3.5 Sonnet or Gemini Flash (fast, efficient)

**Input:** User query
**Output:** List of 3-7 sub-questions

**Example:**
```
Query: "Impact of AI on healthcare stocks"

Sub-questions:
1. "What AI technologies are being adopted in healthcare?"
2. "Which healthcare companies are investing heavily in AI?"
3. "What are recent AI healthcare stock performance trends?"
4. "What regulatory changes affect AI in healthcare?"
5. "What are analyst predictions for AI healthcare sector?"
```

### Researcher

**Role:** Evidence gathering

**Model:** Claude 3.5 Sonnet or Gemini Pro

**Tools:**
- **Web Search** (Tavily/Serper): Find relevant sources
- **URL Reader**: Extract content from web pages
- **Vector Store** (optional): Search curated document collections

**Output:** Draft findings with source citations

### Reviewer

**Role:** Quality assurance and gap analysis

**Model:** Claude 3.5 Sonnet (critical reasoning)

**Responsibilities:**
- Validate findings against sub-questions
- Check for hallucinations
- Identify coverage gaps
- Rate quality (1-5 scale)

**Decision Logic:**
```
IF quality_score >= 4 AND no_critical_gaps:
    RETURN "APPROVED"
ELSE:
    RETURN "NEEDS_WORK" + specific_feedback
```

### Writer

**Role:** Report synthesis

**Model:** Claude Opus 4.5 (high-quality writing)

**Input:** All approved findings with citations
**Output:** Comprehensive markdown report

**Report Structure:**
1. Executive Summary
2. Key Findings (per sub-question)
3. Analysis & Insights
4. Conclusions
5. Sources

---

## Reflection Loop

The Reviewer creates a feedback cycle that ensures quality:

```
┌─────────────────────────────────────────────────────────────┐
│                    Reflection Loop                           │
│                                                              │
│   ┌──────────────┐                                          │
│   │  Researcher  │                                          │
│   │   Output     │                                          │
│   └──────┬───────┘                                          │
│          │                                                   │
│          ▼                                                   │
│   ┌──────────────┐     ┌──────────────────────────────┐     │
│   │   Reviewer   │────►│  Quality Check                │     │
│   └──────┬───────┘     │  - Coverage complete?         │     │
│          │             │  - Sources credible?          │     │
│          │             │  - No hallucinations?         │     │
│          │             │  - Depth sufficient?          │     │
│          │             └──────────────────────────────┘     │
│          │                                                   │
│          ▼                                                   │
│   ┌──────────────────────────────────────────────────┐      │
│   │  Decision                                         │      │
│   │                                                   │      │
│   │  APPROVED (score ≥ 4):                           │      │
│   │    → Continue to Writer                           │      │
│   │                                                   │      │
│   │  NEEDS_WORK (score < 4):                         │      │
│   │    → Return feedback to Supervisor                │      │
│   │    → Supervisor re-routes to Researcher           │      │
│   │    → Max 3 iterations                             │      │
│   └──────────────────────────────────────────────────┘      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## LangFlow Implementation

### Tool Mode Configuration

Each worker agent is wrapped in **Tool Mode** so the Supervisor can invoke it:

```
┌─────────────────────────────────────┐
│ Researcher Agent                     │
│ Tool Mode: ENABLED                   │
│                                      │
│ System Prompt:                       │
│ "You are a research specialist.     │
│  Use web search and URL reader to   │
│  find evidence for the given        │
│  question. Cite all sources."       │
│                                      │
│ Tools:                               │
│ ├── Tavily Search                    │
│ └── URL Reader                       │
└─────────────────────────────────────┘
```

### Supervisor Tool Connections

```
┌─────────────────────────────────────┐
│ Supervisor Agent                     │
│                                      │
│ Tools Input:                         │
│ ├── Planner Agent (Tool Mode)        │
│ ├── Researcher Agent (Tool Mode)     │
│ ├── Reviewer Agent (Tool Mode)       │
│ └── Writer Agent (Tool Mode)         │
└─────────────────────────────────────┘
```

### State Management

The flow uses **LangGraph** under the hood for state persistence:

```python
# Conceptual state structure
state = {
    "query": "User's original question",
    "plan": ["sub-q1", "sub-q2", "sub-q3"],
    "researched": {
        "sub-q1": {"findings": "...", "sources": [...], "approved": True},
        "sub-q2": {"findings": "...", "sources": [...], "approved": False},
    },
    "iteration_count": 2,
    "max_iterations": 3
}
```

---

## Observability

### Langfuse Trace Structure

```
Trace: deep-research-{session_id}
  ├─ Span: supervisor
  │    ├─ Generation: supervisor-reasoning
  │    └─ Tool Call: planner
  ├─ Span: planner
  │    └─ Generation: query-decomposition
  ├─ Span: researcher (iteration 1)
  │    ├─ Tool Call: tavily-search
  │    ├─ Tool Call: url-reader
  │    └─ Generation: findings-synthesis
  ├─ Span: reviewer (iteration 1)
  │    └─ Generation: quality-assessment
  │         └─ Score: research_quality = 3 (NEEDS_WORK)
  ├─ Span: researcher (iteration 2)  ←── Loop back
  │    └─ ...
  ├─ Span: reviewer (iteration 2)
  │    └─ Score: research_quality = 5 (APPROVED)
  └─ Span: writer
       └─ Generation: final-report
```

### Custom Quality Scoring

Add a **Custom Component** to log Reviewer scores to Langfuse:

```python
from langflow.custom import Component
from langfuse import Langfuse

class LangfuseScore(Component):
    display_name = "Log Quality Score"

    def execute(self):
        langfuse = Langfuse()
        langfuse.score(
            name="research_quality",
            value=self.score,
            comment=self.feedback
        )
        return {"status": "scored", "value": self.score}
```

---

## Configuration

### Environment Variables

```bash
# LLM Providers
ANTHROPIC_API_KEY=<claude-key>
GOOGLE_API_KEY=<gemini-key>

# Search Tools
TAVILY_API_KEY=<tavily-key>

# Observability
LANGFUSE_PUBLIC_KEY=<key>
LANGFUSE_SECRET_KEY=<secret>

# Flow Limits
MAX_RESEARCH_ITERATIONS=3
MAX_TOKENS_PER_AGENT=4096
```

### Model Recommendations

| Agent | Recommended Model | Fallback |
|-------|-------------------|----------|
| Supervisor | Claude Opus 4.5 | Gemini Pro |
| Planner | Gemini Flash | Claude Haiku |
| Researcher | Claude Sonnet | Gemini Pro |
| Reviewer | Claude Sonnet | Gemini Pro |
| Writer | Claude Opus 4.5 | Gemini Pro |

---

## Differences from Other Flows

| Aspect | Basic Flow | Analyze Flow | Deep Research Flow |
|--------|------------|--------------|-------------------|
| Agents | 1 (LLM only) | 3+ (departments) | 5 (specialized roles) |
| Data Source | None | Enterprise data | Web + documents |
| Validation | None | Citation mapping | Reviewer feedback loop |
| Iteration | None | None | Up to 3 cycles |
| Output | Chat response | Answer + citations | Full report |

---

## When to Use

**Good for:**
- Open-ended research questions
- Report generation requiring multiple sources
- Topics requiring validation and fact-checking
- Exploratory analysis with unknown scope

**Not suitable for:**
- Simple Q&A (use Basic Flow)
- Enterprise data queries (use Analyze Flow)
- Real-time responses (iteration adds latency)
- Highly structured/predictable queries

---

## Production Considerations

1. **Loop Limits**: Set `max_iterations=3` to prevent runaway research
2. **Token Budgets**: Monitor per-agent token usage
3. **Timeout Handling**: Web searches can be slow; add timeouts
4. **Source Credibility**: Consider adding source reputation scoring
5. **Cost Management**: Opus models are expensive; use for synthesis only
