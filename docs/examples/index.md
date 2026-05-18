# Examples

TAC comes with comprehensive examples demonstrating various integration patterns and use cases.

## Example Repository Structure

All examples are located in the [`getting_started/examples`](https://github.com/twilio/twilio-agent-connect-python/tree/main/getting_started/examples) directory:

```
getting_started/examples/
├── partners/           # Partner SDK integrations
│   ├── openai_*.py    # OpenAI examples
│   ├── bedrock_*.py   # AWS Bedrock examples
│   └── strands_*.py   # AWS Strands examples
└── features/          # Feature-specific examples
    ├── chat/          # Chat channel
    ├── dashboard/     # Monitoring dashboard
    └── relay_only.py  # ConversationRelay-only mode
```

## Partner Integrations

### OpenAI

- [OpenAI Chat Completions](openai.md#chat-completions-api) - Using the Chat Completions API
- [OpenAI Responses API](openai.md#responses-api) - Using the new Responses API
- [OpenAI Agents SDK](openai.md#agents-sdk) - Integrating with OpenAI Agents

### AWS

- [AWS Bedrock Agent](aws.md#bedrock-agent) - AWS Bedrock Agent integration
- [AWS Bedrock AgentCore](aws.md#bedrock-agentcore) - AWS Bedrock AgentCore integration
- [AWS Strands](aws.md#strands) - AWS Strands agent integration

## Feature Examples

### ConversationRelay-Only Mode

Start with just voice (no Orchestrator or Memory):

```python
from tac import TAC, TACConfig
from tac.channels.voice import VoiceChannel

config = TACConfig(
    api_key=os.getenv("TWILIO_API_KEY"),
    api_token=os.getenv("TWILIO_API_TOKEN"),
    # No conversation_configuration_id
)

tac = TAC(config=config)
voice_channel = VoiceChannel(tac)

# Your voice handling logic
```

[View full example →](https://github.com/twilio/twilio-agent-connect-python/blob/main/getting_started/examples/features/relay_only.py)

### Multi-Channel Support

Handle Voice, SMS, WhatsApp, and RCS simultaneously:

```python
from tac.channels.voice import VoiceChannel
from tac.channels.sms import SMSChannel
from tac.channels.whatsapp import WhatsAppChannel
from tac.channels.rcs import RCSChannel
from tac.server import TACFastAPIServer

TACFastAPIServer(
    tac=tac,
    voice_channel=VoiceChannel(tac),
    messaging_channels=[
        SMSChannel(tac),
        WhatsAppChannel(tac),
        RCSChannel(tac)
    ]
).start()
```

### Memory Modes

```python
# Always fetch memory with semantic search on every message
voice_channel = VoiceChannel(tac, memory_mode="always")

# Fetch memory once at conversation start
sms_channel = SMSChannel(tac, memory_mode="once")

# Never fetch memory automatically
whatsapp_channel = WhatsAppChannel(tac, memory_mode="never")
```

### Custom Tools

```python
from tac.tools import function_tool

@function_tool
async def check_weather(location: str) -> str:
    """Check the weather for a location."""
    # Your weather API logic
    return f"The weather in {location} is sunny"

@function_tool
async def book_appointment(date: str, time: str) -> str:
    """Book an appointment."""
    # Your booking logic
    return f"Appointment booked for {date} at {time}"

# Use with OpenAI
tools = [
    check_weather.to_openai_tool(),
    book_appointment.to_openai_tool()
]

response = await client.responses.create(
    model="gpt-5.4-mini",
    instructions=INSTRUCTIONS,
    input=messages,
    tools=tools
)
```

## Running Examples

Clone the repository and install dependencies:

```bash
git clone https://github.com/twilio/twilio-agent-connect-python.git
cd twilio-agent-connect-python
make sync
```

Configure your environment:

```bash
cp .env.example .env
# Edit .env with your credentials
```

Run an example:

```bash
uv run getting_started/examples/partners/openai_chat_completions.py
```

## Next Steps

- [OpenAI Examples](openai.md) - Detailed OpenAI integration guides
- [AWS Examples](aws.md) - AWS Bedrock and Strands examples
- [API Reference](../api/core.md) - Complete API documentation
