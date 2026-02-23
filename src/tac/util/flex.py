from typing import Optional

from twilio.twiml.voice_response import VoiceResponse

from tac import get_logger
from tac.models.handoff_data import HandoffData

logger = get_logger(__name__)


def handle_flex_handoff_logic(
    request_data: dict[str, str], flex_workflow_sid: Optional[str]
) -> str:
    """
    Encapsulates all Flex handoff logic for Twilio webhook.

    Args:
        request_data: Dict of form data from the request
        flex_workflow_sid: Flex workflow SID for routing

    Returns:
        TwiML/content string for Twilio response.

    Raises:
        ValueError: If workflow SID is missing or required data is absent.
        ValidationError: If handoff data is invalid JSON or fails model validation.
    """
    if flex_workflow_sid is None:
        raise ValueError("No Flex workflow SID configured")

    response = VoiceResponse()
    handoff_data_str: str = request_data.get("HandoffData", "")
    if handoff_data_str:
        handoff_data = HandoffData.model_validate_json(handoff_data_str)
        task_attributes = handoff_data.model_dump()
        response.enqueue(workflow_sid=flex_workflow_sid).task(task_attributes, priority=5)
        return str(response)
    else:
        if request_data.get("CallStatus") == "completed":
            return "Call Completed"
        else:
            raise ValueError("Handoff Data is Missing")
