# TAC Multi-Channel Demo

A complete, production-ready example demonstrating how to build an AI-powered customer service agent using TAC with both SMS and Voice channels.

> **Prerequisites:** Complete the [Quick Start setup](../README.md#quick-start) in the main examples README before running this demo.

## Overview

This demo simulates **Owl Internet**, a fictional ISP's customer service agent that can:
- Handle customer inquiries via SMS and Voice
- Retrieve customer context and conversation history using TAC memory
- Look up internet plan pricing and process orders
- Provide personalized responses based on customer profile

**Use Case:** An internet service provider customer can text or call to inquire about plan upgrades, and the AI agent retrieves their current plan, offers relevant options, and processes orders.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Server                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  /sms        │  │  /twiml      │  │  /ws         │      │
│  │  SMS webhook │  │  TwiML gen   │  │  WebSocket   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
           │                  │                  │
           ▼                  ▼                  ▼
    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
    │ SMSChannel  │    │VoiceChannel │    │VoiceChannel │
    └─────────────┘    └─────────────┘    └─────────────┘
           │                  │                  │
           └──────────────────┴──────────────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │   TAC Core      │
                 │  Memory/Context │
                 └─────────────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │   LLM Service   │
                 │  (OpenAI Agent) │
                 └─────────────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ Business Tools  │
                 │ - look_up_order │
                 │ - confirm_order │
                 │ - look_up_price │
                 └─────────────────┘
```

## Files

- **`server.py`** - Main FastAPI server with SMS and Voice endpoints
- **`llm_service.py`** - LLM integration using OpenAI Agents SDK with tool calling
- **`tools.py`** - Business-specific tools (order lookup, pricing, confirmation)
- **`business_data.py`** - Company information and internet plan data

## Additional Environment Variables

In addition to the standard TAC configuration, this demo requires:

```bash
# Voice-specific (required for voice calls)
TWILIO_TAC_VOICE_PUBLIC_DOMAIN={your-ngrok-domain}

# OpenAI (required for LLM integration)
TWILIO_TAC_OPENAI_API_KEY=sk-xxxxx...
```

## Running the Demo

### 1. Start the Server

```bash
cd examples/exec_demo
uv run uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

The server will start on `http://0.0.0.0:8000` with:
- `/sms` - SMS webhook endpoint
- `/twiml` - Voice TwiML generation endpoint
- `/ws` - Voice WebSocket endpoint

### 2. Test with SMS

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

4. Send an SMS to your Twilio phone number to interact with the agent

### 3. Test with Voice

1. Start ngrok tunnel:
   ```bash
   ngrok http 8000 --domain={your-ngrok-domain}
   ```

2. Update `.env` with ngrok domain:
   ```bash
   TWILIO_TAC_VOICE_PUBLIC_DOMAIN={your-ngrok-domain}
   ```

3. Configure Twilio phone number webhook to: `https://{your-ngrok-domain}/twiml`

4. Call your Twilio phone number to interact with the voice agent

## Key Features

### 1. Multi-Channel Support

The same logic handles both SMS and Voice:

```python
# Channel detection in callback
if context.channel == "sms":
    await sms_channel.send_response(context.conversation_id, response)
elif context.channel == "voice":
    await voice_channel.send_response(context.conversation_id, response)
```

### 2. Memory Integration

TAC automatically retrieves customer context:

```python
async def handle_memory_ready(
    context: ConversationSession,
    memory_response: MemoryRetrievalResponse,
    user_message: str
):
    # Memory response contains:
    # - observations: User preferences, past interactions
    # - summaries: Conversation summaries
    # - sessions: Historical conversation sessions

    llm_response = await llm_service.process_message(
        user_message=user_message,
        memory_response=memory_response,
        profile_id=context.profile_id,
        conversation_history=conversation_messages[conv_id]
    )
```

### 3. Business Tools with OpenAI Agents SDK

Custom tools for business logic:

```python
@function_tool
async def look_up_order_price(plan_speed: str) -> str:
    """Get pricing for internet plan upgrade."""
    # Business logic here
    return pricing_info

@function_tool
async def confirm_order(plan_name: str, profile_id: str) -> str:
    """Confirm and process a plan upgrade order."""
    # Order processing logic
    return confirmation
```

The LLM agent automatically calls these tools when needed.

### 4. Conversation History Management

User-managed conversation history for context:

```python
conversation_messages: dict[str, list[ChatCompletionMessageParam]] = {}

# Add messages to history
conversation_messages[conv_id].append(user_msg)
conversation_messages[conv_id].append(assistant_msg)
```

## Example Conversation Flow

**Customer (via SMS):** "I want to upgrade my internet plan"

1. **Webhook received** → `/sms` endpoint
2. **SMS channel processes** → Extracts message, conversation ID, profile ID
3. **TAC retrieves memory** → Gets customer's current plan, preferences, history
4. **Memory ready callback** → Triggers with context and memories
5. **LLM processes** → Agent uses customer context + business tools
6. **Tool execution** → Calls `look_up_order_price("1000 Mbps")`
7. **Response generated** → "Based on your current 500 Mbps plan, you can upgrade to..."
8. **Response sent** → Via SMS channel back to customer

## Customization

### Adding New Tools

1. Define tool in `tools.py`:
   ```python
   @function_tool
   async def my_custom_tool(param: str) -> str:
       """Tool description."""
       # Implementation
       return result
   ```

2. Import in `llm_service.py` and add to agent tools

### Updating Business Data

Modify `business_data.py` to update:
- Company information
- Internet plans and pricing
- Any business-specific constants

### Changing LLM Model

Update in `llm_service.py`:
```python
self.agent = Agent(
    model="gpt-4o-mini",  # Change model here
    tools=[...],
    instructions="..."
)
```

## Dashboard

This demo includes a real-time web dashboard to visualize how TAC works.

**To view the dashboard:**
1. Start the server (see "Running the Demo" section above)
2. Open your browser and navigate to `http://localhost:8000/dashboard`
3. You'll see real-time updates as conversations happen:
   - User messages and AI responses
   - Memory retrieval operations
   - Multi-channel activity (SMS/Voice)
