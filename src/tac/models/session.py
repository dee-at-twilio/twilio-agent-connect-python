from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from tac.models.memory import ProfileResponse


class AuthorInfo(BaseModel):
    """Information about the author of a communication."""

    address: str = Field(..., description="Author address (phone number or identifier)")
    participant_id: Optional[str] = Field(
        default=None, description="Participant ID of the author in the conversation"
    )


class ConversationSession(BaseModel):
    """
    Context information for a conversation session that's passed to callbacks.

    This provides the necessary context for developers to handle memory-ready
    events and send responses back through the appropriate channel.
    """

    conversation_id: str = Field(..., description="Unique conversation identifier")
    profile_id: Optional[str] = Field(
        None, description="Profile ID associated with conversation (optional)"
    )
    channel: str = Field(..., description="Channel type (e.g., 'sms', 'voice')")
    started_at: datetime = Field(
        default_factory=datetime.now,
        description="When the conversation session was started",
    )
    profile: Optional[ProfileResponse] = Field(
        None, description="Profile information with traits (optional)"
    )
    author_info: Optional[AuthorInfo] = Field(
        None, description="Author information from communication event (optional)"
    )
    ai_agent_info: Optional[AuthorInfo] = Field(
        None, description="AI agent information from communication event (optional)"
    )
    metadata: dict = Field(
        default_factory=dict, description="Generic metadata storage for session-specific data"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)
