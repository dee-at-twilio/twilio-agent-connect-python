#!/usr/bin/env python3
"""
Voice Channel Example with Session Management and Streaming

This example demonstrates VoiceChannel integration with FastAPI using session management
to handle interrupts and cancel in-flight streaming tasks.

Features:
- Voice call handling with TwiML generation
- WebSocket connection for real-time voice streaming
- OpenAI GPT-4o streaming integration for conversational responses
- Session management for handling interrupts and task cancellation
- Memory retrieval and context management
"""

import os
import sys
from collections.abc import AsyncGenerator

import openai
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Form, WebSocket
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
from tac.channels.session_manager import ThreadSafeSessionManager
from tac.channels.voice import VoiceChannel

# Initialize logger
logger = get_logger(__name__)

# Global variables
voice_channel: VoiceChannel
system_prompt = "Hi! I am a TAC voice expert. Ask me anything"


# User-managed conversation history
# Key: conversation_id, Value: list of messages
conversation_messages: dict[str, list[ChatCompletionMessageParam]] = {}


async def stream_openai_response(prompt: str, session_id: str) -> AsyncGenerator[str, None]:
    """
    Stream generator that yields OpenAI GPT-4o streaming chunks.

    Args:
        prompt: The user's message to send to OpenAI
        session_id: The conversation/session ID for maintaining history

    Yields:
        Text chunks from the OpenAI streaming response
    """
    logger.info(f"Streaming response for session {session_id}")

    # Initialize conversation history with system message if needed
    if session_id not in conversation_messages:
        system_msg: ChatCompletionSystemMessageParam = {"role": "system", "content": system_prompt}
        conversation_messages[session_id] = [system_msg]

    # Add user message to history
    user_msg: ChatCompletionUserMessageParam = {"role": "user", "content": prompt}
    conversation_messages[session_id].append(user_msg)

    # Stream response from OpenAI
    client = openai.AsyncOpenAI(api_key=os.environ.get("TWILIO_TAC_OPENAI_API_KEY"))
    stream = await client.chat.completions.create(
        model="gpt-4o",
        messages=conversation_messages[session_id],
        stream=True,
    )

    full_response = ""
    async for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            content = chunk.choices[0].delta.content
            full_response += content
            yield content

    # Add assistant response to history
    if full_response:
        assistant_msg: ChatCompletionAssistantMessageParam = {
            "role": "assistant",
            "content": full_response,
        }
        conversation_messages[session_id].append(assistant_msg)
        logger.info(f"Completed streaming response for session {session_id}")


if __name__ == "__main__":
    # Initialize TAC - see examples/README.md for configuration
    tac = TAC(config=TACConfig.from_env())

    # Initialize session manager with OpenAI streaming
    session_manager = ThreadSafeSessionManager(stream_generator=stream_openai_response)

    # Initialize VoiceChannel with session management enabled
    voice_channel = VoiceChannel(tac=tac, session_manager=session_manager)

    # Debug: Verify session manager is set
    logger.info(
        f"VoiceChannel initialized with session_manager: {voice_channel.session_manager is not None}"
    )

    # Create FastAPI app
    app = FastAPI(title="TAC Voice Server")

    @app.post("/twiml")
    async def post_twiml(From: str = Form(...), To: str = Form(...)) -> Response:
        """Generate TwiML for incoming voice calls."""
        public_domain = os.environ.get("TWILIO_TAC_VOICE_PUBLIC_DOMAIN")
        websocket_url = f"wss://{public_domain}/ws"

        twiml = await voice_channel.handle_incoming_call(
            websocket_url=websocket_url,
            to_number=To,
            from_number=From,
            welcome_greeting="Hello! How can I assist you today?",
        )
        return Response(content=twiml, media_type="application/xml")

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        """Handle voice WebSocket connections for real-time streaming."""
        await voice_channel.handle_websocket(websocket)

    # Start the server
    logger.info("Starting TAC Voice Server on 0.0.0.0:8000")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
