# Twilio Agent Connect (TAC)

Twilio Agent Connect (TAC) is a powerful Python library designed to simplify the development of intelligent,
context-aware applications using Twilio's communication technologies. TAC provides seamless integration with Twilio's
Memory and Conversation services, enabling you to build LLM-powered agents with persistent memory and conversation context.

> [!NOTE]
> Looking for the JavaScript/TypeScript version? Check out [TAC SDK JS/TS](https://github.com/twilio/twilio-agent-connect-typescript).

Explore the [examples](examples) directory to see the SDK in action.

## Key Features

- **SMS Channel Support**: Built-in webhook handling for Twilio SMS conversations
- **Voice Channel Support**: WebSocket protocol handling for Twilio Voice with ConversationRelay
- **Conversation Intelligence**: Webhook processing for CI operator results to create observations and summaries in Memory
- **Memory Management**: Automatic integration with Twilio Memory for persistent user context
- **Conversation Lifecycle**: Automatic tracking of conversation sessions and state
- **Type-Safe**: Full type hints and Pydantic models throughout
- **Callback-Based**: Simple `on_message_ready` callback for LLM integration with optional memory retrieval
- **Production Ready**: Comprehensive test coverage and error handling

## Get Started

To get started, set up your Python environment (Python 3.9 or newer required), and then install TAC SDK package.

### uv (Recommended)

We recommend using [uv](https://docs.astral.sh/uv/) for the best development experience:

```bash
uv init
uv add git+https://github.com/twilio/twilio-agent-connect-python.git

# Install with server support (includes FastAPI and uvicorn for TACServer)
uv add git+https://github.com/twilio/twilio-agent-connect-python.git --extra server
```

### pip/venv (Alternative)

If you prefer using pip and venv:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install git+https://github.com/twilio/twilio-agent-connect-python.git

# Install with server support
pip install "git+https://github.com/twilio/twilio-agent-connect-python.git[server]"
```

## Quick Examples

Use the [Quickstart Wizard](examples/quickstart/) to automatically create Memory and Maestro services and generate your `.env` file for running examples (requires [uv](https://docs.astral.sh/uv/)):

```bash
git clone https://github.com/twilio/twilio-agent-connect-python.git
cd twilio-agent-connect-python
make quickstart  # Open http://localhost:8080
```

### SMS Channel with Memory

```python
from typing import Optional
from tac import TAC, TACConfig
from tac.channels.sms import SMSChannel
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse

# 1. Configure TAC - automatically loads from environment variables
# Set these in your .env file:
#   TWILIO_TAC_ENVIRONMENT=prod
#   TWILIO_TAC_ACCOUNT_SID=ACxxxxx...
#   TWILIO_TAC_AUTH_TOKEN=your_auth_token
#   TWILIO_TAC_PHONE_NUMBER=+1234567890
#   TWILIO_TAC_CONVERSATION_SERVICE_SID=conv_configuration_xxxxx...
#   TWILIO_TAC_MEMORY_STORE_ID=mem_service_xxxxx... (optional)
#   TWILIO_TAC_MEMORY_API_KEY=your_api_key (optional)
#   TWILIO_TAC_MEMORY_API_TOKEN=your_api_token (optional)

tac = TAC(config=TACConfig.from_env())

# 2. Register callback for when messages are processed
def handle_message_ready(
    user_message: str,
    context: ConversationSession,
    memory_response: Optional[TACMemoryResponse] = None
):
    """Called when message is received and memory is retrieved"""
    print(f"Conversation: {context.conversation_id}")
    print(f"Profile: {context.profile_id}")
    print(f"User message: {user_message}")

    if memory_response:
        print(f"Memories: {len(memory_response.observations)}")
        print(f"Communications: {len(memory_response.communications)}")

    # Process message and call your LLM with user message
    # llm_response = your_llm.generate(user_message, memory_response)
    # sms_channel.send_response(context.conversation_id, llm_response)

tac.on_message_ready(handle_message_ready)

# 3. Initialize SMS channel
sms_channel = SMSChannel(tac)

# 4. In your webhook handler (Flask example)
@app.route('/webhook', methods=['POST'])
def webhook():
    webhook_data = request.json
    sms_channel.process_webhook(webhook_data)
    return {"status": "ok"}
```

### Voice Channel with TACServer

For the fastest way to get started with voice, use `TACServer`:

```python
from typing import Optional
from tac import TAC, TACConfig
from tac.channels.voice import VoiceChannel
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse
from tac.server import TACServer

# 1. Configure TAC - automatically loads from environment variables
tac = TAC(config=TACConfig.from_env())

# 2. Register callback for when memories are retrieved
async def handle_message_ready(
    user_message: str,
    context: ConversationSession,
    memory_response: Optional[TACMemoryResponse] = None
):
    """Called when memory retrieval completes"""
    # Process memories and call your LLM
    # llm_response = await your_llm.generate(user_message, memory_response)
    # await voice_channel.send_response(context.conversation_id, llm_response)

tac.on_message_ready(handle_message_ready)

# 3. Initialize Voice channel and TACServer
voice_channel = VoiceChannel(tac=tac)

server = TACServer(tac=tac, voice_channel=voice_channel)

# 4. Start server (creates FastAPI app with /twiml, /ws, and callback endpoints)
server.start()
```

That's it! The server automatically:
- Creates FastAPI app
- Sets up POST /twiml endpoint for call handling
- Sets up WebSocket /ws endpoint for ConversationRelay
- Sets up POST /conversation-relay-callback endpoint
- Creates conversations and participants
- Handles all WebSocket protocol details

For manual control over FastAPI configuration, see [`examples/channels/voice.py`](examples/channels/voice.py).

## Configuration

TAC can be configured using environment variables (recommended) or programmatically.

> **Tip**: Use the [Quickstart Wizard](examples/quickstart/) (`make quickstart`) to automatically create Memory and Maestro services and generate a complete `.env` file.

### Using Environment Variables (Recommended)

Set these in your `.env` file and use `TACConfig.from_env()`:

```python
from tac import TAC, TACConfig

# Automatically loads all configuration from environment
tac = TAC(config=TACConfig.from_env())
```

**Required Environment Variables:**
- `TWILIO_TAC_ENVIRONMENT` - TAC environment: `"prod"`, `"stage"`, or `"dev"` (case-insensitive, sets Memory and Maestro URLs)
- `TWILIO_TAC_ACCOUNT_SID` - Your Twilio Account SID (e.g., `ACxxxxx...`)
- `TWILIO_TAC_AUTH_TOKEN` - Your Twilio Auth Token
- `TWILIO_TAC_CONVERSATION_SERVICE_SID` - Twilio Conversation Service SID (e.g., `conv_configuration_xxxxx...`)
- `TWILIO_TAC_PHONE_NUMBER` - Your Twilio Phone Number for Voice (inbound) and SMS (send/receive)

**Optional Environment Variables:**
- `TWILIO_TAC_LOG_LEVEL` - Logging level (default: `INFO`)
- `TWILIO_TAC_MEMORY_STORE_ID` - Memory Store ID (e.g., `mem_store_xxxxx...`)
- `TWILIO_TAC_MEMORY_API_KEY` - Twilio API Key SID (starts with `SK`)
- `TWILIO_TAC_MEMORY_API_TOKEN` - Twilio API Key Secret
- `TWILIO_TAC_TRAIT_GROUPS` - Comma-separated trait groups (e.g., `"Contact,Preferences"`)
- `TWILIO_TAC_CI_CONFIGURATION_ID` - CI Configuration ID - **Required for CI webhook processing**
- `TWILIO_TAC_CI_OBSERVATION_OPERATOR_SID` - Operator SID for observations (e.g., `LY...`) - Optional
- `TWILIO_TAC_CI_SUMMARY_OPERATOR_SID` - Operator SID for summaries (e.g., `LY...`) - Optional

### Manual Configuration

You can also configure TAC programmatically:

```python
from tac import TAC, TACConfig
from tac.core.config import TwilioMemoryConfig

config = TACConfig(
    environment="prod",
    twilio_account_sid="ACxxxxx...",
    twilio_auth_token="your_auth_token",
    twilio_phone_number="+1234567890",
    conversation_service_sid="conv_configuration_xxxxx...",
    twilio_memory_config=TwilioMemoryConfig(  # Optional
        memory_store_id="mem_service_xxxxx...",
        api_key="your_api_key",
        api_token="your_api_token",
        trait_groups=["Contact", "Preferences"],
    ),
)

tac = TAC(config=config)
```

## How It Works

### Message Flow (SMS/Voice)

1. **Webhook Received**: Twilio sends SMS webhook to your server
2. **Channel Processing**: `SMSChannel` validates and processes the event
3. **Memory Retrieval**: TAC optionally retrieves user memories from Memory
4. **Callback Invoked**: Your `on_message_ready` callback receives user message, context, and optional memory response
5. **LLM Integration**: Your code calls LLM with message and optional memories, sends response

### Conversation Intelligence Flow

1. **Webhook Received**: Twilio CI sends operator result webhook to your `/ci-webhook` endpoint
2. **Event Filtering**: `OperatorResultProcessor` filters by `MEMORA_` prefix and discards test events
3. **Profile Extraction**: Extracts profile IDs from event participants
4. **Content Generation**: Parses operator result based on output format (JSON, CLASSIFICATION, EXTRACTION, TEXT)
5. **Memory Creation**: Creates observations or conversation summaries in Memory for each profile

## Examples

Check out the [examples](examples) directory for complete working examples:

- **[`quickstart/`](examples/quickstart)**: Web-based setup wizard to create Memory and Maestro services and generate `.env` file
- **[`exec_demo/`](examples/exec_demo)**: Complete multi-channel demo with SMS and Voice support, OpenAI Agents integration, and custom business tools
- **[`servers/voice.py`](examples/servers/voice.py)**: **Recommended starting point** - Simplified voice server with automatic setup using TACServer
- **[`channels/sms.py`](examples/channels/sms.py)**: SMS webhook server with FastAPI and TAC integration
- **[`channels/voice.py`](examples/channels/voice.py)**: Voice server with manual FastAPI, TwiML generation, and WebSocket handling
- **[`channels/voice_escalation.py`](examples/channels/voice_escalation.py)**: Voice server with Flex escalation for agent handoff to humans
- **[`channels/voice_streaming.py`](examples/channels/voice_streaming.py)**: Voice streaming with interrupt support using ThreadSafeSessionManager

---

# TAC Development / Contribution

TAC uses [`uv`](https://docs.astral.sh/uv/) for package management. Ensure you have it installed:

```bash
uv --version
```

### Setup Development Environment

```bash
# Install all dependencies (including dev tools)
make sync

# Or manually with uv
uv sync --all-extras --all-packages
```

### Running Tests and Checks

```bash
# Format code
make format

# Run linting
make lint

# Run type checking
make type-check

# Run tests
make test

# Run all checks at once
make check
```

# TAC E2E Tests
[![Build status](https://badge.buildkite.com/c1f5e96e9ee98361b2c18d88d21ab22c948353f417d6e06215.svg?branch=main)](https://buildkite.com/twilio/tac-e2e-tests-python)
