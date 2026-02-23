"""
TAC Multi-Channel Demo - Executable Example

A complete multi-channel demo showing how to:
1. Set up TAC with SMS and Voice channels
2. Process webhooks from Twilio (SMS and Voice)
3. Retrieve memories and context
4. Process messages with LLM (OpenAI)
5. Send responses back through SMS and Voice
6. Handle WebSocket connections for Voice streaming

This demo demonstrates TAC's channel-agnostic architecture with both SMS and Voice support.
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn

# Dashboard imports
from dashboard.event_handler import get_event_queue, setup_dashboard_logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from llm_service import create_llm_service
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionUserMessageParam,
)

from tac import TAC, TACConfig
from tac.channels import SMSChannel
from tac.channels.voice import VoiceChannel
from tac.core.logging import get_logger, setup_logging
from tac.models.session import ConversationSession
from tac.models.tac import TACMemoryResponse
from tac.server import FastAPIWebSocketAdapter
from tac.server.webhook import validate_twilio_webhook
from tac.util.flex import handle_flex_handoff_logic

load_dotenv()

# Get the directory where this script is located
BASE_DIR = Path(__file__).resolve().parent

# Configure structured logging using TAC's logging utilities
setup_logging(log_level="INFO", log_format="console")

logger = get_logger(__name__)

# Initialize TAC - see examples/README.md for configuration
tac = TAC(config=TACConfig.from_env())

# IMPORTANT: Setup dashboard logging AFTER TAC initialization
# (TAC calls setup_logging() which clears handlers)
setup_dashboard_logging()

# Global variables for channels and services (initialized in lifespan)
voice_channel = VoiceChannel(tac)
sms_channel = SMSChannel(tac)
llm_service = None  # Will be initialized in lifespan


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for async initialization."""
    global llm_service

    # Startup: Initialize LLM service with async factory function
    logger.info("[STARTUP] Initializing LLM service...")
    llm_service = await create_llm_service(tac)
    logger.info("[STARTUP] LLM service initialized")
    logger.info(
        "[HINT] View live dashboard at http://localhost:8000/dashboard to see how TAC works"
    )

    yield

    # Shutdown: Cleanup if needed
    logger.info("[SHUTDOWN] Shutting down...")


app = FastAPI(
    title="TAC Multi-Channel Demo",
    description="Multi-channel demo using Twilio Agent Connect",
    version="1.0.0",
    lifespan=lifespan,
)

# User-managed conversation history
# Key: conversation_id, Value: list of messages
conversation_messages: dict[str, list[ChatCompletionMessageParam]] = {}


async def flex_handoff_handler(request_data: dict[str, str]) -> str:
    """
    Handler for Flex handoff requests.

    This function is called when the AI agent triggers a handoff to a human agent.
    It processes the handoff logic and returns the TwiML response content.
    """
    return handle_flex_handoff_logic(
        request_data, flex_workflow_sid=os.environ.get("TWILIO_TAC_VOICE_HANDOFF_FLEX_WORKFLOW_SID")
    )


# Register message ready callback
async def handle_message_ready(
    user_message: str,
    context: ConversationSession,
    memory_response: Optional[TACMemoryResponse],
) -> None:
    """
    Callback invoked when a message is ready to be processed.

    This demonstrates how to process memories and respond to messages.
    Uses LLM service with user-managed message history.
    Memory response is optional - SMS channel provides it, Voice channel does not.
    """
    conv_id = context.conversation_id
    try:
        # Initialize conversation history if needed
        if conv_id not in conversation_messages:
            conversation_messages[conv_id] = []

        # Add current user message
        user_msg: ChatCompletionUserMessageParam = {"role": "user", "content": user_message}
        conversation_messages[conv_id].append(user_msg)

        # Log incoming message with clear separator
        logger.info(
            f"\n{'=' * 80}\nUSER MESSAGE | {user_message[:50]}{'...' if len(user_message) > 50 else ''}",
            conversation_id=conv_id,
            channel=context.channel,
            profile_id=context.profile_id,
        )

        if memory_response:
            # Build memory summary
            memory_items = []
            if memory_response.observations:
                memory_items.append(f"{len(memory_response.observations)} observations")
            if memory_response.summaries:
                memory_items.append(f"{len(memory_response.summaries)} summaries")
            if memory_response.communications:
                memory_items.append(f"{len(memory_response.communications)} communications")
            memory_summary = ", ".join(memory_items) if memory_items else "context"
            logger.info(
                f"MEMORY | Retrieved {memory_summary}",
                conversation_id=conv_id,
                channel=context.channel,
            )

        # Get the active websocket for this conversation if it's a voice channel
        active_websocket = (
            voice_channel.get_websocket(conv_id) if context.channel == "voice" else None
        )

        # Process message with LLM
        logger.info(
            "AI AGENT | Processing message...",
            conversation_id=conv_id,
            channel=context.channel,
        )
        llm_response = await llm_service.process_message(
            user_message=user_message,
            memory_response=memory_response,
            context=context,
            websocket=active_websocket,
            conversation_history=conversation_messages[conv_id],
        )

        # Send response through appropriate channel
        if llm_response:
            if context.channel == "voice":
                await voice_channel.send_response(
                    context.conversation_id, llm_response, role="assistant"
                )
            elif context.channel == "sms":
                await sms_channel.send_response(
                    context.conversation_id, llm_response, role="assistant"
                )
            else:
                logger.error(
                    "Unknown channel",
                    conversation_id=conv_id,
                    channel=context.channel,
                )
                return

            # Log response with preview
            response_preview = (
                llm_response[:100] + "..." if len(llm_response) > 100 else llm_response
            )
            logger.info(
                f"AI RESPONSE | {response_preview}",
                conversation_id=conv_id,
                channel=context.channel,
                profile_id=context.profile_id,
            )

            # Check if there's a pending handoff in session metadata
            if "pending_handoff" in context.metadata:
                pending_handoff = context.metadata["pending_handoff"]
                handoff_data_json = pending_handoff.get("handoff_data")

                if context.channel == "voice" and handoff_data_json:
                    try:
                        logger.info(
                            f"\n{'=' * 80}\nHANDOFF | Transferring to human agent...",
                            conversation_id=conv_id,
                        )
                        await active_websocket.send_text(
                            json.dumps({"type": "end", "handoffData": handoff_data_json})
                        )
                        # Clear the metadata after processing
                        del context.metadata["pending_handoff"]
                    except Exception as e:
                        logger.error(
                            "Handoff failed",
                            conversation_id=conv_id,
                            error=str(e),
                            exc_info=True,
                        )

            # Store assistant response in history
            assistant_msg: ChatCompletionAssistantMessageParam = {
                "role": "assistant",
                "content": llm_response,
            }
            conversation_messages[conv_id].append(assistant_msg)
    except Exception as e:
        logger.error(
            "Error processing message",
            conversation_id=conv_id,
            error=str(e),
            exc_info=True,
        )


tac.on_message_ready(handle_message_ready)

tac.on_handoff(flex_handoff_handler)


@app.post("/webhook")
async def webhook_handler(request: Request) -> JSONResponse:
    """Handle incoming webhooks from Twilio (all conversation events).

    Returns 200 immediately to prevent Twilio retries, then processes webhook
    asynchronously. Uses Twilio's i-twilio-idempotency-token header for
    deduplication in case retries still occur.
    """
    try:
        raw_body = await request.body()
        body_str = raw_body.decode("utf-8")

        # Validate Twilio webhook signature
        if not validate_twilio_webhook(request, tac.config.twilio_auth_token, body_str):
            logger.warning("Invalid Twilio webhook signature")
            return JSONResponse(content={"error": "Invalid signature"}, status_code=403)

        webhook_data = json.loads(body_str)

        # Extract idempotency token from headers for deduplication
        idempotency_token = request.headers.get("i-twilio-idempotency-token")

        # Fire and forget - process webhook completely asynchronously
        # Pass idempotency token for deduplication
        asyncio.create_task(sms_channel.process_webhook(webhook_data, idempotency_token))

        # Return 200 immediately without waiting for processing
        return JSONResponse(content={"status": "ok"}, status_code=200)

    except Exception as e:
        logger.error("SMS webhook error", error=str(e), exc_info=True)
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=400)


@app.post("/twiml")
async def post_twiml(request: Request) -> Response:
    """Generate TwiML for Twilio voice calls."""
    form_data = await request.form()
    form_dict = {key: str(value) for key, value in form_data.items()}

    # Validate Twilio webhook signature
    if not validate_twilio_webhook(request, tac.config.twilio_auth_token, form_dict):
        logger.warning("Invalid Twilio webhook signature for /twiml")
        return Response(content="Invalid signature", status_code=403)

    from_number_raw = form_dict.get("From")
    to_number_raw = form_dict.get("To")
    call_sid_raw = form_dict.get("CallSid")

    if not from_number_raw or not to_number_raw or not call_sid_raw:
        logger.warning(
            "Missing required Twilio form fields for /twiml",
            from_number=from_number_raw,
            to_number=to_number_raw,
            call_sid=call_sid_raw,
        )
        return Response(
            content="Missing required Twilio fields (From, To, CallSid)",
            status_code=400,
        )

    from_number = str(from_number_raw)
    to_number = str(to_number_raw)
    call_sid = str(call_sid_raw)

    logger.info(
        f"\n{'=' * 80}\nINCOMING CALL | {from_number} → {to_number}",
        call_sid=call_sid,
    )

    # Get WebSocket URL from environment
    public_domain = os.environ.get("TWILIO_TAC_VOICE_PUBLIC_DOMAIN", "")
    websocket_url = f"wss://{public_domain}/ws"
    callback_url = f"https://{public_domain}/conversation-relay-callback"

    # Generate TwiML with conversation and participant setup
    # From contains the caller's phone number, To contains the Twilio number
    twiml = await voice_channel.handle_incoming_call(
        to_number=to_number,
        from_number=from_number,
        options={
            "websocket_url": websocket_url,
            "action_url": callback_url,
        },
        call_sid=call_sid,
    )

    logger.info("CALL SETUP | TwiML generated, connecting WebSocket...", call_sid=call_sid)
    return Response(content=twiml, media_type="application/xml")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Handle voice streaming WebSocket connection."""
    logger.info("WEBSOCKET | Connected - streaming ready")
    adapter = FastAPIWebSocketAdapter(websocket)
    await voice_channel.handle_websocket(adapter)
    logger.info("WEBSOCKET | Disconnected")


@app.post("/conversation-relay-callback")
async def conversation_relay_callback(request: Request) -> Response:
    """Handle ConversationRelay callback webhook from Twilio."""
    form_data = await request.form()
    form_dict = {key: str(value) for key, value in form_data.items()}

    # Validate Twilio webhook signature
    if not validate_twilio_webhook(request, tac.config.twilio_auth_token, form_dict):
        logger.warning("Invalid Twilio webhook signature for /conversation-relay-callback")
        return Response(content="Invalid signature", status_code=403)

    try:
        result = await voice_channel.handle_conversation_relay_callback(form_dict)
        if result is not None:
            return Response(content=result, media_type="text/xml")
        return Response(content="OK", media_type="text/plain")
    except Exception as e:
        logger.error(f"Error handling callback: {e}", exc_info=True)
        return Response(content=str(e), media_type="text/plain", status_code=400)


# Dashboard routes
# Mount static files for dashboard JavaScript
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "dashboard" / "static")), name="static")


@app.get("/dashboard")
async def dashboard_page() -> FileResponse:
    """Serve the dashboard HTML page."""
    return FileResponse(
        BASE_DIR / "dashboard" / "templates" / "dashboard.html", media_type="text/html"
    )


@app.get("/events")
async def event_stream(request: Request) -> StreamingResponse:
    """SSE endpoint for streaming dashboard events."""

    async def event_generator():
        import asyncio

        queue = get_event_queue()
        try:
            while True:
                if queue:
                    event = queue.popleft()
                    yield f"data: {event.model_dump_json()}\n\n"
                else:
                    # Send keepalive comment every 15 seconds
                    yield ": keepalive\n\n"
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            logger.info("Dashboard client disconnected")
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    # Configure uvicorn logging to reduce noise
    uvicorn_log_config = uvicorn.config.LOGGING_CONFIG
    uvicorn_log_config["formatters"]["default"]["fmt"] = "%(levelprefix)s %(message)s"
    uvicorn_log_config["formatters"]["access"]["fmt"] = (
        '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="warning",
        access_log=False,
        log_config=uvicorn_log_config,
    )
