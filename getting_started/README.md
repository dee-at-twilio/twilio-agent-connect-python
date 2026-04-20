# Getting Started with Twilio Agent Connect (TAC)

This guide will walk you through setting up and running your first TAC application.

## Prerequisites

1. **Python 3.10+** installed
2. **Twilio account** with a phone number
3. **API key** for the SDK you're using (e.g., OpenAI API key)
4. **ngrok** or similar tunneling tool for local development

## Step 1: Set Up Twilio Services

You need to create a Twilio Conversation Configuration and Memory Store before using TAC.

**Option 1: Use the Setup Wizard**

Run the interactive wizard to automatically create services:

```bash
make setup
# Open http://localhost:8080 and follow the wizard
```

The wizard will:
- Create a Twilio Conversation Configuration and Memory Store
- Generate a `.env` file with all required credentials

**Option 2: Manual Setup**

Create services manually through the [Twilio Console](https://1console.twilio.com/).

## Step 2: Choose an Example

TAC includes examples for different integration approaches:

### `overview.py` - Framework-Agnostic Pattern

Learn the core pattern for manually extracting and injecting TAC memory into **any** agent framework:
- Works with OpenAI, AWS Bedrock, Azure AI, GCP Vertex AI, custom agents
- Full control over memory formatting and injection
- Uses TAC's official `MemoryPromptBuilder` utility
- **Start here** to understand how TAC memory works

### `openai/` - OpenAI SDK with Adapter

Production-ready examples using the OpenAI adapter:
- **`chat_completions.py`**: Chat Completions API
- **`responses_api.py`**: Responses API
- Automatic memory injection with `with_tac_memory()`
- Less boilerplate, more convention-based

## Step 3: Run an Example

### Install Dependencies

From the repository root:

```bash
make sync
```

### Configure Environment Variables

```bash
cd getting_started/examples
cp .env.example .env
# Edit .env with your credentials
```

See the **Environment Variables** section below for details.

### Run the Server

```bash
# Run overview example (framework-agnostic)
python overview.py

# Or run OpenAI Chat Completions example
python openai/chat_completions.py

# Or run OpenAI Responses API example
python openai/responses_api.py
```

### Expose Your Server

In another terminal, start ngrok:

```bash
ngrok http 8000
# Copy the ngrok URL (e.g., abc123.ngrok.io)
```

Update `TWILIO_VOICE_PUBLIC_DOMAIN` in your `.env` file with the ngrok URL (without `https://`).

Restart the server to pick up the new configuration.

## Environment Variables

See `examples/.env.example` for all available configuration options. Key variables:

### Required
- `TWILIO_ACCOUNT_SID`: Twilio Account SID
- `TWILIO_AUTH_TOKEN`: Twilio auth token
- `TWILIO_API_KEY`: Twilio API key SID (starts with SK)
- `TWILIO_API_SECRET`: Twilio API key secret
- `TWILIO_PHONE_NUMBER`: Your Twilio phone number
- `TWILIO_CONVERSATION_CONFIGURATION_ID`: Conversation Configuration ID

### Optional (Voice Channel)
- `TWILIO_VOICE_PUBLIC_DOMAIN`: Your ngrok domain (required for voice)

### Optional (OpenAI Example)
- `OPENAI_API_KEY`: Your OpenAI API key (only needed to run OpenAI examples)

## Next Steps

- Start with `examples/overview.py` to learn the core memory injection pattern
- Try the `examples/openai/` examples for production-ready OpenAI integration
- Customize the agent's behavior by modifying the message handler
- Add tool calling to enable agent actions beyond text responses
- Explore the main [README](../README.md) for advanced features
