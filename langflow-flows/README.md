# LangFlow Flows

This directory is a placeholder for local flow development. The platform imports flows from external sources (git repositories) rather than bundling them.

## Example Flows

Official example flows are maintained in a separate repository:

**[cfchase/langflow-examples](https://github.com/cfchase/langflow-examples)**

## Flow Sources

The platform can load flows from multiple sources:

| Source Type | Description | Use Case |
|-------------|-------------|----------|
| **File** | Single JSON file or URL | Quick imports, direct links |
| **Git (Public)** | Public git repository | Community flows, examples |
| **Git (Private)** | Private git repository | Enterprise, proprietary flows |
| **Local** | Directory on filesystem | Development, testing |

### Configuration

Configure flow sources in `config/flow-sources.yaml`:

```yaml
flow_sources:
  # Example flows from GitHub
  - name: examples
    type: git
    url: https://github.com/cfchase/langflow-examples
    project: "Examples"       # Target project (created if missing)
    public: true              # Make flows visible to all users

  # Private enterprise flows
  - name: enterprise
    type: git
    url: https://github.com/your-org/your-flows
    project: "Enterprise"
    pattern: "**/flows/*.json"  # Only import from flows/ subdirectories
    auth:
      env_var: GITHUB_FLOW_TOKEN

  # Local development
  - name: local-dev
    type: local
    path: ./langflow-flows/dev
    project: "Development"
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `name` | Source identifier | required |
| `type` | `file`, `local`, or `git` | required |
| `path` | File path or URL (for `file`/`local` types) | required |
| `url` | Git repository URL (for `git` type) | required |
| `branch` | Git branch to clone (for `git` type) | `main` |
| `project` | LangFlow project name (created if missing) | none |
| `pattern` | Glob pattern for finding flows | `**/*.json` |
| `public` | Make flows visible to all users | `false` |
| `enabled` | Enable/disable this source | `true` |

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

### 2. Metadata (`*.metadata.yaml`) - Planned Feature

> **Note**: Metadata files are not yet processed by the importer. This is a planned feature.

Additional platform metadata (future):

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
├── simple-ollama/
│   └── simple-ollama.json
└── my-flow/
    ├── my-flow.json
    └── my-flow.metadata.yaml   # Optional
```

The import script recursively finds all `*.json` files in the repository.

## See Also

- [cfchase/langflow-examples](https://github.com/cfchase/langflow-examples) - Example flows
- [docs/DEVELOPMENT.md](../docs/DEVELOPMENT.md) - Local development
- [config/flow-sources.yaml.example](../config/flow-sources.yaml.example) - Configuration template
