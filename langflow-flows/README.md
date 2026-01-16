# LangFlow Flows

This directory contains LangFlow flow definitions and documentation for the Deep Research platform.

## Available Flows

| Flow | Status | Complexity | Use Case |
|------|--------|------------|----------|
| [Basic Chat](docs/basic-flow.md) | Phase 2A | Minimal | Simple Q&A, testing |
| [Analyze](docs/analyze-flow.md) | Phase 3 | High | Enterprise data analysis |
| [Deep Research](docs/deep-research-flow.md) | Future | High | Open-ended research with validation |

## Directory Structure

```
langflow-flows/
├── README.md                 # This file
├── docs/                     # Flow architecture documentation
│   ├── basic-flow.md        # Basic Chat flow design
│   ├── analyze-flow.md      # Analyze flow (agents-python port)
│   └── deep-research-flow.md # Deep Research flow design
├── flows/                    # Exported flow JSON files (Phase 2A+)
│   ├── hello-gemini.json    # Basic Chat flow
│   ├── analyze-v1.json      # Analyze flow
│   └── deep-research-v1.json # Deep Research flow
└── prompts/                  # Prompt templates (Phase 3+)
    ├── analyze/             # Analyze flow prompts
    └── deep-research/       # Deep Research flow prompts
```

## Flow Comparison

### When to Use Each Flow

| Question | Basic | Analyze | Deep Research |
|----------|-------|---------|---------------|
| Simple Q&A? | ✅ | | |
| Enterprise data? | | ✅ | |
| Web research? | | | ✅ |
| Need citations? | | ✅ | ✅ |
| Need validation? | | | ✅ |
| Report output? | | | ✅ |

### Architecture Patterns

| Pattern | Basic | Analyze | Deep Research |
|---------|-------|---------|---------------|
| Single LLM | ✅ | | |
| Supervisor-Worker | | ✅ | ✅ |
| Reflection Loop | | | ✅ |
| Tool Mode Agents | | ✅ | ✅ |
| Data Isolation | | ✅ | |

## Working with Flows

### Importing a Flow

1. Open LangFlow UI (http://localhost:7860)
2. Click "Import" or drag JSON file
3. Configure credentials (API keys)
4. Test in playground

### Exporting a Flow

1. Open flow in LangFlow UI
2. Click "Export" → "Download JSON"
3. Save to `flows/` directory
4. Commit to version control

### API Usage

```bash
# Execute a flow
curl -X POST "http://localhost:7860/api/v1/run/{flow_id}" \
  -H "Content-Type: application/json" \
  -d '{
    "input_value": "Your query here",
    "input_type": "chat",
    "output_type": "chat",
    "session_id": "optional-session-id"
  }'
```

## Development Workflow

1. **Design** flow architecture in docs
2. **Build** flow in LangFlow UI
3. **Test** in LangFlow playground
4. **Export** JSON to `flows/`
5. **Document** prompts and decisions
6. **Commit** to version control

## See Also

- [Development Plan](../.tmp/DEVELOPMENT-PLAN.md) - Project phases and tasks
- [Architecture](../docs/ARCHITECTURE.md) - Platform architecture
- [Development Guide](../docs/DEVELOPMENT.md) - Local development setup
