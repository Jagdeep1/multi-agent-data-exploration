"""
Supervisor Agent — orchestrates Data Engineer, Data Scientist, and Visualizer.
Uses the "Agents as Tools" pattern: each sub-agent is wrapped with @tool.
"""

import json
import os

from strands import Agent, tool

from src.agents.data_engineer import create_data_engineer_agent
from src.agents.data_scientist import create_data_scientist_agent
from src.agents.visualizer import create_visualizer_agent
from src.config import DATA_DIR, MODEL_ID, OUTPUT_DIR, S3_BUCKET, S3_ENABLED, S3_PREFIX

SYSTEM_PROMPT = """You are a Supervisor agent that coordinates data exploration tasks. You have three specialist agents available as tools:

1. data_engineer — Call this for data cleaning, profiling, handling missing values, and data quality checks.
2. data_scientist — Call this for training ML models, feature engineering, and statistical analysis. This agent can execute Python code.
3. visualizer — Call this for creating charts, plots, and visual summaries of data. This agent can execute Python code.

When the user asks a question:
1. Analyze what type of work is needed
2. Call the appropriate specialist(s) in the right order
3. Synthesize their responses into a clear final answer

Always start with data_engineer if the data hasn't been profiled yet. Pass relevant context between agents."""

S3_PROMPT_ADDITION = """

You also have S3 integration enabled. The S3 bucket is "{bucket}" with prefix "{prefix}".
- Use s3_download, s3_upload, s3_list tools for direct S3 operations.
- Data from S3 is automatically downloaded to data/ before agents run.
- Outputs from data_scientist and visualizer are automatically uploaded to S3 after they finish.
- The data_engineer agent also has direct S3 access via its own s3_download/s3_upload/s3_list tools.
"""


# ---------------------------------------------------------------------------
# S3 bridge helpers
# ---------------------------------------------------------------------------

def _s3_key(relative_path: str) -> str:
    """Build a full S3 key from a path relative to the project."""
    if S3_PREFIX:
        return f"{S3_PREFIX}/{relative_path}".replace("//", "/")
    return relative_path


def _ensure_data_local() -> None:
    """Download data files from S3 to DATA_DIR if they aren't already present."""
    if not S3_ENABLED:
        return

    from src.utils.s3 import download_from_s3

    import boto3
    client = boto3.client("s3")
    prefix = _s3_key("data/")
    paginator = client.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            s3_key = obj["Key"]
            # Derive local path: strip the S3_PREFIX to get relative path
            relative = s3_key
            if S3_PREFIX and relative.startswith(S3_PREFIX + "/"):
                relative = relative[len(S3_PREFIX) + 1:]
            local_path = os.path.join(relative)  # e.g. "data/housing.csv"
            if not os.path.exists(local_path):
                print(f"  [S3] Downloading s3://{S3_BUCKET}/{s3_key} → {local_path}")
                download_from_s3(s3_key, local_path)


def _upload_outputs_to_s3() -> list[str]:
    """Upload all files in OUTPUT_DIR to S3. Returns list of uploaded keys."""
    if not S3_ENABLED:
        return []

    from src.utils.s3 import upload_directory_to_s3

    s3_prefix = _s3_key("output/")
    uploaded = upload_directory_to_s3(OUTPUT_DIR, s3_prefix)
    for key in uploaded:
        print(f"  [S3] Uploaded → s3://{S3_BUCKET}/{key}")
    return uploaded


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

def create_supervisor_agent() -> Agent:
    """
    Build and return the Supervisor agent.
    Each sub-agent is lazily instantiated inside its @tool wrapper so that
    AgentCore sessions are only opened when needed.
    """

    @tool
    def data_engineer(task: str) -> str:
        """
        Delegate a data engineering task to the Data Engineer specialist agent.
        Use this for profiling datasets, checking missing values, cleaning data,
        and saving cleaned CSVs.

        Args:
            task: A natural-language description of the data engineering task.

        Returns:
            The Data Engineer agent's response as a string.
        """
        try:
            _ensure_data_local()
            agent = create_data_engineer_agent()
            result = agent(task)
            return str(result)
        except Exception as exc:
            return f"[Data Engineer error] {exc}"

    @tool
    def data_scientist(task: str) -> str:
        """
        Delegate a data science task to the Data Scientist specialist agent.
        Use this for EDA, feature engineering, ML model training (regression,
        classification), and reporting metrics.

        Args:
            task: A natural-language description of the data science task.

        Returns:
            The Data Scientist agent's response as a string.
        """
        try:
            _ensure_data_local()
            agent = create_data_scientist_agent()
            result = agent(task)
            response = str(result)
            uploaded = _upload_outputs_to_s3()
            if uploaded:
                response += f"\n\n[S3] Uploaded {len(uploaded)} file(s): {json.dumps(uploaded)}"
            return response
        except Exception as exc:
            return f"[Data Scientist error] {exc}"

    @tool
    def visualizer(task: str) -> str:
        """
        Delegate a visualization task to the Visualization specialist agent.
        Use this for creating charts, plots, heatmaps, and other visual
        summaries. Plots are saved to the output/ directory.

        Args:
            task: A natural-language description of the visualization task.

        Returns:
            The Visualizer agent's response as a string.
        """
        try:
            _ensure_data_local()
            agent = create_visualizer_agent()
            result = agent(task)
            response = str(result)
            uploaded = _upload_outputs_to_s3()
            if uploaded:
                response += f"\n\n[S3] Uploaded {len(uploaded)} file(s): {json.dumps(uploaded)}"
            return response
        except Exception as exc:
            return f"[Visualizer error] {exc}"

    tools = [data_engineer, data_scientist, visualizer]
    system_prompt = SYSTEM_PROMPT

    if S3_ENABLED:
        from src.utils.s3 import s3_download, s3_list, s3_upload

        tools.extend([s3_download, s3_upload, s3_list])
        system_prompt += S3_PROMPT_ADDITION.format(bucket=S3_BUCKET, prefix=S3_PREFIX)

    return Agent(
        model=MODEL_ID,
        system_prompt=system_prompt,
        tools=tools,
    )
