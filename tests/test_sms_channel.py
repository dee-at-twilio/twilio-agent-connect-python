"""Tests for SMS Channel."""

from typing import Any, Optional
from unittest.mock import AsyncMock, patch

import pytest

from tac import TAC
from tac.channels.sms import SMSChannel
from tac.models.memory import MemoryRetrievalMeta, MemoryRetrievalResponse
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse


def create_conversation_created_webhook(conversation_id: str, timestamp: str) -> dict[str, Any]:
    """Create a CONVERSATION_CREATED webhook event."""
    return {
        "eventType": "CONVERSATION_CREATED",
        "timestamp": timestamp,
        "data": {
            "id": conversation_id,
            "accountId": "ACtest123",
            "serviceId": "IStest123",
            "status": "ACTIVE",
            "name": "Test Conversation",
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "configuration": {"intelligenceServiceIds": []},
        },
    }


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


def create_conversation_updated_webhook(
    conversation_id: str, status: str, timestamp: str
) -> dict[str, Any]:
    """Create a CONVERSATION_UPDATED webhook event."""
    return {
        "eventType": "CONVERSATION_UPDATED",
        "timestamp": timestamp,
        "data": {
            "id": conversation_id,
            "accountId": "ACtest123",
            "configurationId": "IStest123",
            "serviceId": "IStest123",
            "status": status,
            "name": "Test Conversation",
            "createdAt": "2025-11-18T00:00:00.000Z",
            "updatedAt": timestamp,
            "configuration": {"intelligenceServiceIds": []},
        },
    }


def get_test_config(with_memory: bool = True) -> dict[str, Any]:
    """Get a valid test configuration."""
    config: dict[str, Any] = {
        "twilio_auth_token": "test_token_123",
        "api_key": "SK123",
        "api_token": "test_api_token",
        "environment": "prod",
        "conversation_service_sid": "IStest123",
        "twilio_account_sid": "ACtest123",
        "twilio_phone_number": "+15551234567",
    }
    if with_memory:
        from tac.core.config import TwilioMemoryConfig

        config["twilio_memory_config"] = TwilioMemoryConfig(trait_groups=["Contact"])
    return config


class TestSMSChannel:
    """Test SMS Channel functionality."""

    def test_initialization(self) -> None:
        """Test SMS channel initialization."""
        tac = TAC(get_test_config())
        channel = SMSChannel(tac)

        assert channel.tac == tac

    def test_initialization_without_phone_number(self) -> None:
        """Test TAC config validation fails without twilio_phone_number."""
        config = get_test_config()
        del config["twilio_phone_number"]

        # twilio_phone_number is now required at TACConfig level
        with pytest.raises(ValueError):
            TAC(config)

    @pytest.mark.asyncio
    async def test_process_conversation_started(self) -> None:
        """Test processing participant.added event to start conversation."""
        tac = TAC(get_test_config())
        channel = SMSChannel(tac)

        # Process participant.added (creates conversation session)
        participant_webhook = create_participant_added_webhook(
            "CH123456", "MB123", "profile_test_123", "2025-11-18T00:00:01.000Z"
        )
        await channel.process_webhook(participant_webhook)

        # Verify conversation was started with profile
        assert "CH123456" in channel._conversations
        assert channel._conversations["CH123456"].profile_id == "profile_test_123"

    @pytest.mark.asyncio
    async def test_process_message_auto_initialize(self) -> None:
        """Test processing message auto-initializes conversation if not started."""
        tac = TAC(get_test_config())

        # Manually create memora_client for this test
        from tac.context.memory import MemoryClient

        tac.memora_client = MemoryClient(
            base_url=tac.config.memora_base_url,
            store_id="MGtest123",
            api_key=tac.config.api_key,
            api_token=tac.config.api_token,
        )

        channel = SMSChannel(tac)

        # Callback to capture context
        captured_context = None
        captured_memories = None

        def message_callback(
            user_message: str,
            context: ConversationSession,
            memory_response: Optional[TACMemoryResponse],
        ) -> None:
            nonlocal captured_context, captured_memories
            captured_context = context
            captured_memories = memory_response

        tac.on_message_ready(message_callback)

        webhook_data = create_communication_created_webhook(
            "CH123456", "MB123", "Hello, I need help", "2025-11-18T00:00:00.000Z"
        )

        empty_response = MemoryRetrievalResponse(
            observations=[],
            summaries=[],
            meta=MemoryRetrievalMeta(queryTime=0),
        )
        tac.memora_client.retrieve_memory = AsyncMock(return_value=empty_response)

        await channel.process_webhook(webhook_data)

        # Verify callback was invoked
        assert captured_context is not None
        assert captured_context.conversation_id == "CH123456"
        # No profile_id since message auto-initialized without participant.added event
        assert captured_context.profile_id is None
        assert captured_context.channel == "sms"

    @pytest.mark.asyncio
    async def test_process_message_with_existing_conversation(self) -> None:
        """Test processing message with pre-existing conversation."""
        tac = TAC(get_test_config())

        # Manually create memora_client for this test
        from tac.context.memory import MemoryClient

        tac.memora_client = MemoryClient(
            base_url=tac.config.memora_base_url,
            store_id="MGtest123",
            api_key=tac.config.api_key,
            api_token=tac.config.api_token,
        )

        channel = SMSChannel(
            tac, config={"auto_retrieve_memory": True}
        )  # Enable memory retrieval for test

        # Start conversation via participant added
        participant_webhook = create_participant_added_webhook(
            "CH123456", "MB123", "profile_test_123", "2025-11-18T00:00:01.000Z"
        )
        await channel.process_webhook(participant_webhook)

        # Now process message
        message_webhook = create_communication_created_webhook(
            "CH123456", "MB123", "Test message", "2025-11-18T00:00:02.000Z"
        )

        empty_response = MemoryRetrievalResponse(
            observations=[],
            summaries=[],
            meta=MemoryRetrievalMeta(queryTime=0),
        )
        tac.memora_client.retrieve_memory = AsyncMock(return_value=empty_response)

        await channel.process_webhook(message_webhook)

        # Verify memory retrieval was called
        tac.memora_client.retrieve_memory.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_empty_message_ignored(self) -> None:
        """Test that empty messages are ignored."""
        tac = TAC(get_test_config())

        # Manually create memora_client for this test
        from tac.context.memory import MemoryClient

        tac.memora_client = MemoryClient(
            base_url=tac.config.memora_base_url,
            store_id="MGtest123",
            api_key=tac.config.api_key,
            api_token=tac.config.api_token,
        )

        channel = SMSChannel(tac)

        webhook_data = create_communication_created_webhook(
            "CH123456", "MB123", "", "2025-11-18T00:00:00.000Z"
        )

        tac.memora_client.retrieve_memory = AsyncMock()

        await channel.process_webhook(webhook_data)

        # Verify memory retrieval was NOT called
        tac.memora_client.retrieve_memory.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_conversation_ended(self) -> None:
        """Test processing onConversationRemoved event."""
        tac = TAC(get_test_config())
        channel = SMSChannel(tac)

        # Start conversation via participant added
        start_webhook = create_participant_added_webhook(
            "CH123456", "MB123", "profile_test_123", "2025-11-18T00:00:00.000Z"
        )
        await channel.process_webhook(start_webhook)

        # End conversation (status changed to CLOSED)
        end_webhook = create_conversation_updated_webhook(
            "CH123456", "CLOSED", "2025-11-18T00:10:00.000Z"
        )

        # Should not raise
        await channel.process_webhook(end_webhook)

    @pytest.mark.asyncio
    async def test_send_response_with_active_conversation(self) -> None:
        """Test sending response to active conversation using Send API."""
        tac = TAC(get_test_config())
        channel = SMSChannel(tac)

        from tac.models.conversation import ParticipantAddress, ParticipantResponse

        # Mock agent participant
        mock_agent_participant = ParticipantResponse(
            **{  # type: ignore[arg-type]
                "id": "PA_AGENT",
                "accountId": "ACtest123",
                "conversationId": "CH123456",
                "name": "Test Agent",
                "type": "AI_AGENT",
                "addresses": [
                    ParticipantAddress(channel="SMS", address="+15551234567").model_dump(
                        by_alias=True
                    )
                ],
            }
        )

        # Mock customer participant
        mock_customer_participant = ParticipantResponse(
            **{  # type: ignore[arg-type]
                "id": "PA_CUSTOMER",
                "accountId": "ACtest123",
                "conversationId": "CH123456",
                "name": "+12345678901",
                "type": "CUSTOMER",
                "addresses": [
                    ParticipantAddress(channel="SMS", address="+12345678901").model_dump(
                        by_alias=True
                    )
                ],
            }
        )

        with (
            patch.object(
                tac.maestro_client,
                "list_participants",
                return_value=[mock_agent_participant, mock_customer_participant],
            ),
            patch.object(tac.maestro_client, "send_communication") as mock_send_comm,
        ):
            await channel.send_response("CH123456", "Test response")

            # Verify send_communication was called
            mock_send_comm.assert_called_once()
            call_args = mock_send_comm.call_args
            assert call_args[0][0] == "CH123456"  # conversation_id

            # Verify request structure
            request = call_args[0][1]
            assert request.author.address == "+15551234567"
            assert request.author.channel == "SMS"
            assert request.author.participant_id == "PA_AGENT"
            assert request.content.type == "TEXT"
            assert request.content.text == "Test response"
            assert len(request.recipients) == 1
            assert request.recipients[0].address == "+12345678901"
            assert request.recipients[0].channel == "SMS"
            assert request.recipients[0].participant_id == "PA_CUSTOMER"

    @pytest.mark.asyncio
    async def test_multiple_concurrent_conversations(self) -> None:
        """Test handling multiple concurrent conversations."""
        tac = TAC(get_test_config())
        channel = SMSChannel(tac)

        # Start first conversation via participant added
        await channel.process_webhook(
            create_participant_added_webhook("CH111", "PA111", "PR111", "2025-11-18T00:00:00.000Z")
        )

        # Start second conversation via participant added
        await channel.process_webhook(
            create_participant_added_webhook("CH222", "PA222", "PR222", "2025-11-18T00:00:01.000Z")
        )

        # Verify both conversations started successfully
        assert "CH111" in channel._conversations
        assert "CH222" in channel._conversations

        # End first conversation (should not raise)
        await channel.process_webhook(
            create_conversation_updated_webhook("CH111", "CLOSED", "2025-11-18T00:10:00.000Z")
        )

        # Verify first conversation was removed
        assert "CH111" not in channel._conversations
        assert "CH222" in channel._conversations

    @pytest.mark.asyncio
    async def test_ignores_unsupported_event_types(self) -> None:
        """Test that unsupported event types are ignored."""
        tac = TAC(get_test_config())
        channel = SMSChannel(tac)

        webhook_data = {
            "eventType": "SOME_UNSUPPORTED_EVENT",
            "timestamp": "2025-11-18T00:00:00.000Z",
            "data": {"id": "CH123456"},
        }

        # Should not raise, just log debug message
        await channel.process_webhook(webhook_data)

    @pytest.mark.asyncio
    async def test_conversation_ended_callback_fires_on_close(self) -> None:
        """Closing an SMS conversation triggers on_conversation_ended with correct data."""
        tac = TAC(get_test_config())
        channel = SMSChannel(tac)
        captured: list[ConversationSession] = []

        def handler(ctx: ConversationSession) -> None:
            captured.append(ctx)

        tac.on_conversation_ended(handler)

        # Start conversation via participant added
        await channel.process_webhook(
            create_participant_added_webhook(
                "CH_CB1", "MB_CB1", "prof_cb1", "2025-11-18T00:00:01.000Z"
            )
        )

        # Close conversation
        await channel.process_webhook(
            create_conversation_updated_webhook("CH_CB1", "CLOSED", "2025-11-18T00:10:00.000Z")
        )

        assert len(captured) == 1
        assert captured[0].conversation_id == "CH_CB1"
        assert captured[0].profile_id == "prof_cb1"
        assert captured[0].channel == "sms"

    @pytest.mark.asyncio
    async def test_conversation_ended_callback_error_does_not_prevent_cleanup(self) -> None:
        """If on_conversation_ended callback raises, the session is still cleaned up."""
        tac = TAC(get_test_config())
        channel = SMSChannel(tac)

        def bad_handler(ctx: ConversationSession) -> None:
            raise RuntimeError("boom")

        tac.on_conversation_ended(bad_handler)

        await channel.process_webhook(
            create_participant_added_webhook(
                "CH_CB2", "MB_CB2", "prof_cb2", "2025-11-18T00:00:00.000Z"
            )
        )
        await channel.process_webhook(
            create_conversation_updated_webhook("CH_CB2", "CLOSED", "2025-11-18T00:10:00.000Z")
        )

        # Session should still be cleaned up despite the error
        assert "CH_CB2" not in channel._conversations

    @pytest.mark.asyncio
    async def test_conversation_ended_async_callback(self) -> None:
        """Async on_conversation_ended callback is awaited correctly."""
        tac = TAC(get_test_config())
        channel = SMSChannel(tac)
        captured: list[ConversationSession] = []

        async def async_handler(ctx: ConversationSession) -> None:
            captured.append(ctx)

        tac.on_conversation_ended(async_handler)

        await channel.process_webhook(
            create_participant_added_webhook(
                "CH_ASYNC1", "MB_ASYNC1", "prof_async1", "2025-11-18T00:00:00.000Z"
            )
        )
        await channel.process_webhook(
            create_conversation_updated_webhook("CH_ASYNC1", "CLOSED", "2025-11-18T00:10:00.000Z")
        )

        assert len(captured) == 1
        assert captured[0].conversation_id == "CH_ASYNC1"
        assert captured[0].channel == "sms"

    @pytest.mark.asyncio
    async def test_conversation_ended_no_callback_registered(self) -> None:
        """Closing a conversation without a registered callback cleans up silently."""
        tac = TAC(get_test_config())
        channel = SMSChannel(tac)

        # No callback registered — should not raise
        await channel.process_webhook(
            create_participant_added_webhook(
                "CH_NOCB", "MB_NOCB", "prof_nocb", "2025-11-18T00:00:00.000Z"
            )
        )
        await channel.process_webhook(
            create_conversation_updated_webhook("CH_NOCB", "CLOSED", "2025-11-18T00:10:00.000Z")
        )

        assert "CH_NOCB" not in channel._conversations

    @pytest.mark.asyncio
    async def test_send_response_agent_participant_not_found(self) -> None:
        """Test sending response when agent participant is not found."""
        tac = TAC(get_test_config())
        channel = SMSChannel(tac)

        with patch.object(tac.maestro_client, "list_participants", return_value=[]):
            # Should log error but not raise
            await channel.send_response("CH123456", "Test response")
