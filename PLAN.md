# Multi-Agent Data Exploration System — Plan

## Overview

A multi-agent system using **AWS Strands Agents SDK** where a Supervisor agent orchestrates three specialist agents (Data Engineer, Data Scientist, Visualization) to collaboratively explore, clean, analyze, and visualize data. The Data Scientist and Visualization agents use **AWS AgentCore Code Interpreter** for sandboxed Python execution.

---

## Architecture

```
User ↔ Supervisor Agent
           ├── Data Engineer Agent (data cleaning/profiling)
           ├── Data Scientist Agent (ML training via Code Interpreter)
           └── Visualization Agent (charts/plots via Code Interpreter)
```

The Supervisor uses the **"Agents as Tools"** pattern — each sub-agent is wrapped with `@tool` and callable by the Supervisor.

---

## Project Structure

```
strands-multi-agent/
├── PLAN.md
├── README.md
├── requirements.txt
├── data/
│   └── housing.csv              # Sample dataset (generated at startup)
├── src/
│   ├── __init__.py
│   ├── main.py                  # Entry point — runs the Supervisor
│   ├── config.py                # AWS region, model config
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── supervisor.py        # Supervisor agent + orchestration
│   │   ├── data_engineer.py     # Data Engineer agent (@tool)
│   │   ├── data_scientist.py    # Data Scientist agent (@tool)
│   │   └── visualizer.py        # Visualization agent (@tool)
│   └── utils/
│       ├── __init__.py
│       └── dataset.py           # Sample dataset generator
└── output/                      # Generated plots/reports land here
```

---

## Dependencies (`requirements.txt`)

```
strands-agents>=0.1.0
strands-agents-tools>=0.1.0
bedrock-agentcore>=0.1.0
pandas>=2.0
scikit-learn>=1.3
boto3>=1.34
```

---

## Configuration (`config.py`)

```python
AWS_REGION = "us-east-1"
MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
DATA_DIR = "data"
OUTPUT_DIR = "output"
```

Use Bedrock as the model provider for all agents (cost-effective for demo).

---

## Sample Dataset

**California Housing Prices** (synthetic, generated via `sklearn.datasets.fetch_california_housing` or a simple synthetic generator). Saved as `data/housing.csv` with columns:

- MedInc, HouseAge, AveRooms, AveBedrms, Population, AveOccup, Latitude, Longitude, MedHouseVal
- Intentionally inject ~5% missing values and a few outliers for the Data Engineer to find.

---

## Agent Definitions

### 1. Supervisor Agent (`supervisor.py`)

**System Prompt:**
```
You are a Supervisor agent that coordinates data exploration tasks. You have three specialist agents available as tools:

1. data_engineer — Call this for data cleaning, profiling, handling missing values, and data quality checks.
2. data_scientist — Call this for training ML models, feature engineering, and statistical analysis. This agent can execute Python code.
3. visualizer — Call this for creating charts, plots, and visual summaries of data. This agent can execute Python code.

When the user asks a question:
1. Analyze what type of work is needed
2. Call the appropriate specialist(s) in the right order
3. Synthesize their responses into a clear final answer

Always start with data_engineer if the data hasn't been profiled yet. Pass relevant context between agents.
```

**Tools:** `[data_engineer, data_scientist, visualizer]` (the three sub-agent tools)

**Model:** Bedrock Claude Sonnet

### 2. Data Engineer Agent (`data_engineer.py`)

**System Prompt:**
```
You are a Data Engineer specialist. Your job is to:
- Profile datasets (column types, statistics, distributions)
- Identify and report missing values, duplicates, and outliers
- Clean data by filling missing values, removing duplicates, handling outliers
- Save cleaned data back for other agents to use

You work with CSV files in the data/ directory. Always report what you found and what you did.
Be concise and structured in your output.
```

**Tools:** Built-in file tools from strands_tools (file_read, file_write) + custom pandas-based tools:
- `profile_data(file_path: str) -> str` — reads CSV, returns summary stats
- `clean_data(file_path: str, output_path: str) -> str` — cleans and saves
- `check_missing(file_path: str) -> str` — reports missing values

**Note:** Does NOT use Code Interpreter. Uses custom `@tool` functions that run pandas locally.

### 3. Data Scientist Agent (`data_scientist.py`)

**System Prompt:**
```
You are a Data Scientist specialist. Your job is to:
- Perform exploratory data analysis
- Engineer features from existing data
- Train machine learning models (regression, classification)
- Evaluate model performance with metrics and cross-validation
- Report findings clearly with metrics

You have access to a Code Interpreter that can execute Python code. Use it to run pandas, scikit-learn, and numpy code. Read data from the data/ directory.
```

**Tools:** `[AgentCoreCodeInterpreter.code_interpreter]`

**Model:** Bedrock Claude Sonnet

### 4. Visualization Agent (`visualizer.py`)

**System Prompt:**
```
You are a Visualization specialist. Your job is to:
- Create informative charts and plots using matplotlib/seaborn
- Generate correlation heatmaps, distribution plots, scatter plots
- Save all plots to the output/ directory
- Describe what each visualization shows

You have access to a Code Interpreter that can execute Python code. Use matplotlib and seaborn. Always save plots as PNG files and describe what they show.
```

**Tools:** `[AgentCoreCodeInterpreter.code_interpreter]`

**Model:** Bedrock Claude Sonnet

---

## Data Flow

```
1. User: "Analyze this housing dataset and predict house values"

2. Supervisor → data_engineer("Profile the housing dataset at data/housing.csv")
   ← Returns: summary stats, missing values report

3. Supervisor → data_engineer("Clean the data, handle missing values, save to data/housing_clean.csv")
   ← Returns: cleaning report

4. Supervisor → data_scientist("Train a regression model to predict MedHouseVal using data/housing_clean.csv")
   ← Returns: model metrics (R², RMSE, feature importance)

5. Supervisor → visualizer("Create visualizations: correlation heatmap, feature importance plot, actual vs predicted scatter")
   ← Returns: descriptions of saved plots

6. Supervisor → User: Synthesized summary with findings, model performance, and generated visualizations
```

---

## Sample User Queries (Demo)

1. **"Profile the housing dataset and check for data quality issues"**
   → Supervisor delegates to Data Engineer

2. **"Clean the data and train a model to predict median house values"**
   → Supervisor chains: Data Engineer (clean) → Data Scientist (train)

3. **"Create visualizations showing the relationship between income and house values"**
   → Supervisor delegates to Visualization Agent

4. **"Give me a complete analysis: clean the data, build a prediction model, and visualize the results"**
   → Supervisor chains all three agents in sequence

---

## How to Run

```bash
# 1. Clone / enter project
cd strands-multi-agent

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set AWS credentials (SSO)
export AWS_PROFILE=claude
export AWS_REGION=us-east-1
aws sso login --profile claude  # if session expired

# 5. Generate sample dataset
python -m src.utils.dataset

# 6. Run the demo
python -m src.main
# This starts an interactive loop where you can type queries

# Or run with a specific query:
python -m src.main --query "Analyze the housing dataset and predict house values"
```

---

## Implementation Notes

- **AgentCore Code Interpreter** requires active AWS credentials with Bedrock permissions and AgentCore access.
- The Code Interpreter runs in a sandboxed environment — it cannot access local files directly. Data must be passed via the prompt or uploaded.
- For the demo, the Data Scientist and Visualization agents will include CSV data snippets in their prompts, or use Code Interpreter's file upload if supported.
- The Data Engineer uses local `@tool` functions (no Code Interpreter) since it needs direct file system access for reading/writing CSVs.
- All agents use `strands.Agent` with Bedrock model provider.
- Error handling: each tool agent wraps execution in try/except and returns error messages to the Supervisor for graceful degradation.

---

## Next Steps (after plan approval)

1. Implement `config.py` and `dataset.py`
2. Implement Data Engineer agent with custom tools
3. Implement Data Scientist agent with Code Interpreter
4. Implement Visualization agent with Code Interpreter
5. Implement Supervisor agent wiring everything together
6. Implement `main.py` with interactive loop
7. Test end-to-end flow
