import platform

import httpx

from tac import __version__
from tac.core.logging import get_logger


class BaseAPIClient:
    """Base client for Twilio API interactions with shared HTTP client logic."""

    base_url: str

    def __init__(
        self,
        api_key: str,
        api_token: str,
    ) -> None:
        """
        Initialize the base API client.

        Args:
            api_key: Twilio API Key SID for authentication
            api_token: Twilio API Key Secret for authentication
        """
        self.api_key = api_key
        self.api_token = api_token
        self.logger = get_logger(self.__class__.__name__)

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
            auth=(self.api_key, self.api_token),
            headers={"User-Agent": self._get_user_agent()},
            timeout=30.0,
        )

    def _get_sync_client(self) -> httpx.Client:
        """Create a new synchronous httpx.Client."""
        return httpx.Client(
            auth=(self.api_key, self.api_token),
            headers={"User-Agent": self._get_user_agent()},
            timeout=30.0,
        )
