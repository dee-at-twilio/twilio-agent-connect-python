"""Tests for TAC core class."""

import pytest

from tac import TAC, TACConfig


def get_test_config(with_memory=False):
    """Get a valid test configuration."""
    config = {
        "twilio_auth_token": "test_token_123",
        "api_key": "SK123",
        "api_token": "test_api_token",
        "environment": "prod",
        "twilio_account_sid": "ACtest123",
        "conversation_service_sid": "IS123test",
        "twilio_phone_number": "+15551234567",
    }
    if with_memory:
        config["twilio_memory_config"] = {
            "memory_store_id": "MGtest123",
        }
    return config


class TestTAC:
    """Test TAC core class."""

    def test_init_with_config_dict(self):
        """Test TAC initialization with configuration dictionary."""
        config_dict = get_test_config()
        tac = TAC(config_dict)

        assert isinstance(tac.config, TACConfig)
        assert tac.config.twilio_auth_token == "test_token_123"
        assert tac.config.memora_base_url == "https://memory.twilio.com"

    def test_init_with_config_object(self):
        """Test TAC initialization with TACConfig object."""
        config = TACConfig(**get_test_config())
        tac = TAC(config)

        assert isinstance(tac.config, TACConfig)
        assert tac.config.twilio_auth_token == "test_token_123"
        assert tac.config.memora_base_url == "https://memory.twilio.com"

    def test_init_with_empty_config_dict_fails(self):
        """Test TAC initialization with empty configuration dictionary fails."""
        config_dict = {}
        with pytest.raises(ValueError, match="Invalid configuration"):
            TAC(config_dict)

    def test_init_with_invalid_config_type(self):
        """Test TAC initialization with invalid configuration type."""
        with pytest.raises(ValueError, match="Config must be TACConfig instance or dictionary"):
            TAC("invalid_config")
