"""Tests for SMS Channel."""

import asyncio
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
        "environment": "prod",
        "conversation_service_sid": "IStest123",
        "twilio_account_sid": "ACtest123",
        "twilio_phone_number": "+15551234567",
    }
    if with_memory:
        config["twilio_memory_config"] = {
            "memory_store_id": "MGtest123",
            "api_key": "test_api_key",
            "api_token": "test_api_token",
        }
    return config


class TestSMSChannel:
    """Test SMS Channel functionality."""

    def test_initialization(self) -> None:
        """Test SMS channel initialization."""
        tac = TAC(get_test_config())
        channel = SMSChannel(tac, auto_retrieve_memory=False)

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
        """Test processing conversation.created and participant.added events."""
        tac = TAC(get_test_config())
        channel = SMSChannel(tac, auto_retrieve_memory=False)

        # Process conversation.created
        conversation_webhook = create_conversation_created_webhook(
            "CH123456", "2025-11-18T00:00:00.000Z"
        )
        await channel.process_webhook(conversation_webhook)

        # Process participant.added
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
        channel = SMSChannel(tac, auto_retrieve_memory=False)

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
        channel = SMSChannel(tac)  # auto_retrieve_memory=True to test memory retrieval

        # Start conversation first
        conversation_webhook = create_conversation_created_webhook(
            "CH123456", "2025-11-18T00:00:00.000Z"
        )
        await channel.process_webhook(conversation_webhook)

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
        channel = SMSChannel(tac, auto_retrieve_memory=False)

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
        channel = SMSChannel(tac, auto_retrieve_memory=False)

        # Start conversation
        start_webhook = create_conversation_created_webhook("CH123456", "2025-11-18T00:00:00.000Z")
        await channel.process_webhook(start_webhook)

        # End conversation (status changed to CLOSED)
        end_webhook = create_conversation_updated_webhook(
            "CH123456", "CLOSED", "2025-11-18T00:10:00.000Z"
        )

        # Should not raise
        await channel.process_webhook(end_webhook)

    @pytest.mark.asyncio
    async def test_send_response_with_active_conversation(self) -> None:
        """Test sending response to active conversation."""
        tac = TAC(get_test_config())
        channel = SMSChannel(tac, auto_retrieve_memory=False)

        # Mock list_participants to return customer participant with matching profile_id
        from tac.models.conversation import ParticipantResponse

        mock_customer_participant = ParticipantResponse(
            **{  # type: ignore[arg-type]
                "id": "PA_CUSTOMER",
                "accountId": "ACtest123",
                "serviceId": "IStest123",
                "conversationId": "CH123456",
                "name": "Test Customer",
                "type": "CUSTOMER",
                "profileId": "profile_test_123",  # Matching profile_id
                "addresses": [{"channel": "SMS", "address": "+12345678901"}],
            }
        )

        # Start conversation with profile_id
        start_webhook = create_conversation_created_webhook("CH123456", "2025-11-18T00:00:00.000Z")
        await channel.process_webhook(start_webhook)

        # Add participant to set profile_id
        participant_webhook = create_participant_added_webhook(
            "CH123456", "PA_CUSTOMER", "profile_test_123", "2025-11-18T00:00:01.000Z"
        )
        await channel.process_webhook(participant_webhook)

        with (
            patch.object(
                tac.maestro_client,
                "list_participants",
                return_value=[mock_customer_participant],
            ),
            patch.object(channel.twilio.messages, "create") as mock_twilio_send,
        ):
            # Send response
            await channel.send_response("CH123456", "Test response")

            # Verify Twilio message was sent to the correct recipient
            mock_twilio_send.assert_called_once_with(
                to="+12345678901",
                from_=tac.config.twilio_phone_number,
                body="Test response",
            )

    def test_send_response_to_unknown_conversation(self) -> None:
        """Test sending response to non-existent conversation logs error."""
        tac = TAC(get_test_config())
        channel = SMSChannel(tac, auto_retrieve_memory=False)

        # Should log error but not raise
        asyncio.run(channel.send_response("CH_UNKNOWN", "Test response"))

    @pytest.mark.asyncio
    async def test_multiple_concurrent_conversations(self) -> None:
        """Test handling multiple concurrent conversations."""
        tac = TAC(get_test_config())
        channel = SMSChannel(tac, auto_retrieve_memory=False)

        # Start first conversation
        await channel.process_webhook(
            create_conversation_created_webhook("CH111", "2025-11-18T00:00:00.000Z")
        )

        # Start second conversation
        await channel.process_webhook(
            create_conversation_created_webhook("CH222", "2025-11-18T00:00:01.000Z")
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
        channel = SMSChannel(tac, auto_retrieve_memory=False)

        webhook_data = {
            "eventType": "SOME_UNSUPPORTED_EVENT",
            "timestamp": "2025-11-18T00:00:00.000Z",
            "data": {"id": "CH123456"},
        }

        # Should not raise, just log debug message
        await channel.process_webhook(webhook_data)
