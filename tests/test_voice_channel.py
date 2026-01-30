"""Tests for Voice Channel."""

from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tac import TAC
from tac.channels.voice import VoiceChannel
from tac.models.conversation import ConversationResponse, ParticipantResponse
from tac.models.memory import MemoryRetrievalResponse
from tac.models.session import ConversationSession
from tac.models.voice import InterruptMessage, PromptMessage, SetupMessage


def get_test_config() -> dict:
    """Get a valid test configuration."""
    return {
        "twilio_auth_token": "test_token_123",
        "environment": "prod",
        "conversation_service_sid": "IStest123",
        "twilio_account_sid": "ACtest123",
        "twilio_phone_number": "+15551234567",
    }


class TestVoiceChannel:
    """Test Voice Channel functionality."""

    def test_initialization(self) -> None:
        """Test Voice channel initialization."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

        assert channel.tac == tac
        assert channel._websocket_manager is not None
        assert len(channel._websocket_manager) == 0

    def test_get_channel_name(self) -> None:
        """Test get_channel_name returns 'voice'."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

        assert channel.get_channel_name() == "voice"

    @pytest.mark.asyncio
    async def test_handle_setup_message(self) -> None:
        """Test handling setup message initializes conversation."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

        # Create setup message
        setup_msg = SetupMessage(
            type="setup",
            conversationId="CALL123",
            customParameters={"conversationId": "CALL123"},
        )

        # Call handler directly
        await channel._handle_setup(setup_msg)

        # Verify conversation was started
        assert "CALL123" in channel._conversations
        assert channel._conversations["CALL123"].profile_id is None
        assert channel._conversations["CALL123"].channel == "voice"

    @pytest.mark.asyncio
    async def test_handle_prompt_message_without_memory_retrieval(self) -> None:
        """Test handling prompt message when auto_retrieve_memory=False."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

        # Setup conversation first
        await channel._start_conversation("CALL123", "profile_test_123")

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
        config["twilio_memory_config"] = {
            "memory_store_id": "MGtest123",
            "api_key": "test_api_key",
            "api_token": "test_api_token",
        }
        tac = TAC(config)

        # Mock the memory retrieval
        mock_memory_response = MemoryRetrievalResponse(
            observations=[],
            summaries=[],
            communications=[],
        )
        tac.memora_client.retrieve_memory = AsyncMock(return_value=mock_memory_response)

        # Create channel with auto_retrieve_memory=True (default)
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=True)

        # Setup conversation with profile_id
        await channel._start_conversation("CALL123", "profile_test_123")

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
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

        # Setup conversation first
        await channel._start_conversation("CALL123", None)

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
        """Test handling setup message without conversation ID logs error."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

        # Create setup message without conversationId in custom parameters
        setup_msg = SetupMessage(type="setup")

        # Call handler directly
        await channel._handle_setup(setup_msg)

        # No conversation should be created
        assert len(channel._conversations) == 0

    @pytest.mark.asyncio
    async def test_send_response(self) -> None:
        """Test sending voice response through websocket."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

        # Start conversation directly
        await channel._start_conversation("CALL123", "profile_test")

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
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

        # Start conversation directly
        await channel._start_conversation("CALL123", "profile_test")

        # No websocket registered in manager
        # (don't add websocket to manager, so lookup returns None)

        # Should log error and return early (no exception raised)
        await channel.send_response("CALL123", "Hello there")

    @pytest.mark.asyncio
    async def test_end_conversation_cleanup(self) -> None:
        """Test ending conversation cleans up resources."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

        # Start conversation directly
        await channel._start_conversation("CALL123", "profile_test")

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
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

        # Should not raise
        await channel.process_webhook({})

    @pytest.mark.asyncio
    async def test_message_callback_integration(self) -> None:
        """Test message callback is invoked with conversation context."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

        # Callback to capture context
        captured_context = None
        captured_memories = None
        captured_user_message = None

        async def message_callback(
            user_message: str,
            context: ConversationSession,
            memory_response: Optional[MemoryRetrievalResponse],
        ) -> None:
            nonlocal captured_context, captured_memories, captured_user_message
            captured_context = context
            captured_memories = memory_response
            captured_user_message = user_message

        tac.on_message_ready(message_callback)

        # Setup conversation first
        await channel._start_conversation("CALL123", "profile_test")

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
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

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
                websocket_url="wss://example.ngrok.io/ws",
                to_number="+15551234567",
                from_number="+15559999999",
                action_url="https://example.ngrok.io/flex_handoff",
                welcome_greeting="Welcome!",
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
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

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

            # Generate TwiML without custom greeting
            twiml = await channel.handle_incoming_call(
                websocket_url="wss://test.ngrok.io/ws",
                to_number="+15551111111",
                from_number="+15559876543",
                action_url="https://example.ngrok.io/flex_handoff",
            )

            # Verify default greeting is used
            assert 'welcomeGreeting="Hello! How can I assist you today?"' in twiml

    @pytest.mark.asyncio
    async def test_setup_with_custom_parameters_profile_id(self) -> None:
        """Test setup message extracts profile_id from custom parameters."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

        # Create setup message with profile_id
        setup_msg = SetupMessage(
            type="setup",
            conversationId="CONV123",
            customParameters={"conversationId": "CONV123", "profileId": "USER_PROFILE_789"},
        )

        # Call handler directly
        await channel._handle_setup(setup_msg)

        # Verify conversation was started with correct profile_id
        assert "CONV123" in channel._conversations
        assert channel._conversations["CONV123"].profile_id == "USER_PROFILE_789"

    @pytest.mark.asyncio
    async def test_setup_without_conversation_id_raises_error(self) -> None:
        """Test setup message logs error when conversationId missing from custom parameters."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

        # Create setup message without conversationId in custom parameters
        setup_msg = SetupMessage(type="setup")

        # Call handler directly
        await channel._handle_setup(setup_msg)

        # Verify conversation was NOT started
        assert len(channel._conversations) == 0

    @pytest.mark.asyncio
    async def test_prompt_with_empty_voice_prompt(self) -> None:
        """Test handling prompt message with empty voice_prompt."""
        tac = TAC(get_test_config())
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

        # Setup conversation first
        await channel._start_conversation("CALL111", "profile_test")

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
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

        # Start three concurrent conversations
        await channel._start_conversation("CALL_001", "profile_001")
        await channel._start_conversation("CALL_002", "profile_002")
        await channel._start_conversation("CALL_003", "profile_003")

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
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

        # Start three conversations
        await channel._start_conversation("CALL_A", "profile_A")
        await channel._start_conversation("CALL_B", "profile_B")
        await channel._start_conversation("CALL_C", "profile_C")

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
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

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
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

        # Setup two conversations
        await channel._start_conversation("CONV_X", "profile_X")
        await channel._start_conversation("CONV_Y", "profile_Y")

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
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

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
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

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
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

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

        # Call handler directly
        await channel._handle_setup(setup_msg)

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
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

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

        # Call handler directly
        await channel._handle_setup(setup_msg)

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
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

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
    async def test_create_communication_without_participant_ids(self) -> None:
        """Test _create_communication without participant IDs (optional parameters)."""
        config = get_test_config()
        config["enable_voice_active_hydration"] = True
        tac = TAC(config)
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

        # Mock the maestro client's create_communication method
        with patch.object(
            tac.maestro_client, "create_communication", new_callable=AsyncMock
        ) as mock_add_comm:
            # Call _create_communication without participant IDs
            await channel._create_communication(
                conversation_id="CONV456",
                message_content="Test message",
                author_address="+15551111111",
                recipient_address="+15552222222",
            )

            # Verify create_communication was called
            assert mock_add_comm.call_count == 1

            # Verify the request structure
            call_args = mock_add_comm.call_args
            assert call_args[0][0] == "CONV456"
            comm_request = call_args[0][1]
            assert comm_request.author.address == "+15551111111"
            assert comm_request.author.participant_id is None  # Should be None
            assert comm_request.content.text == "Test message"
            assert len(comm_request.recipients) == 1
            assert comm_request.recipients[0].address == "+15552222222"
            assert comm_request.recipients[0].participant_id is None  # Should be None

    @pytest.mark.asyncio
    async def test_send_response_with_active_hydration(self) -> None:
        """Test send_response triggers _create_communication when active hydration is enabled."""
        config = get_test_config()
        config["enable_voice_active_hydration"] = True
        tac = TAC(config)
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

        # Start conversation
        await channel._start_conversation("CALL789", "profile_test")

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
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

        # Start conversation
        await channel._start_conversation("CALL999", "profile_test")

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
        channel = VoiceChannel(tac=tac, auto_retrieve_memory=False)

        # Start conversation without setting author/AI agent info
        await channel._start_conversation("CALL_NO_INFO", "profile_test")

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
