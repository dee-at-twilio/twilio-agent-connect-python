# Core API Reference

This page documents the core TAC classes and functions.

## TAC

The main orchestrator class that coordinates all TAC components.

```python
from tac import TAC, TACConfig

tac = TAC(config=TACConfig.from_env())
```

### Methods

#### `__init__(config: TACConfig)`

Initialize a TAC instance with configuration.

#### `on_message_ready(callback)`

Register callback for when a message is ready for processing.

```python
async def handle_message(user_message: str, context, memory_response):
    return "Response"

tac.on_message_ready(handle_message)
```

#### `on_conversation_ended(callback)`

Register callback for when a conversation ends.

```python
async def handle_ended(context):
    print(f"Conversation {context.conversation_id} ended")

tac.on_conversation_ended(handle_ended)
```

#### `retrieve_memory(profile_id, conversation_id, query=None)`

Manually retrieve memory for a user.

#### `is_orchestrator_enabled()`

Check if Conversation Orchestrator is configured.

## TACConfig

Configuration for TAC instances.

```python
from tac import TACConfig

# From environment
config = TACConfig.from_env()

# Manual
config = TACConfig(
    api_key="SKxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    api_token="your_api_secret_here",
    account_sid="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    conversation_configuration_id="conv_configuration_xxxxx"
)
```

### Fields

- `api_key: str` - Twilio API Key SID
- `api_token: str` - Twilio API Token (Secret)
- `account_sid: str` - Twilio Account SID
- `conversation_configuration_id: str | None` - Conversation Configuration SID (optional for ConversationRelay-only mode)

## Context Models

### TACContext

Context information passed to callbacks containing conversation metadata, participant info, and profile data.

### TACMemoryResponse

Memory retrieval response containing user memories and profile information.

## API Clients

API clients for interacting with Twilio services. These are used internally by TAC but can also be used directly.

### ConversationClient

Client for Conversation Orchestrator API.

### MemoryClient

Client for Conversation Memory API.

### KnowledgeClient

Client for Knowledge Base API.

---

**Note**: Full API reference with type signatures coming soon. For now, see the [source code](https://github.com/twilio/twilio-agent-connect-python/tree/main/src/tac) for detailed implementation.
