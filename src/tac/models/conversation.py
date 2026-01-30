"""Pydantic models for Twilio Maestro Conversation API."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from tac.models.pagination import PaginationMeta


class ParticipantAddress(BaseModel):
    """Communication address for a conversation participant."""

    channel: Literal["VOICE", "SMS", "RCS", "EMAIL", "WHATSAPP", "CHAT", "API", "SYSTEM"] = Field(
        ..., description="The channel for Communication (VOICE, SMS, EMAIL, etc.)"
    )
    address: str = Field(..., description="The address value (phone number, email, etc.)")
    channel_id: Optional[str] = Field(
        default=None,
        alias="channelId",
        description="Channel-specific ID for correlating Communications",
    )

    model_config = {"populate_by_name": True}


class ConversationConfiguration(BaseModel):
    """Configuration settings for a conversation response."""

    unique_name: Optional[str] = Field(
        None,
        alias="uniqueName",
        description="A unique, URL-safe identifier for the Configuration",
    )
    friendly_name: Optional[str] = Field(
        None,
        alias="friendlyName",
        description="Human-readable description for the configuration",
    )
    conversation_grouping_type: Optional[str] = Field(
        None,
        alias="conversationGroupingType",
        description="Type of Conversation grouping strategy",
    )
    memory_store_id: Optional[str] = Field(
        None,
        alias="memoryStoreId",
        description="Memory Store ID for Profile Resolution",
    )
    channel_settings: Optional[dict[str, Any]] = Field(
        None,
        alias="channelSettings",
        description=(
            "Channel-specific configuration settings including timeout settings and capture rules"
        ),
    )
    status_callbacks: Optional[list[dict[str, Any]]] = Field(
        None,
        alias="statusCallbacks",
        description=(
            "List of default webhook configurations applied to "
            "conversations under this configuration"
        ),
    )
    intelligence_configuration_ids: Optional[list[str]] = Field(
        None,
        alias="intelligenceConfigurationIds",
        description="List of Intelligence Configuration IDs for this configuration",
    )

    model_config = {"populate_by_name": True}


class ConversationRequest(BaseModel):
    """Request payload for creating a conversation."""

    configuration_id: str = Field(
        ...,
        alias="configurationId",
        description="Configuration ID settings to use for this conversation",
    )
    name: Optional[str] = Field(default=None, description="Conversation name")

    model_config = {"populate_by_name": True}


class UpdateConversationRequest(BaseModel):
    """Request payload for updating a conversation."""

    status: Literal["ACTIVE", "INACTIVE", "CLOSED"] = Field(
        ..., description="Conversation state (ACTIVE/INACTIVE/CLOSED)"
    )
    name: Optional[str] = Field(default=None, description="Conversation name")

    model_config = {"populate_by_name": True}


class ConversationResponse(BaseModel):
    """Response from creating a conversation."""

    id: str = Field(..., description="Conversation ID")
    account_id: str = Field(..., alias="accountId", description="Twilio Account SID")

    status: Optional[str] = Field(None, description="Conversation status")
    name: Optional[str] = Field(None, description="Conversation name")
    configuration_id: Optional[str] = Field(
        None, alias="configurationId", description="Configuration used to create this conversation"
    )
    configuration: Optional[ConversationConfiguration] = Field(
        None, description="Conversation configuration settings"
    )
    created_at: Optional[str] = Field(None, alias="createdAt", description="Creation timestamp")
    updated_at: Optional[str] = Field(None, alias="updatedAt", description="Last update timestamp")

    model_config = {"populate_by_name": True}


class ParticipantRequest(BaseModel):
    """Request payload for creating a conversation participant."""

    name: Optional[str] = Field(default=None, description="Display name for the Participant")
    type: Optional[Literal["HUMAN_AGENT", "CUSTOMER", "AI_AGENT"]] = Field(
        default=None, description="Type of Participant in the Conversation"
    )
    profile_id: Optional[str] = Field(
        default=None, alias="profileId", description="Resolved segment profile"
    )
    addresses: Optional[list[ParticipantAddress]] = Field(
        default_factory=list, description="List of Communication addresses for the Participant"
    )

    model_config = {"populate_by_name": True}


class ParticipantResponse(BaseModel):
    """Response from creating a participant."""

    id: str = Field(..., description="Participant ID")
    conversation_id: str = Field(..., alias="conversationId", description="Conversation ID")
    account_id: str = Field(..., alias="accountId", description="Account ID")
    name: str = Field(..., description="Participant display name")
    type: Optional[Literal["HUMAN_AGENT", "CUSTOMER", "AI_AGENT"]] = Field(
        None, description="Type of Participant in the Conversation"
    )
    profile_id: Optional[str] = Field(None, alias="profileId", description="Segment profile ID")
    addresses: list[ParticipantAddress] = Field(
        default_factory=list, description="Communication addresses for this Participant"
    )
    created_at: Optional[str] = Field(
        None, alias="createdAt", description="Timestamp when this Participant was created"
    )
    updated_at: Optional[str] = Field(
        None, alias="updatedAt", description="Timestamp when this Participant was last updated"
    )

    model_config = {"populate_by_name": True}


class CommunicationParticipant(BaseModel):
    """Author or recipient in a communication."""

    address: str = Field(
        ...,
        max_length=254,
        description="Address of the participant (e.g., phone number, email address)",
        json_schema_extra={"example": "+12025551234"},
    )
    channel: Literal["VOICE", "SMS", "RCS", "EMAIL", "WHATSAPP", "CHAT", "API", "SYSTEM"] = Field(
        ..., description="The channel for the communication"
    )
    participant_id: Optional[str] = Field(
        default=None,
        alias="participantId",
        description="Participant identifier (optional)",
        json_schema_extra={"example": "comms_participant_00000000000000000000000000"},
    )
    delivery_status: Optional[
        Literal["INITIATED", "IN_PROGRESS", "DELIVERED", "COMPLETED", "FAILED"]
    ] = Field(
        default=None,
        alias="deliveryStatus",
        description="Delivery status of the Communication to this recipient",
    )

    model_config = {"populate_by_name": True}


class CommunicationContent(BaseModel):
    """Content of a communication."""

    type: Literal["TEXT", "TRANSCRIPTION"] = Field("TEXT", description="Content type")
    text: Optional[str] = Field(
        default=None,
        max_length=8388608,
        description="Primary text content (optional)",
        json_schema_extra={"example": "Hello, I need help with my account"},
    )
    transcription: Optional[dict[str, Any]] = Field(
        default=None,
        description="Transcription metadata (for TRANSCRIPTION type)",
    )

    model_config = {"populate_by_name": True}


class Communication(BaseModel):
    """A communication representing a message exchanged in a conversation."""

    id: str = Field(
        ...,
        description="Unique communication identifier",
        json_schema_extra={"example": "comms_communication_00000000000000000000000000"},
    )
    conversation_id: Optional[str] = Field(
        None, alias="conversationId", description="Conversation ID"
    )
    account_id: Optional[str] = Field(None, alias="accountId", description="Account ID")
    author: CommunicationParticipant = Field(..., description="Author of the communication")
    content: CommunicationContent = Field(..., description="Content of the communication")
    recipients: list[CommunicationParticipant] = Field(..., description="Communication recipients")
    channel_id: Optional[str] = Field(
        default=None,
        alias="channelId",
        description="Channel-specific ID (optional)",
        json_schema_extra={"example": "SM00000000000000000000000000000000"},
    )
    created_at: str = Field(
        ...,
        alias="createdAt",
        max_length=30,
        description="When communication was created",
        json_schema_extra={"example": "2025-01-15T10:15:30Z"},
    )
    updated_at: Optional[str] = Field(
        default=None,
        alias="updatedAt",
        max_length=30,
        description="When communication was last updated",
        json_schema_extra={"example": "2025-01-15T10:20:30Z"},
    )

    model_config = {"populate_by_name": True}


class CommunicationRequest(BaseModel):
    """Request payload for adding a communication."""

    author: CommunicationParticipant = Field(..., description="Author of the communication")
    content: CommunicationContent = Field(..., description="Content of the communication")
    recipients: list[CommunicationParticipant] = Field(
        ..., description="List of recipients for the communication"
    )
    channel_id: Optional[str] = Field(
        default=None,
        alias="channelId",
        description="Store Call ID/Record ID/etc. for channel reference",
    )

    model_config = {"populate_by_name": True}


class CommunicationsListResponse(BaseModel):
    """Response from list communications endpoint."""

    communications: list[Communication] = Field(..., description="List of communications")
    meta: PaginationMeta = Field(..., description="Pagination metadata")

    model_config = {"populate_by_name": True}


class ConversationsListResponse(BaseModel):
    """Response from list conversations endpoint."""

    conversations: list[ConversationResponse] = Field(..., description="List of conversations")
    meta: PaginationMeta = Field(..., description="Pagination metadata")

    model_config = {"populate_by_name": True}
