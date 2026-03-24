"""
Example: Framework-Agnostic Memory Injection

Shows how to use TAC memory with ANY agent framework (OpenAI, AWS Bedrock, Azure AI,
GCP Vertex AI, custom agents, etc.).

Key Concepts:
1. TAC provides memory via `memory_response` and `context` parameters
2. Use `MemoryPromptBuilder.build()` to format memory and profile data
3. Inject the formatted prompt into your agent's system prompt or context
4. Works with any LLM or agent framework

For SDK-specific examples with more detail, see the openai/ directory.
"""

from typing import Any, Optional

from dotenv import load_dotenv

from tac import TAC, TACConfig
from tac.adapters.prompt_builder import MemoryPromptBuilder
from tac.channels.sms import SMSChannel
from tac.channels.voice import VoiceChannel
from tac.core.logging import get_logger
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse
from tac.server import TACFastAPIServer

load_dotenv()

logger = get_logger(__name__)

# Initialize TAC and channels
tac = TAC(config=TACConfig.from_env())
voice_channel = VoiceChannel(tac)
sms_channel = SMSChannel(tac)

# Store conversation history per conversation
conversation_messages: dict[str, list[Any]] = {}


# No custom formatting needed! TAC provides MemoryPromptBuilder for this.
# You can use it as-is or customize it for your specific needs.


async def handle_message_ready(
    user_message: str,
    context: ConversationSession,
    memory_response: Optional[TACMemoryResponse],
) -> None:
    """
    Process incoming messages using manual memory injection.

    This pattern works with ANY agent framework:
    - OpenAI (see openai/ example for adapter)
    - AWS Bedrock (upcoming example)
    - Azure AI (upcoming example)
    - GCP Vertex AI (upcoming example)
    - Custom agents
    """
    conv_id = context.conversation_id

    try:
        if conv_id not in conversation_messages:
            conversation_messages[conv_id] = []

        # Use TAC's MemoryPromptBuilder to format memory and profile data
        # This is the official way to format TAC memory for any agent/framework
        memory_context = MemoryPromptBuilder.build(
            memory_response=memory_response,
            context=context,
        )

        # Build your system prompt with memory context
        base_prompt = "You are a helpful customer service agent."
        if memory_context:
            system_prompt = f"{base_prompt}\n\n{memory_context}"
        else:
            system_prompt = base_prompt

        # Add user message to conversation history
        conversation_messages[conv_id].append({"role": "user", "content": user_message})

        # Now use system_prompt with your agent/LLM
        # Add it to your agent's messages, system parameter, or context
        # See SDK-specific examples (openai/, aws/, azure/, gcp/) for detailed usage
        #
        # Example usage patterns:
        # - OpenAI: messages=[{"role": "system", "content": system_prompt}, ...]
        # - AWS Bedrock: system=[{"text": system_prompt}]
        # - Azure AI: messages=[{"role": "system", "content": system_prompt}, ...]
        # - Custom: Pass system_prompt to your agent however needed

        # For this example, simulate a response (showing system_prompt is used)
        llm_response = (
            f"[Simulated response with system prompt: {system_prompt[:50]}...]\n\n"
            f"Received: {user_message}"
        )

        conversation_messages[conv_id].append({"role": "assistant", "content": llm_response})

        # Send response through appropriate channel
        if context.channel == "voice":
            await voice_channel.send_response(conv_id, llm_response, role="assistant")
        elif context.channel == "sms":
            await sms_channel.send_response(conv_id, llm_response, role="assistant")

    except Exception as e:
        logger.error("Error processing message", conversation_id=conv_id, error=str(e))


# Register the message handler
tac.on_message_ready(handle_message_ready)

if __name__ == "__main__":
    """
    Key Takeaways:

    1. TAC provides memory via `memory_response` and `context` parameters when you
       register a callback with `tac.on_message_ready()`

    2. Use `MemoryPromptBuilder.build()` to format memory and profile data:
       - Formats observations (key facts)
       - Formats summaries (conversation insights)
       - Formats communications (conversation history)
       - Formats profile traits (customer info)

    3. Inject the formatted prompt into your agent's system prompt, context, or
       wherever your framework expects it:
       - OpenAI: Add to system message
       - AWS Bedrock: Add to system prompt
       - Azure AI: Add to system message
       - GCP Vertex AI: Add to system instructions
       - Custom agents: Add wherever you need context

    This approach is framework-agnostic and works with ANY agent or LLM.

    For automatic injection with zero config, see the OpenAI adapter examples:
    - `examples/openai/chat_completions.py` - Chat Completions API
    - `examples/openai/responses_api.py` - Responses API
    """
    server = TACFastAPIServer(tac=tac, voice_channel=voice_channel, sms_channel=sms_channel)
    server.start()
