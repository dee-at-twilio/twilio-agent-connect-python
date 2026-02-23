# TAC Server Examples

Simplified server implementations using TAC's built-in `TACServer`.

> **Prerequisites:** Complete the [Quick Start setup](../README.md#quick-start) in the main examples README before running these servers.

## Overview

The servers in this directory demonstrate the simplified approach to building TAC applications using `TACServer`. Instead of manually creating FastAPI apps and routes, `TACServer` automatically handles endpoint setup for voice, SMS, and CI webhooks.

**When to Use:**
- You want a quick way to get started with minimal boilerplate
- You prefer convention over configuration
- You don't need custom middleware or advanced FastAPI features

**When to Use Manual Approach (see `examples/channels/`):**
- You need full control over FastAPI configuration
- You want custom middleware, authentication, or rate limiting
- You're integrating TAC into an existing FastAPI application

---

## `voice.py` - Simplified Voice Server

Voice server using `TACServer` for automatic FastAPI app and endpoint setup.

**Additional Environment Variables:**
```bash
TWILIO_TAC_VOICE_PUBLIC_DOMAIN={your-ngrok-domain}  # Your ngrok or public domain
TWILIO_TAC_OPENAI_API_KEY=sk-xxxxx...  # For OpenAI LLM integration
```

**Features:**
- ✅ Automatic FastAPI app creation
- ✅ Automatic TwiML endpoint (`POST /twiml`)
- ✅ Automatic WebSocket endpoint (`WS /ws`)
- ✅ Automatic ConversationRelay callback endpoint (`POST /conversation-relay-callback`)
- ✅ Automatic conversation and participant creation
- ✅ OpenAI integration for intelligent responses
- ✅ Memory retrieval and context management
- ✅ Conversation history management
- ✅ Supports both streaming and non-streaming responses

**Usage:**
```bash
# 1. Add TWILIO_TAC_VOICE_PUBLIC_DOMAIN to your .env file
TWILIO_TAC_VOICE_PUBLIC_DOMAIN={your-ngrok-domain}

# 2. Start ngrok tunnel (in separate terminal)
ngrok http 8000 --domain={your-ngrok-domain}

# 3. Verify TWILIO_TAC_VOICE_PUBLIC_DOMAIN in .env matches your ngrok domain

# 4. Run simplified voice server
uv run python examples/servers/voice.py

# 5. Configure Twilio phone number webhook to point to:
#    https://{your-ngrok-domain}/twiml
```

**How It Works:**
1. `TACServer` creates a FastAPI app with required endpoints
2. Twilio phone call arrives, webhook requests TwiML from `/twiml`
3. Server creates conversation and participant, generates TwiML with WebSocket URL
4. Voice channel establishes WebSocket connection via `/ws`
5. TAC retrieves memories (observations, summaries, sessions)
6. `handle_message_ready` callback invoked with context and memories
7. OpenAI generates response using conversation history
8. Response sent back via voice channel

**Key Code Pattern:**
```python
from tac import TAC, TACConfig
from tac.channels.voice import VoiceChannel
from tac.server import TACServer

# Initialize TAC
tac = TAC(config=TACConfig.from_env())

# Register callback for non-streaming responses
async def handle_message_ready(user_message, context, memory_response):
    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": user_message}]
    )
    content = response.choices[0].message.content
    await voice_channel.send_response(context.conversation_id, content)

tac.on_message_ready(handle_message_ready)

# Initialize channel and start server
voice_channel = VoiceChannel(tac=tac)

server = TACServer(tac=tac, voice_channel=voice_channel)
server.start()
```

**Streaming Pattern with Interrupt Handling:**

```python
from tac.session import ThreadSafeSessionManager

# Register callback for streaming responses
async def handle_message_ready(user_message, context, memory_response):
    async def stream_response():
        stream = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": user_message}],
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    await voice_channel.send_response(context.conversation_id, stream_response())

tac.on_message_ready(handle_message_ready)

# For interrupt handling, add session manager
session_manager = ThreadSafeSessionManager()
voice_channel = VoiceChannel(tac=tac, session_manager=session_manager)

server = TACServer(tac=tac, voice_channel=voice_channel)
server.start()
```

**Comparison with Manual Approach:**

| Feature | Simplified (servers/) | Manual (channels/) |
|---------|----------------------|-------------------|
| FastAPI setup | Automatic | Manual |
| Endpoints | Auto-created | Manual routes |
| Conversation creation | Automatic | Manual |
| Boilerplate | Minimal | More control |
| Customization | Limited | Full control |

**TACServerConfig Options (via env vars or constructor):**
- `TWILIO_TAC_VOICE_PUBLIC_DOMAIN` / `public_domain`: Your public domain for WebSocket URL (required for voice)
- `TWILIO_TAC_SERVER_HOST` / `host` (default: `"0.0.0.0"`): Host to bind the server to
- `TWILIO_TAC_SERVER_PORT` / `port` (default: `8000`): Port to bind the server to
- `welcome_greeting` (default: `"Hello! How can I assist you today?"`): Initial greeting message
- `sms_webhook_path` (default: `"/webhook"`): Path for SMS webhook endpoint
- `twiml_path` (default: `"/twiml"`): Path for TwiML generation endpoint
- `websocket_path` (default: `"/ws"`): Path for voice WebSocket endpoint
- `conversation_relay_callback_path` (default: `"/conversation-relay-callback"`): Path for callback endpoint
- `cintel_webhook_path` (default: `None`): Path for Conversation Intelligence webhook endpoint

**For Advanced Features:**

If you need escalation, custom endpoints, or more control over the FastAPI app, see the manual approach in `examples/channels/`:
- `examples/channels/voice.py` - Manual voice server setup
- `examples/channels/voice_streaming.py` - Detailed streaming example with session management
- `examples/channels/voice_escalation.py` - Voice server with Flex escalation
