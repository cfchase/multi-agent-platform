# LangFlow Flows

This directory contains example LangFlow flows bundled with the platform. The platform supports loading flows from multiple sources including local directories and git repositories.

## Directory Structure

```
langflow-flows/
├── README.md              # This file
└── examples/              # Built-in example flows
    ├── hello-gemini.json          # Flow definition (LangFlow export)
    └── hello-gemini.metadata.yaml # Flow metadata
```

## Flow Sources

The platform can load flows from multiple sources:

| Source Type | Description | Use Case |
|-------------|-------------|----------|
| **Local** | Directory on filesystem | Development, bundled examples |
| **Git (Public)** | Public git repository | Community flows, open source |
| **Git (Private)** | Private git repository | Enterprise, proprietary flows |

### Configuration

Configure flow sources via environment variable or YAML config file.

**Simple (single local path):**
```bash
FLOW_SOURCE_PATH=./langflow-flows/examples
```

**Advanced (config file):**
```bash
FLOW_SOURCES_CONFIG=./config/flow-sources.yaml
```

**Example config file:**
```yaml
# config/flow-sources.yaml
flow_sources:
  # Built-in examples
  - name: examples
    type: local
    path: ./langflow-flows/examples
    description: "Built-in example flows"

  # Public git repo
  - name: community
    type: git
    url: https://github.com/org/langflow-flows-public.git
    branch: main
    path: flows/
    description: "Community flows"

  # Private git repo (requires token)
  - name: enterprise
    type: git
    url: https://github.com/org/langflow-flows-private.git
    branch: main
    path: flows/
    auth:
      type: token
      env_var: GITHUB_FLOW_TOKEN
    description: "Enterprise flows"
```

## Flow File Format

Each flow consists of two files:

### 1. Flow Definition (`*.json`)

The LangFlow export JSON file containing the flow graph:

```json
{
  "name": "Flow Name",
  "description": "Flow description",
  "data": {
    "nodes": [...],
    "edges": [...],
    "viewport": {...}
  }
}
```

### 2. Flow Metadata (`*.metadata.yaml`) - Optional

Additional metadata for the platform:

```yaml
name: Flow Name
description: Flow description
version: 1.0.0
author: Team Name
tags:
  - tag1
  - tag2
requires:
  - API_KEY_NAME
icon: comments  # PatternFly icon
complexity: minimal  # minimal, low, medium, high
use_cases:
  - Use case 1
  - Use case 2
```

## Working with Flows

### Creating a Flow

1. Open LangFlow UI (http://localhost:7860)
2. Create your flow using the visual builder
3. Test in LangFlow playground
4. Export: Click "Export" → "Download JSON"
5. Save to appropriate directory
6. Create metadata YAML file (optional)
7. Commit to version control

### Importing a Flow

1. Open LangFlow UI
2. Click "Import" or drag JSON file
3. Configure required credentials (API keys)
4. Test in playground

### API Usage

```bash
# List available flows
curl http://localhost:8000/api/v1/flows

# Execute a flow via LangFlow API
curl -X POST "http://localhost:7860/api/v1/run/{flow_id}" \
  -H "Content-Type: application/json" \
  -d '{
    "input_value": "Your message here",
    "input_type": "chat",
    "output_type": "chat",
    "session_id": "optional-session-id"
  }'
```

## Available Example Flows

| Flow | Description | Complexity |
|------|-------------|------------|
| [Hello Gemini](examples/hello-gemini.json) | Simple chat with Gemini model | Minimal |

## Creating Your Own Flow Repository

To create a separate repository for your flows:

1. Create a new git repository
2. Add a `flows/` directory
3. Add your flow JSON and metadata files
4. Configure the platform to use your repo as a source

**Example structure:**
```
your-flows-repo/
├── README.md
└── flows/
    ├── my-flow.json
    ├── my-flow.metadata.yaml
    ├── another-flow.json
    └── another-flow.metadata.yaml
```

## See Also

- [Development Guide](../docs/DEVELOPMENT.md) - Local development setup
- [Architecture](../docs/ARCHITECTURE.md) - Platform architecture
- [Phase 2A Plan](../.tmp/PHASE-2A-FLOW-SOURCES.md) - Detailed implementation plan
