"""
Visualization Agent — creates charts and plots via AgentCore Code Interpreter.

The Code Interpreter must be deployed first via:
    python -m src.deploy_code_interpreter
"""

import os

from strands import Agent
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

DATAVISUALIZER_CODE_INTERPRETER_ID = os.getenv("DATAVISUALIZER_CODE_INTERPRETER_ID")

SYSTEM_PROMPT = """You are a Visualization specialist. Your job is to:
- Create informative charts and plots using matplotlib/seaborn
- Generate correlation heatmaps, distribution plots, scatter plots
- Describe what each visualization shows and what insights can be drawn

You have access to a Code Interpreter that can execute Python code.

IMPORTANT: The Code Interpreter runs in a sandboxed cloud environment. It does NOT have access to local files.
To work with data:
1. The data will be provided to you as CSV text in the task description. Embed it in your code using io.StringIO.
2. Install packages if needed: pip install matplotlib seaborn pandas numpy
3. Write complete, self-contained Python scripts with all imports.

When creating visualizations:
1. Use matplotlib and seaborn for professional-looking plots
2. Set figure size, titles, labels, and color schemes
3. Use plt.savefig() to save plots (they will be returned as output)
4. After creating each chart, describe what it shows and key insights
5. Create multiple plots when appropriate (e.g., heatmap + scatter + distribution)"""


def create_visualizer_agent() -> Agent:
    """Instantiate and return the Visualization agent."""
    code_interpreter_tool = AgentCoreCodeInterpreter(region=AWS_REGION)

    return Agent(
        model=MODEL_ID,
        system_prompt=SYSTEM_PROMPT,
        tools=[code_interpreter_tool.code_interpreter],
    )
