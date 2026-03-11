# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Twilio Agent Connect (TAC) is a Python SDK that integrates third-party LLM agentic applications with Twilio communication APIs. TAC provides middleware for identity resolution, memory/context management (via Memory Service), conversation orchestration (via Maestro), and channel handling (Voice, SMS).

**Key Architecture Principle**: TAC is not an agent runtime itself—it's middleware that enables existing LLM applications (OpenAI Agents SDK, Bedrock, LangChain, etc.) to leverage Twilio Sierra primitives (Memory for memory, Maestro for conversations, ConversationRelay for voice).

## Development Commands

### Environment Setup
```bash
# Install dependencies (uses uv package manager)
make sync

# Complete dev environment setup with pre-commit hooks
make dev-setup
```

### Code Quality
```bash
# Format code with ruff (includes linting fixes)
make format

# Run type checking with mypy (required: mypy >=1.0.0, strict mode)
make type-check

# Run linting checks only (no auto-fix)
make lint

# Run all checks (lint + type-check + test)
make check

# Run pre-commit hooks
make pre-commit
```

### Testing
```bash
# Run all tests with pytest
make test

# Run single test file
uv run pytest tests/test_tac.py

# Run specific test
uv run pytest tests/test_tac.py::test_function_name
```

### Pull Requests
When creating PRs, read and fill in the template at `.github/PULL_REQUEST_TEMPLATE.md`.

### Examples
```bash
# Start setup wizard to create Memory and Conversation services (port 8080)
make setup

# Run an example (OpenAI SDK)
cd getting_started/examples/openai
python openai_sdk.py

# Start ngrok tunnel for local testing
ngrok http 8000
```

## Core Architecture

### Package Structure

The codebase follows a modular design matching the architecture diagram in TAC.md:

- **`src/tac/core/`** - Core TAC class, configuration, and context models
  - `tac.py` - Main `TAC` class with `retrieve_memory()` (graceful fallback to Maestro on any memory retrieval failure, automatic profile lookup/fetch), `fetch_profile()`, `on_message_ready()` hook, `on_conversation_ended()` hook, `ci_processor` (optional `OperatorResultProcessor`), and `process_cintel_event()` method. Memory client (`memora_client`) is always initialized from Maestro configuration's `memory_store_id`.
  - `config.py` - `TACConfig` Pydantic model for SDK configuration; `TwilioMemoryConfig` with optional `trait_groups`; `ConversationIntelligenceConfig` with `configuration_id`, `observation_operator_sid`, `summary_operator_sid`

- **`src/tac/context/`** - Integration with Twilio Sierra primitives
  - `memory.py` - `MemoryClient` for memory retrieval (traits, observations, sessions), profile retrieval with `get_profile()`, and profile lookup with `lookup_profile()`
  - `knowledge.py` - `KnowledgeClient` for knowledge base operations (`get_knowledge_base()`, `search_knowledge_base()`)
  - `conversation.py` - `ConversationClient` for conversation/participant management

- **`src/tac/models/`** - Data models
  - `memory.py` - Memory API models: `MemoryRetrievalRequest`, `MemoryRetrievalResponse`, `MemoryCommunication`, `MemoryCommunicationContent`, `MemoryParticipant`, `ObservationInfo`, `SummaryInfo`, `SessionInfo`, `SessionMessage`, `ProfileResponse`, `ProfileLookupRequest`, `ProfileLookupResponse`
  - `conversation.py` - Maestro Conversation API models: `ConversationRequest`, `ConversationResponse` (with `configuration_id` and detailed `ConversationConfiguration` fields), `ParticipantRequest`, `ParticipantResponse`, `ParticipantAddress`, `Communication`, `CommunicationContent`, `CommunicationParticipant`, `ConversationConfiguration` (with `display_name`, `description`, `conversation_grouping_type`, `channel_settings`, `status_callbacks`), `StatusTimeouts`, `CaptureRule`, `ChannelSettings`, `StatusCallback`
  - `tac.py` - TAC unified response models: `TACMemoryResponse` (wrapper for unified memory access with `build_memory_prompts()` helper for LLM prompt generation), `TACCommunication` (unified communication with ALL fields from both APIs), `TACCommunicationAuthor`, `TACCommunicationContent`
  - `session.py` - Session models: `ConversationSession` (with optional `profile` and `author_info` fields, plus `build_profile_prompt()` helper for LLM prompt generation), `AuthorInfo`
  - `voice.py` - Voice WebSocket message models: `SetupMessage`, `PromptMessage`, `InterruptMessage`, `CustomParameters`, `CallbackResponse`, `ConversationRelayCallbackPayload`
  - `knowledge.py` - Knowledge API models: `KnowledgeBase` (with `display_name`, `status`, `created_at`, `updated_at`, `version`), `KnowledgeChunkResult` (search result chunks), `Knowledge` (legacy model)
  - `intelligence.py` - Conversation Intelligence models: `OperatorResultEvent`, `OperatorProcessingResult`, `IntelligenceConfiguration`, `Operator`, `Participant`, `ExecutionDetails`, `TriggerDetails`, `CommunicationsRange`

- **`src/tac/intelligence/`** - Conversation Intelligence webhook processing
  - `operator_result_processor.py` - `OperatorResultProcessor` class for processing CI webhook events; requires `ConversationIntelligenceConfig` to filter events by configuration ID and operator SIDs; creates observations/summaries in Memory based on operator results; returns `OperatorProcessingResult`

- **`src/tac/channels/`** - Channel-specific orchestration and conversation lifecycle management
  - `base.py` - `BaseChannel` abstract class with conversation session management (`_start_conversation()`); `send_response()` with optional `role` parameter
  - `sms.py` - `SMSChannel` implementation handling webhook events, message validation, memory retrieval, and idempotency-based deduplication using Twilio's `i-twilio-idempotency-token` header
  - `voice.py` - `VoiceChannel` for Voice/ConversationRelay WebSocket protocol handling; framework-agnostic (uses `WebSocketProtocol`). For a batteries-included server, use `tac.server.TACServer`

- **`src/tac/tools/`** - LLM tool integration for Sierra primitives
  - `base.py` - `TACTool` dataclass with `to_openai_format()` and `to_anthropic_format()` methods; `function_tool` decorator for creating tools from functions
  - `messaging.py` - `create_messaging_tools(config)` factory returning `send_message` tool
  - `memory.py` - `create_memory_tools(config, session)` factory returning `retrieve_profile_memory` tool
  - `example.py` - Example tool implementations

- **`src/tac/adapters/`** - Runtime-specific adapters for automatic TAC memory injection
  - `openai/adapter.py` - OpenAI SDK adapter using wrapper classes to inject memory without mutating original client; supports sync/async and streaming; exported via `openai/__init__.py` as `with_tac_memory`
  - `prompt_builder.py` - `MemoryPromptBuilder` class for building LLM prompts from TAC memory and profile data; shared across all adapters
  - `options.py` - `AdapterOptions` model for controlling adapter behavior with `profile_traits` field: if not provided, ALL traits are included; if `None` or `[]`, no traits; if list of trait names, only those traits

### Critical Workflow

**Channel-Based Architecture** (Recommended):

1. **Channel processes webhook**: Twilio sends webhook → `channel.process_webhook(webhook_data)` → channel extracts event type and routes to appropriate handler → handler validates event data into typed models (ConversationResponse, ParticipantResponse, Communication) → validates message content

2. **Conversation Management**: Channel handles conversation lifecycle:
   - `participant.added`: Channel filters by participant type (CUSTOMER) and channel (SMS/VOICE addresses) → extracts `profile_id` from webhook → calls `_start_conversation(conv_id, profile_id)` → stores conversation session
   - `communication.created`: Channel validates message → auto-initializes conversation if needed (fallback) → creates `ConversationSession` with all fields → calls `tac.retrieve_memory(conversation_context, query)`
   - `conversation.updated`: Channel validates conversation belongs to configured service (via `configuration_id`) → removes local session if status is CLOSED

3. **Message Processing**: `TAC.retrieve_memory(conversation_context, query)` → retrieves memories with graceful fallback:
   - **Memory Retrieval Strategy** (single try-catch wrapper):
     - **Profile ID Resolution**:
       - If `profile_id` exists: Uses it directly
       - If `profile_id` missing: Attempts automatic lookup via `lookup_profile(id_type="phone", value=author_info.address)`
       - On successful lookup: Sets `profile_id` and immediately fetches profile (one-time attempt)
     - **Profile Fetch**: If `profile_id` exists but profile not yet fetched, fetches it once
     - **Memory Retrieval**: Retrieves full memory (observations, summaries, communications) from Memory Service
     - **Error Handling**: If any step fails (lookup, fetch, retrieval), gracefully falls back to Maestro's `list_communications()` API
   - Always returns `TACMemoryResponse` (unified wrapper) → triggers `on_message_ready()` callback
   - Memory client is always initialized from Maestro configuration's `memory_store_id` field

4. **Message Ready Hook**: Developers register callbacks via `tac.on_message_ready(callback)` to handle incoming messages
   - For SMS: Receives `user_message`, `context` (ConversationSession), and `memory_response` (TACMemoryResponse - only retrieved when `auto_retrieve_memory=True`; retrieval may fall back to Maestro on errors)
   - For Voice: Receives `user_message`, `context`, and `memory_response` (TACMemoryResponse - only retrieved when `auto_retrieve_memory=True`; retrieval may fall back to Maestro on errors)

5. **Conversation Ended Hook**: Developers register callbacks via `tac.on_conversation_ended(callback)` to run custom logic when a conversation ends
   - Triggered when SMS conversation status changes to CLOSED or Voice WebSocket disconnects
   - Callback receives the full `ConversationSession` (with profile, metadata, etc.) before cleanup
   - Supports both sync and async callbacks; errors in the callback do not prevent session cleanup

### API Clients

**MemoryClient** (`src/tac/context/memory.py`):
- `retrieve_memory()`: Retrieve conversation memories
  - Endpoint: `POST /v1/Stores/{store_id}/Profiles/{profile_id}/Recall`
  - Returns: `MemoryRetrievalResponse` with `observations`, `summaries`, `communications` fields
- `get_profile()`: Retrieve profile with traits
  - Endpoint: `GET /v1/Stores/{store_id}/Profiles/{profile_id}`
  - Query param: `traitGroups` (comma-separated list)
  - Returns: `ProfileResponse` with `id`, `createdAt`, `traits` fields
- `lookup_profile()`: Find profiles by identifier value (e.g., phone number, email)
  - Endpoint: `POST /Stores/{service_id}/Profiles/Lookup`
  - Request: `ProfileLookupRequest` with `id_type` (e.g., "phone", "email") and `value`
  - Returns: `ProfileLookupResponse` with `normalized_value` and `profiles` (list of profile IDs)
  - Normalizes identifier values according to identity resolution settings (e.g., E.164 for phone numbers)
  - Returns canonical profile IDs (earliest ID if profiles have been merged)
- `create_observation()`: Create a new observation in Memory
  - Endpoint: `POST /v1/Stores/{store_id}/Profiles/{profile_id}/Observations`
  - Parameters: `profile_id`, `content`, `source` (default: "conversation-intelligence"), `conversation_ids`, `occurred_at`
  - Returns: Dict with created observation details
- `create_conversation_summaries()`: Create conversation summaries in Memory
  - Endpoint: `POST /v1/Stores/{store_id}/Profiles/{profile_id}/ConversationSummaries`
  - Parameters: `profile_id`, `summaries` (list of dicts with `content`, `conversationId`, `occurredAt`, `source`)
  - Returns: Response dict with message field
- Auth: Uses HTTP Basic Authentication (API Key as username, API Token as password)
- Models (from `src/tac/models/memory.py`):
  - `MemoryRetrievalRequest`: Request with `conversation_id`, `query`, optional date filters
  - `MemoryRetrievalResponse`: Response with observations, summaries, sessions arrays
  - `ObservationInfo`: Individual observation memories
  - `SummaryInfo`: Summarized insights from conversations
  - `SessionInfo`: Historical conversation sessions with messages
  - `SessionMessage`: Individual messages within sessions (includes `timestamp`, `direction`, `channel`, `from_address`, `to_address`, `content`)
  - `ProfileResponse`: Profile information with `id`, `createdAt`, `traits` (dict)
  - `ProfileLookupRequest`: Request with `id_type` and `value` for profile lookup
  - `ProfileLookupResponse`: Response with `normalized_value` and list of matching profile IDs

**ConversationClient** (`src/tac/context/conversation.py`):
- `create_conversation(name, configuration)`: Creates new conversation, returns `ConversationResponse`
  - Endpoint: `POST /v2/Conversations`
  - Note: Does not take `configuration_id` parameter (uses client's service_id internally)
- `list_conversations(status, channel_id, page_size, page_token)`: Lists conversations with optional filtering
  - Endpoint: `GET /v2/Conversations`
  - Parameters: `status` accepts list of strings (e.g., `["ACTIVE", "INACTIVE"]`). httpx automatically formats multiple values as repeated query parameters (e.g., `?status=ACTIVE&status=INACTIVE`)
  - Returns: List of `ConversationResponse` objects
- `update_conversation(conversation_id, name, status, configuration)`: Updates an existing conversation
  - Endpoint: `PUT /v2/Conversations/{conversation_id}`
  - Note: `status` parameter is required
  - Returns: `ConversationResponse`
- `add_participant(conversation_id, name, type, addresses)`: Adds participant, returns `ParticipantResponse`
  - Endpoint: `POST /v2/Conversations/{conversation_id}/Participants`
  - Note: Does not take `profile_id` parameter
- `list_communications(conversation_id, channel_id, page_size, page_token)`: Lists communications for a conversation
  - Endpoint: `GET /v2/Conversations/{conversation_id}/Communications`
  - Returns: List of `CommunicationResponse` objects
  - Used for memory fallback when Memory is not configured
- `create_communication(conversation_id, communication_request)`: Creates a new communication in a conversation
  - Endpoint: `POST /v2/Conversations/{conversation_id}/Communications`
  - Returns: `Communication` object
- Auth: Uses HTTP Basic Authentication (API Key as username, API Token as password)
- Models (from `src/tac/models/conversation.py`): `ConversationRequest`, `ConversationResponse` (includes `configuration_id` for filtering conversations by service), `UpdateConversationRequest`, `ConversationsListResponse`, `ParticipantRequest`, `ParticipantResponse`, `ParticipantAddress`, `CommunicationRequest`, `Communication`, `CommunicationsListResponse`, `ConversationConfiguration` (detailed config with `display_name`, `description`, `conversation_grouping_type`, `channel_settings`, `status_callbacks`)
- Pagination (from `src/tac/models/pagination.py`): `PaginationMeta` - Reusable pagination metadata for API list responses

**KnowledgeClient** (`src/tac/context/knowledge.py`):
- `get_knowledge_base(knowledge_base_id)`: Fetch knowledge base metadata
  - Endpoint: `GET /v2/ControlPlane/KnowledgeBases/{knowledge_base_id}`
  - Returns: `KnowledgeBase` with `id`, `display_name`, `description`, `status`, `created_at`, `updated_at`, `version`
- `search_knowledge_base(knowledge_base_id, query, top_k, knowledge_ids)`: Search knowledge base
  - Endpoint: `POST /v2/KnowledgeBases/{knowledge_base_id}/Search`
  - Parameters: `knowledge_base_id` (format: `know_knowledgebase_*`), `query` (max 2048 chars), `top_k` (default: 5, max: 20), `knowledge_ids` (optional list to filter results)
  - Returns: List of `KnowledgeChunkResult` objects with `content`, `knowledge_id`, `created_at`, `score`
- Auth: Uses HTTP Basic Authentication (API Key as username, API Token as password)
- Models (from `src/tac/models/knowledge.py`): `KnowledgeBase`, `KnowledgeChunkResult`
- Note: KnowledgeClient uses same authentication credentials as MemoryClient (API Key/Token from TACConfig)

## Type Checking and Code Style

This project uses **strict mypy configuration** (see pyproject.toml):
- All functions must have type hints (`disallow_untyped_defs = true`)
- No incomplete definitions allowed (`disallow_incomplete_defs = true`)
- Use `typing` module types (`Optional`, `List`, `Dict`, `Any`, `Union`, `Literal`)
- Python 3.9+ compatibility required (use `List` not `list` for type hints)

**Pydantic Usage**:
- All models use Pydantic v2 (`>=2.0.0,<3`)
- Use `Field()` with `alias` for API field name mapping (e.g., `trait_group` → `traitGroup`)
- Set `model_config = {"populate_by_name": True}` to accept both Python and API field names
- Use `.model_dump(by_alias=True, exclude_none=True)` for API request payloads

**Code Formatting**:
- Line length: 100 characters
- Use ruff for formatting and linting (black-compatible)
- Known first party: `["tac"]`
- Import combining: `combine-as-imports = true`
- Enabled lint rules: pycodestyle (E/W), pyflakes (F), isort (I), flake8-bugbear (B), flake8-comprehensions (C4), pyupgrade (UP)
- Per-file ignores: Examples allow E402 (import order) and E501 (line length)

## Testing

Tests are located in `tests/` directory:
- `test_tac.py` - Core TAC class tests
- `test_config.py` - Configuration tests
- `test_integration.py` - Integration tests
- `test_sms_channel.py` - SMS channel tests (including conversation ended callback)
- `test_voice_channel.py` - Voice channel tests (including conversation ended callback)
- `test_voice_models.py` - Voice WebSocket message model tests
- `test_conversation.py` - Conversation client tests
- `test_knowledge.py` - Knowledge client tests (get_knowledge_base, search_knowledge_base)
- `test_tools.py` - Tools module tests (function_tool decorator, TACTool format conversions, knowledge tool)
- `test_profile_retrieval.py` - Profile retrieval tests (trait_groups, fetch_profile, context.profile, lookup_profile)
- `test_profile_lookup_in_memory.py` - Automatic profile lookup in retrieve_memory tests (lookup by phone, lenient error handling, Maestro fallback)
- `test_memory_fallback.py` - Memory retrieval fallback tests (Memory to Maestro fallback)
- `test_init.py` - Package initialization tests
- `test_intelligence.py` - Conversation Intelligence processor tests (models, filtering, validation, content parsing)

Test requirements (pytest.ini_options in pyproject.toml):
- Test files: `test_*.py` or `*_test.py`
- Test classes: `Test*`
- Test functions: `test_*`

## Configuration Requirements

When initializing TAC, developers must provide:
- `twilio_account_sid` - Twilio Account SID from Twilio Console
- `twilio_auth_token` - Twilio Auth Token from Twilio Console
- `api_key` - Twilio API Key SID (starts with `SK`)
- `api_token` - Twilio API Key Secret
- `conversation_service_sid` - Twilio Conversation Service SID (starts with `conv_configuration_`)
  - **Important**: The conversation service must have a `memory_store_id` configured in its Maestro configuration, as TAC requires a memory store to initialize
- `twilio_phone_number` - Twilio Phone Number for Voice (inbound) and SMS (send/receive)

Basic optional configuration:
- `environment` - TAC environment ("dev", "stage", or "prod") - case-insensitive, automatically sets Memory and Maestro base URLs (defaults to "prod")

Optional configuration:
- `twilio_memory_config` - Optional TwilioMemoryConfig object with:
  - `trait_groups` field (list of strings) - Optional, specifies which trait groups to include in profile retrieval
  - TAC automatically fetches the `memory_store_id` from Maestro configuration and initializes the memory client. To enable automatic memory retrieval, set `auto_retrieve_memory=True` when creating the channel (default is False). Profile is fetched once for Voice at conversation start, per message for SMS.
- `conversation_intelligence_config` - Optional ConversationIntelligenceConfig object with:
  - `configuration_id` field (required) - CI Configuration ID
  - `observation_operator_sid` field (optional) - Operator SID for observation extraction (e.g., `LY...`)
  - `summary_operator_sid` field (optional) - Operator SID for summary extraction (e.g., `LY...`)
  - If operator SIDs are not set, falls back to friendly_name detection ("Summary Extractor" → summary, otherwise → observation)
  - Environment variables: `TWILIO_TAC_CI_CONFIGURATION_ID` (required), `TWILIO_TAC_CI_OBSERVATION_OPERATOR_SID` (optional), `TWILIO_TAC_CI_SUMMARY_OPERATOR_SID` (optional)
- `log_level` - Optional, defaults to "INFO"

## Logging

TAC uses structured logging with channel-specific logger names for easier debugging:
- **VoiceChannel**: Logs appear as `tac.channels.voice`
- **SMSChannel**: Logs appear as `tac.channels.sms`
- **BaseChannel**: Each channel automatically uses its module name for logging (via `self.__class__.__module__`)

This allows filtering logs by channel when debugging multi-channel applications:
```bash
# Filter for voice channel logs only
python server.py 2>&1 | grep "tac.channels.voice"

# Filter for SMS channel logs only
python server.py 2>&1 | grep "tac.channels.sms"
```

## Common Patterns

### SMS Channel Usage

```python
from tac import TAC, TACConfig
from tac.channels import SMSChannel
from tac.core.config import TwilioMemoryConfig

# 1. Setup TAC and SMS Channel
config = TACConfig(
    environment="prod",  # or "dev" or "stage"
    twilio_account_sid="AC...",
    twilio_auth_token="...",
    api_key="SK...",
    api_token="...",
    twilio_phone_number="+1234567890",
    conversation_service_sid="conv_configuration_...",
    twilio_memory_config=TwilioMemoryConfig(
        trait_groups=["Contact", "Preferences"]  # Optional: specify trait groups
    )  # Optional - configure memory settings like trait groups
)
tac = TAC(config)
sms_channel = SMSChannel(tac)

# 2. Register callback to handle message processing
def handle_message(user_message, context, memory_response=None):
    # Access profile traits if available (fetched per message for SMS)
    if context.profile:
        traits = context.profile.traits
        # Profile includes name, location, preferences, etc.

    llm_response = call_your_llm(user_message, memory_response, context.profile)
    sms_channel.send_response(context.conversation_id, llm_response)

tac.on_message_ready(handle_message)

# 3. In your webhook handler (FastAPI example)
@app.post('/webhook')
async def webhook(request: Request):
    # Extract idempotency token from headers for deduplication
    idempotency_token = request.headers.get("i-twilio-idempotency-token")

    # Fire and forget - process webhook asynchronously
    asyncio.create_task(sms_channel.process_webhook(request.json(), idempotency_token))

    # Return 200 immediately to prevent Twilio retries
    return {"status": "ok"}

# 4. Optional: Register callback for conversation end events
def handle_conversation_ended(context):
    print(f"Conversation {context.conversation_id} ended")
    # Clean up resources, log analytics, save summaries, etc.

tac.on_conversation_ended(handle_conversation_ended)

# 5. Optional: Configure deduplication capacity for high-traffic applications
# Default 10000 is suitable for most applications
sms_channel_high_traffic = SMSChannel(tac, dedup_capacity=50000)
```

### SMS Channel Deduplication

The SMS channel uses a defense-in-depth approach to prevent duplicate message processing:

**Two-Layer Defense:**

1. **Immediate 200 Response** (Primary Prevention):
   - Returns HTTP 200 immediately using `asyncio.create_task()` for fire-and-forget processing
   - Prevents Twilio from retrying webhooks (Twilio retries if no response within ~5 seconds)
   - Most effective way to prevent duplicates

2. **Idempotency-Based Deduplication** (Backup Protection):
   - Uses Twilio's `i-twilio-idempotency-token` header for deduplication
   - Tracks processed tokens using sliding window with configurable capacity (default: 10,000 tokens)
   - Same token = same webhook (retry), different tokens = different webhooks
   - O(1) performance using OrderedDict with FIFO removal when capacity reached
   - Logs duplicates at DEBUG level (not WARNING)

**Implementation:**
```python
# In your webhook handler
@app.post('/webhook')
async def webhook(request: Request):
    # Extract idempotency token from headers
    idempotency_token = request.headers.get("i-twilio-idempotency-token")

    # Process webhook asynchronously and return 200 immediately
    asyncio.create_task(sms_channel.process_webhook(webhook_data, idempotency_token))
    return JSONResponse(content={"status": "ok"}, status_code=200)
```

**Configuration:**
```python
# Default capacity (suitable for most apps)
channel = SMSChannel(tac)

# High-traffic production (increase capacity)
channel = SMSChannel(tac, dedup_capacity=50000)

# Low-resource testing (decrease capacity)
channel = SMSChannel(tac, dedup_capacity=1000)
```

**Capacity guidelines:**
- At 100 webhooks/sec: 10K capacity = 100 seconds of deduplication window
- At 10 webhooks/sec: 10K capacity = 16+ minutes of deduplication window
- Twilio webhook retries typically complete within ~15 minutes
- With immediate 200 response, retries are rare, so default capacity is sufficient for most applications

### SMS Channel Conversation Lifecycle

The SMS channel handles webhook events with channel-specific filtering:

1. **`participant.added`**: Initializes conversation session and tracks customer participants
   - **Filters by participant type**: Only processes CUSTOMER participants
   - **Filters by channel**: Only processes participants with at least one SMS address (uses structured channel data, not name prefixes)
   - **Voice conversation isolation**: Voice conversations are automatically filtered out because participants have VOICE addresses, not SMS addresses
   - Extracts `profile_id` from webhook data (supports both `profile_id` and `ProfileId`)
   - Calls `_start_conversation(conv_id, profile_id)` to store conversation session with profile
   - This is the primary entry point for creating conversation sessions

2. **`communication.created`**: Processes incoming messages
   - **Filters messages**: Ignores non-SMS messages, AI agent messages (from configured phone number), and empty/whitespace messages
   - Auto-initializes conversation if not already started (extracts `profile_id` from webhook) - fallback for race conditions
   - Fetches profile if `profile_id` is available (updates `context.profile` with fresh data)
   - Creates `ConversationSession` with `conversation_id`, `profile_id`, `channel`, `started_at`, and `profile`
   - Calls `tac.retrieve_memory(conversation_context, query=message_body)`
   - This triggers `on_message_ready` callback with `user_message`, `context`, and optional `memory_response`
   - `context.profile` contains profile traits if memory config includes `trait_groups`

3. **`conversation.updated`**: Selective conversation cleanup
   - Only processes conversations from the configured service (filters by `configuration_id`)
   - Only cleans up SMS conversations tracked locally (`channel == "sms"`)
   - Removes local session when conversation status is CLOSED
   - This ensures proper isolation when multiple TAC instances or services share the same Maestro configuration

**Important**: Profile ID must be included in webhook data as `profile_id` or `ProfileId` field.

**Note**: The SMS channel does not handle `conversation.created` events. Conversations are initialized on `participant.added` when a CUSTOMER participant with SMS addresses joins. This approach uses structured channel data (participant addresses) instead of naming conventions, making it more robust and future-proof.

### Voice Channel Usage

The Voice channel provides WebSocket protocol handling for Twilio ConversationRelay. TAC offers two approaches:

**Simplified Approach (Recommended for Getting Started):**

Use `TACServer` for automatic server setup with minimal boilerplate:

```python
from tac import TAC, TACConfig
from tac.channels.voice import VoiceChannel
from tac.core.config import TwilioMemoryConfig
from tac.server import TACServer

# 1. Setup TAC
config = TACConfig(
    environment="prod",  # or "dev" or "stage"
    twilio_account_sid="AC...",
    twilio_auth_token="...",
    api_key="SK...",
    api_token="...",
    twilio_phone_number="+1234567890",
    conversation_service_sid="conv_configuration_...",
    twilio_memory_config=TwilioMemoryConfig(
        trait_groups=["Contact", "Preferences"]  # Optional: specify trait groups
    )  # Optional - configure memory settings like trait groups
)
tac = TAC(config)

# 2. Register callback to handle memory-ready events
# Note: memory_response available when auto_retrieve_memory=True and Memory configured
# Profile is fetched once at conversation start for Voice
async def handle_memory(user_message, context, memory_response):
    llm_response = await call_your_llm(user_message, memory_response)
    await voice_channel.send_response(context.conversation_id, llm_response)

tac.on_message_ready(handle_memory)

# Optional: Register callback for conversation end events
async def handle_end(context):
    await save_summary(context.conversation_id)

tac.on_conversation_ended(handle_end)

# 3. Initialize channel and server
voice_channel = VoiceChannel(tac=tac)
server = TACServer(tac=tac, voice_channel=voice_channel)

# 4. Start server (creates FastAPI app with /twiml, /ws, /conversation-relay-callback endpoints)
server.start()
```

See `getting_started/examples/openai/openai_sdk.py` for a complete implementation.

**Manual Approach (For Advanced Use Cases):**

Create your own FastAPI application for full control over server configuration:

```python
from fastapi import FastAPI, WebSocket
from fastapi.responses import Response
from tac import TAC, TACConfig
from tac.channels.voice import VoiceChannel
from tac.core.config import TwilioMemoryConfig
from tac.server import FastAPIWebSocketAdapter

# 1. Setup TAC and Voice Channel
config = TACConfig(
    environment="prod",  # or "dev" or "stage"
    twilio_account_sid="AC...",
    twilio_auth_token="...",
    api_key="SK...",
    api_token="...",
    twilio_phone_number="+1234567890",
    conversation_service_sid="conv_configuration_...",
    twilio_memory_config=TwilioMemoryConfig(
        trait_groups=["Contact", "Preferences"]  # Optional: specify trait groups
    )  # Optional - configure memory settings like trait groups
)
tac = TAC(config)
voice_channel = VoiceChannel(tac)

# 2. Register callback to handle message processing
# memory_response available when auto_retrieve_memory=True and Memory configured
async def handle_message(user_message, context, memory_response=None):
    # Access profile traits if available (fetched once at conversation start for Voice)
    if context.profile:
        traits = context.profile.traits
        # Profile includes name, location, preferences, etc.

    llm_response = await call_your_llm(user_message, memory_response, context.profile)
    await voice_channel.send_response(context.conversation_id, llm_response)

tac.on_message_ready(handle_message)

# 3. Create FastAPI app with TwiML and WebSocket endpoints
app = FastAPI()

@app.get("/twiml")
async def get_twiml():
    conversation = tac.maestro_client.create_conversation()
    twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <ConversationRelay url="wss://your-domain.ngrok.io/ws">
            <Parameter name="conversationId" value="{conversation.id}" />
        </ConversationRelay>
    </Connect>
</Response>'''
    return Response(content=twiml, media_type="application/xml")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    adapter = FastAPIWebSocketAdapter(websocket)
    await voice_channel.handle_websocket(adapter)
```

See `getting_started/examples/openai/openai_sdk.py` for a complete implementation.

### Voice Channel Architecture

TAC provides two architectural patterns:

**Simplified Pattern (TACServer):**
- **Built-in Server**: `TACServer` creates FastAPI app with all required endpoints automatically
- **Convention over Configuration**: Opinionated defaults for quick starts
- **Use Case**: Getting started quickly, prototyping, simple voice applications
- **Install**: `pip install tac[server]`

**Manual Pattern (Custom FastAPI):**
- **Protocol Layer** (`VoiceChannel`): Framework-agnostic — handles WebSocket lifecycle, processes ConversationRelay messages, manages conversation state. Uses `WebSocketProtocol` abstraction.
- **Application Layer** (User's FastAPI app): Provides TwiML endpoint and WebSocket endpoint, uses `FastAPIWebSocketAdapter` to bridge FastAPI WebSocket to `WebSocketProtocol`
- **Benefits**: Separation of concerns, no forced dependencies, full control over server configuration
- **Use Case**: Custom middleware, authentication, integration with existing apps

### Voice Channel Conversation Lifecycle

The Voice channel handles conversation cleanup via ConversationRelay status callbacks:

**ConversationRelay Callback (`call_status == "completed"`):**
1. Lists all conversations associated with the call (by `channel_id`)
2. Filters conversations by `configuration_id` to only process conversations from the configured service
3. Closes each conversation via Maestro API (sets status to CLOSED)
4. Cleans up local session if it exists and channel is "voice"
5. This ensures proper isolation when multiple TAC instances or services share the same Maestro configuration

**Note**: Voice conversations are typically long-lived (duration of the call) and are cleaned up when the call ends, unlike SMS conversations which may close immediately after message exchange.

### Conversation Intelligence Webhook Processing

TAC automatically initializes the `OperatorResultProcessor` when both `twilio_memory_config` and `conversation_intelligence_config` are provided. Use `tac.process_cintel_event()` to process CI webhook events:

```python
from tac import TAC, TACConfig

# 1. Setup TAC with memory and CI configuration
# The CI processor (tac.ci_processor) is automatically initialized when both
# twilio_memory_config and conversation_intelligence_config are provided
tac = TAC(config=TACConfig.from_env())

# 2. Process CI webhook events using tac.process_cintel_event()
@app.post("/ci-webhook")
async def ci_webhook_handler(request: Request):
    payload = await request.json()
    result = await tac.process_cintel_event(payload)

    if result.success:
        if result.skipped:
            # Event was filtered (non-MEMORA_, test event, config mismatch, etc.)
            print(f"Skipped: {result.skip_reason}")
        else:
            # Observations or summaries created
            print(f"Created {result.created_count} {result.event_type}(s)")
    else:
        print(f"Error: {result.error}")

    return result.model_dump()
```

For advanced usage, you can also access the processor directly via `tac.ci_processor` or create one manually:

```python
from tac.core.config import ConversationIntelligenceConfig
from tac.intelligence import OperatorResultProcessor

ci_config = ConversationIntelligenceConfig(
    configuration_id="your_ci_configuration_id",
    observation_operator_sid="LY...",
    summary_operator_sid="LY...",
)
processor = OperatorResultProcessor(tac.memora_client, ci_config)
result = await processor.process_event(payload)
```

**Filtering Logic** (ported from Go transformer.go):
- Only processes events where `intelligence_configuration.friendly_name` starts with `MEMORA_`
- Filters out test events (patterns: `testserviceconfig`, `test_service`, `test-service`, `testservice`)
- Filters by `intelligence_configuration.id` matching `configuration_id` in config
- Filters by `operator.id` matching `observation_operator_sid` or `summary_operator_sid` in config

**Event Type Determination**:
- If `operator.id` matches `observation_operator_sid` → Creates observations
- If `operator.id` matches `summary_operator_sid` → Creates conversation summaries
- Otherwise → Skipped (operator SID mismatch)

## Dependencies

**Core Dependencies**:
- `pydantic>=2.0.0,<3` - Data validation
- `requests>=2.31.0,<3` - HTTP client
- `python-dotenv>=1.0.0,<2` - Environment variable loading
- `twilio>=9.8.3,<10` - Twilio Python SDK for messaging and other APIs

**Optional Dependencies**:
- `server` - TACServer support (batteries-included FastAPI server): `fastapi>=0.115.0,<1`, `uvicorn>=0.32.0,<1`, `python-multipart>=0.0.12`
- `dev` - Development tools: `pytest>=7.0.0,<8`, `pytest-cov>=5.0.0,<6`, `ruff>=0.8.0,<1`, `mypy>=1.0.0,<2`, `types-requests>=2.31.0,<3`, `openai>=1.0.0,<2`, `openai-agents>=0.1.0`, `fastapi`, `uvicorn`

**Note**: FastAPI and uvicorn are only required if using `TACServer` or creating your own FastAPI app with VoiceChannel. The core TAC package (including VoiceChannel) does not depend on them.

## Tools Integration

The tools module provides LLM-compatible tool definitions for integrating Twilio Sierra primitives with LLM runtimes:

### TACTool Class (`tools/base.py`)

The `TACTool` dataclass represents a tool/function for LLM integration:
- `name` - Function name
- `description` - What the tool does
- `params_json_schema` - JSON Schema for parameters (auto-generated from type hints)
- `implementation` - The actual function to execute

**Format Conversions**:
- `to_openai_format()` - Returns `{"type": "function", "function": {...}}` for OpenAI API
- `to_anthropic_format()` - Returns `{"name": "...", "description": "...", "input_schema": {...}}` for Anthropic API
- `to_json()` - JSON string representation (OpenAI format by default)

### Creating Tools

**Using `@function_tool()` decorator** (recommended):
```python
from tac.tools import function_tool

@function_tool()
def send_message(phone_number: str, message: str) -> bool:
    """
    Sends a message to a user.

    Args:
        phone_number: The phone number to send to
        message: The message content

    Returns:
        True on success, False on failure
    """
    # Implementation here
    return True
```

The decorator automatically:
- Extracts function name and docstring
- Generates JSON Schema from type hints (supports `str`, `int`, `bool`, `float`, `Optional`, `Literal`, `list`, `dict`, etc.)
- Tracks required vs optional parameters
- Creates TACTool instance

**Using `create_tool()` function**:
```python
from tac.tools import create_tool

tool = create_tool(
    name="send_message",
    description="Sends a message to a user",
    params_json_schema={
        "type": "object",
        "properties": {
            "phone_number": {"type": "string"},
            "message": {"type": "string"}
        },
        "required": ["phone_number", "message"]
    },
    implementation=my_function
)
```

### Built-in Tool Factories

**Messaging Tools** (`tools/messaging.py`):
```python
from tac.tools.messaging import create_messaging_tools

tools = create_messaging_tools(config)  # Returns [send_message]
```

**Memory Tools** (`tools/memory.py`):
```python
from tac.tools.memory import create_memory_tools

tools = create_memory_tools(config, session)  # Returns [retrieve_profile_memory]
```

Both factories return lists of `TACTool` objects configured with your TAC settings.

## Future Enhancements

Based on TAC.md architecture, these modules are planned but not yet implemented:
- **Adapters**: Runtime-specific adapters for OpenAI, Bedrock, Azure AI, LangChain (with `toOpenAiMessages()`, `toBedrockMessages()` formatting)
- **Additional Tools**: `twilio.escalate-to-human`, `twilio.session-memory.fetch`
- **Server**: ~~Standalone server package~~ **Implemented** as `tac.server` module (`TACServer`, `TACServerConfig`) — install with `pip install tac[server]`. Config auto-loads from `TWILIO_TAC_VOICE_PUBLIC_DOMAIN`, `TWILIO_TAC_SERVER_HOST`, `TWILIO_TAC_SERVER_PORT` env vars.
- **Analytics**: Integration with Twilio workbench observability

When implementing these features, refer to the detailed architecture diagrams and sequence flows in TAC.md.