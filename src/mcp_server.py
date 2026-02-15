#!/usr/bin/env python3
"""
MCP Server entrypoint for AgentCore Runtime deployment.

Exposes the multi-agent Supervisor as a single MCP tool ("analyze_data")
that clients can invoke via the MCP protocol.

Local testing:
    python -m src.mcp_server
    # Then connect an MCP client to http://localhost:8000/mcp

AgentCore Runtime:
    Deployed via deploy_runtime.py — AgentCore handles the HTTP serving.
"""

import os
import sys

from dotenv import load_dotenv

# Load .env before any agent imports (Code Interpreter IDs, etc.)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("multi-agent-data-explorer", host="0.0.0.0", stateless_http=True)


@mcp.tool()
def analyze_data(query: str) -> str:
    """
    Send a data analysis query to the multi-agent data exploration system.

    The Supervisor agent will automatically delegate to specialist agents:
    - Data Engineer: data profiling, cleaning, missing value handling
    - Data Scientist: ML model training, feature engineering, statistical analysis
    - Visualizer: charts, plots, correlation heatmaps

    Examples:
    - "Profile the housing dataset and check for data quality issues"
    - "Clean the data and train a model to predict median house values"
    - "Create visualizations showing the relationship between income and house values"
    - "Give me a complete analysis: clean, model, and visualize"

    Args:
        query: Natural language description of the data analysis task.

    Returns:
        The Supervisor's synthesized response combining insights from all agents.
    """
    # Import here to avoid heavy loading at module level (faster cold start for tool listing)
    from src.agents.supervisor import create_supervisor_agent

    supervisor = create_supervisor_agent()
    result = supervisor(query)

    # Extract text content from the agent response
    try:
        content = result.message.get("content", [])
        texts = [block["text"] for block in content if isinstance(block, dict) and block.get("type") == "text"]
        return "\n".join(texts) if texts else str(result)
    except Exception:
        return str(result)


@mcp.tool()
def list_datasets() -> str:
    """
    List available datasets in the data directory.

    Returns:
        A list of CSV files available for analysis.
    """
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    if not os.path.exists(data_dir):
        return "No data directory found. Run 'python -m src.utils.dataset' to generate sample data."

    files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
    if not files:
        return "No CSV files found in data/. Run 'python -m src.utils.dataset' to generate sample data."

    result = "Available datasets:\n"
    for f in sorted(files):
        path = os.path.join(data_dir, f)
        size_kb = os.path.getsize(path) / 1024
        result += f"  - {f} ({size_kb:.1f} KB)\n"
    return result


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
