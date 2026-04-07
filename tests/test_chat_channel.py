"""Tests for Chat Channel."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from tac import TAC
from tac.channels.chat import ChatChannel, ChatChannelConfig
from tac.models.memory import MemoryRetrievalMeta, MemoryRetrievalResponse
from tac.models.session import AuthorInfo, ConversationSession
from tac.models.tac import TACMemoryResponse


def create_participant_added_webhook(
    conversation_id: str,
    participant_id: str,
    profile_id: str,
    timestamp: str,
    address: str = "user@example.com",
) -> dict[str, Any]:
    return {
        "eventType": "PARTICIPANT_ADDED",
        "timestamp": timestamp,
        "data": {
            "id": participant_id,
            "conversationId": conversation_id,
            "accountId": "ACtest123",
            "serviceId": "IStest123",
            "name": address,
            "type": "CUSTOMER",
            "profileId": profile_id,
            "addresses": [{"channel": "CHAT", "address": address, "channelId": "CH_CHAT_SID_123"}],
            "createdAt": timestamp,
            "updatedAt": timestamp,
        },
    }


def create_communication_created_webhook(
    conversation_id: str,
    participant_id: str,
    message_text: str,
    timestamp: str,
    author_address: str = "user@example.com",
    author_channel: str = "CHAT",
    channel_id: str = "CH_CHAT_SID_123",
) -> dict[str, Any]:
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
                "channel": author_channel,
                "participantId": participant_id,
            },
            "content": {"type": "TEXT", "text": message_text},
            "channelId": channel_id,
            "recipients": [
                {
                    "address": "ai-assistant",
                    "channel": "CHAT",
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
    return {
        "eventType": "CONVERSATION_UPDATED",
        "timestamp": timestamp,
        "data": {
            "id": conversation_id,
            "accountId": "ACtest123",
            "configurationId": "conv_configuration_test123",
            "serviceId": "IStest123",
            "status": status,
            "name": "Test Chat Conversation",
            "createdAt": "2025-11-18T00:00:00.000Z",
            "updatedAt": timestamp,
        },
    }


def get_test_config() -> dict[str, Any]:
    return {
        "twilio_auth_token": "test_token_123",
        "api_key": "SK123",
        "api_token": "test_api_token",
        "environment": "prod",
        "conversation_configuration_id": "conv_configuration_test123",
        "twilio_phone_number": "+15551234567",
    }


class TestChatChannel:
    """Test Chat Channel functionality."""

    def test_initialization_defaults(self) -> None:
        tac = TAC(get_test_config())
        channel = ChatChannel(tac)
        assert channel.agent_address == "ai-assistant"
        assert channel.get_channel_name() == "chat"
        assert channel.get_channel_type_upper() == "CHAT"

    def test_initialization_custom_agent_address(self) -> None:
        tac = TAC(get_test_config())
        channel = ChatChannel(tac, config=ChatChannelConfig(agent_address="my-bot"))
        assert channel.agent_address == "my-bot"

    def test_initialization_from_dict(self) -> None:
        tac = TAC(get_test_config())
        channel = ChatChannel(tac, config={"agent_address": "custom-bot"})
        assert channel.agent_address == "custom-bot"

    def test_is_own_message(self) -> None:
        tac = TAC(get_test_config())
        channel = ChatChannel(tac)
        assert channel.is_own_message("ai-assistant") is True
        assert channel.is_own_message("user@example.com") is False

    @pytest.mark.asyncio
    async def test_process_participant_added(self) -> None:
        tac = TAC(get_test_config())
        channel = ChatChannel(tac)

        webhook = create_participant_added_webhook(
            "CH123", "PA123", "profile_123", "2025-11-18T00:00:01.000Z"
        )
        await channel.process_webhook(webhook)

        assert "CH123" in channel._conversations
        assert channel._conversations["CH123"].profile_id == "profile_123"
        assert channel._conversations["CH123"].channel == "chat"

    @pytest.mark.asyncio
    async def test_ignores_sms_participant(self) -> None:
        """PARTICIPANT_ADDED with SMS address should be ignored by ChatChannel."""
        tac = TAC(get_test_config())
        channel = ChatChannel(tac)

        webhook = {
            "eventType": "PARTICIPANT_ADDED",
            "timestamp": "2025-11-18T00:00:01.000Z",
            "data": {
                "id": "PA123",
                "conversationId": "CH123",
                "accountId": "ACtest123",
                "serviceId": "IStest123",
                "name": "+12345678901",
                "type": "CUSTOMER",
                "profileId": "profile_123",
                "addresses": [{"channel": "SMS", "address": "+12345678901"}],
                "createdAt": "2025-11-18T00:00:01.000Z",
                "updatedAt": "2025-11-18T00:00:01.000Z",
            },
        }
        await channel.process_webhook(webhook)
        assert "CH123" not in channel._conversations

    @pytest.mark.asyncio
    async def test_process_message(self) -> None:
        tac = TAC(get_test_config())
        channel = ChatChannel(tac)
        captured_messages: list[str] = []

        def message_callback(
            user_message: str,
            context: ConversationSession,
            memory_response: TACMemoryResponse | None,
        ) -> None:
            captured_messages.append(user_message)

        tac.on_message_ready(message_callback)

        webhook = create_communication_created_webhook(
            "CH123", "PA_USER", "Hello from chat!", "2025-11-18T00:00:00.000Z"
        )
        await channel.process_webhook(webhook)

        assert len(captured_messages) == 1
        assert captured_messages[0] == "Hello from chat!"

    @pytest.mark.asyncio
    async def test_channel_id_stored_in_metadata(self) -> None:
        tac = TAC(get_test_config())
        channel = ChatChannel(tac)

        tac.on_message_ready(lambda msg, ctx, mem: None)

        webhook = create_communication_created_webhook(
            "CH123",
            "PA_USER",
            "Test",
            "2025-11-18T00:00:00.000Z",
            channel_id="CH_CHAT_SID_456",
        )
        await channel.process_webhook(webhook)

        session = channel._conversations["CH123"]
        assert session.metadata["channel_id"] == "CH_CHAT_SID_456"

    @pytest.mark.asyncio
    async def test_ignores_sms_messages(self) -> None:
        """COMMUNICATION_CREATED with author.channel=SMS is filtered by ChatChannel."""
        tac = TAC(get_test_config())
        channel = ChatChannel(tac)
        captured: list[str] = []

        tac.on_message_ready(lambda msg, ctx, mem: captured.append(msg))

        webhook = create_communication_created_webhook(
            "CH123",
            "PA_USER",
            "SMS message",
            "2025-11-18T00:00:00.000Z",
            author_channel="SMS",
        )
        await channel.process_webhook(webhook)

        assert len(captured) == 0

    @pytest.mark.asyncio
    async def test_ignores_own_messages(self) -> None:
        tac = TAC(get_test_config())
        channel = ChatChannel(tac)
        captured: list[str] = []

        tac.on_message_ready(lambda msg, ctx, mem: captured.append(msg))

        webhook = create_communication_created_webhook(
            "CH123",
            "PA_AGENT",
            "Bot response",
            "2025-11-18T00:00:00.000Z",
            author_address="ai-assistant",
        )
        await channel.process_webhook(webhook)

        assert len(captured) == 0

    @pytest.mark.asyncio
    async def test_ignores_empty_messages(self) -> None:
        tac = TAC(get_test_config())
        channel = ChatChannel(tac)
        captured: list[str] = []

        tac.on_message_ready(lambda msg, ctx, mem: captured.append(msg))

        webhook = create_communication_created_webhook(
            "CH123", "PA_USER", "", "2025-11-18T00:00:00.000Z"
        )
        await channel.process_webhook(webhook)

        assert len(captured) == 0

    @pytest.mark.asyncio
    async def test_process_conversation_ended(self) -> None:
        tac = TAC(get_test_config())
        channel = ChatChannel(tac)

        await channel.process_webhook(
            create_participant_added_webhook(
                "CH123", "PA123", "profile_123", "2025-11-18T00:00:01.000Z"
            )
        )
        assert "CH123" in channel._conversations

        await channel.process_webhook(
            create_conversation_updated_webhook("CH123", "CLOSED", "2025-11-18T00:10:00.000Z")
        )
        assert "CH123" not in channel._conversations

    @pytest.mark.asyncio
    async def test_conversation_ended_callback(self) -> None:
        tac = TAC(get_test_config())
        channel = ChatChannel(tac)
        captured: list[ConversationSession] = []

        tac.on_conversation_ended(lambda ctx: captured.append(ctx))

        await channel.process_webhook(
            create_participant_added_webhook(
                "CH123", "PA123", "profile_123", "2025-11-18T00:00:01.000Z"
            )
        )
        await channel.process_webhook(
            create_conversation_updated_webhook("CH123", "CLOSED", "2025-11-18T00:10:00.000Z")
        )

        assert len(captured) == 1
        assert captured[0].conversation_id == "CH123"
        assert captured[0].channel == "chat"

    @pytest.mark.asyncio
    async def test_send_response_reuses_existing_agent(self) -> None:
        from tac.models.conversation import ParticipantAddress, ParticipantResponse

        tac = TAC(get_test_config())
        channel = ChatChannel(tac)

        # Set up session with author_info and channel_id
        channel._conversations["CH123"] = ConversationSession(
            conversation_id="CH123",
            channel="chat",
            author_info=AuthorInfo(address="user@example.com", participant_id="PA_USER"),
            metadata={"channel_id": "CH_CHAT_SID_123"},
        )

        mock_agent = ParticipantResponse(
            **{  # type: ignore[arg-type]
                "id": "PA_AGENT",
                "accountId": "ACtest123",
                "conversationId": "CH123",
                "name": "AI Agent",
                "type": "AI_AGENT",
                "addresses": [
                    ParticipantAddress(
                        channel="CHAT", address="ai-assistant", channel_id="CH_CHAT_SID_123"
                    ).model_dump(by_alias=True)
                ],
            }
        )

        mock_customer = ParticipantResponse(
            **{  # type: ignore[arg-type]
                "id": "PA_USER",
                "accountId": "ACtest123",
                "conversationId": "CH123",
                "name": "user@example.com",
                "type": "CUSTOMER",
                "addresses": [
                    ParticipantAddress(
                        channel="CHAT", address="user@example.com", channel_id="CH_CHAT_SID_123"
                    ).model_dump(by_alias=True)
                ],
            }
        )

        with (
            patch.object(
                tac.conversation_orchestrator_client,
                "list_participants",
                return_value=[mock_agent, mock_customer],
            ),
            patch.object(tac.conversation_orchestrator_client, "send_communication") as mock_send,
        ):
            await channel.send_response("CH123", "Hello from bot!")

            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][0] == "CH123"
            request = call_args[0][1]
            assert request.author.address == "ai-assistant"
            assert request.author.channel == "CHAT"
            assert request.author.participant_id == "PA_AGENT"
            assert request.content.text == "Hello from bot!"
            assert request.recipients[0].address == "user@example.com"
            assert request.recipients[0].channel == "CHAT"
            assert request.channel_id == "CH_CHAT_SID_123"

    @pytest.mark.asyncio
    async def test_send_response_creates_agent_lazily(self) -> None:
        from tac.models.conversation import ParticipantAddress, ParticipantResponse

        tac = TAC(get_test_config())
        channel = ChatChannel(tac)

        channel._conversations["CH123"] = ConversationSession(
            conversation_id="CH123",
            channel="chat",
            author_info=AuthorInfo(address="user@example.com", participant_id="PA_USER"),
            metadata={"channel_id": "CH_CHAT_SID_123"},
        )

        mock_customer = ParticipantResponse(
            **{  # type: ignore[arg-type]
                "id": "PA_USER",
                "accountId": "ACtest123",
                "conversationId": "CH123",
                "name": "user@example.com",
                "type": "CUSTOMER",
                "addresses": [
                    ParticipantAddress(channel="CHAT", address="user@example.com").model_dump(
                        by_alias=True
                    )
                ],
            }
        )

        mock_new_agent = ParticipantResponse(
            **{  # type: ignore[arg-type]
                "id": "PA_NEW_AGENT",
                "accountId": "ACtest123",
                "conversationId": "CH123",
                "name": "AI Agent",
                "type": "AI_AGENT",
                "addresses": [
                    ParticipantAddress(
                        channel="CHAT", address="ai-assistant", channel_id="CH_CHAT_SID_123"
                    ).model_dump(by_alias=True)
                ],
            }
        )

        with (
            patch.object(
                tac.conversation_orchestrator_client,
                "list_participants",
                return_value=[mock_customer],  # No AI_AGENT
            ),
            patch.object(
                tac.conversation_orchestrator_client,
                "add_participant",
                return_value=mock_new_agent,
            ) as mock_add,
            patch.object(tac.conversation_orchestrator_client, "send_communication") as mock_send,
        ):
            await channel.send_response("CH123", "Hello!")

            mock_add.assert_called_once()
            add_args = mock_add.call_args
            assert add_args[1]["participant_type"] == "AI_AGENT"
            addresses = add_args[1]["addresses"]
            assert addresses[0].channel == "CHAT"
            assert addresses[0].address == "ai-assistant"

            mock_send.assert_called_once()
            request = mock_send.call_args[0][1]
            assert request.author.participant_id == "PA_NEW_AGENT"

    @pytest.mark.asyncio
    async def test_send_response_race_condition(self) -> None:
        """If add_participant fails, retry listing to find existing agent."""
        from tac.models.conversation import ParticipantAddress, ParticipantResponse

        tac = TAC(get_test_config())
        channel = ChatChannel(tac)

        channel._conversations["CH123"] = ConversationSession(
            conversation_id="CH123",
            channel="chat",
            author_info=AuthorInfo(address="user@example.com", participant_id="PA_USER"),
            metadata={"channel_id": "CH_CHAT_SID_123"},
        )

        mock_customer = ParticipantResponse(
            **{  # type: ignore[arg-type]
                "id": "PA_USER",
                "accountId": "ACtest123",
                "conversationId": "CH123",
                "name": "user@example.com",
                "type": "CUSTOMER",
                "addresses": [
                    ParticipantAddress(channel="CHAT", address="user@example.com").model_dump(
                        by_alias=True
                    )
                ],
            }
        )

        mock_agent = ParticipantResponse(
            **{  # type: ignore[arg-type]
                "id": "PA_AGENT",
                "accountId": "ACtest123",
                "conversationId": "CH123",
                "name": "AI Agent",
                "type": "AI_AGENT",
                "addresses": [
                    ParticipantAddress(channel="CHAT", address="ai-assistant").model_dump(
                        by_alias=True
                    )
                ],
            }
        )

        # First list returns no agent, add_participant fails, retry list finds agent
        with (
            patch.object(
                tac.conversation_orchestrator_client,
                "list_participants",
                side_effect=[
                    [mock_customer],  # First call: no agent
                    [mock_customer, mock_agent],  # Retry: agent exists
                ],
            ),
            patch.object(
                tac.conversation_orchestrator_client,
                "add_participant",
                side_effect=Exception("409 Conflict"),
            ),
            patch.object(tac.conversation_orchestrator_client, "send_communication") as mock_send,
        ):
            await channel.send_response("CH123", "Hello!")

            mock_send.assert_called_once()
            request = mock_send.call_args[0][1]
            assert request.author.participant_id == "PA_AGENT"

    @pytest.mark.asyncio
    async def test_send_response_no_session(self) -> None:
        tac = TAC(get_test_config())
        channel = ChatChannel(tac)
        # No session — should log error and return without raising
        await channel.send_response("CH999", "Hello!")

    @pytest.mark.asyncio
    async def test_send_response_no_channel_id(self) -> None:
        tac = TAC(get_test_config())
        channel = ChatChannel(tac)

        channel._conversations["CH123"] = ConversationSession(
            conversation_id="CH123",
            channel="chat",
            author_info=AuthorInfo(address="user@example.com", participant_id="PA_USER"),
            metadata={},  # No channel_id
        )
        # Should log error and return without raising
        await channel.send_response("CH123", "Hello!")

    @pytest.mark.asyncio
    async def test_send_response_rejects_non_string(self) -> None:
        tac = TAC(get_test_config())
        channel = ChatChannel(tac)
        with pytest.raises(TypeError, match="Chat channel only supports string responses"):
            await channel.send_response("CH123", 123)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_deduplication(self) -> None:
        tac = TAC(get_test_config())
        channel = ChatChannel(tac)
        captured: list[str] = []

        tac.on_message_ready(lambda msg, ctx, mem: captured.append(msg))

        webhook = create_communication_created_webhook(
            "CH123", "PA_USER", "Dedup test", "2025-11-18T00:00:00.000Z"
        )

        await channel.process_webhook(webhook, idempotency_token="token_1")
        await channel.process_webhook(webhook, idempotency_token="token_1")

        assert len(captured) == 1

    @pytest.mark.asyncio
    async def test_skips_webhook_with_missing_data(self) -> None:
        """Webhook with missing or null data field should be skipped gracefully."""
        tac = TAC(get_test_config())
        channel = ChatChannel(tac)
        captured: list[str] = []

        tac.on_message_ready(lambda msg, ctx, mem: captured.append(msg))

        # Missing data field entirely
        await channel.process_webhook({"eventType": "COMMUNICATION_CREATED"})
        # Null data field
        await channel.process_webhook({"eventType": "PARTICIPANT_ADDED", "data": None})

        assert len(captured) == 0
        assert len(channel._conversations) == 0

    @pytest.mark.asyncio
    async def test_auto_retrieve_memory(self) -> None:
        from tac.context.memory import MemoryClient

        tac = TAC(get_test_config())
        tac.conversation_memory_client = MemoryClient(
            base_url=tac.config.memory_base_url,
            store_id="MGtest123",
            api_key=tac.config.api_key,
            api_token=tac.config.api_token,
        )
        channel = ChatChannel(tac, config={"auto_retrieve_memory": True})

        # Start conversation with profile_id via participant added
        await channel.process_webhook(
            create_participant_added_webhook(
                "CH123", "PA_USER", "profile_test_123", "2025-11-18T00:00:01.000Z"
            )
        )

        captured_memory: list[TACMemoryResponse | None] = []

        def callback(msg: str, ctx: ConversationSession, mem: TACMemoryResponse | None) -> None:
            captured_memory.append(mem)

        tac.on_message_ready(callback)

        empty_response = MemoryRetrievalResponse(
            observations=[], summaries=[], meta=MemoryRetrievalMeta(queryTime=0)
        )
        tac.conversation_memory_client.retrieve_memory = AsyncMock(return_value=empty_response)

        webhook = create_communication_created_webhook(
            "CH123", "PA_USER", "Memory test", "2025-11-18T00:00:02.000Z"
        )
        await channel.process_webhook(webhook)

        tac.conversation_memory_client.retrieve_memory.assert_called_once()
