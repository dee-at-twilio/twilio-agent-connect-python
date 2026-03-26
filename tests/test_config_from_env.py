"""Tests for TwilioMemoryConfig.from_env() and TACConfig.from_env() methods."""

import pytest

from tac.core.config import TACConfig, TwilioMemoryConfig


class TestTwilioMemoryConfigFromEnv:
    """Test suite for TwilioMemoryConfig.from_env() factory method."""

    def test_from_env_no_vars_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() returns empty config when no environment variables are set."""
        monkeypatch.delenv("TWILIO_TAC_TRAIT_GROUPS", raising=False)

        config = TwilioMemoryConfig.from_env()

        assert config is not None
        assert config.trait_groups is None

    def test_from_env_with_trait_groups_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() parses TWILIO_TAC_TRAIT_GROUPS from environment."""
        monkeypatch.setenv("TWILIO_TAC_TRAIT_GROUPS", "Contact, Preferences, Custom")

        config = TwilioMemoryConfig.from_env()

        assert config is not None
        assert config.trait_groups == ["Contact", "Preferences", "Custom"]

    def test_from_env_empty_trait_groups(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() handles empty TWILIO_TAC_TRAIT_GROUPS environment variable."""
        monkeypatch.setenv("TWILIO_TAC_TRAIT_GROUPS", "")

        config = TwilioMemoryConfig.from_env()

        assert config is not None
        assert config.trait_groups is None


class TestTACConfigFromEnv:
    """Test suite for TACConfig.from_env() factory method."""

    def _set_all_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Helper to set all TACConfig environment variables.

        Sets all required vars (Conversation Service SID, Account SID, Auth Token,
        API Key/Token, Phone Number) and optional vars (Environment). Tests can
        selectively remove variables to test specific scenarios.
        """
        monkeypatch.setenv("TWILIO_TAC_ENVIRONMENT", "prod")
        monkeypatch.setenv("TWILIO_TAC_CONVERSATION_SERVICE_SID", "conv_configuration_123")
        monkeypatch.setenv("TWILIO_TAC_AUTH_TOKEN", "test_auth_token")
        monkeypatch.setenv("TWILIO_TAC_API_KEY", "SK123")
        monkeypatch.setenv("TWILIO_TAC_API_TOKEN", "test_api_token")
        monkeypatch.setenv("TWILIO_TAC_PHONE_NUMBER", "+1234567890")

    def test_from_env_with_all_required_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() creates config when all required env vars are set."""
        self._set_all_env_vars(monkeypatch)

        config = TACConfig.from_env()

        assert config.environment == "prod"
        assert config.conversation_service_sid == "conv_configuration_123"
        assert config.twilio_auth_token == "test_auth_token"
        assert config.api_key == "SK123"
        assert config.api_token == "test_api_token"
        assert config.twilio_phone_number == "+1234567890"
        assert config.log_level == "INFO"  # Default
        # Always returns config (memory store ID auto-fetched)
        assert config.twilio_memory_config is not None
        assert config.twilio_memory_config.trait_groups is None  # No trait groups env var set

    def test_from_env_with_memory_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() includes memory config when memory env vars are set."""
        self._set_all_env_vars(monkeypatch)
        monkeypatch.setenv("TWILIO_TAC_TRAIT_GROUPS", "Contact, Preferences")

        config = TACConfig.from_env()

        assert config.twilio_memory_config is not None
        assert config.twilio_memory_config.trait_groups == ["Contact", "Preferences"]

    def test_from_env_with_custom_log_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() respects custom TWILIO_TAC_LOG_LEVEL."""
        self._set_all_env_vars(monkeypatch)
        monkeypatch.setenv("TWILIO_TAC_LOG_LEVEL", "DEBUG")

        config = TACConfig.from_env()

        assert config.log_level == "DEBUG"

    def test_from_env_missing_environment_defaults_to_prod(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test from_env() defaults to prod when TWILIO_TAC_ENVIRONMENT is missing."""
        self._set_all_env_vars(monkeypatch)
        monkeypatch.delenv("TWILIO_TAC_ENVIRONMENT", raising=False)

        config = TACConfig.from_env()
        assert config.environment == "prod"

    def test_from_env_missing_conversation_service_sid(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test from_env() raises KeyError when TWILIO_TAC_CONVERSATION_SERVICE_SID is missing."""
        self._set_all_env_vars(monkeypatch)
        monkeypatch.delenv("TWILIO_TAC_CONVERSATION_SERVICE_SID", raising=False)

        with pytest.raises(KeyError, match="TWILIO_TAC_CONVERSATION_SERVICE_SID"):
            TACConfig.from_env()

    def test_from_env_missing_twilio_auth_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() raises KeyError when TWILIO_TAC_AUTH_TOKEN is missing."""
        self._set_all_env_vars(monkeypatch)
        monkeypatch.delenv("TWILIO_TAC_AUTH_TOKEN", raising=False)

        with pytest.raises(KeyError, match="TWILIO_TAC_AUTH_TOKEN"):
            TACConfig.from_env()

    def test_from_env_missing_twilio_phone_number(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() raises KeyError when TWILIO_TAC_PHONE_NUMBER is missing."""
        self._set_all_env_vars(monkeypatch)
        monkeypatch.delenv("TWILIO_TAC_PHONE_NUMBER", raising=False)

        with pytest.raises(KeyError, match="TWILIO_TAC_PHONE_NUMBER"):
            TACConfig.from_env()

    def test_from_env_missing_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() raises KeyError when TWILIO_TAC_API_KEY is missing."""
        self._set_all_env_vars(monkeypatch)
        monkeypatch.delenv("TWILIO_TAC_API_KEY", raising=False)

        with pytest.raises(KeyError, match="TWILIO_TAC_API_KEY"):
            TACConfig.from_env()

    def test_from_env_missing_api_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() raises KeyError when TWILIO_TAC_API_TOKEN is missing."""
        self._set_all_env_vars(monkeypatch)
        monkeypatch.delenv("TWILIO_TAC_API_TOKEN", raising=False)

        with pytest.raises(KeyError, match="TWILIO_TAC_API_TOKEN"):
            TACConfig.from_env()

    def test_from_env_missing_multiple_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() raises KeyError when environment variables are missing."""
        monkeypatch.delenv("TWILIO_TAC_ENVIRONMENT", raising=False)
        monkeypatch.delenv("TWILIO_TAC_CONVERSATION_SERVICE_SID", raising=False)
        monkeypatch.delenv("TWILIO_TAC_AUTH_TOKEN", raising=False)
        monkeypatch.delenv("TWILIO_TAC_PHONE_NUMBER", raising=False)

        with pytest.raises(KeyError):
            TACConfig.from_env()

    def test_from_env_validates_environment_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() validates environment field through Pydantic."""
        self._set_all_env_vars(monkeypatch)
        monkeypatch.setenv("TWILIO_TAC_ENVIRONMENT", "invalid")

        with pytest.raises(ValueError, match="environment must be one of"):
            TACConfig.from_env()

    def test_from_env_environment_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() accepts environment values in any case and normalizes to lowercase."""
        self._set_all_env_vars(monkeypatch)

        # Test uppercase
        monkeypatch.setenv("TWILIO_TAC_ENVIRONMENT", "PROD")
        config = TACConfig.from_env()
        assert config.environment == "prod"

        # Test mixed case
        monkeypatch.setenv("TWILIO_TAC_ENVIRONMENT", "Prod")
        config = TACConfig.from_env()
        assert config.environment == "prod"

        # Test stage uppercase
        monkeypatch.setenv("TWILIO_TAC_ENVIRONMENT", "STAGE")
        config = TACConfig.from_env()
        assert config.environment == "stage"

        # Test dev uppercase
        monkeypatch.setenv("TWILIO_TAC_ENVIRONMENT", "DEV")
        config = TACConfig.from_env()
        assert config.environment == "dev"
