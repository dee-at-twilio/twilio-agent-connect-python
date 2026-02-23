"""Tests for Twilio webhook signature validation."""

from unittest.mock import MagicMock

from twilio.request_validator import RequestValidator

from tac.server.webhook import _build_url, validate_twilio_webhook


class TestValidateTwilioWebhook:
    """Test validate_twilio_webhook function."""

    def test_valid_form_body_signature(self) -> None:
        """Test validation passes with correct signature for form-encoded body."""
        auth_token = "test_auth_token"
        body = {"From": "+15551234567", "To": "+15559876543", "CallSid": "CA123"}

        validator = RequestValidator(auth_token)
        url = "https://example.com/twiml"
        signature = validator.compute_signature(url, body)

        request = MagicMock()
        request.headers = {
            "X-Twilio-Signature": signature,
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "example.com",
        }
        request.url.path = "/twiml"
        request.url.query = ""

        assert validate_twilio_webhook(request, auth_token, body) is True

    def test_invalid_signature_returns_false(self) -> None:
        """Test validation fails with incorrect signature."""
        auth_token = "test_auth_token"
        body = {"From": "+15551234567", "Body": "Hello"}

        request = MagicMock()
        request.headers = {
            "X-Twilio-Signature": "invalid_signature",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "example.com",
        }
        request.url.path = "/webhook"
        request.url.query = ""

        assert validate_twilio_webhook(request, auth_token, body) is False

    def test_missing_signature_returns_false(self) -> None:
        """Test validation fails when X-Twilio-Signature header is missing."""
        auth_token = "test_auth_token"
        body = {"From": "+15551234567", "Body": "Hello"}

        request = MagicMock()
        request.headers = {}
        request.url.path = "/webhook"
        request.url.query = ""
        request.url.scheme = "https"

        assert validate_twilio_webhook(request, auth_token, body) is False

    def test_valid_string_body_signature(self) -> None:
        """Test validation passes with correct signature for JSON/string body."""
        auth_token = "test_auth_token"
        # For string bodies, Twilio signs with empty params dict
        body_str = '{"event": "onMessageAdded", "conversationSid": "CH123"}'

        validator = RequestValidator(auth_token)
        url = "https://example.com/webhook"
        # String bodies are validated with empty params
        signature = validator.compute_signature(url, {})

        request = MagicMock()
        request.headers = {
            "X-Twilio-Signature": signature,
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "example.com",
        }
        request.url.path = "/webhook"
        request.url.query = ""

        assert validate_twilio_webhook(request, auth_token, body_str) is True

    def test_invalid_string_body_signature(self) -> None:
        """Test validation fails with incorrect signature for JSON/string body."""
        auth_token = "test_auth_token"
        body_str = '{"event": "onMessageAdded"}'

        request = MagicMock()
        request.headers = {
            "X-Twilio-Signature": "invalid_signature",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "example.com",
        }
        request.url.path = "/webhook"
        request.url.query = ""

        assert validate_twilio_webhook(request, auth_token, body_str) is False


class TestBuildUrl:
    """Test _build_url function."""

    def test_uses_forwarded_headers(self) -> None:
        """Test that X-Forwarded-* headers are used."""
        request = MagicMock()
        request.headers = {
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "example.com",
        }
        request.url.path = "/webhook"
        request.url.query = ""

        url = _build_url(request)
        assert url == "https://example.com/webhook"

    def test_falls_back_to_request_url_scheme(self) -> None:
        """Test fallback to request.url.scheme when X-Forwarded-Proto is missing."""
        request = MagicMock()
        request.headers = {"Host": "example.com"}
        request.url.path = "/webhook"
        request.url.query = ""
        request.url.scheme = "http"

        url = _build_url(request)
        assert url == "http://example.com/webhook"

    def test_handles_comma_separated_headers(self) -> None:
        """Test handling of comma-separated X-Forwarded-* headers from multiple proxies."""
        request = MagicMock()
        request.headers = {
            "X-Forwarded-Proto": "https, http, http",
            "X-Forwarded-Host": "public.example.com, internal-alb.local, 10.0.0.1",
        }
        request.url.path = "/webhook"
        request.url.query = ""

        url = _build_url(request)
        assert url == "https://public.example.com/webhook"

    def test_includes_query_string(self) -> None:
        """Test that query string is included in URL."""
        request = MagicMock()
        request.headers = {
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "example.com",
        }
        request.url.path = "/webhook"
        request.url.query = "foo=bar&baz=qux"

        url = _build_url(request)
        assert url == "https://example.com/webhook?foo=bar&baz=qux"

    def test_falls_back_to_request_url_netloc(self) -> None:
        """Test fallback to request.url.netloc when both Host headers are missing."""
        request = MagicMock()
        request.headers = {}
        request.url.path = "/webhook"
        request.url.query = ""
        request.url.scheme = "https"
        request.url.netloc = "localhost:8000"

        url = _build_url(request)
        assert url == "https://localhost:8000/webhook"
