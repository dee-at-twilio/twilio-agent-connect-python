# Quick Start

This guide will walk you through building your first TAC-powered AI agent in under 10 minutes.

## Prerequisites

Before starting, ensure you have:

- Python 3.10+ installed
- A Twilio account with API credentials
- Completed the [Twilio Setup](twilio-setup.md) (or have Memory Store and Conversation Configuration IDs)

## Step 1: Install TAC

```bash
pip install "twilio-agent-connect[server]" openai python-dotenv
```

## Step 2: Configure Environment

Create a `.env` file with your Twilio credentials:

```bash
# Twilio credentials
TWILIO_API_KEY=your_api_key
TWILIO_API_TOKEN=your_api_token
TWILIO_ACCOUNT_SID=your_account_sid

# TAC configuration
CONVERSATION_CONFIGURATION_ID=your_config_id

# OpenAI
OPENAI_API_KEY=your_openai_key
```

## Step 3: Create Your Agent

Create `app.py`:

```python
from dotenv import load_dotenv
from openai import AsyncOpenAI
from tac import TAC, TACConfig
from tac.adapters.openai import with_tac_memory
from tac.channels.sms import SMSChannel
from tac.channels.voice import VoiceChannel
from tac.server import TACFastAPIServer

load_dotenv()

# Initialize TAC
tac = TAC(config=TACConfig.from_env())
voice_channel = VoiceChannel(tac)
sms_channel = SMSChannel(tac)
openai_client = AsyncOpenAI()

# Store conversation history per conversation
conversation_history = {}

SYSTEM_INSTRUCTIONS = (
    "You are a helpful customer service agent. "
    "Keep responses short and conversational. "
    "Do not use markdown or emojis."
)

async def handle_message_ready(user_message, context, memory_response):
    """Called when a message is ready for processing."""
    conv_id = context.conversation_id

    # Initialize or retrieve conversation history
    if conv_id not in conversation_history:
        conversation_history[conv_id] = []
    
    conversation_history[conv_id].append({
        "role": "user",
        "content": user_message
    })

    # Wrap OpenAI client with TAC memory injection
    client = with_tac_memory(openai_client, memory_response, context)

    # Generate response
    response = await client.responses.create(
        model="gpt-5.4-mini",
        instructions=SYSTEM_INSTRUCTIONS,
        input=conversation_history[conv_id]
    )

    llm_response = response.output_text
    conversation_history[conv_id].append({
        "role": "assistant",
        "content": llm_response
    })

    return llm_response

# Register callback
tac.on_message_ready(handle_message_ready)

# Start server
TACFastAPIServer(
    tac=tac,
    voice_channel=voice_channel,
    messaging_channels=[sms_channel]
).start()
```

## Step 4: Run Your Agent

```bash
python app.py
```

Your server will start on `http://localhost:8000` with these endpoints:

- `/twiml` - Voice call entry point
- `/ws` - WebSocket for ConversationRelay
- `/webhook` - Messaging webhooks (SMS, WhatsApp, etc.)

## Step 5: Test It Out

### Option A: Use ngrok for Testing

```bash
# Install ngrok
brew install ngrok  # macOS
# or download from https://ngrok.com/

# Expose your local server
ngrok http 8000
```

Configure your Twilio phone number webhooks to point to your ngrok URL:

- Voice: `https://your-ngrok-url.ngrok.io/twiml`
- SMS: `https://your-ngrok-url.ngrok.io/webhook`

### Option B: Deploy to Production

See the [Server Setup Guide](../guides/server.md) for deployment options.

## What Just Happened?

Let's break down the code:

1. **TAC Initialization**: Loads configuration from environment variables
2. **Channel Setup**: Creates Voice and SMS channels
3. **Callback Registration**: `on_message_ready` processes each message
4. **Memory Injection**: `with_tac_memory()` automatically adds user context to OpenAI calls
5. **Server Creation**: `TACFastAPIServer` handles all webhook routing

## Next Steps

### Add More Channels

```python
from tac.channels.whatsapp import WhatsAppChannel
from tac.channels.rcs import RCSChannel

whatsapp = WhatsAppChannel(tac)
rcs = RCSChannel(tac)

TACFastAPIServer(
    tac=tac,
    voice_channel=voice_channel,
    messaging_channels=[sms_channel, whatsapp, rcs]
).start()
```

### Enable Memory Retrieval

Configure when to fetch user memories:

```python
voice_channel = VoiceChannel(tac, memory_mode="always")
sms_channel = SMSChannel(tac, memory_mode="once")
```

Options:

- `"never"` (default): No memory retrieval
- `"always"`: Fetch on every message with semantic search
- `"once"`: Fetch once at conversation start, cache results

### Add Tools

Give your agent capabilities:

```python
from tac.tools import function_tool

@function_tool
async def get_order_status(order_id: str) -> str:
    """Check the status of an order."""
    # Your logic here
    return f"Order {order_id} is in transit"

# Use with OpenAI
tools = [get_order_status.to_openai_tool()]
```

### Handle Conversation End

```python
async def handle_conversation_ended(context):
    """Called when conversation ends."""
    conv_id = context.conversation_id
    if conv_id in conversation_history:
        del conversation_history[conv_id]
    print(f"Conversation {conv_id} ended")

tac.on_conversation_ended(handle_conversation_ended)
```

## Common Issues

### "Configuration not found"

Make sure your `.env` file contains valid IDs and your Twilio credentials are correct.

### "Port 8000 already in use"

Change the port:

```python
TACFastAPIServer(...).start(host="0.0.0.0", port=8080)
```

### Memory not working

Verify:

1. Your Conversation Configuration has a Memory Store configured
2. Memory mode is set to `"always"` or `"once"`
3. Your Twilio account has Conversation Memory enabled

## Learn More

- [Architecture Guide](../guides/architecture.md) - Understand how TAC works
- [Channels Guide](../guides/channels.md) - Deep dive into channels
- [Memory Management](../guides/memory.md) - Memory retrieval strategies
- [Examples](../examples/index.md) - More code examples
