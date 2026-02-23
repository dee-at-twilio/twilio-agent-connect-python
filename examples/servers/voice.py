#!/usr/bin/env python3
"""
Simplified Voice Server Example with SessionManager for Interrupt Handling

This example demonstrates:
- TACServer for automatic FastAPI endpoint setup
- VoiceChannel with ThreadSafeSessionManager for proper interrupt handling
- OpenAI streaming integration
- Memory retrieval and context management
- LLM service for clean separation of concerns

For a basic example without SessionManager, see examples/channels/voice.py.
For a manual FastAPI example with custom endpoints, see examples/channels/voice_escalation.py.
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

from tac import TAC, TACConfig, get_logger
from tac.channels.voice import VoiceChannel
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse
from tac.server import TACServer
from tac.session import ThreadSafeSessionManager
from tac.tools.knowledge import KnowledgeToolConfig, create_knowledge_tool

# Initialize logger
logger = get_logger(__name__)

# Global variables
system_prompt = "You're a helpful assistant that helps users over the phone."

# These will be initialized in __main__
tac: Optional[TAC] = None
voice_channel: Optional[VoiceChannel] = None
llm_service: Optional[LLMService] = None


async def handle_message_ready(
    user_message: str,
    context: ConversationSession,
    memory_response: Optional[TACMemoryResponse],
) -> None:
    """
    Callback invoked when a message is ready to be processed.

    This callback is always triggered for voice messages. With SessionManager,
    streaming tasks can be automatically cancelled when interrupts occur.
    """
    logger.debug(f"[CALLBACK] Processing message: {user_message[:50]}")

    # Create inline async generator for streaming
    async def stream_response() -> AsyncGenerator[str, None]:
        if llm_service:
            async for chunk in llm_service.stream_response(
                user_message, context.conversation_id, context
            ):
                yield chunk
        else:
            logger.error("LLM service not initialized")
            yield "I'm sorry, something went wrong."

    # Send streaming response to voice channel
    if voice_channel:
        await voice_channel.send_response(context.conversation_id, stream_response())
    else:
        logger.error("Voice channel not initialized")


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

    # Create SessionManager for task tracking and cancellation support
    session_manager = ThreadSafeSessionManager()
    logger.info("[SETUP] SessionManager created")

    # Register callback for message ready; with SessionManager, streaming tasks are cancellable
    tac.on_message_ready(handle_message_ready)

    # Initialize channel with session manager
    voice_channel = VoiceChannel(
        tac=tac,
        session_manager=session_manager,
    )
    logger.info("[SETUP] Voice channel initialized with SessionManager for interrupt handling")

    # Create and start TACServer
    server = TACServer(tac=tac, voice_channel=voice_channel)
    server.start()
