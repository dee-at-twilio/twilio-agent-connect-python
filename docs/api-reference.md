<a id="tac.core.tac"></a>

# tac.core.tac

<a id="tac.core.tac.TAC"></a>

## TAC Objects

```python
class TAC()
```

Main Twilio Agent Connect class for processing webhook events with configuration.

This class accepts configuration and provides methods to process webhook events.

<a id="tac.core.tac.TAC.__init__"></a>

#### \_\_init\_\_

```python
def __init__(config: TACConfig | dict[str, Any])
```

Initialize TAC instance with configuration.

**Arguments**:

- `config` - TACConfig instance or dictionary with configuration parameters.

<a id="tac.core.tac.TAC.is_orchestrator_enabled"></a>

#### is\_orchestrator\_enabled

```python
def is_orchestrator_enabled() -> bool
```

True if TAC is configured with Conversation Orchestrator (not relay-only mode).

<a id="tac.core.tac.TAC.retrieve_memory"></a>

#### retrieve\_memory

```python
async def retrieve_memory(conversation_context: ConversationSession,
                          query: str | None = None) -> TACMemoryResponse
```

Retrieve memories from Memory Store with fallback to Conversation Orchestrator.

Three-tier resolution:
1. Memory API (when conversation_memory_client is configured).
2. Conversation Orchestrator list_communications fallback (when CO is configured).
3. Empty TACMemoryResponse (relay-only mode).

**Arguments**:

- `conversation_context` - Session containing conversation and profile information.
- `query` - Optional search query to filter memories.
  

**Returns**:

  Memory response containing conversation history and profile data.

<a id="tac.core.tac.TAC.process_cintel_event"></a>

#### process\_cintel\_event

```python
async def process_cintel_event(
        payload: dict[str, Any]) -> OperatorProcessingResult
```

Process Conversation Intelligence webhook and create observations/summaries in Memory.

**Arguments**:

- `payload` - Webhook payload from Conversation Intelligence service.
  

**Returns**:

  Processing result with created observations and summaries.

<a id="tac.core.tac.TAC.on_message_ready"></a>

#### on\_message\_ready

```python
def on_message_ready(callback: (
    Callable[[str, ConversationSession, TACMemoryResponse | None], str | None]
    | Callable[[str, ConversationSession, TACMemoryResponse | None],
               Awaitable[str | None]])) -> None
```

Register callback invoked when a message is ready.

Callback can return a string (TAC auto-sends to channel) or None (manual handling).

**Example**:

    ```python
    async def handle_message(
        message: str, context: ConversationSession, memory: TACMemoryResponse | None
    ) -> str:
        response = await openai_client.responses.create(...)
        return response.output_text  # TAC routes to appropriate channel


    tac.on_message_ready(handle_message)
    ```
  

**Arguments**:

- `callback` - Function with (message, context, memory). Returns str or None.

<a id="tac.core.tac.TAC.on_interrupt"></a>

#### on\_interrupt

```python
def on_interrupt(callback: (Callable[[ConversationSession, Any], None]
                            | Callable[[ConversationSession, Any],
                                       Awaitable[None]])) -> None
```

Register callback invoked on user interrupt.

**Example**:

    ```python
    def handle_interrupt(context: ConversationSession, interrupt_data: Any):
        # Handle user interrupt...
        pass


    tac.on_interrupt(handle_interrupt)
    ```
  

**Arguments**:

- `callback` - Function to call with (context, interrupt_data). Supports sync and async.

<a id="tac.core.tac.TAC.on_conversation_ended"></a>

#### on\_conversation\_ended

```python
def on_conversation_ended(callback: (Callable[[ConversationSession], None]
                                     | Callable[[ConversationSession],
                                                Awaitable[None]])) -> None
```

Register callback invoked when conversation ends.

**Example**:

    ```python
    def handle_conversation_ended(context: ConversationSession):
        # Clean up conversation...
        pass


    tac.on_conversation_ended(handle_conversation_ended)
    ```
  

**Arguments**:

- `callback` - Function to call with conversation context. Supports sync and async.

<a id="tac.core.tac.TAC.register_partner_connector"></a>

#### register\_partner\_connector

```python
def register_partner_connector(connector: PartnerConnector,
                               package_version: str) -> None
```

Tag outbound Twilio requests with a partner connector identifier.

Partner packages built on top of TAC (e.g. ``tac_aws``, ``tac_azure``)
call this from their connector's ``__init__`` to append a suffix to
the User-Agent header of every outbound Twilio request.

**Arguments**:

- `connector` - A :class:`PartnerConnector` enum value identifying the
  partner package and connector.
- `package_version` - Version string of the partner package (e.g.
  ``"0.1.0"``).
  

**Example**:

    ```python
    from tac import PartnerConnector

    tac.register_partner_connector(PartnerConnector.AZURE_AGENT_FRAMEWORK, "0.1.0")
    ```

<a id="tac.core.tac.TAC.trigger_message_ready"></a>

#### trigger\_message\_ready

```python
async def trigger_message_ready(
        user_message: str,
        conversation_context: ConversationSession,
        memory_response: TACMemoryResponse | None = None) -> str | None
```

Trigger the registered message ready callback.

**Arguments**:

- `user_message` - User's message text.
- `conversation_context` - Session containing conversation information.
- `memory_response` - Optional memory data to pass to callback.
  

**Returns**:

  Response string if callback returns one (for auto-send), None otherwise.
  

**Raises**:

- `TypeError` - If callback returns a value that is neither None nor str.

<a id="tac.core.tac.TAC.trigger_interrupt"></a>

#### trigger\_interrupt

```python
def trigger_interrupt(conversation_context: ConversationSession,
                      interrupt_data: Any) -> None
```

Trigger the registered interrupt callback.

**Arguments**:

- `conversation_context` - Session containing conversation information.
- `interrupt_data` - Interrupt event data from voice channel.

<a id="tac.core.tac.TAC.trigger_conversation_ended"></a>

#### trigger\_conversation\_ended

```python
async def trigger_conversation_ended(
        conversation_context: ConversationSession) -> None
```

Trigger the registered conversation ended callback.

**Arguments**:

- `conversation_context` - Session containing conversation information.

<a id="tac.core.config"></a>

# tac.core.config

Configuration models for the Twilio Agent Connect.

<a id="tac.core.config.ConversationIntelligenceConfig"></a>

## ConversationIntelligenceConfig Objects

```python
class ConversationIntelligenceConfig(BaseModel)
```

Configuration for Conversation Intelligence webhook filtering.

This config specifies which CI configuration and operators to process.
Events that don't match are filtered out.

<a id="tac.core.config.ConversationIntelligenceConfig.from_env"></a>

#### from\_env

```python
@classmethod
def from_env(cls) -> "ConversationIntelligenceConfig | None"
```

Create ConversationIntelligenceConfig from CONVERSATION_INTELLIGENCE_* env vars.

<a id="tac.core.config.TwilioMemoryConfig"></a>

## TwilioMemoryConfig Objects

```python
class TwilioMemoryConfig(BaseModel)
```

Configuration for Twilio Memory Store integration.

Controls memory retrieval limits, relevance filtering, and profile trait groups.
Memory client is auto-initialized from Conversation Orchestrator configuration.

<a id="tac.core.config.TwilioMemoryConfig.from_env"></a>

#### from\_env

```python
@classmethod
def from_env(cls) -> "TwilioMemoryConfig"
```

Create TwilioMemoryConfig from TWILIO_MEMORY_* environment variables.

<a id="tac.core.config.TACConfig"></a>

## TACConfig Objects

```python
class TACConfig(BaseModel)
```

Configuration model for Twilio Agent Connect settings.

<a id="tac.core.config.TACConfig.from_env"></a>

#### from\_env

```python
@classmethod
def from_env(cls) -> "TACConfig"
```

Create TACConfig from environment variables.

Required:
- TWILIO_ACCOUNT_SID: Twilio Account SID
- TWILIO_AUTH_TOKEN: Twilio Auth Token for API authentication
- TWILIO_API_KEY: Twilio API Key SID (starts with SK)
- TWILIO_API_SECRET: Twilio API Secret for API Key authentication
- TWILIO_PHONE_NUMBER: Phone number for voice and SMS channels

Required for Conversation Orchestrator / Memory / Knowledge:
- TWILIO_CONVERSATION_CONFIGURATION_ID: Conversation Orchestrator configuration ID
  (when omitted, TAC runs in ConversationRelay-only mode)

Optional:
- TWILIO_RCS_SENDER_ID: RCS Sender ID for RCS channel
- TWILIO_WHATSAPP_NUMBER: WhatsApp-enabled phone number
  (format: whatsapp:+1234567890)
- TWILIO_KNOWLEDGE_BASE_ID: Knowledge Base ID for RAG search functionality
- TWILIO_LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
  Default: INFO
- TWILIO_REGION: Twilio region for data residency (e.g., 'au1', 'ie1')
- TWILIO_STUDIO_HANDOFF_FLOW_SID: Studio Flow SID (FWxxx...) for handoff tool

Memory Configuration:
- TWILIO_MEMORY_PROFILE_TRAIT_GROUPS: Trait groups to include
  (comma-separated, e.g., "Contact,Preferences")
- TWILIO_MEMORY_OBSERVATIONS_LIMIT: Max observations in memory retrieval.
  Default: 20
- TWILIO_MEMORY_SUMMARIES_LIMIT: Max summaries in memory retrieval. Default: 5
- TWILIO_MEMORY_COMMUNICATIONS_LIMIT: Max communications in memory retrieval.
  Default: 0
- TWILIO_MEMORY_RELEVANCE_THRESHOLD: Min relevance score (0.0-1.0). Default: 0.0

Conversation Intelligence:
- CONVERSATION_INTELLIGENCE_CONFIGURATION_ID: CI Service configuration ID
  for webhook filtering
- CONVERSATION_INTELLIGENCE_OBSERVATION_OPERATOR_SID: Operator SID for
  observation extraction
- CONVERSATION_INTELLIGENCE_SUMMARY_OPERATOR_SID: Operator SID for summary
  extraction

<a id="tac.core.logging"></a>

# tac.core.logging

Structured logging configuration for the Twilio Agent Connect.

<a id="tac.core.logging.JSONFormatter"></a>

## JSONFormatter Objects

```python
class JSONFormatter(logging.Formatter)
```

JSON formatter for structured logging using only stdlib.

<a id="tac.core.logging.JSONFormatter.__init__"></a>

#### \_\_init\_\_

```python
def __init__(*args: Any, **kwargs: Any) -> None
```

Initialize JSON formatter.

<a id="tac.core.logging.JSONFormatter.format"></a>

#### format

```python
def format(record: logging.LogRecord) -> str
```

Format log record as JSON.

**Arguments**:

- `record` - Log record to format
  

**Returns**:

  JSON-formatted log string

<a id="tac.core.logging.ConsoleFormatter"></a>

## ConsoleFormatter Objects

```python
class ConsoleFormatter(logging.Formatter)
```

Human-readable console formatter with context support.

<a id="tac.core.logging.ConsoleFormatter.format"></a>

#### format

```python
def format(record: logging.LogRecord) -> str
```

Format log record for console output with context.

**Arguments**:

- `record` - Log record to format
  

**Returns**:

  Formatted log string

<a id="tac.core.logging.ContextLogger"></a>

## ContextLogger Objects

```python
class ContextLogger()
```

Logger wrapper that binds context to all log calls.

<a id="tac.core.logging.ContextLogger.__init__"></a>

#### \_\_init\_\_

```python
def __init__(logger: logging.Logger, **context: Any)
```

Initialize context logger.

**Arguments**:

- `logger` - Base logger instance
- `**context` - Context fields to bind to all log calls

<a id="tac.core.logging.ContextLogger.debug"></a>

#### debug

```python
def debug(msg: str, **extra: Any) -> None
```

Log debug message with context.

**Arguments**:

- `msg` - Log message
- `**extra` - Additional fields

<a id="tac.core.logging.ContextLogger.info"></a>

#### info

```python
def info(msg: str, **extra: Any) -> None
```

Log info message with context.

**Arguments**:

- `msg` - Log message
- `**extra` - Additional fields

<a id="tac.core.logging.ContextLogger.warning"></a>

#### warning

```python
def warning(msg: str, **extra: Any) -> None
```

Log warning message with context.

**Arguments**:

- `msg` - Log message
- `**extra` - Additional fields

<a id="tac.core.logging.ContextLogger.error"></a>

#### error

```python
def error(msg: str, exc_info: bool = False, **extra: Any) -> None
```

Log error message with context.

**Arguments**:

- `msg` - Log message
- `exc_info` - Include exception traceback
- `**extra` - Additional fields

<a id="tac.core.logging.ContextLogger.critical"></a>

#### critical

```python
def critical(msg: str, exc_info: bool = False, **extra: Any) -> None
```

Log critical message with context.

**Arguments**:

- `msg` - Log message
- `exc_info` - Include exception traceback
- `**extra` - Additional fields

<a id="tac.core.logging.ContextLogger.bind"></a>

#### bind

```python
def bind(**context: Any) -> "ContextLogger"
```

Create new logger with additional context.

**Arguments**:

- `**context` - Additional context fields to bind
  

**Returns**:

  New ContextLogger with merged context

<a id="tac.core.logging.ContextLogger.isEnabledFor"></a>

#### isEnabledFor

```python
def isEnabledFor(level: int) -> bool
```

Check if logger is enabled for the given level.

Note: Method name uses camelCase to match the standard library's logging.Logger API
for drop-in compatibility with code expecting a Logger interface.

**Arguments**:

- `level` - Logging level to check
  

**Returns**:

  True if logger is enabled for the level

<a id="tac.core.logging.setup_logging"></a>

#### setup\_logging

```python
def setup_logging(log_level: str = "INFO",
                  log_format: str = "json") -> logging.Logger
```

Configure structured logging for TAC framework.

**Arguments**:

- `log_level` - Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `log_format` - Log format - 'json' for structured logs, 'console' for human-readable
  

**Returns**:

  Configured logger instance

<a id="tac.core.logging.get_logger"></a>

#### get\_logger

```python
def get_logger(name: str, **context: Any) -> ContextLogger
```

Get a context-aware logger instance for a specific module.

**Arguments**:

- `name` - Logger name (typically __name__ from the calling module)
- `**context` - Initial context to bind (e.g., conversation_id, channel)
  

**Returns**:

  ContextLogger instance with bound context

<a id="tac.channels.base"></a>

# tac.channels.base

Base channel interface for TAC channels.

<a id="tac.channels.base.BaseChannel"></a>

## BaseChannel Objects

```python
class BaseChannel(ABC)
```

Abstract base class for TAC channels.

Channels handle protocol-specific webhook processing and response delivery
for different communication channels (SMS, Voice, etc.).

This class provides common conversation lifecycle management that is shared
across all channel types.

<a id="tac.channels.base.BaseChannel.__init__"></a>

#### \_\_init\_\_

```python
def __init__(tac: TAC,
             memory_mode: MemoryMode = "never",
             dedup_capacity: int = 10000)
```

Initialize base channel.

**Arguments**:

- `tac` - TAC instance for memory/context operations
- `memory_mode` - Memory retrieval mode. Default is "never".
  - "always": Retrieve memory for every message with the query string
  - "once": Retrieve memory once at conversation start with empty query and cache it.
  Cache is invalidated when conversation becomes INACTIVE.
  - "never": Skip memory retrieval
- `dedup_capacity` - Maximum number of idempotency tokens to track for
  webhook deduplication. Default 10000. Must be positive.

<a id="tac.channels.base.BaseChannel.process_webhook"></a>

#### process\_webhook

```python
@abstractmethod
async def process_webhook(webhook_data: dict[str, Any],
                          idempotency_token: str | None = None) -> None
```

Process incoming webhook event from Twilio.

This method should:
1. Parse and validate webhook data
2. Handle conversation lifecycle (start, message, end)
3. Trigger memory retrieval via TAC
4. Invoke registered callbacks

**Arguments**:

- `webhook_data` - Raw webhook event data from Twilio
- `idempotency_token` - Optional Twilio idempotency token from request headers

<a id="tac.channels.base.BaseChannel.send_response"></a>

#### send\_response

```python
@abstractmethod
async def send_response(conversation_id: str,
                        response: str
                        | AsyncGenerator[str | dict[str, Any], None],
                        role: str | None = None) -> None
```

Send response back through the channel.

Supports both simple string responses and streaming via async generators.

**Arguments**:

- `conversation_id` - Conversation ID to send response to
- `response` - Message content (string) or async generator for streaming
- `role` - Optional message role (e.g., 'assistant', 'user', 'system')

<a id="tac.channels.base.BaseChannel.get_channel_name"></a>

#### get\_channel\_name

```python
@abstractmethod
def get_channel_name() -> str
```

Get the channel name identifier.

**Returns**:

  Channel name (e.g., 'sms', 'voice')

<a id="tac.channels.base.BaseChannel.get_channel_type_upper"></a>

#### get\_channel\_type\_upper

```python
def get_channel_type_upper() -> str
```

Get uppercase channel type for webhook filtering.

**Returns**:

  Uppercase channel type (e.g., 'SMS', 'VOICE')

<a id="tac.channels.messaging"></a>

# tac.channels.messaging

MessagingChannel base class for messaging channels (SMS, RCS, WhatsApp, Chat).

<a id="tac.channels.messaging.MessagingChannelConfig"></a>

## MessagingChannelConfig Objects

```python
class MessagingChannelConfig(BaseModel)
```

Base configuration for messaging channels (SMS, RCS, WhatsApp, Chat).

**Attributes**:

- `dedup_capacity` - Maximum number of idempotency tokens to track.
  Default 10000 is suitable for most applications.
  Uses Twilio's i-twilio-idempotency-token header for deduplication.
- `memory_mode` - Memory retrieval mode. Default is "never".
  - "always": Retrieve memory for every message with the query string
  - "once": Retrieve memory once at conversation start with empty query and cache it.
  Cache is invalidated when conversation becomes INACTIVE and is fetched
  again the next time a message triggers memory retrieval after the
  conversation becomes ACTIVE.
  - "never": Skip memory retrieval

<a id="tac.channels.messaging.MessagingChannel"></a>

## MessagingChannel Objects

```python
class MessagingChannel(BaseChannel)
```

Abstract base class for messaging channels (SMS, RCS, WhatsApp, Chat).

Provides shared webhook processing logic for channels that use
Conversation Orchestrator webhooks with COMMUNICATION_CREATED
and CONVERSATION_UPDATED event types.

Subclasses must implement:
- is_default_agent_address(): Fast-path check for the channel's default agent address
- get_channel_type_upper(): Return uppercase channel type ("SMS", "RCS", "WHATSAPP", "CHAT")
- get_agent_address(conversation_id): Return the agent's ParticipantAddress for a conversation
- send_response(): Send messages back through the channel
- get_channel_name(): Return lowercase channel name ("sms", "rcs", "whatsapp", "chat")

Subclass class attributes:
- reconcile_customer_type: If True, reconciliation will also promote a
  channel-matching UNKNOWN participant (not owning the agent address) to
  CUSTOMER. Set False for channels where the customer is identified
  author-driven (e.g. chat).

<a id="tac.channels.messaging.MessagingChannel.is_default_agent_address"></a>

#### is\_default\_agent\_address

```python
@abstractmethod
def is_default_agent_address(author_address: str) -> bool
```

Fast-path check: is the author address this channel's default agent address?

For example, config.phone_number for SMS, config.rcs_sender_id for RCS,
config.whatsapp_number for WhatsApp, agent_address for Chat.

**Arguments**:

- `author_address` - The address of the message author
  

**Returns**:

  True if the address matches the channel's default agent address

<a id="tac.channels.messaging.MessagingChannel.get_channel_type_upper"></a>

#### get\_channel\_type\_upper

```python
@abstractmethod
def get_channel_type_upper() -> str
```

Return the uppercase channel type for webhook filtering.

**Returns**:

  Channel type string (e.g., "SMS", "CHAT")

<a id="tac.channels.messaging.MessagingChannel.get_agent_address"></a>

#### get\_agent\_address

```python
@abstractmethod
def get_agent_address(conversation_id: str) -> ParticipantAddress
```

Return the agent-side ParticipantAddress for this conversation.

Used by `_reconcile_participants` to identify which participant (by
channel + address) represents the agent. May read from session state
(e.g. chat's per-conversation channelId) to build the address.

<a id="tac.channels.messaging.MessagingChannel.process_webhook"></a>

#### process\_webhook

```python
async def process_webhook(webhook_data: dict[str, Any],
                          idempotency_token: str | None = None) -> None
```

Process messaging channel webhook event and manage conversation lifecycle.

Handles:
- COMMUNICATION_CREATED: Process incoming messages from customers
- CONVERSATION_UPDATED: Clean up when conversation is closed

Note: Conversation tracking uses instance-local memory. In multi-instance
deployments, webhooks may route to a different instance, preventing cleanup.
See CLAUDE.md for horizontal scaling considerations.

**Arguments**:

- `webhook_data` - Raw webhook event data from Twilio
- `idempotency_token` - Optional Twilio idempotency token from request headers

<a id="tac.channels.sms"></a>

# tac.channels.sms

SMS Channel implementation for TAC.

<a id="tac.channels.sms.SMSChannelConfig"></a>

## SMSChannelConfig Objects

```python
class SMSChannelConfig(MessagingChannelConfig)
```

Configuration for SMS channel.

Inherits dedup_capacity and memory_mode from MessagingChannelConfig.

<a id="tac.channels.sms.SMSChannel"></a>

## SMSChannel Objects

```python
class SMSChannel(MessagingChannel)
```

SMS Channel for handling SMS-based conversations.

Inherits shared messaging channel webhook processing from MessagingChannel
and provides SMS-specific message sending and filtering.

<a id="tac.channels.sms.SMSChannel.send_response"></a>

#### send\_response

```python
async def send_response(conversation_id: str,
                        response: str
                        | AsyncGenerator[str | dict[str, Any], None],
                        role: str | None = None) -> None
```

Send SMS response using the Conversation Orchestrator Send API.

Reads the agent and customer participant ids stashed on the session
by inbound reconciliation or outbound initiation. Missing ids are a
misuse — send_response is only expected to be called after an inbound
webhook (COMMUNICATION_CREATED → reconcile) or after
`initiate_outbound_conversation`, both of which populate the session.

**Arguments**:

- `conversation_id` - Conversation ID to send response to
- `response` - Message content (must be string for SMS)
- `role` - Optional message role (not used in SMS channel)
  

**Raises**:

- `TypeError` - If response is not a string
- `RuntimeError` - If the session or participant ids are missing

<a id="tac.channels.sms.SMSChannel.initiate_outbound_conversation"></a>

#### initiate\_outbound\_conversation

```python
async def initiate_outbound_conversation(
    options: InitiateMessagingConversationOptions
) -> InitiateConversationResult
```

Initiate an outbound SMS conversation.

Creates a conversation via Conversation Orchestrator with inline
participants, then sends the initial message via the Actions API.
If an active conversation with the same addresses already exists
(group-by dedup), CO returns 409 and the existing conversation is reused.

<a id="tac.channels.rcs"></a>

# tac.channels.rcs

RCS Channel implementation for TAC.

<a id="tac.channels.rcs.RCSChannelConfig"></a>

## RCSChannelConfig Objects

```python
class RCSChannelConfig(MessagingChannelConfig)
```

Configuration for RCS channel.

Inherits dedup_capacity and memory_mode from MessagingChannelConfig.

<a id="tac.channels.rcs.RCSChannel"></a>

## RCSChannel Objects

```python
class RCSChannel(MessagingChannel)
```

RCS Channel for handling RCS-based conversations.

Inherits shared messaging channel webhook processing from MessagingChannel
and provides RCS-specific message sending and filtering.

RCS uses RCS Sender IDs configured in TACConfig (via TWILIO_RCS_SENDER_ID).

<a id="tac.channels.rcs.RCSChannel.is_default_agent_address"></a>

#### is\_default\_agent\_address

```python
def is_default_agent_address(author_address: str) -> bool
```

Check if the author address matches the configured RCS sender ID.

<a id="tac.channels.rcs.RCSChannel.get_agent_address"></a>

#### get\_agent\_address

```python
def get_agent_address(conversation_id: str) -> ParticipantAddress
```

Get the agent's participant address for this conversation.

<a id="tac.channels.rcs.RCSChannel.send_response"></a>

#### send\_response

```python
async def send_response(conversation_id: str,
                        response: str
                        | AsyncGenerator[str | dict[str, Any], None],
                        role: str | None = None) -> None
```

Send RCS response using the Conversation Orchestrator Send API.

Reads the agent and customer participant ids stashed on the session
by inbound reconciliation or outbound initiation. Missing ids are a
misuse — send_response is only expected to be called after an inbound
webhook (COMMUNICATION_CREATED → reconcile) or after
`initiate_outbound_conversation`, both of which populate the session.

**Arguments**:

- `conversation_id` - Conversation ID to send response to
- `response` - Message content (must be string for RCS)
- `role` - Optional message role (not used in RCS channel)
  

**Raises**:

- `TypeError` - If response is not a string
- `RuntimeError` - If the session or participant ids are missing

<a id="tac.channels.rcs.RCSChannel.initiate_outbound_conversation"></a>

#### initiate\_outbound\_conversation

```python
async def initiate_outbound_conversation(
    options: InitiateMessagingConversationOptions
) -> InitiateConversationResult
```

Initiate an outbound RCS conversation.

Creates a conversation via Conversation Orchestrator with inline
participants, then sends the initial message via the Actions API.
Uses the RCS sender ID from TACConfig as the from address.
If an active conversation with the same addresses already exists
(group-by dedup), CO returns 409 and the existing conversation is reused.

**Arguments**:

- `options` - Conversation initiation options (to address and message)
  

**Returns**:

  InitiateConversationResult with conversation_id and session
  

**Raises**:

- `RuntimeError` - If rcs_sender_id is not configured

<a id="tac.channels.whatsapp"></a>

# tac.channels.whatsapp

WhatsApp Channel implementation for TAC.

<a id="tac.channels.whatsapp.WhatsAppChannelConfig"></a>

## WhatsAppChannelConfig Objects

```python
class WhatsAppChannelConfig(MessagingChannelConfig)
```

Configuration for WhatsApp channel.

Inherits dedup_capacity and memory_mode from MessagingChannelConfig.

<a id="tac.channels.whatsapp.WhatsAppChannel"></a>

## WhatsAppChannel Objects

```python
class WhatsAppChannel(MessagingChannel)
```

WhatsApp Channel for handling WhatsApp-based conversations.

Inherits shared messaging channel webhook processing from MessagingChannel
and provides WhatsApp-specific message sending and filtering.

WhatsApp uses WhatsApp sender phone numbers configured in TACConfig
(via TWILIO_WHATSAPP_NUMBER). Address format: whatsapp:+1234567890

<a id="tac.channels.whatsapp.WhatsAppChannel.is_default_agent_address"></a>

#### is\_default\_agent\_address

```python
def is_default_agent_address(author_address: str) -> bool
```

Check if the author address matches the configured WhatsApp number.

<a id="tac.channels.whatsapp.WhatsAppChannel.get_agent_address"></a>

#### get\_agent\_address

```python
def get_agent_address(conversation_id: str) -> ParticipantAddress
```

Get the agent's participant address for this conversation.

<a id="tac.channels.whatsapp.WhatsAppChannel.send_response"></a>

#### send\_response

```python
async def send_response(conversation_id: str,
                        response: str
                        | AsyncGenerator[str | dict[str, Any], None],
                        role: str | None = None) -> None
```

Send WhatsApp response using the Conversation Orchestrator Send API.

Reads the agent and customer participant ids stashed on the session
by inbound reconciliation or outbound initiation. Missing ids are a
misuse — send_response is only expected to be called after an inbound
webhook (COMMUNICATION_CREATED → reconcile) or after
`initiate_outbound_conversation`, both of which populate the session.

**Arguments**:

- `conversation_id` - Conversation ID to send response to
- `response` - Message content (must be string for WhatsApp)
- `role` - Optional message role (not used in WhatsApp channel)
  

**Raises**:

- `TypeError` - If response is not a string
- `RuntimeError` - If the session or participant ids are missing

<a id="tac.channels.whatsapp.WhatsAppChannel.initiate_outbound_conversation"></a>

#### initiate\_outbound\_conversation

```python
async def initiate_outbound_conversation(
    options: InitiateMessagingConversationOptions
) -> InitiateConversationResult
```

Initiate an outbound WhatsApp conversation.

Creates a conversation via Conversation Orchestrator with inline
participants, then sends the initial message via the Actions API.
Uses the WhatsApp number from TACConfig as the from address.
If an active conversation with the same addresses already exists
(group-by dedup), CO returns 409 and the existing conversation is reused.

**Arguments**:

- `options` - Conversation initiation options (to address and message)
  

**Returns**:

  InitiateConversationResult with conversation_id and session
  

**Raises**:

- `RuntimeError` - If whatsapp_number is not configured

<a id="tac.channels.chat"></a>

# tac.channels.chat

Chat Channel implementation for TAC.

<a id="tac.channels.chat.ChatChannelConfig"></a>

## ChatChannelConfig Objects

```python
class ChatChannelConfig(MessagingChannelConfig)
```

Configuration for Chat channel.

**Attributes**:

- `agent_address` - Chat agent identity string used to identify the bot's messages.

<a id="tac.channels.chat.ChatChannel"></a>

## ChatChannel Objects

```python
class ChatChannel(MessagingChannel)
```

Chat Channel for handling web chat conversations.

Uses identity-based addressing instead of phone numbers.
Automatically creates AI_AGENT participant if needed (lazy creation)
and manages conversation lifecycle through Conversation Orchestrator webhooks.

<a id="tac.channels.chat.ChatChannel.send_response"></a>

#### send\_response

```python
async def send_response(conversation_id: str,
                        response: str
                        | AsyncGenerator[str | dict[str, Any], None],
                        role: str | None = None) -> None
```

Send chat response using the Conversation Orchestrator Send API.

Reads the agent and customer participant ids stashed on the session
by inbound reconciliation or outbound initiation. Missing ids are a
misuse — send_response is only expected to be called after an inbound
webhook (COMMUNICATION_CREATED → reconcile) or after
`initiate_outbound_conversation`, both of which populate the session.

**Arguments**:

- `conversation_id` - Conversation ID to send response to
- `response` - Message content (must be string for Chat)
- `role` - Optional message role (not used in Chat channel)
  

**Raises**:

- `TypeError` - If response is not a string
- `RuntimeError` - If the session, channel_id, or participant ids are missing

<a id="tac.channels.chat.ChatChannel.initiate_outbound_conversation"></a>

#### initiate\_outbound\_conversation

```python
async def initiate_outbound_conversation(
        options: InitiateChatConversationOptions
) -> InitiateConversationResult
```

Initiate an outbound Chat conversation.

Creates a conversation via Conversation Orchestrator with inline
participants, then sends the initial message via the Actions API.
If an active conversation with the same addresses already exists
(group-by dedup), CO returns 409 and the existing conversation is reused.

<a id="tac.channels.voice.config"></a>

# tac.channels.voice.config

Voice channel configuration.

<a id="tac.channels.voice.config.VoiceChannelConfig"></a>

## VoiceChannelConfig Objects

```python
class VoiceChannelConfig(BaseModel)
```

Configuration for Voice channel.

**Attributes**:

- `session_manager` - SessionManager for tracking and canceling in-flight tasks.
  Defaults to ThreadSafeSessionManager for automatic task cancellation on
  interrupts and new prompts. Set to None only for debugging/testing.
- `memory_mode` - Memory retrieval mode. Default is "never".
  - "always": Retrieve memory for every message with the query string
  - "once": Retrieve memory once at conversation start with empty query and cache it.
  Cache is invalidated when conversation becomes INACTIVE.
  - "never": Skip memory retrieval

<a id="tac.channels.voice.channel"></a>

# tac.channels.voice.channel

<a id="tac.channels.voice.channel.VoiceChannel"></a>

## VoiceChannel Objects

```python
class VoiceChannel(BaseChannel)
```

Voice Channel for handling voice-based conversations via WebSocket.

Key features:
- TwiML generation for incoming calls (see twiml module)
- WebSocket connection management for real-time voice streaming
- Conversation lifecycle management (inherited from BaseChannel)
- Outbound call initiation

This channel is framework-agnostic and accepts any WebSocket implementation
satisfying WebSocketProtocol. For a batteries-included FastAPI server, use
tac.server.TACFastAPIServer.

<a id="tac.channels.voice.channel.VoiceChannel.__init__"></a>

#### \_\_init\_\_

```python
def __init__(tac: TAC,
             config: VoiceChannelConfig | dict[str, Any] | None = None)
```

Initialize Voice channel for websocket protocol handling.

**Arguments**:

- `tac` - TAC instance for memory/context operations
- `config` - Voice channel configuration (VoiceChannelConfig or dict).
  If None, uses default configuration.
  

**Examples**:

  >>> channel = VoiceChannel(tac, config={"memory_mode": "always"})
  >>> channel = VoiceChannel(tac, config=VoiceChannelConfig(session_manager=sm))
  >>> channel = VoiceChannel(tac)  # Use defaults

<a id="tac.channels.voice.channel.VoiceChannel.handle_incoming_call"></a>

#### handle\_incoming\_call

```python
async def handle_incoming_call(options: TwiMLOptions | dict[str, Any]) -> str
```

Generate TwiML response for incoming voice calls.

ConversationRelay automatically handles conversation creation and participant
management via the conversation_configuration parameter.

**Arguments**:

- `options` - TwiML generation options (TwiMLOptions or dict) containing:
  - websocket_url (required): WebSocket URL for ConversationRelay
  - custom_parameters (optional): Additional custom parameters
  - welcome_greeting (optional): Initial greeting message
  - action_url (optional): URL for call completion webhook
  

**Returns**:

  TwiML XML string for call connection
  

**Example**:

  >>> twiml = await voice_channel.handle_incoming_call(
  ...     options={
  ...         "websocket_url": "wss://example.com/ws",
  ...         "custom_parameters": {"session_id": "sess_123"},
  ...         "welcome_greeting": "Hello!",
  ...         "action_url": "https://example.com/callback",
  ...     },
  ... )

<a id="tac.channels.voice.channel.VoiceChannel.handle_conversation_relay_callback"></a>

#### handle\_conversation\_relay\_callback

```python
async def handle_conversation_relay_callback(
        payload_dict: dict[str, str]) -> None
```

Handle ConversationRelay callback webhook from Twilio.

In relay-only mode, this is a secondary mechanism for cleaning up
conversation state when a call ends (the primary mechanism is websocket
disconnect). In orchestrated mode, conversation lifecycle is managed by
CO webhooks, so this is a no-op.

**Arguments**:

- `payload_dict` - Raw form data dict from the webhook request.

<a id="tac.channels.voice.channel.VoiceChannel.handle_websocket"></a>

#### handle\_websocket

```python
async def handle_websocket(websocket: WebSocketProtocol) -> None
```

Handle voice streaming WebSocket connection lifecycle.

This method manages the entire websocket connection:
- Accepts the connection
- Processes incoming messages
- Tracks and cancels in-flight tasks (if session_manager provided)
- Cleans up on disconnect

**Arguments**:

- `websocket` - Any WebSocket implementation satisfying WebSocketProtocol

<a id="tac.channels.voice.channel.VoiceChannel.initiate_outbound_conversation"></a>

#### initiate\_outbound\_conversation

```python
async def initiate_outbound_conversation(
    options: InitiateVoiceConversationOptions
) -> InitiateVoiceConversationResult
```

Initiate an outbound voice conversation.

Places an outbound call with inline TwiML that connects to ConversationRelay.
The conversationConfiguration attribute tells CO to create and manage the
conversation during passive hydration. The session is initialized lazily
on the first prompt when the conversation is discovered by callSid.

``options.websocket_url`` must be the publicly accessible WebSocket
endpoint (e.g., ``wss://your-domain.ngrok.app/ws``). Unlike inbound calls
where TACServer sets this automatically, outbound calls require it
explicitly since there is no incoming HTTP request to derive the host from.

<a id="tac.channels.voice.channel.VoiceChannel.process_webhook"></a>

#### process\_webhook

```python
async def process_webhook(webhook_data: dict[str, Any],
                          idempotency_token: str | None = None) -> None
```

Process conversation webhooks for cleanup and cache invalidation.

Voice channel processes CONVERSATION_UPDATED events:
- CLOSED status: Clean up local session state
- INACTIVE status: Invalidate cached memory (memory will be updated by
Conversation Orchestrator)

Note: Conversation tracking uses instance-local memory. In multi-instance
deployments, webhooks may route to a different instance, preventing cleanup.
See CLAUDE.md for horizontal scaling considerations.

**Arguments**:

- `webhook_data` - Raw webhook event data from Twilio
- `idempotency_token` - Optional Twilio idempotency token from request headers

<a id="tac.channels.voice.channel.VoiceChannel.send_response"></a>

#### send\_response

```python
async def send_response(conversation_id: str,
                        response: str
                        | AsyncGenerator[str | dict[str, Any], None],
                        role: str | None = None) -> None
```

Send voice response through the websocket connection for this conversation.

Supports both simple string responses and streaming async generators.

**Arguments**:

- `conversation_id` - Conversation ID
- `response` - Response text (string) or async generator for streaming
- `role` - Optional message role (not used in this implementation, but kept
  for API consistency with BaseChannel interface)

<a id="tac.channels.voice.channel.VoiceChannel.get_websocket"></a>

#### get\_websocket

```python
def get_websocket(conversation_id: str) -> WebSocketProtocol | None
```

Get the WebSocket connection for a specific conversation.

**Arguments**:

- `conversation_id` - Conversation ID
  

**Returns**:

  WebSocket connection if exists, None otherwise

<a id="tac.channels.voice.twiml"></a>

# tac.channels.voice.twiml

TwiML generation for voice channel.

<a id="tac.channels.voice.twiml.generate_twiml"></a>

#### generate\_twiml

```python
def generate_twiml(options: TwiMLOptions | dict[str, Any]) -> str
```

Generate TwiML XML for ConversationRelay with custom parameters.

This is a low-level function for generating TwiML with arbitrary custom
parameters. For automatic conversation creation and participant management,
use VoiceChannel.handle_incoming_call() instead.

**Arguments**:

- `options` - TwiML generation options (TwiMLOptions model or dict with:
  - websocket_url (required): WebSocket URL for ConversationRelay
  - custom_parameters (optional): Dict of custom parameters
  - welcome_greeting (optional): Initial greeting message
  - action_url (optional): URL for call end webhook
  - conversation_configuration (optional): Conversation Service SID for
  automatic conversation creation
  

**Returns**:

  TwiML XML string ready to return to Twilio
  

**Example**:

  >>> twiml = generate_twiml(
  ...     {
  ...         "websocket_url": "wss://example.com/voice",
  ...         "custom_parameters": {
  ...             "session_id": "sess_abc123",
  ...             "user_language": "es",
  ...         },
  ...         "welcome_greeting": "Hello!",
  ...         "conversation_configuration": "conv_configuration_xxxx",
  ...     }
  ... )

<a id="tac.channels.websocket_protocol"></a>

# tac.channels.websocket\_protocol

WebSocket protocol abstraction for framework-agnostic channel implementation.

Defines a Protocol class that any WebSocket implementation (FastAPI, Starlette,
custom, etc.) can satisfy, along with a common disconnect error type.

<a id="tac.channels.websocket_protocol.WebSocketDisconnectError"></a>

## WebSocketDisconnectError Objects

```python
class WebSocketDisconnectError(Exception)
```

Raised when a WebSocket connection is unexpectedly closed.

<a id="tac.channels.websocket_protocol.WebSocketProtocol"></a>

## WebSocketProtocol Objects

```python
@runtime_checkable
class WebSocketProtocol(Protocol)
```

Protocol defining the WebSocket interface used by VoiceChannel.

Any WebSocket implementation that provides these async methods can be used
with VoiceChannel, including FastAPI WebSocket, raw Starlette WebSocket,
or custom adapters.

<a id="tac.channels.websocket_manager"></a>

# tac.channels.websocket\_manager

WebSocket connection management for voice channels.

Provides WebSocket connection tracking for concurrent conversations,
enabling proper response routing in multi-connection scenarios.

<a id="tac.channels.websocket_manager.WebSocketManager"></a>

## WebSocketManager Objects

```python
class WebSocketManager()
```

Manager for WebSocket connections per conversation.

Manages the mapping between conversation IDs and their associated WebSocket
connections, enabling proper response routing when multiple calls are active
simultaneously.

This manager is separate from SessionManager (which handles LLM streaming tasks)
to maintain clean separation of concerns:
- WebSocketManager: Connection routing and lifecycle
- SessionManager: LLM streaming and task cancellation

Thread safety: No locking needed because each conversation operates on different
dict keys, and Python's dict operations are atomic for simple get/set/delete.

**Example**:

  >>> ws_manager = WebSocketManager()
  >>> ws_manager.add_websocket("conv_123", websocket)
  >>> ws = ws_manager.get_websocket("conv_123")
  >>> await ws.send_text("Hello")
  >>> ws_manager.remove_websocket("conv_123")

<a id="tac.channels.websocket_manager.WebSocketManager.__init__"></a>

#### \_\_init\_\_

```python
def __init__() -> None
```

Initialize WebSocket manager.

<a id="tac.channels.websocket_manager.WebSocketManager.add_websocket"></a>

#### add\_websocket

```python
def add_websocket(conversation_id: str, websocket: WebSocketProtocol) -> None
```

Store WebSocket connection for a conversation.

**Arguments**:

- `conversation_id` - Unique conversation identifier
- `websocket` - WebSocket connection satisfying WebSocketProtocol

<a id="tac.channels.websocket_manager.WebSocketManager.get_websocket"></a>

#### get\_websocket

```python
def get_websocket(conversation_id: str) -> WebSocketProtocol | None
```

Retrieve WebSocket connection for a conversation.

**Arguments**:

- `conversation_id` - Unique conversation identifier
  

**Returns**:

  WebSocket connection if exists, None otherwise

<a id="tac.channels.websocket_manager.WebSocketManager.has_websocket"></a>

#### has\_websocket

```python
def has_websocket(conversation_id: str) -> bool
```

Check if WebSocket exists for a conversation.

**Arguments**:

- `conversation_id` - Unique conversation identifier
  

**Returns**:

  True if WebSocket connection exists, False otherwise

<a id="tac.channels.websocket_manager.WebSocketManager.remove_websocket"></a>

#### remove\_websocket

```python
def remove_websocket(conversation_id: str) -> None
```

Remove WebSocket connection for a conversation.

**Arguments**:

- `conversation_id` - Unique conversation identifier

<a id="tac.channels.websocket_manager.WebSocketManager.get_all_conversation_ids"></a>

#### get\_all\_conversation\_ids

```python
def get_all_conversation_ids() -> list[str]
```

Get list of all active conversation IDs.

**Returns**:

  List of conversation IDs with active WebSocket connections

<a id="tac.channels.websocket_manager.WebSocketManager.__len__"></a>

#### \_\_len\_\_

```python
def __len__() -> int
```

Get count of active WebSocket connections.

**Returns**:

  Number of active connections

<a id="tac.models.tac"></a>

# tac.models.tac

TAC unified response models.

<a id="tac.models.tac.TACCommunicationAuthor"></a>

## TACCommunicationAuthor Objects

```python
class TACCommunicationAuthor(BaseModel)
```

Unified author model with all fields from both Memory and Conversation Orchestrator APIs.

<a id="tac.models.tac.TACCommunicationContent"></a>

## TACCommunicationContent Objects

```python
class TACCommunicationContent(BaseModel)
```

Unified content model with all fields from both Memory and Conversation Orchestrator APIs.

<a id="tac.models.tac.TACCommunication"></a>

## TACCommunication Objects

```python
class TACCommunication(BaseModel)
```

Unified communication model with all fields from both Memory and Conversation Orchestrator APIs.

Provides complete access to all communication fields regardless of the source.
Fields not available from a particular API will be None.

<a id="tac.models.tac.TACMemoryResponse"></a>

## TACMemoryResponse Objects

```python
class TACMemoryResponse()
```

Unified response wrapper for TAC.retrieve_memory().

Provides a consistent interface for accessing memory data regardless of whether
Memory API is configured or falling back to Conversation Orchestrator Communications API.

Memory configured:
- observations, summaries, communications all populated
- communications include Memory-specific fields (author id, name, type, profile_id)

Conversation Orchestrator fallback:
- observations and summaries are empty lists
- communications include Conversation Orchestrator-specific fields
  (conversation_id, account_id, etc.)

<a id="tac.models.tac.TACMemoryResponse.__init__"></a>

#### \_\_init\_\_

```python
def __init__(data: MemoryRetrievalResponse | list[Communication])
```

Initialize wrapper with either Memory or Conversation Orchestrator data.

**Arguments**:

- `data` - Either MemoryRetrievalResponse (Memory) or
  list[Communication] (Conversation Orchestrator)

<a id="tac.models.tac.TACMemoryResponse.observations"></a>

#### observations

```python
@property
def observations() -> list[ObservationInfo]
```

Get observation memories.

**Returns**:

  List of observations if Memory is configured,
  empty list for Conversation Orchestrator fallback

<a id="tac.models.tac.TACMemoryResponse.summaries"></a>

#### summaries

```python
@property
def summaries() -> list[SummaryInfo]
```

Get summary memories.

**Returns**:

  List of summaries if Memory is configured,
  empty list for Conversation Orchestrator fallback

<a id="tac.models.tac.TACMemoryResponse.communications"></a>

#### communications

```python
@property
def communications() -> list[TACCommunication]
```

Get communications in unified format with all available fields.

Communications are converted to a common format during initialization that includes
all fields from both Memory and Conversation Orchestrator APIs.
Fields not available from a particular
API will be None.

**Returns**:

  List of unified communications with all available fields

<a id="tac.models.tac.TACMemoryResponse.has_memory_features"></a>

#### has\_memory\_features

```python
@property
def has_memory_features() -> bool
```

Check if Memory API is configured and providing full features.

**Returns**:

  True if Memory is configured (observations/summaries available),
  False if using Conversation Orchestrator fallback (only communications available)

<a id="tac.models.tac.TACMemoryResponse.raw_data"></a>

#### raw\_data

```python
@property
def raw_data() -> MemoryRetrievalResponse | list[Communication]
```

Access raw underlying data for advanced use cases.

Use this when you need access to all fields from the original API responses,
not just the simplified common fields.

**Returns**:

  Either MemoryRetrievalResponse or list[Communication] depending on configuration

<a id="tac.models.tac.TACMemoryResponse.build_memory_prompts"></a>

#### build\_memory\_prompts

```python
def build_memory_prompts() -> list[str]
```

Build all memory prompt sections (observations, summaries, communications) for LLM context.

**Returns**:

  List of LLM prompt sections. Each element is a complete section
  (e.g., observations section, summaries section). Returns empty list
  if no memory data is available.
  

**Example**:

  >>> sections = memory_response.build_memory_prompts()
  >>> for section in sections:
  ...     print(section)
  ...     print()
  ## Key Observations
  Important notes about the customer from previous interactions:
  - Customer prefers email communication
  - Previously reported billing issue (resolved)
  
  ## Past Conversation Summaries
  Summaries of previous conversations with this customer:
  - Discussed product features and pricing on 2024-01-15

<a id="tac.models.session"></a>

# tac.models.session

<a id="tac.models.session.AuthorInfo"></a>

## AuthorInfo Objects

```python
class AuthorInfo(BaseModel)
```

Information about the author of a communication.

<a id="tac.models.session.ConversationSession"></a>

## ConversationSession Objects

```python
class ConversationSession(BaseModel)
```

Context information for a conversation session that's passed to callbacks.

This provides the necessary context for developers to handle memory-ready
events and send responses back through the appropriate channel.

<a id="tac.models.session.ConversationSession.build_profile_prompt"></a>

#### build\_profile\_prompt

```python
def build_profile_prompt(trait_groups: list[str] | None = None) -> str | None
```

Build customer profile prompt section for LLM context.

**Arguments**:

- `trait_groups` - Optional list of trait group names to include.
  If None, no filtering is applied.
  

**Returns**:

  LLM prompt section with profile data, or None if no profile data
  is available or no traits match the filter.
  

**Example**:

  >>> section = context.build_profile_prompt(["Contact", "Preferences"])
  >>> print(section)
  ## Customer Profile
  Information about this customer:
  - Contact: {"name": "John Doe", "email": "john@example.com"}
  - Preferences: {"language": "en", "timezone": "PST"}

<a id="tac.models.conversation"></a>

# tac.models.conversation

Pydantic models for Twilio Conversation Orchestrator API.

<a id="tac.models.conversation.StatusTimeouts"></a>

## StatusTimeouts Objects

```python
class StatusTimeouts(BaseModel)
```

Timeout settings for channel status transitions.

<a id="tac.models.conversation.CaptureRule"></a>

## CaptureRule Objects

```python
class CaptureRule(BaseModel)
```

Capture rule with from/to addresses and optional metadata.

<a id="tac.models.conversation.ChannelSettings"></a>

## ChannelSettings Objects

```python
class ChannelSettings(BaseModel)
```

Configuration settings for a specific channel type.

<a id="tac.models.conversation.StatusCallback"></a>

## StatusCallback Objects

```python
class StatusCallback(BaseModel)
```

Webhook configuration for status callbacks.

<a id="tac.models.conversation.ParticipantAddress"></a>

## ParticipantAddress Objects

```python
class ParticipantAddress(BaseModel)
```

Communication address for a conversation participant.

<a id="tac.models.conversation.ConversationConfiguration"></a>

## ConversationConfiguration Objects

```python
class ConversationConfiguration(BaseModel)
```

Configuration settings for a conversation response.

<a id="tac.models.conversation.ConversationRequest"></a>

## ConversationRequest Objects

```python
class ConversationRequest(BaseModel)
```

Request payload for creating a conversation.

<a id="tac.models.conversation.UpdateConversationRequest"></a>

## UpdateConversationRequest Objects

```python
class UpdateConversationRequest(BaseModel)
```

Request payload for updating a conversation.

<a id="tac.models.conversation.ConversationResponse"></a>

## ConversationResponse Objects

```python
class ConversationResponse(BaseModel)
```

Response from creating a conversation.

<a id="tac.models.conversation.ParticipantRequest"></a>

## ParticipantRequest Objects

```python
class ParticipantRequest(BaseModel)
```

Request payload for creating a conversation participant.

<a id="tac.models.conversation.ParticipantResponse"></a>

## ParticipantResponse Objects

```python
class ParticipantResponse(BaseModel)
```

Response from creating a participant.

<a id="tac.models.conversation.CommunicationParticipant"></a>

## CommunicationParticipant Objects

```python
class CommunicationParticipant(BaseModel)
```

Author or recipient in a communication.

<a id="tac.models.conversation.TranscriptionWord"></a>

## TranscriptionWord Objects

```python
class TranscriptionWord(BaseModel)
```

Word-level transcription data with timing information.

<a id="tac.models.conversation.Transcription"></a>

## Transcription Objects

```python
class Transcription(BaseModel)
```

Transcription metadata for communication content.

<a id="tac.models.conversation.CommunicationContent"></a>

## CommunicationContent Objects

```python
class CommunicationContent(BaseModel)
```

Content of a communication (ContentText or ContentTranscription).

<a id="tac.models.conversation.Communication"></a>

## Communication Objects

```python
class Communication(BaseModel)
```

A communication representing a message exchanged in a conversation.

<a id="tac.models.conversation.CommunicationRequest"></a>

## CommunicationRequest Objects

```python
class CommunicationRequest(BaseModel)
```

Request payload for adding a communication.

<a id="tac.models.conversation.CommunicationsListResponse"></a>

## CommunicationsListResponse Objects

```python
class CommunicationsListResponse(BaseModel)
```

Response from list communications endpoint.

<a id="tac.models.conversation.ConversationsListResponse"></a>

## ConversationsListResponse Objects

```python
class ConversationsListResponse(BaseModel)
```

Response from list conversations endpoint.

<a id="tac.models.conversation.ActionParticipantRef"></a>

## ActionParticipantRef Objects

```python
class ActionParticipantRef(BaseModel)
```

Participant reference for the Actions API (`from`/`to` entries).

Either `participant_id` or `address` must be supplied; `channel` is always required.
When both are provided, Conversation Orchestrator uses `participant_id` and
`channel` disambiguates
which of the participant's addresses to use.

<a id="tac.models.conversation.ActionTextContent"></a>

## ActionTextContent Objects

```python
class ActionTextContent(BaseModel)
```

Plain-text content for a SEND_MESSAGE action.

<a id="tac.models.conversation.ActionChannelSettings"></a>

## ActionChannelSettings Objects

```python
class ActionChannelSettings(BaseModel)
```

Channel-specific settings forwarded to the downstream backend.

Open pass-through: any field not explicitly modeled here (e.g.
`messagingServiceSid`, `statusCallback`, `Attributes`) can be set by callers and
will be forwarded as-is.

<a id="tac.models.conversation.SendMessageActionPayload"></a>

## SendMessageActionPayload Objects

```python
class SendMessageActionPayload(BaseModel)
```

Inner payload for a SEND_MESSAGE action.

<a id="tac.models.conversation.SendMessageActionRequest"></a>

## SendMessageActionRequest Objects

```python
class SendMessageActionRequest(BaseModel)
```

Request for POST /v2/Conversations/{id}/Actions with type=SEND_MESSAGE.

Body is discriminated by `type` with the action-specific fields under `payload`.

<a id="tac.models.conversation.ActionResponse"></a>

## ActionResponse Objects

```python
class ActionResponse(BaseModel)
```

Response from POST /v2/Conversations/{id}/Actions (202 Accepted).

<a id="tac.models.memory"></a>

# tac.models.memory

<a id="tac.models.memory.MemoryRetrievalRequest"></a>

## MemoryRetrievalRequest Objects

```python
class MemoryRetrievalRequest(BaseModel)
```

Request payload for retrieving conversation memories.

<a id="tac.models.memory.MemoryParticipant"></a>

## MemoryParticipant Objects

```python
class MemoryParticipant(BaseModel)
```

Participant in a Memory communication (author or recipient).

<a id="tac.models.memory.MemoryCommunicationContent"></a>

## MemoryCommunicationContent Objects

```python
class MemoryCommunicationContent(BaseModel)
```

Content of a Memory communication.

<a id="tac.models.memory.MemoryCommunication"></a>

## MemoryCommunication Objects

```python
class MemoryCommunication(BaseModel)
```

A communication from Memory API (historical conversation data).

<a id="tac.models.memory.CiOperator"></a>

## CiOperator Objects

```python
class CiOperator(BaseModel)
```

Information about the Conversational Intelligence operator.

<a id="tac.models.memory.ObservationInfo"></a>

## ObservationInfo Objects

```python
class ObservationInfo(BaseModel)
```

An observation memory from the API response.

<a id="tac.models.memory.SummaryInfo"></a>

## SummaryInfo Objects

```python
class SummaryInfo(BaseModel)
```

A summary memory derived from observations at the end of conversations.

<a id="tac.models.memory.MemoryRetrievalMeta"></a>

## MemoryRetrievalMeta Objects

```python
class MemoryRetrievalMeta(BaseModel)
```

Metadata about the memory retrieval operation.

<a id="tac.models.memory.MemoryRetrievalResponse"></a>

## MemoryRetrievalResponse Objects

```python
class MemoryRetrievalResponse(BaseModel)
```

Response from the Memory API /Recall endpoint.

<a id="tac.models.memory.ProfileResponse"></a>

## ProfileResponse Objects

```python
class ProfileResponse(BaseModel)
```

Response from the profile retrieval API.

<a id="tac.models.memory.ProfileLookupRequest"></a>

## ProfileLookupRequest Objects

```python
class ProfileLookupRequest(BaseModel)
```

Request payload for looking up profiles by identifier.

<a id="tac.models.memory.ProfileLookupResponse"></a>

## ProfileLookupResponse Objects

```python
class ProfileLookupResponse(BaseModel)
```

Response from the profile lookup API.

<a id="tac.models.voice"></a>

# tac.models.voice

Pydantic models for Twilio ConversationRelay Voice WebSocket messages.

<a id="tac.models.voice.CustomParameters"></a>

## CustomParameters Objects

```python
class CustomParameters(BaseModel)
```

Custom parameters for ConversationRelay TwiML.

Supports well-known TAC parameters plus arbitrary custom fields.
All fields are optional since ConversationRelay handles conversation creation automatically.

<a id="tac.models.voice.SetupMessage"></a>

## SetupMessage Objects

```python
class SetupMessage(BaseModel)
```

Setup message sent when WebSocket connection is established.

Contains call metadata from Twilio.

<a id="tac.models.voice.PromptMessage"></a>

## PromptMessage Objects

```python
class PromptMessage(BaseModel)
```

Prompt message containing user's voice input.

Sent when user speaks and speech is transcribed.

<a id="tac.models.voice.InterruptMessage"></a>

## InterruptMessage Objects

```python
class InterruptMessage(BaseModel)
```

Interrupt message sent when user interrupts the agent.

Contains information about what was being said when interrupted.

<a id="tac.models.voice.TwiMLOptions"></a>

## TwiMLOptions Objects

```python
class TwiMLOptions(BaseModel)
```

Options for generating ConversationRelay TwiML.

<a id="tac.models.voice.ConversationRelayCallbackPayload"></a>

## ConversationRelayCallbackPayload Objects

```python
class ConversationRelayCallbackPayload(BaseModel)
```

Payload received from Twilio ConversationRelay callback webhook.

Sent via the <Connect action="..."> URL when a call ends or transitions state.
Used in relay-only mode to signal conversation completion.

<a id="tac.models.outbound"></a>

# tac.models.outbound

Models for outbound conversation initiation.

<a id="tac.models.outbound.InitiateMessagingConversationOptions"></a>

## InitiateMessagingConversationOptions Objects

```python
class InitiateMessagingConversationOptions(BaseModel)
```

Shared options for initiating an outbound messaging conversation.

This base model is used for messaging-style outbound conversations,
including SMS, RCS, WhatsApp, and Chat. Each channel may extend this with
channel-specific requirements (e.g., Chat requires channel_id).

The sender is always TAC's configured address (``config.phone_number``
for SMS, ``config.rcs_sender_id`` for RCS, ``config.whatsapp_number``
for WhatsApp, ``ChatChannelConfig.agent_address`` for Chat).
Multi-sender deployments should use one TAC instance per sender so
inbound webhook routing, memory scoping, and configuration stay in sync.

<a id="tac.models.outbound.InitiateChatConversationOptions"></a>

## InitiateChatConversationOptions Objects

```python
class InitiateChatConversationOptions(InitiateMessagingConversationOptions)
```

Options for initiating an outbound Chat conversation.

Extends InitiateMessagingConversationOptions with a required channel_id
(Conversations v1 Channel SID) for Chat delivery.

<a id="tac.models.outbound.InitiateConversationResult"></a>

## InitiateConversationResult Objects

```python
class InitiateConversationResult(BaseModel)
```

Result of initiating an outbound messaging conversation.

<a id="tac.models.outbound.InitiateVoiceConversationOptions"></a>

## InitiateVoiceConversationOptions Objects

```python
class InitiateVoiceConversationOptions(BaseModel)
```

Options for initiating an outbound voice conversation.

The caller identity is always TAC's configured ``config.phone_number``.
Multi-number deployments should use one TAC instance per line.

<a id="tac.models.outbound.InitiateVoiceConversationResult"></a>

## InitiateVoiceConversationResult Objects

```python
class InitiateVoiceConversationResult(BaseModel)
```

Result of initiating an outbound voice conversation.

<a id="tac.models.handoff"></a>

# tac.models.handoff

<a id="tac.models.handoff.HandoffPayload"></a>

## HandoffPayload Objects

```python
class HandoffPayload(BaseModel)
```

Structured payload generated during a handoff.

Contains conversation context and developer-defined attributes
for routing to the target system (e.g., Flex TaskRouter).

<a id="tac.models.handoff.PendingHandoffData"></a>

## PendingHandoffData Objects

```python
class PendingHandoffData(BaseModel)
```

ConversationRelay WebSocket ``end`` message carrying a handoff payload.

``handoff_data`` is a JSON *string* (not a nested object) — ConversationRelay
forwards it verbatim in the POST body to the ``<Connect action>`` URL.

<a id="tac.models.intelligence"></a>

# tac.models.intelligence

Models for Conversation Intelligence webhook events.

<a id="tac.models.intelligence.IntelligenceConfiguration"></a>

## IntelligenceConfiguration Objects

```python
class IntelligenceConfiguration(BaseModel)
```

Intelligence configuration details from the CI service.

<a id="tac.models.intelligence.Operator"></a>

## Operator Objects

```python
class Operator(BaseModel)
```

Operator details from the CI service.

<a id="tac.models.intelligence.TriggerDetails"></a>

## TriggerDetails Objects

```python
class TriggerDetails(BaseModel)
```

Trigger details for the operator execution.

<a id="tac.models.intelligence.CommunicationsRange"></a>

## CommunicationsRange Objects

```python
class CommunicationsRange(BaseModel)
```

Range of communications used in the operator execution.

<a id="tac.models.intelligence.Participant"></a>

## Participant Objects

```python
class Participant(BaseModel)
```

Participant in a conversation.

<a id="tac.models.intelligence.ExecutionDetails"></a>

## ExecutionDetails Objects

```python
class ExecutionDetails(BaseModel)
```

Execution context details for the operator result.

<a id="tac.models.intelligence.ClassificationResult"></a>

## ClassificationResult Objects

```python
class ClassificationResult(BaseModel)
```

Result for Text-Classification output format.

<a id="tac.models.intelligence.ExtractionEntity"></a>

## ExtractionEntity Objects

```python
class ExtractionEntity(BaseModel)
```

An extracted entity from Text-Extraction.

<a id="tac.models.intelligence.ExtractionResult"></a>

## ExtractionResult Objects

```python
class ExtractionResult(BaseModel)
```

Result for Text-Extraction output format.

<a id="tac.models.intelligence.TextGenerationResult"></a>

## TextGenerationResult Objects

```python
class TextGenerationResult(BaseModel)
```

Result for Text-Generation output format.

<a id="tac.models.intelligence.JSONResult"></a>

## JSONResult Objects

```python
class JSONResult(BaseModel)
```

Result for JSON output format.

<a id="tac.models.intelligence.OperatorProcessingResult"></a>

## OperatorProcessingResult Objects

```python
class OperatorProcessingResult(BaseModel)
```

Result of processing a Conversation Intelligence webhook event.

<a id="tac.models.intelligence.OperatorResult"></a>

## OperatorResult Objects

```python
class OperatorResult(BaseModel)
```

Individual operator result from a CI webhook event.

This model represents a single operator result within the operatorResults array.

<a id="tac.models.intelligence.OperatorResultEvent"></a>

## OperatorResultEvent Objects

```python
class OperatorResultEvent(BaseModel)
```

Operator result event from Conversation Intelligence webhook.

This model represents the webhook payload received from the CI service.
It contains metadata about the conversation and an array of operator results.

<a id="tac.models.knowledge"></a>

# tac.models.knowledge

Knowledge models for the Twilio Agent Connect.

<a id="tac.models.knowledge.Knowledge"></a>

## Knowledge Objects

```python
class Knowledge(BaseModel)
```

Represents a Twilio Knowledge resource.

<a id="tac.models.knowledge.KnowledgeBase"></a>

## KnowledgeBase Objects

```python
class KnowledgeBase(BaseModel)
```

Represents a Twilio Knowledge Base resource.

<a id="tac.models.knowledge.KnowledgeChunkResult"></a>

## KnowledgeChunkResult Objects

```python
class KnowledgeChunkResult(BaseModel)
```

Represents a search result chunk from knowledge base search.

<a id="tac.models.pagination"></a>

# tac.models.pagination

Pagination models for Twilio API responses.

<a id="tac.models.pagination.PaginationMeta"></a>

## PaginationMeta Objects

```python
class PaginationMeta(BaseModel)
```

Pagination metadata for API list responses.

<a id="tac.context.base"></a>

# tac.context.base

<a id="tac.context.base.PartnerConnector"></a>

## PartnerConnector Objects

```python
class PartnerConnector(Enum)
```

Closed set of partner connectors allowed to identify themselves in the User-Agent.

Partner packages built on top of TAC (e.g. ``tac_aws``, ``tac_azure``) select
a value from this enum and pass it to :func:`register_partner_connector`. The
enum is intentionally closed so that customers cannot set arbitrary
User-Agent values. Adding a new partner connector requires a release of
core TAC.

Each value is a ``(package_name, connector_name)`` tuple. The package name
becomes a User-Agent product token and the connector name becomes a
comment, producing e.g. ``tac-azure/0.1.0 (AgentFrameworkConnector)``.

<a id="tac.context.base.BaseAPIClient"></a>

## BaseAPIClient Objects

```python
class BaseAPIClient()
```

Base client for Twilio API interactions with shared HTTP client logic.

<a id="tac.context.base.BaseAPIClient.__init__"></a>

#### \_\_init\_\_

```python
def __init__(api_key: str, api_secret: str, region: str | None = None) -> None
```

Initialize the base API client.

**Arguments**:

- `api_key` - Twilio API Key SID for authentication
- `api_secret` - Twilio API Key Secret for authentication
- `region` - Optional Twilio region (e.g., 'au1', 'ie1')

<a id="tac.context.conversation"></a>

# tac.context.conversation

<a id="tac.context.conversation.ConversationClient"></a>

## ConversationClient Objects

```python
class ConversationClient(BaseAPIClient)
```

Client for interacting with Conversation Orchestrator API.

<a id="tac.context.conversation.ConversationClient.__init__"></a>

#### \_\_init\_\_

```python
def __init__(api_key: str,
             api_secret: str,
             configuration_id: str,
             region: str | None = None) -> None
```

Initialize the Conversation client.

**Arguments**:

- `api_key` - Twilio API Key SID for authentication
- `api_secret` - Twilio API Key Secret for authentication
- `configuration_id` - Conversation Configuration ID for API requests
- `region` - Optional Twilio region (e.g., 'au1', 'ie1')

<a id="tac.context.conversation.ConversationClient.list_conversations"></a>

#### list\_conversations

```python
async def list_conversations(
        status: list[Literal["ACTIVE", "INACTIVE", "CLOSED"]] | None = None,
        channel_id: str | None = None,
        page_size: int | None = None,
        page_token: str | None = None) -> list[ConversationResponse]
```

List conversations with optional filtering and pagination.

**Arguments**:

- `status` - Optional list of statuses to filter conversations
  ("ACTIVE", "INACTIVE", "CLOSED")
- `channel_id` - Optional resource ID (call ID, message ID, etc.) to filter conversations
- `page_size` - Maximum number of items to return (1-1000)
- `page_token` - Token for pagination
  

**Returns**:

  List of ConversationResponse objects
  

**Raises**:

- `httpx.HTTPError` - If the API request fails

<a id="tac.context.conversation.ConversationClient.add_participant"></a>

#### add\_participant

```python
async def add_participant(
    conversation_id: str,
    addresses: list[ParticipantAddress] | None = None,
    participant_type: Literal["HUMAN_AGENT", "CUSTOMER", "AI_AGENT", "AGENT",
                              "UNKNOWN"]
    | None = None
) -> ParticipantResponse
```

Add a new participant to a conversation.

Used by `_reconcile_participants` when Conversation Orchestrator's v1-bridge emits only
the customer participant on an inbound SMS/chat — TAC adds itself as
`AI_AGENT` before replying.

**Arguments**:

- `conversation_id` - The conversation ID to add participant to
- `addresses` - List of communication addresses for the participant (optional)
- `participant_type` - Type of participant (e.g., "CUSTOMER", "AI_AGENT"). Optional.
  

**Returns**:

  ParticipantResponse object containing the created participant details
  

**Raises**:

- `httpx.HTTPError` - If the API request fails

<a id="tac.context.conversation.ConversationClient.update_participant"></a>

#### update\_participant

```python
async def update_participant(
        conversation_id: str,
        participant_id: str,
        participant_type: Literal["HUMAN_AGENT", "CUSTOMER", "AI_AGENT",
                                  "AGENT"],
        addresses: list[ParticipantAddress],
        name: str | None = None,
        profile_id: str | None = None) -> ParticipantResponse
```

Replace an existing participant.

PUT is a full resource replacement per the Conversation Orchestrator spec — any field
omitted from the body is cleared on the server. Callers must pass the
current `addresses` (and `name` if set) to preserve them; pass a new
`profile_id` to attach a profile during reconciliation.

**Arguments**:

- `conversation_id` - Conversation ID containing the participant
- `participant_id` - Participant ID to update
- `participant_type` - New participant type
- `addresses` - Current participant addresses (required to avoid wiping)
- `name` - Current participant display name (optional)
- `profile_id` - Conversation Memory profile ID to attach (optional)
  

**Returns**:

  ParticipantResponse reflecting the updated participant.
  

**Raises**:

- `httpx.HTTPError` - If the API request fails.

<a id="tac.context.conversation.ConversationClient.create_conversation"></a>

#### create\_conversation

```python
async def create_conversation(
    name: str | None = None,
    participants: list[ParticipantRequest] | None = None
) -> ConversationResponse
```

Create a new conversation, optionally with inline participants.

When participants are provided, CO creates them atomically with the
conversation. If an active conversation with the same participant
addresses already exists (respecting the configuration's group-by
rules), CO returns 409 with a pointer to the existing conversation.

**Arguments**:

- `name` - Conversation name (optional)
- `participants` - Optional list of participants to create with the conversation
  

**Returns**:

  ConversationResponse object containing the created conversation details
  

**Raises**:

- `httpx.HTTPError` - If the API request fails

<a id="tac.context.conversation.ConversationClient.create_or_reuse_conversation"></a>

#### create\_or\_reuse\_conversation

```python
async def create_or_reuse_conversation(
        participants: list[ParticipantRequest]) -> tuple[str, bool]
```

Create a conversation with inline participants, reusing an existing one on 409.

On 409 CO returns the existing conversation ID in the
X-Conflicting-Resource-Id response header.

**Returns**:

  Tuple of (conversation_id, reused) where reused is True if an
  existing conversation was found via 409 dedup.
  

**Raises**:

- `httpx.HTTPStatusError` - If the API returns a non-409 error
- `RuntimeError` - If 409 is returned without X-Conflicting-Resource-Id header

<a id="tac.context.conversation.ConversationClient.update_conversation"></a>

#### update\_conversation

```python
async def update_conversation(conversation_id: str,
                              status: Literal["ACTIVE", "INACTIVE", "CLOSED"],
                              name: str | None = None) -> ConversationResponse
```

Update an existing conversation.

**Arguments**:

- `conversation_id` - The conversation ID to update
- `status` - Conversation status to update ("ACTIVE", "INACTIVE", "CLOSED") - required
- `name` - Optional conversation name to update
  

**Returns**:

  ConversationResponse object containing the updated conversation details
  

**Raises**:

- `httpx.HTTPError` - If the API request fails

<a id="tac.context.conversation.ConversationClient.clear_status_callbacks"></a>

#### clear\_status\_callbacks

```python
async def clear_status_callbacks(conversation_id: str) -> None
```

Clear statusCallbacks on a conversation's instance configuration.

This stops the conversation from sending webhook events to TAC,
which is needed during handoff so the receiving system can take over.

**Arguments**:

- `conversation_id` - The conversation ID to update
  

**Raises**:

- `httpx.HTTPError` - If the API request fails

<a id="tac.context.conversation.ConversationClient.create_communication"></a>

#### create\_communication

```python
async def create_communication(
        conversation_id: str,
        communication_request: CommunicationRequest) -> Communication
```

Create a new communication for a conversation.

**Arguments**:

- `conversation_id` - The conversation ID to create communication for
- `communication_request` - CommunicationRequest object with author, content, and recipients
  

**Returns**:

  Communication object containing the created communication details
  

**Raises**:

- `httpx.HTTPError` - If the API request fails

<a id="tac.context.conversation.ConversationClient.list_communications"></a>

#### list\_communications

```python
async def list_communications(
        conversation_id: str,
        channel_id: str | None = None,
        page_size: int | None = None,
        page_token: str | None = None) -> list[Communication]
```

List communications for a conversation.

**Arguments**:

- `conversation_id` - The conversation ID to list communications for
- `channel_id` - Optional channel ID filter (call ID, message ID, etc.)
- `page_size` - Maximum number of items to return (1-1000)
- `page_token` - Token for pagination
  

**Returns**:

  List of Communication objects
  

**Raises**:

- `httpx.HTTPError` - If the API request fails

<a id="tac.context.conversation.ConversationClient.create_action"></a>

#### create\_action

```python
async def create_action(conversation_id: str,
                        request: SendMessageActionRequest) -> ActionResponse
```

Create an action via POST /v2/Conversations/{conversationId}/Actions.

Currently supports SEND_MESSAGE actions. Returns 202 Accepted; the action is
processed asynchronously and its status can be polled via getAction.

**Arguments**:

- `conversation_id` - The conversation ID to create the action in
- `request` - SendMessageActionRequest with `from`, `to`, and content
  

**Returns**:

  ActionResponse with id, type, status, and conversationId
  

**Raises**:

- `httpx.HTTPError` - If the API request fails

<a id="tac.context.conversation.ConversationClient.get_configuration"></a>

#### get\_configuration

```python
def get_configuration(configuration_id: str) -> ConversationConfiguration
```

Retrieve the details for a single configuration.

**Arguments**:

- `configuration_id` - The configuration ID to retrieve
  

**Returns**:

  ConversationConfiguration object containing the configuration details
  

**Raises**:

- `httpx.HTTPError` - If the API request fails
- `ValueError` - If the response schema is invalid

<a id="tac.context.memory"></a>

# tac.context.memory

<a id="tac.context.memory.MemoryClient"></a>

## MemoryClient Objects

```python
class MemoryClient(BaseAPIClient)
```

Client for interacting with Twilio Conversation Memory data plane API.

<a id="tac.context.memory.MemoryClient.__init__"></a>

#### \_\_init\_\_

```python
def __init__(store_id: str,
             api_key: str,
             api_secret: str,
             region: str | None = None) -> None
```

Initialize the Memory client.

**Arguments**:

- `store_id` - Memory store ID (starts with mem_store_).
- `api_key` - API Key for Conversation Memory authentication.
- `api_secret` - API Secret for Conversation Memory authentication.
- `region` - Optional Twilio region (e.g., 'au1', 'ie1')

<a id="tac.context.memory.MemoryClient.retrieve_memory"></a>

#### retrieve\_memory

```python
async def retrieve_memory(
        profile_id: str,
        conversation_id: str | None = None,
        query: str | None = None,
        observations_limit: int | None = None,
        summaries_limit: int | None = None,
        communications_limit: int | None = None,
        relevance_threshold: float | None = None) -> MemoryRetrievalResponse
```

Retrieve conversation memories with semantic search and configurable limits.

**Arguments**:

- `profile_id` - Profile ID (TTID format)
- `conversation_id` - Optional conversation ID (TTID format)
- `query` - Optional semantic search query (1-1024 characters)
- `observations_limit` - Max observations to return (0-100)
- `summaries_limit` - Max summaries to return (0-100)
- `communications_limit` - Max communications to return (0-100)
- `relevance_threshold` - Min relevance score (0.0-1.0)
  

**Returns**:

  MemoryRetrievalResponse with observations, summaries, communications, and metadata.
  Returns empty MemoryRetrievalResponse() if API request fails or response cannot be
  parsed.

<a id="tac.context.memory.MemoryClient.get_profile"></a>

#### get\_profile

```python
async def get_profile(
        profile_id: str,
        trait_groups: list[str] | None = None) -> ProfileResponse
```

Retrieve a profile by ID with optional trait group selection.

**Arguments**:

- `profile_id` - Profile ID using Twilio Type ID (TTID) format
- `trait_groups` - Optional list of trait group names to include in the response
  

**Returns**:

  ProfileResponse containing profile ID, creation timestamp, and traits
  

**Raises**:

- `httpx.HTTPError` - If the API request fails
- `ValueError` - If the response cannot be parsed

<a id="tac.context.memory.MemoryClient.lookup_profile"></a>

#### lookup\_profile

```python
async def lookup_profile(id_type: str, value: str) -> ProfileLookupResponse
```

Find profiles that contain a specific identifier value.

Submit an identifier object specifying the idType and value.
The value is normalized using the configured identity resolution settings
(such as phone number formatting) prior to matching. Multiple matches are
returned if more than one profile is associated with the identifier.
Returns canonical profile IDs (the earliest ID if profiles have been merged)
along with the normalized value actually searched.

**Arguments**:

- `id_type` - Identifier type as configured in the service's Identity Resolution Settings
  (e.g., "phone", "email"). Must be 2-30 characters.
- `value` - Raw value captured for the identifier (e.g., "+13175556789").
  The service normalizes this value according to the configured rules.
  

**Returns**:

  ProfileLookupResponse containing normalized value and list of matching profile IDs
  

**Raises**:

- `httpx.HTTPError` - If the API request fails
- `ValueError` - If the response cannot be parsed

<a id="tac.context.memory.MemoryClient.create_profile"></a>

#### create\_profile

```python
async def create_profile(traits: dict[str, dict[str, Any]]) -> str
```

Create a profile via identity resolution (upsert).

Conversation Memory runs identity resolution on the submitted traits: if an
identifier match is found the existing canonical profile ID is
returned, otherwise a new profile is minted. The body must contain
at least one trait promoted-to-identifier per the store's identity
resolution settings, else resolution fails with 400.

The write is queued (202 Accepted) — the canonical profile ID is
returned synchronously in the response body, but downstream traits
may not be fully persisted immediately.

**Arguments**:

- `traits` - Trait-group → field → value mapping, e.g.
- ``{"Contact"` - {"phone": "+13175551234"}}`. Max 50 groups × 99
  traits each.
  

**Returns**:

  Canonical profile ID (`mem_profile_…`).
  

**Raises**:

- `httpx.HTTPError` - If the API request fails.
- `ValueError` - If the response does not contain an `id` field.

<a id="tac.context.memory.MemoryClient.create_observation"></a>

#### create\_observation

```python
async def create_observation(profile_id: str,
                             content: str,
                             source: str = "conversation-intelligence",
                             conversation_ids: list[str] | None = None,
                             occurred_at: str | None = None) -> dict[str, Any]
```

Create a new observation in Conversation Memory.

**Arguments**:

- `profile_id` - Profile ID to associate observation with
- `content` - Observation content (the summary text or extracted fact)
- `source` - Source system identifier (default: "conversation-intelligence")
- `conversation_ids` - List of conversation IDs this observation relates to
- `occurred_at` - Optional timestamp when observation occurred (ISO 8601 format)
  

**Returns**:

  Dict with created observation details
  

**Raises**:

- `httpx.HTTPError` - If the API request fails

<a id="tac.context.memory.MemoryClient.create_conversation_summaries"></a>

#### create\_conversation\_summaries

```python
async def create_conversation_summaries(
        profile_id: str, summaries: list[dict[str, Any]]) -> dict[str, str]
```

Create conversation summaries in Conversation Memory.

**Arguments**:

- `profile_id` - Profile ID to associate summaries with
- `summaries` - List of summary objects, each containing:
  - content (str): The summary text
  - conversationId (str): The conversation ID
  - occurredAt (str): ISO 8601 timestamp when conversation occurred
  - source (str, optional): Source system identifier
  

**Returns**:

  Response dict with message field (e.g., {"message": "Summaries creation accepted"})
  

**Raises**:

- `httpx.HTTPError` - If the API request fails

<a id="tac.context.knowledge"></a>

# tac.context.knowledge

<a id="tac.context.knowledge.KnowledgeClient"></a>

## KnowledgeClient Objects

```python
class KnowledgeClient(BaseAPIClient)
```

Client for interacting with Twilio Knowledge Base API.

<a id="tac.context.knowledge.KnowledgeClient.__init__"></a>

#### \_\_init\_\_

```python
def __init__(api_key: str, api_secret: str, region: str | None = None) -> None
```

Initialize the Knowledge client.

**Arguments**:

- `api_key` - API Key for Knowledge Base authentication.
- `api_secret` - API Secret for Knowledge Base authentication.
- `region` - Optional Twilio region (e.g., 'au1', 'ie1')

<a id="tac.context.knowledge.KnowledgeClient.get_knowledge_base"></a>

#### get\_knowledge\_base

```python
async def get_knowledge_base(knowledge_base_id: str) -> KnowledgeBase
```

Fetch knowledge base metadata from the Knowledge Base API.

**Arguments**:

- `knowledge_base_id` - The knowledge base ID to fetch (format: know_knowledgebase_*)
  

**Returns**:

  KnowledgeBase object with metadata from the API
  

**Raises**:

- `httpx.HTTPError` - If the API request fails

<a id="tac.context.knowledge.KnowledgeClient.search_knowledge_base"></a>

#### search\_knowledge\_base

```python
async def search_knowledge_base(
        knowledge_base_id: str,
        query: str,
        top_k: int = 5,
        knowledge_ids: list[str] | None = None) -> list[KnowledgeChunkResult]
```

Search a knowledge base with the given query.

**Arguments**:

- `knowledge_base_id` - The knowledge base ID to search (format: know_knowledgebase_*)
- `query` - The search query string (max 2048 characters)
- `top_k` - Number of knowledge chunks to return (default: 5, max: 20)
- `knowledge_ids` - Optional list of specific knowledge IDs to filter search results
  

**Returns**:

  List of KnowledgeChunkResult objects with content and relevance scores
  

**Raises**:

- `httpx.HTTPError` - If the API request fails

<a id="tac.tools.base"></a>

# tac.tools.base

Tool representation for the Twilio Agent Connect.

Inspired by OpenAI's function_schema approach from openai-agents-python (MIT License).
Injection pattern inspired by LangChain's InjectedToolArg system (MIT License).

<a id="tac.tools.base.InjectedToolArg"></a>

## InjectedToolArg Objects

```python
class InjectedToolArg()
```

Marker class for tool arguments that are injected at runtime.

Tool arguments annotated with this class are not included in the tool
schema sent to language models and are instead injected during execution.

Inspired by LangChain's InjectedToolArg pattern.

**Example**:

  @function_tool()
  def my_tool(
- `user_input` - str,
- `client` - Annotated[MyClient, InjectedToolArg]
  ) -> str:
  # client is injected, not visible to LLM
  return client.process(user_input)

<a id="tac.tools.base.TACTool"></a>

## TACTool Objects

```python
@dataclass
class TACTool()
```

Represents a tool/function that can be used with LLMs.

Similar to OpenAI's FuncSchema, this captures function metadata
for LLM tool integration. Supports runtime injection of dependencies
that are hidden from the LLM schema.

<a id="tac.tools.base.TACTool.implementation"></a>

#### implementation

```python
@property
def implementation() -> Callable[..., Awaitable[object]]
```

Get a clean callable with only non-injected parameters in its signature.

This property automatically returns the right callable for LLM SDK introspection.
The returned callable has only non-injected parameters in its signature while
automatically handling dependency injection when called.

Returns an async callable since TAC is async-first.

**Returns**:

  An async callable with clean signature that can be inspected by any LLM SDK
  

**Example**:

  # Pass to LLM SDK - it will introspect the clean signature
  sdk.add_tool(tool.implementation)

<a id="tac.tools.base.TACTool.configure_injection"></a>

#### configure\_injection

```python
def configure_injection(**kwargs: object) -> "TACTool"
```

Configure values to be injected at runtime when the tool is called.

These values correspond to parameters marked with InjectedToolArg
annotations and will be automatically supplied when the tool executes.

Validates that provided values match the expected types from the
function signature using Pydantic TypeAdapter for robust validation
of all Python type annotations including generics, Pydantic models,
Literal types, and complex unions.

**Arguments**:

- `**kwargs` - Mapping of parameter names to values to inject
  

**Returns**:

  Self for method chaining
  

**Raises**:

- `TypeError` - If a provided value doesn't match the expected type
- `ValueError` - If an unknown parameter name is provided
  

**Warnings**:

  Do not directly mutate _injected_args. Always use configure_injection()
  to ensure proper cache invalidation and type validation.
  

**Example**:

  tool.configure_injection(client=conversation_memory_client, config=tac_config)

<a id="tac.tools.base.TACTool.__call__"></a>

#### \_\_call\_\_

```python
async def __call__(**kwargs: object) -> object
```

Call the tool with the given arguments, automatically injecting
configured dependencies.

Handles both sync and async implementations transparently.

**Arguments**:

- `**kwargs` - Arguments provided by the LLM or caller
  

**Returns**:

  Result from the tool's implementation

<a id="tac.tools.base.TACTool.to_openai_format"></a>

#### to\_openai\_format

```python
def to_openai_format() -> dict[str, object]
```

Get tool schema in OpenAI function calling format.

**Returns**:

  Dictionary in OpenAI function format

<a id="tac.tools.base.TACTool.to_anthropic_format"></a>

#### to\_anthropic\_format

```python
def to_anthropic_format() -> dict[str, object]
```

Get tool schema in Anthropic tool calling format.

**Returns**:

  Dictionary in Anthropic tool format

<a id="tac.tools.base.TACTool.to_openai_agents_sdk_tool"></a>

#### to\_openai\_agents\_sdk\_tool

```python
def to_openai_agents_sdk_tool() -> "FunctionTool"
```

Convert this tool to an OpenAI Agents SDK ``FunctionTool`` instance.

Unlike ``to_openai_format`` and ``to_anthropic_format`` (which return
plain dicts consumed by HTTP APIs), the OpenAI Agents SDK dispatches
on tool *class*, so this returns a live ``FunctionTool`` object with
an ``on_invoke`` closure that calls this tool and JSON-encodes the
result.

Requires the ``openai-agents`` package:

pip install openai-agents

**Returns**:

  A ``FunctionTool`` ready to pass to ``Agent(tools=[...])``.

<a id="tac.tools.base.TACTool.to_json"></a>

#### to\_json

```python
def to_json() -> str
```

Convert tool to JSON string (OpenAI format by default).

<a id="tac.tools.base.function_tool"></a>

#### function\_tool

```python
def function_tool(
    name: str | None = None,
    description: str | None = None
) -> Callable[[Callable[..., object]], TACTool]
```

Decorator to create a TAC tool from a function.

Similar to OpenAI's function_tool decorator approach.

**Arguments**:

- `name` - Optional name override (defaults to function name)
- `description` - Optional description override (defaults to docstring)
  

**Returns**:

  Decorator function

<a id="tac.tools.base.create_tool"></a>

#### create\_tool

```python
def create_tool(name: str, description: str, params_json_schema: dict[str,
                                                                      object],
                implementation: Callable[..., object]) -> TACTool
```

Create a TAC tool manually with explicit schema.

**Arguments**:

- `name` - The name of the tool/function
- `description` - Description of what the tool does
- `params_json_schema` - JSON Schema for the tool's parameters
- `implementation` - Function that implements the tool's logic
  

**Returns**:

  TACTool instance

<a id="tac.tools.memory"></a>

# tac.tools.memory

Memory API tools for the Twilio Agent Connect.

<a id="tac.tools.memory.retrieve_profile_memory"></a>

#### retrieve\_profile\_memory

```python
async def retrieve_profile_memory(
        query: str, conversation_memory_client: Annotated[MemoryClient,
                                                          InjectedToolArg],
        profile_id: Annotated[str, InjectedToolArg]) -> dict[str, Any]
```

Search and retrieve relevant memories for the current profile.

Performs semantic search across the user's conversation history, observations,
and stored traits to find contextually relevant information.

**Arguments**:

- `query` - What to search for in the user's memory (e.g., "preferences about food",
  "previous complaints", "contact information")
  

**Returns**:

  Dictionary containing relevant memories, traits, and metadata

<a id="tac.tools.memory.create_memory_tool"></a>

#### create\_memory\_tool

```python
def create_memory_tool(conversation_memory_client: MemoryClient,
                       session: ConversationSession,
                       *,
                       name: str | None = None,
                       description: str | None = None) -> TACTool
```

Create memory tool with injected MemoryClient and session context.

**Arguments**:

- `conversation_memory_client` - MemoryClient instance for retrieving memories
- `session` - Current session identity with profile and conversation IDs
- `name` - Tool name exposed to the LLM. Defaults to the function name
  (``"retrieve_profile_memory"``).
- `description` - Tool description exposed to the LLM. Defaults to the
  function's docstring.
  

**Returns**:

  Configured memory tool
  

**Example**:

  >>> tool = create_memory_tool(
  ...     conversation_memory_client,
  ...     session,
  ...     name="recall_customer_history",
  ...     description="Recall prior preferences and complaints for this customer.",
  ... )
  >>> result = await tool(query="user preferences")

<a id="tac.tools.knowledge"></a>

# tac.tools.knowledge

Knowledge API tools for the Twilio Agent Connect.

<a id="tac.tools.knowledge.search_knowledge"></a>

#### search\_knowledge

```python
async def search_knowledge(
        query: str, knowledge_client: Annotated[KnowledgeClient,
                                                InjectedToolArg],
        knowledge_base_id: Annotated[str, InjectedToolArg],
        top_k: Annotated[int, InjectedToolArg]) -> list[KnowledgeChunkResult]
```

Search the knowledge base with the given query.

**Arguments**:

- `query` - The search query string (max 2048 characters)
- `knowledge_client` - KnowledgeClient instance for API calls (injected, not visible to LLM)
- `knowledge_base_id` - Knowledge base ID to search (injected, not visible to LLM)
- `top_k` - Number of chunks to return (injected, not visible to LLM)
  

**Returns**:

  List of KnowledgeChunkResult objects with content, knowledge_id, created_at, and score

<a id="tac.tools.knowledge.create_knowledge_tool"></a>

#### create\_knowledge\_tool

```python
async def create_knowledge_tool(knowledge_client: KnowledgeClient,
                                knowledge_base_id: str,
                                *,
                                name: str | None = None,
                                description: str | None = None,
                                top_k: int = 5) -> TACTool
```

Create a knowledge search tool for the given knowledge base.

Creates a function tool that searches the specified knowledge using Twilio's
Knowledge Base Search API via KnowledgeClient. The tool uses dependency injection
to hide the knowledge client and knowledge ID from the LLM schema.

If both ``name`` and ``description`` are provided, uses them directly (no API call).
If either is missing, fetches the knowledge base metadata to derive defaults.

**Arguments**:

- `knowledge_client` - KnowledgeClient instance for searching knowledge bases
- `knowledge_base_id` - Knowledge base ID string (e.g., "know_knowledgebase_...")
- `name` - Tool name exposed to the LLM. Defaults to ``search_<kb_display_name>``
  (fetched from the knowledge base if unset).
- `description` - Tool description exposed to the LLM. Defaults to the knowledge
  base's ``description`` field (fetched if unset).
- `top_k` - Number of knowledge chunks to return per query. Defaults to 5.
  

**Returns**:

  A configured TACTool that searches the specified knowledge with injected dependencies
  
  Example with custom name and description (no API call):
  >>> tool = await create_knowledge_tool(
  ...     knowledge_client=tac.knowledge_client,
  ...     knowledge_base_id="know_knowledgebase_...",
  ...     name="search_promotions",
  ...     description="Search for promotions and discounts",
  ...     top_k=3,
  ... )
  
  Example using KB metadata as defaults (fetches KB):
  >>> tool = await create_knowledge_tool(
  ...     knowledge_client=tac.knowledge_client,
  ...     knowledge_base_id="know_knowledgebase_...",
  ...     top_k=3,
  ... )

<a id="tac.tools.handoff"></a>

# tac.tools.handoff

Handoff tool for the Twilio Agent Connect.

<a id="tac.tools.handoff.studio_executions_url"></a>

#### studio\_executions\_url

```python
def studio_executions_url(flow_sid: str) -> str
```

Build the Twilio Studio Flow Executions URL for a given Flow SID.

Used for digital (messaging/chat) handoff — POST the handoff payload
to this URL to start a Studio flow execution.

<a id="tac.tools.handoff.studio_voice_handoff_url"></a>

#### studio\_voice\_handoff\_url

```python
def studio_voice_handoff_url(account_sid: str, flow_sid: str) -> str
```

Build the Twilio Studio Flow voice webhook URL for a given Flow SID.

Used as the ``<Connect action=...>`` URL in TwiML for voice handoff,
so that when ConversationRelay ends the session Twilio triggers the
Studio flow for an incoming call.

<a id="tac.tools.handoff.build_handoff_payload"></a>

#### build\_handoff\_payload

```python
def build_handoff_payload(session: ConversationSession, memory_store_id: str,
                          attributes: dict[str, Any]) -> HandoffPayload
```

Build a HandoffPayload from session context and attributes.

Useful for custom handoff tools that want TAC's payload shape without
the Studio-specific delivery in ``post_studio_handoff``.

**Arguments**:

- `session` - Current conversation session
- `memory_store_id` - Memory store ID (typically ``tac.conversation_memory_client.store_id``)
- `attributes` - Developer-defined attributes (including reason)
  

**Returns**:

  HandoffPayload with conversation context and attributes

<a id="tac.tools.handoff.post_studio_handoff"></a>

#### post\_studio\_handoff

```python
async def post_studio_handoff(payload: HandoffPayload,
                              session: ConversationSession, *,
                              handoff_url: str, from_address: str,
                              api_key: str, api_secret: str) -> None
```

POST a handoff payload to a Twilio Studio Flow Executions endpoint.

Emits the Twilio Studio Executions API wire format: form-encoded
``To`` / ``From`` / ``Parameters`` fields with HTTP Basic auth.
``Parameters`` is a JSON string keyed under ``HandoffData`` so Studio
can reference it via ``{{flow.data.HandoffData.*}}``.

**Arguments**:

- `payload` - Structured handoff payload
- `session` - Current conversation session (used for ``To`` address)
- `handoff_url` - Studio Flow Executions URL
  (``https://studio.twilio.com/v2/Flows/FWxxx/Executions``)
- `from_address` - Twilio phone number used as ``From``
- `api_key` - Twilio API Key SID (Basic auth username)
- `api_secret` - Twilio API Key Secret (Basic auth password)
  

**Raises**:

- `httpx.HTTPError` - If the POST request fails

<a id="tac.tools.handoff.create_studio_handoff_tool"></a>

#### create\_studio\_handoff\_tool

```python
def create_studio_handoff_tool(
        tac: "TAC",
        session: ConversationSession,
        attributes: dict[str, Any] | None = None,
        *,
        name: str = DEFAULT_HANDOFF_TOOL_NAME,
        description: str = DEFAULT_HANDOFF_TOOL_DESCRIPTION) -> TACTool
```

Create a handoff tool that delivers in the Twilio Studio Executions API shape.

The returned tool exposes only ``handoff(reason: str)`` to the LLM.
All other dependencies are injected at runtime.

On digital channels, the tool POSTs to the Studio Flow Executions
endpoint derived from ``tac.config.studio_handoff_flow_sid``
(``https://studio.twilio.com/v2/Flows/{flow_sid}/Executions``) using
form-encoded ``To`` / ``From`` / ``Parameters`` fields with HTTP Basic
auth. The Studio flow can access the handoff payload via
``{{flow.data.HandoffData.*}}``.

For voice channels, the payload is stored on the session and the voice
channel automatically sends the WS ``end`` message with ``handoffData``
after the LLM's final response is delivered.

The tool also sets the conversation to INACTIVE and clears status callbacks
to prevent further webhook events from being routed to TAC.

**Not available in ConversationRelay-only mode.** This tool requires
Conversation Orchestrator for conversation state management (setting
INACTIVE status, clearing callbacks) and Conversation Memory for the
handoff payload's ``storeId``. In relay-only mode, implement a custom
handoff by setting ``session.pending_handoff_data`` directly — the voice
channel will send the WebSocket ``end`` message with your payload, and
your ``<Connect action>`` URL handler can route the call accordingly.

**Arguments**:

- `tac` - TAC instance for building payload and posting to Studio
- `session` - Current conversation session
- `attributes` - Static attributes to include in the handoff payload
  (e.g., ``{"department": "billing", "priority": "high"}``).
  The LLM-provided ``reason`` is always added automatically.
- `name` - Tool name exposed to the LLM. Defaults to ``"handoff"``.
- `description` - Tool description exposed to the LLM. Customize when the
  default's phrasing doesn't match your product vocabulary
  or escalation policy.
  

**Returns**:

  Configured TACTool instance for handoff
  

**Example**:

  >>> handoff_tool = create_studio_handoff_tool(
  ...     tac,
  ...     context,
  ...     attributes={"department": "support"},
  ...     name="escalate_to_agent",
  ...     description="Escalate only for billing disputes over $100.",
  ... )
  

**Raises**:

- `ValueError` - If ``tac.config.studio_handoff_flow_sid`` is unset,
  if Conversation Orchestrator is not configured (relay-only mode),
  or if no memory store ID is available.

<a id="tac.adapters.options"></a>

# tac.adapters.options

Options for configuring adapter behavior.

<a id="tac.adapters.options.AdapterOptions"></a>

## AdapterOptions Objects

```python
class AdapterOptions(BaseModel)
```

Options for configuring how adapters inject memory and profile data.

**Example**:

  # Default behavior (no options) - inject ALL profile traits
  client = with_tac_memory(openai_client, memory_response, context)
  
  # Default behavior (options but no profile_traits specified) - inject ALL profile traits
  options = AdapterOptions()
  client = with_tac_memory(openai_client, memory_response, context, options=options)
  
  # Explicitly exclude all profile traits
  options = AdapterOptions(profile_traits=None)
  client = with_tac_memory(openai_client, memory_response, context, options=options)
  # or
  options = AdapterOptions(profile_traits=[])
  client = with_tac_memory(openai_client, memory_response, context, options=options)
  
  # Specific traits only
  options = AdapterOptions(profile_traits=["Contact", "Preferences"])
  client = with_tac_memory(openai_client, memory_response, context, options=options)

<a id="tac.adapters.options.AdapterOptions.get_profile_traits"></a>

#### get\_profile\_traits

```python
def get_profile_traits() -> list[str] | None
```

Get the profile traits to include.

**Returns**:

  None to include all traits (when field not set),
  empty list to exclude all (when explicitly set to None or []),
  or list of specific trait group names to include.

<a id="tac.adapters.prompt_builder"></a>

# tac.adapters.prompt\_builder

Memory prompt builder for TAC adapters.

This module provides a clean class-based API for building LLM prompts from TAC memory
data (observations, summaries, communications) and customer profile information.

All adapters (OpenAI, Anthropic, Bedrock, LangChain, etc.) should use MemoryPromptBuilder
to ensure consistent memory presentation across different LLM providers.

<a id="tac.adapters.prompt_builder.MemoryPromptBuilder"></a>

## MemoryPromptBuilder Objects

```python
class MemoryPromptBuilder()
```

Builds LLM prompts from TAC memory and profile data.

This class orchestrates prompt building by calling helper methods on
TACMemoryResponse and ConversationSession models, then assembles the
sections into a complete prompt.

**Example**:

  >>> prompt = MemoryPromptBuilder.build(memory_response, context, options)
  >>> if prompt:
  ...     # Inject into your LLM messages
  ...     messages.insert(0, {"role": "system", "content": prompt})

<a id="tac.adapters.prompt_builder.MemoryPromptBuilder.build"></a>

#### build

```python
@staticmethod
def build(memory_response: TACMemoryResponse | None = None,
          context: ConversationSession | None = None,
          options: AdapterOptions | None = None) -> str | None
```

Build a complete memory prompt from TAC data.

This is the main entry point. Delegates formatting to model helper methods,
then assembles sections into a complete prompt.

**Arguments**:

- `memory_response` - Memory data from TAC.retrieve_memory()
- `context` - Conversation session with profile data
- `options` - Adapter options for trait filtering
  

**Returns**:

  Formatted prompt string ready for LLM injection, or None if
  no memory/profile data is available.
  

**Example**:

  >>> prompt = MemoryPromptBuilder.build(
  ...     memory_response=memory_response,
  ...     context=context,
  ...     options=AdapterOptions(profile_traits=["Contact"]),
  ... )
  >>> print(prompt)
  # Customer Context
  You have access to the following information about this customer
  from previous interactions:
  
  ## Customer Profile
  Information about this customer:
  - Contact: {"name": "John Doe", "email": "john@example.com"}
  
  ## Key Observations
  Important notes about the customer from previous interactions:
  - Customer prefers email communication

<a id="tac.adapters.prompt_builder.MemoryPromptBuilder.compose"></a>

#### compose

```python
@staticmethod
def compose(system_prompt: str | None = None,
            memory_response: TACMemoryResponse | None = None,
            context: ConversationSession | None = None,
            options: AdapterOptions | None = None) -> str
```

Compose system prompt with memory context.

Appends memory to system_prompt if available. Always returns a string.

**Example**:

  >>> prompt = MemoryPromptBuilder.compose(
  ...     "You are a helpful assistant", memory_response, context
  ... )

<a id="tac.adapters.openai.adapter"></a>

# tac.adapters.openai.adapter

OpenAI adapter for automatic memory injection using wrapper approach.

<a id="tac.adapters.openai.adapter.TACCompletionsNamespace"></a>

## TACCompletionsNamespace Objects

```python
class TACCompletionsNamespace(_BaseCompletionsNamespace)
```

Sync wrapper for OpenAI chat.completions namespace with memory injection.

<a id="tac.adapters.openai.adapter.TACCompletionsNamespace.create"></a>

#### create

```python
def create(*args: Any, messages: list[ChatCompletionMessageParam],
           **kwargs: Any) -> Any
```

Intercepts create() calls to inject memory automatically.

<a id="tac.adapters.openai.adapter.TACCompletionsNamespace.stream"></a>

#### stream

```python
def stream(*args: Any, messages: list[ChatCompletionMessageParam],
           **kwargs: Any) -> Any
```

Intercepts stream() calls to inject memory automatically.

<a id="tac.adapters.openai.adapter.AsyncTACCompletionsNamespace"></a>

## AsyncTACCompletionsNamespace Objects

```python
class AsyncTACCompletionsNamespace(_BaseCompletionsNamespace)
```

Async wrapper for OpenAI chat.completions namespace with memory injection.

<a id="tac.adapters.openai.adapter.AsyncTACCompletionsNamespace.create"></a>

#### create

```python
async def create(*args: Any, messages: list[ChatCompletionMessageParam],
                 **kwargs: Any) -> Any
```

Intercepts async create() calls to inject memory automatically.

<a id="tac.adapters.openai.adapter.AsyncTACCompletionsNamespace.stream"></a>

#### stream

```python
def stream(*args: Any, messages: list[ChatCompletionMessageParam],
           **kwargs: Any) -> Any
```

Intercepts async stream() calls to inject memory automatically.

<a id="tac.adapters.openai.adapter.TACResponsesNamespace"></a>

## TACResponsesNamespace Objects

```python
class TACResponsesNamespace(_BaseResponsesNamespace)
```

Sync wrapper for OpenAI responses namespace with memory injection.

<a id="tac.adapters.openai.adapter.TACResponsesNamespace.create"></a>

#### create

```python
def create(*args: Any, instructions: str | None = None, **kwargs: Any) -> Any
```

Intercepts create() calls to inject memory automatically.

<a id="tac.adapters.openai.adapter.AsyncTACResponsesNamespace"></a>

## AsyncTACResponsesNamespace Objects

```python
class AsyncTACResponsesNamespace(_BaseResponsesNamespace)
```

Async wrapper for OpenAI responses namespace with memory injection.

<a id="tac.adapters.openai.adapter.AsyncTACResponsesNamespace.create"></a>

#### create

```python
async def create(*args: Any,
                 instructions: str | None = None,
                 **kwargs: Any) -> Any
```

Intercepts async create() calls to inject memory automatically.

<a id="tac.adapters.openai.adapter.TACChatNamespace"></a>

## TACChatNamespace Objects

```python
class TACChatNamespace(_BaseChatNamespace)
```

Sync wrapper for OpenAI chat namespace.

<a id="tac.adapters.openai.adapter.AsyncTACChatNamespace"></a>

## AsyncTACChatNamespace Objects

```python
class AsyncTACChatNamespace(_BaseChatNamespace)
```

Async wrapper for OpenAI chat namespace.

<a id="tac.adapters.openai.adapter._BaseOpenAIClient"></a>

## \_BaseOpenAIClient Objects

```python
class _BaseOpenAIClient()
```

Base class for OpenAI client wrappers with shared logic.

<a id="tac.adapters.openai.adapter._BaseOpenAIClient.__getattr__"></a>

#### \_\_getattr\_\_

```python
def __getattr__(name: str) -> Any
```

Proxy all other OpenAI client features (embeddings, images, audio, etc).

<a id="tac.adapters.openai.adapter.TACOpenAIClient"></a>

## TACOpenAIClient Objects

```python
class TACOpenAIClient(_BaseOpenAIClient)
```

Sync wrapper for OpenAI client that automatically injects TAC memory.

Does NOT mutate the original client. Safe for global clients and concurrent conversations.

<a id="tac.adapters.openai.adapter.AsyncTACOpenAIClient"></a>

## AsyncTACOpenAIClient Objects

```python
class AsyncTACOpenAIClient(_BaseOpenAIClient)
```

Async wrapper for AsyncOpenAI client that automatically injects TAC memory.

Does NOT mutate the original client. Safe for global clients and concurrent conversations.

<a id="tac.adapters.openai.adapter.with_tac_memory"></a>

#### with\_tac\_memory

```python
def with_tac_memory(
    openai_client: OpenAI | AsyncOpenAI,
    memory_response: TACMemoryResponse | None = None,
    context: ConversationSession | None = None,
    options: AdapterOptions | None = None
) -> TACOpenAIClient | AsyncTACOpenAIClient
```

Wraps an OpenAI or AsyncOpenAI client with automatic Twilio memory injection.

Does NOT mutate the original client. Returns a new wrapper object that
intercepts chat.completions.create() and stream() calls and injects memory automatically.

Supports both synchronous and asynchronous clients.

**Arguments**:

- `openai_client` - The OpenAI or AsyncOpenAI client instance to wrap
- `memory_response` - Optional memory response from TAC.retrieve_memory()
- `context` - Optional conversation session context with profile data
- `options` - Optional adapter options for controlling memory injection
  

**Returns**:

  Wrapped OpenAI client with memory injection (TACOpenAIClient or AsyncTACOpenAIClient)
  

**Examples**:

  Sync usage:
  >>> client = with_tac_memory(openai_client, memory_response, context)
  >>> response = client.chat.completions.create(
  ...     model="gpt-4", messages=[{"role": "user", "content": "Hello"}]
  ... )
  
  Async usage:
  >>> async_client = with_tac_memory(async_openai_client, memory_response, context)
  >>> response = await async_client.chat.completions.create(
  ...     model="gpt-4", messages=[{"role": "user", "content": "Hello"}]
  ... )
  
  Streaming:
  >>> with client.chat.completions.stream(
  ...     model="gpt-4", messages=[{"role": "user", "content": "Hello"}]
  ... ) as stream:
  ...     for event in stream:
  ...         print(event.content)

<a id="tac.server.fastapi_server"></a>

# tac.server.fastapi\_server

TACFastAPIServer: Batteries-included FastAPI server for TAC channels.

This module provides FastAPIWebSocketAdapter (bridges FastAPI WebSocket to
WebSocketProtocol) and TACFastAPIServer (creates a FastAPI app with routes for
voice, messaging, and CI webhooks).

Requires: pip install tac[server]

<a id="tac.server.fastapi_server.FastAPIWebSocketAdapter"></a>

## FastAPIWebSocketAdapter Objects

```python
class FastAPIWebSocketAdapter()
```

Adapts a FastAPI WebSocket to satisfy WebSocketProtocol.

Converts FastAPI's WebSocketDisconnect into WebSocketDisconnectError
so that VoiceChannel's framework-agnostic exception handling works.

<a id="tac.server.fastapi_server.TACFastAPIServer"></a>

## TACFastAPIServer Objects

```python
class TACFastAPIServer()
```

Batteries-included FastAPI server for TAC channels.

Creates (or adopts) a FastAPI app and registers routes for voice, messaging,
and CI webhooks, then starts uvicorn when start() is called.

Customization:
- Pass your own FastAPI instance via ``app=...`` to control
construction-time settings (title, version, lifespan, docs_url, ...).
TAC routes are registered onto it immediately in ``__init__``.
- Or mutate ``server.app`` after construction: add middleware,
exception handlers, routers, or custom routes — before calling
``start()``.

**Example**:

  from fastapi import FastAPI
  from fastapi.middleware.cors import CORSMiddleware
  
  app = FastAPI(title="My Service", version="1.2.0")
  app.add_middleware(CORSMiddleware, allow_origins=["*"])
  
  server = TACFastAPIServer(tac=tac, voice_channel=vc, app=app)
  
  @server.app.get("/health")
  async def health() -> dict:
  return {"status": "ok"}
  
  server.start()

<a id="tac.server.fastapi_server.TACFastAPIServer.start"></a>

#### start

```python
def start() -> None
```

Start uvicorn serving ``self.app``.

<a id="tac.server.config"></a>

# tac.server.config

Configuration for TAC server implementations.

<a id="tac.server.config.TACServerConfig"></a>

## TACServerConfig Objects

```python
class TACServerConfig(BaseModel)
```

Configuration for TAC server implementations.

Controls host/port binding, public domain for WebSocket URLs,
and customizable webhook paths.

<a id="tac.server.config.TACServerConfig.from_env"></a>

#### from\_env

```python
@classmethod
def from_env(cls) -> "TACServerConfig"
```

Create config from environment variables.

Environment variables:
    TWILIO_VOICE_PUBLIC_DOMAIN: Public domain for WebSocket URLs (required for voice)
    TWILIO_SERVER_HOST: Host to bind to (default: 0.0.0.0)
    TWILIO_SERVER_PORT: Port to bind to (default: 8000)

<a id="tac.server.signature_validation"></a>

# tac.server.signature\_validation

Webhook signature validation for Twilio webhooks.

This module provides utilities for validating Twilio webhook signatures
in FastAPI applications. It handles proxy headers (X-Forwarded-Proto,
X-Forwarded-Host) for environments like ngrok.

Requires: pip install tac[server]

<a id="tac.server.signature_validation.validate_twilio_webhook"></a>

#### validate\_twilio\_webhook

```python
def validate_twilio_webhook(request: Request, auth_token: str,
                            body: str | Mapping[str, str]) -> bool
```

Validate a Twilio webhook signature.

Verifies the X-Twilio-Signature header matches the expected signature for the
request URL and body. Handles proxy headers (X-Forwarded-Proto, X-Forwarded-Host)
for environments like ngrok.

**Arguments**:

- `request` - FastAPI Request object containing headers and URL info.
- `auth_token` - Twilio Auth Token used for signature validation.
- `body` - Request body - pass str for JSON bodies (SMS webhooks from Conversation Orchestrator,
  where signature is computed with empty POST params), or pass a mapping
  for form-encoded bodies (Voice webhooks, where params are included).
  Accepts dict, FormData, or any Mapping[str, str].
  

**Returns**:

  True if signature is valid, False otherwise.

<a id="tac.server.signature_validation.build_http_signature_dependency"></a>

#### build\_http\_signature\_dependency

```python
def build_http_signature_dependency(
        auth_token: str) -> Callable[..., Awaitable[None]]
```

Build a FastAPI dependency that validates Twilio webhook signatures on HTTP POST routes.

Usage:
    sig_dep = build_http_signature_dependency(auth_token)

    @app.post("/webhook", dependencies=[Depends(sig_dep)])
    async def webhook(request: Request) -> JSONResponse:
        ...

<a id="tac.server.signature_validation.build_websocket_signature_dependency"></a>

#### build\_websocket\_signature\_dependency

```python
def build_websocket_signature_dependency(
        auth_token: str) -> Callable[..., Awaitable[None]]
```

Build a FastAPI dependency that validates Twilio signatures on WebSocket upgrade requests.

Validates the signature before the WebSocket is accepted.
Closes with code 1008 (Policy Violation) on invalid signature.

Usage:
    ws_dep = build_websocket_signature_dependency(auth_token)

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket, _: None = Depends(ws_dep)) -> None:
        ...

<a id="tac.intelligence.operator_result_processor"></a>

# tac.intelligence.operator\_result\_processor

Processor for Conversation Intelligence webhook events.

<a id="tac.intelligence.operator_result_processor.OperatorResultProcessor"></a>

## OperatorResultProcessor Objects

```python
class OperatorResultProcessor()
```

Processor for Conversation Intelligence webhook events.

This processor handles incoming CI webhook payloads, validates them,
and creates observations or summaries in Conversation Memory based on the event type.

Events are filtered by:
- Configuration ID matching the provided config
- Operator SID matching observation or summary operator SID in config

Example usage:
    ```python
    from tac.context.memory import MemoryClient
    from tac.core.config import ConversationIntelligenceConfig
    from tac.intelligence import OperatorResultProcessor

    conversation_memory_client = MemoryClient(...)
    config = ConversationIntelligenceConfig(
        configuration_id="GA...",
        observation_operator_sid="LY...",
        summary_operator_sid="LY...",
    )
    processor = OperatorResultProcessor(conversation_memory_client, config)

    result = await processor.process_event(webhook_payload)
    if result.success:
        print(f"Created {result.created_count} {result.event_type}(s)")
    elif result.skipped:
        print(f"Skipped: {result.skip_reason}")
    else:
        print(f"Error: {result.error}")
    ```

<a id="tac.intelligence.operator_result_processor.OperatorResultProcessor.__init__"></a>

#### \_\_init\_\_

```python
def __init__(conversation_memory_client: MemoryClient,
             config: ConversationIntelligenceConfig) -> None
```

Initialize the CI event processor.

**Arguments**:

- `conversation_memory_client` - MemoryClient instance for creating observations/summaries
- `config` - ConversationIntelligenceConfig for filtering events by configuration
  ID and operator SIDs

<a id="tac.intelligence.operator_result_processor.OperatorResultProcessor.process_event"></a>

#### process\_event

```python
async def process_event(payload: dict[str, Any]) -> OperatorProcessingResult
```

Process a CI webhook payload.

This method:
1. Parses the payload into an OperatorResultEvent (Pydantic validates required fields)
2. Applies filtering logic based on intelligence configuration ID and operator SIDs
3. Iterates over operator_results array
4. For each operator result: extracts profile IDs, generates content
5. Creates observations or summaries in Conversation Memory

**Arguments**:

- `payload` - The raw webhook payload dictionary
  

**Returns**:

  OperatorProcessingResult with status and details

<a id="tac.session.base"></a>

# tac.session.base

Abstract base class for session management.

Defines the interface that all session manager implementations must follow.

<a id="tac.session.base.SessionManager"></a>

## SessionManager Objects

```python
class SessionManager(ABC)
```

Abstract base class for managing session state with task cancellation support.

Implementations manage session state and track async tasks for graceful
cancellation. This enables responsive interactions across different channels where:
- New requests can cancel previous incomplete responses
- Sessions are properly cleaned up with task cancellation
- Concurrent sessions are tracked independently

Example use cases:
- Voice channels: Track streaming tasks and cancel when user interrupts
- Chat channels: Track typing indicators or long-running operations
- Any channel with async operations that need graceful cancellation

To implement a custom session manager, inherit from this class and implement
all abstract methods. See ThreadSafeSessionManager for a reference implementation.

<a id="tac.session.base.SessionManager.get_or_create_session"></a>

#### get\_or\_create\_session

```python
@abstractmethod
def get_or_create_session(session_id: str) -> SessionState
```

Get existing session or create a new one.

**Arguments**:

- `session_id` - Unique session identifier
  

**Returns**:

  SessionState object for the session

<a id="tac.session.base.SessionManager.has_session"></a>

#### has\_session

```python
@abstractmethod
def has_session(session_id: str) -> bool
```

Check if a session exists.

**Arguments**:

- `session_id` - Unique session identifier
  

**Returns**:

  True if session exists, False otherwise

<a id="tac.session.base.SessionManager.remove_session"></a>

#### remove\_session

```python
@abstractmethod
def remove_session(session_id: str) -> None
```

Remove session and clean up resources.

**Arguments**:

- `session_id` - Unique session identifier

<a id="tac.session.base.SessionManager.get_all_session_ids"></a>

#### get\_all\_session\_ids

```python
@abstractmethod
def get_all_session_ids() -> list[str]
```

Get all active session IDs.

**Returns**:

  List of session identifiers

<a id="tac.session.base.SessionManager.__len__"></a>

#### \_\_len\_\_

```python
@abstractmethod
def __len__() -> int
```

Return number of active sessions.

**Returns**:

  Count of active sessions

<a id="tac.session.state"></a>

# tac.session.state

Session management utilities for agents

<a id="tac.session.state.SessionState"></a>

## SessionState Objects

```python
class SessionState()
```

Manages session state for voice conversations with streaming task tracking.

Tracks the active streaming task to enable cancellation when:
- A new prompt arrives (cancel previous incomplete response)
- An interrupt occurs (user speaks over the agent)
- The session ends (cleanup)

<a id="tac.session.state.SessionState.cancel_stream_task"></a>

#### cancel\_stream\_task

```python
async def cancel_stream_task() -> None
```

Cancel an in-flight streaming task with timeout protection.

<a id="tac.session.thread_safe"></a>

# tac.session.thread\_safe

Thread-safe session manager implementation.

Provides concurrent session handling with RLock-based synchronization.

<a id="tac.session.thread_safe.ThreadSafeSessionManager"></a>

## ThreadSafeSessionManager Objects

```python
class ThreadSafeSessionManager(SessionManager)
```

Thread-safe implementation of SessionManager for concurrent session handling.

This implementation provides:
- Thread-safe session storage using RLock for concurrent access
- Task lifecycle management with graceful cancellation
- SessionState tracking for each conversation

Tracks active async tasks per session, enabling cancellation when:
- A new request arrives (cancels previous in-flight task)
- An interrupt occurs (e.g., voice channel user interrupts mid-response)
- The session ends (cleanup with graceful task cancellation)

<a id="tac.session.thread_safe.ThreadSafeSessionManager.__init__"></a>

#### \_\_init\_\_

```python
def __init__() -> None
```

Initialize thread-safe session manager.

<a id="tac.utils.redaction"></a>

# tac.utils.redaction

PII redaction utilities for log output.

<a id="tac.utils.redaction.mask_phone"></a>

#### mask\_phone

```python
def mask_phone(value: str | None) -> str
```

Mask a phone number, preserving the first 2 and last 4 characters.

Returns ``"***"`` for ``None``, empty, or short (< 7 char) inputs.

<a id="tac.utils.redaction.mask_email"></a>

#### mask\_email

```python
def mask_email(value: str | None) -> str
```

Mask an email address, preserving the first character and full domain.

Returns ``"***"`` for ``None``, empty, or strings without ``@``.

<a id="tac.utils.redaction.mask_address"></a>

#### mask\_address

```python
def mask_address(value: str | None) -> str
```

Auto-detect address type and apply the appropriate mask.

Delegates to :func:`mask_email` if the value contains ``@``,
otherwise to :func:`mask_phone`.

