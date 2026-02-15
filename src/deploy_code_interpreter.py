#!/usr/bin/env python3
"""
Deploy AWS Bedrock Code Interpreter resources for Data Scientist and Visualizer agents.

Creates:
1. IAM execution role (CodeInterpreterExecutionRole) with S3, logs, Bedrock permissions
2. Two Code Interpreter instances (one for data scientist, one for visualizer)
3. Saves config to .env file

Usage:
    export AWS_PROFILE=claude
    python -m src.deploy_code_interpreter
"""

import json
import os
import time

import boto3
from botocore.config import Config

from src.config import AWS_REGION

INTERPRETERS = [
    {"name": "dataScientist", "description": "Code Interpreter for Data Scientist Agent"},
    {"name": "dataVisualizer", "description": "Code Interpreter for Visualization Agent"},
]
NETWORK_MODE = "PUBLIC"
ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")


def get_account_id() -> str:
    config = Config(read_timeout=1000)
    sts = boto3.client("sts", config=config)
    return sts.get_caller_identity()["Account"]


def create_execution_role(account_id: str) -> str:
    """Create or recreate the CodeInterpreterExecutionRole."""
    config = Config(read_timeout=1000)
    iam = boto3.client("iam", config=config)
    role_name = "CodeInterpreterExecutionRole"
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"

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
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                    "s3:CreateBucket",
                ],
                "Resource": [
                    f"arn:aws:s3:::sagemaker-*-{account_id}",
                    f"arn:aws:s3:::sagemaker-*-{account_id}/*",
                    f"arn:aws:s3:::bedrock-*-{account_id}",
                    f"arn:aws:s3:::bedrock-*-{account_id}/*",
                ],
            },
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
            {
                "Effect": "Allow",
                "Action": ["bedrock-agentcore:*"],
                "Resource": "*",
            },
            {
                "Effect": "Allow",
                "Action": ["iam:PassRole"],
                "Resource": role_arn,
            },
        ],
    }

    # Delete existing role if present
    try:
        iam.get_role(RoleName=role_name)
        print(f"🔄 Found existing role {role_name}, recreating...")
        # Remove inline policies
        for p in iam.list_role_policies(RoleName=role_name).get("PolicyNames", []):
            iam.delete_role_policy(RoleName=role_name, PolicyName=p)
        # Detach managed policies
        for p in iam.list_attached_role_policies(RoleName=role_name).get("AttachedPolicies", []):
            iam.detach_role_policy(RoleName=role_name, PolicyArn=p["PolicyArn"])
        iam.delete_role(RoleName=role_name)
    except iam.exceptions.NoSuchEntityException:
        print(f"🆕 Creating new role: {role_name}")

    iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(trust_policy),
        Description="Execution role for AWS Bedrock Code Interpreter",
    )
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="CodeInterpreterExecutionPolicy",
        PolicyDocument=json.dumps(permissions_policy),
    )
    print(f"✅ Role created: {role_arn}")
    print("   ⏳ Waiting 15s for IAM propagation...")
    time.sleep(15)
    return role_arn


def create_code_interpreter(name: str, description: str, execution_role_arn: str) -> str:
    """Create a Code Interpreter resource, deleting any existing one with same name."""
    config = Config(read_timeout=1000)
    client = boto3.client("bedrock-agentcore-control", region_name=AWS_REGION, config=config)

    # Clean up existing
    try:
        for ci in client.list_code_interpreters().get("codeInterpreterSummaries", []):
            if ci["name"] == name:
                print(f"   🔄 Deleting existing interpreter '{name}': {ci['codeInterpreterId']}")
                client.delete_code_interpreter(codeInterpreterId=ci["codeInterpreterId"])
                time.sleep(10)
                break
    except Exception as e:
        print(f"   ⚠️  Could not list interpreters: {e}")

    print(f"   Creating Code Interpreter '{name}'...")
    response = client.create_code_interpreter(
        name=name,
        description=description,
        executionRoleArn=execution_role_arn,
        networkConfiguration={"networkMode": NETWORK_MODE},
    )
    ci_id = response["codeInterpreterId"]
    print(f"   ✅ Created: {ci_id}")

    # Wait for READY
    for _ in range(60):
        status = client.get_code_interpreter(codeInterpreterId=ci_id)["status"]
        if status == "READY":
            print(f"   ✅ {name} is READY")
            return ci_id
        elif status == "CREATING":
            time.sleep(5)
        else:
            raise RuntimeError(f"Code Interpreter '{name}' failed with status: {status}")

    raise TimeoutError(f"Timeout waiting for '{name}' to be ready")


def save_env(interpreter_ids: dict, execution_role_arn: str, account_id: str):
    """Save configuration to .env file."""
    s3_bucket = f"sagemaker-{AWS_REGION}-{account_id}"
    lines = [
        "# Auto-generated by deploy_code_interpreter.py",
        f"REGION={AWS_REGION}",
        f"EXECUTION_ROLE_ARN={execution_role_arn}",
        f"S3_BUCKET={s3_bucket}",
        f"S3_PREFIX=strands-multi-agent",
    ]
    for name, ci_id in interpreter_ids.items():
        env_key = name.upper().replace("-", "_") + "_CODE_INTERPRETER_ID"
        lines.append(f"{env_key}={ci_id}")

    with open(ENV_FILE, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n✅ Config saved to {ENV_FILE}")
    for line in lines[1:]:
        print(f"   {line}")


def main():
    print("🚀 Deploying Bedrock Code Interpreter resources")
    print("=" * 50)

    account_id = get_account_id()
    print(f"AWS Account: {account_id}")
    print(f"Region: {AWS_REGION}\n")

    role_arn = create_execution_role(account_id)

    interpreter_ids = {}
    for interp in INTERPRETERS:
        ci_id = create_code_interpreter(interp["name"], interp["description"], role_arn)
        interpreter_ids[interp["name"]] = ci_id

    save_env(interpreter_ids, role_arn, account_id)

    # Quick test
    print("\n🧪 Testing Code Interpreters...")
    try:
        from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter

        for name, ci_id in interpreter_ids.items():
            code_client = CodeInterpreter(AWS_REGION)
            session_id = code_client.start(identifier=ci_id)
            print(f"   ✅ {name}: session started ({session_id})")
            code_client.stop()
    except Exception as e:
        print(f"   ⚠️  Test failed: {e}")

    print("\n🎉 Deployment complete!")
    print("\nNext steps:")
    print("  1. Generate dataset:  python -m src.utils.dataset")
    print("  2. Run the system:    python -m src.main")


if __name__ == "__main__":
    main()
