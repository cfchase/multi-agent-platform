# LangFlow Flows

This directory is a placeholder for local flow development. The platform imports flows from external sources (git repositories) rather than bundling them.

## Example Flows

Official example flows are maintained in a separate repository:

**[cfchase/langflow-examples](https://github.com/cfchase/langflow-examples)**

## Flow Sources

The platform can load flows from multiple sources:

| Source Type | Description | Use Case |
|-------------|-------------|----------|
| **Git (Public)** | Public git repository | Community flows, examples |
| **Git (Private)** | Private git repository | Enterprise, proprietary flows |
| **Local** | Directory on filesystem | Development, testing |

### Configuration

Configure flow sources in `config/flow-sources.yaml`:

```yaml
sources:
  # Example flows from GitHub
  - name: examples
    type: git
    url: https://github.com/cfchase/langflow-examples
    path: flows

  # Private enterprise flows
  - name: enterprise
    type: git
    url: https://github.com/your-org/your-flows
    path: flows
    auth:
      type: token
      env_var: GITHUB_FLOW_TOKEN

  # Local development
  - name: local-dev
    type: local
    path: ./langflow-flows/dev
```

### Import Flows

```bash
# Import from all configured sources
make langflow-import

# Or with a simple path override
FLOW_SOURCE_PATH=./my-flows make langflow-import
```

## Flow File Format

Each flow consists of:

### 1. Flow Definition (`*.json`)

LangFlow export JSON file:

```json
{
  "name": "Flow Name",
  "description": "Flow description",
  "data": {
    "nodes": [...],
    "edges": [...]
  }
}
```

### 2. Metadata (`*.metadata.yaml`) - Optional

Additional platform metadata:

```yaml
name: Flow Name
description: Flow description
version: 1.0.0
author: Team Name
tags: [research, chat]
requires: [GEMINI_API_KEY]
```

## Creating Flows

1. Open LangFlow UI: http://localhost:7860
2. Create flow using visual builder
3. Test in playground
4. Export: Click "Export" → "Download JSON"
5. Add to your flow repository
6. Import: `make langflow-import`

## Creating Your Own Flow Repository

See [cfchase/langflow-examples](https://github.com/cfchase/langflow-examples) as a template:

```
your-flows-repo/
├── README.md
├── flows/
│   ├── my-flow.json
│   └── my-flow.metadata.yaml
└── components/     # Custom LangFlow components
```

## See Also

- [cfchase/langflow-examples](https://github.com/cfchase/langflow-examples) - Example flows
- [docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md) - Local development
- [config/flow-sources.yaml.example](../config/flow-sources.yaml.example) - Configuration template
