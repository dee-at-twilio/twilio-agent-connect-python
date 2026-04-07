from typing import Any, Literal

import httpx
from pydantic import ValidationError

from tac.core.logging import get_logger
from tac.models.conversation import (
    Communication,
    CommunicationRequest,
    CommunicationsListResponse,
    ConversationConfiguration,
    ConversationRequest,
    ConversationResponse,
    ConversationsListResponse,
    ParticipantAddress,
    ParticipantRequest,
    ParticipantResponse,
    SendCommunicationRequest,
    SendCommunicationResponse,
    UpdateConversationRequest,
)


class ConversationClient:
    """Client for interacting with Conversation Orchestrator API."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        api_token: str,
        configuration_id: str,
    ) -> None:
        """
        Initialize the Conversation client.

        Args:
            base_url: Base URL for the Conversation Orchestrator API
            api_key: Twilio API Key SID for authentication
            api_token: Twilio API Key Secret for authentication
            configuration_id: Conversation Configuration ID for API requests
        """
        self.base_url = base_url
        self.configuration_id = configuration_id
        self.api_key = api_key
        self.api_token = api_token
        self.logger = get_logger(__name__)

    def _get_client(self) -> httpx.AsyncClient:
        """Create a new httpx.AsyncClient for each request to avoid event loop issues."""
        return httpx.AsyncClient(
            auth=(self.api_key, self.api_token),
            timeout=30.0,
        )

    def _get_sync_client(self) -> httpx.Client:
        """Create a new synchronous httpx.Client."""
        return httpx.Client(
            auth=(self.api_key, self.api_token),
            timeout=30.0,
        )

    async def list_conversations(
        self,
        status: list[Literal["ACTIVE", "INACTIVE", "CLOSED"]] | None = None,
        channel_id: str | None = None,
        page_size: int | None = None,
        page_token: str | None = None,
    ) -> list[ConversationResponse]:
        """
        List conversations with optional filtering and pagination.

        Args:
            status: Optional list of statuses to filter conversations
                   ("ACTIVE", "INACTIVE", "CLOSED")
            channel_id: Optional resource ID (call ID, message ID, etc.) to filter conversations
            page_size: Maximum number of items to return (1-1000)
            page_token: Token for pagination

        Returns:
            List of ConversationResponse objects

        Raises:
            httpx.HTTPError: If the API request fails
        """
        url = f"{self.base_url}/v2/Conversations"

        # Build query parameters
        params: dict[str, Any] = {}
        if status:
            params["status"] = status
        if channel_id:
            params["channelId"] = channel_id
        if page_size:
            params["pageSize"] = page_size
        if page_token:
            params["pageToken"] = page_token

        try:
            async with self._get_client() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                conversations_list = ConversationsListResponse(**response.json())
                return conversations_list.conversations

        except httpx.HTTPError as e:
            response_text = (
                getattr(e.response, "text", "No response body")
                if hasattr(e, "response")
                else "No response"
            )
            self.logger.error(
                f"Failed to list conversations: {e}\n"
                f"URL: {url}\n"
                f"Query params: {params}\n"
                f"Response: {response_text}"
            )
            raise

    async def add_participant(
        self,
        conversation_id: str,
        addresses: list[ParticipantAddress] | None = None,
        participant_type: Literal["HUMAN_AGENT", "CUSTOMER", "AI_AGENT"] = "CUSTOMER",
    ) -> ParticipantResponse:
        """
        Add a new participant to a conversation.

        Args:
            conversation_id: The conversation ID to add participant to
            addresses: List of communication addresses for the participant (optional)
            participant_type: Type of participant (e.g., "CUSTOMER", "AGENT").
                Defaults to "CUSTOMER"

        Returns:
            ParticipantResponse object containing the created participant details

        Raises:
            httpx.HTTPError: If the API request fails
        """
        url = f"{self.base_url}/v2/Conversations/{conversation_id}/Participants"

        request_data = ParticipantRequest(addresses=addresses, type=participant_type)
        request_payload = request_data.model_dump(by_alias=True, exclude_none=True)

        try:
            async with self._get_client() as client:
                response = await client.post(
                    url,
                    json=request_payload,
                )
                response.raise_for_status()
                participant = ParticipantResponse(**response.json())
                return participant

        except httpx.HTTPError as e:
            response_text = (
                getattr(e.response, "text", "No response body")
                if hasattr(e, "response")
                else "No response"
            )
            self.logger.error(
                f"Failed to add participant: {e}\n"
                f"URL: {url}\n"
                f"Request body: {request_payload}\n"
                f"Response: {response_text}"
            )
            raise

    async def list_participants(self, conversation_id: str) -> list[ParticipantResponse]:
        url = f"{self.base_url}/v2/Conversations/{conversation_id}/Participants"

        try:
            async with self._get_client() as client:
                response = await client.get(url)
                response.raise_for_status()
                participants = response.json().get("participants", [])
                return [ParticipantResponse(**p) for p in participants]
        except httpx.TimeoutException:
            self.logger.error(f"Timeout listing participants for conversation {conversation_id}")
            return []
        except httpx.HTTPError as e:
            self.logger.error(
                f"HTTP error listing participants for conversation {conversation_id}: {e}"
            )
            return []
        except ValueError as e:
            self.logger.error(f"Invalid JSON format when listing participants: {e}")
            return []

    async def create_conversation(
        self,
        name: str | None = None,
    ) -> ConversationResponse:
        """
        Create a new conversation.

        Args:
            name: Conversation name (optional)

        Returns:
            ConversationResponse object containing the created conversation details

        Raises:
            httpx.HTTPError: If the API request fails
        """
        url = f"{self.base_url}/v2/Conversations"

        request_data = ConversationRequest(configuration_id=self.configuration_id, name=name)
        request_payload = request_data.model_dump(by_alias=True, exclude_none=True)

        try:
            async with self._get_client() as client:
                response = await client.post(
                    url,
                    json=request_payload,
                )
                response.raise_for_status()
                conversation = ConversationResponse(**response.json())
                return conversation

        except httpx.HTTPError as e:
            response_text = (
                getattr(e.response, "text", "No response body")
                if hasattr(e, "response")
                else "No response"
            )
            self.logger.error(
                f"Failed to create conversation: {e}\n"
                f"URL: {url}\n"
                f"Request body: {request_payload}\n"
                f"Response: {response_text}"
            )
            raise

    async def update_conversation(
        self,
        conversation_id: str,
        status: Literal["ACTIVE", "INACTIVE", "CLOSED"],
        name: str | None = None,
    ) -> ConversationResponse:
        """
        Update an existing conversation.

        Args:
            conversation_id: The conversation ID to update
            status: Conversation status to update ("ACTIVE", "INACTIVE", "CLOSED") - required
            name: Optional conversation name to update

        Returns:
            ConversationResponse object containing the updated conversation details

        Raises:
            httpx.HTTPError: If the API request fails
        """
        url = f"{self.base_url}/v2/Conversations/{conversation_id}"

        request_data = UpdateConversationRequest(status=status, name=name)
        request_payload = request_data.model_dump(by_alias=True, exclude_none=True)

        try:
            async with self._get_client() as client:
                response = await client.put(
                    url,
                    json=request_payload,
                )
                response.raise_for_status()
                conversation = ConversationResponse(**response.json())
                return conversation

        except httpx.HTTPError as e:
            response_text = (
                getattr(e.response, "text", "No response body")
                if hasattr(e, "response")
                else "No response"
            )
            self.logger.error(
                f"Failed to update conversation: {e}\n"
                f"URL: {url}\n"
                f"Request body: {request_payload}\n"
                f"Response: {response_text}"
            )
            raise

    async def create_communication(
        self,
        conversation_id: str,
        communication_request: CommunicationRequest,
    ) -> Communication:
        """
        Create a new communication for a conversation.

        Args:
            conversation_id: The conversation ID to create communication for
            communication_request: CommunicationRequest object with author, content, and recipients

        Returns:
            Communication object containing the created communication details

        Raises:
            httpx.HTTPError: If the API request fails
        """
        url = f"{self.base_url}/v2/Conversations/{conversation_id}/Communications"

        request_payload = communication_request.model_dump(by_alias=True, exclude_none=True)

        try:
            async with self._get_client() as client:
                response = await client.post(
                    url,
                    json=request_payload,
                )
                response.raise_for_status()
                communication = Communication(**response.json())
                return communication

        except httpx.HTTPError as e:
            response_text = (
                getattr(e.response, "text", "No response body")
                if hasattr(e, "response")
                else "No response"
            )
            self.logger.error(
                f"Failed to add communication: {e}\n"
                f"URL: {url}\n"
                f"Request body: {request_payload}\n"
                f"Response: {response_text}"
            )
            raise

    async def list_communications(
        self,
        conversation_id: str,
        channel_id: str | None = None,
        page_size: int | None = None,
        page_token: str | None = None,
    ) -> list[Communication]:
        """
        List communications for a conversation.

        Args:
            conversation_id: The conversation ID to list communications for
            channel_id: Optional channel ID filter (call ID, message ID, etc.)
            page_size: Maximum number of items to return (1-1000)
            page_token: Token for pagination

        Returns:
            List of Communication objects

        Raises:
            httpx.HTTPError: If the API request fails
        """
        url = f"{self.base_url}/v2/Conversations/{conversation_id}/Communications"

        # Build query parameters
        params: dict[str, Any] = {}
        if channel_id:
            params["channelId"] = channel_id
        if page_size:
            params["pageSize"] = page_size
        if page_token:
            params["pageToken"] = page_token

        try:
            async with self._get_client() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                communications_list = CommunicationsListResponse(**response.json())
                return communications_list.communications

        except httpx.HTTPError as e:
            response_text = (
                getattr(e.response, "text", "No response body")
                if hasattr(e, "response")
                else "No response"
            )
            self.logger.error(
                f"Failed to list communications: {e}\n"
                f"URL: {url}\n"
                f"Query params: {params}\n"
                f"Response: {response_text}"
            )
            raise

    async def send_communication(
        self,
        conversation_id: str,
        request: SendCommunicationRequest,
    ) -> SendCommunicationResponse:
        """
        Send a communication via POST /v2/Communications.

        This endpoint sets up necessary conversation infrastructure and sends the message.
        Returns 202 Accepted. The Communication record is created asynchronously after
        delivery.

        Args:
            conversation_id: The conversation ID to send the communication to
            request: SendCommunicationRequest with author, content, and recipients

        Returns:
            SendCommunicationResponse with message, conversationId, and channelId

        Raises:
            httpx.HTTPError: If the API request fails
        """
        url = f"{self.base_url}/v2/Communications"

        # Merge conversationId into the request body
        request_payload = {
            "conversationId": conversation_id,
            **request.model_dump(by_alias=True, exclude_none=True),
        }

        try:
            async with self._get_client() as client:
                response = await client.post(url, json=request_payload)
                response.raise_for_status()

                # Expect 202 Accepted, warn on other 2xx
                if response.status_code != 202:
                    self.logger.warning(
                        f"Expected 202 Accepted, got {response.status_code}",
                        url=url,
                        status_code=response.status_code,
                    )

                send_response = SendCommunicationResponse(**response.json())
                return send_response

        except httpx.HTTPError as e:
            response_text = (
                getattr(e.response, "text", "No response body")
                if hasattr(e, "response")
                else "No response"
            )
            self.logger.error(
                f"Failed to send communication: {e}\n"
                f"URL: {url}\n"
                f"ConversationId: {conversation_id}\n"
                f"Response: {response_text}"
            )
            raise

    def get_configuration(self, configuration_id: str) -> ConversationConfiguration:
        """
        Retrieve the details for a single configuration.

        Args:
            configuration_id: The configuration ID to retrieve

        Returns:
            ConversationConfiguration object containing the configuration details

        Raises:
            httpx.HTTPError: If the API request fails
            ValueError: If the response schema is invalid
        """
        url = f"{self.base_url}/v2/ControlPlane/Configurations/{configuration_id}"

        try:
            with self._get_sync_client() as client:
                response = client.get(url)
                response.raise_for_status()

                try:
                    configuration = ConversationConfiguration(**response.json())
                    return configuration
                except ValidationError as e:
                    self.logger.error(
                        f"Failed to parse configuration response: {e}\n"
                        f"URL: {url}\nResponse: {response.text}"
                    )
                    raise ValueError(f"Invalid configuration response schema: {e}") from e

        except httpx.HTTPError as e:
            response_text = (
                getattr(e.response, "text", "No response body")
                if hasattr(e, "response")
                else "No response"
            )
            self.logger.error(
                f"Failed to get configuration: {e}\nURL: {url}\nResponse: {response_text}"
            )
            raise
