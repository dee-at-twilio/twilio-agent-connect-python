import asyncio
import json
from typing import Any, Optional

from fastapi import WebSocket

from tac import get_logger
from tac.models.handoff_data import HandoffData
from tac.tools.base import TACTool, function_tool

logger = get_logger(__name__)


def create_flex_escalation_tool(
    websocket: Optional[WebSocket] = None,
) -> TACTool:
    """
    Create a Flex escalation tool with injected websocket context.
    This tool, when called, will end the websocket and signal handoff intent.
    Args:
        websocket: Active WebSocket connection (if any)
    Returns:
        TACTool instance for escalation
    """

    @function_tool(
        name="flex_escalate_to_human",
        description="Escalate the conversation to a human agent in Flex with optional reason.",
    )
    def flex_escalate_to_human(reason: str = "User requested human help") -> dict[str, Any]:
        """
        Escalate the conversation to a human agent in Flex, ending websocket and signaling handoff
        Args:
            reason: The reason for escalation (default: user requested human help).
        Returns:
            dict with escalation status and reason.
        """
        if websocket is not None:
            handoff_data = HandoffData(reason="handoff", call_summary=reason, sentiment="neutral")
            asyncio.create_task(
                websocket.send_text(
                    json.dumps({"type": "end", "handoffData": handoff_data.model_dump_json()})
                )
            )
        return {"status": "escalated", "reason": reason}

    return flex_escalate_to_human
