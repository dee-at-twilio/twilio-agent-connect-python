from pydantic import BaseModel, Field


class HandoffData(BaseModel):
    reason: str = Field(
        ..., description="Reason for handoff, e.g. 'handoff' or escalation trigger."
    )
    call_summary: str = Field(..., description="Summary of the call or reason for escalation.")
    sentiment: str = Field(
        ...,
        description="Sentiment of the conversation at handoff, e.g. 'neutral', 'negative'.",
    )
