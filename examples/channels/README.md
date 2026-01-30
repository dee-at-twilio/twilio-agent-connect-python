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

Basic voice server with FastAPI, TwiML generation, and WebSocket handling for Twilio Voice. This is the recommended starting point for voice integration without escalation features.

**Additional Environment Variables:**
```bash
TWILIO_TAC_VOICE_PUBLIC_DOMAIN={your-ngrok-domain}  # Your ngrok or public domain
TWILIO_TAC_OPENAI_API_KEY=sk-xxxxx...  # For OpenAI LLM integration
```

**Features:**
- ✅ FastAPI server with `/twiml` and `/ws` endpoints
- ✅ TwiML generation for incoming voice calls
- ✅ WebSocket connection management via `VoiceChannel.handle_websocket()`
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
2. `/twiml` endpoint generates TwiML with WebSocket URL
3. Voice channel establishes WebSocket connection via `/ws`
4. TAC retrieves memories (observations, summaries, sessions)
5. `handle_message_ready` callback invoked with user message, context, and optional memory_response
6. OpenAI generates response using conversation history and optional memories
7. Response sent back via voice channel

**Key Code Pattern:**
```python
from fastapi import FastAPI, Form, WebSocket
from tac.channels.voice import VoiceChannel

# Initialize TAC and channel
tac = TAC(config)
voice_channel = VoiceChannel(tac)

# Register callback
async def handle_message_ready(user_message, context, memory_response=None):
    # Generate response with OpenAI
    response = await openai_client.chat.completions.create(...)
    await voice_channel.send_response(context.conversation_id, response)

tac.on_message_ready(handle_message_ready)

# Create FastAPI app
app = FastAPI(title="TAC Voice Server")

@app.post("/twiml")
async def post_twiml(From: str = Form(...)):
    websocket_url = f"wss://{public_domain}/ws"
    twiml = voice_channel.handle_incoming_call(
        websocket_url=websocket_url,
        called_phone_number=From,
        welcome_greeting="Hello! How can I assist you today?"
    )
    return Response(content=twiml, media_type="application/xml")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await voice_channel.handle_websocket(websocket)

# Start server
uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## `voice_escalation.py` - Voice Channel with Flex Escalation

Advanced voice server demonstrating agent handoff to Twilio Flex for human escalation. Use this example when you need to transfer calls from AI agents to human agents.

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

---

## `voice_interrupts.py` - Voice Channel with Custom Streaming Agent

Advanced voice server demonstrating custom agent streaming with session management for handling interrupts and canceling in-flight LLM requests. This example shows how to integrate **any AI agent framework** with TAC's voice channel using a platform-agnostic streaming pattern.

**Additional Environment Variables:**
```bash
TWILIO_TAC_VOICE_PUBLIC_DOMAIN={your-ngrok-domain}  # Your ngrok or public domain
WEBSOCKET_PORT=8080  # Port for WebSocket server
TWILIO_TAC_OPENAI_API_KEY=sk-xxxxx...  # For this example (can be any LLM)
```

**Features:**
- ✅ Platform-agnostic streaming agent integration
- ✅ Session management for interrupt handling
- ✅ Automatic cancellation of in-flight LLM tasks when user interrupts
- ✅ Custom conversation history management
- ✅ Works with any LLM provider (OpenAI, Anthropic, local models, etc.)
- ✅ Real-time streaming response delivery via WebSocket

**Usage:**
```bash
# 1. Add configuration to .env
TWILIO_TAC_VOICE_PUBLIC_DOMAIN={your-ngrok-domain}
WEBSOCKET_PORT=8080

# 2. Start ngrok tunnel
ngrok http 8080 --domain={your-ngrok-domain}

# 3. Run voice server with streaming
uv run python examples/channels/voice_interrupts.py

# 4. Configure Twilio phone number webhook to:
#    https://{your-ngrok-domain}/twiml
```

**How It Works:**

The key to this example is the `stream_generator` function - a platform-agnostic async generator that yields response chunks:

```python
async def stream_openai_response(prompt: str, session_id: str) -> AsyncGenerator[str, None]:
    """
    Platform-agnostic streaming function.
    
    Args:
        prompt: User's message (e.g., transcribed speech from voice channel)
        session_id: Conversation/session identifier for context tracking
        
    Yields:
        Text chunks to be sent to the user
    """
    # 1. Manage your conversation history however you want
    if session_id not in conversation_messages:
        conversation_messages[session_id] = [{"role": "system", "content": system_prompt}]
    
    conversation_messages[session_id].append({"role": "user", "content": prompt})
    
    # 2. Stream from ANY LLM provider - OpenAI, Anthropic, local models, etc.
    client = openai.AsyncOpenAI()  # Could be any async streaming client
    stream = await client.chat.completions.create(
        model="gpt-4o",
        messages=conversation_messages[session_id],
        stream=True,
    )
    
    # 3. Yield chunks - TAC handles WebSocket delivery and cancellation
    full_response = ""
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            full_response += content
            yield content  # ← Framework sends this to WebSocket
    
    # 4. Save assistant response to your history
    conversation_messages[session_id].append({"role": "assistant", "content": full_response})
```

**Session Manager Setup:**

The `ThreadSafeSessionManager` wraps your streaming function and handles task lifecycle:

```python
from tac.channels.session_manager import ThreadSafeSessionManager
from tac.channels.voice import VoiceChannel

# Initialize with your custom streaming function
session_manager = ThreadSafeSessionManager(stream_generator=stream_openai_response)

# Pass to VoiceChannel - enables interrupt handling
voice_channel = VoiceChannel(tac=tac, session_manager=session_manager)
```

**What Happens During Interrupts:**

1. User speaks → New prompt arrives
2. Session manager **cancels** the current streaming task (stops LLM generation)
3. New streaming task starts immediately with the latest prompt
4. Previous incomplete response is discarded
5. User gets responsive experience without waiting for old response to finish

**Adapting for Your Agent:**

This pattern works with **any async streaming source**:

```python
# Anthropic example
async def stream_anthropic_response(prompt: str, session_id: str):
    client = anthropic.AsyncAnthropic()
    async with client.messages.stream(
        model="claude-3-5-sonnet-20241022",
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for text in stream.text_stream:
            yield text

# Local model example (e.g., Ollama)
async def stream_local_model(prompt: str, session_id: str):
    async with aiohttp.ClientSession() as session:
        async with session.post('http://localhost:11434/api/generate',
            json={"model": "llama2", "prompt": prompt, "stream": True}
        ) as resp:
            async for line in resp.content:
                data = json.loads(line)
                if 'response' in data:
                    yield data['response']

# Use with session manager
session_manager = ThreadSafeSessionManager(stream_generator=stream_local_model)
```

**Key Benefits:**

- **No vendor lock-in** - Use any LLM provider or custom agent
- **Full control** - Manage your own context, history, and prompting strategy
- **Interrupt handling** - Framework handles task cancellation automatically
- **Minimal overhead** - Just implement one async generator function
- **Production ready** - Thread-safe session management included

**When to Use:**

- You want full control over your agent's streaming logic
- You're using a custom LLM or agent framework
- You need responsive voice interactions with interrupt support
- You want to manage conversation history your own way
- You're building a multi-turn conversational voice agent

