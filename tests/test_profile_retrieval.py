"""Tests for profile retrieval functionality."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from tac import TAC, TACConfig
from tac.channels.sms import SMSChannel
from tac.context.memory import MemoryClient
from tac.core.config import TwilioMemoryConfig
from tac.models.memory import (
    MemoryRetrievalMeta,
    MemoryRetrievalResponse,
    ProfileLookupResponse,
    ProfileResponse,
)
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse


def create_participant_added_webhook(
    conversation_id: str, participant_id: str, profile_id: str, timestamp: str
) -> dict[str, Any]:
    """Create a PARTICIPANT_ADDED webhook event."""
    return {
        "eventType": "PARTICIPANT_ADDED",
        "timestamp": timestamp,
        "data": {
            "id": participant_id,
            "conversationId": conversation_id,
            "accountId": "ACtest123",
            "serviceId": "IStest123",
            "name": "+12345678901",
            "type": "CUSTOMER",
            "profileId": profile_id,
            "addresses": [{"channel": "SMS", "address": "+12345678901", "channelId": None}],
            "createdAt": timestamp,
            "updatedAt": timestamp,
        },
    }


def create_communication_created_webhook(
    conversation_id: str,
    participant_id: str,
    message_text: str,
    timestamp: str,
    author_address: str = "+12345678901",
) -> dict[str, Any]:
    """Create a COMMUNICATION_CREATED webhook event."""
    # Generate unique communication ID using timestamp to avoid deduplication
    comm_id = f"comms_communication_{timestamp.replace(':', '').replace('.', '').replace('-', '')}"
    return {
        "eventType": "COMMUNICATION_CREATED",
        "timestamp": timestamp,
        "data": {
            "id": comm_id,
            "conversationId": conversation_id,
            "accountId": "ACtest123",
            "serviceId": "IStest123",
            "author": {
                "address": author_address,
                "channel": "SMS",
                "participantId": participant_id,
            },
            "content": {"type": "TEXT", "text": message_text},
            "channelId": None,
            "recipients": [
                {
                    "address": "+15551234567",
                    "channel": "SMS",
                    "participantId": "comms_participant_agent",
                    "deliveryStatus": "DELIVERED",
                }
            ],
            "createdAt": timestamp,
            "updatedAt": timestamp,
        },
    }


def get_test_config_with_trait_groups(trait_groups: list[str] | None = None) -> TACConfig:
    """Get test configuration with optional trait groups."""
    memory_config = TwilioMemoryConfig(
        trait_groups=trait_groups,
    )
    return TACConfig(
        environment="prod",
        conversation_configuration_id="conv_configuration_test123",
        twilio_auth_token="test_token_123",
        api_key="SK123",
        api_token="test_api_token",
        twilio_phone_number="+15551234567",
        twilio_memory_config=memory_config,
    )


def create_memory_client(tac: TAC) -> MemoryClient:
    """Helper to manually create Conversation Memory client for tests."""
    return MemoryClient(
        base_url=tac.config.memory_base_url,
        store_id="MGtest123",
        api_key=tac.config.api_key,
        api_token=tac.config.api_token,
    )


def get_mock_profile_response() -> ProfileResponse:
    """Get a mock ProfileResponse for testing."""
    return ProfileResponse(
        id="profile_test_123",
        createdAt="2025-01-15T10:30:45Z",
        traits={
            "Contact": {
                "firstName": "John",
                "lastName": "Doe",
                "address": {
                    "street": "123 Main St",
                    "city": "San Francisco",
                    "state": "CA",
                    "postalCode": "94107",
                    "country": "US",
                },
            },
            "Preferences": {
                "language": "en",
                "timezone": "America/Los_Angeles",
            },
        },
    )


class TestProfileRetrieval:
    """Tests for profile retrieval functionality."""

    @pytest.mark.asyncio
    async def test_profile_fetched_with_trait_groups(self) -> None:
        """Test that profile is fetched with configured trait groups."""
        config = get_test_config_with_trait_groups(trait_groups=["Contact", "Preferences"])
        tac = TAC(config)
        tac.conversation_memory_client = create_memory_client(tac)

        mock_profile = get_mock_profile_response()

        tac.conversation_memory_client.get_profile = AsyncMock(return_value=mock_profile)
        profile = await tac.fetch_profile("profile_test_123")

        # Verify profile was fetched
        assert profile is not None
        assert profile.id == "profile_test_123"
        assert "Contact" in profile.traits
        assert "Preferences" in profile.traits
        assert profile.traits["Contact"]["firstName"] == "John"

        # Verify get_profile was called with correct trait_groups
        tac.conversation_memory_client.get_profile.assert_called_once_with(
            profile_id="profile_test_123",
            trait_groups=["Contact", "Preferences"],
        )

    @pytest.mark.asyncio
    async def test_profile_fetched_without_trait_groups(self) -> None:
        """Test that profile is fetched without trait_groups when not configured."""
        config = get_test_config_with_trait_groups(trait_groups=None)
        tac = TAC(config)
        tac.conversation_memory_client = create_memory_client(tac)

        mock_profile = get_mock_profile_response()

        tac.conversation_memory_client.get_profile = AsyncMock(return_value=mock_profile)
        profile = await tac.fetch_profile("profile_test_123")

        # Verify profile was fetched
        assert profile is not None
        assert profile.id == "profile_test_123"

        # Verify get_profile was called with trait_groups=None
        tac.conversation_memory_client.get_profile.assert_called_once_with(
            profile_id="profile_test_123",
            trait_groups=None,
        )

    @pytest.mark.asyncio
    async def test_profile_fetch_error_handling(self) -> None:
        """Test that profile fetch errors are handled gracefully."""
        config = get_test_config_with_trait_groups()
        tac = TAC(config)
        tac.conversation_memory_client = create_memory_client(tac)

        # Simulate an error during profile fetch
        tac.conversation_memory_client.get_profile = AsyncMock(side_effect=Exception("API Error"))
        profile = await tac.fetch_profile("profile_test_123")

        # Verify None is returned on error (not raised)
        assert profile is None

    @pytest.mark.asyncio
    async def test_profile_fetch_with_empty_profile_id(self) -> None:
        """Test that profile fetch handles empty profile_id gracefully."""
        config = get_test_config_with_trait_groups()
        tac = TAC(config)
        tac.conversation_memory_client = create_memory_client(tac)

        # Test with empty string
        profile = await tac.fetch_profile("")
        assert profile is None


class TestProfileInSMSChannel:
    """Tests for profile retrieval in SMS channel."""

    @pytest.mark.asyncio
    async def test_sms_profile_available_in_callback(self) -> None:
        """Test that profile is available in callback context for SMS."""
        config = get_test_config_with_trait_groups(trait_groups=["Contact"])
        tac = TAC(config)
        tac.conversation_memory_client = create_memory_client(tac)
        channel = SMSChannel(tac, config={"auto_retrieve_memory": True})  # Enable auto retrieval

        # Track callback data
        received_context = None

        def message_ready_callback(
            user_message: str,
            context: ConversationSession,
            memory_response: TACMemoryResponse | None = None,
        ) -> None:
            nonlocal received_context
            received_context = context

        tac.on_message_ready(message_ready_callback)

        mock_profile = get_mock_profile_response()

        # Simulate participant.added webhook with profile
        participant_webhook = create_participant_added_webhook(
            "CH123456", "MB123", "profile_test_123", "2025-11-18T00:00:00.000Z"
        )

        # Simulate message webhook
        message_webhook = create_communication_created_webhook(
            "CH123456", "MB123", "Hello!", "2025-11-18T00:00:01.000Z"
        )

        tac.conversation_memory_client.get_profile = AsyncMock(return_value=mock_profile)
        empty_memory = MemoryRetrievalResponse(
            observations=[],
            summaries=[],
            sessions=[],
            meta=MemoryRetrievalMeta(queryTime=0),
        )
        tac.conversation_memory_client.retrieve_memory = AsyncMock(return_value=empty_memory)

        # Process participant.added first (stores profile_id)
        await channel.process_webhook(participant_webhook)

        # Verify profile_id was stored but profile NOT fetched yet (lazy)
        assert "CH123456" in channel._conversations
        session = channel._conversations["CH123456"]
        assert session.profile_id == "profile_test_123"
        assert session.profile is None  # Profile not fetched until message

        # Process message (triggers memory retrieval which fetches profile)
        await channel.process_webhook(message_webhook)

        # Verify profile was fetched during message processing
        tac.conversation_memory_client.get_profile.assert_called_once_with(
            profile_id="profile_test_123",
            trait_groups=["Contact"],
        )

        # Verify profile is in context
        assert received_context is not None
        assert received_context.profile is not None
        assert received_context.profile.id == "profile_test_123"
        assert received_context.profile.traits["Contact"]["firstName"] == "John"

    @pytest.mark.asyncio
    async def test_sms_profile_fetched_on_conversation_start(self) -> None:
        """Test that profile_id is stored but profile fetch is deferred (lazy)."""

        config = get_test_config_with_trait_groups(trait_groups=["Contact"])
        tac = TAC(config)
        tac.conversation_memory_client = create_memory_client(tac)
        channel = SMSChannel(tac)

        mock_profile = get_mock_profile_response()

        # Simulate participant.added webhook (stores profile_id only)
        participant_added = create_participant_added_webhook(
            "CH123456", "MB123", "profile_test_123", "2025-11-18T00:00:00.000Z"
        )

        tac.conversation_memory_client.get_profile = AsyncMock(return_value=mock_profile)
        await channel.process_webhook(participant_added)

        # Verify profile was NOT fetched (lazy behavior)
        tac.conversation_memory_client.get_profile.assert_not_called()

        # Verify conversation was created with profile_id but no profile yet
        assert "CH123456" in channel._conversations
        session = channel._conversations["CH123456"]
        assert session.profile_id == "profile_test_123"
        assert session.profile is None  # Profile not fetched until needed

    @pytest.mark.asyncio
    async def test_sms_profile_fetched_for_each_message(self) -> None:
        """Test that profile is fetched once and then cached."""
        config = get_test_config_with_trait_groups()
        tac = TAC(config)
        tac.conversation_memory_client = create_memory_client(tac)
        channel = SMSChannel(tac, config={"auto_retrieve_memory": True})  # Enable auto retrieval

        mock_profile = get_mock_profile_response()

        # Simulate participant.added first
        participant_webhook = create_participant_added_webhook(
            "CH123456", "MB123", "profile_test_123", "2025-11-18T00:00:00.000Z"
        )

        # Simulate first message
        message_webhook_1 = create_communication_created_webhook(
            "CH123456", "MB123", "First message", "2025-11-18T00:00:01.000Z"
        )

        tac.conversation_memory_client.get_profile = AsyncMock(return_value=mock_profile)
        empty_memory = MemoryRetrievalResponse(
            observations=[],
            summaries=[],
            sessions=[],
            meta=MemoryRetrievalMeta(queryTime=0),
        )
        tac.conversation_memory_client.retrieve_memory = AsyncMock(return_value=empty_memory)

        # Process participant.added (profile NOT fetched, lazy behavior)
        await channel.process_webhook(participant_webhook)
        first_call_count = tac.conversation_memory_client.get_profile.call_count
        assert first_call_count == 0  # No fetch on participant.added

        # Process first message (profile fetched during retrieve_memory)
        await channel.process_webhook(message_webhook_1)
        second_call_count = tac.conversation_memory_client.get_profile.call_count
        assert second_call_count == 1  # First fetch

        # Simulate second message
        message_webhook_2 = create_communication_created_webhook(
            "CH123456", "MB123", "Second message", "2025-11-18T00:00:02.000Z"
        )

        # Process second message (profile NOT fetched again, cached)
        await channel.process_webhook(message_webhook_2)
        third_call_count = tac.conversation_memory_client.get_profile.call_count

        # Verify profile was fetched only once (then cached)
        assert second_call_count > first_call_count
        assert third_call_count == second_call_count  # No additional fetch, cached
        assert third_call_count == 1  # Only one fetch total (then cached)

    @pytest.mark.asyncio
    async def test_sms_profile_updates_session(self) -> None:
        """Test that profile is cached and persists across messages."""
        config = get_test_config_with_trait_groups()
        tac = TAC(config)
        tac.conversation_memory_client = create_memory_client(tac)
        channel = SMSChannel(tac, config={"auto_retrieve_memory": True})  # Enable auto retrieval

        mock_profile_v1 = ProfileResponse(
            id="profile_test_123",
            createdAt="2025-01-15T10:30:45Z",
            traits={"Contact": {"firstName": "John"}},
        )

        mock_profile_v2 = ProfileResponse(
            id="profile_test_123",
            createdAt="2025-01-15T11:30:45Z",
            traits={"Contact": {"firstName": "Jane"}},  # Updated name
        )

        # Participant added event
        participant_webhook = create_participant_added_webhook(
            "CH123456", "MB123", "profile_test_123", "2025-11-18T00:00:00.000Z"
        )

        # First message
        message_webhook_1 = create_communication_created_webhook(
            "CH123456", "MB123", "Hello", "2025-11-18T00:00:01.000Z"
        )

        # Second message
        message_webhook_2 = create_communication_created_webhook(
            "CH123456", "MB123", "Hi again", "2025-11-18T00:00:02.000Z"
        )

        empty_memory = MemoryRetrievalResponse(
            observations=[],
            summaries=[],
            sessions=[],
            meta=MemoryRetrievalMeta(queryTime=0),
        )
        tac.conversation_memory_client.retrieve_memory = AsyncMock(return_value=empty_memory)

        # Process participant.added (no profile fetch, lazy behavior)
        await channel.process_webhook(participant_webhook)
        session = channel._conversations["CH123456"]
        assert session.profile is None  # Profile not fetched yet

        # Process first message with profile v1
        tac.conversation_memory_client.get_profile = AsyncMock(return_value=mock_profile_v1)
        await channel.process_webhook(message_webhook_1)
        session = channel._conversations["CH123456"]
        assert session.profile is not None
        assert session.profile.traits["Contact"]["firstName"] == "John"

        # Process second message - profile remains cached (v1), not fetched again
        tac.conversation_memory_client.get_profile = AsyncMock(return_value=mock_profile_v2)
        await channel.process_webhook(message_webhook_2)
        session = channel._conversations["CH123456"]
        assert session.profile is not None
        # Profile is cached, so it remains "John" (not updated to "Jane")
        assert session.profile.traits["Contact"]["firstName"] == "John"


class TestProfileInConversationSession:
    """Tests for profile field in ConversationSession."""

    def test_conversation_session_with_profile(self) -> None:
        """Test ConversationSession can be created with profile."""
        mock_profile = get_mock_profile_response()

        session = ConversationSession(
            conversation_id="CH123456",
            profile_id="profile_test_123",
            channel="sms",
            profile=mock_profile,
        )

        assert session.profile is not None
        assert session.profile.id == "profile_test_123"
        assert session.profile.traits["Contact"]["firstName"] == "John"

    def test_conversation_session_without_profile(self) -> None:
        """Test ConversationSession can be created without profile."""
        session = ConversationSession(
            conversation_id="CH123456",
            profile_id="profile_test_123",
            channel="sms",
            profile=None,
        )

        assert session.profile is None

    def test_conversation_session_profile_default_none(self) -> None:
        """Test that profile defaults to None when not provided."""
        session = ConversationSession(
            conversation_id="CH123456",
            profile_id="profile_test_123",
            channel="sms",
            profile=None,  # Explicitly set to None (also the default)
        )

        assert session.profile is None


class TestProfileLookup:
    """Tests for profile lookup functionality."""

    @pytest.mark.asyncio
    async def test_profile_lookup_by_phone(self) -> None:
        """Test profile lookup by phone number."""
        config = get_test_config_with_trait_groups()
        tac = TAC(config)
        tac.conversation_memory_client = create_memory_client(tac)

        mock_lookup_response = ProfileLookupResponse(
            normalizedValue="+13175556789",
            profiles=["mem_profile_00000000000000000000000001"],
        )

        tac.conversation_memory_client.lookup_profile = AsyncMock(return_value=mock_lookup_response)
        response = await tac.conversation_memory_client.lookup_profile(
            id_type="phone", value="+1 (317) 555-6789"
        )

        # Verify response
        assert response.normalized_value == "+13175556789"
        assert len(response.profiles) == 1
        assert response.profiles[0] == "mem_profile_00000000000000000000000001"

        # Verify lookup_profile was called with correct parameters
        tac.conversation_memory_client.lookup_profile.assert_called_once_with(
            id_type="phone", value="+1 (317) 555-6789"
        )

    @pytest.mark.asyncio
    async def test_profile_lookup_by_email(self) -> None:
        """Test profile lookup by email address."""
        config = get_test_config_with_trait_groups()
        tac = TAC(config)
        tac.conversation_memory_client = create_memory_client(tac)

        mock_lookup_response = ProfileLookupResponse(
            normalizedValue="test@example.com",
            profiles=["mem_profile_00000000000000000000000002"],
        )

        tac.conversation_memory_client.lookup_profile = AsyncMock(return_value=mock_lookup_response)
        response = await tac.conversation_memory_client.lookup_profile(
            id_type="email", value="test@example.com"
        )

        # Verify response
        assert response.normalized_value == "test@example.com"
        assert len(response.profiles) == 1
        assert response.profiles[0] == "mem_profile_00000000000000000000000002"

    @pytest.mark.asyncio
    async def test_profile_lookup_multiple_matches(self) -> None:
        """Test profile lookup with multiple matching profiles."""
        config = get_test_config_with_trait_groups()
        tac = TAC(config)
        tac.conversation_memory_client = create_memory_client(tac)

        mock_lookup_response = ProfileLookupResponse(
            normalizedValue="+13175556789",
            profiles=[
                "mem_profile_00000000000000000000000001",
                "mem_profile_00000000000000000000000002",
            ],
        )

        tac.conversation_memory_client.lookup_profile = AsyncMock(return_value=mock_lookup_response)
        response = await tac.conversation_memory_client.lookup_profile(
            id_type="phone", value="+13175556789"
        )

        # Verify multiple profiles returned
        assert len(response.profiles) == 2
        assert "mem_profile_00000000000000000000000001" in response.profiles
        assert "mem_profile_00000000000000000000000002" in response.profiles

    @pytest.mark.asyncio
    async def test_profile_lookup_no_matches(self) -> None:
        """Test profile lookup with no matching profiles."""
        config = get_test_config_with_trait_groups()
        tac = TAC(config)
        tac.conversation_memory_client = create_memory_client(tac)

        mock_lookup_response = ProfileLookupResponse(
            normalizedValue="+13175556789",
            profiles=[],
        )

        tac.conversation_memory_client.lookup_profile = AsyncMock(return_value=mock_lookup_response)
        response = await tac.conversation_memory_client.lookup_profile(
            id_type="phone", value="+13175556789"
        )

        # Verify empty profiles list
        assert len(response.profiles) == 0

    @pytest.mark.asyncio
    async def test_profile_lookup_error_handling(self) -> None:
        """Test profile lookup error handling."""
        config = get_test_config_with_trait_groups()
        tac = TAC(config)
        tac.conversation_memory_client = create_memory_client(tac)

        # Simulate API error
        tac.conversation_memory_client.lookup_profile = AsyncMock(
            side_effect=Exception("Profile lookup API error")
        )

        with pytest.raises(Exception, match="Profile lookup API error"):
            await tac.conversation_memory_client.lookup_profile(
                id_type="phone", value="+13175556789"
            )
