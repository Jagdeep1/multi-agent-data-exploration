#!/usr/bin/env python3
"""
Create IAM execution role for AgentCore Runtime deployment.

Creates AgentCoreMultiAgentRole with permissions for:
- Bedrock model invocations
- AgentCore Runtime execution
- AgentCore Code Interpreter access
- ECR image pull
- CloudWatch logs

Usage:
    export AWS_PROFILE=claude
    python -m src.deploy_iam_role
"""

import json
import os
import time

import boto3
from botocore.config import Config
from dotenv import load_dotenv

from src.config import AWS_REGION

ROLE_NAME = "AgentCoreMultiAgentRole"
ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")


def get_account_id() -> str:
    sts = boto3.client("sts", config=Config(read_timeout=1000))
    return sts.get_caller_identity()["Account"]


def create_role(account_id: str) -> str:
    """Create or update the AgentCore Runtime execution role."""
    iam = boto3.client("iam", config=Config(read_timeout=1000))
    role_arn = f"arn:aws:iam::{account_id}:role/{ROLE_NAME}"

    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    permissions_policy = {
        "Version": "2012-10-17",
        "Statement": [
            # Bedrock model invocations
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:GetFoundationModel",
                    "bedrock:ListFoundationModels",
                ],
                "Resource": "*",
            },
            # AgentCore services (Runtime, Code Interpreter, etc.)
            {
                "Effect": "Allow",
                "Action": ["bedrock-agentcore:*"],
                "Resource": "*",
            },
            # ECR image pull (for container-based deployment)
            {
                "Effect": "Allow",
                "Action": [
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchCheckLayerAvailability",
                ],
                "Resource": "*",
            },
            # CloudWatch logs
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                ],
                "Resource": f"arn:aws:logs:*:{account_id}:*",
            },
            # S3 access for data and Code Interpreter
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                ],
                "Resource": [
                    f"arn:aws:s3:::sagemaker-*-{account_id}",
                    f"arn:aws:s3:::sagemaker-*-{account_id}/*",
                    f"arn:aws:s3:::bedrock-*-{account_id}",
                    f"arn:aws:s3:::bedrock-*-{account_id}/*",
                ],
            },
            # PassRole to self
            {
                "Effect": "Allow",
                "Action": ["iam:PassRole"],
                "Resource": role_arn,
            },
        ],
    }

    # Delete existing role if present
    try:
        iam.get_role(RoleName=ROLE_NAME)
        print(f"🔄 Found existing role {ROLE_NAME}, updating...")
        # Remove inline policies
        for p in iam.list_role_policies(RoleName=ROLE_NAME).get("PolicyNames", []):
            iam.delete_role_policy(RoleName=ROLE_NAME, PolicyName=p)
        # Detach managed policies
        for p in iam.list_attached_role_policies(RoleName=ROLE_NAME).get("AttachedPolicies", []):
            iam.detach_role_policy(RoleName=ROLE_NAME, PolicyArn=p["PolicyArn"])
        iam.delete_role(RoleName=ROLE_NAME)
        time.sleep(5)
    except iam.exceptions.NoSuchEntityException:
        print(f"🆕 Creating new role: {ROLE_NAME}")

    iam.create_role(
        RoleName=ROLE_NAME,
        AssumeRolePolicyDocument=json.dumps(trust_policy),
        Description="Execution role for AgentCore Runtime multi-agent data explorer",
    )
    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="AgentCoreMultiAgentPolicy",
        PolicyDocument=json.dumps(permissions_policy),
    )

    print(f"✅ Role created: {role_arn}")
    print("   ⏳ Waiting 15s for IAM propagation...")
    time.sleep(15)
    return role_arn


def update_env(role_arn: str):
    """Add/update EXECUTION_ROLE_ARN in .env file (preserves other entries)."""
    lines = []
    found = False

    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as f:
            for line in f:
                if line.startswith("EXECUTION_ROLE_ARN="):
                    lines.append(f"EXECUTION_ROLE_ARN={role_arn}\n")
                    found = True
                else:
                    lines.append(line)

    if not found:
        lines.append(f"EXECUTION_ROLE_ARN={role_arn}\n")

    with open(ENV_FILE, "w") as f:
        f.writelines(lines)

    print(f"✅ EXECUTION_ROLE_ARN saved to {ENV_FILE}")


def main():
    print("🚀 Creating AgentCore Runtime IAM Execution Role")
    print("=" * 50)

    account_id = get_account_id()
    print(f"AWS Account: {account_id}")
    print(f"Region: {AWS_REGION}\n")

    role_arn = create_role(account_id)
    update_env(role_arn)

    print(f"\n🎉 Done! Role ARN: {role_arn}")
    print("\nNext steps:")
    print("  1. Deploy Code Interpreters:  python -m src.deploy_code_interpreter")
    print("  2. Deploy to AgentCore:       python -m src.deploy_runtime")


if __name__ == "__main__":
    main()
