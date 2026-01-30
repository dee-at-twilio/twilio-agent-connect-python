from typing import Any, Optional

import httpx

from tac.core.logging import get_logger
from tac.models.knowledge import KnowledgeBase, KnowledgeChunkResult


class KnowledgeClient:
    """Client for interacting with Twilio Knowledge Base API."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        api_token: str,
    ) -> None:
        """
        Initialize the Knowledge client.

        Args:
            base_url: Base URL for the Knowledge Base API.
            api_key: API Key for Knowledge Base authentication.
            api_token: API Token for Knowledge Base authentication.
        """
        self.base_url = base_url
        self.api_key = api_key
        self.api_token = api_token
        self.logger = get_logger(__name__)

    def _get_client(self) -> httpx.AsyncClient:
        """Create a new httpx.AsyncClient for each request to avoid event loop issues."""
        return httpx.AsyncClient(
            auth=(self.api_key, self.api_token),
            timeout=30.0,
        )

    async def get_knowledge_base(self, knowledge_base_id: str) -> KnowledgeBase:
        """
        Fetch knowledge base metadata from the Knowledge Base API.

        Args:
            knowledge_base_id: The knowledge base ID to fetch (format: know_knowledgebase_*)

        Returns:
            KnowledgeBase object with metadata from the API

        Raises:
            httpx.HTTPError: If the API request fails
        """
        url = f"{self.base_url}/v2/ControlPlane/KnowledgeBases/{knowledge_base_id}"

        try:
            async with self._get_client() as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                return KnowledgeBase(**data)
        except httpx.HTTPError as e:
            self.logger.error(f"Failed to fetch knowledge base: {e}")
            raise

    async def search_knowledge_base(
        self,
        knowledge_base_id: str,
        query: str,
        top_k: int = 5,
        knowledge_ids: Optional[list[str]] = None,
    ) -> list[KnowledgeChunkResult]:
        """
        Search a knowledge base with the given query.

        Args:
            knowledge_base_id: The knowledge base ID to search (format: know_knowledgebase_*)
            query: The search query string (max 2048 characters)
            top_k: Number of knowledge chunks to return (default: 5, max: 20)
            knowledge_ids: Optional list of specific knowledge IDs to filter search results

        Returns:
            List of KnowledgeChunkResult objects with content and relevance scores

        Raises:
            httpx.HTTPError: If the API request fails
        """
        url = f"{self.base_url}/v2/KnowledgeBases/{knowledge_base_id}/Search"
        payload: dict[str, Any] = {
            "query": query,
            "top": top_k,
        }
        if knowledge_ids:
            payload["knowledgeIds"] = knowledge_ids

        try:
            async with self._get_client() as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()

                data = response.json()
                chunks = [KnowledgeChunkResult(**chunk) for chunk in data["chunks"]]
                return chunks

        except httpx.HTTPError as e:
            self.logger.error(f"Failed to search knowledge base: {e}")
            raise
