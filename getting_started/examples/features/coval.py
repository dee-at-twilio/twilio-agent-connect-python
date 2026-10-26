"""
Coval trace export

Sends a TAC app's OpenTelemetry spans to Coval, so each simulation result's
"OTel Traces" card shows that call's trace. Add it to any voice app with:

    import coval

    coval.setup(server.app, voice_channel)

TAC records the call's spans (install with `pip install twilio-agent-connect[tracing]`);
add your own anywhere with the plain OpenTelemetry API and they join the call's trace:

    from opentelemetry import trace

    with trace.get_tracer(__name__).start_as_current_span("lookup_order"):
        ...

Coval matches a trace to a simulation by its ID, which reaches the app one of
two ways:

    Inbound (Coval calls the agent). Twilio PSTN strips Coval's SIP header, so
    Coval POSTs the ID just before dialing; it's matched by caller number.
        pre_call_webhook_url: https://<TWILIO_VOICE_PUBLIC_DOMAIN>/coval/register-simulation

    Outbound (the agent calls Coval). Coval POSTs the number to dial and the ID.
        trigger_call_endpoint: https://<TWILIO_VOICE_PUBLIC_DOMAIN>/coval/trigger-call
        trigger_call_payload: {"simulation_output_id": "{{simulation_output_id}}"}

Spans from calls that aren't Coval simulations are dropped. Enabled only when
COVAL_API_KEY is set; unset it to turn Coval off. The /coval/* endpoints are
unauthenticated, so anyone with the URL can trigger calls; use for testing only.
Pending simulation IDs are held in process memory, so run a single instance.
"""

import os
import time
from collections.abc import Sequence

from fastapi import FastAPI, HTTPException, Request
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult

from tac.channels.voice import VoiceChannel
from tac.models.outbound import InitiateVoiceConversationOptions

COVAL_TRACES_URL = "https://api.coval.dev/v1/traces"
PENDING_TTL_SECONDS = 300

# Inbound: (simulation_output_id, from_number, registered_at), oldest first
pending_simulations: list[tuple[str, str, float]] = []
# Outbound: call_sid -> simulation_output_id
outbound_simulations: dict[str, str] = {}
# trace_id -> simulation_output_id, for calls in progress
simulation_by_trace: dict[int, str] = {}


def take_simulation_id(call_sid: str | None, caller: str | None) -> str | None:
    """Pop the simulation ID for this call: by Call SID, by caller, else the oldest."""
    if call_sid in outbound_simulations:
        return outbound_simulations.pop(call_sid)
    cutoff = time.time() - PENDING_TTL_SECONDS
    pending_simulations[:] = [p for p in pending_simulations if p[2] >= cutoff]
    for i, (simulation_id, from_number, _) in enumerate(pending_simulations):
        if from_number == caller:
            del pending_simulations[i]
            return simulation_id
    return pending_simulations.pop(0)[0] if pending_simulations else None


class SimulationMatcher(SpanProcessor):
    """Tags each call's trace with its Coval simulation ID as the call starts."""

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        if span.parent is not None or span.name != "conversation":
            return
        attributes = span.attributes or {}
        direction = str(attributes.get("call.direction", "")).lower()
        caller = attributes.get("call.to" if direction == "outbound" else "call.from")
        simulation_id = take_simulation_id(
            str(attributes.get("call.sid", "")), str(caller) if caller else None
        )
        if simulation_id:
            simulation_by_trace[span.context.trace_id] = simulation_id


class CovalExporter(SpanExporter):
    """Exports each call's spans with its simulation ID as the X-Simulation-Id header."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        by_simulation: dict[str, list[ReadableSpan]] = {}
        for span in spans:
            if span.context is None:
                continue
            trace_id = span.context.trace_id
            simulation_id = simulation_by_trace.get(trace_id)
            if simulation_id:
                by_simulation.setdefault(simulation_id, []).append(span)
            if span.parent is None:
                # The root ends when the call does, after its other spans, so
                # it arrives in the call's last batch.
                simulation_by_trace.pop(trace_id, None)
        result = SpanExportResult.SUCCESS
        for simulation_id, simulation_spans in by_simulation.items():
            exporter = OTLPSpanExporter(
                endpoint=COVAL_TRACES_URL,
                headers={"X-API-Key": self._api_key, "X-Simulation-Id": simulation_id},
                timeout=30,
            )
            if exporter.export(simulation_spans) is not SpanExportResult.SUCCESS:
                result = SpanExportResult.FAILURE
            exporter.shutdown()
        return result

    def shutdown(self) -> None:
        pass


def setup(app: FastAPI, voice_channel: VoiceChannel) -> None:
    """Send call traces to Coval and mount Coval's pre-call and trigger endpoints.

    Does nothing unless COVAL_API_KEY is set, so the key is the on/off switch.
    """
    api_key = os.environ.get("COVAL_API_KEY")
    if not api_key:
        return
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: "tac-voice-agent"}))
    provider.add_span_processor(SimulationMatcher())
    # Batches on a background thread, so calls never block on Coval.
    provider.add_span_processor(BatchSpanProcessor(CovalExporter(api_key)))
    trace.set_tracer_provider(provider)

    async def read_simulation_id(request: Request) -> tuple[dict, str]:
        data = await request.json()
        simulation_id = data.get("simulation_output_id")
        if not simulation_id:
            raise HTTPException(status_code=400, detail="simulation_output_id is required")
        return data, simulation_id

    @app.post("/coval/register-simulation")
    async def register_simulation(request: Request) -> dict:
        """Coval's pre-call webhook: queue the simulation ID for the next inbound call."""
        data, simulation_id = await read_simulation_id(request)
        pending_simulations.append((simulation_id, data.get("from_number", ""), time.time()))
        return {"status": "ok", "queued": len(pending_simulations)}

    @app.post("/coval/trigger-call")
    async def trigger_call(request: Request) -> dict:
        """Coval's outbound trigger: call the simulated customer."""
        data, simulation_id = await read_simulation_id(request)
        phone_number = data.get("phone_number")
        if not phone_number:
            raise HTTPException(status_code=400, detail="phone_number is required")
        result = await voice_channel.initiate_outbound_conversation(
            InitiateVoiceConversationOptions(to=phone_number)
        )
        outbound_simulations[result.call_sid] = simulation_id
        return {"status": "ok", "call_sid": result.call_sid}
