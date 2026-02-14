"""
Data Scientist Agent — ML model training and statistical analysis.
Uses AWS AgentCore Code Interpreter for sandboxed Python execution.
"""

from strands import Agent
from strands_tools.code_interpreter import AgentCoreCodeInterpreter

from src.config import AWS_REGION, MODEL_ID

SYSTEM_PROMPT = """You are a Data Scientist specialist. Your job is to:
- Perform exploratory data analysis
- Engineer features from existing data
- Train machine learning models (regression, classification)
- Evaluate model performance with metrics and cross-validation
- Report findings clearly with metrics

You have access to a Code Interpreter that can execute Python code. Use it to run pandas, scikit-learn, and numpy code. Read data from the data/ directory.

When you need to analyze data, write complete, self-contained Python scripts. Include all necessary imports. Report model metrics (R², RMSE, MAE, feature importances) clearly.

If S3 integration is enabled, input data is pre-downloaded to data/ before you run. Any files you save to output/ will be automatically uploaded to S3 after your execution completes. You do not need to interact with S3 directly."""


def create_data_scientist_agent() -> Agent:
    """Instantiate and return the Data Scientist agent."""
    code_interpreter_tool = AgentCoreCodeInterpreter(region=AWS_REGION)
    return Agent(
        model=MODEL_ID,
        system_prompt=SYSTEM_PROMPT,
        tools=[code_interpreter_tool.code_interpreter],
    )
