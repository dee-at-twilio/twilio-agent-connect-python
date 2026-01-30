from typing import Any, Optional

import httpx

from tac.core.logging import get_logger
from tac.models.memory import (
    MemoryRetrievalRequest,
    MemoryRetrievalResponse,
    ProfileLookupRequest,
    ProfileLookupResponse,
    ProfileResponse,
)


class MemoryClient:
    """Client for interacting with Twilio Memora data plane API."""

    def __init__(
        self,
        base_url: str,
        store_id: str,
        api_key: str,
        api_token: str,
    ) -> None:
        """
        Initialize the Memory client.

        Args:
            base_url: Base URL for the Memora data plane API.
            store_id: Memory store ID (starts with mem_service_).
            api_key: API Key for Memora authentication.
            api_token: API Token for Memora authentication.
        """
        self.base_url = base_url
        self.store_id = store_id
        self.api_key = api_key
        self.api_token = api_token
        self.logger = get_logger(__name__)

    def _get_client(self) -> httpx.AsyncClient:
        """Create a new httpx.AsyncClient for each request to avoid event loop issues."""
        return httpx.AsyncClient(
            auth=(self.api_key, self.api_token),
            timeout=30.0,
        )

    async def retrieve_memory(
        self,
        profile_id: str,
        conversation_id: Optional[str] = None,
        query: Optional[str] = None,
    ) -> MemoryRetrievalResponse:
        """
        Retrieve conversation memories including observations, sessions, and summaries.
        Supports semantic search and uses default limits for different memory types.
        This endpoint is optimized for conversational AI and memory retrieval use cases.

        Args:
            profile_id: Profile ID using Twilio Type ID (TTID) format
            conversation_id: Optional conversation ID using Twilio Type ID (TTID) format
            query: Optional semantic search query for finding relevant memories (1-1024 characters)

        Returns:
            MemoryRetrievalResponse containing observations, summaries, sessions, and metadata

        Raises:
            requests.RequestException: If the API request fails
            ValueError: If the response cannot be parsed
        """

        # Use the correct endpoint from the API spec
        endpoint = f"/v1/Stores/{self.store_id}/Profiles/{profile_id}/Recall"
        url = f"{self.base_url}{endpoint}"

        # Create the request payload with default values
        request_data = MemoryRetrievalRequest(
            conversation_id=conversation_id,
            query=query,
        )
        request_payload = request_data.model_dump(by_alias=True, exclude_none=True)

        try:
            # POST request with JSON body as per API spec
            async with self._get_client() as client:
                response = await client.post(
                    url,
                    json=request_payload,
                )

                response.raise_for_status()

                # Parse the response according to the API spec
                data = response.json()
                memory_response = MemoryRetrievalResponse(**data)

                # Return full response with observations, summaries, sessions, and metadata
                return memory_response

        except httpx.HTTPError as e:
            response_text = (
                getattr(e.response, "text", "No response body")
                if hasattr(e, "response")
                else "No response"
            )
            self.logger.error(
                f"Failed to retrieve context from Memora: {e}\n"
                f"URL: {url}\n"
                f"Request body: {request_payload}\n"
                f"Response: {response_text}"
            )
            # Return empty response on API errors
            return MemoryRetrievalResponse()

        except Exception as e:
            self.logger.error(f"Failed to parse Memora response: {e}")
            # Return empty response on parsing errors
            return MemoryRetrievalResponse()

    async def get_profile(
        self,
        profile_id: str,
        trait_groups: Optional[list[str]] = None,
    ) -> ProfileResponse:
        """
        Retrieve a profile by ID with optional trait group selection.

        Args:
            profile_id: Profile ID using Twilio Type ID (TTID) format
            trait_groups: Optional list of trait group names to include in the response

        Returns:
            ProfileResponse containing profile ID, creation timestamp, and traits

        Raises:
            httpx.HTTPError: If the API request fails
            ValueError: If the response cannot be parsed
        """
        endpoint = f"/v1/Stores/{self.store_id}/Profiles/{profile_id}"
        url = f"{self.base_url}{endpoint}"

        params = {}
        if trait_groups:
            params["traitGroups"] = ",".join(trait_groups)

        self.logger.debug(f"Fetching profile {profile_id} from {url} with params: {params}")

        try:
            async with self._get_client() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()
                profile_response = ProfileResponse(**data)

                return profile_response
        except httpx.HTTPError as e:
            response_text = (
                getattr(e.response, "text", "No response body")
                if hasattr(e, "response")
                else "No response"
            )
            self.logger.error(
                f"Failed to retrieve profile from Memora: {e}\n"
                f"URL: {url}\n"
                f"Query params: {params}\n"
                f"Response: {response_text}"
            )
            raise
        except Exception as e:
            self.logger.error(f"Failed to generate Memora profile response: {e}")
            raise

    async def lookup_profile(
        self,
        id_type: str,
        value: str,
    ) -> ProfileLookupResponse:
        """
        Find profiles that contain a specific identifier value.

        Submit an identifier object specifying the idType and value.
        The value is normalized using the configured identity resolution settings
        (such as phone number formatting) prior to matching. Multiple matches are
        returned if more than one profile is associated with the identifier.
        Returns canonical profile IDs (the earliest ID if profiles have been merged)
        along with the normalized value actually searched.

        Args:
            id_type: Identifier type as configured in the service's Identity Resolution Settings
                    (e.g., "phone", "email"). Must be 2-30 characters.
            value: Raw value captured for the identifier (e.g., "+13175556789").
                  The service normalizes this value according to the configured rules.

        Returns:
            ProfileLookupResponse containing normalized value and list of matching profile IDs

        Raises:
            httpx.HTTPError: If the API request fails
            ValueError: If the response cannot be parsed
        """
        endpoint = f"/v1/Stores/{self.store_id}/Profiles/Lookup"
        url = f"{self.base_url}{endpoint}"

        request_data = ProfileLookupRequest(id_type=id_type, value=value)
        request_payload = request_data.model_dump(by_alias=True, exclude_none=True)

        self.logger.debug(
            f"Looking up profile with {id_type}={value} from {url} with payload: {request_payload}"
        )

        try:
            async with self._get_client() as client:
                response = await client.post(url, json=request_payload)
                response.raise_for_status()

                data = response.json()
                lookup_response = ProfileLookupResponse(**data)

                return lookup_response
        except httpx.HTTPError as e:
            response_text = (
                getattr(e.response, "text", "No response body")
                if hasattr(e, "response")
                else "No response"
            )
            self.logger.error(
                f"Failed to lookup profile from Memora: {e}\n"
                f"URL: {url}\n"
                f"Request body: {request_payload}\n"
                f"Response: {response_text}"
            )
            raise
        except Exception as e:
            self.logger.error(f"Failed to parse Memora lookup response: {e}")
            raise

    async def create_observation(
        self,
        profile_id: str,
        content: str,
        source: str = "conversation-intelligence",
        conversation_ids: Optional[list[str]] = None,
        occurred_at: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create a new observation in Memora.

        Args:
            profile_id: Profile ID to associate observation with
            content: Observation content (the summary text or extracted fact)
            source: Source system identifier (default: "conversation-intelligence")
            conversation_ids: List of conversation IDs this observation relates to
            occurred_at: Optional timestamp when observation occurred (ISO 8601 format)

        Returns:
            Dict with created observation details

        Raises:
            httpx.HTTPError: If the API request fails
        """
        endpoint = f"/v1/Stores/{self.store_id}/Profiles/{profile_id}/Observations"
        url = f"{self.base_url}{endpoint}"

        payload: dict[str, Any] = {
            "content": content,
            "source": source,
        }
        if conversation_ids:
            payload["conversationIds"] = conversation_ids
        if occurred_at:
            payload["occurredAt"] = occurred_at

        try:
            async with self._get_client() as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result: dict[str, Any] = response.json()
                return result

        except httpx.HTTPError as e:
            response_text = (
                getattr(e.response, "text", "No response body")
                if hasattr(e, "response")
                else "No response"
            )
            self.logger.error(
                f"Failed to create observation: {e}\n"
                f"URL: {url}\n"
                f"Profile ID: {profile_id}\n"
                f"Response: {response_text}"
            )
            raise

    async def create_conversation_summaries(
        self,
        profile_id: str,
        summaries: list[dict[str, Any]],
    ) -> dict[str, str]:
        """
        Create conversation summaries in Memora.

        Args:
            profile_id: Profile ID to associate summaries with
            summaries: List of summary objects, each containing:
                - content (str): The summary text
                - conversationId (str): The conversation ID
                - occurredAt (str): ISO 8601 timestamp when conversation occurred
                - source (str, optional): Source system identifier

        Returns:
            Response dict with message field (e.g., {"message": "Summaries creation accepted"})

        Raises:
            httpx.HTTPError: If the API request fails
        """
        endpoint = f"/v1/Stores/{self.store_id}/Profiles/{profile_id}/ConversationSummaries"
        url = f"{self.base_url}{endpoint}"

        payload: dict[str, Any] = {
            "summaries": summaries,
        }

        try:
            async with self._get_client() as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result: dict[str, str] = response.json()
                return result

        except httpx.HTTPError as e:
            response_text = (
                getattr(e.response, "text", "No response body")
                if hasattr(e, "response")
                else "No response"
            )
            self.logger.error(
                f"Failed to create conversation summaries: {e}\n"
                f"URL: {url}\n"
                f"Profile ID: {profile_id}\n"
                f"Summary count: {len(summaries)}\n"
                f"Response: {response_text}"
            )
            raise
