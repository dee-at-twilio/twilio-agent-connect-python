#!/usr/bin/env python3
"""
AWS Bedrock Converse API Example

This demonstrates how to create a conversational agent using AWS Bedrock's Converse API.
The Converse API provides a simple, unified interface for chat-based interactions with
foundation models. You manage conversation history and agent orchestration yourself.

Use this approach when you need:
- Full control over agent behavior
- Custom conversation management
- Simple chat interactions
- Integration with your own tools/workflows

Run this example:
    python examples/agents/bedrock/converse.py
    or
    python -m examples.agents.bedrock.converse
"""

from typing import Any

import boto3


class BedrockConverseAgent:
    """A simple conversational agent using AWS Bedrock Converse API."""

    def __init__(
        self,
        model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
        region_name: str = "us-east-1",
        system_prompt: str = "You are a helpful assistant.",
    ):
        """
        Initialize the Bedrock agent.

        Args:
            model_id: The Bedrock model ID to use
            region_name: AWS region for Bedrock
            system_prompt: System prompt for the agent
        """
        self.client = boto3.client(
            service_name="bedrock-runtime",
            region_name=region_name,
        )
        self.model_id = model_id
        self.system_prompt = system_prompt
        self.conversation_history: list[dict[str, Any]] = []

    def chat(self, user_message: str) -> str:
        """
        Send a message and get a response.

        Args:
            user_message: The user's message

        Returns:
            The agent's response
        """
        # Add user message to history
        self.conversation_history.append(
            {
                "role": "user",
                "content": [{"text": user_message}],
            }
        )

        # Call Bedrock Converse API
        response = self.client.converse(
            modelId=self.model_id,
            messages=self.conversation_history,
            system=[{"text": self.system_prompt}],
            inferenceConfig={
                "maxTokens": 2000,
                "temperature": 0.7,
                "topP": 0.9,
            },
        )

        # Extract response text
        assistant_message = response["output"]["message"]
        response_text = assistant_message["content"][0]["text"]

        # Add assistant response to history
        self.conversation_history.append(assistant_message)

        return response_text

    def reset_conversation(self) -> None:
        """Clear the conversation history."""
        self.conversation_history = []


# Example usage
if __name__ == "__main__":
    # Create Bedrock agent
    agent = BedrockConverseAgent(
        model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
        region_name="us-east-1",
        system_prompt="You are a helpful AI assistant. Be concise and friendly.",
    )

    print("Bedrock Converse Agent initialized! Type 'quit' to exit.\n")

    # Simple chat loop
    while True:
        user_input = input("You: ").strip()

        if user_input.lower() in ["quit", "exit", "bye"]:
            print("Goodbye!")
            break

        if not user_input:
            continue

        try:
            response = agent.chat(user_input)
            print(f"Agent: {response}\n")
        except Exception as e:
            print(f"Error: {e}\n")
