#!/usr/bin/env python3
"""
Voice Channel with Streaming Example

This example demonstrates voice channel with streaming support using session management.
The session manager enables task tracking, cancellation, and interrupt support.
"""

import os
import sys
from collections.abc import AsyncGenerator
from typing import Optional

import openai
from dotenv import load_dotenv
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tac import TAC, TACConfig, get_logger
from tac.channels.voice import VoiceChannel
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse
from tac.server import TACServer
from tac.session import ThreadSafeSessionManager

logger = get_logger(__name__)

voice_channel: VoiceChannel
system_prompt = "You're a helpful assistant that helps users over the phone."
conversation_messages: dict[str, list[ChatCompletionMessageParam]] = {}


async def handle_message_ready(
    user_message: str,
    context: ConversationSession,
    memory_response: Optional[TACMemoryResponse],
) -> None:
    """Handle incoming message with streaming response."""
    logger.info(f"Processing message for conversation {context.conversation_id}")

    if memory_response:
        logger.info(
            f"Retrieved memories: {len(memory_response.observations)} observations, "
            f"{len(memory_response.summaries)} summaries, "
            f"{len(memory_response.communications)} communications"
        )

    conv_id = context.conversation_id
    if conv_id not in conversation_messages:
        system_msg: ChatCompletionSystemMessageParam = {"role": "system", "content": system_prompt}
        conversation_messages[conv_id] = [system_msg]

    user_msg: ChatCompletionUserMessageParam = {"role": "user", "content": user_message}
    conversation_messages[conv_id].append(user_msg)

    # Stream response using inline async generator
    async def stream_response() -> AsyncGenerator[str, None]:
        logger.info(f"Starting streaming response for conversation {conv_id}")
        chunk_count = 0

        client = openai.AsyncOpenAI(api_key=os.environ.get("TWILIO_TAC_OPENAI_API_KEY"))
        stream = await client.chat.completions.create(
            model="gpt-4o",
            messages=conversation_messages[conv_id],
            stream=True,
        )

        full_response = ""
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                full_response += content
                chunk_count += 1
                yield content

        logger.info(f"Streaming completed: {chunk_count} chunks, {len(full_response)} chars")

        assistant_msg: ChatCompletionAssistantMessageParam = {
            "role": "assistant",
            "content": full_response,
        }
        conversation_messages[conv_id].append(assistant_msg)

    await voice_channel.send_response(context.conversation_id, stream_response())


if __name__ == "__main__":
    tac = TAC(config=TACConfig.from_env())
    tac.on_message_ready(handle_message_ready)

    # Session manager enables task tracking, cancellation, and interrupt support
    session_manager = ThreadSafeSessionManager()
    logger.info("Session manager initialized - streaming with interrupt support enabled")

    voice_channel = VoiceChannel(tac=tac, session_manager=session_manager)

    # Create and start TACServer
    server = TACServer(tac=tac, voice_channel=voice_channel)
    server.start()
