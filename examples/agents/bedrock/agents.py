#!/usr/bin/env python3
"""
AWS Bedrock Agents Example

This demonstrates how to use AWS Bedrock Agents, a fully managed service that
handles agent orchestration, tool calling, and knowledge base integration.

Bedrock Agents provide:
- Automatic orchestration and ReAct-style prompting
- Action Groups (tools/functions the agent can call)
- Knowledge Bases (built-in RAG)
- Session management and memory
- Guardrails for safety

Use this approach when you need:
- Managed agent orchestration
- Built-in tool calling without custom loops
- RAG with managed knowledge bases
- Production-ready agent infrastructure

Note: This example requires you to create a Bedrock Agent in the AWS Console first.
"""

import json
from typing import Any, Optional

import boto3


class BedrockManagedAgent:
    """Interface for interacting with AWS Bedrock Agents (managed service)."""

    def __init__(
        self,
        agent_id: str,
        agent_alias_id: str,
        region_name: str = "us-east-1",
    ):
        """
        Initialize the Bedrock Agents client.

        Args:
            agent_id: The Bedrock Agent ID (from AWS Console)
            agent_alias_id: The agent alias ID (e.g., "TSTALIASID" for draft)
            region_name: AWS region for Bedrock
        """
        self.agent_id = agent_id
        self.agent_alias_id = agent_alias_id
        self.client = boto3.client(
            service_name="bedrock-agent-runtime",
            region_name=region_name,
        )
        self.session_id: Optional[str] = None

    def invoke(
        self,
        user_input: str,
        session_id: Optional[str] = None,
        enable_trace: bool = False,
    ) -> dict[str, Any]:
        """
        Invoke the Bedrock Agent with user input.

        Args:
            user_input: The user's message
            session_id: Optional session ID for conversation continuity
            enable_trace: Whether to include reasoning trace in response

        Returns:
            Dictionary containing response text and metadata
        """
        # Use provided session_id or the stored one
        if session_id:
            self.session_id = session_id
        elif not self.session_id:
            # Generate a new session ID if none exists
            import uuid

            self.session_id = str(uuid.uuid4())

        # Invoke the agent
        response = self.client.invoke_agent(
            agentId=self.agent_id,
            agentAliasId=self.agent_alias_id,
            sessionId=self.session_id,
            inputText=user_input,
            enableTrace=enable_trace,
        )

        # Process the streaming response
        result = self._process_response(response, enable_trace)
        return result

    def _process_response(self, response: dict[str, Any], include_trace: bool) -> dict[str, Any]:
        """
        Process the streaming response from Bedrock Agent.

        Args:
            response: Raw response from invoke_agent
            include_trace: Whether to include reasoning trace

        Returns:
            Processed response with text and optional trace
        """
        result = {
            "text": "",
            "trace": [] if include_trace else None,
            "session_id": self.session_id,
        }

        # Process event stream
        event_stream = response.get("completion", [])

        for event in event_stream:
            # Extract text chunks
            if "chunk" in event:
                chunk = event["chunk"]
                if "bytes" in chunk:
                    text = chunk["bytes"].decode("utf-8")
                    result["text"] += text

            # Extract trace information (reasoning steps, tool calls, etc.)
            if include_trace and "trace" in event:
                trace = event["trace"]["trace"]
                result["trace"].append(trace)

        return result

    def reset_session(self) -> None:
        """Reset the session to start a new conversation."""
        self.session_id = None


# Example usage
if __name__ == "__main__":
    import os

    # Get agent configuration from environment variables
    agent_id = os.environ.get("BEDROCK_AGENT_ID")
    agent_alias_id = os.environ.get("BEDROCK_AGENT_ALIAS_ID", "TSTALIASID")
    region = os.environ.get("AWS_REGION", "us-east-1")

    if not agent_id:
        print("Error: BEDROCK_AGENT_ID environment variable not set")
        print("\nTo use this example:")
        print("1. Create a Bedrock Agent in AWS Console")
        print("2. Set environment variable: export BEDROCK_AGENT_ID=<your-agent-id>")
        print("3. Optionally set: export BEDROCK_AGENT_ALIAS_ID=<your-alias-id>")
        exit(1)

    # Create managed agent client
    agent = BedrockManagedAgent(
        agent_id=agent_id,
        agent_alias_id=agent_alias_id,
        region_name=region,
    )

    print(f"Bedrock Managed Agent initialized (Agent ID: {agent_id})")
    print("Type 'quit' to exit, 'reset' to start new session, 'trace' to see reasoning.\n")

    show_trace = False

    # Simple chat loop
    while True:
        user_input = input("You: ").strip()

        if user_input.lower() in ["quit", "exit", "bye"]:
            print("Goodbye!")
            break

        if user_input.lower() == "reset":
            agent.reset_session()
            print("Session reset. Starting new conversation.\n")
            continue

        if user_input.lower() == "trace":
            show_trace = not show_trace
            status = "enabled" if show_trace else "disabled"
            print(f"Trace {status}.\n")
            continue

        if not user_input:
            continue

        try:
            # Invoke the agent
            result = agent.invoke(user_input, enable_trace=show_trace)

            # Display response
            print(f"Agent: {result['text']}\n")

            # Display trace if enabled
            if show_trace and result["trace"]:
                print("--- Reasoning Trace ---")
                for i, trace_step in enumerate(result["trace"], 1):
                    print(f"Step {i}: {json.dumps(trace_step, indent=2)}")
                print("--- End Trace ---\n")

        except Exception as e:
            print(f"Error: {e}\n")
