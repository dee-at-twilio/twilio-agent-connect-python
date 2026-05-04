"""
Example: Using AWS Bedrock Converse API with TAC Memory Injection

Demonstrates how to use MemoryPromptBuilder with the Bedrock Converse API.
This works with any Bedrock foundation model (Claude, Llama, Mistral, etc.).

Prerequisites:
    - AWS credentials configured (env vars, ~/.aws/credentials, or IAM role)
    - Model access enabled in the AWS Bedrock console

For production AWS agents, consider using the Strands Agents SDK:
    https://github.com/strands-agents/sdk-python
"""

import asyncio
import os
from typing import Any

import boto3
from dotenv import load_dotenv

from tac import TAC, TACConfig
from tac.adapters.prompt_builder import MemoryPromptBuilder
from tac.channels.sms import SMSChannel, SMSChannelConfig
from tac.channels.voice import VoiceChannel, VoiceChannelConfig
from tac.core.logging import get_logger
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse
from tac.server import TACFastAPIServer

load_dotenv()

logger = get_logger(__name__)

# Initialize TAC with configuration from environment variables
tac = TAC(config=TACConfig.from_env())

# Create channel handlers for Voice and SMS
voice_channel = VoiceChannel(tac, config=VoiceChannelConfig(memory_mode="always"))
sms_channel = SMSChannel(tac, config=SMSChannelConfig(memory_mode="always"))

# Initialize Bedrock client
# boto3 uses the standard AWS credential chain (env vars, ~/.aws/credentials, IAM role)
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("AWS_BEDROCK_MODEL_ID", "us.anthropic.claude-3-5-haiku-20241022-v1:0")
bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)

# Store conversation history per conversation (Bedrock Converse message format)
conversation_history: dict[str, list[dict[str, Any]]] = {}

SYSTEM_PROMPT = "You are a helpful customer service agent. Be concise and friendly."


async def handle_message_ready(
    user_message: str,
    context: ConversationSession,
    memory_response: TACMemoryResponse | None,
) -> str:
    """
    Callback invoked when a message is ready to be processed.

    This example uses the Bedrock Converse API with manual memory injection
    via MemoryPromptBuilder.

    Args:
        user_message: The customer's message text
        context: Session data (conversation_id, channel, profile, etc.)
        memory_response: Optional retrieved memories (observations, summaries, communications)

    Returns:
        Response string to send to the channel
    """
    conv_id = context.conversation_id

    try:
        # Initialize conversation history for new conversations
        if conv_id not in conversation_history:
            conversation_history[conv_id] = []

        # Build memory context using TAC's MemoryPromptBuilder
        memory_context = MemoryPromptBuilder.build(
            memory_response=memory_response,
            context=context,
        )

        # Combine base system prompt with memory context
        if memory_context:
            system_prompt = f"{SYSTEM_PROMPT}\n\n{memory_context}"
        else:
            system_prompt = SYSTEM_PROMPT

        # Add user message in Bedrock Converse format
        conversation_history[conv_id].append(
            {
                "role": "user",
                "content": [{"text": user_message}],
            }
        )

        # Call Bedrock Converse API
        # Using asyncio.to_thread() because boto3 is synchronous
        response = await asyncio.to_thread(
            bedrock_client.converse,
            modelId=MODEL_ID,
            system=[{"text": system_prompt}],
            messages=conversation_history[conv_id],
        )

        # Extract response text
        llm_response: str = response["output"]["message"]["content"][0]["text"]

        # Save assistant response to conversation history
        conversation_history[conv_id].append(
            {
                "role": "assistant",
                "content": [{"text": llm_response}],
            }
        )

        return llm_response

    except Exception as e:
        logger.error("Error processing message", conversation_id=conv_id, error=str(e))
        return "Sorry, I encountered an error processing your message."


# Register the message handler callback
tac.on_message_ready(handle_message_ready)

if __name__ == "__main__":
    # TACFastAPIServer creates a FastAPI app with all required endpoints:
    # - /twiml: Voice call webhook (returns TwiML with ConversationRelay)
    # - /ws: WebSocket endpoint for Voice channel
    # - /webhook: SMS webhook endpoint
    # - /conversation-relay-callback: Voice status callback
    server = TACFastAPIServer(
        tac=tac, voice_channel=voice_channel, messaging_channels=[sms_channel]
    )
    server.start()
