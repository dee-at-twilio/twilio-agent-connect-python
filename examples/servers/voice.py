#!/usr/bin/env python3
"""
Simplified Voice Server Example with SessionManager for Interrupt Handling

This example demonstrates:
- VoiceChannel with built-in server (VoiceServerConfig)
- ThreadSafeSessionManager for proper interrupt handling
- OpenAI streaming integration
- Memory retrieval and context management
- LLM service for clean separation of concerns

For a basic example without SessionManager, see examples/channels/voice.py.
"""

import asyncio
import os
import sys
from collections.abc import AsyncGenerator
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path to import tac
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_service import LLMService  # type: ignore[import-not-found]

from tac import TAC, TACConfig, VoiceServerConfig, get_logger
from tac.channels.session_manager import ThreadSafeSessionManager
from tac.channels.voice import VoiceChannel
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse
from tac.tools.knowledge import KnowledgeToolConfig, create_knowledge_tool

# Initialize logger
logger = get_logger(__name__)

# Global variables
system_prompt = "You're a helpful assistant that helps users over the phone."

# These will be initialized in __main__
tac: Optional[TAC] = None
voice_channel: Optional[VoiceChannel] = None
llm_service: Optional[LLMService] = None


async def stream_generator(prompt: str, conv_id: str) -> AsyncGenerator[str, None]:
    """
    Stream generator for SessionManager.

    This function is called by SessionManager to stream LLM responses.
    It yields chunks that can be cancelled mid-stream when interrupts occur.

    Note: When using SessionManager, this replaces the message_ready callback
    as the entry point for processing voice messages.
    """
    # Get conversation context from voice channel
    if not voice_channel:
        logger.error("Voice channel not initialized")
        yield "I'm sorry, something went wrong."
        return

    context = voice_channel._conversations.get(conv_id)
    if not context:
        logger.warning(f"No session found for conversation {conv_id}")
        # Create minimal context
        from tac.models.session import ConversationSession

        context = ConversationSession(
            conversation_id=conv_id,
            profile_id=None,
            channel="voice",
            profile=None,
            author_info=None,
            ai_agent_info=None,
        )

    # Stream response from LLM service
    if llm_service:
        async for chunk in llm_service.stream_response(prompt, conv_id, context):
            yield chunk
    else:
        logger.error("LLM service not initialized")
        yield "I'm sorry, something went wrong."


async def handle_message_ready(
    user_message: str,
    context: ConversationSession,
    memory_response: Optional[TACMemoryResponse],
) -> None:
    """
    Callback invoked when a message is ready to be processed.

    Note: When using SessionManager with voice channel, this callback is NOT triggered.
    Message processing happens in stream_generator() instead. This callback is kept
    for compatibility but won't be called for voice messages when SessionManager is used.
    """
    logger.debug(
        f"[CALLBACK] Message ready callback (not used with SessionManager): {user_message[:50]}"
    )


if __name__ == "__main__":
    # Initialize TAC - see examples/README.md for configuration
    tac = TAC(config=TACConfig.from_env())

    # Create knowledge tool if knowledge base ID is provided
    tools = []
    knowledge_id = os.environ.get("TWILIO_TAC_KNOWLEDGE_BASE_ID")
    if knowledge_id and tac.knowledge_client:
        knowledge_tool = asyncio.run(
            create_knowledge_tool(
                knowledge_client=tac.knowledge_client,
                knowledge_base_id=knowledge_id,
                tool_config=KnowledgeToolConfig(
                    name="search_knowledge",
                    description="Search the knowledge base for information",
                    top_k=3,
                ),
            )
        )
        tools.append(knowledge_tool)
        logger.info(f"[SETUP] Knowledge tool created: {knowledge_tool.name}")
    elif knowledge_id and not tac.knowledge_client:
        logger.warning(
            "[SETUP] Knowledge ID provided but Knowledge client is not initialized. "
            "Make sure TWILIO_TAC_MEMORY_* environment variables are set."
        )

    # Initialize LLM service with tools
    llm_service = LLMService(tac=tac, system_prompt=system_prompt, tools=tools)
    logger.info(f"[SETUP] LLM service initialized with {len(tools)} tool(s)")

    # Create SessionManager for interrupt handling and streaming
    session_manager = ThreadSafeSessionManager(stream_generator=stream_generator)
    logger.info("[SETUP] SessionManager created with streaming support")

    # Register callback for message ready (not used with SessionManager for voice)
    tac.on_message_ready(handle_message_ready)

    # Initialize channel with server configuration and session manager
    voice_channel = VoiceChannel(
        tac=tac,
        session_manager=session_manager,
        server_config=VoiceServerConfig(
            public_domain=os.environ["TWILIO_TAC_VOICE_PUBLIC_DOMAIN"],
            host="0.0.0.0",
            port=8000,
        ),
    )
    logger.info("[SETUP] Voice channel initialized with SessionManager for interrupt handling")

    # That's it! Just call start() and everything is handled automatically
    logger.info("Starting voice server with interrupt handling...")
    voice_channel.start()
