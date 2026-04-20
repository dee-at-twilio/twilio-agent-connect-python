"""Tests for TAC configuration models."""

import pytest
from pydantic import ValidationError

from tac import TACConfig
from tac.core.config import TwilioMemoryConfig


class TestTACConfig:
    """Test TACConfig model."""

    def test_config_with_required_fields(self):
        """Test config with all required fields."""
        config = TACConfig(
            twilio_auth_token="test_token_123",
            api_key="SK123",
            api_token="test_api_token",
            twilio_account_sid="ACtest123",
            conversation_configuration_id="conv_configuration_test123",
            twilio_phone_number="+15551234567",
        )
        assert config.twilio_auth_token == "test_token_123"
        assert config.api_key == "SK123"
        assert config.api_token == "test_api_token"
        assert config.log_level == "INFO"  # Default value
        assert config.twilio_memory_config is None  # Optional memory config

    def test_config_with_custom_log_level(self):
        """Test config with custom log level."""
        config = TACConfig(
            twilio_auth_token="test_token_123",
            api_key="SK123",
            api_token="test_api_token",
            twilio_account_sid="ACtest123",
            conversation_configuration_id="conv_configuration_test123",
            twilio_phone_number="+15551234567",
            log_level="DEBUG",
        )
        assert config.twilio_auth_token == "test_token_123"
        assert config.api_key == "SK123"
        assert config.api_token == "test_api_token"
        assert config.log_level == "DEBUG"

    def test_config_with_memory_enabled(self):
        """Test config with Twilio Memory enabled."""
        memory_config = TwilioMemoryConfig(trait_groups=["Contact", "Preferences"])
        config = TACConfig(
            twilio_auth_token="test_token_123",
            api_key="SK123",
            api_token="test_api_token",
            twilio_account_sid="ACtest123",
            conversation_configuration_id="conv_configuration_test123",
            twilio_phone_number="+15551234567",
            twilio_memory_config=memory_config,
        )
        assert config.twilio_memory_config is not None
        assert config.twilio_memory_config.trait_groups == ["Contact", "Preferences"]

    def test_config_dict_conversion(self):
        """Test converting config to dictionary."""
        config = TACConfig(
            twilio_auth_token="test_token_123",
            api_key="SK123",
            api_token="test_api_token",
            twilio_account_sid="ACtest123",
            conversation_configuration_id="conv_configuration_test123",
            twilio_phone_number="+15551234567",
            twilio_memory_config=TwilioMemoryConfig(trait_groups=["Contact", "Preferences"]),
        )
        config_dict = config.model_dump()

        assert isinstance(config_dict, dict)
        assert "twilio_auth_token" in config_dict
        assert config_dict["twilio_auth_token"] == "test_token_123"
        assert "api_key" in config_dict
        assert config_dict["api_key"] == "SK123"
        assert "api_token" in config_dict
        assert config_dict["api_token"] == "test_api_token"
        assert "log_level" in config_dict
        assert config_dict["log_level"] == "INFO"
        assert "twilio_memory_config" in config_dict
        assert config_dict["twilio_memory_config"]["trait_groups"] == ["Contact", "Preferences"]

    def test_config_from_dict(self):
        """Test creating config from dictionary."""
        config_data = {
            "twilio_account_sid": "ACtest123",
            "twilio_auth_token": "test_token_123",
            "api_key": "SK123",
            "api_token": "test_api_token",
            "conversation_configuration_id": "conv_configuration_test123",
            "twilio_phone_number": "+15551234567",
            "twilio_memory_config": {
                "trait_groups": ["Contact", "Preferences"],
            },
        }
        config = TACConfig(**config_data)
        assert config.twilio_auth_token == "test_token_123"
        assert config.api_key == "SK123"
        assert config.api_token == "test_api_token"
        assert config.twilio_memory_config is not None
        assert config.twilio_memory_config.trait_groups == ["Contact", "Preferences"]

    def test_config_json_schema(self):
        """Test that config has valid JSON schema."""
        schema = TACConfig.model_json_schema()

        assert "properties" in schema
        assert "twilio_auth_token" in schema["properties"]
        assert "twilio_phone_number" in schema["properties"]
        assert "log_level" in schema["properties"]

        # Check required fields
        assert "required" in schema
        required_fields = schema["required"]
        assert "api_key" in required_fields
        assert "api_token" in required_fields
        assert "conversation_configuration_id" in required_fields
        assert "twilio_phone_number" in required_fields
        assert "twilio_auth_token" in required_fields
        assert "twilio_account_sid" in required_fields

    def test_config_equality(self):
        """Test config equality comparison."""
        base_config = {
            "twilio_account_sid": "ACtest123",
            "twilio_auth_token": "test_token_123",
            "api_key": "SK123",
            "api_token": "test_api_token",
            "conversation_configuration_id": "conv_configuration_test123",
            "twilio_phone_number": "+15551234567",
        }
        config1 = TACConfig(**base_config)
        config2 = TACConfig(**base_config)

        different_config = base_config.copy()
        different_config["twilio_auth_token"] = "different_token"
        config3 = TACConfig(**different_config)

        assert config1 == config2
        assert config1 != config3

    def test_missing_required_fields(self):
        """Test that missing required fields raise validation error."""
        with pytest.raises(ValidationError) as exc_info:
            TACConfig()

        error = exc_info.value
        assert "api_key" in str(error)
        assert "api_token" in str(error)
        assert "twilio_auth_token" in str(error)
        assert "twilio_account_sid" in str(error)

    def test_partial_config_fails(self):
        """Test that partial config raises validation error."""
        with pytest.raises(ValidationError):
            TACConfig(api_key="SK123")  # Missing other required fields

    def test_config_with_twilio_region(self):
        config = TACConfig(
            twilio_account_sid="ACtest123",
            twilio_auth_token="test_token_123",
            api_key="SK123",
            api_token="test_api_token",
            conversation_configuration_id="conv_configuration_test123",
            twilio_phone_number="+15551234567",
            twilio_region="au1",
        )
        assert config.twilio_region == "au1"

    def test_config_without_twilio_region(self):
        config = TACConfig(
            twilio_account_sid="ACtest123",
            twilio_auth_token="test_token_123",
            api_key="SK123",
            api_token="test_api_token",
            conversation_configuration_id="conv_configuration_test123",
            twilio_phone_number="+15551234567",
        )
        assert config.twilio_region is None

    def test_config_twilio_region_strips_whitespace(self):
        config = TACConfig(
            twilio_account_sid="ACtest123",
            twilio_auth_token="test_token_123",
            api_key="SK123",
            api_token="test_api_token",
            conversation_configuration_id="conv_configuration_test123",
            twilio_phone_number="+15551234567",
            twilio_region="  au1  ",
        )
        assert config.twilio_region == "au1"

    def test_config_twilio_region_empty_string_becomes_none(self):
        config = TACConfig(
            twilio_account_sid="ACtest123",
            twilio_auth_token="test_token_123",
            api_key="SK123",
            api_token="test_api_token",
            conversation_configuration_id="conv_configuration_test123",
            twilio_phone_number="+15551234567",
            twilio_region="",
        )
        assert config.twilio_region is None

    def test_config_twilio_region_rejects_invalid_values(self):
        invalid_regions = [
            "has spaces",
            "has/slash",
            "has:colon",
            "UPPERCASE",
            "-leading-dash",
            "trailing-dash-",
        ]
        for region in invalid_regions:
            with pytest.raises(ValidationError, match="Invalid Twilio region format"):
                TACConfig(
                    twilio_account_sid="ACtest123",
                    twilio_auth_token="test_token_123",
                    api_key="SK123",
                    api_token="test_api_token",
                    conversation_configuration_id="conv_configuration_test123",
                    twilio_phone_number="+15551234567",
                    twilio_region=region,
                )
