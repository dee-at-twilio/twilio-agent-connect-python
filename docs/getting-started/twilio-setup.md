# Twilio Setup

This guide covers setting up the required Twilio resources for TAC.

## Prerequisites

- A Twilio account ([Sign up here](https://www.twilio.com/try-twilio))
- Twilio API credentials (API Key and Secret)

## Option 1: Setup Wizard (Recommended)

The easiest way to get started is using our setup wizard:

```bash
git clone https://github.com/twilio/twilio-agent-connect-python.git
cd twilio-agent-connect-python
make setup
```

This opens a web interface at `http://localhost:8080` that will:

1. Create a Memory Store
2. Create a Conversation Configuration
3. Link them together
4. Generate your `.env` file

## Option 2: Manual Setup

### Step 1: Create API Credentials

1. Go to [Twilio Console - API Keys](https://console.twilio.com/us1/account/keys-credentials/api-keys)
2. Click "Create API Key"
3. Name it (e.g., "TAC Development")
4. Save the SID (API Key) and Secret (API Token) securely

### Step 2: Create a Memory Store

1. Go to [Conversation Memory Console](https://console.twilio.com/us1/develop/conversations/memory)
2. Click "Create Memory Store"
3. Configure your store:
   - **Name**: e.g., "TAC Memory Store"
   - **Description**: Optional
4. Save the Memory Store SID

### Step 3: Create a Conversation Configuration

1. Go to [Conversation Orchestrator Console](https://console.twilio.com/us1/develop/conversations/orchestrator)
2. Click "Create Configuration"
3. Configure:
   - **Name**: e.g., "TAC Configuration"
   - **Memory Store**: Select the store from Step 2
   - **Other settings**: Configure as needed
4. Save the Configuration SID

### Step 4: Configure Environment

Create a `.env` file:

```bash
# Twilio Account
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_API_KEY=SKxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_API_TOKEN=your_api_token

# TAC Configuration
CONVERSATION_CONFIGURATION_ID=OCxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional: For voice
TWILIO_PHONE_NUMBER=+1234567890

# Optional: For OpenAI integration
OPENAI_API_KEY=sk-...
```

### Step 5: Set Up Phone Number Webhooks

For Voice:

1. Go to [Phone Numbers](https://console.twilio.com/us1/develop/phone-numbers/manage/incoming)
2. Select your number
3. Under "Voice Configuration":
   - **A CALL COMES IN**: Webhook, `https://your-domain.com/twiml`, HTTP POST

For SMS:

1. Same phone number settings
2. Under "Messaging Configuration":
   - **A MESSAGE COMES IN**: Webhook, `https://your-domain.com/webhook`, HTTP POST

For WhatsApp:

1. Go to [WhatsApp Senders](https://console.twilio.com/us1/develop/sms/senders/whatsapp-senders)
2. Select your sender
3. Configure webhook: `https://your-domain.com/webhook`

## Verify Setup

Test your configuration:

```python
from tac import TAC, TACConfig

config = TACConfig.from_env()
tac = TAC(config=config)

# Check if Orchestrator is enabled
print(f"Orchestrator enabled: {tac.is_orchestrator_enabled()}")
```

## Troubleshooting

### "Invalid API credentials"

- Verify API Key and Token are correct
- Check that API Key is active in Twilio Console
- Ensure Account SID matches the account that created the API Key

### "Configuration not found"

- Verify `CONVERSATION_CONFIGURATION_ID` is correct
- Check that the configuration exists and is active
- Ensure your API credentials have access to the configuration

### "Memory Store not found"

- Verify the Memory Store is linked to your Conversation Configuration
- Check Memory Store status in Twilio Console

## Next Steps

- [Quick Start Guide](quickstart.md) - Build your first agent
- [Installation](installation.md) - Install TAC
