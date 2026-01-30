"""Base channel interface for TAC channels."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from tac import TAC
from tac.core.logging import get_logger
from tac.models.memory import MemoryRetrievalResponse
from tac.models.session import ConversationSession


class BaseChannel(ABC):
    """
    Abstract base class for TAC channels.

    Channels handle protocol-specific webhook processing and response delivery
    for different communication channels (SMS, Voice, etc.).

    This class provides common conversation lifecycle management that is shared
    across all channel types.
    """

    def __init__(self, tac: TAC, auto_retrieve_memory: bool = True):
        """
        Initialize base channel.

        Args:
            tac: TAC instance for memory/context operations
            auto_retrieve_memory: If True (default), automatically retrieve memory
                before invoking the on_message_ready callback. Set to False to
                disable automatic memory retrieval (e.g., for latency-sensitive
                voice applications).
        """
        self.tac = tac
        self.logger = get_logger(__name__)

        # Auto-disable memory retrieval if memory is not configured
        if auto_retrieve_memory and not tac.is_twilio_memory_enabled():
            self.logger.warning(
                "auto_retrieve_memory is enabled but Twilio Memory is not configured. "
                "Disabling automatic memory retrieval. "
                "To enable memory retrieval, set twilio_memory_config in TACConfig with "
                "memory_store_id, api_key, and api_token."
            )
            auto_retrieve_memory = False

        self.auto_retrieve_memory = auto_retrieve_memory

        # Track active conversations (shared across all channel types)
        self._conversations: dict[str, ConversationSession] = {}

    @abstractmethod
    async def process_webhook(self, webhook_data: dict[str, Any]) -> None:
        """
        Process incoming webhook event from Twilio.

        This method should:
        1. Parse and validate webhook data
        2. Handle conversation lifecycle (start, message, end)
        3. Trigger memory retrieval via TAC
        4. Invoke registered callbacks

        Args:
            webhook_data: Raw webhook event data from Twilio
        """
        pass

    @abstractmethod
    async def send_response(
        self, conversation_id: str, response: str, role: Optional[str] = None
    ) -> None:
        """
        Send response back through the channel.

        Args:
            conversation_id: Conversation ID to send response to
            response: Message content to send
            role: Optional message role (e.g., 'assistant', 'user', 'system')
        """
        pass

    @abstractmethod
    def get_channel_name(self) -> str:
        """
        Get the channel name identifier.

        Returns:
            Channel name (e.g., 'sms', 'voice')
        """
        # TODO: Parse Channel Type based on webhook data
        pass

    async def _start_conversation(
        self,
        conv_id: str,
        profile_id: Optional[str] = None,
    ) -> None:
        """
        Initialize new conversation session and fetch profile if available.

        Args:
            conv_id: Conversation ID
            profile_id: Profile ID for the conversation (optional)
        """
        if conv_id in self._conversations:
            self.logger.warning(
                "Conversation already exists, skipping initialization",
                conversation_id=conv_id,
                channel=self.get_channel_name(),
            )
            return

        # Fetch profile if profile_id is provided
        profile = None
        if profile_id:
            profile = await self.tac.fetch_profile(profile_id)

        # Store conversation session
        self._conversations[conv_id] = ConversationSession(
            conversation_id=conv_id,
            profile_id=profile_id,
            channel=self.get_channel_name(),
            profile=profile,
            author_info=None,
            ai_agent_info=None,
        )

        self.logger.info(
            f"CONVERSATION | Started {self.get_channel_name().upper()} conversation",
            conversation_id=conv_id,
            profile_id=profile_id,
        )

    def _end_conversation(self, conv_id: str) -> None:
        """
        Clean up conversation session.

        Args:
            conv_id: Conversation ID
        """
        if conv_id in self._conversations:
            del self._conversations[conv_id]
            self.logger.debug(
                "Ended conversation",
                conversation_id=conv_id,
                channel=self.get_channel_name(),
            )
        else:
            self.logger.warning(
                "Attempted to end unknown conversation",
                conversation_id=conv_id,
                channel=self.get_channel_name(),
            )

    async def _retrieve_memory_if_enabled(
        self, session: ConversationSession, query: Optional[str], conv_id: str
    ) -> Optional[MemoryRetrievalResponse]:
        """
        Retrieve memory if auto_retrieve_memory is enabled and Twilio Memory is configured.

        This method handles the common logic for memory retrieval across all channels,
        including error handling and debug logging.

        Args:
            session: Conversation session containing profile_id and context
            query: Optional query string for memory retrieval
            conv_id: Conversation ID for logging

        Returns:
            MemoryRetrievalResponse if memory was retrieved, None otherwise
        """
        memory_response = None
        if self.auto_retrieve_memory and self.tac.is_twilio_memory_enabled():
            try:
                memory_response = await self.tac.retrieve_memory(session, query=query)
                self.logger.debug(
                    "Memory retrieved",
                    conversation_id=conv_id,
                )
            except Exception as e:
                self.logger.error(
                    "Failed to retrieve memory",
                    conversation_id=conv_id,
                    error=str(e),
                    exc_info=True,
                )
                # Continue without memory rather than failing the entire message processing
        elif not self.auto_retrieve_memory:
            self.logger.debug(
                "Auto memory retrieval disabled, skipping memory retrieval",
                conversation_id=conv_id,
            )
        else:
            self.logger.debug(
                "Twilio Memory not enabled, skipping memory retrieval",
                conversation_id=conv_id,
            )
        return memory_response
