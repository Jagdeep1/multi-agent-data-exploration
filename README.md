# Multi-Agent Data Exploration System

A multi-agent system built with **AWS Strands Agents SDK** where a Supervisor agent orchestrates three specialist agents to collaboratively explore, clean, analyze, and visualize data.

## Architecture

```
User ↔ Supervisor Agent
           ├── Data Engineer Agent   (data cleaning/profiling — pandas @tool functions)
           ├── Data Scientist Agent  (ML training — AgentCore Code Interpreter)
           └── Visualization Agent  (charts/plots — AgentCore Code Interpreter)
```

The Supervisor uses the **"Agents as Tools"** pattern: each sub-agent is wrapped with `@tool` and callable by the Supervisor.

## Project Structure

```
strands-multi-agent/
├── README.md
├── requirements.txt
├── data/
│   └── housing.csv              # Sample dataset (generated at startup)
├── src/
│   ├── __init__.py
│   ├── main.py                  # Entry point
│   ├── config.py                # AWS region, model config
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── supervisor.py        # Supervisor agent + orchestration
│   │   ├── data_engineer.py     # Data Engineer agent with custom @tool functions
│   │   ├── data_scientist.py    # Data Scientist agent with Code Interpreter
│   │   └── visualizer.py        # Visualization agent with Code Interpreter
│   └── utils/
│       ├── __init__.py
│       └── dataset.py           # Sample dataset generator
└── output/                      # Generated plots/reports
```

## Setup

```bash
# 1. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set AWS credentials
export AWS_PROFILE=claude
export AWS_REGION=us-east-1
aws sso login --profile claude   # if session expired

# 4. Generate sample dataset
python -m src.utils.dataset
```

## Usage

```bash
# Interactive mode
python -m src.main

# Single query
python -m src.main --query "Analyze the housing dataset and predict house values"
```

## Sample Queries

- `"Profile the housing dataset and check for data quality issues"`
- `"Clean the data and train a model to predict median house values"`
- `"Create visualizations showing the relationship between income and house values"`
- `"Give me a complete analysis: clean the data, build a prediction model, and visualize the results"`

## Agents

| Agent | Role | Tools |
|---|---|---|
| **Supervisor** | Orchestrates specialists | `data_engineer`, `data_scientist`, `visualizer` (sub-agents as tools) |
| **Data Engineer** | Profiling, cleaning, QA | `profile_data`, `check_missing`, `clean_data` (custom pandas @tools) |
| **Data Scientist** | EDA, ML training, metrics | AgentCore Code Interpreter |
| **Visualizer** | Charts, plots, heatmaps | AgentCore Code Interpreter |

## Notes

- **AgentCore Code Interpreter** requires AWS credentials with Bedrock and AgentCore permissions.
- The Data Engineer uses local pandas tools (no Code Interpreter) since it needs direct filesystem access.
- Cleaned data is saved to `data/housing_clean.csv`; plots land in `output/`.
