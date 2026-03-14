# Task 1: Call an LLM from Code

## LLM Provider

**Provider:** Qwen OpenAI-Compatible Proxy  
**Base URL:** `http://10.93.25.254:8080/v1`  
**Model:** `coder-model` (Qwen 3.5 Plus)

The proxy server exposes Qwen models through an OpenAI-compatible API endpoint, allowing us to use standard OpenAI client libraries.

## Agent Structure

The agent (`agent.py`) is a simple Python script with the following structure:

```
agent.py
├── Configuration Loading
│   └── Reads from .env.agent.secret (LLM_API_KEY, LLM_API_BASE, LLM_MODEL)
├── Input Handling
│   └── Accepts question from command line argument
├── LLM Client
│   └── OpenAI-compatible client with custom base URL
├── Request Processing
│   └── Sends chat completion request with 60s timeout
└── Output
    └── JSON response: {"answer": "...", "tool_calls": []}
```

### Components

1. **Configuration** - Environment variables loaded via `python-dotenv`
2. **CLI Interface** - Single positional argument for the question
3. **LLM Client** - `openai.OpenAI` client with custom `base_url`
4. **Error Handling** - All debug/output to stderr, clean JSON to stdout
5. **Timeout** - HTTP client configured with 60 second timeout

### Data Flow

```
User Input (CLI arg)
    ↓
Load Config (.env.agent.secret)
    ↓
Create OpenAI Client
    ↓
Send Chat Completion Request
    ↓
Parse Response
    ↓
Output JSON to stdout
```

## Files

| File | Purpose |
|------|---------|
| `agent.py` | Main agent script |
| `.env.agent.secret` | Configuration (API key, base URL, model) |
| `AGENT.md` | Documentation |
| `test_agent.py` | Regression tests |
