"""Tests for User-Agent header in API clients."""

import platform
import re

import pytest

from tac import __version__
from tac.context.base import BaseAPIClient
from tac.context.conversation import ConversationClient
from tac.context.knowledge import KnowledgeClient
from tac.context.memory import MemoryClient


class TestUserAgent:
    """Test User-Agent header generation."""

    def test_base_client_user_agent_format(self) -> None:
        """Test that BaseAPIClient generates correct User-Agent format."""
        client = BaseAPIClient(
            base_url="https://api.example.com",
            api_key="test_key",
            api_token="test_token",
        )

        user_agent = client._get_user_agent()

        # Should match pattern: twilio-agent-connect-python/{version} ({os} {arch}) Python/{py_ver}
        # Use re.escape(__version__) to support PEP 440 versioning (e.g., 0.1.0a1, .dev0, +local)
        pattern = (
            rf"twilio-agent-connect-python/{re.escape(__version__)} "
            r"\(.+ .+\) Python/[\d\.]+"
        )
        assert re.match(pattern, user_agent), f"User-Agent doesn't match pattern: {user_agent}"

        # Verify it contains expected components
        assert f"twilio-agent-connect-python/{__version__}" in user_agent
        assert platform.system() in user_agent
        assert platform.machine() in user_agent
        assert f"Python/{platform.python_version()}" in user_agent

    def test_user_agent_matches_twilio_pattern(self) -> None:
        """Test that User-Agent follows Twilio SDK pattern."""
        client = BaseAPIClient(
            base_url="https://api.example.com",
            api_key="test_key",
            api_token="test_token",
        )

        user_agent = client._get_user_agent()
        expected_format = (
            f"twilio-agent-connect-python/{__version__} "
            f"({platform.system()} {platform.machine()}) "
            f"Python/{platform.python_version()}"
        )

        assert user_agent == expected_format

    @pytest.mark.asyncio
    async def test_conversation_client_sends_user_agent(self) -> None:
        """Test that ConversationClient includes User-Agent in requests."""
        client = ConversationClient(
            base_url="https://api.example.com",
            api_key="test_key",
            api_token="test_token",
            configuration_id="test_configuration",
        )

        async with client._get_client() as http_client:
            headers = http_client.headers
            assert "User-Agent" in headers
            assert "twilio-agent-connect-python" in headers["User-Agent"]

    @pytest.mark.asyncio
    async def test_memory_client_sends_user_agent(self) -> None:
        """Test that MemoryClient includes User-Agent in requests."""
        client = MemoryClient(
            base_url="https://api.example.com",
            store_id="test_store",
            api_key="test_key",
            api_token="test_token",
        )

        async with client._get_client() as http_client:
            headers = http_client.headers
            assert "User-Agent" in headers
            assert "twilio-agent-connect-python" in headers["User-Agent"]

    @pytest.mark.asyncio
    async def test_knowledge_client_sends_user_agent(self) -> None:
        """Test that KnowledgeClient includes User-Agent in requests."""
        client = KnowledgeClient(
            base_url="https://api.example.com",
            api_key="test_key",
            api_token="test_token",
        )

        async with client._get_client() as http_client:
            headers = http_client.headers
            assert "User-Agent" in headers
            assert "twilio-agent-connect-python" in headers["User-Agent"]

    def test_sync_client_sends_user_agent(self) -> None:
        """Test that synchronous client includes User-Agent in requests."""
        client = BaseAPIClient(
            base_url="https://api.example.com",
            api_key="test_key",
            api_token="test_token",
        )

        with client._get_sync_client() as http_client:
            headers = http_client.headers
            assert "User-Agent" in headers
            assert "twilio-agent-connect-python" in headers["User-Agent"]
