"""Configuration models for the Twilio Agent Connect."""

import os

from pydantic import BaseModel, ConfigDict, Field


class ConversationIntelligenceConfig(BaseModel):
    """
    Configuration for Conversation Intelligence webhook filtering.

    This config specifies which CI configuration and operators to process.
    Events that don't match are filtered out.
    """

    configuration_id: str = Field(
        description="Conversation Intelligence Configuration ID",
    )
    observation_operator_sid: str | None = Field(
        default=None,
        description="Operator SID for observation extraction (e.g., LY...)",
    )
    summary_operator_sid: str | None = Field(
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
    def from_env(cls) -> "ConversationIntelligenceConfig | None":
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
    Configuration for Twilio Memory Store integration.

    Note: Memory client is always initialized automatically by fetching memory_store_id
    from the Conversation Orchestrator configuration. This config only controls optional memory
    settings like which trait groups to include when fetching profiles.
    """

    trait_groups: list[str] | None = Field(
        default=None,
        description="Optional list of trait group names to include when retrieving profiles",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "trait_groups": ["Contact", "Preferences"],
            }
        },
    )

    @classmethod
    def from_env(cls) -> "TwilioMemoryConfig":
        """
        Create TwilioMemoryConfig from environment variables.

        Loads configuration from the following environment variables:
        - TWILIO_TAC_TRAIT_GROUPS: Comma-separated list of trait groups (optional)

        Returns:
            TwilioMemoryConfig instance with parsed trait groups from environment,
            or default values if no environment variables are set.

        Example:
            >>> # With trait groups from environment
            >>> config = TwilioMemoryConfig.from_env()

            >>> # Or manually construct
            >>> config = TwilioMemoryConfig(trait_groups=["Contact", "Preferences"])

            >>> # Without trait groups (all traits included)
            >>> config = TwilioMemoryConfig()
        """
        trait_groups_str = os.environ.get("TWILIO_TAC_TRAIT_GROUPS")

        # Parse trait groups from environment variable
        trait_groups = None
        if trait_groups_str:
            trait_groups = [g.strip() for g in trait_groups_str.split(",")]

        return cls(trait_groups=trait_groups)


class TACConfig(BaseModel):
    """Configuration model for Twilio Agent Connect settings."""

    conversation_configuration_id: str = Field(description="Twilio Conversation Configuration ID")

    twilio_memory_config: TwilioMemoryConfig | None = Field(
        default=None,
        description="Optional Twilio Memory configuration for controlling which trait groups "
        "to include when fetching profiles. Note: Memory client is always initialized "
        "automatically from Conversation Orchestrator configuration - "
        "this only configures trait group filtering.",
    )

    twilio_auth_token: str = Field(description="Twilio Auth Token")
    api_key: str = Field(description="Twilio API Key SID (starts with SK)")
    api_token: str = Field(description="Twilio API Key Secret")

    twilio_phone_number: str = Field(
        description="Twilio Phone Number for Voice (inbound) and SMS (send/receive).",
    )

    knowledge_base_id: str | None = Field(
        default=None,
        description="Optional Knowledge Base ID for knowledge search functionality",
    )

    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    conversation_intelligence_config: ConversationIntelligenceConfig | None = Field(
        default=None,
        description="Optional Conversation Intelligence configuration for filtering webhook "
        "events. When provided to OperatorResultProcessor, only matching events are processed.",
    )

    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "conversation_configuration_id": "conv_configuration_xxxxxxxxxxxxxxxxxx",
                "twilio_auth_token": "your_auth_token_here",
                "api_key": "SKxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "api_token": "your_api_token_here",
                "twilio_phone_number": "your_phone_number_here",
                "twilio_memory_config": {
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
        - TWILIO_TAC_CONVERSATION_CONFIGURATION_ID: Twilio Conversation Configuration ID
        - TWILIO_TAC_API_KEY: Twilio API Key SID (starts with SK)
        - TWILIO_TAC_API_TOKEN: Twilio API Key Secret
        - TWILIO_TAC_PHONE_NUMBER: Twilio Phone Number for Voice and SMS channels
        - TWILIO_TAC_AUTH_TOKEN: Twilio Auth Token
        - TWILIO_TAC_KNOWLEDGE_BASE_ID: Knowledge Base ID (optional)
        - TWILIO_TAC_LOG_LEVEL: Logging level (optional, defaults to INFO)

        Memory configuration is automatically loaded via TwilioMemoryConfig.from_env()
        from these environment variables (all optional):
        - TWILIO_TAC_TRAIT_GROUPS: Comma-separated list of trait groups

        Conversation Intelligence configuration is automatically loaded via
        ConversationIntelligenceConfig.from_env() from these environment variables (all optional):
        - TWILIO_TAC_CI_CONFIGURATION_ID: CI Configuration ID (TTID format)
        - TWILIO_TAC_CI_OBSERVATION_OPERATOR_SID: Operator SID for observations
        - TWILIO_TAC_CI_SUMMARY_OPERATOR_SID: Operator SID for summaries

        Returns:

        Raises:
            KeyError: If required environment variables are not set.
            ValidationError: If environment variable values are invalid.

        Example:
            >>> # With all env vars set in .env file
            >>> config = TACConfig.from_env()
            >>> tac = TAC(config=config)
        """
        # Load optional memory configuration
        twilio_memory_config = TwilioMemoryConfig.from_env()

        # Load optional conversation intelligence configuration
        conversation_intelligence_config = ConversationIntelligenceConfig.from_env()

        return cls(
            conversation_configuration_id=os.environ["TWILIO_TAC_CONVERSATION_CONFIGURATION_ID"],
            twilio_auth_token=os.environ["TWILIO_TAC_AUTH_TOKEN"],
            api_key=os.environ["TWILIO_TAC_API_KEY"],
            api_token=os.environ["TWILIO_TAC_API_TOKEN"],
            twilio_phone_number=os.environ["TWILIO_TAC_PHONE_NUMBER"],
            knowledge_base_id=os.environ.get("TWILIO_TAC_KNOWLEDGE_BASE_ID"),
            log_level=os.environ.get("TWILIO_TAC_LOG_LEVEL", "INFO"),
            twilio_memory_config=twilio_memory_config,
            conversation_intelligence_config=conversation_intelligence_config,
        )
