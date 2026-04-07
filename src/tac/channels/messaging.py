"""MessagingChannel base class for messaging channels (SMS, Chat)."""

from abc import abstractmethod
from collections import OrderedDict
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import BaseModel, Field

from tac import TAC
from tac.channels.base import BaseChannel
from tac.models.conversation import (
    Communication,
    ConversationResponse,
    ParticipantResponse,
)
from tac.models.session import AuthorInfo


class MessagingChannelConfig(BaseModel):
    """Base configuration for messaging channels (SMS, Chat).

    Attributes:
        dedup_capacity: Maximum number of idempotency tokens to track.
            Default 10000 is suitable for most applications.
            Uses Twilio's i-twilio-idempotency-token header for deduplication.
        auto_retrieve_memory: If True, automatically retrieve memory
            before invoking the on_message_ready callback.
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


class MessagingChannel(BaseChannel):
    """Abstract base class for messaging channels (SMS, Chat).

    Provides shared webhook processing logic for channels that use
    Conversation Orchestrator webhooks with PARTICIPANT_ADDED,
    COMMUNICATION_CREATED, and CONVERSATION_UPDATED event types.

    Subclasses must implement:
    - is_own_message(): Check if a message is from the bot itself
    - get_channel_type_upper(): Return uppercase channel type ("SMS", "CHAT")
    - send_response(): Send messages back through the channel
    - get_channel_name(): Return lowercase channel name ("sms", "chat")
    """

    def __init__(
        self,
        tac: TAC,
        dedup_capacity: int = 10000,
        auto_retrieve_memory: bool = False,
    ):
        super().__init__(tac, auto_retrieve_memory=auto_retrieve_memory)
        self._processed_tokens: OrderedDict[str, bool] = OrderedDict()
        self._max_tracked_tokens = dedup_capacity

    @abstractmethod
    def is_own_message(self, author_address: str) -> bool:
        """Check if a message is from the bot itself.

        Args:
            author_address: The address of the message author

        Returns:
            True if the message is from the bot
        """
        pass

    @abstractmethod
    def get_channel_type_upper(self) -> str:
        """Return the uppercase channel type for webhook filtering.

        Returns:
            Channel type string (e.g., "SMS", "CHAT")
        """
        pass

    @abstractmethod
    async def send_response(
        self,
        conversation_id: str,
        response: str | AsyncGenerator[str | dict[str, Any], None],
        role: str | None = None,
    ) -> None:
        pass

    def _is_duplicate_webhook(self, idempotency_token: str) -> bool:
        """Check if a webhook has already been processed using Twilio's idempotency token.

        Uses a sliding window approach with fixed capacity to track tokens.

        Args:
            idempotency_token: Twilio's i-twilio-idempotency-token header value

        Returns:
            True if the webhook has already been processed
        """
        if idempotency_token in self._processed_tokens:
            return True

        if len(self._processed_tokens) >= self._max_tracked_tokens:
            self._processed_tokens.popitem(last=False)

        self._processed_tokens[idempotency_token] = True
        return False

    def _is_event_for_this_channel(self, webhook_data: dict[str, Any]) -> bool:
        """Self-filtering: check if webhook event belongs to this channel.

        For COMMUNICATION_CREATED: require author.channel matches this channel type.
        For CONVERSATION_UPDATED: only process if conversation is tracked locally.
        Other events pass through.
        """
        event_type = webhook_data.get("eventType")
        event_data = webhook_data.get("data") or {}

        if event_type == "COMMUNICATION_CREATED":
            author_channel = event_data.get("author", {}).get("channel")
            if not author_channel:
                return False
            return bool(author_channel == self.get_channel_type_upper())

        if event_type == "CONVERSATION_UPDATED":
            conv_id = event_data.get("id")
            if conv_id and conv_id not in self._conversations:
                return False

        return True

    async def process_webhook(
        self, webhook_data: dict[str, Any], idempotency_token: str | None = None
    ) -> None:
        """Process messaging channel webhook event and manage conversation lifecycle.

        Handles:
        - PARTICIPANT_ADDED: Initialize conversation and track profile_id
        - COMMUNICATION_CREATED: Process incoming messages from customers
        - CONVERSATION_UPDATED: Clean up when conversation is closed

        Args:
            webhook_data: Raw webhook event data from Twilio
            idempotency_token: Optional Twilio idempotency token from request headers
        """
        if idempotency_token:
            if self._is_duplicate_webhook(idempotency_token):
                return

        if not self._is_event_for_this_channel(webhook_data):
            return

        event_type = webhook_data.get("eventType")
        event_data = webhook_data.get("data")

        if not isinstance(event_data, dict):
            self.logger.warning(
                "Webhook missing or malformed data field, skipping",
                event_type=event_type,
            )
            return

        if event_type == "PARTICIPANT_ADDED":
            self._handle_participant_added(event_data)
        elif event_type == "COMMUNICATION_CREATED":
            await self._handle_communication_created(event_data)
        elif event_type == "CONVERSATION_UPDATED":
            await self._handle_conversation_updated(event_data)

    def _handle_participant_added(self, event_data: Any) -> None:
        """Handle PARTICIPANT_ADDED event.

        Only processes CUSTOMER participants with addresses matching this channel type.
        """
        participant_data = ParticipantResponse.model_validate(event_data)
        conv_id = participant_data.conversation_id
        profile_id = participant_data.profile_id
        participant_type = participant_data.type

        if participant_type != "CUSTOMER":
            return

        has_matching_address = any(
            address.channel == self.get_channel_type_upper()
            for address in participant_data.addresses
        )

        if not has_matching_address:
            return

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
        """Handle COMMUNICATION_CREATED event (incoming message)."""
        communication_data = Communication.model_validate(event_data)
        conv_id = communication_data.conversation_id
        message_text = communication_data.content.text

        if (
            self.is_own_message(communication_data.author.address)
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

        # Store channelId in session metadata for Chat channel reply sending
        if communication_data.channel_id:
            session.metadata["channel_id"] = communication_data.channel_id

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
        """Handle CONVERSATION_UPDATED event.

        Only processes CLOSED status for conversations tracked by this channel.
        """
        conversation_data = ConversationResponse.model_validate(event_data)
        conv_id = conversation_data.id

        if (
            conversation_data.configuration_id == self.tac.config.conversation_configuration_id
            and conversation_data.status == "CLOSED"
            and conv_id in self._conversations
            and self._conversations[conv_id].channel == self.get_channel_name()
        ):
            await self._end_conversation(conv_id)
