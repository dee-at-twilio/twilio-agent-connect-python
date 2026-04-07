"""SMS Channel implementation for TAC."""

from collections.abc import AsyncGenerator
from typing import Any

from pydantic import Field

from tac import TAC
from tac.channels.messaging import MessagingChannel, MessagingChannelConfig
from tac.models.conversation import (
    CommunicationContent,
    SendCommunicationParticipantAddress,
    SendCommunicationRequest,
)


class SMSChannelConfig(MessagingChannelConfig):
    """Configuration for SMS channel.

    Inherits dedup_capacity and auto_retrieve_memory from MessagingChannelConfig.
    """

    dedup_capacity: int = Field(
        default=10000,
        gt=0,
        description="Maximum number of idempotency tokens to track for deduplication",
    )


class SMSChannel(MessagingChannel):
    """SMS Channel for handling SMS-based conversations.

    Inherits shared messaging channel webhook processing from MessagingChannel
    and provides SMS-specific message sending and filtering.
    """

    def __init__(
        self,
        tac: TAC,
        config: SMSChannelConfig | dict[str, Any] | None = None,
    ):
        if isinstance(config, dict):
            config = SMSChannelConfig(**config)
        elif config is None:
            config = SMSChannelConfig()

        super().__init__(
            tac,
            dedup_capacity=config.dedup_capacity,
            auto_retrieve_memory=config.auto_retrieve_memory,
        )

        if not tac.config.twilio_phone_number:
            raise ValueError(
                "twilio_phone_number is required for SMS channel. "
                "Please set TWILIO_TAC_PHONE_NUMBER environment variable or "
                "provide twilio_phone_number in TACConfig."
            )

    def get_channel_name(self) -> str:
        return "sms"

    def get_channel_type_upper(self) -> str:
        return "SMS"

    def is_own_message(self, author_address: str) -> bool:
        return author_address == self.tac.config.twilio_phone_number

    async def send_response(
        self,
        conversation_id: str,
        response: str | AsyncGenerator[str | dict[str, Any], None],
        role: str | None = None,
    ) -> None:
        """Send SMS response using the Conversation Orchestrator Send API.

        Args:
            conversation_id: Conversation ID to send response to
            response: Message content (must be string for SMS)
            role: Optional message role (not used in SMS channel)

        Raises:
            TypeError: If response is not a string
        """
        if not isinstance(response, str):
            raise TypeError("SMS channel only supports string responses")

        try:
            participants = await self.tac.conversation_orchestrator_client.list_participants(
                conversation_id
            )
        except Exception as e:
            self.logger.error(
                "Failed to list participants",
                conversation_id=conversation_id,
                error=str(e),
            )
            return

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

            await self.tac.conversation_orchestrator_client.send_communication(
                conversation_id, send_request
            )

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
