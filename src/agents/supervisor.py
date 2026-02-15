"""
Supervisor Agent — orchestrates Data Engineer, Data Scientist, and Visualizer.
Uses the "Agents as Tools" pattern: each sub-agent is wrapped with @tool.
"""

import os

from strands import Agent, tool

from src.agents.data_engineer import create_data_engineer_agent
from src.agents.data_scientist import create_data_scientist_agent
from src.agents.visualizer import create_visualizer_agent
from src.config import MODEL_ID

SYSTEM_PROMPT = """You are a Supervisor agent that coordinates data exploration tasks. You have three specialist agents available as tools:

1. data_engineer — Call this for data cleaning, profiling, handling missing values, and data quality checks. This agent works with local CSV files.
2. data_scientist — Call this for training ML models, feature engineering, and statistical analysis. This agent executes Python code in a cloud sandbox.
3. visualizer — Call this for creating charts, plots, and visual summaries of data. This agent executes Python code in a cloud sandbox.

IMPORTANT WORKFLOW RULES:
- Always start with data_engineer to profile/clean data first.
- The data_scientist and visualizer agents run in sandboxed cloud environments and CANNOT access local files.
- When calling data_scientist or visualizer, you MUST include the actual data (CSV text or summary stats) in the task description so they can work with it.
- After data_engineer profiles or cleans data, extract the key information and pass it along to the next agent.

Example workflow for "analyze and predict house values":
1. Call data_engineer to profile data/housing.csv → get stats and missing value report
2. Call data_engineer to clean data → saves data/housing_clean.csv
3. Read the cleaning report, then call data_scientist with the data description and ask it to train a model
4. Call visualizer with data summary to create relevant charts

Always synthesize the final answer clearly, combining insights from all agents."""


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
        and saving cleaned CSVs. This agent has direct access to local CSV files.

        Args:
            task: A natural-language description of the data engineering task.
                  Include the file path (e.g., 'data/housing.csv').

        Returns:
            The Data Engineer agent's response as a string.
        """
        try:
            agent = create_data_engineer_agent()
            result = agent(task)
            return str(result)
        except Exception as exc:
            return f"[Data Engineer error] {exc}"

    @tool
    def data_scientist(task: str) -> str:
        """
        Delegate a data science task to the Data Scientist specialist agent.
        This agent runs code in a sandboxed cloud Code Interpreter.
        It CANNOT access local files — you must include data in the task description.

        Args:
            task: A natural-language description of the data science task.
                  MUST include the actual data (CSV text or summary) since
                  the agent cannot access local files.

        Returns:
            The Data Scientist agent's response as a string.
        """
        try:
            agent = create_data_scientist_agent()
            result = agent(task)
            return str(result)
        except Exception as exc:
            return f"[Data Scientist error] {exc}"

    @tool
    def visualizer(task: str) -> str:
        """
        Delegate a visualization task to the Visualization specialist agent.
        This agent runs code in a sandboxed cloud Code Interpreter.
        It CANNOT access local files — you must include data in the task description.

        Args:
            task: A natural-language description of the visualization task.
                  MUST include the actual data (CSV text or summary) since
                  the agent cannot access local files.

        Returns:
            The Visualizer agent's response as a string.
        """
        try:
            agent = create_visualizer_agent()
            result = agent(task)
            return str(result)
        except Exception as exc:
            return f"[Visualizer error] {exc}"

    return Agent(
        model=MODEL_ID,
        system_prompt=SYSTEM_PROMPT,
        tools=[data_engineer, data_scientist, visualizer],
    )
