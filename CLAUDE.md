# CLAUDE.md

## Project Overview

Twilio Agent Connect (TAC) is a Python SDK — middleware (not an agent runtime) that enables LLM applications (OpenAI Agents SDK, Bedrock, LangChain, etc.) to use Twilio primitives: Conversation Memory for memory, Conversation Orchestrator for conversations, ConversationRelay for voice.

## Development Commands

```bash
make sync              # Install dependencies (uses uv)
make dev-setup         # Full dev setup with pre-commit hooks
make format            # Format with ruff
make lint              # Lint check only
make type-check        # mypy strict mode
make test              # Run pytest
make check             # All checks (lint + type-check + test)

uv run pytest tests/test_tac.py                      # Single test file
uv run pytest tests/test_tac.py::test_function_name  # Single test
```

When creating PRs, read and fill in `.github/PULL_REQUEST_TEMPLATE.md`.

## Package Structure

```
src/tac/
├── core/           # TAC class, TACConfig, context models
├── context/        # API clients: MemoryClient, ConversationClient, KnowledgeClient
├── models/         # Pydantic models (memory, conversation, session, voice, knowledge, intelligence)
├── channels/       # SMS and Voice channel implementations (base, sms, voice)
├── intelligence/   # Conversation Intelligence webhook processing
├── tools/          # LLM tool integration (@function_tool decorator, TACTool)
├── adapters/       # Runtime adapters (OpenAI memory injection, prompt builder)
└── server/         # Optional TACFastAPIServer (FastAPI-based, install with tac[server])
```

Tests are in `tests/` — one test file per module (e.g., `test_tac.py`, `test_sms_channel.py`, `test_voice_channel.py`).

## Code Conventions

- **Python 3.9+**: Use `typing` module types (`List`, `Dict`, `Optional`) — not `list`, `dict`
- **mypy strict**: All functions need type hints, no incomplete defs
- **Pydantic v2**: Use `Field(alias=...)` for API name mapping, `model_config = {"populate_by_name": True}`, `.model_dump(by_alias=True, exclude_none=True)` for API payloads
- **ruff**: Line length 100, black-compatible formatting
- **Lint rules**: pycodestyle (E/W), pyflakes (F), isort (I), flake8-bugbear (B), flake8-comprehensions (C4), pyupgrade (UP)
- **Per-file ignores**: Examples allow E402 and E501

## Key Architecture Concepts

- **Channel-based**: SMS and Voice channels process Twilio webhooks, manage conversation lifecycle, and trigger `on_message_ready` / `on_conversation_ended` callbacks
- **Memory fallback**: `TAC.retrieve_memory()` tries Conversation Memory first, gracefully falls back to Conversation Orchestrator's `list_communications()` on any failure
- **Profile resolution**: Automatic profile lookup by phone/email if `profile_id` not present in webhook
- **Memory auto-init**: Memory client is always initialized from Conversation Orchestrator configuration's `memory_store_id`
- **Auth**: All API clients use HTTP Basic Auth (API Key as username, API Token as password)

## OpenAI Adapter

The OpenAI adapter (`src/tac/adapters/openai/adapter.py`) supports both Chat Completions and Responses APIs for automatic memory injection:

**Chat Completions API**:
- Injects memory as system message at start of messages array
- Example: `client.chat.completions.create(model="gpt-5.4-mini", messages=[...])`

**Responses API**:
- Injects memory by prepending to instructions parameter
- Example: `client.responses.create(model="gpt-5.4-mini", instructions="...", input=[...])`

Both APIs are fully supported with sync/async variants and streaming support.

## Dependencies

- **Core**: `pydantic>=2`, `requests>=2.31`, `httpx>=0.27`, `twilio>=9.8.3`
- **Server** (optional): `fastapi`, `uvicorn`, `python-multipart` — install with `pip install tac[server]`
- **Dev**: `pytest`, `ruff`, `mypy`, `openai`, `openai-agents`
