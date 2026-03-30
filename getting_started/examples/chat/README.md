# TAC Chat Example

Example demonstrating ChatChannel integration with Twilio Agent Connect. Uses the Twilio Conversations JS SDK for web chat conversations.

## Setup

1. Copy `.env.example` to `../.env` (in the `getting_started/examples` directory) and fill in your credentials:
   - Standard TAC credentials (Account SID, Auth Token, API credentials, Conversation Service ID)
   - `TWILIO_CONVERSATIONS_SERVICE_SID` — Conversations v1 Service SID (starts with IS, **not** the Conversation Orchestrator configuration ID)
   - `OPENAI_API_KEY` — OpenAI API key

2. Install dependencies:
   ```bash
   make sync
   ```

3. Start the server:
   ```bash
   uv run python getting_started/examples/chat/app.py
   ```

4. Open http://localhost:8000 in your browser

## How it Works

1. **Frontend**: Browser-based chat with Twilio Conversations SDK
   - Select from predefined email identities (e.g., `test1@example.com`) for identity resolution
   - Fetches access token from `/token` endpoint
   - Creates conversation lazily on first message
   - Sends messages via Conversations SDK
   - Displays AI responses in real-time

2. **Backend**: FastAPI server with TAC + ChatChannel + OpenAI
   - `POST /token` — generates Conversations SDK access token
   - `POST /conversation` — Conversation Orchestrator webhook endpoint
   - Routes webhook events to ChatChannel
   - Calls OpenAI gpt-4o-mini for responses
   - Sends responses via Conversation Orchestrator Send API

## Architecture

```
Browser (Conversations JS SDK) -> Maestro -> webhook -> server -> AI -> Maestro Send API -> SDK
```

1. Browser fetches access token from `POST /token`
2. Browser creates conversation and sends message via Conversations SDK
3. Maestro passively hydrates the conversation
4. Maestro sends `COMMUNICATION_CREATED` webhook to `POST /conversation`
5. Server calls OpenAI for a response
6. Server sends response via Conversation Orchestrator Send API
7. Maestro delivers message to Conversations SDK
8. Browser displays the AI response

## Notes

- Conversations are created client-side by the Conversations SDK
- The backend receives webhook events from Conversation Orchestrator
- Messages from the AI agent (`ai-agent`) are filtered out to prevent echo
- Email identities enable TAC memory profile resolution via identity auto-detection
