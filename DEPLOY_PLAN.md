# AgentCore Runtime Deployment Plan — MCP Server

## Goal

Deploy the multi-agent data exploration system to **Amazon Bedrock AgentCore Runtime** as an **MCP server**, exposing only the Supervisor agent as a single MCP tool that clients can call.

---

## Architecture

```
MCP Client (Claude Desktop / Strands Agent / any MCP client)
    │
    ▼ (MCP over Streamable HTTP)
AgentCore Runtime (MCP protocol, port 8000)
    │
    ▼
MCP Server (FastMCP)
    └── tool: "analyze_data" → Supervisor Agent
            ├── Data Engineer (local pandas @tools)
            ├── Data Scientist (AgentCore Code Interpreter)
            └── Visualizer (AgentCore Code Interpreter)
```

The MCP server exposes ONE tool (`analyze_data`) that accepts a natural language query and routes it through the Supervisor, which orchestrates the three sub-agents.

---

## Deployment Steps

### Step 1: Create IAM Execution Role (manual, no auto-generation)

Create `AgentCoreMultiAgentRole` with these policies:
- `AmazonBedrockFullAccess` (for model invocations)
- `AmazonBedrockAgentCoreRuntimeExecutionPolicy` (for AgentCore Runtime)
- Custom inline policy for Code Interpreter access:
  ```json
  {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": [
          "bedrock-agentcore:InvokeCodeInterpreter",
          "bedrock-agentcore:CreateCodeInterpreterSession",
          "bedrock-agentcore:DeleteCodeInterpreterSession"
        ],
        "Resource": "*"
      }
    ]
  }
  ```

Trust policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "bedrock-agentcore.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Script: `src/deploy_iam_role.py` — creates the role using boto3, stores ARN in `.env`.

### Step 2: Deploy Code Interpreter instances

Already implemented in `src/deploy_code_interpreter.py`. Must run before deployment. Stores IDs in `.env`.

### Step 3: Create the MCP Server entrypoint

New file: `src/mcp_server.py`

```python
from mcp.server.fastmcp import FastMCP
from src.agents.supervisor import create_supervisor_agent

mcp = FastMCP(host="0.0.0.0", stateless_http=True)

@mcp.tool()
def analyze_data(query: str) -> str:
    """
    Send a data analysis query to the multi-agent system.
    The Supervisor agent will delegate to specialist agents:
    - Data Engineer for cleaning/profiling
    - Data Scientist for ML/statistics
    - Visualizer for charts/plots
    """
    supervisor = create_supervisor_agent()
    result = supervisor(query)
    # Extract text from the agent response
    content = result.message.get("content", [])
    texts = [block["text"] for block in content if block.get("type") == "text"]
    return "\n".join(texts) if texts else str(result)

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

### Step 4: Package & Deploy to AgentCore Runtime

New file: `src/deploy_runtime.py`

Uses `bedrock-agentcore-starter-toolkit` to:
1. Configure the deployment (entrypoint, requirements, execution role, ECR, MCP protocol)
2. Build Docker image and push to ECR
3. Create AgentCore Runtime with MCP protocol

```python
from bedrock_agentcore_starter_toolkit import Runtime
from dotenv import load_dotenv
import os, time

load_dotenv()

region = os.getenv("REGION", "us-east-1")
execution_role_arn = os.getenv("EXECUTION_ROLE_ARN")

runtime = Runtime()

# Configure — NO auto_create_execution_role (we create it manually)
runtime.configure(
    entrypoint="src/mcp_server.py",
    auto_create_execution_role=False,
    execution_role_arn=execution_role_arn,
    auto_create_ecr=True,
    requirements_file="requirements.txt",
    region=region,
    protocol="MCP",
    agent_name="multi-agent-data-explorer",
)

# Launch (builds Docker image, pushes to ECR, creates Runtime)
result = runtime.launch()
print(f"Agent ARN: {result.agent_arn}")
print(f"Agent ID: {result.agent_id}")

# Wait for READY status
status = runtime.status().endpoint["status"]
while status not in ["READY", "CREATE_FAILED"]:
    time.sleep(15)
    status = runtime.status().endpoint["status"]
    print(f"Status: {status}")

print(f"Final status: {status}")
```

### Step 5: Verify deployment

Test with a simple MCP client that connects to the deployed endpoint:

```python
# src/test_remote.py
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from datetime import timedelta

async def main():
    agent_arn = "..."  # from deploy output
    region = "us-east-1"
    encoded_arn = agent_arn.replace(":", "%3A").replace("/", "%2F")
    url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    
    async with streamablehttp_client(url, {}, timeout=timedelta(seconds=300)) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"Tools: {[t.name for t in tools.tools]}")
            # Should show: ['analyze_data']

asyncio.run(main())
```

---

## New Files

| File | Purpose |
|---|---|
| `src/deploy_iam_role.py` | Creates IAM execution role |
| `src/mcp_server.py` | MCP server entrypoint (FastMCP wrapping Supervisor) |
| `src/deploy_runtime.py` | Packages and deploys to AgentCore Runtime |
| `src/test_remote.py` | Tests the deployed MCP endpoint |

## Updated Files

| File | Change |
|---|---|
| `requirements.txt` | Add `mcp`, `bedrock-agentcore`, `bedrock-agentcore-starter-toolkit` |
| `.env` | Add `EXECUTION_ROLE_ARN`, `AGENT_ARN` (after deploy) |

---

## Important Considerations

1. **Docker required**: The starter toolkit builds a Docker image locally and pushes to ECR. Docker must be running.
2. **Data files**: The `data/` directory with `housing.csv` must be included in the container image. The Data Engineer reads local files.
3. **Code Interpreter IDs**: Must be deployed BEFORE the Runtime deployment. The `.env` file with Code Interpreter IDs is baked into the container.
4. **Authentication**: For simplicity, we'll start with IAM auth (no Cognito). The MCP client uses AWS SigV4 signing. Can add OAuth/Cognito later.
5. **Cold start**: First invocation may take 30-60s due to container cold start. Subsequent calls are faster.
6. **Cost**: AgentCore Runtime charges per invocation + compute time. Code Interpreter sessions also incur charges.

---

## Deployment Sequence

```
1. aws sso login --profile claude
2. python -m src.deploy_iam_role          # Creates IAM role, saves ARN to .env
3. python -m src.deploy_code_interpreter  # Creates Code Interpreter instances
4. python -m src.deploy_runtime           # Builds container, deploys to AgentCore
5. python -m src.test_remote              # Verify MCP endpoint works
```

---

## Cleanup

```python
# src/cleanup.py
# Deletes: AgentCore Runtime, ECR repo, IAM role, Code Interpreter sessions
```
