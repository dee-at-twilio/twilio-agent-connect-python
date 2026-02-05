#!/usr/bin/env python3
"""
Simple Voice Channel Example for Twilio Agent Connect

This example demonstrates basic VoiceChannel integration with FastAPI for handling
voice calls without escalation features. For an example with Flex escalation support,
see voice_escalation.py.

Features:
- Basic voice call handling with TwiML generation
- WebSocket connection for real-time voice streaming
- OpenAI integration for conversational responses
- Memory retrieval and context management
"""

import os
import sys
from typing import Optional

import openai
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request, WebSocket
from fastapi.responses import Response
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path to import tac
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tac import TAC, TACConfig, get_logger
from tac.channels.voice import VoiceChannel
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse

# Initialize logger
logger = get_logger(__name__)

# Global variables
voice_channel: VoiceChannel
system_prompt = "You're a helpful assistant that helps users over the phone."


# User-managed conversation history
# Key: conversation_id, Value: list of messages
conversation_messages: dict[str, list[ChatCompletionMessageParam]] = {}


async def handle_message_ready(
    user_message: str,
    context: ConversationSession,
    memory_response: Optional[TACMemoryResponse],
) -> None:
    """
    Callback invoked when a message is ready to be processed.

    Processes user message with OpenAI, using retrieved memories for context
    (if available) and maintaining conversation history for coherent multi-turn interactions.
    Memory is automatically retrieved when auto_retrieve_memory=True (default) and
    Twilio Memory is configured. Profile is fetched once at conversation start.
    """
    logger.info(f"Processing message for conversation {context.conversation_id}")

    if memory_response:
        logger.info(
            f"Retrieved memories: {len(memory_response.observations)} observations, "
            f"{len(memory_response.summaries)} summaries, "
            f"{len(memory_response.communications)} communications"
        )
    else:
        logger.info("No memory response available")

    # Initialize conversation history with system message
    conv_id = context.conversation_id
    if conv_id not in conversation_messages:
        system_msg: ChatCompletionSystemMessageParam = {"role": "system", "content": system_prompt}
        conversation_messages[conv_id] = [system_msg]

        # Add profile traits as context if available (fetched once at conversation start)
        if context.profile:
            traits = context.profile.traits
            logger.info(f"Profile traits available: {list(traits.keys())}")

            # Build a personalized context message with profile information
            profile_context_parts = []
            if "Contact" in traits:
                contact = traits["Contact"]
                if "firstName" in contact:
                    profile_context_parts.append(f"Caller's name: {contact['firstName']}")
                if "lastName" in contact:
                    profile_context_parts.append(f"Last name: {contact['lastName']}")
                if "address" in contact:
                    address = contact["address"]
                    city = address.get("city", "")
                    state = address.get("state", "")
                    if city and state:
                        profile_context_parts.append(f"Location: {city}, {state}")

            if "Preferences" in traits:
                prefs = traits["Preferences"]
                if "language" in prefs:
                    profile_context_parts.append(f"Preferred language: {prefs['language']}")

            if profile_context_parts:
                profile_context = "Caller Profile Information:\n" + "\n".join(
                    f"- {part}" for part in profile_context_parts
                )
                context_msg: ChatCompletionSystemMessageParam = {
                    "role": "system",
                    "content": profile_context,
                }
                conversation_messages[conv_id].append(context_msg)
                logger.info(f"Added profile context to conversation: {profile_context}")

    # Add user message to history
    user_msg: ChatCompletionUserMessageParam = {"role": "user", "content": user_message}
    conversation_messages[conv_id].append(user_msg)

    # Generate response with OpenAI
    client = openai.AsyncOpenAI(api_key=os.environ.get("TWILIO_TAC_OPENAI_API_KEY"))
    completion = await client.chat.completions.create(
        model="gpt-4o",
        messages=conversation_messages[conv_id],
    )

    response = completion.choices[0].message.content

    logger.info("Response generated", response=response)

    # Send response and update history
    if response:
        assistant_msg: ChatCompletionAssistantMessageParam = {
            "role": "assistant",
            "content": response,
        }
        conversation_messages[conv_id].append(assistant_msg)

        await voice_channel.send_response(context.conversation_id, response, role="assistant")


if __name__ == "__main__":
    # Initialize TAC - see examples/README.md for configuration
    tac = TAC(config=TACConfig.from_env())

    # Register callback for message ready
    tac.on_message_ready(handle_message_ready)

    # Initialize channel
    voice_channel = VoiceChannel(tac=tac)

    # Create FastAPI app
    app = FastAPI(title="TAC Voice Server")

    @app.post("/twiml")
    async def post_twiml(
        From: str = Form(...), To: str = Form(...), CallSid: str = Form(...)
    ) -> Response:
        """Generate TwiML for incoming voice calls."""
        public_domain = os.environ.get("TWILIO_TAC_VOICE_PUBLIC_DOMAIN")
        websocket_url = f"wss://{public_domain}/ws"
        callback_url = f"https://{public_domain}/conversation-relay-callback"

        twiml = await voice_channel.handle_incoming_call(
            websocket_url=websocket_url,
            to_number=To,
            from_number=From,
            call_sid=CallSid,
            action_url=callback_url,
            welcome_greeting="Hello! How can I assist you today?",
        )
        return Response(content=twiml, media_type="application/xml")

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        """Handle voice WebSocket connections for real-time streaming."""
        await voice_channel.handle_websocket(websocket)

    @app.post("/conversation-relay-callback")
    async def conversation_relay_callback(request: Request) -> Response:
        """Handle ConversationRelay callback webhook from Twilio."""
        return await voice_channel.handle_conversation_relay_callback(request)

    # Start the server
    logger.info("Starting TAC Voice Server on 0.0.0.0:8000")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
