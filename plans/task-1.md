# Task 1 Plan: Call an LLM from Code

## LLM Provider

The agent will use an OpenAI-compatible API endpoint. The specific provider is configured via environment variables:

- `LLM_API_KEY` - API key for authentication
- `LLM_API_BASE` - Base URL of the API endpoint (e.g., `https://api.openai.com/v1` or a custom endpoint)
- `LLM_MODEL` - Model name to use (e.g., `qwen3-coder-plus`, `gpt-4o`, etc.)

This design allows the autochecker to inject its own LLM credentials during evaluation.

## Agent Architecture

### Components

1. **CLI Entry Point** (`agent.py`)
   - Parses command-line arguments to get the user's question
   - Loads environment variables from `.env.agent.secret`
   - Calls the LLM API
   - Formats and outputs the response as JSON

2. **LLM Client**
   - Uses the `openai` Python package (works with any OpenAI-compatible API)
   - Sends a chat completion request with the user's question
   - Receives and parses the response

3. **Response Formatter**
   - Extracts the answer from the LLM response
   - Outputs a JSON object with required fields:
     - `answer`: The LLM's text response
     - `tool_calls`: Empty array (will be populated in Task 2)

### Data Flow

```
User question (CLI arg) 
    → agent.py 
    → Load env vars (LLM_API_KEY, LLM_API_BASE, LLM_MODEL)
    → Create OpenAI client
    → Call chat.completions.create()
    → Parse response
    → Output JSON to stdout
```

## Error Handling

- Network errors: Catch and log to stderr, exit with code 1
- API errors (401, 429, 500): Log to stderr, exit with code 1
- Missing environment variables: Log to stderr, exit with code 1
- Invalid JSON output: Ensure valid JSON is always written to stdout

## Output Format

The agent outputs a single JSON line to stdout:

```json
{"answer": "Representational State Transfer.", "tool_calls": []}
```

All debug/logging output goes to stderr to avoid polluting stdout.

## Testing Strategy

Create one regression test that:
1. Runs `agent.py` as a subprocess with a test question
2. Parses the JSON output from stdout
3. Verifies that `answer` field exists and is non-empty
4. Verifies that `tool_calls` field exists and is an array

## Dependencies

- `openai` Python package - for calling the LLM API
- `python-dotenv` - for loading environment variables from `.env.agent.secret`
- Standard library: `argparse`, `json`, `os`, `sys`
