# TAC Channel Examples

Production-ready channel implementation examples for Twilio Agent Connect (TAC).

> **Prerequisites:** Complete the [Quick Start setup](../README.md#quick-start) in the main examples README before running these servers.

## Profile Traits (Optional Feature)

All examples support optional profile trait retrieval from Twilio Memory. When configured, profile traits are automatically fetched and made available in the callback context.

**Environment Variable:**
```bash
TRAIT_GROUPS="Contact,Preferences"  # Optional: Specify which trait groups to fetch
```

**Accessing Profile Traits in Callbacks:**
```python
async def handle_message_ready(user_message, context, memory_response=None):
    # Initialize conversation with system message
    if conv_id not in conversation_messages:
        system_msg = {"role": "system", "content": system_prompt}
        conversation_messages[conv_id] = [system_msg]

        # Add profile traits as context for personalized responses
        if context.profile:
            traits = context.profile.traits
            profile_context_parts = []

            # Extract contact information
            if "Contact" in traits:
                contact = traits["Contact"]
                if "firstName" in contact:
                    profile_context_parts.append(f"User's name: {contact['firstName']}")
                if "address" in contact:
                    city = contact["address"].get("city", "")
                    state = contact["address"].get("state", "")
                    if city and state:
                        profile_context_parts.append(f"Location: {city}, {state}")

            # Add as system message so LLM can personalize responses
            if profile_context_parts:
                profile_context = "User Profile:\n" + "\n".join(f"- {part}" for part in profile_context_parts)
                context_msg = {"role": "system", "content": profile_context}
                conversation_messages[conv_id].append(context_msg)

    # Now LLM can greet user by name: "Hello, John! How can I help you today?"
    # ...rest of your logic
```

**Behavior by Channel:**
- **SMS**: Profile fetched for each incoming message (fresh data)
- **Voice**: Profile fetched once at conversation start (cached for duration of call)

**When to Use:**
- Personalize responses based on user information
- Access user preferences and settings
- Retrieve contact details for context-aware assistance

## `sms.py` - SMS Webhook Server

FastAPI server to receive and process Twilio SMS webhooks with TAC, featuring complete OpenAI LLM integration.

**Additional Environment Variables:**
```bash
TWILIO_TAC_OPENAI_API_KEY=sk-xxxxx...  # For OpenAI LLM integration
```

**Features:**
- ✅ FastAPI server with `/sms` endpoint
- ✅ Async/await pattern for webhook handling
- ✅ OpenAI integration for intelligent responses
- ✅ Conversation history management
- ✅ Processes webhook events and validates into typed Maestro API models
- ✅ Processes with TAC and triggers memory callbacks
- ✅ SMS channel integration with conversation lifecycle

**Usage:**
```bash
# Start server on 0.0.0.0:8000
uv run python examples/channels/sms.py
```

**Setup Twilio Webhook:**

1. Start ngrok tunnel:
   ```bash
   ngrok http 8000 --domain={your-ngrok-domain}
   ```

2. Your ngrok URL will be `https://{your-ngrok-domain}`

3. Configure Twilio Conversations API Webhook:
   - Go to Twilio Console → Conversations → Configuration
   - Set "Post-Event Webhook URL" to: `https://{your-ngrok-domain}/sms`
   - Enable webhook events: `onMessageAdded`, `onConversationAdded`, `onConversationRemoved`

4. Send an SMS to your Twilio phone number - the webhook will be triggered automatically

**How It Works:**
1. Twilio sends SMS webhook to `/sms` endpoint
2. SMS channel processes webhook and validates message
3. TAC retrieves memories (observations, summaries, sessions)
4. `handle_message_ready` callback invoked with user message, context, and optional memory_response
5. OpenAI generates response using conversation history and optional memories
6. Response sent back via SMS channel

**Key Code Pattern:**
```python
from fastapi import FastAPI, Request
from tac.channels.sms import SMSChannel

# Initialize TAC and channel
tac = TAC(config)
sms_channel = SMSChannel(tac)

# Register callback
async def handle_message_ready(user_message, context, memory_response=None):
    # Generate response with OpenAI
    response = await openai_client.chat.completions.create(...)
    await sms_channel.send_response(context.conversation_id, response)

tac.on_message_ready(handle_message_ready)

# Create FastAPI app
app = FastAPI(title="TAC SMS Server")

@app.post("/sms")
async def sms_webhook(request: Request):
    webhook_data = await request.json()
    sms_channel.process_webhook(webhook_data)
    return {"status": "ok"}

# Start server
uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## `voice.py` - Simple Voice Channel Server

Basic voice server using `TACServer` for automatic endpoint setup. This is the recommended starting point for voice integration without escalation features.

**Additional Environment Variables:**
```bash
TWILIO_TAC_VOICE_PUBLIC_DOMAIN={your-ngrok-domain}  # Your ngrok or public domain
TWILIO_TAC_OPENAI_API_KEY=sk-xxxxx...  # For OpenAI LLM integration
```

**Features:**
- ✅ TACServer for automatic endpoint setup (TwiML, WebSocket, callback)
- ✅ OpenAI integration for conversational responses
- ✅ Memory retrieval and LLM integration (OpenAI)
- ✅ Proper message role handling (`role="assistant"`) for LLM context
- ✅ Conversation lifecycle management

**Usage:**
```bash
# 1. Add TWILIO_TAC_VOICE_PUBLIC_DOMAIN to your .env file
TWILIO_TAC_VOICE_PUBLIC_DOMAIN={your-ngrok-domain}

# 2. Start ngrok tunnel (in separate terminal)
ngrok http 8000 --domain={your-ngrok-domain}

# 3. Verify TWILIO_TAC_VOICE_PUBLIC_DOMAIN in .env matches your ngrok domain

# 4. Run voice server
uv run python examples/channels/voice.py

# 5. Configure Twilio phone number webhook to point to:
#    https://{your-ngrok-domain}/twiml
```

**How It Works:**
1. Twilio phone call arrives, webhook requests TwiML
2. TACServer generates TwiML with WebSocket URL
3. Voice channel establishes WebSocket connection via `/ws`
4. TAC retrieves memories (observations, summaries, sessions)
5. `handle_message_ready` callback invoked with user message, context, and optional memory_response
6. OpenAI generates response using conversation history and optional memories
7. Response sent back via voice channel

**Key Code Pattern:**
```python
from tac import TAC, TACConfig
from tac.channels.voice import VoiceChannel
from tac.server import TACServer

tac = TAC(config=TACConfig.from_env())
voice_channel = VoiceChannel(tac=tac)

async def handle_message_ready(user_message, context, memory_response=None):
    response = await openai_client.chat.completions.create(...)
    await voice_channel.send_response(context.conversation_id, response)

tac.on_message_ready(handle_message_ready)

server = TACServer(tac=tac, voice_channel=voice_channel)
server.start()
```

---

## `voice_streaming.py` - Voice Channel with Streaming & Interrupt Handling

Advanced voice server demonstrating streaming responses with interrupt support using `TACServer` and session management. This example shows how to stream LLM responses in real-time and handle user interruptions gracefully.

**Additional Environment Variables:**
```bash
TWILIO_TAC_VOICE_PUBLIC_DOMAIN={your-ngrok-domain}  # Your ngrok or public domain
TWILIO_TAC_OPENAI_API_KEY=sk-xxxxx...  # For OpenAI LLM integration
```

**Features:**
- ✅ All features from `voice.py` (TwiML, WebSocket, memory, LLM)
- ✅ Streaming responses with async generators for real-time delivery
- ✅ Interrupt handling - automatically cancels in-flight LLM requests when users interrupt
- ✅ Session management with `ThreadSafeSessionManager` for task tracking and cancellation
- ✅ Inline async generator pattern for clean streaming logic

**Usage:**
```bash
# 1. Add TWILIO_TAC_VOICE_PUBLIC_DOMAIN to your .env file
TWILIO_TAC_VOICE_PUBLIC_DOMAIN={your-ngrok-domain}

# 2. Start ngrok tunnel (in separate terminal)
ngrok http 8000 --domain={your-ngrok-domain}

# 3. Run voice streaming server
uv run python examples/channels/voice_streaming.py

# 4. Configure Twilio phone number webhook to point to:
#    https://{your-ngrok-domain}/twiml

# 5. Call your Twilio number and try interrupting the agent while it's speaking
```

**How It Works:**
1. User speaks → TAC retrieves memories → `on_message_ready` callback invoked
2. Callback creates async generator for streaming response
3. LLM generates response chunks in real-time
4. TAC streams chunks to user via WebSocket
5. **On interrupt:** Current streaming task is cancelled, new task starts with latest message

**Key Code Pattern:**
```python
from tac import TAC, TACConfig
from tac.channels.voice import VoiceChannel
from tac.server import TACServer
from tac.session import ThreadSafeSessionManager

# 1. Setup TAC
tac = TAC(config=TACConfig.from_env())

# 2. Initialize session manager for interrupt handling
session_manager = ThreadSafeSessionManager()

# 3. Initialize voice channel with session manager
voice_channel = VoiceChannel(tac=tac, session_manager=session_manager)

# 4. Register callback with inline async generator
async def handle_message_ready(user_message, context, memory_response):
    conv_id = context.conversation_id

    # Manage conversation history
    if conv_id not in conversation_messages:
        conversation_messages[conv_id] = [{"role": "system", "content": system_prompt}]
    conversation_messages[conv_id].append({"role": "user", "content": user_message})

    # Create inline async generator for streaming
    async def stream_response():
        stream = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=conversation_messages[conv_id],
            stream=True,
        )

        full_response = ""
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                full_response += chunk.choices[0].delta.content
                yield chunk.choices[0].delta.content

        conversation_messages[conv_id].append({"role": "assistant", "content": full_response})

    await voice_channel.send_response(conv_id, stream_response())

tac.on_message_ready(handle_message_ready)

# 5. Create and start server
server = TACServer(tac=tac, voice_channel=voice_channel)
server.start()
```

**When to Use:**
- You need real-time streaming responses for voice interactions
- Your LLM generates long responses that benefit from streaming
- You want to support user interruptions during agent responses
- You need task cancellation to avoid wasted LLM tokens on interrupted responses

---

## `voice_escalation.py` - Voice Channel with Flex Escalation (Manual FastAPI)

Advanced voice server demonstrating agent handoff to Twilio Flex for human escalation. This example uses manual FastAPI setup (instead of TACServer) because it requires a custom `/handoff` endpoint. Use this as a reference for building custom server configurations.

**Additional Environment Variables:**
```bash
TWILIO_TAC_VOICE_PUBLIC_DOMAIN={your-ngrok-domain}  # Your ngrok or public domain
TWILIO_TAC_OPENAI_API_KEY=sk-xxxxx...  # For OpenAI LLM integration
# Additional Flex configuration may be required
```

**Features:**
- ✅ All features from `voice.py` (TwiML, WebSocket, memory, LLM)
- ✅ Flex escalation tool integration
- ✅ OpenAI tool calling for intelligent escalation decisions
- ✅ `/handoff` endpoint for processing transfer requests
- ✅ Automatic detection of escalation requests (e.g., "speak to a human")
- ✅ Handoff handler registration with `tac.on_handoff()`

**Usage:**
```bash
# Same setup as voice.py, plus:
# 1. Ensure Flex workspace is configured
# 2. Run voice escalation server
uv run python examples/channels/voice_escalation.py

# 3. Configure Twilio phone number webhook to point to:
#    https://{your-ngrok-domain}/twiml
```

**How It Works:**
1. Voice call handled same as `voice.py`
2. AI agent monitors conversation for escalation requests
3. When user requests human assistance, LLM calls `flex_escalate_to_human` tool
4. Tool triggers handoff process via `/handoff` endpoint
5. Call transferred to available Flex agent
6. Conversation context preserved during transfer

**Key Code Pattern:**
```python
from tac.tools.flex_escalation import create_flex_escalation_tool
from tac.util.flex import handle_flex_handoff_logic

# Create escalation tool
# Get the active websocket for this conversation
active_websocket = voice_channel.get_websocket(context.conversation_id)
flex_escalation_tool = create_flex_escalation_tool(
    websocket=active_websocket
)

# Register handoff handler
def flex_handoff_handler(request_data):
    return handle_flex_handoff_logic(request_data)

tac.on_handoff(flex_handoff_handler)

# Use tool with OpenAI
completion = await client.chat.completions.create(
    model="gpt-4o",
    messages=conversation_messages[conv_id],
    tools=[flex_escalation_tool.to_openai_format()],
    tool_choice="auto",
)

# Add handoff endpoint
@app.post("/handoff")
async def handoff(request: Request):
    return await voice_channel.handle_handoff(request)
```

**When to Use:**
- You need agent-to-human escalation
- Your application integrates with Twilio Flex
- Conversations require human intervention for complex cases
- You want intelligent escalation based on user requests
