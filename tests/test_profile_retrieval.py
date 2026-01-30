"""Tests for profile retrieval functionality."""

from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tac import TAC, TACConfig
from tac.channels.sms import SMSChannel
from tac.core.config import TwilioMemoryConfig
from tac.models.memory import (
    MemoryRetrievalMeta,
    MemoryRetrievalResponse,
    ProfileLookupResponse,
    ProfileResponse,
)
from tac.models.session import ConversationSession


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


def get_test_config_with_trait_groups(trait_groups: Optional[list[str]] = None) -> TACConfig:
    """Get test configuration with optional trait groups."""
    memory_config = TwilioMemoryConfig(
        memory_store_id="MGtest123",
        api_key="test_api_key",
        api_token="test_api_token",
        trait_groups=trait_groups,
    )
    return TACConfig(
        environment="prod",
        conversation_service_sid="IStest123",
        twilio_account_sid="ACtest123",
        twilio_auth_token="test_token_123",
        twilio_phone_number="+15551234567",
        twilio_memory_config=memory_config,
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

        mock_profile = get_mock_profile_response()

        tac.memora_client.get_profile = AsyncMock(return_value=mock_profile)
        profile = await tac.fetch_profile("profile_test_123")

        # Verify profile was fetched
        assert profile is not None
        assert profile.id == "profile_test_123"
        assert "Contact" in profile.traits
        assert "Preferences" in profile.traits
        assert profile.traits["Contact"]["firstName"] == "John"

        # Verify get_profile was called with correct trait_groups
        tac.memora_client.get_profile.assert_called_once_with(
            profile_id="profile_test_123",
            trait_groups=["Contact", "Preferences"],
        )

    @pytest.mark.asyncio
    async def test_profile_fetched_without_trait_groups(self) -> None:
        """Test that profile is fetched without trait_groups when not configured."""
        config = get_test_config_with_trait_groups(trait_groups=None)
        tac = TAC(config)

        mock_profile = get_mock_profile_response()

        tac.memora_client.get_profile = AsyncMock(return_value=mock_profile)
        profile = await tac.fetch_profile("profile_test_123")

        # Verify profile was fetched
        assert profile is not None
        assert profile.id == "profile_test_123"

        # Verify get_profile was called with trait_groups=None
        tac.memora_client.get_profile.assert_called_once_with(
            profile_id="profile_test_123",
            trait_groups=None,
        )

    @pytest.mark.asyncio
    async def test_profile_fetch_error_handling(self) -> None:
        """Test that profile fetch errors are handled gracefully."""
        config = get_test_config_with_trait_groups()
        tac = TAC(config)

        # Simulate an error during profile fetch
        tac.memora_client.get_profile = AsyncMock(side_effect=Exception("API Error"))
        profile = await tac.fetch_profile("profile_test_123")

        # Verify None is returned on error (not raised)
        assert profile is None

    @pytest.mark.asyncio
    async def test_profile_fetch_without_memory_config(self) -> None:
        """Test that profile fetch returns None when memory config is not provided."""
        config = TACConfig(
            environment="prod",
            conversation_service_sid="IStest123",
            twilio_account_sid="ACtest123",
            twilio_auth_token="test_token_123",
            twilio_phone_number="+15551234567",
            twilio_memory_config=None,  # No memory config
        )
        tac = TAC(config)

        # Verify memora_client is None
        assert tac.memora_client is None

        # Attempt to fetch profile
        profile = await tac.fetch_profile("profile_test_123")

        # Should return None without error
        assert profile is None

    @pytest.mark.asyncio
    async def test_profile_fetch_with_empty_profile_id(self) -> None:
        """Test that profile fetch handles empty profile_id gracefully."""
        config = get_test_config_with_trait_groups()
        tac = TAC(config)

        # Test with empty string
        profile = await tac.fetch_profile("")
        assert profile is None


class TestProfileInSMSChannel:
    """Tests for profile retrieval in SMS channel."""

    @pytest.mark.asyncio
    async def test_sms_profile_available_in_callback(self) -> None:
        """Test that profile is available in callback context for SMS."""
        with patch("tac.channels.sms.Client"):
            config = get_test_config_with_trait_groups(trait_groups=["Contact"])
            tac = TAC(config)
            channel = SMSChannel(tac, auto_retrieve_memory=False)

            # Track callback data
            received_context = None

            def message_ready_callback(
                user_message: str,
                context: ConversationSession,
                memory_response: Optional[MemoryRetrievalResponse] = None,
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

            tac.memora_client.get_profile = AsyncMock(return_value=mock_profile)
            empty_memory = MemoryRetrievalResponse(
                observations=[],
                summaries=[],
                sessions=[],
                meta=MemoryRetrievalMeta(queryTime=0),
            )
            tac.memora_client.retrieve_memory = AsyncMock(return_value=empty_memory)

            # Process participant.added first (triggers profile fetch)
            await channel.process_webhook(participant_webhook)

            # Verify profile was fetched on participant.added
            tac.memora_client.get_profile.assert_called_with(
                profile_id="profile_test_123",
                trait_groups=["Contact"],
            )

            # Process message
            await channel.process_webhook(message_webhook)

            # Verify profile is in context
            assert received_context is not None
            assert received_context.profile is not None
            assert received_context.profile.id == "profile_test_123"
            assert received_context.profile.traits["Contact"]["firstName"] == "John"

    @pytest.mark.asyncio
    async def test_sms_profile_fetched_on_conversation_start(self) -> None:
        """Test that profile is fetched when conversation starts."""
        with patch("tac.channels.sms.Client") as mock_client_class:
            # Mock participant creation
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_participants_create = MagicMock()
            mock_client.conversations.v1.conversations.return_value.participants.create = (
                mock_participants_create
            )

            config = get_test_config_with_trait_groups(trait_groups=["Contact"])
            tac = TAC(config)
            channel = SMSChannel(tac, auto_retrieve_memory=False)

            mock_profile = get_mock_profile_response()

            # Simulate participant.added webhook (this is when profile is fetched)
            participant_added = create_participant_added_webhook(
                "CH123456", "MB123", "profile_test_123", "2025-11-18T00:00:00.000Z"
            )

            tac.memora_client.get_profile = AsyncMock(return_value=mock_profile)
            await channel.process_webhook(participant_added)

            # Verify profile was fetched when participant was added
            tac.memora_client.get_profile.assert_called_once_with(
                profile_id="profile_test_123",
                trait_groups=["Contact"],
            )

            # Verify conversation was created with profile
            assert "CH123456" in channel._conversations
            session = channel._conversations["CH123456"]
            assert session.profile is not None
            assert session.profile.id == "profile_test_123"

    @pytest.mark.asyncio
    async def test_sms_profile_fetched_for_each_message(self) -> None:
        """Test that profile is fetched fresh for each SMS message."""
        with patch("tac.channels.sms.Client"):
            config = get_test_config_with_trait_groups()
            tac = TAC(config)
            channel = SMSChannel(tac, auto_retrieve_memory=False)

            mock_profile = get_mock_profile_response()

            # Simulate participant.added first
            participant_webhook = create_participant_added_webhook(
                "CH123456", "MB123", "profile_test_123", "2025-11-18T00:00:00.000Z"
            )

            # Simulate first message
            message_webhook_1 = create_communication_created_webhook(
                "CH123456", "MB123", "First message", "2025-11-18T00:00:01.000Z"
            )

            tac.memora_client.get_profile = AsyncMock(return_value=mock_profile)
            empty_memory = MemoryRetrievalResponse(
                observations=[],
                summaries=[],
                sessions=[],
                meta=MemoryRetrievalMeta(queryTime=0),
            )
            tac.memora_client.retrieve_memory = AsyncMock(return_value=empty_memory)

            # Process participant.added (first profile fetch)
            await channel.process_webhook(participant_webhook)
            first_call_count = tac.memora_client.get_profile.call_count

            # Process first message (second profile fetch)
            await channel.process_webhook(message_webhook_1)
            second_call_count = tac.memora_client.get_profile.call_count

            # Simulate second message
            message_webhook_2 = create_communication_created_webhook(
                "CH123456", "MB123", "Second message", "2025-11-18T00:00:02.000Z"
            )

            # Process second message (third profile fetch)
            await channel.process_webhook(message_webhook_2)
            third_call_count = tac.memora_client.get_profile.call_count

            # Verify profile was fetched multiple times
            # (once on participant.added, once per message)
            assert second_call_count > first_call_count
            assert third_call_count > second_call_count

    @pytest.mark.asyncio
    async def test_sms_profile_updates_session(self) -> None:
        """Test that profile updates the session for each message."""
        with patch("tac.channels.sms.Client"):
            config = get_test_config_with_trait_groups()
            tac = TAC(config)
            channel = SMSChannel(tac, auto_retrieve_memory=False)

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
            message_webhook = create_communication_created_webhook(
                "CH123456", "MB123", "Hello", "2025-11-18T00:00:01.000Z"
            )

            empty_memory = MemoryRetrievalResponse(
                observations=[],
                summaries=[],
                sessions=[],
                meta=MemoryRetrievalMeta(queryTime=0),
            )
            tac.memora_client.retrieve_memory = AsyncMock(return_value=empty_memory)

            # Process participant.added with first profile version
            tac.memora_client.get_profile = AsyncMock(return_value=mock_profile_v1)
            await channel.process_webhook(participant_webhook)
            session = channel._conversations["CH123456"]
            assert session.profile is not None
            assert session.profile.traits["Contact"]["firstName"] == "John"

            # Process message with updated profile
            tac.memora_client.get_profile = AsyncMock(return_value=mock_profile_v2)
            await channel.process_webhook(message_webhook)
            session = channel._conversations["CH123456"]
            assert session.profile is not None
            assert session.profile.traits["Contact"]["firstName"] == "Jane"


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

        mock_lookup_response = ProfileLookupResponse(
            normalizedValue="+13175556789",
            profiles=["mem_profile_00000000000000000000000001"],
        )

        tac.memora_client.lookup_profile = AsyncMock(return_value=mock_lookup_response)
        response = await tac.memora_client.lookup_profile(
            id_type="phone", value="+1 (317) 555-6789"
        )

        # Verify response
        assert response.normalized_value == "+13175556789"
        assert len(response.profiles) == 1
        assert response.profiles[0] == "mem_profile_00000000000000000000000001"

        # Verify lookup_profile was called with correct parameters
        tac.memora_client.lookup_profile.assert_called_once_with(
            id_type="phone", value="+1 (317) 555-6789"
        )

    @pytest.mark.asyncio
    async def test_profile_lookup_by_email(self) -> None:
        """Test profile lookup by email address."""
        config = get_test_config_with_trait_groups()
        tac = TAC(config)

        mock_lookup_response = ProfileLookupResponse(
            normalizedValue="test@example.com",
            profiles=["mem_profile_00000000000000000000000002"],
        )

        tac.memora_client.lookup_profile = AsyncMock(return_value=mock_lookup_response)
        response = await tac.memora_client.lookup_profile(id_type="email", value="test@example.com")

        # Verify response
        assert response.normalized_value == "test@example.com"
        assert len(response.profiles) == 1
        assert response.profiles[0] == "mem_profile_00000000000000000000000002"

    @pytest.mark.asyncio
    async def test_profile_lookup_multiple_matches(self) -> None:
        """Test profile lookup with multiple matching profiles."""
        config = get_test_config_with_trait_groups()
        tac = TAC(config)

        mock_lookup_response = ProfileLookupResponse(
            normalizedValue="+13175556789",
            profiles=[
                "mem_profile_00000000000000000000000001",
                "mem_profile_00000000000000000000000002",
            ],
        )

        tac.memora_client.lookup_profile = AsyncMock(return_value=mock_lookup_response)
        response = await tac.memora_client.lookup_profile(id_type="phone", value="+13175556789")

        # Verify multiple profiles returned
        assert len(response.profiles) == 2
        assert "mem_profile_00000000000000000000000001" in response.profiles
        assert "mem_profile_00000000000000000000000002" in response.profiles

    @pytest.mark.asyncio
    async def test_profile_lookup_no_matches(self) -> None:
        """Test profile lookup with no matching profiles."""
        config = get_test_config_with_trait_groups()
        tac = TAC(config)

        mock_lookup_response = ProfileLookupResponse(
            normalizedValue="+13175556789",
            profiles=[],
        )

        tac.memora_client.lookup_profile = AsyncMock(return_value=mock_lookup_response)
        response = await tac.memora_client.lookup_profile(id_type="phone", value="+13175556789")

        # Verify empty profiles list
        assert len(response.profiles) == 0

    @pytest.mark.asyncio
    async def test_profile_lookup_error_handling(self) -> None:
        """Test profile lookup error handling."""
        config = get_test_config_with_trait_groups()
        tac = TAC(config)

        # Simulate API error
        tac.memora_client.lookup_profile = AsyncMock(
            side_effect=Exception("Profile lookup API error")
        )

        with pytest.raises(Exception, match="Profile lookup API error"):
            await tac.memora_client.lookup_profile(id_type="phone", value="+13175556789")
