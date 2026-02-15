#!/usr/bin/env python3
"""
Test the deployed MCP server on AgentCore Runtime.

Connects to the deployed endpoint, lists available tools,
and optionally runs a test query.

Usage:
    export AWS_PROFILE=claude
    python -m src.test_remote
    python -m src.test_remote --query "Profile the housing dataset"
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import timedelta

from dotenv import load_dotenv

ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(ENV_FILE)


async def test_connection(agent_arn: str, region: str, query: str | None = None):
    """Connect to the MCP endpoint and list tools / run a query."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    encoded_arn = agent_arn.replace(":", "%3A").replace("/", "%2F")
    mcp_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"

    print(f"📡 Connecting to: {mcp_url}\n")

    # For IAM auth, we need to sign the request
    # For now, using direct connection (works if the Runtime has no auth configured)
    headers = {"Content-Type": "application/json"}

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
                    print(f"     {tool.description}")
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
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Test deployed MCP server")
    parser.add_argument("--query", type=str, help="Optional test query to run")
    parser.add_argument("--arn", type=str, help="Agent ARN (default: from .env)")
    args = parser.parse_args()

    agent_arn = args.arn or os.getenv("AGENT_ARN")
    region = os.getenv("REGION", "us-east-1")

    if not agent_arn:
        print("❌ AGENT_ARN not found. Either:")
        print("   - Run deploy_runtime.py first")
        print("   - Pass --arn <agent_arn>")
        sys.exit(1)

    print("🧪 Testing AgentCore Runtime MCP Server")
    print("=" * 50)
    print(f"   Agent ARN: {agent_arn}")
    print(f"   Region:    {region}")
    print()

    asyncio.run(test_connection(agent_arn, region, args.query))


if __name__ == "__main__":
    main()
