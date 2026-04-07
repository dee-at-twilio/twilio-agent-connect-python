"""Chat Channel implementation for TAC."""

from collections.abc import AsyncGenerator
from typing import Any

from pydantic import Field

from tac import TAC
from tac.channels.messaging import MessagingChannel, MessagingChannelConfig
from tac.models.conversation import (
    CommunicationContent,
    ParticipantAddress,
    SendCommunicationParticipantAddress,
    SendCommunicationRequest,
)


class ChatChannelConfig(MessagingChannelConfig):
    """Configuration for Chat channel.

    Attributes:
        agent_address: Chat agent identity string used to identify the bot's messages.
    """

    agent_address: str = Field(
        default="ai-assistant",
        description="Chat agent identity string for bot message filtering",
    )


class ChatChannel(MessagingChannel):
    """Chat Channel for handling web chat conversations.

    Uses identity-based addressing instead of phone numbers.
    Automatically creates AI_AGENT participant if needed (lazy creation)
    and manages conversation lifecycle through Conversation Orchestrator webhooks.
    """

    def __init__(
        self,
        tac: TAC,
        config: ChatChannelConfig | dict[str, Any] | None = None,
    ):
        if isinstance(config, dict):
            config = ChatChannelConfig(**config)
        elif config is None:
            config = ChatChannelConfig()

        super().__init__(
            tac,
            dedup_capacity=config.dedup_capacity,
            auto_retrieve_memory=config.auto_retrieve_memory,
        )
        self.agent_address = config.agent_address

    def get_channel_name(self) -> str:
        return "chat"

    def get_channel_type_upper(self) -> str:
        return "CHAT"

    def is_own_message(self, author_address: str) -> bool:
        return author_address == self.agent_address

    async def send_response(
        self,
        conversation_id: str,
        response: str | AsyncGenerator[str | dict[str, Any], None],
        role: str | None = None,
    ) -> None:
        """Send chat response using the Conversation Orchestrator Send API.

        Lazily creates an AI_AGENT participant if one doesn't exist yet.

        Args:
            conversation_id: Conversation ID to send response to
            response: Message content (must be string for Chat)
            role: Optional message role (not used in Chat channel)

        Raises:
            TypeError: If response is not a string
        """
        if not isinstance(response, str):
            raise TypeError("Chat channel only supports string responses")

        session = self._conversations.get(conversation_id)
        if not session:
            self.logger.error(
                "No active session found",
                conversation_id=conversation_id,
            )
            return

        if not session.author_info:
            self.logger.error(
                "No author info found - no inbound message received yet",
                conversation_id=conversation_id,
            )
            return

        chat_channel_sid = session.metadata.get("channel_id")
        if not chat_channel_sid or not isinstance(chat_channel_sid, str):
            self.logger.error(
                "No channelId found in session metadata",
                conversation_id=conversation_id,
            )
            return

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

        agent_participant = next(
            (p for p in participants if p.type == "AI_AGENT"),
            None,
        )

        # Lazy AI_AGENT creation if not found
        if not agent_participant:
            self.logger.debug(
                "No AI_AGENT participant found, creating one",
                conversation_id=conversation_id,
                agent_address=self.agent_address,
            )
            try:
                agent_participant = await self.tac.conversation_orchestrator_client.add_participant(
                    conversation_id,
                    addresses=[
                        ParticipantAddress(
                            channel="CHAT",
                            address=self.agent_address,
                            channel_id=chat_channel_sid,
                        )
                    ],
                    participant_type="AI_AGENT",
                )
                self.logger.info(
                    "Created AI_AGENT participant",
                    conversation_id=conversation_id,
                    participant_id=agent_participant.id,
                )
            except Exception:
                # Race condition: another process may have created it
                self.logger.warning(
                    "Failed to create AI_AGENT, retrying participant list",
                    conversation_id=conversation_id,
                )
                try:
                    retried = await self.tac.conversation_orchestrator_client.list_participants(
                        conversation_id
                    )
                    agent_participant = next(
                        (p for p in retried if p.type == "AI_AGENT"),
                        None,
                    )
                except Exception as e:
                    self.logger.error(
                        "Failed to retry listing participants",
                        conversation_id=conversation_id,
                        error=str(e),
                    )
                    return

                if not agent_participant:
                    self.logger.error(
                        "Failed to create or find AI_AGENT participant",
                        conversation_id=conversation_id,
                    )
                    return

        try:
            send_request = SendCommunicationRequest(
                author=SendCommunicationParticipantAddress(
                    address=self.agent_address,
                    channel="CHAT",
                    participant_id=agent_participant.id,
                ),
                content=CommunicationContent(type="TEXT", text=response),
                recipients=[
                    SendCommunicationParticipantAddress(
                        address=session.author_info.address,
                        channel="CHAT",
                        participant_id=session.author_info.participant_id,
                    )
                ],
                channel_id=chat_channel_sid,
            )

            await self.tac.conversation_orchestrator_client.send_communication(
                conversation_id, send_request
            )

            self.logger.debug(
                "Sent chat response via Send API",
                conversation_id=conversation_id,
                channel_id=chat_channel_sid,
            )
        except Exception as e:
            self.logger.error(
                "Failed to send communication",
                conversation_id=conversation_id,
                error=str(e),
                exc_info=True,
            )
