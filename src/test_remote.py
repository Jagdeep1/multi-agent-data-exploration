#!/usr/bin/env python3
"""
Test the deployed MCP server on AgentCore Runtime.

Connects to the deployed endpoint using Cognito JWT auth,
lists available tools, and optionally runs a test query.

Usage:
    export AWS_PROFILE=claude
    python -m src.test_remote
    python -m src.test_remote --query "Profile the housing dataset"
"""

import argparse
import asyncio
import base64
import json
import os
import sys
import time
from datetime import timedelta

import boto3
from dotenv import load_dotenv

from src.config import AWS_REGION

ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(ENV_FILE)


def refresh_access_token(client_id: str, refresh_token: str) -> str:
    """Get a new access token using the refresh token."""
    client = boto3.client("cognito-idp", region_name=AWS_REGION)
    response = client.initiate_auth(
        ClientId=client_id,
        AuthFlow="REFRESH_TOKEN_AUTH",
        AuthParameters={"REFRESH_TOKEN": refresh_token},
    )
    return response["AuthenticationResult"]["AccessToken"]


def get_valid_token() -> str:
    """Return a valid bearer token, refreshing if needed."""
    bearer_token = os.getenv("COGNITO_BEARER_TOKEN", "")
    client_id = os.getenv("COGNITO_CLIENT_ID", "")
    refresh_token = os.getenv("COGNITO_REFRESH_TOKEN", "")

    if not bearer_token or not client_id:
        print("❌ Cognito tokens not found in .env. Run: python -m src.deploy_cognito")
        sys.exit(1)

    # Check if token is expired or expiring soon
    try:
        payload_b64 = bearer_token.split(".")[1]
        # Add padding
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.b64decode(payload_b64))
        exp = payload.get("exp", 0)

        if time.time() > exp - 300:  # Less than 5 min remaining
            print("🔄 Token expired or expiring soon, refreshing...")
            bearer_token = refresh_access_token(client_id, refresh_token)
            _update_env("COGNITO_BEARER_TOKEN", bearer_token)
            print("✅ Token refreshed")
    except Exception as e:
        print(f"🔄 Could not validate token ({e}), refreshing...")
        try:
            bearer_token = refresh_access_token(client_id, refresh_token)
            _update_env("COGNITO_BEARER_TOKEN", bearer_token)
            print("✅ Token refreshed")
        except Exception as refresh_err:
            print(f"❌ Token refresh failed: {refresh_err}")
            print("   Re-run: python -m src.deploy_cognito")
            sys.exit(1)

    return bearer_token


def _update_env(key: str, value: str):
    """Update a key in the .env file."""
    lines = []
    found = False

    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as f:
            for line in f:
                if line.startswith(f"{key}="):
                    lines.append(f"{key}={value}\n")
                    found = True
                else:
                    lines.append(line)

    if not found:
        lines.append(f"{key}={value}\n")

    with open(ENV_FILE, "w") as f:
        f.writelines(lines)


async def test_connection(agent_arn: str, bearer_token: str, query: str | None = None):
    """Connect to the MCP endpoint and list tools / run a query."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    encoded_arn = agent_arn.replace(":", "%3A").replace("/", "%2F")
    mcp_url = f"https://bedrock-agentcore.{AWS_REGION}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"

    print(f"📡 Connecting to:\n   {mcp_url}\n")

    headers = {
        "authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
    }

    try:
        async with streamablehttp_client(
            mcp_url, headers, timeout=timedelta(seconds=300), terminate_on_close=False
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                print("🔄 Initializing MCP session...")
                await session.initialize()
                print("✅ MCP session initialized\n")

                # List tools
                print("📋 Available MCP Tools:")
                print("=" * 50)
                tool_result = await session.list_tools()
                for tool in tool_result.tools:
                    print(f"  🔧 {tool.name}")
                    if tool.description:
                        # Print first line of description
                        desc = tool.description.strip().split("\n")[0]
                        print(f"     {desc}")
                    if hasattr(tool, "inputSchema") and tool.inputSchema:
                        props = tool.inputSchema.get("properties", {})
                        if props:
                            print(f"     Parameters: {list(props.keys())}")
                    print()

                print(f"Found {len(tool_result.tools)} tool(s)\n")

                # Run test query if provided
                if query:
                    print(f"🧪 Running test query: {query}")
                    print("=" * 50)
                    result = await session.call_tool("analyze_data", {"query": query})
                    for content in result.content:
                        if hasattr(content, "text"):
                            print(content.text)
                    print()

                print("✅ All tests passed!")

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Test deployed MCP server")
    parser.add_argument("--query", type=str, help="Optional test query to run")
    parser.add_argument("--arn", type=str, help="Agent ARN (default: from .env)")
    args = parser.parse_args()

    agent_arn = args.arn or os.getenv("AGENT_ARN")

    if not agent_arn:
        print("❌ AGENT_ARN not found. Either:")
        print("   - Run deploy_runtime.py first")
        print("   - Pass --arn <agent_arn>")
        sys.exit(1)

    print("🧪 Testing AgentCore Runtime MCP Server")
    print("=" * 50)
    print(f"   Agent ARN: {agent_arn}")
    print(f"   Region:    {AWS_REGION}")
    print()

    # Get valid bearer token
    bearer_token = get_valid_token()
    print()

    asyncio.run(test_connection(agent_arn, bearer_token, args.query))


if __name__ == "__main__":
    main()
