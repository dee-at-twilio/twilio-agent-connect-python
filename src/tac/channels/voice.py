import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any, Optional, Union

from pydantic import BaseModel, Field
from twilio.twiml.voice_response import VoiceResponse

from tac.channels.base import BaseChannel
from tac.channels.websocket_manager import WebSocketManager
from tac.channels.websocket_protocol import WebSocketDisconnectError, WebSocketProtocol
from tac.core.tac import TAC
from tac.models.conversation import (
    CommunicationContent,
    CommunicationParticipant,
    CommunicationRequest,
    ParticipantAddress,
)
from tac.models.session import AuthorInfo
from tac.models.voice import (
    ConversationRelayCallbackPayload,
    InterruptMessage,
    PromptMessage,
    SetupMessage,
    TwiMLOptions,
)
from tac.session import SessionManager, SessionState


class VoiceChannelConfig(BaseModel):
    """
    Configuration for Voice channel.

    Attributes:
        session_manager: Optional SessionManager for tracking and
            canceling in-flight streaming tasks. The SessionManager
            encapsulates the stream_generator for LLM responses.
            If provided, enables task cancellation on interrupts
            and new prompts.
        auto_retrieve_memory: If True, automatically retrieve memory
            before invoking the on_message_ready callback. Default is False.
            Set to True to enable automatic memory retrieval.
    """

    model_config = {"arbitrary_types_allowed": True}

    session_manager: Optional[SessionManager] = Field(
        default=None,
        description="SessionManager for tracking and canceling in-flight streaming tasks",
    )
    auto_retrieve_memory: bool = Field(
        default=False,
        description="Automatically retrieve memory before on_message_ready callback",
    )


class VoiceChannel(BaseChannel):
    """
    Voice Channel for handling voice-based conversations.

    Inherits conversation lifecycle management from BaseChannel and provides
    voice-specific metadata extraction.

    This channel is framework-agnostic: it accepts any WebSocket implementation
    satisfying WebSocketProtocol. For a batteries-included FastAPI server, use
    tac.server.TACFastAPIServer.

    Provides two approaches for TwiML generation:

    1. **High-level** (handle_incoming_call): Automatically creates conversations,
       adds participants, and generates TwiML with standard TAC parameters
       (conversationId, profileId, customerParticipantId, aiAgentParticipantId).
       You can also pass additional custom parameters that get merged with the
       standard ones. **Recommended for most use cases.**

    2. **Low-level** (generate_twiml): Generate TwiML with complete control over
       all parameters. Bypasses automatic conversation/participant creation.
       Use ONLY when you manage conversations outside of TAC or need a completely
       custom flow.

    Examples:
        High-level approach (automatic TAC setup + custom params):
            >>> twiml = await voice_channel.handle_incoming_call(
            ...     to_number="+15551234567",
            ...     from_number="+15559876543",
            ...     options={
            ...         "websocket_url": "wss://example.com/ws",
            ...         "custom_parameters": {"session_type": "support", "language": "es"},
            ...         "welcome_greeting": "Hello!",
            ...     },
            ... )

        Low-level approach (manual conversation management):
            >>> twiml = voice_channel.generate_twiml(
            ...     {
            ...         "websocket_url": "wss://example.com/ws",
            ...         "custom_parameters": {
            ...             "conversationId": "CH123",
            ...             "session_id": "custom_session_123",
            ...         },
            ...         "welcome_greeting": "¡Hola!",
            ...     }
            ... )
    """

    def __init__(
        self,
        tac: TAC,
        config: Optional[Union[VoiceChannelConfig, dict[str, Any]]] = None,
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
        to_number: str,
        from_number: str,
        options: Union[TwiMLOptions, dict[str, Any]],
        call_sid: Optional[str] = None,
    ) -> str:
        """
        Generate TwiML response for incoming voice calls.

        This method creates a new conversation, adds participants, and returns TwiML
        that connects the call to a ConversationRelay WebSocket endpoint with standard
        TAC parameters (conversationId, profileId, customerParticipantId,
        aiAgentParticipantId) plus any custom parameters from options.

        Args:
            to_number: Twilio phone number that was called (e.g., '+15551234567')
            from_number: Caller's phone number (e.g., '+15559876543')
            options: TwiML generation options (TwiMLOptions or dict) containing:
                - websocket_url (required): WebSocket URL for ConversationRelay
                - custom_parameters (optional): Additional custom parameters
                - welcome_greeting (optional): Initial greeting message
                - action_url (optional): URL for call completion webhook
            call_sid: Optional Twilio Call SID to associate with participants

        Returns:
            TwiML XML string for call connection

        Example:
            >>> twiml = await voice_channel.handle_incoming_call(
            ...     to_number="+15551234567",
            ...     from_number="+15559876543",
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

        # Create a new conversation for each call
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conversation_name = f"tac-voice-{from_number}-{timestamp}"
        conversation = await self.tac.maestro_client.create_conversation(name=conversation_name)
        conversation_id = conversation.id

        self.logger.debug(
            f"[Voice Channel] Created conversation {conversation_id} for CallSid: {call_sid}"
        )

        # Add participant with the caller's phone number
        participant_response = await self.tac.maestro_client.add_participant(
            conversation_id=conversation_id,
            addresses=[
                ParticipantAddress(channel="VOICE", address=from_number, channelId=call_sid)
            ],
            participant_type="CUSTOMER",
        )
        profile_id = participant_response.profile_id if participant_response else ""
        customer_participant_id = participant_response.id if participant_response else ""

        ai_agent_participant_response = await self.tac.maestro_client.add_participant(
            conversation_id=conversation_id,
            addresses=[ParticipantAddress(channel="VOICE", address=to_number, channelId=call_sid)],
            participant_type="AI_AGENT",
        )
        ai_agent_participant_id = (
            ai_agent_participant_response.id if ai_agent_participant_response else ""
        )

        self.logger.debug(
            f"[Voice Channel] Added participants - "
            f"customer_id={customer_participant_id}, ai_agent_id={ai_agent_participant_id}, "
            f"profile_id={profile_id}"
        )

        # Build standard TAC custom parameters
        tac_params: dict[str, Any] = {
            "conversationId": conversation_id,
            "profileId": profile_id,
            "customerParticipantId": customer_participant_id,
            "aiAgentParticipantId": ai_agent_participant_id,
        }

        # Merge with any custom parameters from options
        if options.custom_parameters:
            # Handle both Pydantic model and dict
            user_params = (
                options.custom_parameters.model_dump(by_alias=True, exclude_none=True)
                if isinstance(options.custom_parameters, BaseModel)
                else options.custom_parameters
            )
            tac_params.update(user_params)

        # Use generate_twiml for consistent TwiML generation
        return self.generate_twiml(
            TwiMLOptions(
                websocket_url=options.websocket_url,
                custom_parameters=tac_params,
                welcome_greeting=options.welcome_greeting,
                action_url=options.action_url,
            )
        )

    def generate_twiml(
        self,
        options: Union[TwiMLOptions, dict[str, Any]],
    ) -> str:
        """
        Generate TwiML XML for ConversationRelay with custom parameters.

        This is a low-level method for generating TwiML with arbitrary custom
        parameters. For automatic conversation creation and participant management,
        use handle_incoming_call() instead.

        Args:
            options: TwiML generation options (TwiMLOptions model or dict with:
                - websocket_url (required): WebSocket URL for ConversationRelay
                - custom_parameters (optional): Dict of custom parameters
                - welcome_greeting (optional): Initial greeting message
                - action_url (optional): URL for call end webhook

        Returns:
            TwiML XML string ready to return to Twilio

        Example:
            >>> twiml = voice_channel.generate_twiml(
            ...     {
            ...         "websocket_url": "wss://example.com/voice",
            ...         "custom_parameters": {
            ...             "conversation_id": "CH123",
            ...             "custom_field": "custom_value",
            ...         },
            ...         "welcome_greeting": "Hello!",
            ...     }
            ... )
        """
        # Handle dict input (convert to TwiMLOptions)
        if isinstance(options, dict):
            options = TwiMLOptions(**options)

        websocket_url = options.websocket_url
        custom_parameters = options.custom_parameters
        welcome_greeting = options.welcome_greeting
        action_url = options.action_url

        # Create VoiceResponse
        response = VoiceResponse()

        # Create Connect verb with optional action
        connect_kwargs: dict[str, str] = {}
        if action_url:
            connect_kwargs["action"] = action_url
        connect = response.connect(**connect_kwargs)

        # Build ConversationRelay kwargs
        relay_kwargs: dict[str, str] = {"url": websocket_url}
        if welcome_greeting:
            relay_kwargs["welcome_greeting"] = welcome_greeting

        # Create ConversationRelay
        relay = connect.conversation_relay(**relay_kwargs)

        # Add custom parameters
        if custom_parameters:
            # Handle both Pydantic model and dict
            params_dict: dict[str, Any] = (
                custom_parameters.model_dump(by_alias=True, exclude_none=True)
                if isinstance(custom_parameters, BaseModel)
                else custom_parameters
            )

            # Add each parameter as a child element
            for name, value in params_dict.items():
                if value is not None:
                    relay.parameter(name=name, value=str(value))

        return str(response)

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
    ) -> Optional[str]:
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

        conv_id: Optional[str] = None
        session_state = None
        handler_task = None

        try:
            # First message should be 'setup'
            data = await websocket.receive_json()
            if data.get("type") == "setup":
                setup_msg = SetupMessage(**data)
                conv_id = setup_msg.custom_parameters.conversation_id

                # Store WebSocket in manager BEFORE calling _handle_setup
                self._websocket_manager.add_websocket(conv_id, websocket)

                # Handle setup to initialize conversation
                self._handle_setup(setup_msg)

                # Get or create session state if session manager is available
                if self.session_manager is not None:
                    session_state = self.session_manager.get_or_create_session(conv_id)

                # Create dedicated task to handle all subsequent messages
                handler_task = asyncio.create_task(
                    self._message_handler(websocket, conv_id, session_state)
                )
                await handler_task
            else:
                self.logger.warning("First message was not 'setup'. Closing connection.")
                await websocket.close()
                return
        except WebSocketDisconnectError:
            self.logger.info("WebSocket connection closed", conversation_id=conv_id)
        except Exception as e:
            self.logger.error(f"WebSocket error: {str(e)}")
        finally:
            # Cancel handler task if still running
            if handler_task and not handler_task.done():
                handler_task.cancel()
                try:
                    await handler_task
                except asyncio.CancelledError:
                    pass

            # Clean up conversation and websocket
            if conv_id:
                self.logger.debug("Cleanup - removing WebSocket", conversation_id=conv_id)
                await self._cleanup_connection(conv_id)

    async def _message_handler(
        self,
        websocket: WebSocketProtocol,
        conv_id: str,
        session_state: Optional[SessionState],
    ) -> None:
        """
        Handle all incoming messages for a conversation session.

        Args:
            websocket: WebSocket connection
            conv_id: Conversation ID
            session_state: Session state object (if session_manager provided)
        """
        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type")

                if msg_type == "prompt":
                    await self._handle_prompt_async(conv_id, data, session_state)
                elif msg_type == "interrupt":
                    await self._handle_interrupt_async(conv_id, data, session_state)
                else:
                    self.logger.debug(f"Skip message type received: {msg_type}")
        except WebSocketDisconnectError:
            self.logger.debug(
                f"WebSocket disconnected during message handling for conversation {conv_id}"
            )
        except Exception as e:
            self.logger.error(
                f"Error in message_handler for conversation {conv_id}: {e}", exc_info=True
            )

    async def _handle_prompt_async(
        self,
        conv_id: str,
        data: dict[str, Any],
        session_state: Optional[SessionState],
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
        session_state: Optional[SessionState],
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
        response: Union[str, AsyncGenerator[Union[str, dict[str, Any]], None]],
        role: Optional[str] = None,
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
                response_gen: AsyncGenerator[Union[str, dict[str, Any]], None] = response

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
                # Simple string response
                full_response = response
                await websocket.send_text(
                    json.dumps({"type": "text", "token": response, "last": True})
                )

            # If active hydration is enabled, send agent response to Maestro
            # Check all required fields are available before creating communication
            if (
                self.tac.config.enable_voice_active_hydration
                and conversation_id in self._conversations
            ):
                session = self._conversations[conversation_id]

                if (
                    session.author_info
                    and session.ai_agent_info
                    and session.ai_agent_info.address
                    and session.ai_agent_info.participant_id
                    and session.author_info.address
                    and session.author_info.participant_id
                ):
                    # Agent is author, customer is recipient
                    await self._create_communication(
                        conversation_id=conversation_id,
                        message_content=full_response,
                        author_address=session.ai_agent_info.address,
                        recipient_address=session.author_info.address,
                        author_participant_id=session.ai_agent_info.participant_id,
                        recipient_participant_id=session.author_info.participant_id,
                    )
                else:
                    self.logger.warning(
                        "[Active Hydration] Skipping communication - missing required fields",
                        conversation_id=conversation_id,
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

    def get_websocket(self, conversation_id: str) -> Optional[WebSocketProtocol]:
        """
        Get the WebSocket connection for a specific conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            WebSocket connection if exists, None otherwise
        """
        return self._websocket_manager.get_websocket(conversation_id)

    def _handle_setup(self, message: SetupMessage) -> None:
        """
        Handle WebSocket setup message.

        Args:
            message: Parsed SetupMessage containing call metadata
        """
        conversation_id = message.custom_parameters.conversation_id
        profile_id = message.custom_parameters.profile_id

        self._start_conversation(conversation_id, profile_id)

        # If active hydration is enabled, populate author_info and ai_agent_info
        if self.tac.config.enable_voice_active_hydration:
            if message.from_number:
                self._conversations[conversation_id].author_info = AuthorInfo(
                    address=message.from_number,
                    participant_id=message.custom_parameters.customer_participant_id,
                )
            if message.to_number:
                self._conversations[conversation_id].ai_agent_info = AuthorInfo(
                    address=message.to_number,
                    participant_id=message.custom_parameters.ai_agent_participant_id,
                )

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
                "Conversation should be initialized in setup message first.",
                conversation_id=conv_id,
            )
            return

        message_body = message.voice_prompt or ""
        session = self._conversations[conv_id]

        # If active hydration is enabled, send user message to Maestro
        # Check all required fields are available before creating communication
        if self.tac.config.enable_voice_active_hydration:
            if (
                session.author_info
                and session.ai_agent_info
                and session.author_info.address
                and session.author_info.participant_id
                and session.ai_agent_info.address
                and session.ai_agent_info.participant_id
            ):
                # Customer is author, agent is recipient
                await self._create_communication(
                    conversation_id=conv_id,
                    message_content=message_body,
                    author_address=session.author_info.address,
                    recipient_address=session.ai_agent_info.address,
                    author_participant_id=session.author_info.participant_id,
                    recipient_participant_id=session.ai_agent_info.participant_id,
                )
            else:
                self.logger.warning(
                    "[Active Hydration] Skipping communication - missing required fields",
                    conversation_id=conv_id,
                )

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

    async def _create_communication(
        self,
        conversation_id: str,
        message_content: str,
        author_address: str,
        recipient_address: str,
        author_participant_id: str,
        recipient_participant_id: str,
    ) -> None:
        """
        Add communication to Maestro for active hydration.

        This method creates a communication record in Maestro using the provided participant IDs.
        Callers must ensure participant IDs are available before invoking this method.

        Args:
            conversation_id: Conversation ID
            message_content: Message content
            author_address: Author's address (phone number)
            recipient_address: Recipient's address (phone number)
            author_participant_id: Author's participant ID (required by Maestro API)
            recipient_participant_id: Recipient's participant ID (required by Maestro API)
        """
        try:
            communication_request = CommunicationRequest(
                author=CommunicationParticipant(
                    address=author_address, channel="VOICE", participant_id=author_participant_id
                ),
                content=CommunicationContent(type="TEXT", text=message_content),
                recipients=[
                    CommunicationParticipant(
                        address=recipient_address,
                        channel="VOICE",
                        participant_id=recipient_participant_id,
                    )
                ],
            )

            await self.tac.maestro_client.create_communication(
                conversation_id, communication_request
            )
        except Exception:
            self.logger.error(
                "[Active Hydration] Failed to add communication",
                conversation_id=conversation_id,
                exc_info=True,
            )
