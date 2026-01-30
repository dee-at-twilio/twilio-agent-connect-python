# TAC Server Examples

Simplified server implementations using TAC's built-in server configuration.

> **Prerequisites:** Complete the [Quick Start setup](../README.md#quick-start) in the main examples README before running these servers.

## Overview

The servers in this directory demonstrate the simplified approach to building TAC applications using built-in server configuration. Instead of manually creating FastAPI apps and routes, you can use TAC's server configuration objects to automatically handle endpoint setup.

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

Voice server using built-in `VoiceServerConfig` for automatic FastAPI app and endpoint setup.

**Additional Environment Variables:**
```bash
TWILIO_TAC_VOICE_PUBLIC_DOMAIN={your-ngrok-domain}  # Your ngrok or public domain
TWILIO_TAC_OPENAI_API_KEY=sk-xxxxx...  # For OpenAI LLM integration
```

**Features:**
- ✅ Automatic FastAPI app creation
- ✅ Automatic TwiML endpoint (`POST /twiml`)
- ✅ Automatic WebSocket endpoint (`WS /ws`)
- ✅ Automatic conversation and participant creation
- ✅ OpenAI integration for intelligent responses
- ✅ Memory retrieval and context management
- ✅ Conversation history management

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
1. VoiceServerConfig automatically creates FastAPI app with required endpoints
2. Twilio phone call arrives, webhook requests TwiML from `/twiml`
3. Server creates conversation and participant, generates TwiML with WebSocket URL
4. Voice channel establishes WebSocket connection via `/ws`
5. TAC retrieves memories (observations, summaries, sessions)
6. `handle_message_ready` callback invoked with context and memories
7. OpenAI generates response using conversation history
8. Response sent back via voice channel

**Key Code Pattern:**
```python
from tac import TAC, TACConfig, VoiceServerConfig
from tac.channels.voice import VoiceChannel

# Initialize TAC
tac = TAC(config=TACConfig(...))

# Register callback
async def handle_message_ready(user_message, context, memory_response):
    # Generate response with OpenAI
    response = await openai_client.chat.completions.create(...)
    await voice_channel.send_response(context.conversation_id, response)

tac.on_message_ready(handle_message_ready)

# Initialize channel with server configuration
voice_channel = VoiceChannel(
    tac=tac,
    server_config=VoiceServerConfig(
        public_domain=os.environ["TWILIO_TAC_VOICE_PUBLIC_DOMAIN"],
        host="0.0.0.0",
        port=8000,
        welcome_greeting="Hello! How can I assist you today?",
    ),
)

# That's it! Just call start() and everything is handled automatically
voice_channel.start()
```

**Comparison with Manual Approach:**

| Feature | Simplified (servers/) | Manual (channels/) |
|---------|----------------------|-------------------|
| FastAPI setup | Automatic | Manual |
| Endpoints | Auto-created | Manual routes |
| Conversation creation | Automatic | Manual |
| Boilerplate | Minimal | More control |
| Customization | Limited | Full control |

**VoiceServerConfig Options:**
- `public_domain` (required): Your public domain for WebSocket URL (e.g., `example.ngrok.io`)
- `host` (default: `"0.0.0.0"`): Host to bind the server to
- `port` (default: `8000`): Port to bind the server to
- `welcome_greeting` (default: `"Hello! How can I assist you today?"`): Initial greeting message

**For Advanced Features:**

If you need escalation, custom endpoints, or more control over the FastAPI app, see the manual approach in `examples/channels/`:
- `examples/channels/voice.py` - Manual voice server setup
- `examples/channels/voice_escalation.py` - Voice server with Flex escalation
