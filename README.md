# Twilio Agent Connect (TAC)

Twilio Agent Connect (TAC) is a powerful Python library designed to simplify the development of intelligent,
context-aware applications using Twilio's communication technologies. TAC provides seamless integration with Twilio's
Memory Store and Conversation Configuration, enabling you to build LLM-powered agents with persistent memory and conversation context.

> [!NOTE]
> Looking for the JavaScript/TypeScript version? Check out [TAC SDK JS/TS](https://github.com/twilio-innovation/twilio-agent-connect-typescript).

Explore the [getting_started](getting_started) directory to see the SDK in action.

## Key Features

- **SMS Channel Support**: Built-in webhook handling for Twilio SMS conversations
- **Voice Channel Support**: WebSocket protocol handling for Twilio Voice with ConversationRelay
- **Memory Management**: Automatic integration with Twilio Memory for persistent user context
- **Conversation Lifecycle**: Automatic tracking of conversation sessions and state
- **Type-Safe**: Full type hints and Pydantic models throughout
- **Callback-Based**: Simple `on_message_ready` callback for LLM integration with optional memory retrieval
- **Production Ready**: Comprehensive test coverage and error handling

## Get Started

To get started, set up your Python environment (Python 3.10 or newer required), and then install TAC SDK package.

### uv (Recommended)

We recommend using [uv](https://docs.astral.sh/uv/) for the best development experience:

```bash
uv init
uv add git+https://github.com/twilio-innovation/twilio-agent-connect-python.git

# Install with server support (includes FastAPI and uvicorn for TACFastAPIServer)
uv add git+https://github.com/twilio-innovation/twilio-agent-connect-python.git --extra server
```

### pip/venv (Alternative)

If you prefer using pip and venv:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install git+https://github.com/twilio-innovation/twilio-agent-connect-python.git

# Install with server support
pip install "git+https://github.com/twilio-innovation/twilio-agent-connect-python.git[server]"
```

## Quick Examples

**Option 1: Use the Setup Wizard**

Use the [Twilio Setup Wizard](getting_started/twilio_setup/) to automatically create a Memory Store and Conversation Configuration and generate your `.env` file:

```bash
git clone https://github.com/twilio-innovation/twilio-agent-connect-python.git
cd twilio-agent-connect-python
make setup  # Open http://localhost:8080
```

**Option 2: Manual Setup**

You can also create a Memory Store and Conversation Configuration manually through the [Twilio Console](https://1console.twilio.com).

---

After completing setup, here's a minimal example to get started:

### Multi-Channel with OpenAI SDK

Use the OpenAI adapter to automatically inject conversation memory and user context into your OpenAI API calls across both Voice and SMS channels.

First, install the required packages:

```bash
uv add openai python-dotenv
```

> **Note**: `python-dotenv` is optional — TAC works with environment variables from any source (`.env` files, Docker, Kubernetes, CI/CD, shell exports, etc.).

Then create your application:

```python
from dotenv import load_dotenv
from openai import AsyncOpenAI
from tac import TAC, TACConfig
from tac.adapters.openai import with_tac_memory
from tac.channels.sms import SMSChannel
from tac.channels.voice import VoiceChannel
from tac.server import TACFastAPIServer

load_dotenv()

tac = TAC(config=TACConfig.from_env())
voice_channel = VoiceChannel(tac)
sms_channel = SMSChannel(tac)
openai_client = AsyncOpenAI()

conversation_history = {}
SYSTEM_INSTRUCTIONS = "You are a helpful customer service agent. Be concise and friendly."

async def handle_message_ready(user_message, context, memory_response):
    conv_id = context.conversation_id

    if conv_id not in conversation_history:
        conversation_history[conv_id] = []
    conversation_history[conv_id].append({"role": "user", "content": user_message})

    client = with_tac_memory(openai_client, memory_response, context)

    response = await client.responses.create(
        model="gpt-5.4-mini",
        instructions=SYSTEM_INSTRUCTIONS,
        input=conversation_history[conv_id]
    )

    llm_response = response.output_text
    conversation_history[conv_id].append({"role": "assistant", "content": llm_response})

    return llm_response

tac.on_message_ready(handle_message_ready)
TACFastAPIServer(tac=tac, voice_channel=voice_channel, messaging_channels=[sms_channel]).start()
```

> **Note**: See the [getting started guide](getting_started/README.md) for complete setup instructions and `.env` configuration details.

**That's it!** The server automatically:
- Creates FastAPI app with `/twiml`, `/ws`, and `/webhook` endpoints
- Handles both Voice and SMS conversations
- Routes responses to the appropriate channel
- Injects conversation memory and user profile into OpenAI calls

For configuration details and environment variables, see the [getting started guide](getting_started/README.md).

## How It Works

TAC simplifies building AI agents by handling the integration between Twilio's communication channels and your LLM:

### Message Flow

1. **Webhook/Connection Received**: Twilio sends webhook (SMS) or WebSocket connection (Voice) to your server
2. **Channel Processing**: Channel validates and processes the incoming event
3. **Memory Retrieval**: TAC optionally retrieves user memories and profile from Memory
4. **Callback Invoked**: Your `on_message_ready` callback receives user message, context, and optional memory response
5. **Response Handling**: Your callback returns a response string that TAC routes to the appropriate channel

For detailed architecture and advanced usage, see [CLAUDE.md](CLAUDE.md).

## Learn More

**Examples & Guides:**
- **[Getting Started Guide](getting_started/)** - Setup wizard, examples, and comprehensive documentation
- **[OpenAI SDK Example](getting_started/examples/openai/)** - Complete multi-channel example with Voice and SMS
- More examples coming soon

**Documentation:**
- **[CLAUDE.md](CLAUDE.md)** - Architecture, development guide, and API reference
- **[Getting Started Guide](getting_started/README.md)** - Setup instructions, environment variables, and troubleshooting

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
