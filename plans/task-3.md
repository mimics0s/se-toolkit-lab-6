# Task 3 Plan: The System Agent

## Overview

This plan describes how to extend the Task 2 agent with a new `query_api` tool that allows the LLM to query the deployed backend API. This enables the agent to answer questions about system facts (framework, ports, status codes) and data-dependent queries (item count, scores).

## Environment Variables

The agent must read all configuration from environment variables:

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for `query_api` auth | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for `query_api` (default: `http://localhost:42002`) | Optional, env var |

### Implementation Strategy

Update `load_env_vars()` to:
1. Load `.env.agent.secret` for LLM credentials (existing)
2. Load `.env.docker.secret` for `LMS_API_KEY`
3. Read `AGENT_API_BASE_URL` from environment with default `http://localhost:42002`

## New Tool: `query_api`

### Function Schema

```python
{
    "type": "function",
    "function": {
        "name": "query_api",
        "description": "Call the backend API to query data or check system behavior. Use this for questions about item counts, status codes, API errors, or any runtime data.",
        "parameters": {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "description": "HTTP method (GET, POST, PUT, DELETE, etc.)"
                },
                "path": {
                    "type": "string",
                    "description": "API path (e.g., '/items/', '/analytics/completion-rate')"
                },
                "body": {
                    "type": "string",
                    "description": "Optional JSON request body (for POST/PUT requests)"
                }
            },
            "required": ["method", "path"]
        }
    }
}
```

### Implementation

```python
def query_api(method: str, path: str, body: str = None) -> str:
    """
    Call the backend API with authentication.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        path: API path (e.g., '/items/')
        body: Optional JSON request body
        
    Returns:
        JSON string with 'status_code' and 'body' fields
    """
    import httpx
    
    base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    lms_api_key = os.getenv("LMS_API_KEY")
    
    url = f"{base_url}{path}"
    headers = {"Authorization": f"Bearer {lms_api_key}"}
    
    # Make the request
    async with httpx.AsyncClient() as client:
        if method.upper() == "GET":
            response = await client.get(url, headers=headers)
        elif method.upper() == "POST":
            response = await client.post(url, headers=headers, json=json.loads(body) if body else None)
        # ... handle other methods
    
    return json.dumps({
        "status_code": response.status_code,
        "body": response.json() if response.content else response.text
    })
```

### Authentication

- Use `LMS_API_KEY` from `.env.docker.secret`
- Send as `Authorization: Bearer {LMS_API_KEY}` header
- This is different from `LLM_API_KEY` (which authenticates with the LLM provider)

## Updated System Prompt

The system prompt must instruct the LLM when to use each tool:

```
You are a documentation and system assistant for a software engineering lab.
You have access to these tools:

- list_files: List files in a directory. Use this to explore the project structure.
- read_file: Read the contents of a file. Use this to read documentation in wiki/, 
  source code in backend/, or configuration files like docker-compose.yml.
- query_api: Call the backend API. Use this for questions about:
  - Data in the database (e.g., "How many items are stored?")
  - API behavior (e.g., "What status code does /items/ return without auth?")
  - Runtime errors (e.g., "Query /analytics/completion-rate for lab-99")

To answer questions:
1. For wiki/documentation questions → use read_file on wiki/ files
2. For source code questions → use read_file on backend/ files  
3. For data/API questions → use query_api to query the running backend
4. Include a source reference when applicable

Do not make up information. Only answer based on what you read or query.
```

## Implementation Steps

### Step 1: Update `load_env_vars()`

- Add loading of `.env.docker.secret` for `LMS_API_KEY`
- Add `AGENT_API_BASE_URL` with default value
- Return all config values for use in tools

### Step 2: Add `query_api` Tool

- Implement synchronous HTTP client (use `httpx` or `requests`)
- Handle authentication with `LMS_API_KEY`
- Return JSON string with `status_code` and `body`
- Add error handling for network failures

### Step 3: Update `get_tool_definitions()`

- Add `query_api` schema to the list of tools
- Write clear description so LLM knows when to use it

### Step 4: Update `execute_tool()`

- Add case for `query_api` tool
- Pass method, path, body arguments to the function

### Step 5: Update System Prompt

- Modify `get_system_prompt()` to include guidance on `query_api`
- Clarify when to use wiki tools vs API tool

### Step 6: Test and Iterate

- Run `uv run run_eval.py` to test against benchmark
- Fix failures one at a time
- Update plan with scores and iteration strategy

## Testing Strategy

### Test 1: Backend Framework Question

**Question:** "What framework does the backend use?"

**Expected behavior:**
- Agent should call `read_file` on backend source code (e.g., `backend/app/main.py`)
- Answer should contain "FastAPI"

**Assertions:**
- `tool_calls` contains `read_file`
- Not `query_api` (this is a static code question)

### Test 2: Database Item Count Question

**Question:** "How many items are in the database?"

**Expected behavior:**
- Agent should call `query_api` with `GET /items/`
- Answer should contain a number > 0

**Assertions:**
- `tool_calls` contains `query_api`
- `args.method` is "GET"
- `args.path` is "/items/"

## Benchmark Questions Analysis

| # | Question | Tool Required | Strategy |
|---|----------|---------------|----------|
| 0 | Wiki: protect branch on GitHub | `read_file` | Read wiki/git-workflow.md |
| 1 | Wiki: SSH connection steps | `read_file` | Read wiki SSH docs |
| 2 | Backend framework | `read_file` | Read backend/app/main.py |
| 3 | API router modules | `list_files` | List backend/app/routers/ |
| 4 | Item count in database | `query_api` | GET /items/ |
| 5 | Status code without auth | `query_api` | GET /items/ without header |
| 6 | /analytics/completion-rate error | `query_api` + `read_file` | Query API, then read source |
| 7 | /analytics/top-learners crash | `query_api` + `read_file` | Query API, then read source |
| 8 | Request lifecycle (docker-compose) | `read_file` | Read docker-compose.yml, Dockerfile |
| 9 | ETL pipeline idempotency | `read_file` | Read backend/app/etl.py |

## Initial Benchmark Results

*To be filled after first run of `uv run run_eval.py`*

- **Initial Score:** _/10
- **First Failures:**
  - Question #X: [description]
  - Question #Y: [description]

## Iteration Strategy

1. Run benchmark, note first failure
2. Debug by running agent manually with that question
3. Check stderr output to see tool calls
4. Fix issues:
   - Wrong tool selected → improve system prompt
   - Tool returns error → fix tool implementation
   - Answer doesn't match keywords → adjust phrasing
5. Re-run benchmark
6. Repeat until all pass

## Acceptance Criteria Checklist

- [ ] `plans/task-3.md` exists with implementation plan
- [ ] `agent.py` defines `query_api` tool schema
- [ ] `query_api` authenticates with `LMS_API_KEY`
- [ ] Agent reads all config from environment variables
- [ ] System prompt distinguishes wiki vs API tools
- [ ] `run_eval.py` passes all 10 questions
- [ ] 2 new regression tests added to `test_agent.py`
- [ ] `AGENT.md` updated with 200+ words documentation
- [ ] Git workflow followed (issue, branch, PR with `Closes #...`)
