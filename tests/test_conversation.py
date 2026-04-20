"""Tests for ConversationClient and related models."""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from tac.context.conversation import ConversationClient
from tac.models.conversation import (
    Communication,
    CommunicationContent,
    CommunicationParticipant,
    CommunicationRequest,
    ConversationRequest,
    ConversationResponse,
    ParticipantRequest,
    ParticipantResponse,
    SendCommunicationParticipantAddress,
    SendCommunicationRequest,
    SendCommunicationResponse,
)


class TestConversationModels:
    """Test Pydantic models for conversation API."""

    def test_conversation_response_model(self):
        """Test ConversationResponse model with all fields."""
        response_data = {
            "id": "CH123456",
            "account_id": "AC123456",
            "configuration_id": "conv_configuration_test123",
            "status": "ACTIVE",
            "name": "Test Conversation",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T01:00:00Z",
        }

        conversation = ConversationResponse(**response_data)

        assert conversation.id == "CH123456"
        assert conversation.account_id == "AC123456"
        assert conversation.configuration_id == "conv_configuration_test123"
        assert conversation.status == "ACTIVE"
        assert conversation.name == "Test Conversation"
        assert conversation.created_at == "2025-01-01T00:00:00Z"
        assert conversation.updated_at == "2025-01-01T01:00:00Z"

    def test_conversation_response_minimal_fields(self):
        """Test ConversationResponse with only required fields."""
        response_data = {
            "id": "CH123456",
            "account_id": "AC123456",
        }

        conversation = ConversationResponse(**response_data)

        assert conversation.id == "CH123456"
        assert conversation.account_id == "AC123456"
        assert conversation.configuration_id is None
        assert conversation.status is None
        assert conversation.name is None
        assert conversation.created_at is None
        assert conversation.updated_at is None

    def test_conversation_request_model(self):
        """Test ConversationRequest model with all fields."""
        request_data = {
            "configuration_id": "conv_configuration_test123",
            "name": "Test Conversation",
        }

        request = ConversationRequest(**request_data)

        assert request.configuration_id == "conv_configuration_test123"
        assert request.name == "Test Conversation"

    def test_conversation_request_minimal(self):
        """Test ConversationRequest with only required fields."""
        request = ConversationRequest(configuration_id="conv_configuration_test123")

        assert request.configuration_id == "conv_configuration_test123"
        assert request.name is None

    def test_participant_request_model(self):
        """Test ParticipantRequest model with all fields."""
        request_data = {
            "name": "John Doe",
            "type": "CUSTOMER",
            "profile_id": "profile_123",
            "addresses": [{"channel": "SMS", "address": "+15551234567"}],
        }

        request = ParticipantRequest(**request_data)

        assert request.name == "John Doe"
        assert request.type == "CUSTOMER"
        assert request.profile_id == "profile_123"
        assert len(request.addresses) == 1
        assert request.addresses[0].channel == "SMS"
        assert request.addresses[0].address == "+15551234567"

    def test_participant_request_minimal(self):
        """Test ParticipantRequest with no fields (all optional)."""
        request = ParticipantRequest()

        assert request.name is None
        assert request.type is None
        assert request.profile_id is None
        assert request.addresses == []

    def test_participant_request_model_dump(self):
        """Test ParticipantRequest model_dump excludes None values."""
        request = ParticipantRequest(name="John", profile_id="profile_123")

        payload = request.model_dump(by_alias=True, exclude_none=True)

        # addresses has default_factory=list, so it's included as empty list
        assert payload == {"name": "John", "profileId": "profile_123", "addresses": []}
        assert "type" not in payload

    def test_participant_response_model(self):
        """Test ParticipantResponse model with all fields."""
        response_data = {
            "id": "MB123456",
            "conversationId": "CH123456",
            "accountId": "AC123456",
            "name": "John Doe",
            "type": "CUSTOMER",
            "profileId": "profile_123",
            "addresses": [{"channel": "SMS", "address": "+15551234567"}],
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-01-01T01:00:00Z",
        }

        participant = ParticipantResponse(**response_data)

        assert participant.id == "MB123456"
        assert participant.conversation_id == "CH123456"
        assert participant.account_id == "AC123456"
        assert participant.name == "John Doe"
        assert participant.type == "CUSTOMER"
        assert participant.profile_id == "profile_123"
        assert len(participant.addresses) == 1
        assert participant.addresses[0].channel == "SMS"
        assert participant.addresses[0].address == "+15551234567"
        assert participant.created_at == "2025-01-01T00:00:00Z"
        assert participant.updated_at == "2025-01-01T01:00:00Z"

    def test_participant_response_minimal_fields(self):
        """Test ParticipantResponse with only required fields."""
        response_data = {
            "id": "MB123456",
            "conversationId": "CH123456",
            "accountId": "AC123456",
            "name": "Participant",
        }

        participant = ParticipantResponse(**response_data)

        assert participant.id == "MB123456"
        assert participant.conversation_id == "CH123456"
        assert participant.account_id == "AC123456"
        assert participant.name == "Participant"
        assert participant.type is None
        assert participant.profile_id is None
        assert participant.addresses == []
        assert participant.created_at is None
        assert participant.updated_at is None

    def test_participant_request_with_agent_type(self):
        """Test ParticipantRequest accepts AGENT type."""
        request = ParticipantRequest(
            name="Agent Bot",
            type="AGENT",
            profile_id="profile_agent_123",
        )

        assert request.type == "AGENT"
        payload = request.model_dump(by_alias=True, exclude_none=True)
        assert payload["type"] == "AGENT"

    def test_participant_request_with_unknown_type(self):
        """Test ParticipantRequest accepts UNKNOWN type."""
        request = ParticipantRequest(
            name="Unknown Participant",
            type="UNKNOWN",
        )

        assert request.type == "UNKNOWN"
        payload = request.model_dump(by_alias=True, exclude_none=True)
        assert payload["type"] == "UNKNOWN"

    def test_participant_response_with_agent_type(self):
        """Test ParticipantResponse validates webhook payload with AGENT type."""
        # Simulates webhook payload from API with new AGENT type
        response_data = {
            "id": "MB123456",
            "conversationId": "CH123456",
            "accountId": "AC123456",
            "name": "Agent System",
            "type": "AGENT",
            "addresses": [{"channel": "SMS", "address": "+18887608751"}],
        }

        participant = ParticipantResponse(**response_data)

        assert participant.id == "MB123456"
        assert participant.type == "AGENT"
        assert participant.name == "Agent System"

    def test_participant_response_with_unknown_type(self):
        """Test ParticipantResponse validates webhook payload with UNKNOWN type."""
        # Simulates webhook payload from API with new UNKNOWN type
        response_data = {
            "id": "MB123456",
            "conversationId": "CH123456",
            "accountId": "AC123456",
            "name": "Unknown Entity",
            "type": "UNKNOWN",
        }

        participant = ParticipantResponse(**response_data)

        assert participant.id == "MB123456"
        assert participant.type == "UNKNOWN"
        assert participant.name == "Unknown Entity"

    def test_participant_response_all_types(self):
        """Test ParticipantResponse accepts all valid participant types."""
        valid_types = ["HUMAN_AGENT", "CUSTOMER", "AI_AGENT", "AGENT", "UNKNOWN"]

        for participant_type in valid_types:
            response_data = {
                "id": f"MB_{participant_type}",
                "conversationId": "CH123456",
                "accountId": "AC123456",
                "name": f"{participant_type} Participant",
                "type": participant_type,
            }

            participant = ParticipantResponse(**response_data)
            assert participant.type == participant_type

    def test_communication_request_model(self):
        """Test CommunicationRequest model with all fields."""
        request_data = {
            "author": {
                "address": "+12025551234",
                "channel": "SMS",
                "participantId": "comms_participant_01k1etx3jbfx88476ccja0889c",
            },
            "content": {"type": "TEXT", "text": "Hello World!"},
            "recipients": [
                {
                    "address": "+12025551234",
                    "channel": "SMS",
                    "participantId": "comms_participant_01k1etx3jbfx88476ccja0889c",
                }
            ],
        }

        request = CommunicationRequest(**request_data)

        assert request.author.address == "+12025551234"
        assert request.author.channel == "SMS"
        assert request.author.participant_id == "comms_participant_01k1etx3jbfx88476ccja0889c"
        assert request.content.text == "Hello World!"
        assert len(request.recipients) == 1
        assert request.recipients[0].address == "+12025551234"

    def test_communication_request_model_dump(self):
        """Test CommunicationRequest model_dump with alias mapping."""
        author = CommunicationParticipant(
            address="+12025551234",
            channel="SMS",
            participantId="comms_participant_123",
        )
        content = CommunicationContent(type="TEXT", text="Hello World!")
        recipient = CommunicationParticipant(
            address="+12025555678", channel="SMS", participantId="comms_participant_456"
        )
        request = CommunicationRequest(author=author, content=content, recipients=[recipient])

        payload = request.model_dump(by_alias=True, exclude_none=True)

        assert payload == {
            "author": {
                "address": "+12025551234",
                "channel": "SMS",
                "participantId": "comms_participant_123",
            },
            "content": {"type": "TEXT", "text": "Hello World!"},
            "recipients": [
                {
                    "address": "+12025555678",
                    "channel": "SMS",
                    "participantId": "comms_participant_456",
                }
            ],
        }

    def test_communication_response_model(self):
        """Test Communication model with all fields."""
        response_data = {
            "id": "comms_communication_01k1etk2y5f1y9fpe2epfdtvv2",
            "conversationId": "CH123456",
            "accountId": "AC123456",
            "author": {
                "address": "+12025551234",
                "channel": "SMS",
                "participantId": "comms_participant_01k1etx3jbfx88476ccja0889c",
            },
            "content": {"type": "TEXT", "text": "Hello World!"},
            "channelId": "SM123456",
            "recipients": [
                {
                    "address": "+12025551234",
                    "channel": "SMS",
                    "participantId": "comms_participant_01k1etx3jbfx88476ccja0889c",
                    "deliveryStatus": "INITIATED",
                }
            ],
            "createdAt": "2019-08-24T14:15:22Z",
            "updatedAt": "2019-08-24T14:15:22Z",
        }

        response = Communication(**response_data)

        assert response.id == "comms_communication_01k1etk2y5f1y9fpe2epfdtvv2"
        assert response.conversation_id == "CH123456"
        assert response.account_id == "AC123456"
        assert response.author.address == "+12025551234"
        assert response.content.text == "Hello World!"
        assert response.channel_id == "SM123456"
        assert len(response.recipients) == 1
        assert response.created_at == "2019-08-24T14:15:22Z"
        assert response.updated_at == "2019-08-24T14:15:22Z"


class TestConversationClient:
    """Test ConversationClient API interactions."""

    def test_client_initialization(self):
        """Test ConversationClient initialization."""
        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )

        assert client.base_url == "https://conversations.twilio.com"
        assert client.configuration_id == "conv_configuration_test123"
        assert client.api_key == "SK123456"
        assert client.api_token == "test_token"

    def test_client_initialization_with_region(self):
        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
            region="au1",
        )
        assert client.base_url == "https://conversations.au1.twilio.com"

    def test_client_initialization_without_region(self):
        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )
        assert client.base_url == "https://conversations.twilio.com"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_create_conversation_success(self, mock_async_client_class):
        """Test successful conversation creation."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "CH123456",
            "accountId": "AC123456",
            "configurationId": "conv_configuration_test123",
            "status": "ACTIVE",
        }
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_async_client_class.return_value.__aenter__.return_value = mock_client

        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )

        result = await client.create_conversation()

        # Verify API call
        mock_client.post.assert_called_once_with(
            "https://conversations.twilio.com/v2/Conversations",
            json={"configurationId": "conv_configuration_test123"},
        )

        # Verify response
        assert isinstance(result, ConversationResponse)
        assert result.id == "CH123456"
        assert result.account_id == "AC123456"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_create_conversation_with_parameters(self, mock_async_client_class):
        """Test conversation creation with optional parameters."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "CH123456",
            "accountId": "AC123456",
            "configurationId": "conv_configuration_test123",
            "name": "Customer Support",
            "status": "ACTIVE",
        }
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_async_client_class.return_value.__aenter__.return_value = mock_client

        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )

        result = await client.create_conversation(name="Customer Support")

        # Verify API call includes all parameters
        mock_client.post.assert_called_once_with(
            "https://conversations.twilio.com/v2/Conversations",
            json={"configurationId": "conv_configuration_test123", "name": "Customer Support"},
        )

        # Verify response
        assert isinstance(result, ConversationResponse)
        assert result.id == "CH123456"
        assert result.name == "Customer Support"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_create_conversation_api_error(self, mock_async_client_class):
        """Test create_conversation handles API errors."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.HTTPError("API Error"))
        mock_async_client_class.return_value.__aenter__.return_value = mock_client

        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )

        with pytest.raises(httpx.HTTPError, match="API Error"):
            await client.create_conversation()

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_add_participant_success(self, mock_async_client_class):
        """Test successful participant addition."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "MB123456",
            "conversationId": "CH123456",
            "accountId": "AC123456",
            "name": "John Doe",
            "profileId": "profile_123",
            "type": "CUSTOMER",
            "addresses": [],
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-01-01T01:00:00Z",
        }
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_async_client_class.return_value.__aenter__.return_value = mock_client

        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )

        result = await client.add_participant(
            conversation_id="CH123456",
        )

        # Verify API call
        expected_url = "https://conversations.twilio.com/v2/Conversations/CH123456/Participants"
        mock_client.post.assert_called_once_with(
            expected_url,
            json={},  # No default type - API determines participant type
        )

        # Verify response
        assert isinstance(result, ParticipantResponse)
        assert result.id == "MB123456"
        assert result.conversation_id == "CH123456"
        assert result.name == "John Doe"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_add_participant_with_minimal_params(self, mock_async_client_class):
        """Test add_participant with only some optional parameters."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "MB123456",
            "conversationId": "CH123456",
            "accountId": "AC123456",
            "name": "System",
            "profileId": "profile_123",
            "type": "CUSTOMER",
            "addresses": [],
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-01-01T01:00:00Z",
        }
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_async_client_class.return_value.__aenter__.return_value = mock_client

        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )

        result = await client.add_participant(
            conversation_id="CH123456",
        )

        # Verify only non-None values are sent
        assert mock_client.post.call_args[1]["json"] == {}

        # Verify response
        assert isinstance(result, ParticipantResponse)
        assert result.id == "MB123456"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_add_participant_api_error(self, mock_async_client_class):
        """Test add_participant handles API errors."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.HTTPError("API Error"))
        mock_async_client_class.return_value.__aenter__.return_value = mock_client

        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )

        with pytest.raises(httpx.HTTPError, match="API Error"):
            await client.add_participant(
                conversation_id="CH123456",
            )

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_add_participant_with_agent_type(self, mock_async_client_class):
        """Test add_participant with participant_type=AGENT."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "MB123456",
            "conversationId": "CH123456",
            "accountId": "AC123456",
            "name": "Agent System",
            "type": "AGENT",
            "addresses": [],
        }
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_async_client_class.return_value.__aenter__.return_value = mock_client

        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )

        result = await client.add_participant(
            conversation_id="CH123456",
            participant_type="AGENT",
        )

        # Verify the request payload contains the AGENT type
        assert mock_client.post.call_args[1]["json"]["type"] == "AGENT"

        # Verify response
        assert isinstance(result, ParticipantResponse)
        assert result.type == "AGENT"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_add_participant_with_unknown_type(self, mock_async_client_class):
        """Test add_participant with participant_type=UNKNOWN."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "MB123456",
            "conversationId": "CH123456",
            "accountId": "AC123456",
            "name": "Unknown Entity",
            "type": "UNKNOWN",
            "addresses": [],
        }
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_async_client_class.return_value.__aenter__.return_value = mock_client

        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )

        result = await client.add_participant(
            conversation_id="CH123456",
            participant_type="UNKNOWN",
        )

        # Verify the request payload contains the UNKNOWN type
        assert mock_client.post.call_args[1]["json"]["type"] == "UNKNOWN"

        # Verify response
        assert isinstance(result, ParticipantResponse)
        assert result.type == "UNKNOWN"

    def test_conversation_client_uses_correct_headers(self):
        """Test that ConversationClient stores authentication credentials."""
        # Credentials are stored as instance variables and passed to httpx.AsyncClient
        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )

        # Verify credentials are stored
        assert client.api_key == "SK123456"
        assert client.api_token == "test_token"
        # Note: These credentials are passed to httpx.AsyncClient as auth=(api_key, api_token)

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_conversation_client_constructs_correct_url(self, mock_async_client_class):
        """Test that ConversationClient constructs correct service-scoped URLs."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "CH123456",
            "account_id": "AC123456",
        }
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_async_client_class.return_value.__aenter__.return_value = mock_client

        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test999",
        )

        # Test create_conversation URL
        await client.create_conversation()
        assert (
            mock_client.post.call_args[0][0] == "https://conversations.twilio.com/v2/Conversations"
        )

        # Test add_participant URL
        mock_response.json.return_value = {
            "id": "MB123456",
            "conversationId": "CH123456",
            "accountId": "AC123456",
            "name": "Test",
            "profileId": "profile_123",
            "type": "CUSTOMER",
            "addresses": [],
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-01-01T01:00:00Z",
        }

        await client.add_participant(conversation_id="CH123456")

        expected_url = "https://conversations.twilio.com/v2/Conversations/CH123456/Participants"
        assert mock_client.post.call_args[0][0] == expected_url

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_create_communication_success(self, mock_async_client_class):
        """Test successful communication addition."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "comms_communication_01k1etk2y5f1y9fpe2epfdtvv2",
            "conversationId": "CH123456",
            "accountId": "AC123456",
            "author": {
                "address": "+12025551234",
                "channel": "SMS",
                "participantId": "comms_participant_123",
            },
            "content": {"type": "TEXT", "text": "Hello World!"},
            "channelId": "SM123456",
            "recipients": [
                {
                    "address": "+12025555678",
                    "channel": "SMS",
                    "participantId": "comms_participant_456",
                    "deliveryStatus": "INITIATED",
                }
            ],
            "createdAt": "2019-08-24T14:15:22Z",
            "updatedAt": "2019-08-24T14:15:22Z",
        }
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_async_client_class.return_value.__aenter__.return_value = mock_client

        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )

        # Create communication request
        author = CommunicationParticipant(
            address="+12025551234", channel="SMS", participantId="comms_participant_123"
        )
        content = CommunicationContent(type="TEXT", text="Hello World!")
        recipient = CommunicationParticipant(
            address="+12025555678", channel="SMS", participantId="comms_participant_456"
        )
        comm_request = CommunicationRequest(author=author, content=content, recipients=[recipient])

        result = await client.create_communication(
            conversation_id="CH123456", communication_request=comm_request
        )

        # Verify API call
        expected_url = "https://conversations.twilio.com/v2/Conversations/CH123456/Communications"
        mock_client.post.assert_called_once()
        assert mock_client.post.call_args[0][0] == expected_url

        # Verify request payload
        payload = mock_client.post.call_args[1]["json"]
        assert payload["author"]["address"] == "+12025551234"
        assert payload["content"]["text"] == "Hello World!"
        assert len(payload["recipients"]) == 1

        # Verify response
        assert isinstance(result, Communication)
        assert result.id == "comms_communication_01k1etk2y5f1y9fpe2epfdtvv2"
        assert result.author.address == "+12025551234"
        assert result.content.text == "Hello World!"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_create_communication_api_error(self, mock_async_client_class):
        """Test create_communication handles API errors."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.HTTPError("API Error"))
        mock_async_client_class.return_value.__aenter__.return_value = mock_client

        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )

        # Create communication request
        author = CommunicationParticipant(
            address="+12025551234", channel="SMS", participantId="comms_participant_123"
        )
        content = CommunicationContent(type="TEXT", text="Hello World!")
        recipient = CommunicationParticipant(
            address="+12025555678", channel="SMS", participantId="comms_participant_456"
        )
        comm_request = CommunicationRequest(author=author, content=content, recipients=[recipient])

        with pytest.raises(httpx.HTTPError, match="API Error"):
            await client.create_communication(
                conversation_id="CH123456", communication_request=comm_request
            )

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_list_communications_success(self, mock_async_client_class):
        """Test successful communications list retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "communications": [
                {
                    "id": "comms_communication_01",
                    "conversationId": "CH123456",
                    "accountId": "AC123456",
                    "serviceId": "IS123456",
                    "author": {
                        "address": "+12025551234",
                        "channel": "SMS",
                        "participantId": "comms_participant_123",
                    },
                    "content": {"type": "TEXT", "text": "Hello"},
                    "recipients": [
                        {
                            "address": "+12025555678",
                            "channel": "SMS",
                            "participantId": "comms_participant_456",
                        }
                    ],
                    "createdAt": "2019-08-24T14:15:22Z",
                    "updatedAt": "2019-08-24T14:15:22Z",
                },
                {
                    "id": "comms_communication_02",
                    "conversationId": "CH123456",
                    "accountId": "AC123456",
                    "serviceId": "IS123456",
                    "author": {
                        "address": "+12025555678",
                        "channel": "SMS",
                        "participantId": "comms_participant_456",
                    },
                    "content": {"type": "TEXT", "text": "World"},
                    "recipients": [
                        {
                            "address": "+12025551234",
                            "channel": "SMS",
                            "participantId": "comms_participant_123",
                        }
                    ],
                    "createdAt": "2019-08-24T14:16:22Z",
                    "updatedAt": "2019-08-24T14:16:22Z",
                },
            ],
            "meta": {
                "key": "items",
                "pageSize": 20,
                "previousToken": None,
                "nextToken": "eyJwYWdlIjoyLCJxdWVyeSI6ImJvb2tzIn0=",
            },
        }
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_async_client_class.return_value.__aenter__.return_value = mock_client

        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )

        result = await client.list_communications(conversation_id="CH123456")

        # Verify API call
        expected_url = "https://conversations.twilio.com/v2/Conversations/CH123456/Communications"
        mock_client.get.assert_called_once_with(expected_url, params={})

        # Verify response
        assert len(result) == 2
        assert result[0].id == "comms_communication_01"
        assert result[0].content.text == "Hello"
        assert result[1].id == "comms_communication_02"
        assert result[1].content.text == "World"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_list_communications_with_parameters(self, mock_async_client_class):
        """Test list_communications with query parameters."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "communications": [],
            "meta": {
                "key": "items",
                "pageSize": 50,
                "previousToken": None,
                "nextToken": None,
            },
        }
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_async_client_class.return_value.__aenter__.return_value = mock_client

        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )

        result = await client.list_communications(
            conversation_id="CH123456",
            channel_id="SM123456",
            page_size=50,
            page_token="token123",
        )

        # Verify API call includes query parameters
        expected_url = "https://conversations.twilio.com/v2/Conversations/CH123456/Communications"
        expected_params = {
            "channelId": "SM123456",
            "pageSize": 50,
            "pageToken": "token123",
        }
        mock_client.get.assert_called_once_with(expected_url, params=expected_params)

        # Verify response
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_list_communications_api_error(self, mock_async_client_class):
        """Test list_communications handles API errors."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("API Error"))
        mock_async_client_class.return_value.__aenter__.return_value = mock_client

        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )

        with pytest.raises(httpx.HTTPError, match="API Error"):
            await client.list_communications(conversation_id="CH123456")

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_send_communication_success(self, mock_async_client_class):
        """Test successful communication send via POST /v2/Communications."""
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.json.return_value = {
            "message": "Conversation setup complete",
            "conversationId": "CH123456",
            "channelId": "SM123456",
        }
        mock_response.raise_for_status = Mock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_async_client_class.return_value.__aenter__.return_value = mock_client

        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )

        # Create send request
        author = SendCommunicationParticipantAddress(
            address="+15551234567", channel="SMS", participant_id="comms_participant_agent"
        )
        content = CommunicationContent(type="TEXT", text="Hello from agent!")
        recipient = SendCommunicationParticipantAddress(
            address="+12025551234", channel="SMS", participant_id="comms_participant_customer"
        )
        send_request = SendCommunicationRequest(
            author=author, content=content, recipients=[recipient]
        )

        result = await client.send_communication(conversation_id="CH123456", request=send_request)

        # Verify API call
        expected_url = "https://conversations.twilio.com/v2/Communications"
        mock_client.post.assert_called_once()
        assert mock_client.post.call_args[0][0] == expected_url

        # Verify request payload includes conversationId
        payload = mock_client.post.call_args[1]["json"]
        assert payload["conversationId"] == "CH123456"
        assert payload["author"]["address"] == "+15551234567"
        assert payload["content"]["text"] == "Hello from agent!"
        assert len(payload["recipients"]) == 1

        # Verify response
        assert isinstance(result, SendCommunicationResponse)
        assert result.message == "Conversation setup complete"
        assert result.conversation_id == "CH123456"
        assert result.channel_id == "SM123456"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_send_communication_api_error(self, mock_async_client_class):
        """Test send_communication handles API errors."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "400 Bad Request",
                request=Mock(),
                response=Mock(status_code=400, text='{"error": "Invalid request"}'),
            )
        )
        mock_async_client_class.return_value.__aenter__.return_value = mock_client

        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )

        # Create send request
        author = SendCommunicationParticipantAddress(
            address="+15551234567", channel="SMS", participant_id="comms_participant_agent"
        )
        content = CommunicationContent(type="TEXT", text="Hello from agent!")
        recipient = SendCommunicationParticipantAddress(
            address="+12025551234", channel="SMS", participant_id="comms_participant_customer"
        )
        send_request = SendCommunicationRequest(
            author=author, content=content, recipients=[recipient]
        )

        with pytest.raises(httpx.HTTPStatusError, match="400 Bad Request"):
            await client.send_communication(conversation_id="CH123456", request=send_request)

    @pytest.mark.no_auto_mock
    def test_get_configuration_success(self):
        """Test successful configuration retrieval."""
        from tac.models.conversation import ConversationConfiguration

        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "conv_configuration_test123",
            "memoryStoreId": "MGtest123",
            "displayName": "Test Configuration",
            "description": "Test configuration description",
            "conversationGroupingType": "GROUP_BY_PARTICIPANT_ADDRESSES_AND_CHANNEL_TYPE",
        }
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.get = Mock(return_value=mock_response)
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)

        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )

        with patch.object(client, "_get_sync_client", return_value=mock_client):
            result = client.get_configuration(configuration_id="conv_configuration_test123")

        # Verify API call
        expected_url = "https://conversations.twilio.com/v2/ControlPlane/Configurations/conv_configuration_test123"
        mock_client.get.assert_called_once_with(expected_url)

        # Verify response
        assert isinstance(result, ConversationConfiguration)
        assert result.id == "conv_configuration_test123"
        assert result.memory_store_id == "MGtest123"
        assert result.display_name == "Test Configuration"

    @pytest.mark.no_auto_mock
    def test_get_configuration_http_error(self):
        """Test get_configuration handles HTTP errors."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "401 Unauthorized",
                request=Mock(),
                response=Mock(status_code=401, text='{"error": "Unauthorized"}'),
            )
        )

        mock_client = Mock()
        mock_client.get = Mock(return_value=mock_response)
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)

        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )

        with patch.object(client, "_get_sync_client", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError, match="401 Unauthorized"):
                client.get_configuration(configuration_id="conv_configuration_test123")

    @pytest.mark.no_auto_mock
    def test_get_configuration_validation_error(self):
        """Test get_configuration handles schema validation errors."""
        mock_response = Mock()
        # Missing required field 'description'
        mock_response.json.return_value = {
            "id": "conv_configuration_test123",
            "memoryStoreId": "MGtest123",
            "displayName": "Test Configuration",
            # Missing 'description' - required field
            "conversationGroupingType": "GROUP_BY_PARTICIPANT_ADDRESSES_AND_CHANNEL_TYPE",
        }
        mock_response.raise_for_status = Mock()
        mock_response.text = '{"id":"conv_configuration_test123","memoryStoreId":"MGtest123"}'

        mock_client = Mock()
        mock_client.get = Mock(return_value=mock_response)
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)

        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )

        with patch.object(client, "_get_sync_client", return_value=mock_client):
            with pytest.raises(ValueError, match="Invalid configuration response schema"):
                client.get_configuration(configuration_id="conv_configuration_test123")

    @pytest.mark.no_auto_mock
    def test_get_configuration_network_error(self):
        """Test get_configuration handles network errors."""
        mock_client = Mock()
        mock_client.get = Mock(side_effect=httpx.NetworkError("Connection failed"))
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)

        client = ConversationClient(
            api_key="SK123456",
            api_token="test_token",
            configuration_id="conv_configuration_test123",
        )

        with patch.object(client, "_get_sync_client", return_value=mock_client):
            with pytest.raises(httpx.NetworkError, match="Connection failed"):
                client.get_configuration(configuration_id="conv_configuration_test123")
