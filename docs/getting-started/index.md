# Getting Started

Welcome to Twilio Agent Connect! This guide will help you set up TAC and build your first AI agent.

## Prerequisites

- Python 3.10 or newer
- A Twilio account ([Sign up here](https://www.twilio.com/try-twilio))
- Basic familiarity with Python async/await

## Setup Options

TAC offers two ways to get started:

### Option 1: Setup Wizard (Recommended)

Use the [Twilio Setup Wizard](twilio-setup.md) to automatically create a Memory Store and Conversation Configuration and generate your `.env` file:

```bash
git clone https://github.com/twilio/twilio-agent-connect-python.git
cd twilio-agent-connect-python
make setup  # Open http://localhost:8080
```

### Option 2: Manual Setup

You can also create a Memory Store and Conversation Configuration manually through the [Twilio Console](https://console.twilio.com). For a full walkthrough — credentials, Console navigation, and webhook configuration — see the [TAC Quickstart](https://www.twilio.com/docs/conversations/agent-connect/quickstart).

## What's Next?

- [Installation Guide](installation.md) - Install TAC in your project
- [Quick Start](quickstart.md) - Build your first agent
- [Twilio Setup](twilio-setup.md) - Configure Twilio services
