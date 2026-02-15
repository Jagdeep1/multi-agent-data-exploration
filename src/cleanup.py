#!/usr/bin/env python3
"""
Clean up all deployed AgentCore resources.

Deletes:
- AgentCore Runtime
- ECR repository
- Code Interpreter instances
- IAM roles (optional, with --all flag)

Usage:
    export AWS_PROFILE=claude
    python -m src.cleanup           # Runtime + ECR only
    python -m src.cleanup --all     # Everything including IAM roles and Code Interpreters
"""

import argparse
import os
import sys

import boto3
from botocore.config import Config
from dotenv import load_dotenv

from src.config import AWS_REGION

ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(ENV_FILE)

AGENT_NAME = "multi-agent-data-explorer"


def delete_runtime():
    """Delete the AgentCore Runtime."""
    agent_id = os.getenv("AGENT_ID")
    if not agent_id:
        print("   ⚠️  AGENT_ID not found in .env, skipping Runtime deletion")
        return

    try:
        client = boto3.client("bedrock-agentcore-control", region_name=AWS_REGION)
        client.delete_agent_runtime(agentRuntimeId=agent_id)
        print(f"   ✅ Deleted AgentCore Runtime: {agent_id}")
    except Exception as e:
        print(f"   ⚠️  Could not delete Runtime: {e}")


def delete_ecr():
    """Delete the ECR repository."""
    try:
        ecr = boto3.client("ecr", region_name=AWS_REGION)
        ecr.delete_repository(repositoryName=AGENT_NAME, force=True)
        print(f"   ✅ Deleted ECR repository: {AGENT_NAME}")
    except Exception as e:
        print(f"   ⚠️  Could not delete ECR repo: {e}")


def delete_code_interpreters():
    """Delete Code Interpreter instances."""
    for env_key in ["DATASCIENTIST_CODE_INTERPRETER_ID", "DATAVISUALIZER_CODE_INTERPRETER_ID"]:
        ci_id = os.getenv(env_key)
        if not ci_id:
            continue
        try:
            client = boto3.client("bedrock-agentcore-control", region_name=AWS_REGION)
            client.delete_code_interpreter(codeInterpreterId=ci_id)
            print(f"   ✅ Deleted Code Interpreter: {ci_id}")
        except Exception as e:
            print(f"   ⚠️  Could not delete {ci_id}: {e}")


def delete_iam_roles():
    """Delete IAM roles created by the deployment scripts."""
    iam = boto3.client("iam", config=Config(read_timeout=1000))

    for role_name in ["AgentCoreMultiAgentRole", "CodeInterpreterExecutionRole"]:
        try:
            # Remove inline policies
            for p in iam.list_role_policies(RoleName=role_name).get("PolicyNames", []):
                iam.delete_role_policy(RoleName=role_name, PolicyName=p)
            # Detach managed policies
            for p in iam.list_attached_role_policies(RoleName=role_name).get("AttachedPolicies", []):
                iam.detach_role_policy(RoleName=role_name, PolicyArn=p["PolicyArn"])
            iam.delete_role(RoleName=role_name)
            print(f"   ✅ Deleted IAM role: {role_name}")
        except iam.exceptions.NoSuchEntityException:
            print(f"   ⚠️  Role {role_name} not found, skipping")
        except Exception as e:
            print(f"   ⚠️  Could not delete {role_name}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Clean up AgentCore resources")
    parser.add_argument("--all", action="store_true", help="Delete everything including IAM roles and Code Interpreters")
    args = parser.parse_args()

    print("🧹 Cleaning up AgentCore resources")
    print("=" * 50)

    print("\n📦 Deleting AgentCore Runtime...")
    delete_runtime()

    print("\n🐳 Deleting ECR repository...")
    delete_ecr()

    if args.all:
        print("\n💻 Deleting Code Interpreters...")
        delete_code_interpreters()

        print("\n🔐 Deleting IAM roles...")
        delete_iam_roles()

    print("\n🎉 Cleanup complete!")

    if not args.all:
        print("\nTip: Run with --all to also delete Code Interpreters and IAM roles")


if __name__ == "__main__":
    main()
