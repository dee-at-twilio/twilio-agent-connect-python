import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

import uvicorn
from fastapi import FastAPI, Form, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.datastructures import FormData

from tac.channels.base import BaseChannel
from tac.channels.websocket_manager import WebSocketManager
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
    VoiceServerConfig,
)

if TYPE_CHECKING:
    from tac.channels.session_manager import SessionManager

#
# TODO See https://www.twilio.com/docs/voice/conversationrelay/websocket-messages
# for WebSocket reconnection logic

TASK_CANCELLATION_TIMEOUT = 5.0


class VoiceChannel(BaseChannel):
    """
    Voice Channel for handling voice-based conversations.

    Inherits conversation lifecycle management from BaseChannel and provides
    voice-specific metadata extraction.
    """

    def __init__(
        self,
        tac: TAC,
        session_manager: Optional["SessionManager"] = None,
        server_config: Optional[VoiceServerConfig] = None,
        auto_retrieve_memory: bool = True,
    ):
        """
        Initialize Voice channel for websocket protocol handling.

        Args:
            tac: TAC instance for memory/context operations
            session_manager: Optional SessionManager for tracking and
                canceling in-flight streaming tasks. The SessionManager
                encapsulates the stream_generator for LLM responses
                If provided, enables task cancellation on interrupts
                and new prompts.
            server_config: Optional server configuration. If provided, enables the simplified
                         start() method to automatically create and run a FastAPI server.
            auto_retrieve_memory: If True (default), automatically retrieve memory
                before invoking the on_message_ready callback. Set to False to
                disable automatic memory retrieval (e.g., for latency-sensitive
                voice applications).
        """
        super().__init__(tac, auto_retrieve_memory=auto_retrieve_memory)

        # Optional session manager for task tracking, cancellation, and streaming
        self.session_manager = session_manager

        # WebSocket manager for multi-connection support
        self._websocket_manager = WebSocketManager()
        self._server_config = server_config

    async def handle_incoming_call(
        self,
        websocket_url: str,
        to_number: str,
        from_number: str,
        call_sid: Optional[str] = None,
        action_url: Optional[str] = None,
        welcome_greeting: str = "Hello! How can I assist you today?",
    ) -> str:
        """
        Generate TwiML response for incoming voice calls.

        This method creates a new conversation and returns TwiML that connects
        the call to a ConversationRelay WebSocket endpoint.

        Args:
            websocket_url: WebSocket URL for ConversationRelay (e.g., 'wss://example.ngrok.io/ws')
            to_number: Twilio phone number that was called (e.g., '+15551234567')
            from_number: Caller's phone number (e.g., '+15559876543')
            call_sid: Optional Twilio Call SID to associate with participants
            action_url: Optional URL for Twilio to request when the call ends.
            welcome_greeting: Initial greeting message for the caller.
                            Defaults to "Hello! How can I assist you today?"

        Returns:
            TwiML XML string for call connection
        """
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

        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect action="{action_url}">
        <ConversationRelay url="{websocket_url}" welcomeGreeting="{welcome_greeting}">
            <Parameter name="conversationId" value="{conversation_id}" />
            <Parameter name="profileId" value="{profile_id}" />
            <Parameter name="customerParticipantId" value="{customer_participant_id}" />
            <Parameter name="aiAgentParticipantId" value="{ai_agent_participant_id}" />
        </ConversationRelay>
    </Connect>
</Response>"""

        return twiml

    async def handle_handoff(self, request: Request) -> Response:
        """
        Generic handler for handoff webhook. Delegates to registered TAC handoff callback.
        Args:
            request: FastAPI Request object for the webhook.
        Returns:
            FastAPI Response for Twilio (or as returned by the callback).
        """
        self.logger.info("Handling handoff webhook (delegated)")
        request_data: FormData = await request.form()
        cb = getattr(self.tac, "_handoff_callback", None)
        if cb is not None:
            result = await cb(request_data)
            # Explicitly cast to Response for mypy
            from fastapi import Response as FastAPIResponse

            if not isinstance(result, FastAPIResponse):
                raise TypeError("Handoff callback did not return a FastAPI Response")
            return result
        return Response(
            content="No handoff handler registered", media_type="text/plain", status_code=501
        )

    async def handle_conversation_relay_callback(self, request: Request) -> Response:
        """
        Handle ConversationRelay callback webhook from Twilio.

        This method processes the callback sent by Twilio when a ConversationRelay
        session ends, and closes associated conversations if the call status is "completed".

        Args:
            request: FastAPI Request object containing form data with:
                - CallSid: Twilio Call SID
                - CallStatus: Call status (e.g., "completed", "in-progress")
                - SessionStatus: ConversationRelay session status
                - SessionDuration: Duration of the session in seconds
                - HandoffData: Optional JSON string with handoff information

        Returns:
            FastAPI Response acknowledging the callback
        """
        # TODO: Need to integrate handoff logic to this function as well. Will do it later.
        try:
            # Parse form data into dict
            form_data = await request.form()
            payload_dict = {key: str(value) for key, value in form_data.items()}

            # Parse into Pydantic model
            payload = ConversationRelayCallbackPayload(**payload_dict)

            self.logger.debug(
                f"[ConversationRelay Callback] CallSid: {payload.call_sid}, "
                f"Status: {payload.call_status}"
            )

            if payload.call_status == "in-progress" and payload.handoff_data:
                return await self.handle_handoff(request)

            # If call is completed, close associated conversations
            if payload.call_status == "completed":
                # Get all conversations associated with this call
                conversations = await self.tac.maestro_client.list_conversations(
                    channel_id=payload.call_sid
                )

                self.logger.info(
                    f"\n{'=' * 80}\n📞 CALL ENDED | Closing {len(conversations)} conversation(s)",
                    call_sid=payload.call_sid,
                )

                # Close each conversation
                for conversation in conversations:
                    try:
                        await self.tac.maestro_client.update_conversation(
                            conversation_id=conversation.id, status="CLOSED"
                        )
                        self.logger.debug(
                            f"[ConversationRelay Callback] Closed conversation: {conversation.id}"
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Failed to close conversation {conversation.id}: {e}",
                            exc_info=True,
                        )

            return Response(content="OK", media_type="text/plain", status_code=200)
        except Exception as e:
            self.logger.error(f"Error handling ConversationRelay callback: {e}", exc_info=True)
            return Response(
                content="Internal Server Error", media_type="text/plain", status_code=500
            )

    async def handle_websocket(self, websocket: WebSocket) -> None:
        """
        Handle voice streaming WebSocket connection lifecycle.

        This method manages the entire websocket connection:
        - Accepts the connection
        - Processes incoming messages
        - Tracks and cancels in-flight tasks (if session_manager provided)
        - Cleans up on disconnect

        Args:
            websocket: FastAPI WebSocket instance
        """
        await websocket.accept()
        self.logger.debug("WebSocket connection established")

        conv_id = None
        session_state = None
        handler_task = None

        try:
            # First message should be 'setup'
            data = await websocket.receive_json()
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f"Received WebSocket data: {data}")

            if data.get("type") == "setup":
                setup_msg = SetupMessage(**data)

                # Extract conversation ID from setup message
                if (
                    not setup_msg.custom_parameters
                    or not setup_msg.custom_parameters.conversation_id
                ):
                    self.logger.error(
                        "conversationId is required in custom_parameters but was not provided"
                    )
                    await websocket.close()
                    return

                conv_id = setup_msg.custom_parameters.conversation_id

                # Store WebSocket in manager BEFORE calling _handle_setup
                self._websocket_manager.add_websocket(conv_id, websocket)
                self.logger.debug("Registered WebSocket", conversation_id=conv_id)

                # Handle setup to initialize conversation
                await self._handle_setup(setup_msg)
                session_state = None  # Initialize as None

                # Get or create session state if session manager is available
                if self.session_manager is not None and conv_id:
                    try:
                        session_state = self.session_manager.get_or_create_session(conv_id)
                        if self.logger.isEnabledFor(logging.DEBUG):
                            self.logger.info(
                                f"Session state SUCCESSFULLY created for {conv_id}: {session_state}"
                            )
                    except Exception as e:
                        self.logger.error(f"Error creating session state: {e}", exc_info=True)
            else:
                self.logger.warning("First message was not 'setup'. Closing connection.")
                await websocket.close()
                return

            # Create dedicated task to handle all subsequent messages
            handler_task = asyncio.create_task(
                self._message_handler(websocket, conv_id, session_state)
            )
            await handler_task

        except WebSocketDisconnect:
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
        websocket: WebSocket,
        conv_id: Optional[str],
        session_state: Any,
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
                self.logger.debug(f"Received WebSocket data: {data}")
                msg_type = data.get("type")

                if msg_type == "prompt":
                    await self._handle_prompt_async(conv_id, data, session_state)
                elif msg_type == "interrupt":
                    await self._handle_interrupt_async(conv_id, data, session_state)
                elif msg_type == "setup":
                    self.logger.info(
                        f"Ignoring subsequent setup message for conversation {conv_id}"
                    )
                else:
                    # ignore unknown message types
                    self.logger.debug(f"Unknown message type received: {msg_type}")

        except WebSocketDisconnect:
            self.logger.debug(
                f"WebSocket disconnected during message handling for conversation {conv_id}"
            )
        except Exception as e:
            self.logger.error(
                f"Error in message_handler for conversation {conv_id}: {e}", exc_info=True
            )

    async def _handle_prompt_async(
        self,
        conv_id: Optional[str],
        data: dict[str, Any],
        session_state: Any,
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

                if not conv_id:
                    self.logger.error(
                        "No active conversation ID for prompt message; "
                        "ensure setup message is processed first"
                    )
                    return

                # Cancel previous stream task if session manager is enabled
                if session_state:
                    if session_state.stream_task and not session_state.stream_task.done():
                        if self.logger.isEnabledFor(logging.DEBUG):
                            self.logger.debug(
                                "Cancelling previous stream task", conversation_id=conv_id
                            )
                        session_state.stream_task.cancel()
                        try:
                            await asyncio.wait_for(
                                session_state.stream_task, timeout=TASK_CANCELLATION_TIMEOUT
                            )
                        except asyncio.CancelledError:
                            pass
                        except asyncio.TimeoutError:
                            self.logger.error(
                                f"Task cancellation timed out for {conv_id}. "
                                f"The stream generator is not handling cancellation properly."
                            )

                    # Create new streaming task
                    session_state.stream_task = asyncio.create_task(
                        self._process_prompt(conv_id, prompt_msg)
                    )
                else:
                    # No session manager - await directly
                    await self._handle_prompt(conv_id, prompt_msg)
        except Exception as e:
            self.logger.error(f"Failed to handle prompt: {str(e)}")

    async def _handle_interrupt_async(
        self,
        conv_id: Optional[str],
        data: dict[str, Any],
        session_state: Any,
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

            if not conv_id:
                self.logger.error(
                    "No active conversation ID for interrupt message; "
                    "ensure setup message is processed first"
                )
                return

            # Cancel in-flight stream task if session manager is enabled
            if session_state:
                if session_state.stream_task and not session_state.stream_task.done():
                    session_state.stream_task.cancel()
                    self.logger.info(
                        "Canceled streaming task due to interrupt", conversation_id=conv_id
                    )
                    try:
                        await session_state.stream_task
                    except asyncio.CancelledError:
                        pass

                # Send acknowledgment to Twilio after cancelling
                websocket = self._websocket_manager.get_websocket(conv_id)
                if websocket:
                    try:
                        await websocket.send_text(
                            json.dumps({"type": "text", "token": "", "last": True})
                        )
                    except (WebSocketDisconnect, RuntimeError):
                        self.logger.info(
                            f"WebSocket closed before sending interrupt acknowledgment "
                            f"for {conv_id}."
                        )

            # Call the interrupt handler
            self._handle_interrupt(conv_id, interrupt_msg)

        except Exception as e:
            self.logger.error(f"Failed to handle interrupt: {str(e)}")

    async def _process_prompt(self, conv_id: str, message: PromptMessage) -> None:
        """
        Process prompt asynchronously with streaming if session_manager is available.

        Args:
            conv_id: Conversation ID
            message: Parsed PromptMessage
        """
        if self.session_manager:
            # Use session manager's streaming capability
            await self._stream_and_send_response(conv_id, message)
        else:
            # No session manager - await handler directly
            await self._handle_prompt(conv_id, message)

    async def _stream_and_send_response(self, conv_id: str, message: PromptMessage) -> None:
        """
        Stream LLM response using session_manager and send to websocket.

        Args:
            conv_id: Conversation ID
            message: Parsed PromptMessage containing user's speech
        """
        # Get WebSocket from manager
        websocket = self._websocket_manager.get_websocket(conv_id)
        if not websocket:
            self.logger.error("No websocket for conversation", conversation_id=conv_id)
            return

        if not self.session_manager:
            self.logger.error("No session_manager available", conversation_id=conv_id)
            return

        prompt = message.voice_prompt or ""

        try:
            json_template = {"type": "text", "token": "", "last": False}
            closed = False

            # Stream response chunks from session manager
            async for chunk in self.session_manager.stream_response(prompt, conv_id):
                # Handle different chunk types (plain text or dict with metadata)
                if isinstance(chunk, dict):
                    if "output" in chunk:
                        json_template["token"] = chunk["output"]
                    else:
                        json_template["token"] = str(chunk)
                else:
                    json_template["token"] = chunk

                try:
                    await websocket.send_text(json.dumps(json_template))
                except (WebSocketDisconnect, RuntimeError):
                    self.logger.info("WebSocket closed during streaming", conversation_id=conv_id)
                    closed = True
                    break

            # Send final message marker
            if not closed:
                try:
                    await websocket.send_text(
                        json.dumps({"type": "text", "token": "", "last": True})
                    )
                except (WebSocketDisconnect, RuntimeError):
                    self.logger.info(
                        "WebSocket closed before sending final marker", conversation_id=conv_id
                    )

        except asyncio.CancelledError:
            self.logger.info("Streaming cancelled", conversation_id=conv_id)
            raise
        except Exception as e:
            self.logger.error(
                f"Error during streaming: {e}", conversation_id=conv_id, exc_info=True
            )
            error_msg = json.dumps(
                {"type": "text", "token": "Sorry, an error occurred.", "last": True}
            )
            try:
                await websocket.send_text(error_msg)
            except (WebSocketDisconnect, RuntimeError):
                self.logger.info(
                    "WebSocket closed before sending error message", conversation_id=conv_id
                )
        finally:
            self.logger.info("Finished streaming response", conversation_id=conv_id)

    # todo: voice does not support webhooks yet
    async def process_webhook(self, webhook_data: dict[str, Any]) -> None:
        pass

    async def send_response(
        self, conversation_id: str, response: str, role: Optional[str] = None
    ) -> None:
        """
        Send voice response through the websocket connection for this conversation.

        Args:
            conversation_id: Conversation ID
            response: Response text to send
            role: Optional message role (not used in this implementation, but kept
                  for API consistency with BaseChannel interface)
        """
        # Get WebSocket from manager
        websocket = self._websocket_manager.get_websocket(conversation_id)
        if not websocket:
            self.logger.error("No websocket connection", conversation_id=conversation_id)
            return

        try:
            await websocket.send_text(json.dumps({"type": "text", "token": response, "last": True}))

            if (
                self.tac.config.enable_voice_active_hydration
                and conversation_id in self._conversations
            ):
                session = self._conversations[conversation_id]

                if session.author_info and session.ai_agent_info:
                    # Agent is author, customer is recipient
                    await self._create_communication(
                        conversation_id=conversation_id,
                        message_content=response,
                        author_address=session.ai_agent_info.address,
                        recipient_address=session.author_info.address,
                        author_participant_id=session.ai_agent_info.participant_id,
                        recipient_participant_id=session.author_info.participant_id,
                    )
                else:
                    self.logger.warning(
                        "[Active Hydration] Missing author or AI agent info",
                        conversation_id=conversation_id,
                    )
        except (WebSocketDisconnect, RuntimeError):
            self.logger.info(
                "WebSocket closed before sending response", conversation_id=conversation_id
            )

    def get_channel_name(self) -> str:
        return "voice"

    def get_websocket(self, conversation_id: str) -> Optional[WebSocket]:
        """
        Get the WebSocket connection for a specific conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            WebSocket connection if exists, None otherwise
        """
        return self._websocket_manager.get_websocket(conversation_id)

    async def _handle_setup(self, message: SetupMessage) -> None:
        """
        Handle WebSocket setup message.

        Args:
            message: Parsed SetupMessage containing call metadata
        """
        # Validate conversation ID is present in custom parameters
        if not message.custom_parameters or not message.custom_parameters.conversation_id:
            self.logger.error(
                "conversationId is required in custom_parameters but was not provided"
            )
            return

        # Use the conversation ID from custom parameters as the canonical conversation ID
        conversation_id = message.custom_parameters.conversation_id

        # Extract profile ID from custom parameters if available
        profile_id = None
        if message.custom_parameters.profile_id:
            profile_id = message.custom_parameters.profile_id

        await self._start_conversation(conversation_id, profile_id)

        # If active hydration is enabled, populate author_info and ai_agent_info
        if self.tac.config.enable_voice_active_hydration:
            # Save customer info if from_number is available
            if message.from_number:
                self._conversations[conversation_id].author_info = AuthorInfo(
                    address=message.from_number,
                    participant_id=message.custom_parameters.customer_participant_id,
                )
            # Save AI agent info if to_number is available
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
                "Conversation should be initialized in setup message first."
            )
            return

        message_body = message.voice_prompt or ""
        session = self._conversations[conv_id]

        # If active hydration is enabled, send user message to Maestro
        if (
            self.tac.config.enable_voice_active_hydration
            and session.author_info
            and session.ai_agent_info
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
        self.logger.info(
            f"INTERRUPT | User interrupted (after {message.duration_until_interrupt_ms}ms)",
            conversation_id=conv_id,
        )

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
            self.logger.debug("Removed WebSocket", conversation_id=conv_id)

        # Cancel any running stream task and cleanup session if session manager is enabled
        if self.session_manager and self.session_manager.has_session(conv_id):
            sessions_before = len(self.session_manager)
            self.logger.info(
                f"Cleaning up conversation {conv_id} - sessions before: {sessions_before}"
            )

            session_state = self.session_manager.get_or_create_session(conv_id)
            if session_state.stream_task and not session_state.stream_task.done():
                session_state.stream_task.cancel()
                self.logger.info("Cancelled stream_task", conversation_id=conv_id)

            self.session_manager.remove_session(conv_id)
            sessions_after = len(self.session_manager)
            self.logger.info(
                f"Cleaned up conversation {conv_id} - sessions after: {sessions_after}"
            )

        # Clean up conversation state from BaseChannel
        if conv_id in self._conversations:
            del self._conversations[conv_id]
            self.logger.debug("Ended conversation", conversation_id=conv_id)

    async def _create_communication(
        self,
        conversation_id: str,
        message_content: str,
        author_address: str,
        recipient_address: str,
        author_participant_id: Optional[str] = None,
        recipient_participant_id: Optional[str] = None,
    ) -> None:
        """
        Add communication to Maestro for active hydration.

        Args:
            conversation_id: Conversation ID
            message_content: Message content
            author_address: Author's address (phone number)
            recipient_address: Recipient's address (phone number)
            author_participant_id: Optional author's participant ID
            recipient_participant_id: Optional recipient's participant ID
        """
        try:
            communication_request = CommunicationRequest(
                author=CommunicationParticipant(
                    address=author_address, channel="VOICE", participantId=author_participant_id
                ),
                content=CommunicationContent(type="TEXT", text=message_content),
                recipients=[
                    CommunicationParticipant(
                        address=recipient_address,
                        channel="VOICE",
                        participantId=recipient_participant_id,
                    )
                ],
            )

            await self.tac.maestro_client.create_communication(
                conversation_id, communication_request
            )
            self.logger.debug(
                "[Active Hydration] Added communication to conversation",
                conversation_id=conversation_id,
            )
        except Exception:
            self.logger.error(
                "[Active Hydration] Failed to add communication",
                conversation_id=conversation_id,
                exc_info=True,
            )

    def start(self) -> None:
        """
        Start the built-in FastAPI server with TwiML and WebSocket endpoints.

        This method is only available when server_config is provided during initialization.
        It automatically creates a FastAPI app with:
        - POST /twiml endpoint for handling incoming calls
        - WebSocket /ws endpoint for ConversationRelay connections
        - POST /conversation-relay-callback endpoint for handling call completion

        Raises:
            ValueError: If server_config was not provided during initialization
            ImportError: If FastAPI or uvicorn are not installed
        """
        if not self._server_config:
            raise ValueError(
                "Cannot start server: server_config was not provided during initialization. "
                "Either provide VoiceServerConfig to VoiceChannel.__init__() or manually "
                "create your FastAPI app and routes."
            )
        # Store config in local variable for type checking
        config = self._server_config

        # Create FastAPI app
        app = FastAPI(title="TAC Voice Server")

        # Register TwiML endpoint
        @app.post("/twiml")
        async def post_twiml(
            From: str = Form(...),  # noqa: N803
            To: str = Form(...),  # noqa: N803
            CallSid: str = Form(...),  # noqa: N803
        ) -> Response:
            """Generate TwiML for incoming voice calls."""
            websocket_url = f"wss://{config.public_domain}/ws"
            callback_url = f"https://{config.public_domain}/conversation-relay-callback"

            twiml = await self.handle_incoming_call(
                websocket_url=websocket_url,
                to_number=To,
                from_number=From,
                call_sid=CallSid,
                action_url=callback_url,
                welcome_greeting=config.welcome_greeting,
            )
            return Response(content=twiml, media_type="application/xml")

        # Register WebSocket endpoint
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket) -> None:
            """Handle voice WebSocket connections for real-time streaming."""
            await self.handle_websocket(websocket)

        # Register ConversationRelay callback endpoint
        @app.post("/conversation-relay-callback")
        async def conversation_relay_callback(request: Request) -> Response:
            """Handle ConversationRelay callback webhook from Twilio."""
            return await self.handle_conversation_relay_callback(request)

        # Start the server
        self.logger.info(f"Starting TAC Voice Server on {config.host}:{config.port}")

        uvicorn.run(
            app,
            host=config.host,
            port=config.port,
            log_level="info",
        )
