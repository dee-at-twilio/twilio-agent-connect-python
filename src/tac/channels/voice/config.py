"""Voice channel configuration."""

from typing import Literal

from pydantic import BaseModel, Field

from tac.session import SessionManager, ThreadSafeSessionManager


class VoiceChannelConfig(BaseModel):
    """
    Configuration for Voice channel.

    Attributes:
        session_manager: SessionManager for tracking and canceling in-flight tasks.
            Defaults to ThreadSafeSessionManager for automatic task cancellation on
            interrupts and new prompts. Set to None only for debugging/testing.
        memory_retrieval: Memory retrieval strategy.
            - 'always': Fetch memory on every message using message content as query
            - 'once': Fetch memory once at conversation start without query
            - 'never': Do not fetch memory (default)
    """

    model_config = {"arbitrary_types_allowed": True}

    session_manager: SessionManager | None = Field(
        default_factory=ThreadSafeSessionManager,
        description=(
            "SessionManager for task cancellation. Defaults to ThreadSafeSessionManager. "
            "Set to None only for debugging/testing."
        ),
    )
    memory_retrieval: Literal["always", "once", "never"] = Field(
        default="never",
        description=(
            "Memory retrieval strategy: "
            "'always' - fetch memory on every message using message content as query, "
            "'once' - fetch memory once at conversation start without query, "
            "'never' - do not fetch memory"
        ),
    )
