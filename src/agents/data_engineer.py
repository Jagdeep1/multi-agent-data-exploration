"""
Data Engineer Agent — data profiling, cleaning, and quality checks.
Uses custom @tool functions backed by pandas (no Code Interpreter).
"""

import json
import os

import numpy as np
import pandas as pd
from strands import Agent, tool

from src.config import MODEL_ID, S3_ENABLED

SYSTEM_PROMPT = """You are a Data Engineer specialist. Your job is to:
- Profile datasets (column types, statistics, distributions)
- Identify and report missing values, duplicates, and outliers
- Clean data by filling missing values, removing duplicates, handling outliers
- Save cleaned data back for other agents to use

You work with CSV files in the data/ directory. Always report what you found and what you did.
Be concise and structured in your output."""

S3_PROMPT_ADDITION = """

You also have S3 tools available (s3_download, s3_upload, s3_list). Use them to download additional data from S3 or upload results directly. Data from S3 is also pre-downloaded to data/ automatically."""


@tool
def profile_data(file_path: str) -> str:
    """
    Read a CSV file and return a structured summary of its contents,
    including shape, dtypes, basic statistics, and missing-value counts.

    Args:
        file_path: Path to the CSV file to profile.

    Returns:
        A JSON-formatted string containing profiling information.
    """
    try:
        df = pd.read_csv(file_path)
        missing = df.isnull().sum().to_dict()
        missing_pct = (df.isnull().mean() * 100).round(2).to_dict()
        desc = df.describe().round(4).to_dict()

        result = {
            "file": file_path,
            "rows": int(df.shape[0]),
            "columns": int(df.shape[1]),
            "column_names": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "missing_counts": missing,
            "missing_pct": missing_pct,
            "statistics": desc,
        }
        return json.dumps(result, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


@tool
def check_missing(file_path: str) -> str:
    """
    Report missing value counts and percentages for each column in a CSV file.

    Args:
        file_path: Path to the CSV file to check.

    Returns:
        A JSON-formatted string with per-column missing value info.
    """
    try:
        df = pd.read_csv(file_path)
        report = {}
        for col in df.columns:
            n_missing = int(df[col].isnull().sum())
            pct = round(n_missing / len(df) * 100, 2)
            report[col] = {"missing_count": n_missing, "missing_pct": pct}
        return json.dumps(
            {"file": file_path, "total_rows": len(df), "missing_by_column": report},
            indent=2,
        )
    except Exception as exc:
        return json.dumps({"error": str(exc)})


@tool
def clean_data(file_path: str, output_path: str) -> str:
    """
    Clean a CSV dataset:
    - Fill numeric missing values with the column median.
    - Remove duplicate rows.
    - Cap extreme outliers at the 1st and 99th percentile.
    Save the cleaned data to output_path.

    Args:
        file_path: Path to the raw CSV file.
        output_path: Path where the cleaned CSV will be saved.

    Returns:
        A JSON-formatted cleaning report.
    """
    try:
        df = pd.read_csv(file_path)
        report: dict = {
            "input_file": file_path,
            "output_file": output_path,
            "original_rows": int(df.shape[0]),
        }

        # Fill numeric missing values with median
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        filled: dict = {}
        for col in numeric_cols:
            n_missing = int(df[col].isnull().sum())
            if n_missing > 0:
                median_val = df[col].median()
                df[col] = df[col].fillna(median_val)
                filled[col] = {"filled_count": n_missing, "fill_value": round(float(median_val), 4)}
        report["filled_missing"] = filled

        # Remove duplicates
        before_dedup = len(df)
        df = df.drop_duplicates()
        report["duplicates_removed"] = before_dedup - len(df)

        # Cap outliers at 1st / 99th percentile
        capped: dict = {}
        for col in numeric_cols:
            p1 = df[col].quantile(0.01)
            p99 = df[col].quantile(0.99)
            n_capped = int(((df[col] < p1) | (df[col] > p99)).sum())
            if n_capped > 0:
                df[col] = df[col].clip(lower=p1, upper=p99)
                capped[col] = {"capped_count": n_capped, "lower": round(float(p1), 4), "upper": round(float(p99), 4)}
        report["capped_outliers"] = capped

        report["cleaned_rows"] = int(df.shape[0])

        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        df.to_csv(output_path, index=False)

        return json.dumps(report, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def create_data_engineer_agent() -> Agent:
    """Instantiate and return the Data Engineer agent."""
    tools = [profile_data, check_missing, clean_data]
    system_prompt = SYSTEM_PROMPT

    if S3_ENABLED:
        from src.utils.s3 import s3_download, s3_list, s3_upload

        tools.extend([s3_download, s3_upload, s3_list])
        system_prompt += S3_PROMPT_ADDITION

    return Agent(
        model=MODEL_ID,
        system_prompt=system_prompt,
        tools=tools,
    )
