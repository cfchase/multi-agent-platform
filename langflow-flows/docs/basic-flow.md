# Basic Chat Flow

## Overview

The Basic Chat Flow is the simplest flow in the platform, designed to validate LangFlow integration and provide a foundation for more complex flows.

**Status:** Phase 2A
**Complexity:** Minimal
**Use Case:** Simple Q&A, testing, learning LangFlow

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Basic Chat Flow                         │
│                                                              │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│   │              │    │              │    │              │  │
│   │  Chat Input  │───►│ Gemini Model │───►│ Chat Output  │  │
│   │              │    │              │    │              │  │
│   └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Components

| Component | Type | Purpose |
|-----------|------|---------|
| **Chat Input** | Input | Receives user message |
| **Gemini Model** | LLM | Google Generative AI (gemini-1.5-flash or gemini-1.5-pro) |
| **Chat Output** | Output | Returns model response |

---

## Configuration

### Model Settings

| Parameter | Value | Notes |
|-----------|-------|-------|
| Model | `gemini-1.5-flash` | Fast, cost-effective for simple queries |
| Temperature | 0.7 | Balanced creativity/consistency |
| Max Tokens | 2048 | Sufficient for most responses |
| Streaming | Enabled | Real-time response display |

### Required Credentials

| Secret | Description |
|--------|-------------|
| `GOOGLE_API_KEY` | Google AI Studio API key |

---

## Data Flow

```
User Message
    │
    ▼
┌─────────────────────────────────────┐
│ Chat Input Component                 │
│ - Extracts message text              │
│ - Passes session_id for continuity   │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ Gemini Model Component               │
│ - Receives message + history         │
│ - Generates response                 │
│ - Streams tokens                     │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ Chat Output Component                │
│ - Formats response                   │
│ - Returns to user                    │
└─────────────────────────────────────┘
```

---

## Session Management

The flow supports multi-turn conversations via `session_id`:

```json
{
  "input_value": "What is the capital of France?",
  "input_type": "chat",
  "output_type": "chat",
  "session_id": "user-123-session-456"
}
```

The session maintains conversation history, enabling follow-up questions:
- User: "What is the capital of France?"
- Assistant: "The capital of France is Paris."
- User: "What's its population?"
- Assistant: "Paris has a population of approximately 2.1 million..."

---

## API Usage

### Execute Flow

```bash
curl -X POST "http://localhost:7860/api/v1/run/{flow_id}" \
  -H "Content-Type: application/json" \
  -d '{
    "input_value": "Hello, how are you?",
    "input_type": "chat",
    "output_type": "chat",
    "session_id": "test-session-1"
  }'
```

### Streaming Response

```bash
curl -X POST "http://localhost:7860/api/v1/run/{flow_id}?stream=true" \
  -H "Content-Type: application/json" \
  -d '{
    "input_value": "Explain quantum computing",
    "input_type": "chat",
    "output_type": "chat"
  }'
```

---

## Observability

### Langfuse Tracing

When Langfuse is configured, the flow automatically traces:
- Input message
- Model generation (tokens, latency)
- Output response

Trace hierarchy:
```
Trace: basic-chat-{session_id}
  └─ Generation: gemini-1.5-flash
       ├─ Input: user message
       ├─ Output: assistant response
       ├─ Tokens: {prompt: N, completion: M}
       └─ Latency: Xms
```

---

## Limitations

- **No tools**: Cannot search web, access databases, or call APIs
- **No memory persistence**: Session history is flow-internal only
- **Single model**: No routing or model selection
- **No validation**: No output checking or guardrails

---

## When to Use

**Good for:**
- Quick Q&A
- Testing LangFlow connectivity
- Validating API integration
- Learning LangFlow basics

**Not suitable for:**
- Research tasks requiring sources
- Complex multi-step reasoning
- Tasks requiring external data access

---

## Next Steps

After validating the Basic Chat Flow:
1. Add Langfuse tracing (Phase 2B)
2. Build chatbot MVP with flow selection (Phase 2C)
3. Progress to Analyze Flow for complex orchestration (Phase 3)
