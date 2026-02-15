"""
Data Scientist Agent — ML model training and statistical analysis.
Uses AWS AgentCore Code Interpreter for sandboxed Python execution.

The Code Interpreter must be deployed first via:
    python -m src.deploy_code_interpreter

Config is loaded from .env (CODE_INTERPRETER_ID, S3_BUCKET, etc.).
"""

import os

from strands import Agent, tool
from strands_tools.code_interpreter import AgentCoreCodeInterpreter

from src.config import AWS_REGION, MODEL_ID

# Load .env if present
try:
    from dotenv import load_dotenv
    from pathlib import Path

    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

DATASCIENTIST_CODE_INTERPRETER_ID = os.getenv("DATASCIENTIST_CODE_INTERPRETER_ID")

SYSTEM_PROMPT = """You are a Data Scientist specialist. Your job is to:
- Perform exploratory data analysis
- Engineer features from existing data
- Train machine learning models (regression, classification)
- Evaluate model performance with metrics and cross-validation
- Report findings clearly with metrics

You have access to a Code Interpreter that can execute Python code. Use it to run pandas, scikit-learn, and numpy code.

IMPORTANT: The Code Interpreter runs in a sandboxed cloud environment. It does NOT have access to local files.
To work with data:
1. Read the CSV data and embed it directly in your Python code as a string literal or use the data provided in the task description.
2. Install packages if needed: pip install pandas scikit-learn numpy xgboost
3. Write complete, self-contained Python scripts with all imports.

When training models:
- Use scikit-learn for standard ML (RandomForest, GradientBoosting, LinearRegression)
- Report metrics clearly: R², RMSE, MAE for regression; accuracy, F1 for classification
- Include feature importance analysis
- Use cross-validation when appropriate"""


def create_data_scientist_agent() -> Agent:
    """Instantiate and return the Data Scientist agent."""
    code_interpreter_tool = AgentCoreCodeInterpreter(region=AWS_REGION)

    return Agent(
        model=MODEL_ID,
        system_prompt=SYSTEM_PROMPT,
        tools=[code_interpreter_tool.code_interpreter],
    )
