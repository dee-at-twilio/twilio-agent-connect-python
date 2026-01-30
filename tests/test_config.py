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
            environment="prod",
            twilio_account_sid="ACtest123",
            conversation_service_sid="IS123test",
            twilio_phone_number="+15551234567",
        )
        assert config.twilio_auth_token == "test_token_123"
        assert config.memora_base_url == "https://memory.twilio.com"
        assert config.environment == "prod"
        assert config.maestro_base_url == "https://conversations.twilio.com"
        assert config.twilio_account_sid == "ACtest123"
        assert config.log_level == "INFO"  # Default value
        assert config.twilio_memory_config is None  # Optional memory config

    def test_config_with_custom_log_level(self):
        """Test config with custom log level."""
        config = TACConfig(
            twilio_auth_token="test_token_123",
            environment="dev",
            twilio_account_sid="ACtest123",
            conversation_service_sid="IS123test",
            twilio_phone_number="+15551234567",
            log_level="DEBUG",
        )
        assert config.twilio_auth_token == "test_token_123"
        assert config.environment == "dev"
        assert config.memora_base_url == "https://memory.dev.twilio.com"
        assert config.maestro_base_url == "https://conversations.dev.twilio.com"
        assert config.twilio_account_sid == "ACtest123"
        assert config.log_level == "DEBUG"

    def test_config_with_memory_enabled(self):
        """Test config with Twilio Memory enabled."""
        memory_config = TwilioMemoryConfig(
            memory_store_id="MGtest123", api_key="test_api_key", api_token="test_api_token"
        )
        config = TACConfig(
            twilio_auth_token="test_token_123",
            environment="prod",
            twilio_account_sid="ACtest123",
            conversation_service_sid="IS123test",
            twilio_phone_number="+15551234567",
            twilio_memory_config=memory_config,
        )
        assert config.twilio_memory_config is not None
        assert config.twilio_memory_config.memory_store_id == "MGtest123"
        assert config.twilio_memory_config.api_key == "test_api_key"
        assert config.twilio_memory_config.api_token == "test_api_token"

    def test_config_dict_conversion(self):
        """Test converting config to dictionary."""
        config = TACConfig(
            twilio_auth_token="test_token_123",
            environment="stage",
            twilio_account_sid="ACtest123",
            conversation_service_sid="IS123test",
            twilio_phone_number="+15551234567",
            twilio_memory_config=TwilioMemoryConfig(
                memory_store_id="MGtest123", api_key="test_api_key", api_token="test_api_token"
            ),
        )
        config_dict = config.model_dump()

        assert isinstance(config_dict, dict)
        assert "twilio_auth_token" in config_dict
        assert config_dict["twilio_auth_token"] == "test_token_123"
        assert "environment" in config_dict
        assert config_dict["environment"] == "stage"
        assert "log_level" in config_dict
        assert config_dict["log_level"] == "INFO"
        assert "twilio_memory_config" in config_dict
        assert config_dict["twilio_memory_config"]["memory_store_id"] == "MGtest123"
        assert config_dict["twilio_memory_config"]["api_key"] == "test_api_key"
        assert config_dict["twilio_memory_config"]["api_token"] == "test_api_token"

    def test_config_from_dict(self):
        """Test creating config from dictionary."""
        config_data = {
            "twilio_auth_token": "test_token_123",
            "environment": "prod",
            "twilio_account_sid": "ACtest123",
            "conversation_service_sid": "IS123test",
            "twilio_phone_number": "+15551234567",
            "twilio_memory_config": {
                "memory_store_id": "MGtest123",
                "api_key": "test_api_key",
                "api_token": "test_api_token",
            },
        }
        config = TACConfig(**config_data)
        assert config.twilio_auth_token == "test_token_123"
        assert config.memora_base_url == "https://memory.twilio.com"
        assert config.environment == "prod"
        assert config.twilio_memory_config is not None
        assert config.twilio_memory_config.memory_store_id == "MGtest123"
        assert config.twilio_memory_config.api_key == "test_api_key"
        assert config.twilio_memory_config.api_token == "test_api_token"

    def test_config_json_schema(self):
        """Test that config has valid JSON schema."""
        schema = TACConfig.model_json_schema()

        assert "properties" in schema
        assert "twilio_auth_token" in schema["properties"]
        assert "environment" in schema["properties"]
        assert "twilio_account_sid" in schema["properties"]
        assert "twilio_phone_number" in schema["properties"]
        assert "log_level" in schema["properties"]

        # Check that environment is a string type
        assert schema["properties"]["environment"]["type"] == "string"

        # Check required fields
        assert "required" in schema
        required_fields = schema["required"]
        assert "twilio_auth_token" in required_fields
        assert "environment" in required_fields
        assert "twilio_account_sid" in required_fields

    def test_config_equality(self):
        """Test config equality comparison."""
        base_config = {
            "twilio_auth_token": "test_token_123",
            "environment": "prod",
            "twilio_account_sid": "ACtest123",
            "conversation_service_sid": "IS123test",
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
        assert "twilio_auth_token" in str(error)
        assert "environment" in str(error)
        assert "twilio_account_sid" in str(error)

    def test_partial_config_fails(self):
        """Test that partial config raises validation error."""
        with pytest.raises(ValidationError):
            TACConfig(twilio_auth_token="test_token_123")  # Missing other required fields

    def test_invalid_environment_fails(self):
        """Test that invalid environment value raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            TACConfig(
                twilio_auth_token="test_token_123",
                environment="invalid",  # Invalid environment
                twilio_account_sid="ACtest123",
                conversation_service_sid="IS123test",
                twilio_phone_number="+15551234567",
            )

        error = exc_info.value
        assert "environment" in str(error)
        assert "must be one of" in str(error)
