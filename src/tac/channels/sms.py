"""SMS Channel implementation for TAC."""

from collections import OrderedDict
from typing import Any, Optional

from twilio.rest import Client

from tac import TAC
from tac.channels.base import BaseChannel
from tac.models.conversation import (
    Communication,
    CommunicationContent,
    CommunicationParticipant,
    CommunicationRequest,
    ConversationResponse,
    ParticipantResponse,
)
from tac.models.session import AuthorInfo


class SMSChannel(BaseChannel):
    """
    SMS Channel for handling SMS-based conversations.

    Inherits conversation lifecycle management from BaseChannel and provides
    SMS-specific metadata extraction.
    """

    def __init__(self, tac: TAC, dedup_capacity: int = 10000, auto_retrieve_memory: bool = True):
        """
        Initialize SMS channel with idempotency-based deduplication.

        Args:
            tac: TAC instance for memory/context operations
            dedup_capacity: Maximum number of idempotency tokens to track.
                          Default 10000 is suitable for most applications.
                          Uses Twilio's i-twilio-idempotency-token header for deduplication.
            auto_retrieve_memory: If True (default), automatically retrieve memory
                before invoking the on_message_ready callback. Set to False to
                disable automatic memory retrieval.

        Raises:
            ValueError: If twilio_phone_number is not configured
        """
        super().__init__(tac, auto_retrieve_memory=auto_retrieve_memory)
        if not tac.config.twilio_phone_number:
            raise ValueError(
                "twilio_phone_number is required for SMS channel. "
                "Please set TWILIO_TAC_PHONE_NUMBER environment variable or "
                "provide twilio_phone_number in TACConfig."
            )
        self.twilio = Client(tac.config.twilio_account_sid, tac.config.twilio_auth_token)
        # Track processed idempotency tokens to prevent duplicate webhook processing
        # OrderedDict maintains insertion order for FIFO removal when at capacity
        self._processed_tokens: OrderedDict[str, bool] = OrderedDict()
        self._max_tracked_tokens = dedup_capacity

    def _is_duplicate_webhook(self, idempotency_token: str) -> bool:
        """
        Check if a webhook has already been processed using Twilio's idempotency token.

        Uses a sliding window approach with fixed capacity to track tokens.
        When capacity is reached, the oldest token is automatically removed (FIFO).

        Args:
            idempotency_token: Twilio's i-twilio-idempotency-token header value

        Returns:
            True if the webhook has already been processed (is a duplicate),
            False if this is the first time seeing this webhook
        """
        # Check if we've already processed this webhook
        if idempotency_token in self._processed_tokens:
            return True

        # Sliding window: Remove oldest entry if at capacity
        if len(self._processed_tokens) >= self._max_tracked_tokens:
            # Remove the oldest (first) entry - FIFO
            self._processed_tokens.popitem(last=False)

        # Mark webhook as processed
        self._processed_tokens[idempotency_token] = True
        return False

    async def process_webhook(
        self, webhook_data: dict[str, Any], idempotency_token: Optional[str] = None
    ) -> None:
        """
        Process SMS webhook event and manage conversation lifecycle.

        Handles:
        - conversation.created: Initialize new conversation
        - participant.added: Track profile_id when customer joins
        - communication.created: Process incoming messages from customers
        - conversation.updated: Clean up when conversation is closed

        Uses Twilio's i-twilio-idempotency-token header to prevent duplicate processing
        when webhooks are retried.

        Args:
            webhook_data: Raw webhook event data from Twilio
            idempotency_token: Optional Twilio idempotency token from request headers
        """
        # Deduplicate using Twilio's idempotency token (if provided)
        if idempotency_token:
            if self._is_duplicate_webhook(idempotency_token):
                self.logger.debug("DUPLICATE WEBHOOK (retry)")
                return

        event_type = webhook_data.get("eventType")
        event_data = webhook_data.get("data")

        if event_type == "CONVERSATION_CREATED":
            await self._handle_conversation_created(event_data)
        elif event_type == "PARTICIPANT_ADDED":
            await self._handle_participant_added(event_data)
        elif event_type == "COMMUNICATION_CREATED":
            await self._handle_communication_created(event_data)
        elif event_type == "CONVERSATION_UPDATED":
            self._handle_conversation_updated(event_data)
        else:
            self.logger.debug(
                "Ignoring event type",
                event_type=event_type,
            )

    async def send_response(
        self, conversation_id: str, response: str, role: Optional[str] = None
    ) -> None:
        """
        Send SMS response for a conversation using the Maestro Communications API.

        Args:
            conversation_id: Conversation ID to send response to
            response: Message content to send
            role: Optional message role (not used in SMS channel)

        Note:
            This is a placeholder implementation. In production, this would
            use the Twilio SMS API to send the actual message.
        """
        if conversation_id not in self._conversations:
            self.logger.error(
                "Cannot send response: conversation not found",
                conversation_id=conversation_id,
            )
            return

        # TODO this is a super hacky workaround because Maestro isn't ready to
        # support sending messages yet. Defensively go from conversation_id ->
        # participant -> address -> phone number
        try:
            participants = await self.tac.maestro_client.list_participants(conversation_id)
        except Exception as e:
            self.logger.error(
                "Failed to list participants",
                conversation_id=conversation_id,
                error=str(e),
            )
            self.logger.info("Continuing without sending response via Maestro")
            return

        for participant in participants:
            if participant.type != "CUSTOMER":
                self.logger.debug("Found non-customer participant; skipping")
                continue

            for address in participant.addresses:
                if address.channel != "SMS":
                    self.logger.debug("Found non-SMS address; skipping")
                    continue

                self.logger.debug(
                    "Sending SMS response",
                    conversation_id=conversation_id,
                    to_address=address.address,
                )
                self.twilio.messages.create(
                    to=address.address,
                    from_=self.tac.config.twilio_phone_number,
                    body=response,
                )
                self.logger.info(
                    "Sent SMS response",
                    conversation_id=conversation_id,
                    to_address=address.address,
                )

    def get_channel_name(self) -> str:
        """Get the channel name identifier."""
        return "sms"

    async def _handle_conversation_created(self, event_data: Any) -> None:
        """
        Handle conversation.created event.

        Args:
            event_data: Raw event data from webhook
        """
        conversation_data = ConversationResponse.model_validate(event_data)
        conv_id = conversation_data.id
        self.logger.debug("Conversation created", conversation_id=conv_id)
        # Start conversation without profile_id initially
        # Profile ID will be added when participant.added event arrives
        await self._start_conversation(conv_id, profile_id=None)

    async def _handle_participant_added(self, event_data: Any) -> None:
        """
        Handle participant.added event.

        Args:
            event_data: Raw event data from webhook
        """
        participant_data = ParticipantResponse.model_validate(event_data)
        conv_id = participant_data.conversation_id
        # Only track CUSTOMER participants with profile_id
        if participant_data.type == "CUSTOMER" and participant_data.profile_id:
            self.logger.debug(
                "Customer participant added",
                conversation_id=conv_id,
                profile_id=participant_data.profile_id,
            )

            # Auto-initialize conversation if not already started
            if conv_id not in self._conversations:
                await self._start_conversation(conv_id, participant_data.profile_id)
            else:
                # Update existing conversation with profile_id
                session = self._conversations[conv_id]
                session.profile_id = participant_data.profile_id

                # Fetch profile immediately
                if self.tac.is_twilio_memory_enabled():
                    profile = await self.tac.fetch_profile(participant_data.profile_id)
                    if profile:
                        session.profile = profile
        else:
            self.logger.debug(
                "Participant added",
                conversation_id=conv_id,
                participant_type=participant_data.type,
                profile_id=participant_data.profile_id,
            )

    async def _handle_communication_created(self, event_data: Any) -> None:
        """
        Handle communication.created event (incoming message).

        Args:
            event_data: Raw event data from webhook
        """
        communication_data = Communication.model_validate(event_data)

        # Filter out non-SMS communications
        if communication_data.author.channel != "SMS":
            self.logger.debug(
                "Ignoring non-SMS communication", channel=communication_data.author.channel
            )
            return

        conv_id = communication_data.conversation_id
        if not conv_id:
            self.logger.error("No conversation_id in communication data")
            return

        # TODO: Figure out a way to filter out messages from non-CUSTOMER participants
        if communication_data.author.address == self.tac.config.twilio_phone_number:
            self.logger.debug(
                "Ignoring message from AI agent",
                conversation_id=conv_id,
            )
            return

        # Extract and validate message text
        message_text = communication_data.content.text
        if not message_text or not message_text.strip():
            self.logger.debug(
                "Empty message, ignoring",
                conversation_id=conv_id,
            )
            return

        # Only process messages from CUSTOMER participants
        # Check if author is a customer by looking up the participant
        if conv_id not in self._conversations:
            self.logger.debug(
                "Received message for unknown conversation, auto-initializing without profile",
                conversation_id=conv_id,
            )
            await self._start_conversation(conv_id, profile_id=None)

        session = self._conversations[conv_id]

        # Update session with author info from the communication event
        session.author_info = AuthorInfo(
            address=communication_data.author.address,
            participant_id=communication_data.author.participant_id,
        )

        # Fetch profile for each message if profile_id is available
        if session.profile_id and self.tac.is_twilio_memory_enabled():
            profile = await self.tac.fetch_profile(session.profile_id)
            if profile:
                # Update session with fresh profile data
                session.profile = profile

        # Retrieve memory if auto_retrieve_memory is enabled and Twilio Memory is configured
        memory_response = await self._retrieve_memory_if_enabled(session, message_text, conv_id)

        # Trigger message ready callback (with or without memory)
        try:
            await self.tac.trigger_message_ready(message_text, session, memory_response)
        except Exception as e:
            self.logger.error(
                "Error in message ready callback",
                conversation_id=conv_id,
                error=str(e),
                exc_info=True,
            )

    def _handle_conversation_updated(self, event_data: Any) -> None:
        """
        Handle conversation.updated event.

        Args:
            event_data: Raw event data from webhook
        """
        conversation_data = ConversationResponse.model_validate(event_data)
        conv_id = conversation_data.id
        # Check if conversation is closed
        if conversation_data.status == "CLOSED":
            self.logger.debug(
                "Conversation closed, cleaning up",
                conversation_id=conv_id,
            )
            self._end_conversation(conv_id)
        else:
            self.logger.debug(
                "Conversation updated",
                conversation_id=conv_id,
                status=conversation_data.status,
            )

    async def _send_response_via_maestro(self, conversation_id: str, response: str) -> None:
        """
        Send SMS response via Maestro Communications API. This is only for demo purpose.

        TODO: Remove this before going production.

        Args:
            conversation_id: Conversation ID to send response to
            response: Message content to send
        """
        session = self._conversations[conversation_id]

        # Build recipient from author_info in session
        if not session.author_info:
            self.logger.error(
                "Cannot send response: no author_info",
                conversation_id=conversation_id,
            )
            return

        recipient = CommunicationParticipant(
            address=session.author_info.address,
            channel="SMS",
            participantId=session.author_info.participant_id,
        )
        recipients = [recipient]

        # Create author using AI_AGENT type and configured Twilio phone number
        # Note: We don't need to find an actual AI_AGENT participant,
        # we can create the author directly
        author = CommunicationParticipant(
            address=self.tac.config.twilio_phone_number,
            channel="SMS",
            participantId=None,  # No participant ID needed for AI agent
        )
        content = CommunicationContent(type="TEXT", text=response)
        comm_request = CommunicationRequest(author=author, content=content, recipients=recipients)

        # Send communication via Maestro
        try:
            self.logger.debug(
                "Sending communication via Maestro",
                conversation_id=conversation_id,
            )
            await self.tac.maestro_client.create_communication(conversation_id, comm_request)
            self.logger.info(
                "Sent response via Maestro",
                conversation_id=conversation_id,
            )
        except Exception as e:
            self.logger.error(
                "Failed to send communication",
                conversation_id=conversation_id,
                error=str(e),
                exc_info=True,
            )
