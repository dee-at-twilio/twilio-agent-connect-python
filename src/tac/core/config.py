"""Configuration models for the Twilio Agent Connect."""

import os
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class ConversationIntelligenceConfig(BaseModel):
    """
    Configuration for Conversation Intelligence webhook filtering.

    This config specifies which CI configuration and operators to process.
    Events that don't match are filtered out.
    """

    configuration_id: str = Field(
        description="Conversation Intelligence Configuration ID",
    )
    observation_operator_sid: Optional[str] = Field(
        default=None,
        description="Operator SID for observation extraction (e.g., LY...)",
    )
    summary_operator_sid: Optional[str] = Field(
        default=None,
        description="Operator SID for summary extraction (e.g., LY...)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "configuration_id": "your_ci_configuration_id",
                "observation_operator_sid": "LY00000000000000000000000000000001",
                "summary_operator_sid": "LY00000000000000000000000000000002",
            }
        },
    )

    @classmethod
    def from_env(cls) -> Optional["ConversationIntelligenceConfig"]:
        """
        Create ConversationIntelligenceConfig from environment variables.

        Loads configuration from the following environment variables:
        - TWILIO_TAC_CI_CONFIGURATION_ID: CI Configuration ID (required)
        - TWILIO_TAC_CI_OBSERVATION_OPERATOR_SID: Operator SID for observations (optional)
        - TWILIO_TAC_CI_SUMMARY_OPERATOR_SID: Operator SID for summaries (optional)

        Returns:
            ConversationIntelligenceConfig instance if configuration_id is set,
            None otherwise.
        """
        configuration_id = os.environ.get("TWILIO_TAC_CI_CONFIGURATION_ID")

        if not configuration_id:
            return None

        return cls(
            configuration_id=configuration_id,
            observation_operator_sid=os.environ.get("TWILIO_TAC_CI_OBSERVATION_OPERATOR_SID"),
            summary_operator_sid=os.environ.get("TWILIO_TAC_CI_SUMMARY_OPERATOR_SID"),
        )


class TwilioMemoryConfig(BaseModel):
    """
    Configuration for Twilio Memory Service integration.

    This config should only be provided if you have purchased Twilio Memory functionality.
    When provided, TAC will automatically retrieve memory for SMS conversations.
    """

    memory_store_id: str = Field(
        description="Memory Store ID (starts with mem_store_ or mem_service_)",
    )
    api_key: str = Field(
        description="Twilio API Key SID (starts with SK)",
    )
    api_token: str = Field(
        description="Twilio API Key Secret",
    )

    trait_groups: Optional[list[str]] = Field(
        default=None,
        description="Optional list of trait group names to include when retrieving profiles",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "memory_store_id": "mem_service_xxxxxxxxxxxxxxxxxx",
                "trait_groups": ["Contact", "Preferences"],
                "api_key": "SKxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "api_token": "your_api_key_secret_here",
            }
        },
    )

    @classmethod
    def from_env(cls) -> Optional["TwilioMemoryConfig"]:
        """
        Create TwilioMemoryConfig from environment variables.

        Loads configuration from the following environment variables:
        - TWILIO_TAC_MEMORY_STORE_ID: Memory Store ID (starts with mem_store_ or mem_service_)
        - TWILIO_TAC_MEMORY_API_KEY: Twilio API Key SID (starts with SK)
        - TWILIO_TAC_MEMORY_API_TOKEN: Twilio API Key Secret
        - TWILIO_TAC_TRAIT_GROUPS: Comma-separated list of trait groups (optional)

        Returns:
            TwilioMemoryConfig instance if all required env vars are set, None otherwise.

        Example:
            >>> # From environment variables
            >>> config = TwilioMemoryConfig.from_env()

            >>> # Or manually construct with custom trait_groups
            >>> config = TwilioMemoryConfig(
            >>>     memory_store_id="mem_service_123",
            >>>     api_key="key",
            >>>     api_token="token",
            >>>     trait_groups=["Contact", "Preferences"],
            >>> )
        """
        memory_store_id = os.environ.get("TWILIO_TAC_MEMORY_STORE_ID")
        api_key = os.environ.get("TWILIO_TAC_MEMORY_API_KEY")
        api_token = os.environ.get("TWILIO_TAC_MEMORY_API_TOKEN")

        # Return None if any required variable is missing
        if not (memory_store_id and api_key and api_token):
            return None

        # Parse trait groups from environment variable
        trait_groups = None
        trait_groups_str = os.environ.get("TWILIO_TAC_TRAIT_GROUPS")
        if trait_groups_str:
            trait_groups = [g.strip() for g in trait_groups_str.split(",")]

        return cls(
            memory_store_id=memory_store_id,
            api_key=api_key,
            api_token=api_token,
            trait_groups=trait_groups,
        )


class TACConfig(BaseModel):
    """Configuration model for Twilio Agent Connect settings."""

    environment: str = Field(description="TAC environment (dev, stage, or prod)")
    conversation_service_sid: str = Field(description="Twilio Conversation Service SID")

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate that environment is one of the allowed values."""
        v = v.lower()  # Normalize to lowercase
        allowed = {"dev", "stage", "prod"}
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}, got '{v}'")
        return v

    twilio_memory_config: Optional[TwilioMemoryConfig] = Field(
        default=None,
        description="Optional Twilio Memory configuration. Provide this if you have "
        "purchased Twilio Memory functionality. When provided, memory will be "
        "automatically retrieved for SMS conversations.",
    )

    twilio_account_sid: str = Field(description="Twilio Account SID")
    twilio_auth_token: str = Field(description="Twilio Auth Token from Twilio Console")

    twilio_phone_number: str = Field(
        description="Twilio Phone Number for Voice (inbound) and SMS (send/receive).",
    )

    knowledge_base_id: Optional[str] = Field(
        default=None,
        description="Optional Knowledge Base ID for knowledge search functionality",
    )

    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    enable_voice_active_hydration: bool = Field(
        default=False,
        description="Enable active hydration for voice conversations. When enabled, "
        "user messages and LLM responses are sent to Maestro via create_communication API "
        "to keep conversation history in sync.",
    )

    conversation_intelligence_config: Optional[ConversationIntelligenceConfig] = Field(
        default=None,
        description="Optional Conversation Intelligence configuration for filtering webhook "
        "events. When provided to OperatorResultProcessor, only matching events are processed.",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def memora_base_url(self) -> str:
        """Return the Memory Service base URL based on the environment."""
        memory_urls = {
            "dev": "https://memory.dev.twilio.com",
            "stage": "https://memory.stage.twilio.com",
            "prod": "https://memory.twilio.com",
        }
        return memory_urls[self.environment]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def maestro_base_url(self) -> str:
        """Return the Maestro base URL based on the environment."""
        maestro_urls = {
            "dev": "https://conversations.dev.twilio.com",
            "stage": "https://conversations.stage.twilio.com",
            "prod": "https://conversations.twilio.com",
        }
        return maestro_urls[self.environment]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def knowledge_base_url(self) -> str:
        """Return the Knowledge Base URL based on the environment."""
        knowledge_urls = {
            "dev": "https://knowledge.dev.twilio.com",
            "stage": "https://knowledge.stage.twilio.com",
            "prod": "https://knowledge.twilio.com",
        }
        return knowledge_urls[self.environment]

    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "environment": "prod",
                "conversation_service_sid": "conv_configuration_xxxxxxxxxxxxxxxxxx",
                "twilio_account_sid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "twilio_auth_token": "your_auth_token_here",
                "twilio_phone_number": "your_phone_number_here",
                "twilio_memory_config": {
                    "memory_store_id": "mem_service_xxxxxxxxxxxxxxxxxx",
                    "api_key": "your_api_key_here",
                    "api_token": "your_api_token_here",
                    "trait_groups": ["Contact", "Preferences"],
                },
                "conversation_intelligence_config": {
                    "configuration_id": "GAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                    "observation_operator_sid": "LYxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                    "summary_operator_sid": "LYyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
                },
            }
        },
    )

    @classmethod
    def from_env(cls) -> "TACConfig":
        """
        Create TACConfig from environment variables.

        Loads configuration from the following environment variables:
        - TWILIO_TAC_ENVIRONMENT: TAC environment (dev, stage, or prod)
        - TWILIO_TAC_CONVERSATION_SERVICE_SID: Twilio Conversation Service SID
        - TWILIO_TAC_ACCOUNT_SID: Twilio Account SID
        - TWILIO_TAC_AUTH_TOKEN: Twilio Auth Token
        - TWILIO_TAC_PHONE_NUMBER: Twilio Phone Number for Voice and SMS channels
        - TWILIO_TAC_KNOWLEDGE_BASE_ID: Knowledge Base ID (optional)
        - TWILIO_TAC_LOG_LEVEL: Logging level (optional, defaults to INFO)
        - TWILIO_TAC_ENABLE_VOICE_ACTIVE_HYDRATION: Enable voice active hydration (optional,
          defaults to false, set to 'true' or '1' to enable)

        Memory configuration is automatically loaded via TwilioMemoryConfig.from_env()
        from these environment variables (all optional):
        - TWILIO_TAC_MEMORY_STORE_ID: Memory Store ID
        - TWILIO_TAC_MEMORY_API_KEY: Twilio API Key SID
        - TWILIO_TAC_MEMORY_API_TOKEN: Twilio API Key Secret
        - TWILIO_TAC_TRAIT_GROUPS: Comma-separated list of trait groups

        Conversation Intelligence configuration is automatically loaded via
        ConversationIntelligenceConfig.from_env() from these environment variables (all optional):
        - TWILIO_TAC_CI_CONFIGURATION_ID: CI Configuration ID (TTID format)
        - TWILIO_TAC_CI_OBSERVATION_OPERATOR_SID: Operator SID for observations
        - TWILIO_TAC_CI_SUMMARY_OPERATOR_SID: Operator SID for summaries

        Returns:
            TACConfig instance with all configuration loaded from environment.

        Raises:
            KeyError: If required environment variables are not set.
            ValidationError: If environment variable values are invalid.

        Example:
            >>> # With all env vars set in .env file
            >>> config = TACConfig.from_env()
            >>> tac = TAC(config=config)

            >>> # Or fall back to manual config if env vars not set
            >>> try:
            >>>     config = TACConfig.from_env()
            >>> except (KeyError, ValidationError):
            >>>     config = TACConfig(environment="prod", ...)
        """
        # Load optional memory configuration
        twilio_memory_config = TwilioMemoryConfig.from_env()

        # Load optional conversation intelligence configuration
        conversation_intelligence_config = ConversationIntelligenceConfig.from_env()

        # Parse enable_voice_active_hydration as boolean
        enable_voice_active_hydration = False
        voice_hydration_str = os.environ.get("TWILIO_TAC_ENABLE_VOICE_ACTIVE_HYDRATION", "").lower()
        if voice_hydration_str in ("true", "1", "yes"):
            enable_voice_active_hydration = True

        return cls(
            environment=os.environ["TWILIO_TAC_ENVIRONMENT"],
            conversation_service_sid=os.environ["TWILIO_TAC_CONVERSATION_SERVICE_SID"],
            twilio_account_sid=os.environ["TWILIO_TAC_ACCOUNT_SID"],
            twilio_auth_token=os.environ["TWILIO_TAC_AUTH_TOKEN"],
            twilio_phone_number=os.environ["TWILIO_TAC_PHONE_NUMBER"],
            knowledge_base_id=os.environ.get("TWILIO_TAC_KNOWLEDGE_BASE_ID"),
            log_level=os.environ.get("TWILIO_TAC_LOG_LEVEL", "INFO"),
            enable_voice_active_hydration=enable_voice_active_hydration,
            twilio_memory_config=twilio_memory_config,
            conversation_intelligence_config=conversation_intelligence_config,
        )
