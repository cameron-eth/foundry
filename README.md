# Foundry

Dynamic tool creation and execution service for AI agents. Describe what you need in plain English, get production-ready Python tools deployed in seconds.

Built on [Modal](https://modal.com) for zero-infrastructure serverless deployment.

## What It Does

Foundry lets AI agents build custom tools at runtime:

1. **Describe** a capability in natural language (`"Calculate compound interest"`)
2. **Get** validated, sandboxed Python code generated automatically
3. **Invoke** the tool via REST API with typed inputs/outputs

Tools run in isolated Modal Sandboxes with no filesystem, network, or system access. Code is validated via AST analysis before execution.

## Quick Start

### Prerequisites

- Python 3.11+
- A [Modal](https://modal.com) account (free tier available)
- An Anthropic or OpenAI API key

### 1. Clone and install

```bash
git clone https://github.com/cameron-eth/foundry.git
cd foundry
pip install modal
```

### 2. Authenticate with Modal

```bash
modal token new
```

### 3. Create secrets

You need at least one LLM provider:

```bash
# Anthropic (recommended)
modal secret create anthropic-credentials ANTHROPIC_API_KEY=sk-ant-...

# OpenAI (alternative or additional)
modal secret create openai-credentials OPENAI_API_KEY=sk-...
```

Create the branding/config secret (required):

```bash
modal secret create foundry-branding \
  FOUNDRY_LLM_PROVIDER=anthropic \
  FOUNDRY_AGENT_MODEL=claude-sonnet-4-20250514 \
  FOUNDRY_API_TITLE="My Foundry Instance"
```

Optional secrets for extra features:

```bash
# Web search (Brave Search — free tier: 2000 queries/month)
modal secret create brave-credentials BRAVE_API_KEY=...

# Exa search (alternative search provider)
modal secret create exa-credentials EXA_API_KEY=...
```

### 4. Deploy

```bash
modal deploy foundry.py
```

Your API is now live at:
```
https://{your-workspace}--toolfoundry-serve.modal.run
```

### Or use the interactive deploy script

```bash
chmod +x deploy.sh
./deploy.sh setup    # Interactive first-time setup wizard
./deploy.sh deploy   # Deploy to Modal
./deploy.sh serve    # Local dev with hot reload
./deploy.sh status   # Check deployment status
./deploy.sh branding # Customize Swagger docs appearance
```

## Usage

### Create a tool from a description

```bash
curl -X POST https://YOUR-WORKSPACE--toolfoundry-serve.modal.run/v1/construct \
  -H "Content-Type: application/json" \
  -d '{
    "capability_description": "Calculate compound interest given principal, rate, and years",
    "org_id": "my-org",
    "conversation_id": "demo"
  }'
```

Response:
```json
{
  "request_id": "req-abc123",
  "tool_id": "tool-def456",
  "status": "ready",
  "invoke_url": ".../v1/tools/tool-def456/invoke"
}
```

### Invoke a tool

```bash
curl -X POST .../v1/tools/tool-def456/invoke \
  -H "Content-Type: application/json" \
  -d '{"input": {"principal": 1000, "rate": 0.05, "years": 10}}'
```

### Create a tool with explicit code

```bash
curl -X POST .../v1/tools \
  -H "Content-Type: application/json" \
  -d '{
    "name": "add",
    "description": "Add two numbers",
    "implementation": "def main(a: float, b: float) -> float:\n    return a + b",
    "input_schema": {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}}
  }'
```

### Web search

```bash
curl -X POST .../v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "latest AI research", "num_results": 10, "num_searches": 3}'
```

## Python SDK

```python
from foundry import Foundry

client = Foundry(
    base_url="https://YOUR-WORKSPACE--toolfoundry-serve.modal.run",
)

# Create a tool from a description
tool = client.create("Calculate factorial of a number")
result = tool.invoke(n=10)
print(result.result)  # 3628800

# Chain tools together
chain = (
    client.create("Search for news about AI")
    .then(client.create("Summarize the key points"))
)
result = chain.invoke(topic="artificial intelligence")
```

Set `FOUNDRY_API_URL` to avoid passing `base_url` every time:

```bash
export FOUNDRY_API_URL=https://YOUR-WORKSPACE--toolfoundry-serve.modal.run
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Swagger UI documentation |
| `POST` | `/v1/construct` | Create tool from natural language |
| `POST` | `/v1/tools` | Create tool with explicit code |
| `GET` | `/v1/tools` | List all tools |
| `GET` | `/v1/tools/{id}` | Get tool manifest/schema |
| `POST` | `/v1/tools/{id}/invoke` | Execute a tool |
| `DELETE` | `/v1/tools/{id}` | Delete a tool |
| `POST` | `/v1/tools/{id}/rebuild` | Rebuild a broken tool |
| `POST` | `/v1/tools/{id}/deprecate` | Soft-delete a tool |
| `POST` | `/v1/search` | Web search with query expansion |
| `GET` | `/v1/builds/{id}` | Check async build status |

### Typed Result Envelope

Invoke responses use a typed envelope so agents can deterministically parse results:

```json
{
  "success": true,
  "result_type": "number",
  "result": { "number": 22.86 },
  "raw_result": 22.86,
  "execution_time_ms": 45
}
```

| `result_type` | Field | Use Case |
|---------------|-------|----------|
| `text` | `result.text` | Strings, formatted text |
| `number` | `result.number` | Numeric calculations |
| `image` | `result.image_base64` | Charts, visualizations (base64 PNG) |
| `table` | `result.table` | List of objects/rows |
| `object` | `result.object` | Complex structured data |

## Configuration

### LLM Providers

Set via the `foundry-branding` Modal secret:

| Variable | Options | Default |
|----------|---------|---------|
| `FOUNDRY_LLM_PROVIDER` | `anthropic`, `openai` | `anthropic` |
| `FOUNDRY_AGENT_MODEL` | Any supported model ID | `claude-sonnet-4-20250514` |

### Optional Features

All optional — the service works without any of these:

| Feature | Secret Name | What It Enables |
|---------|-------------|-----------------|
| Web Search | `brave-credentials` | `/v1/search` endpoint via Brave API |
| Exa Search | `exa-credentials` | Alternative search provider |
| Database | `neon-credentials` | Multi-tenant auth, API key management, usage tracking |
| Billing | `autumn-credentials` | Usage-based billing via Stripe |
| Auth | Set `FOUNDRY_REQUIRE_AUTH=true` | Require API keys on all routes |

### Swagger Branding

Customize the API docs via `foundry-branding`:

```bash
modal secret create foundry-branding \
  FOUNDRY_API_TITLE="My API" \
  FOUNDRY_API_DESCRIPTION="Custom description" \
  FOUNDRY_LOGO_URL="https://example.com/logo.png" \
  FOUNDRY_CONTACT_NAME="Your Name" \
  FOUNDRY_CONTACT_EMAIL="you@example.com" \
  FOUNDRY_LLM_PROVIDER=anthropic \
  FOUNDRY_AGENT_MODEL=claude-sonnet-4-20250514
```

## Security Model

- **Code validation**: AST analysis blocks `eval`, `exec`, `os`, `subprocess`, `__import__`, etc.
- **Module allowlist**: Only safe modules (math, json, numpy, pandas, scipy, sklearn, etc.)
- **Sandboxed execution**: Modal Sandbox — no filesystem, network, or system access
- **Resource limits**: 30s timeout, 256MB memory per invocation
- **Secret isolation**: Generated tools cannot access Foundry's own credentials

## Project Structure

```
foundry.py              # Modal app entry point
deploy.sh               # Interactive deployment script
src/
  api/
    routes.py           # FastAPI endpoints + landing page
    auth.py             # API key authentication + rate limiting
    schemas.py          # Pydantic request/response models
    billing.py          # Optional billing endpoints (Autumn/Stripe)
    keys.py             # API key management endpoints
    usage.py            # Usage tracking endpoints
    secrets.py          # Per-tool secret injection
  agent/
    builder_agent.py    # AI agent that generates tool code
    planner.py          # Tool planning logic
    tools.py            # Agent tool definitions
    providers.py        # LLM provider abstraction (Anthropic/OpenAI)
    prompts.py          # System prompts for code generation
    sdk_agents.py       # OpenAI Agents SDK integration
    generator.py        # Code generation pipeline
  builder/
    validator.py        # AST-based code validation
    sandbox.py          # Sandboxed execution (Modal Sandbox / local)
  infra/
    config.py           # Centralized settings (Pydantic)
    database.py         # Optional Postgres/Neon integration
    secrets.py          # Secret management helpers
    logging.py          # Structured logging
    autumn.py           # Optional Autumn billing client
  registry/
    store.py            # Tool storage (Modal Dict or in-memory)
  orchestration/
    workflow.py         # Build orchestration
  events/
    emitter.py          # Event emission
sdk/
  foundry/
    client.py           # Python SDK
    exceptions.py       # SDK exceptions
tests/
  test_api.py
  test_validator.py
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Local development with hot reload
modal serve foundry.py

# Run tests
PYTHONPATH=. pytest tests/ -v

# Lint
ruff check .

# Type check
pyright
```

## Cost Estimate

Modal is pay-per-use with no idle costs:

- **API endpoint**: ~$5-20/month depending on traffic
- **Tool executions**: ~$0.001-0.01 per invocation
- **Estimated total**: $20-50/month for moderate usage

## License

MIT
