import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

from tac.channels.base import BaseChannel
from tac.channels.websocket_manager import WebSocketManager
from tac.channels.websocket_protocol import WebSocketDisconnectError, WebSocketProtocol
from tac.core.tac import TAC
from tac.models.voice import (
    ConversationRelayCallbackPayload,
    InterruptMessage,
    PromptMessage,
    SetupMessage,
    TwiMLOptions,
)
from tac.session import SessionState

from . import twiml
from .config import VoiceChannelConfig


class VoiceChannel(BaseChannel):
    """
    Voice Channel for handling voice-based conversations via WebSocket.

    Key features:
    - TwiML generation for incoming calls (see twiml module)
    - WebSocket connection management for real-time voice streaming
    - Conversation lifecycle management (inherited from BaseChannel)
    - ConversationRelay callback webhook handling

    This channel is framework-agnostic and accepts any WebSocket implementation
    satisfying WebSocketProtocol. For a batteries-included FastAPI server, use
    tac.server.TACFastAPIServer.
    """

    def __init__(
        self,
        tac: TAC,
        config: VoiceChannelConfig | dict[str, Any] | None = None,
    ):
        """
        Initialize Voice channel for websocket protocol handling.

        Args:
            tac: TAC instance for memory/context operations
            config: Voice channel configuration (VoiceChannelConfig or dict).
                If None, uses default configuration.

        Examples:
            >>> channel = VoiceChannel(tac, config={"auto_retrieve_memory": True})
            >>> channel = VoiceChannel(tac, config=VoiceChannelConfig(session_manager=sm))
            >>> channel = VoiceChannel(tac)  # Use defaults
        """
        # Convert dict to config model or use defaults
        if isinstance(config, dict):
            config = VoiceChannelConfig(**config)
        elif config is None:
            config = VoiceChannelConfig()

        super().__init__(tac, auto_retrieve_memory=config.auto_retrieve_memory)
        self.session_manager = config.session_manager
        self._websocket_manager = WebSocketManager()

    async def handle_incoming_call(
        self,
        options: TwiMLOptions | dict[str, Any],
    ) -> str:
        """
        Generate TwiML response for incoming voice calls.

        ConversationRelay automatically handles conversation creation and participant
        management via the conversation_configuration parameter.

        Args:
            options: TwiML generation options (TwiMLOptions or dict) containing:
                - websocket_url (required): WebSocket URL for ConversationRelay
                - custom_parameters (optional): Additional custom parameters
                - welcome_greeting (optional): Initial greeting message
                - action_url (optional): URL for call completion webhook

        Returns:
            TwiML XML string for call connection

        Example:
            >>> twiml = await voice_channel.handle_incoming_call(
            ...     options={
            ...         "websocket_url": "wss://example.com/ws",
            ...         "custom_parameters": {"session_id": "sess_123"},
            ...         "welcome_greeting": "Hello!",
            ...         "action_url": "https://example.com/callback",
            ...     },
            ... )
        """
        # Handle dict input (convert to TwiMLOptions)
        if isinstance(options, dict):
            options = TwiMLOptions(**options)

        # Set default welcome greeting if not provided
        if options.welcome_greeting is None:
            options.welcome_greeting = "Hello! How can I assist you today?"

        # ConversationRelay automatically creates conversation and participants
        return twiml.generate_twiml(
            TwiMLOptions(
                websocket_url=options.websocket_url,
                custom_parameters=options.custom_parameters,
                welcome_greeting=options.welcome_greeting,
                action_url=options.action_url,
                conversation_configuration=self.tac.config.conversation_service_sid,
            )
        )

    async def handle_handoff(self, form_data: dict[str, str]) -> str:
        """
        Generic handler for handoff webhook. Delegates to registered TAC handoff callback.

        Args:
            form_data: Dict of form data from the request.

        Returns:
            TwiML/content string from the handoff callback.

        Raises:
            ValueError: If no handoff handler is registered.
        """
        self.logger.info("Handling handoff webhook (delegated)")
        cb = self.tac._handoff_callback
        if cb is None:
            raise ValueError("No handoff handler registered")
        return await cb(form_data)

    async def handle_conversation_relay_callback(
        self,
        payload_dict: dict[str, str],
    ) -> str | None:
        """
        Handle ConversationRelay callback webhook from Twilio.

        This method processes the callback sent by Twilio when a ConversationRelay
        session ends, and closes associated conversations if the call status is "completed".

        Args:
            payload_dict: Raw form data dict from the webhook request.
                Validated internally into ConversationRelayCallbackPayload.

        Returns:
            Content string for handoff responses, or None for simple acknowledgment.

        Raises:
            ValidationError: If the payload dict fails validation.
            ValueError: If handoff is triggered but no handler is registered.
        """
        payload = ConversationRelayCallbackPayload(**payload_dict)

        self.logger.info(
            f"[ConversationRelay Callback] CallSid: {payload.call_sid}, "
            f"Status: {payload.call_status}"
        )

        if payload.call_status == "in-progress" and payload.handoff_data:
            return await self.handle_handoff(payload_dict)

        # If call is completed, close associated conversations
        if payload.call_status == "completed":
            conversations = await self.tac.maestro_client.list_conversations(
                channel_id=payload.call_sid, status=["ACTIVE", "INACTIVE"]
            )

            self.logger.debug(
                f"\n{'=' * 80}\nCALL ENDED | Closing {len(conversations)} conversation(s)",
                call_sid=payload.call_sid,
            )

            # Close each conversation
            for conversation in conversations:
                try:
                    # Only handle conversations from our configuration
                    if conversation.configuration_id != self.tac.config.conversation_service_sid:
                        continue

                    await self.tac.maestro_client.update_conversation(
                        conversation_id=conversation.id, status="CLOSED"
                    )

                    # Clean up local session if it exists and is a voice channel
                    if (
                        conversation.id in self._conversations
                        and self._conversations[conversation.id].channel == "voice"
                    ):
                        await self._end_conversation(conversation.id)

                    self.logger.debug(
                        "Closed conversation",
                        conversation_id=conversation.id,
                        call_sid=payload.call_sid,
                    )
                except Exception as e:
                    self.logger.error(
                        f"Failed to close conversation {conversation.id}: {e}",
                        exc_info=True,
                    )

        return None

    async def handle_websocket(self, websocket: WebSocketProtocol) -> None:
        """
        Handle voice streaming WebSocket connection lifecycle.

        This method manages the entire websocket connection:
        - Accepts the connection
        - Processes incoming messages
        - Tracks and cancels in-flight tasks (if session_manager provided)
        - Cleans up on disconnect

        Args:
            websocket: Any WebSocket implementation satisfying WebSocketProtocol
        """
        await websocket.accept()
        self.logger.debug("WebSocket connection established")

        conv_id: str | None = None
        session_state = None

        try:
            # First message should be 'setup'
            data = await websocket.receive_json()
            if data.get("type") == "setup":
                setup_msg = SetupMessage(**data)
                call_sid = setup_msg.call_sid
                from_number = setup_msg.from_number

                # Don't initialize conversation yet - wait for first prompt
                # when ConversationRelay has created the conversation

                # Process all subsequent messages
                while True:
                    data = await websocket.receive_json()
                    msg_type = data.get("type")

                    if msg_type == "prompt":
                        # First prompt? Initialize conversation from ConversationRelay
                        if not conv_id and call_sid:
                            conversations = await self.tac.maestro_client.list_conversations(
                                channel_id=call_sid,
                                status=["ACTIVE"],
                            )

                            if len(conversations) != 1:
                                raise RuntimeError(
                                    f"Expected exactly 1 conversation for call_sid {call_sid}, "
                                    f"but found {len(conversations)}. "
                                    "ConversationRelay should have created exactly one."
                                )

                            conversation = conversations[0]
                            conv_id = conversation.id

                            # Get profile_id from participants
                            participants = await self.tac.maestro_client.list_participants(conv_id)
                            profile_id = None
                            for participant in participants:
                                if from_number and participant.addresses:
                                    for address in participant.addresses:
                                        if (
                                            address.channel == "VOICE"
                                            and address.address == from_number
                                            and participant.profile_id
                                        ):
                                            profile_id = participant.profile_id
                                            break
                                if profile_id:
                                    break

                            self._websocket_manager.add_websocket(conv_id, websocket)
                            self._start_conversation(conv_id, profile_id)

                            if self.session_manager is not None:
                                session_state = self.session_manager.get_or_create_session(conv_id)

                        if conv_id:
                            await self._handle_prompt_async(conv_id, data, session_state)
                        else:
                            self.logger.warning("Received prompt before conversation initialized")
                    elif msg_type == "interrupt":
                        if conv_id:
                            await self._handle_interrupt_async(conv_id, data, session_state)
                        else:
                            self.logger.warning(
                                "Received interrupt before conversation initialized"
                            )
                    else:
                        self.logger.debug(f"Skip message type received: {msg_type}")
            else:
                self.logger.warning("First message was not 'setup'. Closing connection.")
                await websocket.close()
                return
        except WebSocketDisconnectError:
            self.logger.info("WebSocket connection closed", conversation_id=conv_id)
        except Exception as e:
            self.logger.error(f"WebSocket error: {str(e)}")
        finally:
            if conv_id:
                self.logger.debug("Cleanup - removing WebSocket", conversation_id=conv_id)
                await self._cleanup_connection(conv_id)

    async def _handle_prompt_async(
        self,
        conv_id: str,
        data: dict[str, Any],
        session_state: SessionState | None,
    ) -> None:
        """
        Handle prompt message asynchronously with task tracking.

        Args:
            conv_id: Conversation ID
            data: Raw message data
            session_state: Session state object (if session_manager provided)
        """
        try:
            should_process = data.get("final", True)
            if should_process:
                prompt_msg = PromptMessage(**data)
                conv_id = prompt_msg.conversation_id or conv_id

                # Cancel previous stream task if session manager is enabled
                if session_state:
                    await session_state.cancel_stream_task()

                    # Create new task using unified flow (memory retrieval + callback)
                    session_state.stream_task = asyncio.create_task(
                        self._handle_prompt(conv_id, prompt_msg)
                    )
                else:
                    await self._handle_prompt(conv_id, prompt_msg)
        except Exception as e:
            self.logger.error(f"Failed to handle prompt: {str(e)}")

    async def _handle_interrupt_async(
        self,
        conv_id: str,
        data: dict[str, Any],
        session_state: SessionState | None,
    ) -> None:
        """
        Handle interrupt message asynchronously with task cancellation.

        Args:
            conv_id: Conversation ID
            data: Raw message data
            session_state: Session state object (if session_manager provided)
        """
        try:
            interrupt_msg = InterruptMessage(**data)
            conv_id = interrupt_msg.conversation_id or conv_id

            # Cancel in-flight stream task if session manager is enabled
            if session_state:
                await session_state.cancel_stream_task()

                # Send acknowledgment to Twilio after cancelling
                websocket = self._websocket_manager.get_websocket(conv_id)
                if websocket:
                    try:
                        await websocket.send_text(
                            json.dumps({"type": "text", "token": "", "last": True})
                        )
                    except (WebSocketDisconnectError, RuntimeError):
                        self.logger.debug(
                            f"WebSocket closed before sending interrupt acknowledgment "
                            f"for {conv_id}."
                        )

            # Call the interrupt handler
            self._handle_interrupt(conv_id, interrupt_msg)
        except Exception as e:
            self.logger.error(f"Failed to handle interrupt: {str(e)}")

    # todo: voice does not support webhooks yet
    async def process_webhook(self, webhook_data: dict[str, Any]) -> None:
        pass

    async def send_response(
        self,
        conversation_id: str,
        response: str | AsyncGenerator[str | dict[str, Any], None],
        role: str | None = None,
    ) -> None:
        """
        Send voice response through the websocket connection for this conversation.

        Supports both simple string responses and streaming async generators.

        Args:
            conversation_id: Conversation ID
            response: Response text (string) or async generator for streaming
            role: Optional message role (not used in this implementation, but kept
                  for API consistency with BaseChannel interface)
        """
        # Validate response type before processing
        if not isinstance(response, (str, AsyncGenerator)):
            raise TypeError("Voice channel requires string or async generator for response")

        # Get WebSocket from manager
        websocket = self._websocket_manager.get_websocket(conversation_id)
        if not websocket:
            self.logger.error("No websocket connection", conversation_id=conversation_id)
            return

        full_response = ""

        try:
            # Check if response is an async generator (streaming)
            if isinstance(response, AsyncGenerator):
                # Streaming response
                json_template = {"type": "text", "token": "", "last": False}
                closed = False
                response_gen: AsyncGenerator[str | dict[str, Any], None] = response

                try:
                    async for chunk in response_gen:
                        # Handle different chunk types (plain text or dict with metadata)
                        if isinstance(chunk, dict):
                            if "output" in chunk:
                                token = chunk["output"]
                            else:
                                token = str(chunk)
                        else:
                            token = chunk

                        full_response += token
                        json_template["token"] = token

                        try:
                            await websocket.send_text(json.dumps(json_template))
                        except (WebSocketDisconnectError, RuntimeError):
                            self.logger.info(
                                "WebSocket closed during streaming",
                                conversation_id=conversation_id,
                            )
                            closed = True
                            break

                    # Send final message marker
                    if not closed:
                        try:
                            await websocket.send_text(
                                json.dumps({"type": "text", "token": "", "last": True})
                            )
                        except (WebSocketDisconnectError, RuntimeError):
                            self.logger.info(
                                "WebSocket closed before sending final marker",
                                conversation_id=conversation_id,
                            )
                except asyncio.CancelledError:
                    # Let Python's async generator cleanup handle closing the generator
                    raise
            else:
                await websocket.send_text(
                    json.dumps({"type": "text", "token": response, "last": True})
                )

        except asyncio.CancelledError:
            # Re-raise to propagate cancellation up the call stack.
            # Note: Partial responses from interrupted streams are NOT saved to Maestro.
            # This is intentional - incomplete responses shouldn't be part of conversation history.
            raise
        except (WebSocketDisconnectError, RuntimeError):
            self.logger.info(
                "WebSocket closed before sending response", conversation_id=conversation_id
            )
        except Exception as e:
            self.logger.error(
                f"Error sending response: {e}", conversation_id=conversation_id, exc_info=True
            )

    def get_channel_name(self) -> str:
        return "voice"

    def get_websocket(self, conversation_id: str) -> WebSocketProtocol | None:
        """
        Get the WebSocket connection for a specific conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            WebSocket connection if exists, None otherwise
        """
        return self._websocket_manager.get_websocket(conversation_id)

    async def _handle_prompt(self, conv_id: str, message: PromptMessage) -> None:
        """
        Handle incoming voice prompt (user speech).

        Args:
            conv_id: Conversation ID
            message: Parsed PromptMessage containing user's transcribed speech
        """
        if conv_id not in self._conversations:
            self.logger.error(
                f"Received prompt for unknown conversation {conv_id}. "
                "Conversation should be initialized on first prompt.",
                conversation_id=conv_id,
            )
            return

        message_body = message.voice_prompt or ""
        session = self._conversations[conv_id]

        # Retrieve memory if auto_retrieve_memory is enabled and Twilio Memory is configured
        memory_response = await self._retrieve_memory_if_enabled(session, message_body, conv_id)

        # Trigger message ready callback
        try:
            await self.tac.trigger_message_ready(message_body, session, memory_response)
        except Exception as e:
            self.logger.error(
                "Error in message ready callback",
                conversation_id=conv_id,
                error=str(e),
                exc_info=True,
            )

    def _handle_interrupt(self, conv_id: str, message: InterruptMessage) -> None:
        """
        Handle interrupt message when user interrupts the agent.

        Note: Task cancellation is handled by the async wrapper (_handle_interrupt_async)
        when called from the WebSocket message handler. This method only triggers the
        TAC interrupt callback.

        Args:
            conv_id: Conversation ID
            message: Parsed InterruptMessage with interruption details
        """
        # Trigger interrupt callback if conversation exists
        if conv_id in self._conversations:
            session = self._conversations[conv_id]
            self.tac.trigger_interrupt(session, message)
        else:
            self.logger.warning(
                f"Received interrupt for unknown conversation {conv_id}, skipping callback"
            )

    async def _cleanup_connection(self, conv_id: str) -> None:
        """
        Clean up all resources for a conversation (WebSocket, session, conversation state).

        Args:
            conv_id: Conversation ID
        """
        # Remove WebSocket from manager
        if self._websocket_manager.has_websocket(conv_id):
            self._websocket_manager.remove_websocket(conv_id)

        # Cancel any running stream task and cleanup session if session manager is enabled
        if self.session_manager is not None and self.session_manager.has_session(conv_id):
            session_state = self.session_manager.get_or_create_session(conv_id)
            await session_state.cancel_stream_task()
            self.session_manager.remove_session(conv_id)

        # Clean up conversation state from BaseChannel
        await self._end_conversation(conv_id)
