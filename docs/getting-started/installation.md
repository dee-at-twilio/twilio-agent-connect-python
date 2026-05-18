# Installation

## Requirements

- Python 3.10 or newer
- pip or uv package manager

## Install from PyPI

### Basic Installation

For basic TAC functionality (channels, memory, adapters):

```bash
pip install twilio-agent-connect
```

### With Server Support

To include the FastAPI-based `TACFastAPIServer`:

```bash
pip install "twilio-agent-connect[server]"
```

This installs additional dependencies:

- `fastapi>=0.115.0`
- `uvicorn[standard]>=0.32.0`
- `python-multipart>=0.0.20`

## Install from Source

For development or to try the latest features:

```bash
git clone https://github.com/twilio/twilio-agent-connect-python.git
cd twilio-agent-connect-python
make sync  # Installs via uv
```

## Verify Installation

```python
import tac
print(f"TAC version: {tac.__version__}")
```

## Additional Dependencies

Depending on your use case, you may need additional packages:

### For OpenAI Integration

```bash
pip install openai python-dotenv
```

### For AWS Integration

```bash
pip install boto3 boto3-stubs[bedrock-agent-runtime,bedrock-agentcore] strands-agents
```

### For Development

```bash
pip install pytest pytest-asyncio ruff mypy
```

## Next Steps

- [Quick Start Guide](quickstart.md) - Build your first agent
- [Twilio Setup](twilio-setup.md) - Configure Twilio services
