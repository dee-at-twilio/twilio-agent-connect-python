# TAC Examples

This directory contains examples demonstrating how to use the Twilio Agent Connect (TAC) with various LLM frameworks and channels.

## Quick Start

1. **Install dependencies:**
   ```bash
   make sync
   # or
   uv sync --extra dev
   ```

2. **Configure environment:**

   **Option A: Use the Quickstart Wizard (Recommended)**

   Run the setup wizard to automatically create Memory and Maestro services and generate your `.env` file:
   ```bash
   make quickstart
   # Open http://localhost:8080
   ```

   The wizard will guide you through entering your Twilio credentials and create all required services.

   **Option B: Manual Configuration**

   Copy `.env.example` to `.env` and fill in your credentials:

   **Required:**
   ```bash
   TWILIO_TAC_ENVIRONMENT=prod  # 'dev', 'stage', or 'prod'
   TWILIO_TAC_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_TAC_AUTH_TOKEN=your_auth_token_here
   TWILIO_TAC_PHONE_NUMBER=+1234567890
   TWILIO_TAC_CONVERSATION_SERVICE_SID=conv_configuration_xxxxxxxxxxxxxxxxxx
   ```

   **Optional (for Twilio Memory):**
   ```bash
   TWILIO_TAC_MEMORY_STORE_ID=mem_store_xxxxxxxxxxxxxxxxxx
   TWILIO_TAC_MEMORY_API_KEY=SKxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx  # Twilio API Key SID
   TWILIO_TAC_MEMORY_API_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx  # Twilio API Key Secret
   TWILIO_TAC_TRAIT_GROUPS=Contact,Preferences
   ```

   **Optional (for specific examples):**
   ```bash
   TWILIO_TAC_LOG_LEVEL=INFO
   TWILIO_TAC_OPENAI_API_KEY=sk-xxxxx...  # For OpenAI examples
   TWILIO_TAC_VOICE_PUBLIC_DOMAIN=example.ngrok.io  # For voice examples
   TWILIO_TAC_KNOWLEDGE_BASE_ID=know_knowledgebase_xxxxx...  # For knowledge tool examples
   ```

3. **Run an example:**
   ```bash
   # Start simplified voice server (recommended for getting started)
   uv run python examples/servers/voice.py

   # Or start SMS webhook server
   uv run python examples/channels/sms.py

   # Or try a tool integration example
   uv run python examples/tools/openai_chat_with_tools.py
   ```

## Examples Overview

### [quickstart/](quickstart/) - Setup Wizard

Web-based setup wizard to create Memory and Maestro services:

- **Automated setup** - Creates Memory Store, Profile, and Maestro Configuration
- **Credential management** - Saves form inputs to localStorage
- **Environment generation** - Generates complete `.env` file with copy button
- **Configuration management** - List and delete existing Maestro configurations

```bash
make quickstart
# Open http://localhost:8080
```

[→ View Quickstart Wizard](quickstart/)

### [exec_demo/](exec_demo/) - Multi-Channel Demo

Complete production-ready example demonstrating both SMS and Voice channels:

- **Multi-channel support** - Single server handling SMS and Voice
- **OpenAI Agents integration** - LLM with custom business tools
- **Memory integration** - Full TAC memory retrieval and context
- **Realistic use case** - ISP customer service agent with plan upgrades

[→ View Multi-Channel Demo](exec_demo/)

### [servers/](servers/) - Simplified Server Setup

**Recommended starting point** for new users. Examples using TAC's built-in server configuration for minimal boilerplate:

- **`voice.py`** - Simplified voice server with automatic FastAPI setup and endpoint creation

Perfect for getting started quickly. For advanced features or custom control, see the manual approach in `channels/`.

[→ View Simplified Server Examples](servers/)

### [channels/](channels/) - Channel Implementation Examples

Ready-to-deploy examples with full control over FastAPI configuration:

- **`sms.py`** - SMS channel webhook server with TAC integration
- **`voice.py`** - Voice channel server with manual FastAPI and WebSocket setup
- **`voice_escalation.py`** - Voice channel with Flex escalation for agent handoff to humans

Use these examples when you need custom middleware, authentication, or integration with existing apps.

[→ View Channel Examples](channels/)

## What You'll Learn

- ✅ Setting up TAC with Twilio services (Memory, Maestro)
- ✅ Processing SMS and Voice webhooks
- ✅ Retrieving and using user memories
- ✅ Integrating TAC tools with LLM frameworks
- ✅ Building production-ready agentic applications

## Need Help?

- See individual example READMEs for detailed setup and usage
- Check the main [project README](../README.md) for core concepts
- Review [CLAUDE.md](../CLAUDE.md) for architecture details
