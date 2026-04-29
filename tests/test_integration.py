"""Integration tests for the complete TAC framework."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from tac import TAC, TACConfig
from tac.channels.sms import SMSChannel
from tac.context.memory import MemoryClient
from tac.core.config import TwilioMemoryConfig
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
            "configurationId": "conv_configuration_test123",
            "serviceId": "IStest123",
            "status": status,
            "name": "Test Conversation",
            "createdAt": "2025-11-18T00:00:00.000Z",
            "updatedAt": timestamp,
            "configuration": {"intelligenceServiceIds": []},
        },
    }


def get_test_config(with_memory=True):
    """Get a valid test configuration."""
    config = {
        "account_sid": "ACtest123",
        "auth_token": "test_token_123",
        "api_key": "SK123",
        "api_secret": "test_api_token",
        "conversation_configuration_id": "conv_configuration_test123",
        "phone_number": "+15551234567",
    }
    if with_memory:
        config["memory_config"] = TwilioMemoryConfig(trait_groups=["Contact"])
    return config


def create_memory_client(tac: TAC) -> MemoryClient:
    """Helper to manually create Conversation Memory client for tests."""
    return MemoryClient(
        store_id="MGtest123",
        api_key=tac.config.api_key,
        api_secret=tac.config.api_secret,
    )


class TestTACIntegration:
    """Integration tests for complete TAC workflow."""

    def test_configuration_validation_workflow(self):
        """Test complete workflow with configuration validation."""
        # Valid configurations
        valid_configs = [
            get_test_config(),
            TACConfig(**get_test_config()),
        ]

        for config in valid_configs:
            tac = TAC(config)
            assert tac.config.auth_token == "test_token_123"

        # Configuration with extra fields should be allowed (ignored)
        flexible_config = get_test_config().copy()
        flexible_config["extra_field"] = "extra_value"
        tac = TAC(flexible_config)
        assert tac.config.auth_token == "test_token_123"

        # Invalid configurations (wrong types)
        invalid_configs = [
            "not_a_dict_or_config",
            123,
        ]

        for invalid_config in invalid_configs:
            with pytest.raises((ValueError, TypeError)):
                TAC(invalid_config)

    @pytest.mark.asyncio
    async def test_sms_channel_end_to_end_workflow(self):
        """Test complete SMS channel workflow from webhook to callback."""

        tac = TAC(get_test_config())
        tac.conversation_memory_client = create_memory_client(tac)
        channel = SMSChannel(
            tac, config={"memory_retrieval": "always"}
        )  # Enable memory retrieval for test

        # Track callback invocations
        callback_invoked = False
        received_context = None
        received_memories = None

        def message_ready_callback(
            user_message: str,
            context: ConversationSession,
            memory_response: TACMemoryResponse | None = None,
        ):
            nonlocal callback_invoked, received_context, received_memories
            callback_invoked = True
            received_context = context
            received_memories = memory_response

        tac.on_message_ready(message_ready_callback)

        # Simulate participant.added webhook (CUSTOMER with profile)
        participant_added = create_participant_added_webhook(
            "CH123456", "MB123", "profile_test_123", "2025-11-18T00:00:01.000Z"
        )

        await channel.process_webhook(participant_added)

        # Verify conversation was initialized with profile
        assert "CH123456" in channel._conversations
        assert channel._conversations["CH123456"].profile_id == "profile_test_123"

        # Simulate communication.created webhook (incoming message)
        message_webhook = create_communication_created_webhook(
            "CH123456", "MB123", "Hello, I need help with my order", "2025-11-18T00:00:02.000Z"
        )

        empty_response = MemoryRetrievalResponse(
            observations=[],
            summaries=[],
            meta=MemoryRetrievalMeta(queryTime=0),
        )
        tac.conversation_memory_client.retrieve_memory = AsyncMock(return_value=empty_response)

        await channel.process_webhook(message_webhook)

        # Verify memory retrieval was called
        tac.conversation_memory_client.retrieve_memory.assert_called_once()

        # Verify callback was invoked with correct data
        assert callback_invoked
        assert received_context is not None
        assert received_context.conversation_id == "CH123456"
        assert received_context.profile_id == "profile_test_123"
        assert received_context.channel == "sms"

        # Verify memory response is wrapped in TACMemoryResponse
        assert isinstance(received_memories, TACMemoryResponse)
        assert received_memories.raw_data == empty_response
        assert len(received_memories.observations) == 0
        assert len(received_memories.summaries) == 0

    @pytest.mark.asyncio
    async def test_sms_channel_auto_initialize_conversation(self):
        """Test SMS channel auto-initializes conversation on first message."""
        tac = TAC(get_test_config())
        tac.conversation_memory_client = create_memory_client(tac)
        channel = SMSChannel(tac)

        callback_invoked = False

        def message_ready_callback(
            user_message: str,
            context: ConversationSession,
            memory_response: TACMemoryResponse | None = None,
        ):
            nonlocal callback_invoked
            callback_invoked = True

        tac.on_message_ready(message_ready_callback)

        # Send message without explicit conversation start (auto-initialize)
        message_webhook = create_communication_created_webhook(
            "CH999999",
            "MB999",
            "First message without conversation start",
            "2025-11-18T00:00:00.000Z",
            author_address="+19999999999",
        )

        empty_response = MemoryRetrievalResponse(
            observations=[],
            summaries=[],
            meta=MemoryRetrievalMeta(queryTime=0),
        )
        tac.conversation_memory_client.retrieve_memory = AsyncMock(return_value=empty_response)

        await channel.process_webhook(message_webhook)

        # Verify conversation was auto-initialized
        assert "CH999999" in channel._conversations
        assert callback_invoked

    @pytest.mark.asyncio
    async def test_sms_channel_filters_empty_messages(self):
        """Test SMS channel ignores empty/whitespace messages."""

        tac = TAC(get_test_config())
        tac.conversation_memory_client = create_memory_client(tac)
        channel = SMSChannel(tac)

        callback_invoked = False

        def message_ready_callback(
            user_message: str,
            context: ConversationSession,
            memory_response: TACMemoryResponse | None = None,
        ):
            nonlocal callback_invoked
            callback_invoked = True

        tac.on_message_ready(message_ready_callback)

        # Initialize conversation
        await channel.process_webhook(
            create_conversation_created_webhook("CH111", "2025-11-18T00:00:00.000Z")
        )

        # Test empty message
        empty_message = create_communication_created_webhook(
            "CH111", "MB111", "", "2025-11-18T00:00:01.000Z", author_address="+11111111111"
        )

        tac.conversation_memory_client.retrieve_memory = AsyncMock()
        await channel.process_webhook(empty_message)
        tac.conversation_memory_client.retrieve_memory.assert_not_called()
        assert not callback_invoked

        # Test whitespace message
        whitespace_message = create_communication_created_webhook(
            "CH111",
            "MB111",
            "   \n\t   ",
            "2025-11-18T00:00:02.000Z",
            author_address="+11111111111",
        )

        tac.conversation_memory_client.retrieve_memory = AsyncMock()
        await channel.process_webhook(whitespace_message)
        tac.conversation_memory_client.retrieve_memory.assert_not_called()
        assert not callback_invoked

    @pytest.mark.asyncio
    async def test_sms_channel_conversation_cleanup(self):
        """Test SMS channel cleans up conversation state properly."""

        tac = TAC(get_test_config())
        channel = SMSChannel(tac)

        # Start conversation via participant added
        await channel.process_webhook(
            create_participant_added_webhook("CH222", "PA222", "PR222", "2025-11-18T00:00:00.000Z")
        )

        assert "CH222" in channel._conversations

        # End conversation (status changed to CLOSED)
        await channel.process_webhook(
            create_conversation_updated_webhook("CH222", "CLOSED", "2025-11-18T00:10:00.000Z")
        )

        assert "CH222" not in channel._conversations

    @pytest.mark.asyncio
    async def test_sms_channel_multiple_concurrent_conversations(self):
        """Test SMS channel handles multiple concurrent conversations."""

        tac = TAC(get_test_config())
        tac.conversation_memory_client = create_memory_client(tac)
        channel = SMSChannel(tac)

        callback_count = 0
        conversation_ids = set()

        def message_ready_callback(
            user_message: str,
            context: ConversationSession,
            memory_response: TACMemoryResponse | None = None,
        ):
            nonlocal callback_count
            callback_count += 1
            conversation_ids.add(context.conversation_id)

        tac.on_message_ready(message_ready_callback)

        # Start multiple conversations via participant added
        for i in range(3):
            conv_id = f"CH{i:06d}"
            participant_id = f"PA{i:06d}"
            profile_id = f"PR{i:06d}"
            await channel.process_webhook(
                create_participant_added_webhook(
                    conv_id, participant_id, profile_id, f"2025-11-18T00:00:{i:02d}.000Z"
                )
            )

        # Send messages to each conversation
        empty_response = MemoryRetrievalResponse(
            observations=[],
            summaries=[],
            meta=MemoryRetrievalMeta(queryTime=0),
        )
        tac.conversation_memory_client.retrieve_memory = AsyncMock(return_value=empty_response)

        for i in range(3):
            conv_id = f"CH{i:06d}"
            await channel.process_webhook(
                create_communication_created_webhook(
                    conv_id,
                    f"MB{i:06d}",
                    f"Message {i}",
                    f"2025-11-18T00:01:{i:02d}.000Z",
                    author_address=f"+1{i:010d}",
                )
            )

        # Verify all callbacks were invoked
        assert callback_count == 3
        assert len(conversation_ids) == 3

    @pytest.mark.asyncio
    async def test_sms_channel_real_world_webhook_scenario(self):
        """Test SMS channel with real-world webhook data including all fields."""
        tac = TAC(get_test_config())
        tac.conversation_memory_client = create_memory_client(tac)
        channel = SMSChannel(tac)

        callback_invoked = False
        received_context = None

        def message_ready_callback(
            user_message: str,
            context: ConversationSession,
            memory_response: TACMemoryResponse | None = None,
        ):
            nonlocal callback_invoked, received_context
            callback_invoked = True
            received_context = context

        tac.on_message_ready(message_ready_callback)

        # Simulate real Twilio webhook with ConversationEvent format
        real_webhook = create_communication_created_webhook(
            "CHd151e6bcbe3643979a3f41f6d0da3b24",
            "MB723da60623f74438acee5baafbd438f0",
            "Hi, I'm having trouble with my account login. Can you help me reset my password?",
            "2025-09-17T22:23:11.350Z",
            author_address="+12162622233",
        )

        empty_response = MemoryRetrievalResponse(
            observations=[],
            summaries=[],
            meta=MemoryRetrievalMeta(queryTime=0),
        )
        tac.conversation_memory_client.retrieve_memory = AsyncMock(return_value=empty_response)

        await channel.process_webhook(real_webhook)

        # Verify processing completed
        assert callback_invoked
        assert received_context is not None
        assert received_context.conversation_id == "CHd151e6bcbe3643979a3f41f6d0da3b24"
        # No profile_id in this webhook (auto-initialized without profile)
        assert received_context.profile_id is None
        assert received_context.channel == "sms"

    @pytest.mark.asyncio
    async def test_sms_channel_missing_profile_id_handling(self):
        """Test SMS channel raises ValueError when profile_id is missing."""
        tac = TAC(get_test_config())
        channel = SMSChannel(tac)

        callback_invoked = False

        def message_ready_callback(
            user_message: str,
            context: ConversationSession,
            memory_response: TACMemoryResponse | None = None,
        ):
            nonlocal callback_invoked
            callback_invoked = True

        tac.on_message_ready(message_ready_callback)

        # Message without profile_id (using new event format)
        message_webhook = create_communication_created_webhook(
            "CH777",
            "MB777",
            "Message without profile",
            "2025-11-18T00:00:00.000Z",
            author_address="+17777777777",
        )

        # Verify that processing webhook without profile_id doesn't propagate
        # an exception to the caller. The conversation is auto-initialized with
        # None profile_id, which will cause retrieve_memory to raise ValueError
        # internally if memory is enabled; otherwise, no exception is raised.
        # In both cases, the exception (if any) is handled internally and the
        # callback is still invoked.
        await channel.process_webhook(message_webhook)

        # Callback should be invoked despite the memory retrieval error
        # (memory retrieval failure doesn't prevent message processing)
        assert callback_invoked
        # Verify conversation was auto-initialized despite the error
        assert "CH777" in channel._conversations
