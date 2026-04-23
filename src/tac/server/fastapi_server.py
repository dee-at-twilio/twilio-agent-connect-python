"""TACFastAPIServer: Batteries-included FastAPI server for TAC channels.

This module provides FastAPIWebSocketAdapter (bridges FastAPI WebSocket to
WebSocketProtocol) and TACFastAPIServer (creates a FastAPI app with routes for
voice, messaging, and CI webhooks).

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
from tac.tools.handoff import studio_voice_handoff_url

if TYPE_CHECKING:
    from tac.channels.messaging import MessagingChannel
    from tac.channels.voice import VoiceChannel

try:
    import uvicorn
    from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
    from fastapi.responses import JSONResponse, Response
except ImportError as e:
    raise ImportError(
        "TACFastAPIServer requires FastAPI and uvicorn. Install with: pip install tac[server]"
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


class TACFastAPIServer:
    """Batteries-included FastAPI server for TAC channels.

    Creates (or adopts) a FastAPI app and registers routes for voice, messaging,
    and CI webhooks, then starts uvicorn when start() is called.

    Customization:
        - Pass your own FastAPI instance via ``app=...`` to control
          construction-time settings (title, version, lifespan, docs_url, ...).
          TAC routes are registered onto it immediately in ``__init__``.
        - Or mutate ``server.app`` after construction: add middleware,
          exception handlers, routers, or custom routes — before calling
          ``start()``.

    Example:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware

        app = FastAPI(title="My Service", version="1.2.0")
        app.add_middleware(CORSMiddleware, allow_origins=["*"])

        server = TACFastAPIServer(tac=tac, voice_channel=vc, app=app)

        @server.app.get("/health")
        async def health() -> dict:
            return {"status": "ok"}

        server.start()
    """

    def __init__(
        self,
        tac: TAC,
        voice_channel: VoiceChannel | None = None,
        messaging_channels: list[MessagingChannel] | None = None,
        config: TACServerConfig | None = None,
        app: FastAPI | None = None,
    ) -> None:
        self.tac = tac
        self.config = config or TACServerConfig.from_env()
        self.voice_channel = voice_channel
        self.messaging_channels: list[MessagingChannel] = messaging_channels or []
        self.app: FastAPI = app if app is not None else FastAPI(title="TAC Server")
        self._register_routes(self.app)

    def _register_routes(self, app: FastAPI) -> None:
        """Register TAC routes (messaging, voice, CI) onto the given FastAPI app."""
        config = self.config

        if self.messaging_channels:
            channels = self.messaging_channels

            @app.post(config.messaging_webhook_path)
            async def messaging_webhook(request: Request) -> JSONResponse:
                """Handle incoming messaging webhooks from Twilio."""
                try:
                    form_data = await request.json()
                    webhook_data = dict(form_data)
                    idempotency_token = request.headers.get("i-twilio-idempotency-token")
                    for channel in channels:
                        asyncio.create_task(
                            channel.process_webhook(webhook_data, idempotency_token)
                        )
                    return JSONResponse(content={"status": "ok"}, status_code=200)
                except Exception as e:
                    logger.error("Messaging webhook error", error=str(e), exc_info=True)
                    return JSONResponse(
                        content={"status": "error", "message": str(e)}, status_code=400
                    )
        else:
            logger.warning("No messaging channels configured — messaging webhook route disabled")

        if self.voice_channel is not None:
            vc = self.voice_channel

            if not config.public_domain:
                logger.warning(
                    "public_domain is not set — voice URLs will be malformed. "
                    "Set TWILIO_VOICE_PUBLIC_DOMAIN environment variable."
                )

            @app.post(config.twiml_path)
            async def post_twiml() -> Response:
                """Generate TwiML for incoming voice calls."""
                websocket_url = f"wss://{config.public_domain}{config.websocket_path}"
                if self.tac.config.studio_handoff_flow_sid:
                    action_url = studio_voice_handoff_url(
                        self.tac.config.account_sid,
                        self.tac.config.studio_handoff_flow_sid,
                    )
                else:
                    action_url = (
                        f"https://{config.public_domain}{config.conversation_relay_callback_path}"
                    )

                twiml = await vc.handle_incoming_call(
                    options={
                        "websocket_url": websocket_url,
                        "action_url": action_url,
                        "welcome_greeting": config.welcome_greeting,
                    },
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

    def start(self) -> None:
        """Start uvicorn serving ``self.app``."""
        logger.info(f"Starting TAC FastAPI Server on {self.config.host}:{self.config.port}")
        uvicorn.run(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level="info",
            access_log=False,  # Disable verbose HTTP request logs
        )
