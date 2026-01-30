"""
Session management utilities for streaming agents with concurrency control.

Provides channel-agnostic session tracking and task lifecycle management for
streaming interactions. For example, in voice channels this enables canceling
in-flight LLM tasks when users interrupt the agent mid-response.
"""

import threading
from collections.abc import AsyncGenerator
from typing import Any, Callable, Protocol, Union, runtime_checkable

from .session import SessionState


@runtime_checkable
class SessionManager(Protocol):
    """
    Protocol for managing streaming sessions with task cancellation support.

    Implementations of this protocol manage session state and provide streaming
    capabilities with support for cancelling in-flight async tasks. This enables
    responsive interactions across different channels where:
    - New requests can cancel previous incomplete responses
    - Sessions are properly cleaned up with task cancellation
    - Concurrent sessions are tracked independently

    Example use cases:
    - Voice channels: Cancel LLM streaming when user interrupts mid-response
    - Chat channels: Cancel typing indicators or long-running operations
    - Any channel with async streaming that needs graceful cancellation
    """

    def get_or_create_session(self, session_id: str) -> SessionState: ...
    def has_session(self, session_id: str) -> bool: ...
    def remove_session(self, session_id: str) -> None: ...
    def get_all_session_ids(self) -> list[str]: ...
    def __len__(self) -> int: ...

    def stream_response(
        self, prompt: str, session_id: str
    ) -> AsyncGenerator[Union[str, dict[str, Any]], None]:
        """
        Stream response for the given prompt and session.

        The generator returned by this method will be wrapped in an asyncio task
        that can be cancelled when interrupts occur or new prompts arrive.

        Args:
            prompt: User's prompt/query
            session_id: Unique session identifier

        Yields:
            Response chunks (str or dict with metadata). Plain strings are common,
            but dict format allows passing additional metadata like timestamps.
        """
        ...


class ThreadSafeSessionManager:
    """
    Thread-safe manager for streaming sessions with task lifecycle management.
    Provides concurrency control for multiple simultaneous connections.

    This manager tracks active async tasks per session, enabling cancellation
    when needed:
    - A new request arrives (cancels previous in-flight task)
    - An interrupt occurs (e.g., voice channel user interrupts mid-response)
    - The session ends (cleanup with graceful task cancellation)

    The implementation is channel-agnostic and works with any async streaming
    pattern that benefits from task cancellation and session isolation.
    """

    def __init__(
        self,
        stream_generator: Callable[[str, str], AsyncGenerator[Union[str, dict[str, Any]], None]],
    ):
        """
        Initialize session manager with streaming capability.

        Args:
            stream_generator: Async function that takes (prompt, session_id)
                and yields response chunks (str or dict). This generator
                MUST support cancellation - when the asyncio task running it is
                cancelled, it should stop generating and clean up gracefully.
                This enables interrupting in-flight operations when new requests
                arrive or sessions end.
        """
        self._sessions: dict[str, SessionState] = {}
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        self._stream_generator = stream_generator

    def get_or_create_session(self, session_id: str) -> SessionState:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionState()
            return self._sessions[session_id]

    def has_session(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._sessions

    def remove_session(self, session_id: str) -> None:
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]

    def get_all_session_ids(self) -> list[str]:
        with self._lock:
            return list(self._sessions.keys())

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)

    async def stream_response(
        self, prompt: str, session_id: str
    ) -> AsyncGenerator[Union[str, dict[str, Any]], None]:
        """
        Stream response for the given prompt and session.

        This method delegates to the stream_generator provided at initialization.
        The underlying generator task can be cancelled when:
        - A new request arrives (channel cancels the previous stream_task)
        - An interrupt occurs (e.g., user speaks over the agent in voice channels)
        - The session ends (cleanup)

        Args:
            prompt: User's prompt/query
            session_id: Unique session identifier

        Yields:
            Response chunks from the streaming source (str or dict with metadata)
        """
        async for chunk in self._stream_generator(prompt, session_id):
            yield chunk
