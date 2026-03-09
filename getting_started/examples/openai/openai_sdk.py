"""
Example: Using OpenAI Adapter with Voice and SMS Channels

Demonstrates how to use with_tac_memory to automatically inject memory context into OpenAI calls.
"""

import os
from typing import Any, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI

from tac import TAC, TACConfig
from tac.adapters.openai import with_tac_memory
from tac.channels.sms import SMSChannel
from tac.channels.voice import VoiceChannel
from tac.core.logging import get_logger
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse
from tac.server import TACServer

load_dotenv()

logger = get_logger(__name__)

# Initialize TAC and channels
tac = TAC(config=TACConfig.from_env())
voice_channel = VoiceChannel(tac)
sms_channel = SMSChannel(tac)

# Initialize AsyncOpenAI client
openai_client = AsyncOpenAI(api_key=os.environ.get("TWILIO_TAC_OPENAI_API_KEY"))

# Store conversation history per conversation
conversation_messages: dict[str, list[Any]] = {}

SYSTEM_MESSAGE = {
    "role": "system",
    "content": "You are a helpful customer service agent.",
}


async def handle_message_ready(
    user_message: str,
    context: ConversationSession,
    memory_response: Optional[TACMemoryResponse],
) -> None:
    """Process incoming messages and generate responses using OpenAI."""
    conv_id = context.conversation_id

    try:
        if conv_id not in conversation_messages:
            conversation_messages[conv_id] = []

        conversation_messages[conv_id].append({"role": "user", "content": user_message})

        # Wrap OpenAI client - memory and profile automatically injected
        client = with_tac_memory(openai_client, memory_response, context)

        messages = [SYSTEM_MESSAGE] + conversation_messages[conv_id]

        response = await client.chat.completions.create(
            model="gpt-5-mini",
            messages=messages,
        )

        llm_response = response.choices[0].message.content or ""
        conversation_messages[conv_id].append({"role": "assistant", "content": llm_response})

        if context.channel == "voice":
            await voice_channel.send_response(conv_id, llm_response, role="assistant")
        elif context.channel == "sms":
            await sms_channel.send_response(conv_id, llm_response, role="assistant")

    except Exception as e:
        logger.error("Error processing message", conversation_id=conv_id, error=str(e))


tac.on_message_ready(handle_message_ready)

if __name__ == "__main__":
    server = TACServer(tac=tac, voice_channel=voice_channel, sms_channel=sms_channel)
    server.start()
