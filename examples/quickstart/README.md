# TAC Quickstart Setup

A web-based setup wizard to help you create the Memory (Memora) and Maestro services required for Twilio Agent Connect.

## Overview

Before using TAC, you need to set up two Twilio services:

1. **Memory Store (Memora)** - Stores conversation memories, observations, and user profiles
2. **Conversation Service (Maestro)** - Manages conversations and participants

This wizard automates the creation of these services using your Twilio credentials.

## Prerequisites

You'll need the following from your [Twilio Console](https://console.twilio.com):

- **Account SID** - Found on your Console dashboard (starts with `AC`)
- **Auth Token** - Found on your Console dashboard
- **API Key SID** - Create at Console > Account > API keys & tokens (starts with `SK`)
- **API Secret** - Shown only once when creating the API key

## Usage

```bash
# From the repository root
make quickstart
```

Then open http://localhost:8080 in your browser.

## What It Does

1. Validates your Twilio credentials
2. Creates a Memory Store in Memora
3. Creates a test Profile with your contact info (for verifying the setup works)
4. Creates a Conversation Service in Maestro
5. Returns the service IDs to add to your `.env` file
