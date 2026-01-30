"""Tests for automatic profile lookup in memory retrieval."""

from unittest.mock import AsyncMock

import pytest

from tac import TAC, TACConfig
from tac.core.config import TwilioMemoryConfig
from tac.models.memory import MemoryRetrievalResponse, ProfileLookupResponse
from tac.models.session import AuthorInfo, ConversationSession


def get_test_config_with_memory() -> TACConfig:
    """Get test configuration with Twilio Memory."""
    return TACConfig(
        environment="prod",
        conversation_service_sid="conv_configuration_test123",
        twilio_account_sid="ACtest123",
        twilio_auth_token="test_token_123",
        twilio_phone_number="+15551234567",
        twilio_memory_config=TwilioMemoryConfig(
            memory_store_id="mem_service_test123",
            api_key="test_api_key",
            api_token="test_api_token",
        ),
    )


class TestProfileLookupInMemoryRetrieval:
    """Tests for automatic profile lookup when profile_id is missing."""

    @pytest.mark.asyncio
    async def test_retrieve_memory_with_profile_id(self) -> None:
        """Test retrieve_memory works normally when profile_id is provided."""
        config = get_test_config_with_memory()
        tac = TAC(config)

        # Mock memory retrieval
        mock_memory_response = MemoryRetrievalResponse(
            observations=[],
            summaries=[],
            communications=[],
        )
        tac.memora_client.retrieve_memory = AsyncMock(return_value=mock_memory_response)

        # Create conversation session WITH profile_id
        session = ConversationSession(
            conversation_id="conv_test_123",
            profile_id="mem_profile_existing",
            channel="sms",
        )

        # Retrieve memory
        result = await tac.retrieve_memory(session, query="test query")

        # Verify memory was retrieved without lookup
        assert result == mock_memory_response
        tac.memora_client.retrieve_memory.assert_called_once_with(
            profile_id="mem_profile_existing",
            conversation_id="conv_test_123",
            query="test query",
        )

    @pytest.mark.asyncio
    async def test_retrieve_memory_with_profile_lookup(self) -> None:
        """Test retrieve_memory automatically looks up profile when missing."""
        config = get_test_config_with_memory()
        tac = TAC(config)

        # Mock profile lookup
        mock_lookup_response = ProfileLookupResponse(
            normalizedValue="+13175556789",
            profiles=["mem_profile_00000000000000000000000001"],
        )
        tac.memora_client.lookup_profile = AsyncMock(return_value=mock_lookup_response)

        # Mock memory retrieval
        mock_memory_response = MemoryRetrievalResponse(
            observations=[],
            summaries=[],
            communications=[],
        )
        tac.memora_client.retrieve_memory = AsyncMock(return_value=mock_memory_response)

        # Create conversation session WITHOUT profile_id but WITH author_info
        session = ConversationSession(
            conversation_id="conv_test_123",
            profile_id=None,  # No profile_id
            channel="sms",
            author_info=AuthorInfo(
                address="+1 (317) 555-6789",
                participant_id="participant_123",
            ),
        )

        # Retrieve memory
        result = await tac.retrieve_memory(session, query="test query")

        # Verify profile was looked up
        tac.memora_client.lookup_profile.assert_called_once_with(
            id_type="phone",
            value="+1 (317) 555-6789",
        )

        # Verify profile_id was assigned
        assert session.profile_id == "mem_profile_00000000000000000000000001"

        # Verify memory was retrieved with the looked up profile_id
        tac.memora_client.retrieve_memory.assert_called_once_with(
            profile_id="mem_profile_00000000000000000000000001",
            conversation_id="conv_test_123",
            query="test query",
        )

        assert result == mock_memory_response

    @pytest.mark.asyncio
    async def test_retrieve_memory_lookup_uses_first_profile(self) -> None:
        """Test that first profile is used when multiple profiles are found."""
        config = get_test_config_with_memory()
        tac = TAC(config)

        # Mock profile lookup with multiple profiles
        mock_lookup_response = ProfileLookupResponse(
            normalizedValue="+13175556789",
            profiles=[
                "mem_profile_00000000000000000000000001",
                "mem_profile_00000000000000000000000002",
                "mem_profile_00000000000000000000000003",
            ],
        )
        tac.memora_client.lookup_profile = AsyncMock(return_value=mock_lookup_response)

        # Mock memory retrieval
        mock_memory_response = MemoryRetrievalResponse()
        tac.memora_client.retrieve_memory = AsyncMock(return_value=mock_memory_response)

        # Create conversation session WITHOUT profile_id
        session = ConversationSession(
            conversation_id="conv_test_123",
            profile_id=None,
            channel="sms",
            author_info=AuthorInfo(address="+13175556789"),
        )

        # Retrieve memory
        await tac.retrieve_memory(session)

        # Verify first profile was used
        assert session.profile_id == "mem_profile_00000000000000000000000001"
        tac.memora_client.retrieve_memory.assert_called_once_with(
            profile_id="mem_profile_00000000000000000000000001",
            conversation_id="conv_test_123",
            query=None,
        )

    @pytest.mark.asyncio
    async def test_retrieve_memory_no_author_info_error(self) -> None:
        """Test error when profile_id and author_info are both missing."""
        config = get_test_config_with_memory()
        tac = TAC(config)

        # Create conversation session WITHOUT profile_id and WITHOUT author_info
        session = ConversationSession(
            conversation_id="conv_test_123",
            profile_id=None,
            channel="sms",
            author_info=None,  # No author info
        )

        # Attempt to retrieve memory should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            await tac.retrieve_memory(session)

        assert "profile_id is required for memory retrieval" in str(exc_info.value)
        assert "author_info.address is not available" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_retrieve_memory_no_address_error(self) -> None:
        """Test error when author_info exists but address is missing."""
        config = get_test_config_with_memory()
        tac = TAC(config)

        # Create conversation session WITHOUT profile_id and WITHOUT address
        session = ConversationSession(
            conversation_id="conv_test_123",
            profile_id=None,
            channel="sms",
            author_info=AuthorInfo(
                address="",  # Empty address
                participant_id="participant_123",
            ),
        )

        # Attempt to retrieve memory should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            await tac.retrieve_memory(session)

        assert "profile_id is required for memory retrieval" in str(exc_info.value)
        assert "author_info.address is not available" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_retrieve_memory_no_profiles_found_error(self) -> None:
        """Test error when profile lookup returns no profiles."""
        config = get_test_config_with_memory()
        tac = TAC(config)

        # Mock profile lookup with empty profiles list
        mock_lookup_response = ProfileLookupResponse(
            normalizedValue="+13175556789",
            profiles=[],  # No profiles found
        )
        tac.memora_client.lookup_profile = AsyncMock(return_value=mock_lookup_response)

        # Create conversation session WITHOUT profile_id
        session = ConversationSession(
            conversation_id="conv_test_123",
            profile_id=None,
            channel="sms",
            author_info=AuthorInfo(address="+13175556789"),
        )

        # Attempt to retrieve memory should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            await tac.retrieve_memory(session)

        assert "No profile found for phone number +13175556789" in str(exc_info.value)
        assert "Profile lookup returned no results" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_retrieve_memory_lookup_api_error(self) -> None:
        """Test error handling when profile lookup API fails."""
        config = get_test_config_with_memory()
        tac = TAC(config)

        # Mock profile lookup to raise an exception
        tac.memora_client.lookup_profile = AsyncMock(
            side_effect=Exception("Profile lookup API error")
        )

        # Create conversation session WITHOUT profile_id
        session = ConversationSession(
            conversation_id="conv_test_123",
            profile_id=None,
            channel="sms",
            author_info=AuthorInfo(address="+13175556789"),
        )

        # Attempt to retrieve memory should raise the exception
        with pytest.raises(Exception, match="Profile lookup API error"):
            await tac.retrieve_memory(session)

    @pytest.mark.asyncio
    async def test_retrieve_memory_lookup_modifies_session(self) -> None:
        """Test that profile lookup modifies the original session object."""
        config = get_test_config_with_memory()
        tac = TAC(config)

        # Mock profile lookup
        mock_lookup_response = ProfileLookupResponse(
            normalizedValue="+13175556789",
            profiles=["mem_profile_looked_up"],
        )
        tac.memora_client.lookup_profile = AsyncMock(return_value=mock_lookup_response)

        # Mock memory retrieval
        tac.memora_client.retrieve_memory = AsyncMock(return_value=MemoryRetrievalResponse())

        # Create conversation session
        session = ConversationSession(
            conversation_id="conv_test_123",
            profile_id=None,
            channel="sms",
            author_info=AuthorInfo(address="+13175556789"),
        )

        # Profile_id should be None initially
        assert session.profile_id is None

        # Retrieve memory
        await tac.retrieve_memory(session)

        # Profile_id should now be set
        assert session.profile_id == "mem_profile_looked_up"

    @pytest.mark.asyncio
    async def test_retrieve_memory_with_normalized_phone_number(self) -> None:
        """Test that phone numbers are normalized during lookup."""
        config = get_test_config_with_memory()
        tac = TAC(config)

        # Mock profile lookup (simulating normalization)
        mock_lookup_response = ProfileLookupResponse(
            normalizedValue="+13175556789",  # Normalized format
            profiles=["mem_profile_normalized"],
        )
        tac.memora_client.lookup_profile = AsyncMock(return_value=mock_lookup_response)

        # Mock memory retrieval
        tac.memora_client.retrieve_memory = AsyncMock(return_value=MemoryRetrievalResponse())

        # Create conversation session with formatted phone number
        session = ConversationSession(
            conversation_id="conv_test_123",
            profile_id=None,
            channel="sms",
            author_info=AuthorInfo(
                address="+1 (317) 555-6789"  # Formatted input
            ),
        )

        # Retrieve memory
        await tac.retrieve_memory(session)

        # Verify lookup was called with the formatted input
        tac.memora_client.lookup_profile.assert_called_once_with(
            id_type="phone",
            value="+1 (317) 555-6789",
        )

        # Verify profile_id was assigned correctly
        assert session.profile_id == "mem_profile_normalized"
