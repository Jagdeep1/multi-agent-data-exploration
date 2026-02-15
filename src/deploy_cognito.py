#!/usr/bin/env python3
"""
Create Amazon Cognito User Pool and App Client for AgentCore Runtime auth.

Creates:
1. Cognito User Pool (MultiAgentMCPPool)
2. App Client (MultiAgentMCPClient) with USER_PASSWORD_AUTH flow
3. Test user (testuser) with permanent password
4. Authenticates and saves tokens to .env

Usage:
    export AWS_PROFILE=claude
    python -m src.deploy_cognito
"""

import os
import sys

import boto3
from dotenv import load_dotenv

from src.config import AWS_REGION

ENV_FILE = os.path.join(os.path.dirname(__file__), "..", ".env")
POOL_NAME = "MultiAgentMCPPool"
CLIENT_NAME = "MultiAgentMCPClient"
TEST_USERNAME = "testuser"
TEST_PASSWORD = "MyPassword123!"


def cleanup_existing_pool():
    """Delete existing pool with same name if present."""
    client = boto3.client("cognito-idp", region_name=AWS_REGION)
    paginator = client.get_paginator("list_user_pools")
    for page in paginator.paginate(MaxResults=60):
        for pool in page["UserPools"]:
            if pool["Name"] == POOL_NAME:
                pool_id = pool["Id"]
                print(f"   🔄 Deleting existing pool: {pool_id}")
                client.delete_user_pool(UserPoolId=pool_id)
                return


def create_user_pool() -> dict:
    """Create Cognito User Pool, App Client, test user, and authenticate."""
    client = boto3.client("cognito-idp", region_name=AWS_REGION)

    # Clean up existing
    cleanup_existing_pool()

    # 1. Create User Pool
    print("   Creating User Pool...")
    pool_response = client.create_user_pool(
        PoolName=POOL_NAME,
        Policies={
            "PasswordPolicy": {
                "MinimumLength": 8,
                "RequireUppercase": True,
                "RequireLowercase": True,
                "RequireNumbers": True,
                "RequireSymbols": True,
            }
        },
        AutoVerifiedAttributes=[],
        MfaConfiguration="OFF",
    )
    pool_id = pool_response["UserPool"]["Id"]
    print(f"   ✅ User Pool created: {pool_id}")

    # 2. Create App Client
    print("   Creating App Client...")
    app_response = client.create_user_pool_client(
        UserPoolId=pool_id,
        ClientName=CLIENT_NAME,
        GenerateSecret=False,
        ExplicitAuthFlows=[
            "ALLOW_USER_PASSWORD_AUTH",
            "ALLOW_REFRESH_TOKEN_AUTH",
        ],
    )
    client_id = app_response["UserPoolClient"]["ClientId"]
    print(f"   ✅ App Client created: {client_id}")

    # 3. Create test user
    print(f"   Creating test user '{TEST_USERNAME}'...")
    client.admin_create_user(
        UserPoolId=pool_id,
        Username=TEST_USERNAME,
        TemporaryPassword="Temp123!@",
        MessageAction="SUPPRESS",
    )
    client.admin_set_user_password(
        UserPoolId=pool_id,
        Username=TEST_USERNAME,
        Password=TEST_PASSWORD,
        Permanent=True,
    )
    print(f"   ✅ Test user created")

    # 4. Authenticate to get tokens
    print("   Authenticating test user...")
    auth_response = client.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={
            "USERNAME": TEST_USERNAME,
            "PASSWORD": TEST_PASSWORD,
        },
    )
    auth_result = auth_response["AuthenticationResult"]
    bearer_token = auth_result["AccessToken"]
    refresh_token = auth_result["RefreshToken"]
    print("   ✅ Authentication successful")

    discovery_url = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{pool_id}/.well-known/openid-configuration"

    return {
        "pool_id": pool_id,
        "client_id": client_id,
        "discovery_url": discovery_url,
        "bearer_token": bearer_token,
        "refresh_token": refresh_token,
    }


def update_env(config: dict):
    """Add/update Cognito config in .env file."""
    env_keys = {
        "COGNITO_POOL_ID": config["pool_id"],
        "COGNITO_CLIENT_ID": config["client_id"],
        "COGNITO_DISCOVERY_URL": config["discovery_url"],
        "COGNITO_BEARER_TOKEN": config["bearer_token"],
        "COGNITO_REFRESH_TOKEN": config["refresh_token"],
    }

    lines = []
    found_keys = set()

    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as f:
            for line in f:
                key = line.split("=", 1)[0].strip()
                if key in env_keys:
                    lines.append(f"{key}={env_keys[key]}\n")
                    found_keys.add(key)
                else:
                    lines.append(line)

    for key, value in env_keys.items():
        if key not in found_keys:
            lines.append(f"{key}={value}\n")

    with open(ENV_FILE, "w") as f:
        f.writelines(lines)

    print(f"   ✅ Cognito config saved to {ENV_FILE}")


def main():
    print("🔐 Setting up Amazon Cognito for AgentCore Runtime Auth")
    print("=" * 55)
    print(f"   Region: {AWS_REGION}\n")

    config = create_user_pool()
    update_env(config)

    print(f"\n🎉 Cognito setup complete!")
    print(f"   Pool ID:       {config['pool_id']}")
    print(f"   Client ID:     {config['client_id']}")
    print(f"   Discovery URL: {config['discovery_url']}")
    print(f"\nNext steps:")
    print(f"  1. Deploy Code Interpreters: python -m src.deploy_code_interpreter")
    print(f"  2. Deploy to AgentCore:      python -m src.deploy_runtime")


if __name__ == "__main__":
    main()
