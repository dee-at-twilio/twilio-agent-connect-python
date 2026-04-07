"""Voice channel configuration."""

from typing import Optional

from pydantic import BaseModel, Field

from tac.session import SessionManager


class VoiceChannelConfig(BaseModel):
    """
    Configuration for Voice channel.

    Attributes:
        session_manager: Optional SessionManager for tracking and
            canceling in-flight streaming tasks. The SessionManager
            encapsulates the stream_generator for LLM responses.
            If provided, enables task cancellation on interrupts
            and new prompts.
        auto_retrieve_memory: If True, automatically retrieve memory
            before invoking the on_message_ready callback. Default is False.
            Set to True to enable automatic memory retrieval.
    """

    model_config = {"arbitrary_types_allowed": True}

    session_manager: Optional[SessionManager] = Field(
        default=None,
        description="SessionManager for tracking and canceling in-flight streaming tasks",
    )
    auto_retrieve_memory: bool = Field(
        default=False,
        description="Automatically retrieve memory before on_message_ready callback",
    )
