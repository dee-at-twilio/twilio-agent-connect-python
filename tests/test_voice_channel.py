"""Tests for Voice Channel."""

import asyncio
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tac import TAC
from tac.channels.voice import VoiceChannel
from tac.models.conversation import ConversationResponse, ParticipantResponse
from tac.models.memory import MemoryRetrievalResponse
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse
from tac.models.voice import (
    CustomParameters,
    InterruptMessage,
    PromptMessage,
    SetupMessage,
    TwiMLOptions,
)


def get_test_config() -> dict:
    """Get a valid test configuration."""
    return {
        "twilio_auth_token": "test_token_123",
        "api_key": "SK123",
        "api_token": "test_api_token",
        "environment": "prod",
        "conversation_service_sid": "IStest123",
        "twilio_phone_number": "+15551234567",
    }


class TestVoiceChannel:
    """Test Voice Channel functionality."""

    def test_initialization(self) -> None:
        """Test Voice channel initialization."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        assert channel.tac == tac
        assert channel._websocket_manager is not None
        assert len(channel._websocket_manager) == 0

    def test_get_channel_name(self) -> None:
        """Test get_channel_name returns 'voice'."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        assert channel.get_channel_name() == "voice"

    @pytest.mark.asyncio
    async def test_handle_setup_message(self) -> None:
        """Test handling setup message initializes conversation."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Create setup message
        setup_msg = SetupMessage(
            type="setup",
            conversationId="CALL123",
            customParameters={"conversationId": "CALL123"},
        )

        # Call handler directly (not async)
        channel._handle_setup(setup_msg)

        # Verify conversation was started
        assert "CALL123" in channel._conversations
        assert channel._conversations["CALL123"].profile_id is None
        assert channel._conversations["CALL123"].channel == "voice"

    @pytest.mark.asyncio
    async def test_handle_prompt_message_without_memory_retrieval(self) -> None:
        """Test handling prompt message when auto_retrieve_memory=False."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Setup conversation first
        channel._start_conversation("CALL123", "profile_test_123")

        # Create prompt message
        prompt_msg = PromptMessage(
            type="prompt",
            conversationId="CALL123",
            voicePrompt="Hello, I need help",
        )

        # Call handler directly
        await channel._handle_prompt("CALL123", prompt_msg)

        # With auto_retrieve_memory=False, memory is not fetched - test passes if no exception

    @pytest.mark.asyncio
    async def test_handle_prompt_message_with_memory_retrieval(self) -> None:
        """Test handling prompt message retrieves memory when auto_retrieve_memory=True."""
        # Create config with memory enabled
        config = get_test_config()
        from tac.core.config import TwilioMemoryConfig

        config["twilio_memory_config"] = TwilioMemoryConfig(trait_groups=["Contact"])
        tac = TAC(config)

        # Manually create memora_client for this test
        from tac.context.memory import MemoryClient

        tac.memora_client = MemoryClient(
            base_url=tac.config.memora_base_url,
            store_id="MGtest123",
            api_key=tac.config.api_key,
            api_token=tac.config.api_token,
        )

        # Mock the memory retrieval
        mock_memory_response = MemoryRetrievalResponse(
            observations=[],
            summaries=[],
            communications=[],
        )
        tac.memora_client.retrieve_memory = AsyncMock(return_value=mock_memory_response)

        # Create channel with auto_retrieve_memory enabled (default is False)
        channel = VoiceChannel(tac, config={"auto_retrieve_memory": True})

        # Setup conversation with profile_id
        channel._start_conversation("CALL123", "profile_test_123")

        # Create prompt message
        prompt_msg = PromptMessage(
            type="prompt",
            conversationId="CALL123",
            voicePrompt="Hello, I need help",
        )

        # Call handler directly
        await channel._handle_prompt("CALL123", prompt_msg)

        # Verify memory retrieval was called
        tac.memora_client.retrieve_memory.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_interrupt_message(self) -> None:
        """Test handling interrupt message."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Setup conversation first
        channel._start_conversation("CALL123", None)

        # Create interrupt message
        interrupt_msg = InterruptMessage(
            type="interrupt",
            utteranceUntilInterrupt="Hello, I was saying...",
            durationUntilInterruptMs=1500,
        )

        # Call handler directly
        channel._handle_interrupt("CALL123", interrupt_msg)

        # Test passes if no exception is raised

    @pytest.mark.asyncio
    async def test_handle_message_without_conversation_id(self) -> None:
        """Test that creating setup message without customParameters raises ValidationError."""
        from pydantic import ValidationError

        # Attempting to create SetupMessage without required customParameters
        # should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            SetupMessage(type="setup")

        # Verify error mentions the missing field
        assert "customParameters" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_send_response(self) -> None:
        """Test sending voice response through websocket."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Start conversation directly
        channel._start_conversation("CALL123", "profile_test")

        # Mock websocket and register it with the manager
        mock_websocket = AsyncMock()
        channel._websocket_manager.add_websocket("CALL123", mock_websocket)

        # Send response without role
        await channel.send_response("CALL123", "Hello there")

        # Verify websocket.send_text was called once
        assert mock_websocket.send_text.call_count == 1

        # Send response with role
        await channel.send_response("CALL123", "How can I help?", role="assistant")

        # Verify websocket.send_text was called again
        assert mock_websocket.send_text.call_count == 2

    @pytest.mark.asyncio
    async def test_send_response_without_websocket(self) -> None:
        """Test sending response without active websocket logs error."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Start conversation directly
        channel._start_conversation("CALL123", "profile_test")

        # No websocket registered in manager
        # (don't add websocket to manager, so lookup returns None)

        # Should log error and return early (no exception raised)
        await channel.send_response("CALL123", "Hello there")

    @pytest.mark.asyncio
    async def test_end_conversation_cleanup(self) -> None:
        """Test ending conversation cleans up resources."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Start conversation directly
        channel._start_conversation("CALL123", "profile_test")

        # Add a mock websocket to the manager
        mock_websocket = MagicMock()
        channel._websocket_manager.add_websocket("CALL123", mock_websocket)

        # Verify websocket is registered
        assert channel._websocket_manager.has_websocket("CALL123")
        assert "CALL123" in channel._conversations

        # Clean up conversation using the internal cleanup method
        await channel._cleanup_connection("CALL123")

        # Verify cleanup
        assert "CALL123" not in channel._conversations
        assert not channel._websocket_manager.has_websocket("CALL123")

    @pytest.mark.asyncio
    async def test_process_webhook_not_implemented(self) -> None:
        """Test that process_webhook is stubbed."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Should not raise
        await channel.process_webhook({})

    @pytest.mark.asyncio
    async def test_message_callback_integration(self) -> None:
        """Test message callback is invoked with conversation context."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Callback to capture context
        captured_context = None
        captured_memories = None
        captured_user_message = None

        async def message_callback(
            user_message: str,
            context: ConversationSession,
            memory_response: Optional[TACMemoryResponse],
        ) -> None:
            nonlocal captured_context, captured_memories, captured_user_message
            captured_context = context
            captured_memories = memory_response
            captured_user_message = user_message

        tac.on_message_ready(message_callback)

        # Setup conversation first
        channel._start_conversation("CALL123", "profile_test")

        # Create and handle prompt message
        prompt_msg = PromptMessage(
            type="prompt",
            conversationId="CALL123",
            voicePrompt="Test message",
        )
        await channel._handle_prompt("CALL123", prompt_msg)

        # Verify callback was invoked
        assert captured_context is not None
        assert captured_context.conversation_id == "CALL123"
        assert captured_context.profile_id == "profile_test"
        assert captured_context.channel == "voice"
        # Voice channel doesn't fetch memory, so it should be None
        assert captured_memories is None
        assert captured_user_message == "Test message"

    @pytest.mark.asyncio
    async def test_handle_incoming_call(self) -> None:
        """Test handle_incoming_call generates valid TwiML."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Mock conversation creation and participant addition
        with (
            patch.object(
                tac.maestro_client, "create_conversation", new_callable=AsyncMock
            ) as mock_create,
            patch.object(
                tac.maestro_client, "add_participant", new_callable=AsyncMock
            ) as mock_add_participant,
        ):
            mock_create.return_value = ConversationResponse(
                id="CONV123",
                account_id="ACtest123",
                service_id="IStest123",
            )
            mock_add_participant.return_value = ParticipantResponse(
                id="PART123",
                conversation_id="CONV123",
                account_id="ACtest123",
                service_id="IStest123",
                name="participant",
            )

            # Generate TwiML
            twiml = await channel.handle_incoming_call(
                to_number="+15551234567",
                from_number="+15559999999",
                options={
                    "websocket_url": "wss://example.ngrok.io/ws",
                    "action_url": "https://example.ngrok.io/flex_handoff",
                    "welcome_greeting": "Welcome!",
                },
            )

            # Verify TwiML contains expected elements
            assert '<?xml version="1.0" encoding="UTF-8"?>' in twiml
            assert "<Response>" in twiml
            assert '<Connect action="https://example.ngrok.io/flex_handoff">' in twiml
            assert "<ConversationRelay" in twiml
            assert 'url="wss://example.ngrok.io/ws"' in twiml
            assert 'welcomeGreeting="Welcome!"' in twiml
            assert '<Parameter name="conversationId" value="CONV123" />' in twiml
            assert "</ConversationRelay>" in twiml
            assert "</Connect>" in twiml
            assert "</Response>" in twiml

    @pytest.mark.asyncio
    async def test_handle_incoming_call_default_greeting(self) -> None:
        """Test handle_incoming_call uses default greeting."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Mock conversation creation and participant addition
        with (
            patch.object(
                tac.maestro_client, "create_conversation", new_callable=AsyncMock
            ) as mock_create,
            patch.object(
                tac.maestro_client, "add_participant", new_callable=AsyncMock
            ) as mock_add_participant,
        ):
            mock_create.return_value = ConversationResponse(
                id="CONV456",
                account_id="ACtest123",
                service_id="IStest123",
            )
            mock_add_participant.return_value = ParticipantResponse(
                id="PART456",
                conversation_id="CONV456",
                account_id="ACtest123",
                service_id="IStest123",
                name="participant",
            )

            # Generate TwiML without custom greeting (uses default)
            twiml = await channel.handle_incoming_call(
                to_number="+15551111111",
                from_number="+15559876543",
                options={
                    "websocket_url": "wss://test.ngrok.io/ws",
                    "action_url": "https://example.ngrok.io/flex_handoff",
                },
            )

            # Verify default greeting is used
            assert 'welcomeGreeting="Hello! How can I assist you today?"' in twiml

    @pytest.mark.asyncio
    async def test_setup_with_custom_parameters_profile_id(self) -> None:
        """Test setup message extracts profile_id from custom parameters."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Create setup message with profile_id
        setup_msg = SetupMessage(
            type="setup",
            conversationId="CONV123",
            customParameters={"conversationId": "CONV123", "profileId": "USER_PROFILE_789"},
        )

        # Call handler directly (not async)
        channel._handle_setup(setup_msg)

        # Verify conversation was started with correct profile_id
        assert "CONV123" in channel._conversations
        assert channel._conversations["CONV123"].profile_id == "USER_PROFILE_789"

    @pytest.mark.asyncio
    async def test_setup_without_conversation_id_raises_error(self) -> None:
        """Test that creating setup message without required fields raises ValidationError."""
        from pydantic import ValidationError

        # Attempting to create SetupMessage without required customParameters
        # should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            SetupMessage(type="setup")

        # Verify error is about missing required field
        assert "Field required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_prompt_with_empty_voice_prompt(self) -> None:
        """Test handling prompt message with empty voice_prompt."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Setup conversation first
        channel._start_conversation("CALL111", "profile_test")

        # Create prompt message with None voicePrompt
        prompt_msg = PromptMessage(
            type="prompt",
            conversationId="CALL111",
            voicePrompt=None,
        )

        # Call handler directly
        await channel._handle_prompt("CALL111", prompt_msg)

        # Voice channel doesn't fetch memory - test passes if no exception raised

    @pytest.mark.asyncio
    async def test_multiple_concurrent_conversations(self) -> None:
        """Test managing multiple concurrent conversations with separate websockets."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Start three concurrent conversations
        channel._start_conversation("CALL_001", "profile_001")
        channel._start_conversation("CALL_002", "profile_002")
        channel._start_conversation("CALL_003", "profile_003")

        # Create mock websockets for each conversation
        mock_ws_1 = AsyncMock()
        mock_ws_2 = AsyncMock()
        mock_ws_3 = AsyncMock()

        # Register websockets with the manager
        channel._websocket_manager.add_websocket("CALL_001", mock_ws_1)
        channel._websocket_manager.add_websocket("CALL_002", mock_ws_2)
        channel._websocket_manager.add_websocket("CALL_003", mock_ws_3)

        # Verify all conversations and websockets are tracked
        assert len(channel._conversations) == 3
        assert len(channel._websocket_manager) == 3
        assert channel._websocket_manager.has_websocket("CALL_001")
        assert channel._websocket_manager.has_websocket("CALL_002")
        assert channel._websocket_manager.has_websocket("CALL_003")

        # Send responses to each conversation independently
        await channel.send_response("CALL_001", "Response to call 1")
        await channel.send_response("CALL_002", "Response to call 2")
        await channel.send_response("CALL_003", "Response to call 3")

        # Verify each websocket received only its own message
        assert mock_ws_1.send_text.call_count == 1
        assert mock_ws_2.send_text.call_count == 1
        assert mock_ws_3.send_text.call_count == 1

        # Verify correct messages were sent to each websocket
        call_args_1 = mock_ws_1.send_text.call_args[0][0]
        call_args_2 = mock_ws_2.send_text.call_args[0][0]
        call_args_3 = mock_ws_3.send_text.call_args[0][0]

        assert "Response to call 1" in call_args_1
        assert "Response to call 2" in call_args_2
        assert "Response to call 3" in call_args_3

    @pytest.mark.asyncio
    async def test_multiple_conversations_independent_cleanup(self) -> None:
        """Test that cleaning up one conversation doesn't affect others."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Start three conversations
        channel._start_conversation("CALL_A", "profile_A")
        channel._start_conversation("CALL_B", "profile_B")
        channel._start_conversation("CALL_C", "profile_C")

        # Register websockets
        channel._websocket_manager.add_websocket("CALL_A", AsyncMock())
        channel._websocket_manager.add_websocket("CALL_B", AsyncMock())
        channel._websocket_manager.add_websocket("CALL_C", AsyncMock())

        # Verify initial state
        assert len(channel._conversations) == 3
        assert len(channel._websocket_manager) == 3

        # Clean up CALL_B only
        await channel._cleanup_connection("CALL_B")

        # Verify CALL_B is cleaned up but others remain
        assert "CALL_B" not in channel._conversations
        assert not channel._websocket_manager.has_websocket("CALL_B")
        assert len(channel._conversations) == 2
        assert len(channel._websocket_manager) == 2

        # Verify CALL_A and CALL_C are still active
        assert "CALL_A" in channel._conversations
        assert "CALL_C" in channel._conversations
        assert channel._websocket_manager.has_websocket("CALL_A")
        assert channel._websocket_manager.has_websocket("CALL_C")

        # Clean up remaining conversations
        await channel._cleanup_connection("CALL_A")
        await channel._cleanup_connection("CALL_C")

        # Verify complete cleanup
        assert len(channel._conversations) == 0
        assert len(channel._websocket_manager) == 0

    @pytest.mark.asyncio
    async def test_websocket_manager_get_all_conversation_ids(self) -> None:
        """Test WebSocketManager returns all active conversation IDs."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Initially empty
        assert channel._websocket_manager.get_all_conversation_ids() == []

        # Add multiple websockets
        channel._websocket_manager.add_websocket("CONV_1", AsyncMock())
        channel._websocket_manager.add_websocket("CONV_2", AsyncMock())
        channel._websocket_manager.add_websocket("CONV_3", AsyncMock())

        # Get all conversation IDs
        conv_ids = channel._websocket_manager.get_all_conversation_ids()

        # Verify all IDs are returned
        assert len(conv_ids) == 3
        assert "CONV_1" in conv_ids
        assert "CONV_2" in conv_ids
        assert "CONV_3" in conv_ids

    @pytest.mark.asyncio
    async def test_concurrent_responses_correct_routing(self) -> None:
        """Test that concurrent responses are routed to correct websockets."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Setup two conversations
        channel._start_conversation("CONV_X", "profile_X")
        channel._start_conversation("CONV_Y", "profile_Y")

        # Create distinct mock websockets
        mock_ws_x = AsyncMock()
        mock_ws_y = AsyncMock()

        channel._websocket_manager.add_websocket("CONV_X", mock_ws_x)
        channel._websocket_manager.add_websocket("CONV_Y", mock_ws_y)

        # Send multiple messages to each conversation
        await channel.send_response("CONV_X", "Message 1 to X")
        await channel.send_response("CONV_Y", "Message 1 to Y")
        await channel.send_response("CONV_X", "Message 2 to X")
        await channel.send_response("CONV_Y", "Message 2 to Y")
        await channel.send_response("CONV_X", "Message 3 to X")

        # Verify correct call counts
        assert mock_ws_x.send_text.call_count == 3
        assert mock_ws_y.send_text.call_count == 2

        # Verify CONV_X received only X messages
        x_calls = [call[0][0] for call in mock_ws_x.send_text.call_args_list]
        assert all("to X" in call for call in x_calls)
        assert not any("to Y" in call for call in x_calls)

        # Verify CONV_Y received only Y messages
        y_calls = [call[0][0] for call in mock_ws_y.send_text.call_args_list]
        assert all("to Y" in call for call in y_calls)
        assert not any("to X" in call for call in y_calls)

    @pytest.mark.asyncio
    async def test_websocket_removal_idempotent(self) -> None:
        """Test that removing a websocket multiple times is safe."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Add a websocket
        channel._websocket_manager.add_websocket("CONV_Z", AsyncMock())
        assert channel._websocket_manager.has_websocket("CONV_Z")

        # Remove it once
        channel._websocket_manager.remove_websocket("CONV_Z")
        assert not channel._websocket_manager.has_websocket("CONV_Z")

        # Remove it again (should not raise error)
        channel._websocket_manager.remove_websocket("CONV_Z")
        assert not channel._websocket_manager.has_websocket("CONV_Z")

        # Remove non-existent websocket (should not raise error)
        channel._websocket_manager.remove_websocket("NON_EXISTENT")

    @pytest.mark.asyncio
    async def test_websocket_replacement(self) -> None:
        """Test that adding a websocket with same conversation ID replaces the old one."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Add first websocket
        first_ws = AsyncMock()
        channel._websocket_manager.add_websocket("CONV_REPLACE", first_ws)

        # Verify first websocket is registered
        retrieved_ws = channel._websocket_manager.get_websocket("CONV_REPLACE")
        assert retrieved_ws is first_ws

        # Add second websocket with same conversation ID
        second_ws = AsyncMock()
        channel._websocket_manager.add_websocket("CONV_REPLACE", second_ws)

        # Verify second websocket replaced the first
        retrieved_ws = channel._websocket_manager.get_websocket("CONV_REPLACE")
        assert retrieved_ws is second_ws
        assert retrieved_ws is not first_ws

        # Verify still only one websocket tracked
        assert len(channel._websocket_manager) == 1

    @pytest.mark.asyncio
    async def test_active_hydration_setup(self) -> None:
        """Test that active hydration setup populates author_info and ai_agent_info."""
        config = get_test_config()
        config["enable_voice_active_hydration"] = True
        tac = TAC(config)
        channel = VoiceChannel(tac)

        # Create setup message with all required fields for active hydration
        setup_msg = SetupMessage(
            type="setup",
            conversationId="CONV123",
            from_number="+15551234567",
            to_number="+15559876543",
            customParameters={
                "conversationId": "CONV123",
                "customerParticipantId": "PART_CUSTOMER_123",
                "aiAgentParticipantId": "PART_AGENT_456",
            },
        )

        # Call handler directly (not async)
        channel._handle_setup(setup_msg)

        # Verify conversation was started with author and AI agent info
        assert "CONV123" in channel._conversations
        session = channel._conversations["CONV123"]
        assert session.author_info is not None
        assert session.author_info.address == "+15551234567"
        assert session.author_info.participant_id == "PART_CUSTOMER_123"
        assert session.ai_agent_info is not None
        assert session.ai_agent_info.address == "+15559876543"
        assert session.ai_agent_info.participant_id == "PART_AGENT_456"

    @pytest.mark.asyncio
    async def test_active_hydration_disabled(self) -> None:
        """Test that author_info and ai_agent_info are not set when active hydration is disabled."""
        config = get_test_config()
        config["enable_voice_active_hydration"] = False
        tac = TAC(config)
        channel = VoiceChannel(tac)

        # Create setup message with all fields
        setup_msg = SetupMessage(
            type="setup",
            conversationId="CONV456",
            from_number="+15551234567",
            to_number="+15559876543",
            customParameters={
                "conversationId": "CONV456",
                "customerParticipantId": "PART_CUSTOMER_123",
                "aiAgentParticipantId": "PART_AGENT_456",
            },
        )

        # Call handler directly (not async)
        channel._handle_setup(setup_msg)

        # Verify conversation was started but without author/AI agent info
        assert "CONV456" in channel._conversations
        session = channel._conversations["CONV456"]
        assert session.author_info is None
        assert session.ai_agent_info is None

    @pytest.mark.asyncio
    async def test_create_communication_with_optional_params(self) -> None:
        """Test _create_communication with optional participant IDs."""
        config = get_test_config()
        config["enable_voice_active_hydration"] = True
        tac = TAC(config)
        channel = VoiceChannel(tac)

        # Mock the maestro client's create_communication method
        with patch.object(
            tac.maestro_client, "create_communication", new_callable=AsyncMock
        ) as mock_add_comm:
            # Call _create_communication with optional parameters
            await channel._create_communication(
                conversation_id="CONV123",
                message_content="Hello world",
                author_address="+15551234567",
                recipient_address="+15559876543",
                author_participant_id="PART_AUTHOR",
                recipient_participant_id="PART_RECIPIENT",
            )

            # Verify create_communication was called
            assert mock_add_comm.call_count == 1

            # Verify the request structure
            call_args = mock_add_comm.call_args
            assert call_args[0][0] == "CONV123"  # conversation_id
            comm_request = call_args[0][1]  # CommunicationRequest
            assert comm_request.author.address == "+15551234567"
            assert comm_request.author.participant_id == "PART_AUTHOR"
            assert comm_request.content.text == "Hello world"
            assert len(comm_request.recipients) == 1
            assert comm_request.recipients[0].address == "+15559876543"
            assert comm_request.recipients[0].participant_id == "PART_RECIPIENT"

    @pytest.mark.asyncio
    async def test_send_response_skips_communication_without_participant_ids(self) -> None:
        """Test send_response skips _create_communication when participant IDs are missing."""
        config = get_test_config()
        config["enable_voice_active_hydration"] = True
        tac = TAC(config)
        channel = VoiceChannel(tac)

        # Start conversation
        channel._start_conversation("CALL789", "profile_test")

        # Set up author and AI agent info WITHOUT participant IDs
        from tac.models.session import AuthorInfo

        channel._conversations["CALL789"].author_info = AuthorInfo(
            address="+15551234567",
            participant_id=None,  # Missing participant ID
        )
        channel._conversations["CALL789"].ai_agent_info = AuthorInfo(
            address="+15559876543",
            participant_id=None,  # Missing participant ID
        )

        # Mock websocket and create_communication
        mock_websocket = AsyncMock()
        channel._websocket_manager.add_websocket("CALL789", mock_websocket)

        with patch.object(
            tac.maestro_client, "create_communication", new_callable=AsyncMock
        ) as mock_add_comm:
            # Send response - should skip communication creation due to missing participant IDs
            await channel.send_response("CALL789", "Test response")

            # Verify websocket was called but create_communication was NOT called
            assert mock_websocket.send_text.call_count == 1
            assert mock_add_comm.call_count == 0

    @pytest.mark.asyncio
    async def test_send_response_with_active_hydration(self) -> None:
        """Test send_response triggers _create_communication when active hydration is enabled."""
        config = get_test_config()
        config["enable_voice_active_hydration"] = True
        tac = TAC(config)
        channel = VoiceChannel(tac)

        # Start conversation
        channel._start_conversation("CALL789", "profile_test")

        # Set up author and AI agent info
        from tac.models.session import AuthorInfo

        channel._conversations["CALL789"].author_info = AuthorInfo(
            address="+15551234567", participant_id="PART_CUSTOMER"
        )
        channel._conversations["CALL789"].ai_agent_info = AuthorInfo(
            address="+15559876543", participant_id="PART_AGENT"
        )

        # Mock websocket and create_communication
        mock_websocket = AsyncMock()
        channel._websocket_manager.add_websocket("CALL789", mock_websocket)

        with patch.object(
            tac.maestro_client, "create_communication", new_callable=AsyncMock
        ) as mock_add_comm:
            # Send response
            await channel.send_response("CALL789", "Agent response")

            # Verify websocket was called
            assert mock_websocket.send_text.call_count == 1

            # Verify create_communication was called for active hydration
            assert mock_add_comm.call_count == 1

            # Verify the communication request
            call_args = mock_add_comm.call_args
            assert call_args[0][0] == "CALL789"
            comm_request = call_args[0][1]
            assert comm_request.author.address == "+15559876543"  # AI agent
            assert comm_request.recipients[0].address == "+15551234567"  # Customer

    @pytest.mark.asyncio
    async def test_handle_prompt_with_active_hydration(self) -> None:
        """Test _handle_prompt triggers _create_communication when active hydration is enabled."""
        config = get_test_config()
        config["enable_voice_active_hydration"] = True
        tac = TAC(config)
        channel = VoiceChannel(tac)

        # Start conversation
        channel._start_conversation("CALL999", "profile_test")

        # Set up author and AI agent info
        from tac.models.session import AuthorInfo

        channel._conversations["CALL999"].author_info = AuthorInfo(
            address="+15551234567", participant_id="PART_CUSTOMER"
        )
        channel._conversations["CALL999"].ai_agent_info = AuthorInfo(
            address="+15559876543", participant_id="PART_AGENT"
        )

        # Create prompt message
        prompt_msg = PromptMessage(
            type="prompt",
            conversationId="CALL999",
            voicePrompt="Customer message",
        )

        with patch.object(
            tac.maestro_client, "create_communication", new_callable=AsyncMock
        ) as mock_add_comm:
            # Handle prompt
            await channel._handle_prompt("CALL999", prompt_msg)

            # Verify create_communication was called for active hydration
            assert mock_add_comm.call_count == 1

            # Verify the communication request
            call_args = mock_add_comm.call_args
            assert call_args[0][0] == "CALL999"
            comm_request = call_args[0][1]
            assert comm_request.author.address == "+15551234567"  # Customer
            assert comm_request.recipients[0].address == "+15559876543"  # AI agent

    @pytest.mark.asyncio
    async def test_active_hydration_skipped_when_missing_info(self) -> None:
        """Test that active hydration is skipped when author_info or ai_agent_info is missing."""
        config = get_test_config()
        config["enable_voice_active_hydration"] = True
        tac = TAC(config)
        channel = VoiceChannel(tac)

        # Start conversation without setting author/AI agent info
        channel._start_conversation("CALL_NO_INFO", "profile_test")

        # Mock websocket
        mock_websocket = AsyncMock()
        channel._websocket_manager.add_websocket("CALL_NO_INFO", mock_websocket)

        with patch.object(
            tac.maestro_client, "create_communication", new_callable=AsyncMock
        ) as mock_add_comm:
            # Send response
            await channel.send_response("CALL_NO_INFO", "Response")

            # Verify websocket was called
            assert mock_websocket.send_text.call_count == 1

            # Verify create_communication was NOT called (missing info)
            assert mock_add_comm.call_count == 0

    @pytest.mark.asyncio
    async def test_send_response_with_invalid_type_raises_error(self) -> None:
        """Test that send_response raises TypeError for invalid response types."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Start conversation
        channel._start_conversation("CALL_INVALID", "profile_test")

        # Mock websocket
        mock_websocket = AsyncMock()
        channel._websocket_manager.add_websocket("CALL_INVALID", mock_websocket)

        # Test with integer (invalid type)
        with pytest.raises(TypeError, match="Voice channel requires string or async generator"):
            await channel.send_response("CALL_INVALID", 123)  # type: ignore[arg-type]

        # Test with dict (invalid type)
        with pytest.raises(TypeError, match="Voice channel requires string or async generator"):
            await channel.send_response("CALL_INVALID", {"message": "test"})  # type: ignore[arg-type]

        # Test with list (invalid type)
        with pytest.raises(TypeError, match="Voice channel requires string or async generator"):
            await channel.send_response("CALL_INVALID", ["hello"])  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_send_response_with_async_generator(self) -> None:
        """Test that send_response correctly handles async generators (streaming)."""
        from collections.abc import AsyncGenerator

        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Start conversation
        channel._start_conversation("CALL_STREAM", "profile_test")

        # Mock websocket
        mock_websocket = AsyncMock()
        channel._websocket_manager.add_websocket("CALL_STREAM", mock_websocket)

        # Create async generator
        async def stream_response() -> AsyncGenerator[str, None]:
            yield "Hello "
            yield "world"

        # Send streaming response
        await channel.send_response("CALL_STREAM", stream_response())

        # Verify websocket.send_text was called for each chunk + final marker
        # 3 calls: "Hello ", "world", and final {"last": True}
        assert mock_websocket.send_text.call_count == 3

    @pytest.mark.asyncio
    async def test_conversation_ended_callback_fires_on_cleanup(self) -> None:
        """Voice _cleanup_connection triggers on_conversation_ended with correct data."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)
        captured: list[ConversationSession] = []

        def handler(ctx: ConversationSession) -> None:
            captured.append(ctx)

        tac.on_conversation_ended(handler)

        # Start conversation and add a mock websocket
        channel._start_conversation("CALL_CB1", "prof_cb1")
        mock_ws = MagicMock()
        channel._websocket_manager.add_websocket("CALL_CB1", mock_ws)

        await channel._cleanup_connection("CALL_CB1")

        assert len(captured) == 1
        assert captured[0].conversation_id == "CALL_CB1"
        assert captured[0].profile_id == "prof_cb1"
        assert captured[0].channel == "voice"

    @pytest.mark.asyncio
    async def test_conversation_ended_callback_error_does_not_prevent_cleanup(self) -> None:
        """If on_conversation_ended callback raises, voice resources are still cleaned up."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        def bad_handler(ctx: ConversationSession) -> None:
            raise RuntimeError("boom")

        tac.on_conversation_ended(bad_handler)

        channel._start_conversation("CALL_CB2", "prof_cb2")
        mock_ws = MagicMock()
        channel._websocket_manager.add_websocket("CALL_CB2", mock_ws)

        await channel._cleanup_connection("CALL_CB2")

        assert "CALL_CB2" not in channel._conversations
        assert not channel._websocket_manager.has_websocket("CALL_CB2")

    @pytest.mark.asyncio
    async def test_conversation_ended_async_callback(self) -> None:
        """Async on_conversation_ended callback is awaited correctly for voice."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)
        captured: list[ConversationSession] = []

        async def async_handler(ctx: ConversationSession) -> None:
            captured.append(ctx)

        tac.on_conversation_ended(async_handler)

        channel._start_conversation("CALL_ASYNC1", "prof_async1")
        mock_ws = MagicMock()
        channel._websocket_manager.add_websocket("CALL_ASYNC1", mock_ws)

        await channel._cleanup_connection("CALL_ASYNC1")

        assert len(captured) == 1
        assert captured[0].conversation_id == "CALL_ASYNC1"
        assert captured[0].channel == "voice"

    @pytest.mark.asyncio
    async def test_conversation_ended_no_callback_registered(self) -> None:
        """Cleaning up voice connection without a registered callback works silently."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # No callback registered — should not raise
        channel._start_conversation("CALL_NOCB", "prof_nocb")
        mock_ws = MagicMock()
        channel._websocket_manager.add_websocket("CALL_NOCB", mock_ws)

        await channel._cleanup_connection("CALL_NOCB")

        assert "CALL_NOCB" not in channel._conversations
        assert not channel._websocket_manager.has_websocket("CALL_NOCB")

    @pytest.mark.asyncio
    async def test_conversation_ended_callback_fires_only_once_on_double_cleanup(self) -> None:
        """Calling _cleanup_connection twice fires the callback only once."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)
        captured: list[ConversationSession] = []

        def handler(ctx: ConversationSession) -> None:
            captured.append(ctx)

        tac.on_conversation_ended(handler)

        channel._start_conversation("CALL_DUP", "prof_dup")
        mock_ws = MagicMock()
        channel._websocket_manager.add_websocket("CALL_DUP", mock_ws)

        # First cleanup triggers callback and removes session
        await channel._cleanup_connection("CALL_DUP")
        # Second cleanup should be a no-op (session already gone)
        await channel._cleanup_connection("CALL_DUP")

        assert len(captured) == 1
        assert captured[0].conversation_id == "CALL_DUP"

    @pytest.mark.asyncio
    async def test_task_cancellation_with_unified_workflow(self) -> None:
        """Test that task cancellation still works with unified workflow.

        Tests streaming via callback pattern.
        """
        from collections.abc import AsyncGenerator

        from tac.session import ThreadSafeSessionManager

        tac = TAC(get_test_config())

        # Track cancellation
        stream_started = False
        stream_cancelled = False
        chunks_sent = 0

        async def user_callback(
            user_message: str,
            context: ConversationSession,
            memory_response: Optional[TACMemoryResponse],
        ) -> None:
            """User callback that generates streaming response."""
            nonlocal stream_started, stream_cancelled, chunks_sent

            # Create async generator (simulates OpenAI streaming)
            async def stream_response() -> AsyncGenerator[str, None]:
                nonlocal stream_started, stream_cancelled, chunks_sent
                stream_started = True
                try:
                    for i in range(100):
                        await asyncio.sleep(0.01)  # Simulate slow streaming
                        chunks_sent += 1
                        yield f"chunk_{i}"
                except asyncio.CancelledError:
                    stream_cancelled = True
                    raise

            # Send streaming response via voice channel
            await voice_channel.send_response(context.conversation_id, stream_response())

        tac.on_message_ready(user_callback)

        # Create session manager and voice channel
        session_manager = ThreadSafeSessionManager()
        voice_channel = VoiceChannel(
            tac=tac, config={"session_manager": session_manager, "auto_retrieve_memory": False}
        )

        # Setup conversation
        voice_channel._start_conversation("CONV_CANCEL_TEST", None)

        # Mock websocket
        mock_websocket = AsyncMock()
        voice_channel._websocket_manager.add_websocket("CONV_CANCEL_TEST", mock_websocket)

        # Create prompt message
        prompt_data = {
            "type": "prompt",
            "conversationId": "CONV_CANCEL_TEST",
            "voicePrompt": "Tell me a long story",
        }

        # Get session state
        session_state = session_manager.get_or_create_session("CONV_CANCEL_TEST")

        # Start processing prompt (creates task but doesn't await it)
        await voice_channel._handle_prompt_async("CONV_CANCEL_TEST", prompt_data, session_state)

        # Verify task was created
        assert session_state.stream_task is not None
        assert not session_state.stream_task.done()

        # Give task time to start and stream some chunks
        await asyncio.sleep(0.05)
        assert stream_started, "Stream should have started"

        # Simulate new prompt arriving (should cancel previous task)
        prompt_data2 = {
            "type": "prompt",
            "conversationId": "CONV_CANCEL_TEST",
            "voicePrompt": "Actually, never mind",
        }

        # Manually cancel the old task (simulating what _handle_prompt_async does)
        old_task = session_state.stream_task
        session_state.stream_task.cancel()

        # Wait for cancellation to complete
        try:
            await asyncio.wait_for(old_task, timeout=5.0)
        except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
            pass  # Expected

        # Verify cancellation happened
        assert stream_cancelled, "Stream should have been cancelled"
        assert chunks_sent < 100, f"Should not have sent all chunks (sent {chunks_sent})"
        assert chunks_sent > 0, "Should have sent some chunks before cancellation"

        # Now process new prompt
        await voice_channel._handle_prompt_async("CONV_CANCEL_TEST", prompt_data2, session_state)

        # Verify new task was created
        assert session_state.stream_task is not None
        assert session_state.stream_task != old_task, "Should have created new task"

        # Clean up new task
        if session_state.stream_task and not session_state.stream_task.done():
            session_state.stream_task.cancel()
            try:
                await session_state.stream_task
            except (asyncio.CancelledError, Exception):
                # Ignore exceptions during cleanup to avoid masking earlier test results
                pass

    def test_generate_twiml_minimal(self) -> None:
        """Test TwiML generation with only websocket URL."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        twiml = channel.generate_twiml(TwiMLOptions(websocket_url="wss://example.com/voice"))

        assert '<?xml version="1.0" encoding="UTF-8"?>' in twiml
        assert "<Response>" in twiml
        assert '<ConversationRelay url="wss://example.com/voice" />' in twiml
        assert "</Connect>" in twiml
        assert "</Response>" in twiml
        # Should NOT have greeting or action
        assert "welcomeGreeting" not in twiml
        assert "action=" not in twiml

    def test_generate_twiml_with_welcome_greeting(self) -> None:
        """Test TwiML generation with welcome greeting."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        twiml = channel.generate_twiml(
            TwiMLOptions(
                websocket_url="wss://example.com/voice",
                welcome_greeting="Hello! How can I help you?",
            )
        )

        assert 'welcomeGreeting="Hello! How can I help you?"' in twiml

    def test_generate_twiml_with_action_url(self) -> None:
        """Test TwiML generation with action URL."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        twiml = channel.generate_twiml(
            TwiMLOptions(
                websocket_url="wss://example.com/voice",
                action_url="https://example.com/callback",
            )
        )

        assert '<Connect action="https://example.com/callback">' in twiml

    def test_generate_twiml_with_standard_custom_parameters(self) -> None:
        """Test TwiML generation with standard TAC custom parameters."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        twiml = channel.generate_twiml(
            TwiMLOptions(
                websocket_url="wss://example.com/voice",
                custom_parameters={
                    "conversationId": "CH123",
                    "profileId": "mem_profile_123",
                    "customerParticipantId": "PA_cust",
                    "aiAgentParticipantId": "PA_agent",
                },
            )
        )

        assert '<Parameter name="conversationId" value="CH123" />' in twiml
        assert '<Parameter name="profileId" value="mem_profile_123" />' in twiml
        assert '<Parameter name="customerParticipantId" value="PA_cust" />' in twiml
        assert '<Parameter name="aiAgentParticipantId" value="PA_agent" />' in twiml

    def test_generate_twiml_with_arbitrary_custom_parameters(self) -> None:
        """Test TwiML generation with arbitrary custom parameters."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        twiml = channel.generate_twiml(
            TwiMLOptions(
                websocket_url="wss://example.com/voice",
                custom_parameters={
                    "custom_field_1": "value1",
                    "custom_field_2": "value2",
                    "session_id": "sess_123",
                },
            )
        )

        assert '<Parameter name="custom_field_1" value="value1" />' in twiml
        assert '<Parameter name="custom_field_2" value="value2" />' in twiml
        assert '<Parameter name="session_id" value="sess_123" />' in twiml

    def test_generate_twiml_with_pydantic_model(self) -> None:
        """Test TwiML generation using Pydantic CustomParameters model."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        custom_params = CustomParameters(conversationId="CH123", profileId="mem_profile_123")

        twiml = channel.generate_twiml(
            TwiMLOptions(
                websocket_url="wss://example.com/voice",
                custom_parameters=custom_params,
            )
        )

        # Should use camelCase aliases
        assert '<Parameter name="conversationId" value="CH123" />' in twiml
        assert '<Parameter name="profileId" value="mem_profile_123" />' in twiml

    def test_generate_twiml_with_dict_options(self) -> None:
        """Test TwiML generation accepting plain dict instead of TwiMLOptions."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        twiml = channel.generate_twiml(
            {
                "websocket_url": "wss://example.com/voice",
                "custom_parameters": {"key": "value"},
                "welcome_greeting": "Hi there!",
            }
        )

        assert 'url="wss://example.com/voice"' in twiml
        assert '<Parameter name="key" value="value" />' in twiml
        assert 'welcomeGreeting="Hi there!"' in twiml

    def test_generate_twiml_filters_none_values(self) -> None:
        """Test that None values are excluded from parameters."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        twiml = channel.generate_twiml(
            TwiMLOptions(
                websocket_url="wss://example.com/voice",
                custom_parameters={
                    "field1": "value1",
                    "field2": None,
                    "field3": "value3",
                },
            )
        )

        assert '<Parameter name="field1" value="value1" />' in twiml
        assert "field2" not in twiml  # None should be filtered
        assert '<Parameter name="field3" value="value3" />' in twiml

    def test_generate_twiml_escapes_xml_special_chars(self) -> None:
        """Test XML character escaping in parameter values."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        twiml = channel.generate_twiml(
            TwiMLOptions(
                websocket_url="wss://example.com/voice",
                custom_parameters={
                    "field": 'value with "quotes" & ampersand',
                },
            )
        )

        # Twilio SDK automatically escapes XML special characters
        assert "&amp;" in twiml
        assert "&quot;" in twiml
        # Verify the full escaped parameter is present
        expected_param = (
            '<Parameter name="field" value="value with &quot;quotes&quot; &amp; ampersand" />'
        )
        assert expected_param in twiml

    def test_generate_twiml_complete_example(self) -> None:
        """Test complete TwiML generation with all options."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        twiml = channel.generate_twiml(
            TwiMLOptions(
                websocket_url="wss://example.ngrok.io/voice",
                custom_parameters={
                    "conversationId": "CH_abc123",
                    "profileId": "mem_profile_xyz",
                    "customField": "customValue",
                },
                welcome_greeting="Welcome to our support line!",
                action_url="https://example.com/call-ended",
            )
        )

        # Verify all components present
        assert '<?xml version="1.0" encoding="UTF-8"?>' in twiml
        assert '<Connect action="https://example.com/call-ended">' in twiml
        assert 'url="wss://example.ngrok.io/voice"' in twiml
        assert 'welcomeGreeting="Welcome to our support line!"' in twiml
        assert '<Parameter name="conversationId" value="CH_abc123" />' in twiml
        assert '<Parameter name="profileId" value="mem_profile_xyz" />' in twiml
        assert '<Parameter name="customField" value="customValue" />' in twiml

    @pytest.mark.asyncio
    async def test_handle_incoming_call_with_additional_parameters(self) -> None:
        """Test handle_incoming_call includes additional custom parameters."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Mock conversation creation and participant addition
        with (
            patch.object(
                tac.maestro_client, "create_conversation", new_callable=AsyncMock
            ) as mock_create,
            patch.object(
                tac.maestro_client, "add_participant", new_callable=AsyncMock
            ) as mock_add_participant,
        ):
            mock_create.return_value = ConversationResponse(
                id="CONV999",
                account_id="ACtest123",
                service_id="IStest123",
            )
            mock_add_participant.side_effect = [
                ParticipantResponse(
                    id="PART_CUST",
                    conversation_id="CONV999",
                    account_id="ACtest123",
                    service_id="IStest123",
                    name="customer",
                    profile_id="PROFILE123",
                ),
                ParticipantResponse(
                    id="PART_AGENT",
                    conversation_id="CONV999",
                    account_id="ACtest123",
                    service_id="IStest123",
                    name="agent",
                ),
            ]

            # Generate TwiML with additional parameters
            twiml = await channel.handle_incoming_call(
                to_number="+15551234567",
                from_number="+15559999999",
                options={
                    "websocket_url": "wss://example.ngrok.io/ws",
                    "action_url": "https://example.ngrok.io/callback",
                    "welcome_greeting": "Welcome!",
                    "custom_parameters": {
                        "session_id": "sess_abc123",
                        "user_language": "es",
                        "priority": "high",
                    },
                },
            )

            # Verify standard TAC parameters are present
            assert '<Parameter name="conversationId" value="CONV999" />' in twiml
            assert '<Parameter name="profileId" value="PROFILE123" />' in twiml
            assert '<Parameter name="customerParticipantId" value="PART_CUST" />' in twiml
            assert '<Parameter name="aiAgentParticipantId" value="PART_AGENT" />' in twiml

            # Verify additional custom parameters are present
            assert '<Parameter name="session_id" value="sess_abc123" />' in twiml
            assert '<Parameter name="user_language" value="es" />' in twiml
            assert '<Parameter name="priority" value="high" />' in twiml

    @pytest.mark.asyncio
    async def test_handle_incoming_call_without_additional_parameters(self) -> None:
        """Test handle_incoming_call works without additional parameters (backward compat)."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Mock conversation creation and participant addition
        with (
            patch.object(
                tac.maestro_client, "create_conversation", new_callable=AsyncMock
            ) as mock_create,
            patch.object(
                tac.maestro_client, "add_participant", new_callable=AsyncMock
            ) as mock_add_participant,
        ):
            mock_create.return_value = ConversationResponse(
                id="CONV888",
                account_id="ACtest123",
                service_id="IStest123",
            )
            mock_add_participant.return_value = ParticipantResponse(
                id="PART888",
                conversation_id="CONV888",
                account_id="ACtest123",
                service_id="IStest123",
                name="participant",
            )

            # Generate TwiML without additional parameters
            twiml = await channel.handle_incoming_call(
                to_number="+15551234567",
                from_number="+15559999999",
                options={
                    "websocket_url": "wss://example.ngrok.io/ws",
                },
            )

            # Verify only standard TAC parameters are present
            assert '<Parameter name="conversationId" value="CONV888" />' in twiml
            assert "session_id" not in twiml
            assert "user_language" not in twiml


class TestHandleConversationRelayCallback:
    """Test handle_conversation_relay_callback behavior."""

    @staticmethod
    def _make_payload(**overrides: str) -> dict[str, str]:
        """Create a valid callback payload with optional overrides."""
        base = {
            "AccountSid": "ACtest123",
            "CallSid": "CA123",
            "CallStatus": "completed",
            "From": "+15551234567",
            "To": "+15559876543",
            "Direction": "inbound",
        }
        base.update(overrides)
        return base

    @pytest.mark.asyncio
    async def test_handoff_on_in_progress_with_handoff_data(self) -> None:
        """Test that in-progress call with HandoffData triggers handoff callback."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        handoff_result = "<Response><Enqueue/></Response>"

        async def mock_handoff(form_data: dict) -> str:
            return handoff_result

        tac.on_handoff(mock_handoff)

        payload = self._make_payload(
            CallStatus="in-progress",
            HandoffData='{"reason": "customer request"}',
        )

        result = await channel.handle_conversation_relay_callback(payload)
        assert result == handoff_result

    @pytest.mark.asyncio
    async def test_handoff_passes_original_payload_dict(self) -> None:
        """Test that handoff receives the original payload_dict with all keys."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        captured_data: dict = {}

        async def mock_handoff(form_data: dict) -> str:
            captured_data.update(form_data)
            return "OK"

        tac.on_handoff(mock_handoff)

        payload = self._make_payload(
            CallStatus="in-progress",
            HandoffData='{"reason": "test"}',
            ExtraField="should-be-preserved",
        )

        await channel.handle_conversation_relay_callback(payload)
        assert captured_data["ExtraField"] == "should-be-preserved"

    @pytest.mark.asyncio
    async def test_handoff_raises_without_handler(self) -> None:
        """Test that handoff raises ValueError when no handler is registered."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        payload = self._make_payload(
            CallStatus="in-progress",
            HandoffData='{"reason": "test"}',
        )

        with pytest.raises(ValueError, match="No handoff handler registered"):
            await channel.handle_conversation_relay_callback(payload)

    @pytest.mark.asyncio
    async def test_completed_call_closes_conversations(self) -> None:
        """Test that completed call status closes matching conversations."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        # Add a local session to verify cleanup
        channel._start_conversation("conv123", "profile123")

        mock_conversation = ConversationResponse(
            id="conv123",
            accountId="ACtest123",
            configuration_id="IStest123",
            status="ACTIVE",
        )
        tac.maestro_client.list_conversations = AsyncMock(return_value=[mock_conversation])
        tac.maestro_client.update_conversation = AsyncMock()

        payload = self._make_payload(CallStatus="completed")
        result = await channel.handle_conversation_relay_callback(payload)

        assert result is None
        tac.maestro_client.list_conversations.assert_called_once_with(
            channel_id="CA123", status=["ACTIVE", "INACTIVE"]
        )
        tac.maestro_client.update_conversation.assert_called_once_with(
            conversation_id="conv123", status="CLOSED"
        )
        assert "conv123" not in channel._conversations

    @pytest.mark.asyncio
    async def test_completed_call_skips_other_configurations(self) -> None:
        """Test that conversations from other configurations are not closed."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        mock_conversation = ConversationResponse(
            id="conv456",
            accountId="ACtest123",
            configuration_id="ISother999",
            status="ACTIVE",
        )
        tac.maestro_client.list_conversations = AsyncMock(return_value=[mock_conversation])
        tac.maestro_client.update_conversation = AsyncMock()

        payload = self._make_payload(CallStatus="completed")
        result = await channel.handle_conversation_relay_callback(payload)

        assert result is None
        tac.maestro_client.update_conversation.assert_not_called()

    @pytest.mark.asyncio
    async def test_other_status_returns_none(self) -> None:
        """Test that non-handoff, non-completed status returns None."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        payload = self._make_payload(CallStatus="ringing")
        result = await channel.handle_conversation_relay_callback(payload)

        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_payload_raises_validation_error(self) -> None:
        """Test that invalid payload raises ValidationError."""
        from pydantic import ValidationError

        tac = TAC(get_test_config())
        channel = VoiceChannel(tac)

        with pytest.raises(ValidationError):
            await channel.handle_conversation_relay_callback({})
