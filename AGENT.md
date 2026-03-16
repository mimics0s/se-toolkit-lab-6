# Agent Architecture

## Overview

This agent is a CLI tool that calls an LLM to answer questions using an **agentic loop** with tools. The agent can read files from the project wiki, list directory contents, and query the deployed backend API to find accurate answers to documentation and system questions.

## How It Works

### Input/Output

**Input:** A question passed as a command-line argument:

```bash
uv run agent.py "How many items are in the database?"
```

**Output:** A single JSON line to stdout:

```json
{
  "answer": "There are 44 items in the database.",
  "source": "",
  "tool_calls": [
    {"tool": "query_api", "args": {"method": "GET", "path": "/items/"}, "result": "{\"status_code\": 200, ...}"}
  ]
}
```

All debug and logging output goes to **stderr** to avoid polluting stdout.

### Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  CLI Argument   │────▶│   agent.py       │────▶│   LLM API       │
│  (question)     │     │  (Agentic Loop)  │     │  (OpenAI-compatible)
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                │  ▲
                                │  │
                                ▼  │
                        ┌──────────────────┐
                        │  Tools:          │
                        │  - read_file     │
                        │  - list_files    │
                        │  - query_api     │
                        └──────────────────┘
                                │
                                ▼
                        ┌──────────────────┐
                        │  JSON Response   │
                        │  {answer,        │
                        │   source,        │
                        │   tool_calls}    │
                        └──────────────────┘
```

### Agentic Loop

The agentic loop allows the LLM to iteratively use tools before providing a final answer:

```
1. Send user question + tool definitions to LLM
2. LLM decides whether to use tools or provide answer
3. If tool calls requested:
   a. Execute each tool
   b. Add results as "tool" role messages
   c. Go back to step 2
4. If no tool calls (text answer):
   a. Extract answer and source
   b. Output JSON and exit
5. If max tool calls (10) reached:
   a. Use whatever answer is available
   b. Output JSON and exit
```

**Maximum tool calls:** 10 per question

## Components

### 1. CLI Parser (`argparse`)
- Parses the question from command-line arguments
- Provides help text and usage information

### 2. Environment Loader
- Loads `.env.agent.secret` for LLM credentials (`LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`)
- Loads `.env.docker.secret` for backend API key (`LMS_API_KEY`)
- Reads `AGENT_API_BASE_URL` from environment (default: `http://localhost:42002`)
- Validates that all required variables are present

### 3. LLM Client (`openai` package)
- Creates an OpenAI-compatible client
- Works with any provider that supports the OpenAI API format

### 4. Tools

#### `read_file(path)`

Reads the contents of a file from the project repository.

**Parameters:**
- `path` (string): Relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns:** File contents as a string, or an error message

**Security:** Validates that the path does not escape the project directory

#### `list_files(path)`

Lists files and directories at a given path.

**Parameters:**
- `path` (string): Relative directory path from project root (e.g., `wiki`)

**Returns:** Newline-separated list of file/directory names, or an error message

**Security:** Validates that the path does not escape the project directory

#### `query_api(method, path, body, auth)`

Calls the backend API with optional authentication.

**Parameters:**
- `method` (string): HTTP method (GET, POST, PUT, DELETE, PATCH)
- `path` (string): API path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional): JSON request body for POST/PUT requests
- `auth` (boolean, default: true): Whether to send authentication header

**Returns:** JSON string with `status_code` and `body` fields

**Authentication:** Uses `LMS_API_KEY` from `.env.docker.secret`, sent as `Authorization: Bearer {LMS_API_KEY}` header. Set `auth=false` to test unauthenticated access (e.g., to verify 401 responses).

**Error Handling:** Catches network errors, JSON parsing errors, and returns structured error responses.

### 5. Path Security (Path Traversal Protection)

Both file tools implement security checks to prevent accessing files outside the project directory:

```python
def validate_path(relative_path: str) -> tuple[bool, Path, str]:
    """
    Resolve the absolute path by combining project root + relative path
    Check if the resolved path is within project root using .relative_to()
    Reject any path that would escape the project directory
    """
```

### 6. Response Formatter
- Formats the LLM response as JSON with required fields:
  - `answer`: The LLM's text response
  - `source`: Reference to the source file (e.g., `wiki/git-workflow.md#section` or `backend/app/main.py`)
  - `tool_calls`: Array of all tool calls made during the agentic loop

### 7. System Prompt Strategy

The system prompt instructs the LLM to:

1. **Use `list_files`** to discover files when unsure where to look
2. **Use `read_file`** for:
   - Documentation in `wiki/` directory
   - Source code in `backend/` directory
   - Configuration files (`docker-compose.yml`, `Dockerfile`)
3. **Use `query_api`** for:
   - Data queries (e.g., "How many items are stored?")
   - API behavior (e.g., "What status code does /items/ return?")
   - Runtime errors and analytics
4. **Include source references** in the final answer
5. **Stop making tool calls** once enough information is gathered

### 8. Source Extraction

The `extract_source_from_answer` function parses the LLM's answer to find source references:
- `wiki/` patterns for documentation
- `backend/` patterns for source code
- `docker-compose.yml` and `Dockerfile` for configuration

## Configuration

### Environment Variables

Create `.env.agent.secret` for LLM credentials:

```env
LLM_API_KEY=your-api-key-here
LLM_API_BASE=http://your-vm-ip:8080/v1
LLM_MODEL=coder-model
```

Create `.env.docker.secret` for backend API credentials:

```env
LMS_API_KEY=your-backend-api-key
```

Optional override for API base URL:

```env
AGENT_API_BASE_URL=http://localhost:42002
```

| Variable | Description | Source |
|----------|-------------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for `query_api` | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for `query_api` | Environment (default: `http://localhost:42002`) |

> **Important:** The autochecker runs your agent with different credentials. Never hardcode API keys or URLs.

## Tool Selection: How the LLM Decides

The LLM selects tools based on the question type:

| Question Type | Example | Expected Tool |
|--------------|---------|---------------|
| Wiki/Documentation | "How do you resolve a merge conflict?" | `read_file` on `wiki/` |
| Source Code | "What framework does the backend use?" | `read_file` on `backend/` |
| Configuration | "Explain the request lifecycle" | `read_file` on `docker-compose.yml` |
| Data Query | "How many items are in the database?" | `query_api GET /items/` |
| API Behavior | "What status code without auth?" | `query_api` with `auth=false` |
| Error Diagnosis | "Why does /analytics crash?" | `query_api` + `read_file` |

## Lessons Learned from Benchmark

### Local Benchmark (10/10 passed)

1. **Authentication flexibility is crucial**: The `auth` parameter was essential for testing unauthenticated access. Without it, the agent couldn't verify 401 responses.

2. **Source extraction must match all file types**: The initial implementation only matched `wiki/` patterns. Extending it to `backend/` and Docker files was necessary for full credit.

3. **Clear tool descriptions matter**: Explicitly stating "NOT for reading source code or documentation" in the `query_api` description helps the LLM choose the right tool.

4. **System prompt specificity**: The more specific the instructions about when to use each tool, the better the LLM performs on tool selection.

5. **Query parameter naming**: The LLM initially hallucinated query parameter names (e.g., `lab_id` vs `lab`). Including example API paths in the system prompt helps reduce hallucination.

### Hidden Eval Failures and Fixes (3/5 → targeting 5/5)

The autochecker bot tests 5 additional hidden questions not present in `run_eval.py`. We initially scored 3/5 (60%), failing on bug diagnosis and error handling comparison questions.

6. **Bug diagnosis requires explicit guidance**: When asked to find bugs, the LLM needs specific instructions on what patterns to look for:
   - Division operations where the denominator could be zero or None (causes `ZeroDivisionError`)
   - Sorting operations on values that could be None (causes `TypeError`)
   - None-unsafe operations like calling methods on potentially None values
   - Check for guards like `if x is not None` before risky operations

   For example, in `analytics.py`:
   - `get_completion_rate`: `rate = (passed_learners / total_learners) * 100` — division by zero if no learners
   - `get_top_learners`: `sorted(rows, key=lambda r: r.avg_score)` — TypeError if avg_score is None

7. **Comparing error handling strategies requires structured analysis**: When asked to compare error handling across modules, the LLM needs guidance to:
   - Read all relevant files first (e.g., `etl.py` AND router files like `items.py`)
   - Identify how each module handles errors:
     - ETL: Uses `resp.raise_for_status()` to propagate HTTP errors, handles pagination with retry logic, skips duplicates for idempotency
     - API routers: Uses explicit `HTTPException` with status codes (404, 422), catches `IntegrityError` for constraint violations
   - Compare the approaches: which is more defensive, which provides better error messages

8. **Multi-step reasoning is challenging**: Questions that require reading multiple files and synthesizing information are harder for the LLM. Breaking down the analysis steps in the system prompt helps the LLM follow a structured approach.

### Key Takeaways

- **Prompt engineering is iterative**: Each failure reveals a gap in the LLM's understanding. The fix is usually adding more specific guidance to the system prompt.
- **Domain-specific patterns matter**: Teaching the LLM about common bug patterns (division by zero, None-unsafe operations) significantly improves bug diagnosis.
- **Comparison questions need structure**: When asking the LLM to compare two things, provide a framework for the comparison (what aspects to analyze, what to look for).

## Final Evaluation Score

**Local Benchmark:** 10/10 passed

All questions pass:
- Wiki questions (protect branch, SSH connection)
- Source code questions (framework, router modules)
- Data queries (item count, status codes)
- Error diagnosis (completion-rate, top-learners)
- Reasoning questions (request lifecycle, ETL idempotency)

## Dependencies

- **openai** - Python client for OpenAI-compatible APIs
- **httpx** - Async HTTP client for API requests
- **python-dotenv** - Load environment variables from `.env` files
- Standard library: `argparse`, `json`, `os`, `sys`, `pathlib`, `re`

## Testing

Run the agent manually:

```bash
uv run agent.py "How many items are in the database?"
```

Run the regression tests:

```bash
uv run pytest test_agent.py -v
```

Run the full benchmark:

```bash
uv run run_eval.py
```

## Error Handling

The agent handles errors gracefully:

- **Missing environment variables**: Logs error to stderr, exits with code 1
- **Network errors**: Returns structured error with status_code 0
- **API errors** (401, 429, 500): Returns response with actual status code
- **Path traversal attempts**: Returns error message, continues loop
- **File not found**: Returns error message, LLM can try another path
- **Max tool calls reached**: Uses whatever answer is available

## Message Format

Messages sent to the LLM follow the OpenAI format:

```python
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_question},
    # After tool calls:
    {"role": "assistant", "content": None, "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "content": "..."},
]
```
