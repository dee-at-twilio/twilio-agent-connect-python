"""Webhook signature validation for Twilio webhooks.

This module provides utilities for validating Twilio webhook signatures
in FastAPI applications. It handles proxy headers (X-Forwarded-Proto,
X-Forwarded-Host) for environments like ngrok.

Requires: pip install tac[server]
"""

from collections.abc import Mapping
from typing import Union

from fastapi import Request
from twilio.request_validator import RequestValidator


def validate_twilio_webhook(
    request: Request,
    auth_token: str,
    body: Union[str, Mapping[str, str]],
) -> bool:
    """Validate a Twilio webhook signature.

    Verifies the X-Twilio-Signature header matches the expected signature for the
    request URL and body. Handles proxy headers (X-Forwarded-Proto, X-Forwarded-Host)
    for environments like ngrok.

    Args:
        request: FastAPI Request object containing headers and URL info.
        auth_token: Twilio Auth Token used for signature validation.
        body: Request body - pass str for JSON bodies (SMS webhooks from Maestro,
              where signature is computed with empty POST params), or pass a mapping
              for form-encoded bodies (Voice webhooks, where params are included).
              Accepts dict, FormData, or any Mapping[str, str].

    Returns:
        True if signature is valid, False otherwise.
    """
    signature = request.headers.get("X-Twilio-Signature")
    if not signature:
        return False

    url = _build_url(request)

    validator = RequestValidator(auth_token)

    # For JSON bodies (string), Twilio signs with URL only (empty params).
    # For form-encoded bodies (mapping), params are included in signature.
    params = dict(body) if isinstance(body, Mapping) else {}
    result: bool = validator.validate(url, params, signature)
    return result


def _build_url(request: Request) -> str:
    """Build the full URL from request, handling proxy headers.

    When behind a proxy (like ngrok), the request URL may have incorrect scheme
    or host. This function checks X-Forwarded-Proto and X-Forwarded-Host headers
    to reconstruct the original URL that Twilio signed.

    Handles comma-separated values in X-Forwarded-* headers when requests
    traverse multiple proxies (e.g., CloudFlare -> ALB -> k8s ingress).
    """
    proto_header = request.headers.get("X-Forwarded-Proto") or request.url.scheme
    proto = proto_header.split(",")[0].strip()

    host_header = (
        request.headers.get("X-Forwarded-Host") or request.headers.get("Host") or request.url.netloc
    )
    host = host_header.split(",")[0].strip()

    path = request.url.path
    query = request.url.query

    url = f"{proto}://{host}{path}"
    if query:
        url = f"{url}?{query}"

    return url
