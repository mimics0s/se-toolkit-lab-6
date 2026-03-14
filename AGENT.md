# Agent - LLM Call Script

A Python script that calls an LLM through an OpenAI-compatible proxy and returns structured JSON output.

## Overview

The agent sends a question to a Qwen model via a proxy server and returns the response in a standardized JSON format.

## Requirements

- Python 3.8+
- `uv` package manager (recommended) or `pip`

## Installation

### Using uv (recommended)

```bash
# Install dependencies
uv pip install openai python-dotenv
```

### Using pip

```bash
pip install openai python-dotenv
```

## Configuration

1. Copy the example environment file:

```bash
cp .env.agent.secret.example .env.agent.secret
```

2. Edit `.env.agent.secret` with your values:

```bash
# API Key for the proxy server
LLM_API_KEY=key1

# Base URL for the OpenAI-compatible proxy
LLM_API_BASE=http://10.93.25.254:8080/v1

# Model name to use
LLM_MODEL=coder-model
```

## Usage

Run the agent with a question as a command-line argument:

```bash
uv run agent.py "What is the capital of France?"
```

### Output

The agent outputs a single JSON line to stdout:

```json
{"answer": "The capital of France is Paris.", "tool_calls": []}
```

All debug and error messages are written to stderr.

## Output Format

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | The LLM's text response |
| `tool_calls` | array | Any tool calls made by the LLM (currently empty for simple queries) |

## Error Handling

- Missing config file → exits with error to stderr
- Missing environment variables → exits with error to stderr
- LLM API errors → exits with error to stderr
- Empty question → exits with error to stderr

## Timeout

The HTTP client has a 60-second timeout. If the LLM doesn't respond within this time, the request will fail.

## Example

```bash
$ uv run agent.py "Write a Python function to add two numbers"
{"answer": "Here's a simple Python function...\n\ndef add(a, b):\n    return a + b", "tool_calls": []}
```

## Files

| File | Purpose |
|------|---------|
| `agent.py` | Main agent script |
| `.env.agent.secret` | Configuration file (create from example) |
| `.env.agent.secret.example` | Example configuration template |
| `plans/task-1.md` | Task planning document |
| `test_agent.py` | Regression tests |
