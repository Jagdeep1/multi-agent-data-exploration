#!/usr/bin/env python3
"""
Deploy the multi-agent MCP server to Amazon Bedrock AgentCore Runtime.

Prerequisites:
    1. Docker must be running
    2. Run deploy_iam_role.py first (creates execution role)
    3. Run deploy_code_interpreter.py first (creates Code Interpreter instances)
    4. Run src.utils.dataset to generate sample data

Usage:
    export AWS_PROFILE=claude
    python -m src.deploy_runtime
"""

import json
import os
import sys
import time

import boto3
from botocore.config import Config
from dotenv import load_dotenv

from src.config import AWS_REGION

ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")
AGENT_NAME = "multi-agent-data-explorer"


def check_prerequisites():
    """Verify everything is in place before deploying."""
    load_dotenv(ENV_FILE)

    errors = []

    # Check .env exists
    if not os.path.exists(ENV_FILE):
        errors.append(f".env file not found at {ENV_FILE}. Run deploy_iam_role.py first.")

    # Check execution role
    role_arn = os.getenv("EXECUTION_ROLE_ARN")
    if not role_arn:
        errors.append("EXECUTION_ROLE_ARN not set in .env. Run: python -m src.deploy_iam_role")

    # Check Code Interpreter IDs
    ds_id = os.getenv("DATASCIENTIST_CODE_INTERPRETER_ID")
    dv_id = os.getenv("DATAVISUALIZER_CODE_INTERPRETER_ID")
    if not ds_id or not dv_id:
        errors.append("Code Interpreter IDs not set in .env. Run: python -m src.deploy_code_interpreter")

    # Check data directory
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    if not os.path.exists(os.path.join(data_dir, "housing.csv")):
        errors.append("data/housing.csv not found. Run: python -m src.utils.dataset")

    # Check Docker
    import subprocess
    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=10)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        errors.append("Docker is not running. Start Docker Desktop and try again.")

    if errors:
        print("❌ Prerequisites not met:\n")
        for e in errors:
            print(f"   • {e}")
        sys.exit(1)

    print("✅ All prerequisites met")
    return role_arn


def deploy():
    """Configure and launch the AgentCore Runtime."""
    role_arn = check_prerequisites()

    # Import starter toolkit
    try:
        from bedrock_agentcore_starter_toolkit import Runtime
    except ImportError:
        print("❌ bedrock-agentcore-starter-toolkit not installed.")
        print("   Run: pip install bedrock-agentcore-starter-toolkit")
        sys.exit(1)

    print(f"\n🚀 Deploying '{AGENT_NAME}' to AgentCore Runtime")
    print(f"   Region: {AWS_REGION}")
    print(f"   Role: {role_arn}")
    print(f"   Protocol: MCP")
    print()

    runtime = Runtime()

    # Step 1: Configure
    print("📦 Step 1/3: Configuring deployment...")
    response = runtime.configure(
        entrypoint="src/mcp_server.py",
        auto_create_execution_role=False,
        execution_role_arn=role_arn,
        auto_create_ecr=True,
        requirements_file="requirements.txt",
        region=AWS_REGION,
        protocol="MCP",
        agent_name=AGENT_NAME,
    )
    print(f"   ✅ Configuration complete")

    # Step 2: Launch (builds Docker image, pushes to ECR, creates Runtime)
    print("\n🐳 Step 2/3: Building and deploying (this may take several minutes)...")
    launch_result = runtime.launch()
    print(f"   ✅ Launch initiated")
    print(f"   Agent ARN: {launch_result.agent_arn}")
    print(f"   Agent ID:  {launch_result.agent_id}")
    print(f"   ECR URI:   {launch_result.ecr_uri}")

    # Step 3: Wait for READY
    print("\n⏳ Step 3/3: Waiting for Runtime to be ready...")
    end_statuses = {"READY", "CREATE_FAILED", "DELETE_FAILED", "UPDATE_FAILED"}
    status = "CREATING"
    attempt = 0
    while status not in end_statuses:
        time.sleep(15)
        attempt += 1
        try:
            status_response = runtime.status()
            status = status_response.endpoint["status"]
        except Exception as e:
            status = f"CHECKING ({e})"
        print(f"   [{attempt * 15}s] Status: {status}")

    if status == "READY":
        print(f"\n🎉 Deployment successful!")
    else:
        print(f"\n❌ Deployment failed with status: {status}")
        sys.exit(1)

    # Save agent ARN to .env
    _update_env("AGENT_ARN", launch_result.agent_arn)
    _update_env("AGENT_ID", launch_result.agent_id)

    # Print connection info
    encoded_arn = launch_result.agent_arn.replace(":", "%3A").replace("/", "%2F")
    mcp_url = f"https://bedrock-agentcore.{AWS_REGION}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"

    print(f"\n📡 MCP Endpoint:")
    print(f"   {mcp_url}")
    print(f"\nNext steps:")
    print(f"  1. Test:    python -m src.test_remote")
    print(f"  2. Cleanup: python -m src.cleanup")

    return launch_result


def _update_env(key: str, value: str):
    """Add or update a key in the .env file."""
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


def main():
    print("=" * 60)
    print("  AgentCore Runtime Deployment — MCP Server")
    print("=" * 60)
    deploy()


if __name__ == "__main__":
    main()
