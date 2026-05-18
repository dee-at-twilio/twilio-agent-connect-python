# Twilio Agent Connect Python SDK

<div align="center">
  <img src="https://raw.githubusercontent.com/twilio/twilio-agent-connect-python/main/logo.svg" alt="TAC Logo" width="120" height="120">
</div>

A powerful SDK for building intelligent, context-aware AI agents with Twilio's communication technologies.

[![Python SDK](https://img.shields.io/badge/Python-3.10+-3776AB.svg)](https://github.com/twilio/twilio-agent-connect-python)
[![PyPI](https://img.shields.io/pypi/v/twilio-agent-connect.svg)](https://pypi.org/project/twilio-agent-connect/)
[![CI](https://github.com/twilio/twilio-agent-connect-python/actions/workflows/ci.yml/badge.svg)](https://github.com/twilio/twilio-agent-connect-python/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/twilio/twilio-agent-connect-python/blob/main/LICENSE)

---

## Overview

Seamlessly integrate with Twilio Conversation Memory and Conversation Orchestrator to build LLM-powered agents with persistent memory and conversation context.

!!! tip "Building AI agents on AWS or Microsoft?"
    Connect them to Twilio's voice, messaging, and conversation context with these dedicated packages:
    
    - **[TAC for AWS](https://github.com/twilio/twilio-agent-connect-aws)** — Strands, Bedrock Agents, Bedrock AgentCore
    - **[TAC for Microsoft](https://github.com/twilio/twilio-agent-connect-microsoft)** — Microsoft Agent Framework, Azure AI Foundry (incl. Voice Live), Azure OpenAI

## Key Features

- **Multi-Channel Support**: Built-in handling for Voice (ConversationRelay), SMS, RCS, WhatsApp, and Chat
- **Outbound Conversations**: Agent-initiated conversations across all supported channels
- **ConversationRelay-Only Mode**: Get started quickly with TAC's voice plumbing (TwiML, WebSocket, callbacks) before adding Conversation Orchestrator or Conversation Memory
- **Memory Management**: Automatic integration with Twilio Conversation Memory for persistent user context
- **Conversation Lifecycle**: Automatic tracking of conversation sessions and state
- **Human Handoff**: Built-in tool to route conversations to human agents via Twilio Studio Flows (including Flex)

## Installation

=== "Basic Installation"
    ```bash
    pip install twilio-agent-connect
    ```

=== "With Server Support"
    ```bash
    pip install "twilio-agent-connect[server]"
    ```

!!! note "Requirements"
    TAC requires **Python 3.10 or newer**.

## Quick Start

Here's a minimal example to get you started:

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
SYSTEM_INSTRUCTIONS = (
    "You are a customer service agent speaking with a user over voice or SMS. "
    "Keep responses short and conversational — a sentence or two. "
    "Do not use markdown, asterisks, bullets, or emojis; your words will be "
    "spoken aloud or sent as plain text."
)

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

**That's it!** The server automatically:

- Creates FastAPI app with `/twiml`, `/ws`, and `/webhook` endpoints
- Handles Voice, SMS, RCS, WhatsApp, and Chat conversations
- Routes responses to the appropriate channel
- Injects conversation memory and user profile into OpenAI calls

For detailed setup instructions, see the [Getting Started Guide](getting-started/index.md).

## How It Works

TAC simplifies building AI agents by handling the integration between Twilio's communication channels and your LLM:

1. **Webhook/Connection Received**: Twilio sends webhook (SMS) or WebSocket connection (Voice) to your server
2. **Channel Processing**: Channel validates and processes the incoming event
3. **Memory Retrieval**: TAC optionally retrieves user memories and profile from Memory
4. **Callback Invoked**: Your `on_message_ready` callback receives user message, context, and optional memory response
5. **Response Handling**: Your callback returns a response string that TAC routes to the appropriate channel

## Next Steps

- [Installation Guide](getting-started/installation.md)
- [Quick Start Tutorial](getting-started/quickstart.md)
- [Architecture Overview](guides/architecture.md)
- [Examples](examples/index.md)
- [API Reference](api/core.md)

## Learn More

- **[GitHub Repository](https://github.com/twilio/twilio-agent-connect-python)** - Source code and examples
- **[Official Documentation](https://www.twilio.com/docs/conversations/agent-connect)** - Twilio's official docs
- **[PyPI Package](https://pypi.org/project/twilio-agent-connect/)** - Package registry
- **[TAC for AWS](https://github.com/twilio/twilio-agent-connect-aws)** - AWS integrations
- **[TAC for Microsoft](https://github.com/twilio/twilio-agent-connect-microsoft)** - Microsoft integrations
