"""TAC unified response models."""

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

from tac.models.conversation import Communication, Transcription
from tac.models.memory import (
    MemoryCommunication,
    MemoryRetrievalResponse,
    ObservationInfo,
    SummaryInfo,
)


class TACCommunicationAuthor(BaseModel):
    """
    Unified author model with all fields from both Memory and Maestro APIs.
    """

    # Common fields (both APIs)
    address: str = Field(..., description="Address of the communication author")
    channel: Literal["VOICE", "SMS", "RCS", "EMAIL", "WHATSAPP", "CHAT", "API", "SYSTEM"] = Field(
        ..., description="Channel type"
    )

    # Maestro-only fields
    participant_id: Optional[str] = Field(
        default=None, alias="participantId", description="Participant ID (Maestro only)"
    )
    delivery_status: Optional[
        Literal["INITIATED", "IN_PROGRESS", "DELIVERED", "COMPLETED", "FAILED"]
    ] = Field(
        default=None,
        alias="deliveryStatus",
        description="Delivery status (Maestro recipients only)",
    )

    # Memory-only fields
    id: Optional[str] = Field(default=None, description="Author ID (Memory only)")
    name: Optional[str] = Field(default=None, description="Display name (Memory only)")
    type: Optional[Literal["HUMAN_AGENT", "CUSTOMER", "AI_AGENT"]] = Field(
        default=None, description="Author type (Memory only)"
    )
    profile_id: Optional[str] = Field(
        default=None, alias="profileId", description="Profile ID (Memory only)"
    )

    model_config = {"populate_by_name": True}


class TACCommunicationContent(BaseModel):
    """
    Unified content model with all fields from both Memory and Maestro APIs.
    """

    type: Optional[Literal["TEXT", "TRANSCRIPTION"]] = Field(
        default=None, description="Content type discriminator (Maestro only)"
    )
    text: Optional[str] = Field(default=None, description="Message text content")
    transcription: Optional[Transcription] = Field(
        default=None, description="Transcription metadata (Maestro only, when type=TRANSCRIPTION)"
    )

    model_config = {"populate_by_name": True}


class TACCommunication(BaseModel):
    """
    Unified communication model with all fields from both Memory and Maestro APIs.

    Provides complete access to all communication fields regardless of the source.
    Fields not available from a particular API will be None.
    """

    # Common fields (both APIs)
    id: str = Field(..., description="Communication identifier")
    author: TACCommunicationAuthor = Field(..., description="Communication author")
    content: TACCommunicationContent = Field(..., description="Communication content")
    recipients: list[TACCommunicationAuthor] = Field(
        default_factory=list, description="Communication recipients"
    )
    channel_id: Optional[str] = Field(
        default=None,
        alias="channelId",
        description="Channel-specific reference ID, when provided by the source API",
    )
    created_at: Optional[str] = Field(
        default=None, alias="createdAt", description="When communication was created"
    )
    updated_at: Optional[str] = Field(
        default=None, alias="updatedAt", description="When communication was last updated"
    )

    # Maestro-only fields
    conversation_id: Optional[str] = Field(
        default=None, alias="conversationId", description="Conversation ID (Maestro only)"
    )
    account_id: Optional[str] = Field(
        default=None, alias="accountId", description="Account ID (Maestro only)"
    )

    model_config = {"populate_by_name": True}


class TACMemoryResponse:
    """
    Unified response wrapper for TAC.retrieve_memory().

    Provides a consistent interface for accessing memory data regardless of whether
    Memory API is configured or falling back to Maestro Communications API.

    Memory configured:
    - observations, summaries, communications all populated
    - communications include Memory-specific fields (author id, name, type, profile_id)

    Maestro fallback:
    - observations and summaries are empty lists
    - communications include Maestro-specific fields (conversation_id, account_id, etc.)
    """

    def __init__(self, data: Union[MemoryRetrievalResponse, list[Communication]]):
        """
        Initialize wrapper with either Memory or Maestro data.

        Args:
            data: Either MemoryRetrievalResponse (Memory) or list[Communication] (Maestro)
        """
        self._data = data
        self._is_memory = isinstance(data, MemoryRetrievalResponse)

        # Convert communications once during initialization for better performance
        if self._is_memory:
            memory_data: MemoryRetrievalResponse = data  # type: ignore[assignment]
            memory_comms = memory_data.communications or []
            self._communications = [self._convert_communication(comm) for comm in memory_comms]
        else:
            maestro_comms: list[Communication] = data  # type: ignore[assignment]
            self._communications = [self._convert_communication(comm) for comm in maestro_comms]

    @property
    def observations(self) -> list[ObservationInfo]:
        """
        Get observation memories.

        Returns:
            List of observations if Memory is configured, empty list for Maestro fallback
        """
        if self._is_memory:
            return self._data.observations  # type: ignore[union-attr]
        return []

    @property
    def summaries(self) -> list[SummaryInfo]:
        """
        Get summary memories.

        Returns:
            List of summaries if Memory is configured, empty list for Maestro fallback
        """
        if self._is_memory:
            return self._data.summaries  # type: ignore[union-attr]
        return []

    @property
    def communications(self) -> list[TACCommunication]:
        """
        Get communications in unified format with all available fields.

        Communications are converted to a common format during initialization that includes
        all fields from both Memory and Maestro APIs. Fields not available from a particular
        API will be None.

        Returns:
            List of unified communications with all available fields
        """
        return self._communications

    @property
    def has_memory_features(self) -> bool:
        """
        Check if Memory API is configured and providing full features.

        Returns:
            True if Memory is configured (observations/summaries available),
            False if using Maestro fallback (only communications available)
        """
        return self._is_memory

    @property
    def raw_data(self) -> Union[MemoryRetrievalResponse, list[Communication]]:
        """
        Access raw underlying data for advanced use cases.

        Use this when you need access to all fields from the original API responses,
        not just the simplified common fields.

        Returns:
            Either MemoryRetrievalResponse or list[Communication] depending on configuration
        """
        return self._data

    def _convert_communication(
        self, comm: Union[MemoryCommunication, Communication]
    ) -> TACCommunication:
        """
        Convert Memory or Maestro communication to unified format.

        Pydantic automatically handles missing fields by setting them to None.
        """
        data = comm.model_dump(by_alias=True)

        data["author"] = TACCommunicationAuthor(**data["author"])
        data["content"] = TACCommunicationContent(**data["content"])
        data["recipients"] = [TACCommunicationAuthor(**r) for r in data["recipients"]]

        return TACCommunication(**data)
