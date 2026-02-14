"""
S3 utilities — helper functions and @tool wrappers for agent use.
"""

import json
import os

import boto3
from strands import tool

from src.config import AWS_REGION, S3_BUCKET, S3_PREFIX

_s3_client = None


def _get_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3", region_name=AWS_REGION)
    return _s3_client


def _full_key(relative_key: str) -> str:
    """Prepend S3_PREFIX to a relative key."""
    if S3_PREFIX:
        return f"{S3_PREFIX}/{relative_key}".replace("//", "/")
    return relative_key


# ---------------------------------------------------------------------------
# Helper functions (used by supervisor wrappers)
# ---------------------------------------------------------------------------

def download_from_s3(s3_key: str, local_path: str) -> None:
    """Download a single file from S3."""
    os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
    _get_client().download_file(S3_BUCKET, s3_key, local_path)


def upload_to_s3(local_path: str, s3_key: str) -> None:
    """Upload a single file to S3."""
    _get_client().upload_file(local_path, S3_BUCKET, s3_key)


def upload_directory_to_s3(local_dir: str, s3_key_prefix: str) -> list[str]:
    """Upload all files in a local directory to S3. Returns list of uploaded keys."""
    uploaded = []
    for root, _dirs, files in os.walk(local_dir):
        for fname in files:
            local_path = os.path.join(root, fname)
            relative = os.path.relpath(local_path, local_dir)
            s3_key = f"{s3_key_prefix}/{relative}".replace("//", "/")
            upload_to_s3(local_path, s3_key)
            uploaded.append(s3_key)
    return uploaded


# ---------------------------------------------------------------------------
# @tool functions (for agents to call directly)
# ---------------------------------------------------------------------------

@tool
def s3_download(s3_path: str, local_path: str) -> str:
    """
    Download a file from S3.

    Args:
        s3_path: S3 key relative to the configured prefix (e.g. "data/housing.csv").
        local_path: Local filesystem path to save the file to.

    Returns:
        A confirmation message with the download details.
    """
    try:
        full_key = _full_key(s3_path)
        download_from_s3(full_key, local_path)
        return json.dumps({"status": "ok", "s3_key": full_key, "local_path": local_path})
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})


@tool
def s3_upload(local_path: str, s3_path: str) -> str:
    """
    Upload a local file to S3.

    Args:
        local_path: Local filesystem path of the file to upload.
        s3_path: S3 key relative to the configured prefix (e.g. "output/plot.png").

    Returns:
        A confirmation message with the upload details.
    """
    try:
        full_key = _full_key(s3_path)
        upload_to_s3(local_path, full_key)
        return json.dumps({"status": "ok", "local_path": local_path, "s3_key": full_key})
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})


@tool
def s3_list(prefix: str) -> str:
    """
    List objects in S3 under a given prefix.

    Args:
        prefix: S3 key prefix relative to the configured prefix (e.g. "data/").

    Returns:
        A JSON list of object keys found under the prefix.
    """
    try:
        full_prefix = _full_key(prefix)
        client = _get_client()
        paginator = client.get_paginator("list_objects_v2")
        keys = []
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=full_prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return json.dumps({"status": "ok", "prefix": full_prefix, "keys": keys})
    except Exception as exc:
        return json.dumps({"status": "error", "error": str(exc)})
