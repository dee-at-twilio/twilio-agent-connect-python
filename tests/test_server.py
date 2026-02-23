"""Tests for TACServer module."""

import pytest

from tac import TAC
from tac.channels.websocket_protocol import WebSocketDisconnectError, WebSocketProtocol
from tac.server.config import TACServerConfig


def get_test_config() -> dict:
    """Get a valid test configuration."""
    return {
        "twilio_auth_token": "test_token_123",
        "environment": "prod",
        "conversation_service_sid": "IStest123",
        "twilio_account_sid": "ACtest123",
        "twilio_phone_number": "+15551234567",
    }


class TestTACServerConfig:
    """Test TACServerConfig."""

    def test_defaults(self) -> None:
        config = TACServerConfig(public_domain="example.ngrok.io")
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.public_domain == "example.ngrok.io"
        assert config.welcome_greeting == "Hello! How can I assist you today?"
        assert config.sms_webhook_path == "/webhook"
        assert config.twiml_path == "/twiml"
        assert config.websocket_path == "/ws"
        assert config.conversation_relay_callback_path == "/conversation-relay-callback"
        assert config.cintel_webhook_path is None

    def test_custom_paths(self) -> None:
        config = TACServerConfig(
            public_domain="my.domain.com",
            host="127.0.0.1",
            port=3000,
            sms_webhook_path="/sms",
            twiml_path="/voice/twiml",
            websocket_path="/voice/ws",
            cintel_webhook_path="/ci",
        )
        assert config.host == "127.0.0.1"
        assert config.port == 3000
        assert config.sms_webhook_path == "/sms"
        assert config.twiml_path == "/voice/twiml"
        assert config.websocket_path == "/voice/ws"
        assert config.cintel_webhook_path == "/ci"

    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TWILIO_TAC_VOICE_PUBLIC_DOMAIN", "my.ngrok.io")
        monkeypatch.setenv("TWILIO_TAC_SERVER_HOST", "127.0.0.1")
        monkeypatch.setenv("TWILIO_TAC_SERVER_PORT", "3000")
        config = TACServerConfig.from_env()
        assert config.public_domain == "my.ngrok.io"
        assert config.host == "127.0.0.1"
        assert config.port == 3000

    def test_from_env_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TWILIO_TAC_VOICE_PUBLIC_DOMAIN", raising=False)
        monkeypatch.delenv("TWILIO_TAC_SERVER_HOST", raising=False)
        monkeypatch.delenv("TWILIO_TAC_SERVER_PORT", raising=False)
        config = TACServerConfig.from_env()
        assert config.public_domain == ""
        assert config.host == "0.0.0.0"
        assert config.port == 8000


class TestWebSocketDisconnectError:
    """Test WebSocketDisconnectError."""

    def test_is_exception(self) -> None:
        err = WebSocketDisconnectError("test")
        assert isinstance(err, Exception)
        assert str(err) == "test"


class TestFastAPIWebSocketAdapter:
    """Test FastAPIWebSocketAdapter wraps FastAPI WebSocket correctly."""

    def test_import_and_register(self) -> None:
        from tac.server import FastAPIWebSocketAdapter

        assert FastAPIWebSocketAdapter is not None

    @pytest.mark.asyncio
    async def test_accept(self) -> None:
        from unittest.mock import AsyncMock

        from fastapi import WebSocket

        from tac.server import FastAPIWebSocketAdapter

        mock_ws = AsyncMock(spec=WebSocket)
        adapter = FastAPIWebSocketAdapter(mock_ws)
        await adapter.accept()
        mock_ws.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_receive_json(self) -> None:
        from unittest.mock import AsyncMock

        from fastapi import WebSocket

        from tac.server import FastAPIWebSocketAdapter

        mock_ws = AsyncMock(spec=WebSocket)
        mock_ws.receive_json.return_value = {"type": "setup"}
        adapter = FastAPIWebSocketAdapter(mock_ws)
        result = await adapter.receive_json()
        assert result == {"type": "setup"}

    @pytest.mark.asyncio
    async def test_receive_json_disconnect(self) -> None:
        from unittest.mock import AsyncMock

        from fastapi import WebSocket, WebSocketDisconnect

        from tac.server import FastAPIWebSocketAdapter

        mock_ws = AsyncMock(spec=WebSocket)
        mock_ws.receive_json.side_effect = WebSocketDisconnect()
        adapter = FastAPIWebSocketAdapter(mock_ws)
        with pytest.raises(WebSocketDisconnectError):
            await adapter.receive_json()

    @pytest.mark.asyncio
    async def test_send_text(self) -> None:
        from unittest.mock import AsyncMock

        from fastapi import WebSocket

        from tac.server import FastAPIWebSocketAdapter

        mock_ws = AsyncMock(spec=WebSocket)
        adapter = FastAPIWebSocketAdapter(mock_ws)
        await adapter.send_text("hello")
        mock_ws.send_text.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_send_text_disconnect(self) -> None:
        from unittest.mock import AsyncMock

        from fastapi import WebSocket, WebSocketDisconnect

        from tac.server import FastAPIWebSocketAdapter

        mock_ws = AsyncMock(spec=WebSocket)
        mock_ws.send_text.side_effect = WebSocketDisconnect()
        adapter = FastAPIWebSocketAdapter(mock_ws)
        with pytest.raises(WebSocketDisconnectError):
            await adapter.send_text("hello")

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        from unittest.mock import AsyncMock

        from fastapi import WebSocket

        from tac.server import FastAPIWebSocketAdapter

        mock_ws = AsyncMock(spec=WebSocket)
        adapter = FastAPIWebSocketAdapter(mock_ws)
        await adapter.close()
        mock_ws.close.assert_called_once()

    def test_isinstance_check(self) -> None:
        from unittest.mock import AsyncMock

        from fastapi import WebSocket

        from tac.server import FastAPIWebSocketAdapter

        mock_ws = AsyncMock(spec=WebSocket)
        adapter = FastAPIWebSocketAdapter(mock_ws)
        assert isinstance(adapter, WebSocketProtocol)


class TestTACServer:
    """Test TACServer route creation."""

    def test_create_app_voice_only(self) -> None:
        from tac.channels.voice import VoiceChannel
        from tac.server import TACServer

        tac = TAC(get_test_config())
        vc = VoiceChannel(tac=tac, auto_retrieve_memory=False)
        server = TACServer(
            tac=tac,
            config=TACServerConfig(public_domain="test.ngrok.io"),
            voice_channel=vc,
        )
        app = server._create_app()

        # Check that voice routes are registered
        route_paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/twiml" in route_paths
        assert "/ws" in route_paths
        assert "/conversation-relay-callback" in route_paths
        # No SMS route
        assert "/webhook" not in route_paths

    def test_create_app_sms_only(self) -> None:
        from tac.channels import SMSChannel
        from tac.server import TACServer

        tac = TAC(get_test_config())
        sms = SMSChannel(tac)
        server = TACServer(
            tac=tac,
            config=TACServerConfig(public_domain="test.ngrok.io"),
            sms_channel=sms,
        )
        app = server._create_app()

        route_paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/webhook" in route_paths
        # No voice routes
        assert "/twiml" not in route_paths
        assert "/ws" not in route_paths

    def test_create_app_with_cintel(self) -> None:
        from tac.server import TACServer

        tac = TAC(get_test_config())
        server = TACServer(
            tac=tac,
            config=TACServerConfig(
                public_domain="test.ngrok.io", cintel_webhook_path="/ci-webhook"
            ),
        )
        app = server._create_app()

        route_paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/ci-webhook" in route_paths

    def test_create_app_custom_paths(self) -> None:
        from tac.channels import SMSChannel
        from tac.channels.voice import VoiceChannel
        from tac.server import TACServer

        tac = TAC(get_test_config())
        server = TACServer(
            tac=tac,
            config=TACServerConfig(
                public_domain="test.ngrok.io",
                sms_webhook_path="/sms",
                twiml_path="/voice/twiml",
                websocket_path="/voice/ws",
                conversation_relay_callback_path="/voice/callback",
            ),
            voice_channel=VoiceChannel(tac=tac, auto_retrieve_memory=False),
            sms_channel=SMSChannel(tac),
        )
        app = server._create_app()

        route_paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/sms" in route_paths
        assert "/voice/twiml" in route_paths
        assert "/voice/ws" in route_paths
        assert "/voice/callback" in route_paths
