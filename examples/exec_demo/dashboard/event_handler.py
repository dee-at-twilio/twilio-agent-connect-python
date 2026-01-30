"""Dashboard event handler for capturing and streaming log events."""

import logging
import re
from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional

from pydantic import BaseModel, Field

# Event queue for storing dashboard events
_event_queue: Optional[deque] = None
_queue_lock = Lock()

# Maximum number of events to keep in queue
MAX_EVENTS = 100


class DashboardEvent(BaseModel):
    """Model for dashboard events."""

    timestamp: str
    event_type: str
    conversation_id: Optional[str] = None
    channel: Optional[str] = None
    profile_id: Optional[str] = None
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


# Pattern mapping for log message to event type
EVENT_PATTERNS = {
    "USER MESSAGE": "user_message",
    "MEMORY | Retrieved": "memory",
    "AI AGENT | Processing": "ai_processing",
    "AI RESPONSE": "ai_response",
    "HANDOFF": "handoff",
    "CONVERSATION | Started": "conversation_started",
    "INCOMING CALL": "call_started",
    "WEBSOCKET | Connected": "websocket_connected",
    "CALL SETUP": "call_setup",
}


class DashboardLogHandler(logging.Handler):
    """Custom logging handler that captures events for dashboard streaming."""

    def __init__(self) -> None:
        """Initialize the dashboard log handler."""
        super().__init__()
        self.setLevel(logging.INFO)

    def emit(self, record: logging.LogRecord) -> None:
        """
        Process log record and push to event queue.

        Args:
            record: Log record to process
        """
        try:
            # Only process logs from tac.* loggers
            if not record.name.startswith("tac."):
                return

            # Extract structured context from log record
            conversation_id = getattr(record, "conversation_id", None)
            profile_id = getattr(record, "profile_id", None)
            channel = getattr(record, "channel", None)

            # Determine event type from log message
            message = record.getMessage()
            event_type = self._determine_event_type(message, record.levelname)

            # Skip if we can't determine event type
            if not event_type:
                return

            # Extract message content (remove quotes if present)
            clean_message = self._extract_message_content(message)

            # Create dashboard event
            event = DashboardEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                event_type=event_type,
                conversation_id=conversation_id,
                channel=channel,
                profile_id=profile_id,
                message=clean_message,
                metadata={
                    "level": record.levelname,
                    "logger": record.name,
                },
            )

            # Push to queue
            self._push_event(event)

        except Exception:
            # Silently ignore errors in dashboard logging to avoid breaking core functionality
            pass

    def _determine_event_type(self, message: str, level: str) -> Optional[str]:
        """
        Determine event type from log message.

        Args:
            message: Log message text
            level: Log level name

        Returns:
            Event type string or None
        """
        # Check for error events first
        if level == "ERROR":
            return "error"

        # Check against known patterns
        for pattern, event_type in EVENT_PATTERNS.items():
            if pattern in message:
                return event_type

        return None

    def _extract_message_content(self, message: str) -> str:
        """
        Extract clean content from log message.

        Args:
            message: Log message text

        Returns:
            Extracted content or original message
        """
        # Remove the separator lines
        message = message.replace("=" * 80, "").strip()

        # Extract content after the | separator
        if " | " in message:
            parts = message.split(" | ", 1)
            if len(parts) > 1:
                return parts[1].strip()

        # Try to extract content within quotes (legacy support)
        quote_match = re.search(r'"([^"]+)"', message)
        if quote_match:
            return quote_match.group(1)

        return message

    def _push_event(self, event: DashboardEvent) -> None:
        """
        Push event to queue in thread-safe manner.

        Args:
            event: Dashboard event to push
        """
        global _event_queue

        if _event_queue is None:
            return

        with _queue_lock:
            _event_queue.append(event)


def get_event_queue() -> deque:
    """
    Get the global event queue.

    Returns:
        Event queue (deque)
    """
    global _event_queue

    if _event_queue is None:
        with _queue_lock:
            if _event_queue is None:
                _event_queue = deque(maxlen=MAX_EVENTS)

    return _event_queue


def setup_dashboard_logging() -> None:
    """Set up dashboard logging by attaching custom handler to TAC logger."""
    global _event_queue

    # Initialize event queue
    with _queue_lock:
        _event_queue = deque(maxlen=MAX_EVENTS)

    # Create and attach dashboard handler to the 'tac' logger
    # (not root logger, since tac logger has propagate=False)
    handler = DashboardLogHandler()
    tac_logger = logging.getLogger("tac")
    tac_logger.addHandler(handler)
