from typing import Optional

from fastapi.datastructures import FormData
from fastapi.responses import Response
from pydantic import ValidationError
from twilio.twiml.voice_response import VoiceResponse

from tac import get_logger
from tac.models.handoff_data import HandoffData

logger = get_logger(__name__)


def handle_flex_handoff_logic(request_data: FormData, flex_workflow_sid: Optional[str]) -> Response:
    """
    Encapsulates all Flex handoff logic for Twilio webhook.
    Args:
        request_data: FormData from FastAPI request
    Returns:
        FastAPI Response for Twilio
    """
    if flex_workflow_sid is None:
        if logger:
            logger.error("No Flex workflow SID configured")
        return Response(content="Invalid handoff data", media_type="text/plain", status_code=400)

    response = VoiceResponse()
    handoff_data_raw = request_data.get("HandoffData")
    handoff_data_str: str = str(handoff_data_raw) if handoff_data_raw is not None else ""
    if handoff_data_str:
        try:
            handoff_data = HandoffData.model_validate_json(handoff_data_str)
        except ValidationError as e:
            if logger:
                logger.error(f"Invalid handoff data: {e}")
            return Response(
                content="Invalid handoff data", media_type="text/plain", status_code=400
            )
        task_attributes = handoff_data.model_dump()
        response.enqueue(workflow_sid=flex_workflow_sid).task(task_attributes, priority=5)
        return Response(content=str(response), media_type="text/xml")
    else:
        if request_data.get("CallStatus") == "completed":
            return Response(content="Call Completed", media_type="text/xml", status_code=200)
        else:
            return Response(
                content="Handoff Data is Missing", media_type="text/xml", status_code=400
            )
