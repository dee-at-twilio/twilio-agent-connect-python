import platform

import httpx

from tac import __version__
from tac.core.logging import get_logger


class BaseAPIClient:
    """Base client for Twilio API interactions with shared HTTP client logic."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        region: str | None = None,
    ) -> None:
        """
        Initialize the base API client.

        Args:
            api_key: Twilio API Key SID for authentication
            api_secret: Twilio API Key Secret for authentication
            region: Optional Twilio region (e.g., 'au1', 'ie1')
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.region = region
        self.logger = get_logger(self.__class__.__name__)

    @staticmethod
    def _build_base_url(product: str, region: str | None) -> str:
        if region:
            return f"https://{product}.{region}.twilio.com"
        return f"https://{product}.twilio.com"

    def _get_user_agent(self) -> str:
        """Generate User-Agent header following Twilio SDK conventions."""
        os_name = platform.system()
        os_arch = platform.machine()
        python_version = platform.python_version()
        return (
            f"twilio-agent-connect-python/{__version__} "
            f"({os_name} {os_arch}) Python/{python_version}"
        )

    def _get_client(self) -> httpx.AsyncClient:
        """Create a new httpx.AsyncClient for each request to avoid event loop issues."""
        return httpx.AsyncClient(
            auth=(self.api_key, self.api_secret),
            headers={"User-Agent": self._get_user_agent()},
            timeout=30.0,
        )

    def _get_sync_client(self) -> httpx.Client:
        """Create a new synchronous httpx.Client."""
        return httpx.Client(
            auth=(self.api_key, self.api_secret),
            headers={"User-Agent": self._get_user_agent()},
            timeout=30.0,
        )
