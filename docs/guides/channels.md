# Channels Guide

Channels handle the communication protocol specifics for each Twilio platform. This guide covers how to use and configure channels effectively.

## Available Channels

TAC provides five built-in channels:

| Channel | Use Case | Protocol |
|---------|----------|----------|
| **Voice** | Phone calls | ConversationRelay WebSocket + TwiML |
| **SMS** | Text messages | HTTP webhooks |
| **RCS** | Rich messaging | HTTP webhooks |
| **WhatsApp** | WhatsApp Business | HTTP webhooks |
| **Chat** | Multi-platform chat | HTTP webhooks |

## Basic Usage

### Single Channel

```python
from tac import TAC, TACConfig
from tac.channels.sms import SMSChannel

tac = TAC(config=TACConfig.from_env())
sms_channel = SMSChannel(tac)

async def handle_message(user_message, context, memory_response):
    return "Hello from SMS!"

tac.on_message_ready(handle_message)
```

### Multiple Channels

```python
from tac.channels.voice import VoiceChannel
from tac.channels.sms import SMSChannel
from tac.channels.whatsapp import WhatsAppChannel
from tac.server import TACFastAPIServer

tac = TAC(config=TACConfig.from_env())

TACFastAPIServer(
    tac=tac,
    voice_channel=VoiceChannel(tac),
    messaging_channels=[
        SMSChannel(tac),
        WhatsAppChannel(tac)
    ]
).start()
```

## Memory Modes

All channels support three memory retrieval modes:

### Never (Default)

No automatic memory retrieval:

```python
channel = SMSChannel(tac, memory_mode="never")
```

Use when:

- You don't need memory
- You'll manually call `tac.retrieve_memory()`
- Testing without Memory configured

### Always

Fetch memory on every message with semantic search:

```python
channel = VoiceChannel(tac, memory_mode="always")
```

The user's message is used as the query for semantic search. Best for:

- Conversations where context changes frequently
- When you need the most relevant memories per message

### Once

Fetch memory once at conversation start, cache until conversation ends:

```python
channel = SMSChannel(tac, memory_mode="once")
```

Memory is retrieved with an empty query (returns all/recent memories) and cached. Cache is invalidated when:

- Conversation status becomes INACTIVE
- Conversation ends
- Memory Store updates memories

Best for:

- Long conversations with stable context
- Reducing API calls
- Faster response times

## Voice Channel

Handles ConversationRelay WebSocket connections and TwiML generation.

### Configuration

```python
from tac.channels.voice import VoiceChannel, VoiceConfig

voice_config = VoiceConfig(
    welcome_message="Hello! How can I help you?",
    voice="Polly.Joanna-Neural",
    language="en-US",
    dtmf_detection=True
)

voice_channel = VoiceChannel(tac, config=voice_config, memory_mode="always")
```

### TwiML Generation

Voice channel automatically generates TwiML for call handling:

```python
# The /twiml endpoint returns:
<Response>
    <Start>
        <Stream url="wss://your-domain.com/ws" track="inbound_track"/>
    </Start>
    <Say voice="Polly.Joanna-Neural">Hello! How can I help you?</Say>
</Response>
```

### WebSocket Handling

The channel manages the WebSocket lifecycle:

1. **Connection**: Client connects to `/ws`
2. **Session start**: Receives configuration from Twilio
3. **Media streaming**: Processes audio in/out
4. **Message processing**: Triggers `on_message_ready` for transcripts
5. **Cleanup**: Handles disconnection and conversation end

### Voice-Specific Callbacks

```python
async def handle_call_connected(context):
    print(f"Call connected: {context.conversation_id}")

async def handle_call_ended(context):
    print(f"Call ended: {context.conversation_id}")

voice_channel.on_connected(handle_call_connected)
voice_channel.on_ended(handle_call_ended)
```

## Messaging Channels

SMS, RCS, WhatsApp, and Chat channels share similar webhook-based architecture.

### SMS Channel

```python
from tac.channels.sms import SMSChannel

sms_channel = SMSChannel(tac, memory_mode="once")

async def handle_sms(user_message, context, memory_response):
    # Access SMS-specific data
    from_number = context.from_
    to_number = context.to
    
    return f"Received your SMS: {user_message}"

tac.on_message_ready(handle_sms)
```

### WhatsApp Channel

```python
from tac.channels.whatsapp import WhatsAppChannel

whatsapp_channel = WhatsAppChannel(tac, memory_mode="always")

async def handle_whatsapp(user_message, context, memory_response):
    # WhatsApp-specific context
    from_number = context.from_  # e.g., "whatsapp:+1234567890"
    
    return "Thanks for your WhatsApp message!"

tac.on_message_ready(handle_whatsapp)
```

### RCS Channel

Rich Communication Services with media support:

```python
from tac.channels.rcs import RCSChannel

rcs_channel = RCSChannel(tac, memory_mode="once")

async def handle_rcs(user_message, context, memory_response):
    # RCS supports rich media
    return "RCS response with rich formatting support"

tac.on_message_ready(handle_rcs)
```

## Channel Context

Each channel provides context in the callback:

```python
async def handle_message(user_message, context, memory_response):
    # Common to all channels
    conversation_id = context.conversation_id
    profile_id = context.profile_id
    
    # Channel-specific
    from_number = context.from_
    to_number = context.to
    
    # For voice
    if hasattr(context, 'call_sid'):
        call_sid = context.call_sid
    
    return "Response"
```

## Manual Response Handling

By default, returning a string sends it as the response. For manual control, return `None`:

```python
async def handle_message(user_message, context, memory_response):
    # Process message
    response_text = "Custom response"
    
    # Send manually
    await sms_channel.send_response(response_text, context)
    
    # Return None to prevent auto-send
    return None
```

## Error Handling

Channels handle errors gracefully:

```python
async def handle_message(user_message, context, memory_response):
    try:
        # Your logic
        return "Success"
    except Exception as e:
        # Channel logs error but doesn't crash
        return "Sorry, something went wrong. Please try again."
```

## Next Steps

- [Memory Management](memory.md) - Memory retrieval strategies
- [Server Setup](server.md) - Deploying with channels
- [Architecture](architecture.md) - How channels work internally
