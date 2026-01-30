"""Knowledge API tools for the Twilio Agent Connect."""

from typing import Annotated, Optional

from pydantic import BaseModel

from tac.context.knowledge import KnowledgeClient
from tac.models.knowledge import KnowledgeChunkResult
from tac.tools.base import InjectedToolArg, TACTool, function_tool


class KnowledgeToolConfig(BaseModel):
    """Configuration to customize the generated knowledge tool."""

    name: Optional[str] = None
    description: Optional[str] = None
    top_k: int = 5  # Number of knowledge chunks to return


async def search_knowledge(
    query: str,
    knowledge_client: Annotated[KnowledgeClient, InjectedToolArg],
    knowledge_base_id: Annotated[str, InjectedToolArg],
    top_k: Annotated[int, InjectedToolArg],
) -> list[KnowledgeChunkResult]:
    """
    Search the knowledge base with the given query.

    Args:
        query: The search query string (max 2048 characters)
        knowledge_client: KnowledgeClient instance for API calls (injected, not visible to LLM)
        knowledge_base_id: Knowledge base ID to search (injected, not visible to LLM)
        top_k: Number of chunks to return (injected, not visible to LLM)

    Returns:
        List of KnowledgeChunkResult objects with content, knowledge_id, created_at, and score
    """
    return await knowledge_client.search_knowledge_base(
        knowledge_base_id=knowledge_base_id,
        query=query,
        top_k=top_k,
    )


async def create_knowledge_tool(
    knowledge_client: KnowledgeClient,
    knowledge_base_id: str,
    tool_config: Optional[KnowledgeToolConfig] = None,
) -> TACTool:
    """
    Create a knowledge search tool for the given knowledge base.

    Creates a function tool that searches the specified knowledge using Twilio's
    Knowledge Base Search API via KnowledgeClient. The tool uses dependency injection
    to hide the knowledge client and knowledge ID from the LLM schema.

    If tool_config provides name and description, uses them directly (no API call).
    If either is missing, fetches the knowledge base metadata to use as defaults.

    Args:
        knowledge_client: KnowledgeClient instance for searching knowledge bases
        knowledge_base_id: Knowledge base ID string (e.g., "know_knowledgebase_...")
        tool_config: Optional configuration for tool name, description, and top-K

    Returns:
        A configured TACTool that searches the specified knowledge with injected dependencies

    Example with custom name and description (no API call):
        >>> tool = await create_knowledge_tool(
        ...     knowledge_client=tac.knowledge_client,
        ...     knowledge_base_id="know_knowledgebase_...",
        ...     tool_config=KnowledgeToolConfig(
        ...         name="search_promotions",
        ...         description="Search for promotions and discounts",
        ...         top_k=3,
        ...     ),
        ... )

    Example using KB metadata as defaults (fetches KB):
        >>> tool = await create_knowledge_tool(
        ...     knowledge_client=tac.knowledge_client,
        ...     knowledge_base_id="know_knowledgebase_...",
        ...     tool_config=KnowledgeToolConfig(top_k=3),
        ... )
    """
    tool_config = tool_config or KnowledgeToolConfig()

    # If name and description are provided, use them directly (no fetch needed)
    if tool_config.name and tool_config.description:
        tool_name = tool_config.name
        tool_description = tool_config.description
    else:
        # Fetch knowledge base metadata to use as fallback
        knowledge_base = await knowledge_client.get_knowledge_base(knowledge_base_id)
        tool_name = tool_config.name or (
            f"search_{knowledge_base.display_name.lower().replace(' ', '_').replace('-', '_')}"
        )
        tool_description = tool_config.description or (
            f"{knowledge_base.description}\n\nThe input MUST be a question in the form of a string."
        )

    # Wrap the standalone search_knowledge function with the tool decorator
    knowledge_tool = function_tool(name=tool_name, description=tool_description)(search_knowledge)

    # Configure injection
    return knowledge_tool.configure_injection(
        knowledge_client=knowledge_client,
        knowledge_base_id=knowledge_base_id,
        top_k=tool_config.top_k,
    )
