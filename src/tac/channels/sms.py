"""SMS Channel implementation for TAC."""

from collections import OrderedDict
from collections.abc import AsyncGenerator
from typing import Any, Optional, Union

from pydantic import BaseModel, Field

from tac import TAC
from tac.channels.base import BaseChannel
from tac.models.conversation import (
    Communication,
    CommunicationContent,
    ConversationResponse,
    ParticipantResponse,
    SendCommunicationParticipantAddress,
    SendCommunicationRequest,
)
from tac.models.session import AuthorInfo


class SMSChannelConfig(BaseModel):
    """
    Configuration for SMS channel.

    Attributes:
        dedup_capacity: Maximum number of idempotency tokens to track.
            Default 10000 is suitable for most applications.
            Uses Twilio's i-twilio-idempotency-token header for deduplication.
        auto_retrieve_memory: If True, automatically retrieve memory
            before invoking the on_message_ready callback. Default is False.
            Set to True to enable automatic memory retrieval.
    """

    dedup_capacity: int = Field(
        default=10000,
        gt=0,
        description="Maximum number of idempotency tokens to track for deduplication",
    )
    auto_retrieve_memory: bool = Field(
        default=False,
        description="Automatically retrieve memory before on_message_ready callback",
    )


class SMSChannel(BaseChannel):
    """
    SMS Channel for handling SMS-based conversations.

    Inherits conversation lifecycle management from BaseChannel and provides
    SMS-specific metadata extraction.
    """

    def __init__(
        self,
        tac: TAC,
        config: Optional[Union[SMSChannelConfig, dict[str, Any]]] = None,
    ):
        """
        Initialize SMS channel with idempotency-based deduplication.

        Args:
            tac: TAC instance for memory/context operations
            config: SMS channel configuration (SMSChannelConfig or dict).
                If None, uses default configuration.

        Raises:
            ValueError: If twilio_phone_number is not configured

        Examples:
            >>> channel = SMSChannel(tac, config={"dedup_capacity": 50000})
            >>> channel = SMSChannel(tac, config=SMSChannelConfig(auto_retrieve_memory=True))
            >>> channel = SMSChannel(tac)  # Use defaults
        """
        # Convert dict to config model or use defaults
        if isinstance(config, dict):
            config = SMSChannelConfig(**config)
        elif config is None:
            config = SMSChannelConfig()

        super().__init__(tac, auto_retrieve_memory=config.auto_retrieve_memory)

        if not tac.config.twilio_phone_number:
            raise ValueError(
                "twilio_phone_number is required for SMS channel. "
                "Please set TWILIO_TAC_PHONE_NUMBER environment variable or "
                "provide twilio_phone_number in TACConfig."
            )
        # Track processed idempotency tokens to prevent duplicate webhook processing
        # OrderedDict maintains insertion order for FIFO removal when at capacity
        self._processed_tokens: OrderedDict[str, bool] = OrderedDict()
        self._max_tracked_tokens = config.dedup_capacity

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
        - participant.added: Initialize conversation and track profile_id when customer joins
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
                return

        event_type = webhook_data.get("eventType")
        event_data = webhook_data.get("data")

        if event_type == "PARTICIPANT_ADDED":
            self._handle_participant_added(event_data)
        elif event_type == "COMMUNICATION_CREATED":
            await self._handle_communication_created(event_data)
        elif event_type == "CONVERSATION_UPDATED":
            await self._handle_conversation_updated(event_data)

    async def send_response(
        self,
        conversation_id: str,
        response: Union[str, AsyncGenerator[Union[str, dict[str, Any]], None]],
        role: Optional[str] = None,
    ) -> None:
        """
        Send SMS response for a conversation using the Conversation Orchestrator Send API.

        Note: SMS channel only supports simple string responses. Async generators
        (streaming) are not supported and will raise a TypeError.

        Args:
            conversation_id: Conversation ID to send response to
            response: Message content (must be string for SMS)
            role: Optional message role (not used in SMS channel)

        Raises:
            TypeError: If response is not a string
        """
        # SMS only supports string responses (no streaming)
        if not isinstance(response, str):
            raise TypeError("SMS channel only supports string responses")

        # Fetch all participants from Conversation Orchestrator
        try:
            participants = await self.tac.maestro_client.list_participants(conversation_id)
        except Exception as e:
            self.logger.error(
                "Failed to list participants",
                conversation_id=conversation_id,
                error=str(e),
            )
            return

        # Find agent and customer participants with SMS addresses
        agent_participant = None
        customer_participant = None
        customer_address = None
        for participant in participants:
            if not agent_participant and participant.type in ("AI_AGENT", "HUMAN_AGENT"):
                for address in participant.addresses:
                    if (
                        address.channel == "SMS"
                        and address.address == self.tac.config.twilio_phone_number
                    ):
                        agent_participant = participant
                        break
            elif not customer_participant and participant.type == "CUSTOMER":
                for address in participant.addresses:
                    if address.channel == "SMS":
                        customer_participant = participant
                        customer_address = address.address
                        break

        if not agent_participant:
            self.logger.error(
                "Agent participant not found",
                conversation_id=conversation_id,
                phone_number=self.tac.config.twilio_phone_number,
            )
            return

        if not customer_participant or not customer_address:
            self.logger.error(
                "Customer participant with SMS address not found",
                conversation_id=conversation_id,
            )
            return

        # Build and send communication via Send API
        try:
            send_request = SendCommunicationRequest(
                author=SendCommunicationParticipantAddress(
                    address=self.tac.config.twilio_phone_number,
                    channel="SMS",
                    participant_id=agent_participant.id,
                ),
                content=CommunicationContent(type="TEXT", text=response),
                recipients=[
                    SendCommunicationParticipantAddress(
                        address=customer_address,
                        channel="SMS",
                        participant_id=customer_participant.id,
                    )
                ],
            )

            await self.tac.maestro_client.send_communication(conversation_id, send_request)

            self.logger.debug(
                "Sent SMS response via Send API",
                conversation_id=conversation_id,
                to_address=customer_address,
            )
        except Exception as e:
            self.logger.error(
                "Failed to send communication",
                conversation_id=conversation_id,
                error=str(e),
                exc_info=True,
            )

    def get_channel_name(self) -> str:
        """Get the channel name identifier."""
        return "sms"

    def _handle_participant_added(self, event_data: Any) -> None:
        """
        Handle participant.added event.

        Only processes CUSTOMER participants with SMS addresses.

        Args:
            event_data: Raw event data from webhook
        """
        participant_data = ParticipantResponse.model_validate(event_data)
        conv_id = participant_data.conversation_id
        profile_id = participant_data.profile_id
        participant_type = participant_data.type

        if participant_type != "CUSTOMER":
            return

        # Check if participant has any SMS addresses
        has_sms_address = any(address.channel == "SMS" for address in participant_data.addresses)

        if not has_sms_address:
            return

        # Process CUSTOMER participant with SMS address
        if conv_id not in self._conversations:
            self._start_conversation(conv_id, profile_id)

        if profile_id:
            session = self._conversations[conv_id]
            session.profile_id = profile_id

        self.logger.debug(
            "Customer participant added",
            conversation_id=conv_id,
            profile_id=profile_id,
        )

    async def _handle_communication_created(self, event_data: Any) -> None:
        """
        Handle communication.created event (incoming message).

        Args:
            event_data: Raw event data from webhook
        """
        communication_data = Communication.model_validate(event_data)
        conv_id = communication_data.conversation_id
        message_text = communication_data.content.text

        # Filter out non-SMS messages, AI agent messages, and empty messages
        if (
            communication_data.author.channel != "SMS"
            or communication_data.author.address == self.tac.config.twilio_phone_number
            or not message_text
            or not message_text.strip()
        ):
            return

        if conv_id not in self._conversations:
            self._start_conversation(conv_id, profile_id=None)

        session = self._conversations[conv_id]

        session.author_info = AuthorInfo(
            address=communication_data.author.address,
            participant_id=communication_data.author.participant_id,
        )

        memory_response = await self._retrieve_memory_if_enabled(session, message_text, conv_id)

        try:
            await self.tac.trigger_message_ready(message_text, session, memory_response)
        except Exception as e:
            self.logger.error(
                "Error in message ready callback",
                conversation_id=conv_id,
                error=str(e),
                exc_info=True,
            )

    async def _handle_conversation_updated(self, event_data: Any) -> None:
        """
        Handle conversation.updated event.

        Only processes conversation updates for the configured conversation service
        and only cleans up SMS conversations that are tracked locally.

        Args:
            event_data: Raw event data from webhook
        """
        conversation_data = ConversationResponse.model_validate(event_data)
        conv_id = conversation_data.id

        if (
            conversation_data.configuration_id == self.tac.config.conversation_service_sid
            and conversation_data.status == "CLOSED"
            and conv_id in self._conversations
            and self._conversations[conv_id].channel == self.get_channel_name()
        ):
            await self._end_conversation(conv_id)
