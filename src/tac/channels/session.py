"""
Session management utilities for agents
"""

import asyncio
from typing import Optional


class SessionState:
    """
    Manages session state for voice conversations with streaming task tracking.

    Tracks the active streaming task to enable cancellation when:
    - A new prompt arrives (cancel previous incomplete response)
    - An interrupt occurs (user speaks over the agent)
    - The session ends (cleanup)
    """

    def __init__(self) -> None:
        self.stream_task: Optional[asyncio.Task] = (
            None  # Track active streaming task for cancellation
        )
