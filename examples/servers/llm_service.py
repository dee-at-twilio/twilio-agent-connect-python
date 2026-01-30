"""
LLM Service for Voice Server with Streaming Support

Provides streaming LLM responses using OpenAI with memory integration and tools.
"""

import asyncio
import json
import os
from collections.abc import AsyncGenerator
from typing import Any, Optional

import openai
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionUserMessageParam,
)

from tac import get_logger
from tac.core.tac import TAC
from tac.models.session import ConversationSession
from tac.tools.base import TACTool

logger = get_logger(__name__)


class LLMService:
    """Service for streaming LLM responses with memory context and tool support."""

    def __init__(self, tac: TAC, system_prompt: str, tools: Optional[list[TACTool]] = None):
        """
        Initialize LLM service.

        Args:
            tac: TAC instance for memory operations
            system_prompt: Base system prompt for the assistant
            tools: Optional list of TACTools to make available to the LLM
        """
        self.tac = tac
        self.system_prompt = system_prompt
        self.openai_client = openai.AsyncOpenAI(api_key=os.environ.get("TWILIO_TAC_OPENAI_API_KEY"))
        self.tools = tools or []
        # Conversation history per conversation_id
        self.conversation_messages: dict[str, list[ChatCompletionMessageParam]] = {}

    async def stream_response(
        self,
        prompt: str,
        conv_id: str,
        context: ConversationSession,
    ) -> AsyncGenerator[str, None]:
        """
        Stream LLM response with memory retrieval and context.

        Args:
            prompt: User's message
            conv_id: Conversation ID
            context: Conversation session context

        Yields:
            Response chunks from the LLM
        """
        try:
            logger.info(
                f"[LLM] ===== Starting stream_response for conversation {conv_id[:8]} ====="
            )
            logger.info(f"[LLM] Prompt: {prompt[:100]}...")
            logger.info(f"[LLM] Tools available: {len(self.tools)}")
            logger.info(f"[LLM] Processing prompt for conversation {conv_id[:8]}...")

            # Initialize conversation history if needed
            if conv_id not in self.conversation_messages:
                system_msg: ChatCompletionSystemMessageParam = {
                    "role": "system",
                    "content": self.system_prompt,
                }
                self.conversation_messages[conv_id] = [system_msg]

            # Add current user message to history
            user_msg: ChatCompletionUserMessageParam = {"role": "user", "content": prompt}
            self.conversation_messages[conv_id].append(user_msg)

            # Retrieve memory if enabled
            memory_response = None
            if self.tac.is_twilio_memory_enabled():
                try:
                    memory_response = await self.tac.retrieve_memory(context, query=prompt)
                    if memory_response:
                        obs_count = (
                            len(memory_response.observations) if memory_response.observations else 0
                        )
                        sum_count = (
                            len(memory_response.summaries) if memory_response.summaries else 0
                        )
                        logger.info(
                            f"[MEMORY] Retrieved {obs_count} observations, {sum_count} summaries"
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to retrieve memory for conversation {conv_id}: {e}",
                        exc_info=True,
                    )

            # Build enhanced system prompt with memory context
            enhanced_system_prompt = self.system_prompt
            if memory_response:
                context_parts = [self.system_prompt, "\n=== RELEVANT CONTEXT ==="]
                if memory_response.observations:
                    context_parts.append("\nObservations:")
                    for obs in memory_response.observations[:3]:  # Limit to top 3
                        context_parts.append(f"- {obs.content}")
                enhanced_system_prompt = "\n".join(context_parts)
                self.conversation_messages[conv_id][0] = {
                    "role": "system",
                    "content": enhanced_system_prompt,
                }

            # Prepare tools for OpenAI (if any)
            openai_tools = None
            if self.tools:
                openai_tools = [tool.to_openai_format() for tool in self.tools]
                logger.info(f"[TOOLS] Sending {len(self.tools)} tools to OpenAI:")
                for tool in self.tools:
                    logger.info(f"[TOOLS]   - {tool.name}: {tool.description[:100]}...")

            # Stream response from OpenAI
            logger.debug(
                f"[LLM] Starting OpenAI stream with {len(self.conversation_messages[conv_id])} messages"
            )
            stream = await self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=self.conversation_messages[conv_id],
                tools=openai_tools,  # type: ignore[arg-type]
                stream=True,
            )

            full_response = ""
            tool_calls: list[dict[str, Any]] = []
            current_tool_call: Optional[dict[str, Any]] = None

            async for chunk in stream:  # type: ignore[union-attr]
                delta = chunk.choices[0].delta

                # Handle content streaming
                if delta.content:
                    content = delta.content
                    full_response += content
                    yield content

                # Handle tool calls
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        if tc_delta.index is not None:
                            # Start new tool call or continue existing one
                            while len(tool_calls) <= tc_delta.index:
                                tool_calls.append(
                                    {
                                        "id": "",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""},
                                    }
                                )
                            current_tool_call = tool_calls[tc_delta.index]

                            if tc_delta.id:
                                current_tool_call["id"] = tc_delta.id
                            if tc_delta.function:
                                if tc_delta.function.name:
                                    current_tool_call["function"]["name"] = tc_delta.function.name
                                if tc_delta.function.arguments:
                                    current_tool_call["function"]["arguments"] += (
                                        tc_delta.function.arguments
                                    )

            # If there were tool calls, execute them and continue
            logger.info(f"[TOOLS] Stream completed. Detected {len(tool_calls)} tool calls")
            if tool_calls:
                logger.info("[TOOLS] Tool calls detected:")
                for tc in tool_calls:
                    logger.info(
                        f"[TOOLS]   - {tc['function']['name']}: {tc['function']['arguments'][:100]}..."
                    )
                logger.info(f"[TOOLS] Executing {len(tool_calls)} tool calls")

                # Add assistant message with tool calls to history
                assistant_with_tools: ChatCompletionAssistantMessageParam = {
                    "role": "assistant",
                    "content": full_response if full_response else None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": tc["function"]["arguments"],
                            },
                        }
                        for tc in tool_calls
                    ],
                }
                self.conversation_messages[conv_id].append(assistant_with_tools)

                # Execute tools and add results
                for tc in tool_calls:
                    tool_name = tc["function"]["name"]
                    tool_args_str = tc["function"]["arguments"]
                    tool_id = tc["id"]

                    # Find the tool
                    found_tool = next((t for t in self.tools if t.name == tool_name), None)
                    if not found_tool:
                        logger.error(f"[TOOLS] Tool not found: {tool_name}")
                        continue

                    try:
                        # Parse arguments and execute tool
                        tool_args = json.loads(tool_args_str)
                        logger.info(
                            f"[TOOLS] Executing {tool_name} with args: {json.dumps(tool_args)}"
                        )
                        result = await found_tool(**tool_args)
                        result_str = json.dumps(result)
                        logger.info(f"[TOOLS] Tool {tool_name} returned {len(result_str)} chars")
                        logger.debug(f"[TOOLS] Tool result preview: {result_str[:200]}...")

                        # Add tool result to messages
                        tool_msg: ChatCompletionToolMessageParam = {
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "content": result_str,
                        }
                        self.conversation_messages[conv_id].append(tool_msg)
                    except Exception as e:
                        logger.error(
                            f"[TOOLS] Error executing tool {tool_name}: {e}", exc_info=True
                        )
                        error_msg: ChatCompletionToolMessageParam = {
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "content": f"Error: {str(e)}",
                        }
                        self.conversation_messages[conv_id].append(error_msg)

                # Get final response after tool execution
                final_stream = await self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=self.conversation_messages[conv_id],
                    tools=openai_tools,  # type: ignore[arg-type]
                    stream=True,
                )

                final_response = ""
                async for chunk in final_stream:  # type: ignore[union-attr]
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        final_response += content
                        yield content

                # Add final assistant response to history
                final_assistant_msg: ChatCompletionAssistantMessageParam = {
                    "role": "assistant",
                    "content": final_response,
                }
                self.conversation_messages[conv_id].append(final_assistant_msg)
                logger.info(
                    f"[LLM] Completed streaming {len(final_response)} characters (after tools)"
                )
            else:
                # No tool calls, just add the response to history
                logger.info(
                    f"[TOOLS] No tool calls made by LLM. Response length: {len(full_response)} chars"
                )
                assistant_msg: ChatCompletionAssistantMessageParam = {
                    "role": "assistant",
                    "content": full_response,
                }
                self.conversation_messages[conv_id].append(assistant_msg)
                logger.info(f"[LLM] Completed streaming {len(full_response)} characters")

        except asyncio.CancelledError:
            logger.info(f"[LLM] Streaming cancelled for conversation {conv_id}")
            raise
        except Exception as e:
            logger.error(f"[LLM] Error in stream_response: {e}", exc_info=True)
            yield "I'm sorry, I'm having trouble processing your message right now."
