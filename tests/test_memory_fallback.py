"""Tests for memory retrieval fallback functionality."""

from unittest.mock import AsyncMock

import pytest

from tac import TAC, TACConfig
from tac.models.conversation import (
    Communication,
    CommunicationContent,
    CommunicationParticipant,
    Transcription,
    TranscriptionWord,
)
from tac.models.memory import (
    MemoryCommunication,
    MemoryCommunicationContent,
    MemoryParticipant,
    MemoryRetrievalMeta,
    MemoryRetrievalResponse,
)
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse


def get_test_config_without_memory():
    """Get test configuration without Twilio Memory."""
    return {
        "twilio_auth_token": "test_token_123",
        "environment": "prod",
        "twilio_account_sid": "ACtest123",
        "conversation_service_sid": "IS123test",
        "twilio_phone_number": "+15551234567",
    }


def get_test_config_with_memory():
    """Get test configuration with Twilio Memory."""
    config = get_test_config_without_memory()
    config["twilio_memory_config"] = {
        "memory_store_id": "MGtest123",
        "api_key": "test_api_key",
        "api_token": "test_api_token",
    }
    return config


class TestMemoryFallback:
    """Test memory retrieval fallback to Maestro Communications API."""

    @pytest.mark.asyncio
    async def test_retrieve_memory_with_memora_configured(self):
        """Test retrieve_memory uses Memora when configured."""
        # Setup
        config = TACConfig(**get_test_config_with_memory())
        tac = TAC(config)

        tac.memora_client.retrieve_memory = AsyncMock(
            return_value=MemoryRetrievalResponse(
                observations=[],
                summaries=[],
                communications=[],
                meta=MemoryRetrievalMeta(queryTime=100),
            )
        )

        context = ConversationSession(
            conversation_id="CH123",
            profile_id="profile_123",
            channel="SMS",
        )

        # Execute
        result = await tac.retrieve_memory(context, query="test query")

        # Verify
        tac.memora_client.retrieve_memory.assert_called_once_with(
            profile_id="profile_123",
            conversation_id="CH123",
            query="test query",
        )

        # Result should be wrapped in TACMemoryResponse
        from tac.models.tac import TACMemoryResponse

        assert isinstance(result, TACMemoryResponse)
        assert result.has_memory_features
        # Access raw data to check meta
        assert result.raw_data.meta.query_time == 100

    @pytest.mark.asyncio
    async def test_retrieve_memory_memora_configured_without_profile_id_raises(self):
        """Test retrieve_memory falls back to Maestro when profile_id is missing."""
        # Setup
        config = TACConfig(**get_test_config_with_memory())
        tac = TAC(config)

        # Mock Maestro fallback (since profile_id is unavailable)
        from unittest.mock import AsyncMock

        from tac.models.conversation import (
            Communication,
            CommunicationContent,
            CommunicationParticipant,
        )

        mock_communications = [
            Communication(
                id="CM123",
                conversationId="CH123",
                accountId="AC123",
                author=CommunicationParticipant(
                    address="+1234567890",
                    channel="SMS",
                    participantId="MB123",
                ),
                content=CommunicationContent(type="TEXT", text="Hello"),
                recipients=[
                    CommunicationParticipant(
                        address="+1234567890",
                        channel="SMS",
                        participantId="MB456",
                    )
                ],
                createdAt="2025-01-01T00:00:00.000Z",
                updatedAt="2025-01-01T00:00:00.000Z",
            )
        ]
        tac.maestro_client.list_communications = AsyncMock(return_value=mock_communications)

        context = ConversationSession(
            conversation_id="CH123",
            profile_id=None,  # Missing profile_id
            channel="SMS",
        )

        # Execute - should complete without raising exception (falls back to Maestro)
        result = await tac.retrieve_memory(context)

        # Verify - returns Maestro fallback data
        assert result is not None
        assert len(result.communications) > 0
        assert context.profile_id is None  # No profile lookup performed

    @pytest.mark.asyncio
    async def test_retrieve_memory_fallback_to_maestro(self):
        """Test retrieve_memory falls back to Maestro when Memora not configured."""
        # Setup
        config = TACConfig(**get_test_config_without_memory())
        tac = TAC(config)

        # Mock Maestro communications response
        from unittest.mock import AsyncMock

        tac.maestro_client.list_communications = AsyncMock(
            return_value=[
                Communication(
                    id="comm_123",
                    conversationId="CH123",
                    accountId="AC123456",
                    author=CommunicationParticipant(
                        address="+12025551234",
                        channel="SMS",
                        participantId="part_123",
                    ),
                    content=CommunicationContent(type="TEXT", text="Hello"),
                    recipients=[
                        CommunicationParticipant(
                            address="+12025555678",
                            channel="SMS",
                            participantId="part_456",
                        )
                    ],
                    createdAt="2019-08-24T14:15:22Z",
                    updatedAt="2019-08-24T14:15:22Z",
                )
            ]
        )

        context = ConversationSession(
            conversation_id="CH123",
            profile_id=None,  # profile_id not required for fallback
            channel="SMS",
        )

        # Execute
        result = await tac.retrieve_memory(context, query="test query")

        # Verify
        tac.maestro_client.list_communications.assert_called_once_with(conversation_id="CH123")

        # Check response structure - should be TACMemoryResponse wrapper
        from tac.models.tac import TACMemoryResponse

        assert isinstance(result, TACMemoryResponse)

        # Maestro fallback - observations and summaries should be empty
        assert len(result.observations) == 0
        assert len(result.summaries) == 0
        assert not result.has_memory_features

        # Check simplified communications
        assert len(result.communications) == 1
        comm = result.communications[0]
        assert comm.id == "comm_123"
        assert comm.author.address == "+12025551234"
        assert comm.content.text == "Hello"

    @pytest.mark.asyncio
    async def test_retrieve_memory_fallback_with_empty_communications(self):
        """Test retrieve_memory fallback handles empty communications list."""
        # Setup
        config = TACConfig(**get_test_config_without_memory())
        tac = TAC(config)

        from unittest.mock import AsyncMock

        tac.maestro_client.list_communications = AsyncMock(return_value=[])

        context = ConversationSession(
            conversation_id="CH123",
            profile_id=None,
            channel="SMS",
        )

        # Execute
        result = await tac.retrieve_memory(context)

        # Verify - should be TACMemoryResponse wrapper
        from tac.models.tac import TACMemoryResponse

        assert isinstance(result, TACMemoryResponse)
        assert len(result.observations) == 0
        assert len(result.summaries) == 0
        assert len(result.communications) == 0
        assert not result.has_memory_features

    @pytest.mark.asyncio
    async def test_retrieve_memory_fallback_api_error(self):
        """Test retrieve_memory fallback propagates API errors."""
        # Setup
        config = TACConfig(**get_test_config_without_memory())
        tac = TAC(config)

        from unittest.mock import AsyncMock

        import httpx

        tac.maestro_client.list_communications = AsyncMock(
            side_effect=httpx.HTTPError("Maestro API Error")
        )

        context = ConversationSession(
            conversation_id="CH123",
            profile_id=None,
            channel="SMS",
        )

        # Execute & Verify
        with pytest.raises(httpx.HTTPError, match="Maestro API Error"):
            await tac.retrieve_memory(context)

    @pytest.mark.asyncio
    async def test_retrieve_memory_fallback_with_multiple_communications(self):
        """Test retrieve_memory fallback with multiple communications."""
        # Setup
        config = TACConfig(**get_test_config_without_memory())
        tac = TAC(config)

        from unittest.mock import AsyncMock

        tac.maestro_client.list_communications = AsyncMock(
            return_value=[
                Communication(
                    id=f"comm_{i}",
                    conversationId="CH123",
                    accountId="AC123456",
                    author=CommunicationParticipant(
                        address="+12025551234",
                        channel="SMS",
                        participantId="part_123",
                    ),
                    content=CommunicationContent(type="TEXT", text=f"Message {i}"),
                    recipients=[
                        CommunicationParticipant(
                            address="+12025555678",
                            channel="SMS",
                            participantId="part_456",
                        )
                    ],
                    createdAt="2019-08-24T14:15:22Z",
                    updatedAt="2019-08-24T14:15:22Z",
                )
                for i in range(5)
            ]
        )

        context = ConversationSession(
            conversation_id="CH123",
            profile_id=None,
            channel="SMS",
        )

        # Execute
        result = await tac.retrieve_memory(context)

        # Verify - should be TACMemoryResponse wrapper with simplified communications
        from tac.models.tac import TACMemoryResponse

        assert isinstance(result, TACMemoryResponse)
        assert len(result.communications) == 5
        for i, comm in enumerate(result.communications):
            assert comm.id == f"comm_{i}"
            assert comm.content.text == f"Message {i}"

    def test_is_twilio_memory_enabled_with_memory(self):
        """Test is_twilio_memory_enabled returns True when configured."""
        config = TACConfig(**get_test_config_with_memory())
        tac = TAC(config)

        assert tac.is_twilio_memory_enabled() is True

    def test_is_twilio_memory_enabled_without_memory(self):
        """Test is_twilio_memory_enabled returns False when not configured."""
        config = TACConfig(**get_test_config_without_memory())
        tac = TAC(config)

        assert tac.is_twilio_memory_enabled() is False


class TestTACCommunicationConversion:
    """Test unified TACCommunication conversion logic."""

    def test_convert_memory_communication_populates_memory_fields(self):
        """Test that Memory communications populate Memory-only fields correctly."""
        # Create a Memory communication with Memory-only fields
        memory_comm = MemoryCommunication(
            id="mem_comm_123",
            author=MemoryParticipant(
                id="author_123",
                name="John Doe",
                type="CUSTOMER",
                address="+15551234567",
                channel="SMS",
                profileId="profile_456",
            ),
            content=MemoryCommunicationContent(text="Hello from Memory"),
            recipients=[
                MemoryParticipant(
                    id="recipient_789",
                    name="AI Agent",
                    type="AI_AGENT",
                    address="+15559876543",
                    channel="SMS",
                    profileId="profile_agent",
                )
            ],
            channelId="SM123",
            createdAt="2025-01-15T10:15:30Z",
            updatedAt="2025-01-15T10:20:30Z",
        )

        memory_response = MemoryRetrievalResponse(
            observations=[],
            summaries=[],
            communications=[memory_comm],
            meta=MemoryRetrievalMeta(queryTime=100),
        )

        # Wrap in TACMemoryResponse to trigger conversion
        tac_response = TACMemoryResponse(memory_response)

        # Verify conversion
        assert len(tac_response.communications) == 1
        comm = tac_response.communications[0]

        # Check Memory-only fields are populated
        assert comm.author.id == "author_123"
        assert comm.author.name == "John Doe"
        assert comm.author.type == "CUSTOMER"
        assert comm.author.profile_id == "profile_456"

        # Check Maestro-only fields are None
        assert comm.author.participant_id is None
        assert comm.author.delivery_status is None
        assert comm.conversation_id is None
        assert comm.account_id is None
        assert comm.content.type is None

        # Check common fields
        assert comm.id == "mem_comm_123"
        assert comm.author.address == "+15551234567"
        assert comm.content.text == "Hello from Memory"
        assert comm.channel_id == "SM123"
        assert comm.created_at == "2025-01-15T10:15:30Z"
        assert comm.updated_at == "2025-01-15T10:20:30Z"

    def test_convert_maestro_communication_populates_maestro_fields(self):
        """Test that Maestro communications populate Maestro-only fields correctly."""
        # Create a Maestro communication with Maestro-only fields
        maestro_comm = Communication(
            id="comm_789",
            conversationId="CONV123",
            accountId="AC456",
            author=CommunicationParticipant(
                address="+15551234567",
                channel="SMS",
                participantId="part_customer",
            ),
            content=CommunicationContent(type="TEXT", text="Hello from Maestro"),
            recipients=[
                CommunicationParticipant(
                    address="+15559876543",
                    channel="SMS",
                    participantId="part_agent",
                    deliveryStatus="DELIVERED",
                )
            ],
            channelId="SM456",
            createdAt="2025-01-15T11:00:00Z",
            updatedAt="2025-01-15T11:05:00Z",
        )

        # Wrap in TACMemoryResponse to trigger conversion
        tac_response = TACMemoryResponse([maestro_comm])

        # Verify conversion
        assert len(tac_response.communications) == 1
        comm = tac_response.communications[0]

        # Check Maestro-only fields are populated
        assert comm.conversation_id == "CONV123"
        assert comm.account_id == "AC456"
        assert comm.author.participant_id == "part_customer"
        assert comm.content.type == "TEXT"
        assert comm.recipients[0].delivery_status == "DELIVERED"

        # Check Memory-only fields are None
        assert comm.author.id is None
        assert comm.author.name is None
        assert comm.author.type is None
        assert comm.author.profile_id is None

        # Check common fields
        assert comm.id == "comm_789"
        assert comm.author.address == "+15551234567"
        assert comm.content.text == "Hello from Maestro"
        assert comm.channel_id == "SM456"

    def test_convert_maestro_transcription_communication(self):
        """Test Maestro TRANSCRIPTION communications with nested transcription parsing."""
        # Create a Maestro TRANSCRIPTION communication
        transcription_comm = Communication(
            id="comm_voice_123",
            conversationId="CONV_VOICE",
            accountId="AC_VOICE",
            author=CommunicationParticipant(
                address="+15551234567",
                channel="VOICE",
                participantId="part_voice_customer",
            ),
            content=CommunicationContent(
                type="TRANSCRIPTION",
                text="Hello, I need help with my account",
                transcription=Transcription(
                    channel=0,
                    confidence=0.95,
                    engine="google",
                    words=[
                        TranscriptionWord(
                            text="Hello",
                            startTime="2025-01-15T12:00:00.100Z",
                            endTime="2025-01-15T12:00:00.300Z",
                        ),
                        TranscriptionWord(
                            text="I",
                            startTime="2025-01-15T12:00:00.400Z",
                            endTime="2025-01-15T12:00:00.500Z",
                        ),
                        TranscriptionWord(
                            text="need",
                            startTime="2025-01-15T12:00:00.600Z",
                            endTime="2025-01-15T12:00:00.800Z",
                        ),
                    ],
                ),
            ),
            recipients=[
                CommunicationParticipant(
                    address="+15559876543",
                    channel="VOICE",
                    participantId="part_voice_agent",
                )
            ],
            createdAt="2025-01-15T12:00:00Z",
        )

        # Wrap in TACMemoryResponse to trigger conversion
        tac_response = TACMemoryResponse([transcription_comm])

        # Verify conversion
        assert len(tac_response.communications) == 1
        comm = tac_response.communications[0]

        # Check content type and transcription
        assert comm.content.type == "TRANSCRIPTION"
        assert comm.content.text == "Hello, I need help with my account"
        assert comm.content.transcription is not None

        # Check transcription metadata
        transcription = comm.content.transcription
        assert transcription.channel == 0
        assert transcription.confidence == 0.95
        assert transcription.engine == "google"

        # Check transcription words
        assert transcription.words is not None
        assert len(transcription.words) == 3
        assert transcription.words[0].text == "Hello"
        assert transcription.words[0].start_time == "2025-01-15T12:00:00.100Z"
        assert transcription.words[0].end_time == "2025-01-15T12:00:00.300Z"
        assert transcription.words[1].text == "I"
        assert transcription.words[2].text == "need"

    def test_convert_communication_with_optional_fields_missing(self):
        """Test conversion handles optional fields gracefully when missing."""
        # Create minimal Maestro communication with optional fields missing
        minimal_comm = Communication(
            id="comm_minimal",
            conversationId="CONV_MIN",
            accountId="AC_MIN",
            author=CommunicationParticipant(
                address="+15551234567",
                channel="SMS",
                participantId="part_min",
            ),
            content=CommunicationContent(type="TEXT", text="Minimal message"),
            recipients=[],
            # No channelId, createdAt, updatedAt
        )

        # Wrap in TACMemoryResponse to trigger conversion
        tac_response = TACMemoryResponse([minimal_comm])

        # Verify conversion handles missing optional fields
        assert len(tac_response.communications) == 1
        comm = tac_response.communications[0]

        assert comm.id == "comm_minimal"
        assert comm.channel_id is None
        assert comm.created_at is None
        assert comm.updated_at is None
        assert len(comm.recipients) == 0

    def test_convert_multiple_communications_preserves_order(self):
        """Test that converting multiple communications preserves order."""
        comms = [
            Communication(
                id=f"comm_{i}",
                conversationId="CONV",
                accountId="AC",
                author=CommunicationParticipant(
                    address="+15551234567",
                    channel="SMS",
                    participantId="part",
                ),
                content=CommunicationContent(type="TEXT", text=f"Message {i}"),
                recipients=[],
            )
            for i in range(5)
        ]

        tac_response = TACMemoryResponse(comms)

        # Verify order is preserved
        assert len(tac_response.communications) == 5
        for i, comm in enumerate(tac_response.communications):
            assert comm.id == f"comm_{i}"
            assert comm.content.text == f"Message {i}"
