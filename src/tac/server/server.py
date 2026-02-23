"""TACServer: Batteries-included FastAPI server for TAC channels.

This module provides FastAPIWebSocketAdapter (bridges FastAPI WebSocket to
WebSocketProtocol) and TACServer (creates a FastAPI app with routes for
voice, SMS, and CI webhooks).

Requires: pip install tac[server]
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from tac.channels.websocket_protocol import WebSocketDisconnectError
from tac.core.logging import get_logger
from tac.core.tac import TAC
from tac.server.config import TACServerConfig

if TYPE_CHECKING:
    from tac.channels.sms import SMSChannel
    from tac.channels.voice import VoiceChannel

try:
    import uvicorn
    from fastapi import FastAPI, Form, Request, WebSocket, WebSocketDisconnect
    from fastapi.responses import JSONResponse, Response
except ImportError as e:
    raise ImportError(
        "TACServer requires FastAPI and uvicorn. Install with: pip install tac[server]"
    ) from e

logger = get_logger(__name__)


class FastAPIWebSocketAdapter:
    """Adapts a FastAPI WebSocket to satisfy WebSocketProtocol.

    Converts FastAPI's WebSocketDisconnect into WebSocketDisconnectError
    so that VoiceChannel's framework-agnostic exception handling works.
    """

    def __init__(self, websocket: WebSocket) -> None:
        self._ws = websocket

    async def accept(self) -> None:
        await self._ws.accept()

    async def receive_json(self) -> Any:
        try:
            return await self._ws.receive_json()
        except WebSocketDisconnect:
            raise WebSocketDisconnectError("WebSocket disconnected") from None

    async def send_text(self, data: str) -> None:
        try:
            await self._ws.send_text(data)
        except WebSocketDisconnect:
            raise WebSocketDisconnectError("WebSocket disconnected") from None

    async def close(self) -> None:
        await self._ws.close()


class TACServer:
    """Batteries-included FastAPI server for TAC channels.

    Creates a FastAPI app with routes for voice, SMS, and CI webhooks,
    then starts uvicorn. This replaces VoiceChannel.start() and provides
    a single entry point for multi-channel servers.
    """

    def __init__(
        self,
        tac: TAC,
        voice_channel: VoiceChannel | None = None,
        sms_channel: SMSChannel | None = None,
        config: TACServerConfig | None = None,
    ) -> None:
        self.tac = tac
        self.config = config or TACServerConfig.from_env()
        self.voice_channel = voice_channel
        self.sms_channel = sms_channel

    def _create_app(self) -> FastAPI:
        """Create and configure the FastAPI application with routes."""
        app = FastAPI(title="TAC Server")
        config = self.config

        if self.sms_channel is not None:
            sms = self.sms_channel

            @app.post(config.sms_webhook_path)
            async def sms_webhook(request: Request) -> JSONResponse:
                """Handle incoming SMS webhooks from Twilio."""
                try:
                    form_data = await request.json()
                    webhook_data = dict(form_data)
                    idempotency_token = request.headers.get("i-twilio-idempotency-token")
                    asyncio.create_task(sms.process_webhook(webhook_data, idempotency_token))
                    return JSONResponse(content={"status": "ok"}, status_code=200)
                except Exception as e:
                    logger.error("SMS webhook error", error=str(e), exc_info=True)
                    return JSONResponse(
                        content={"status": "error", "message": str(e)}, status_code=400
                    )

        if self.voice_channel is not None:
            vc = self.voice_channel

            if not config.public_domain:
                logger.warning(
                    "public_domain is not set — voice URLs will be malformed. "
                    "Set TWILIO_TAC_VOICE_PUBLIC_DOMAIN environment variable."
                )

            @app.post(config.twiml_path)
            async def post_twiml(
                From: str = Form(...),  # noqa: N803
                To: str = Form(...),  # noqa: N803
                CallSid: str = Form(...),  # noqa: N803
            ) -> Response:
                """Generate TwiML for incoming voice calls."""
                websocket_url = f"wss://{config.public_domain}{config.websocket_path}"
                callback_url = (
                    f"https://{config.public_domain}{config.conversation_relay_callback_path}"
                )

                twiml = await vc.handle_incoming_call(
                    to_number=To,
                    from_number=From,
                    options={
                        "websocket_url": websocket_url,
                        "action_url": callback_url,
                        "welcome_greeting": config.welcome_greeting,
                    },
                    call_sid=CallSid,
                )
                return Response(content=twiml, media_type="application/xml")

            @app.websocket(config.websocket_path)
            async def websocket_endpoint(websocket: WebSocket) -> None:
                """Handle voice WebSocket connections."""
                adapter = FastAPIWebSocketAdapter(websocket)
                await vc.handle_websocket(adapter)

            @app.post(config.conversation_relay_callback_path)
            async def conversation_relay_callback(request: Request) -> Response:
                """Handle ConversationRelay callback webhook from Twilio."""
                form_data = await request.form()
                payload_dict = {key: str(value) for key, value in form_data.items()}
                try:
                    result = await vc.handle_conversation_relay_callback(payload_dict)
                    if result is not None:
                        return Response(content=result, media_type="text/xml")
                    return Response(content="OK", media_type="text/plain")
                except ValidationError as e:
                    logger.error("Invalid callback payload", error=str(e))
                    return Response(content=str(e), media_type="text/plain", status_code=400)
                except ValueError as e:
                    logger.error("Callback error", error=str(e))
                    return Response(content=str(e), media_type="text/plain", status_code=400)
                except Exception as e:
                    logger.error(f"Error handling callback: {e}", exc_info=True)
                    return Response(
                        content="Internal Server Error",
                        media_type="text/plain",
                        status_code=500,
                    )

        if config.cintel_webhook_path is not None:
            tac = self.tac

            @app.post(config.cintel_webhook_path)
            async def cintel_webhook(request: Request) -> JSONResponse:
                """Handle Conversation Intelligence webhook events."""
                payload = await request.json()
                result = await tac.process_cintel_event(payload)
                return JSONResponse(content=result.model_dump())

        return app

    def start(self) -> None:
        """Create the FastAPI app and start uvicorn."""
        app = self._create_app()
        logger.info(f"Starting TAC Server on {self.config.host}:{self.config.port}")
        uvicorn.run(
            app,
            host=self.config.host,
            port=self.config.port,
            log_level="info",
        )
