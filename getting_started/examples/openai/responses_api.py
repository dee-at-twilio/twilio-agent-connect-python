"""
Example: Using OpenAI Responses API with TAC Memory Injection

Demonstrates how to use with_tac_memory with the Responses API.
For the Chat Completions API, see chat_completions.py.
"""

import os
from typing import Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI

from tac import TAC, TACConfig
from tac.adapters.openai import with_tac_memory
from tac.channels.sms import SMSChannel
from tac.channels.voice import VoiceChannel
from tac.core.logging import get_logger
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse
from tac.server import TACFastAPIServer

load_dotenv()

logger = get_logger(__name__)

# Initialize TAC with configuration from environment variables
# TAC handles conversation orchestration and optional memory retrieval
tac = TAC(config=TACConfig.from_env())

# Create channel handlers for Voice and SMS
# Channels process Twilio webhooks and manage conversation lifecycle
voice_channel = VoiceChannel(tac)
sms_channel = SMSChannel(tac)

# Initialize your LLM client (OpenAI in this example)
openai_client = AsyncOpenAI(api_key=os.environ.get("TWILIO_TAC_OPENAI_API_KEY"))

# Store conversation history per conversation
# This maintains context across multiple turns in a conversation
conversation_history: dict[str, list[dict[str, str]]] = {}

SYSTEM_INSTRUCTIONS = "You are a helpful customer service agent. Be concise and friendly."


async def handle_message_ready(
    user_message: str,
    context: ConversationSession,
    memory_response: Optional[TACMemoryResponse],
) -> None:
    """
    Callback invoked when a message is ready to be processed.

    This example uses the Responses API with automatic memory injection.

    Args:
        user_message: The customer's message text
        context: Session data (conversation_id, channel, profile, etc.)
        memory_response: Optional retrieved memories (observations, summaries, communications)
    """
    conv_id = context.conversation_id

    try:
        # Initialize conversation history for new conversations
        if conv_id not in conversation_history:
            conversation_history[conv_id] = []

        # Add user message to conversation history
        conversation_history[conv_id].append({"role": "user", "content": user_message})

        # Wrap OpenAI client with TAC adapter for automatic memory injection
        # The adapter prepends memory context to the instructions parameter
        client = with_tac_memory(openai_client, memory_response, context)

        # Call OpenAI Responses API - memory is automatically injected
        response = await client.responses.create(
            model="gpt-4o",
            instructions=SYSTEM_INSTRUCTIONS,
            input=conversation_history[conv_id],
        )

        llm_response = response.output_text

        # Save assistant response to conversation history
        conversation_history[conv_id].append({"role": "assistant", "content": llm_response})

        # Route response to the appropriate channel
        # TAC handles the low-level details of sending the response
        if context.channel == "voice":
            await voice_channel.send_response(conv_id, llm_response, role="assistant")
        elif context.channel == "sms":
            await sms_channel.send_response(conv_id, llm_response, role="assistant")

    except Exception as e:
        logger.error("Error processing message", conversation_id=conv_id, error=str(e))


# Register the message handler callback
# TAC will invoke this function whenever a message needs processing
tac.on_message_ready(handle_message_ready)

if __name__ == "__main__":
    # TACFastAPIServer creates a FastAPI app with all required endpoints:
    # - /twiml: Voice call webhook (returns TwiML with ConversationRelay)
    # - /ws: WebSocket endpoint for Voice channel
    # - /webhook: SMS webhook endpoint
    # - /conversation-relay-callback: Voice status callback
    server = TACFastAPIServer(tac=tac, voice_channel=voice_channel, sms_channel=sms_channel)
    server.start()
