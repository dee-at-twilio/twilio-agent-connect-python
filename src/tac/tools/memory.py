"""Memory API tools for the Twilio Agent Connect."""

from typing import Annotated, Any

from tac.context.memory import MemoryClient
from tac.models.session import ConversationSession
from tac.tools.base import InjectedToolArg, TACTool, function_tool


async def retrieve_profile_memory(
    query: str,
    memory_client: Annotated[MemoryClient, InjectedToolArg],
    profile_id: Annotated[str, InjectedToolArg],
) -> dict[str, Any]:
    """
    Search and retrieve relevant memories for the current profile.

    Performs semantic search across the user's conversation history, observations,
    and stored traits to find contextually relevant information.

    Args:
        query: What to search for in the user's memory (e.g., "preferences about food",
               "previous complaints", "contact information")

    Returns:
        Dictionary containing relevant memories, traits, and metadata
    """
    memory_response = await memory_client.retrieve_memory(
        profile_id=profile_id,
        query=query,
    )
    return memory_response.model_dump(by_alias=True, exclude_none=True)


def create_memory_tool(memory_client: MemoryClient, session: ConversationSession) -> TACTool:
    """
    Create memory tool with injected MemoryClient and session context.

    Args:
        memory_client: MemoryClient instance for retrieving memories
        session: Current session identity with profile and conversation IDs

    Returns:
        Configured memory tool

    Example:
        >>> tool = create_memory_tool(memory_client, session)
        >>> # LLM only sees: retrieve_profile_memory(query: str)
        >>> result = await tool(query="user preferences")
    """
    # Wrap the standalone function with the tool decorator
    memory_tool = function_tool()(retrieve_profile_memory)

    # Configure injection with the memory client and profile ID
    return memory_tool.configure_injection(
        memory_client=memory_client,
        profile_id=session.profile_id,
    )
