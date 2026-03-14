# Agent Architecture

## Overview

This agent is a CLI tool that calls an LLM to answer questions using an **agentic loop** with tools. The agent can read files from the project wiki and list directory contents to find accurate answers to documentation questions.

## How It Works

### Input/Output

**Input:** A question passed as a command-line argument:

```bash
uv run agent.py "How do you resolve a merge conflict?"
```

**Output:** A single JSON line to stdout:

```json
{
  "answer": "To resolve a merge conflict, edit the conflicting file to choose which changes to keep, then stage and commit the resolved file.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": "git-workflow.md\n..."},
    {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "..."}
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
                        │  (Wiki access)   │
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
- Loads `.env.agent.secret` from the project root
- Extracts `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`
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

### 5. Path Security (Path Traversal Protection)

Both tools implement security checks to prevent accessing files outside the project directory:

```python
def validate_path(relative_path: str) -> tuple[bool, Path, str]:
    project_root = Path(__file__).parent.resolve()
    requested_path = (project_root / relative_path).resolve()
    
    try:
        requested_path.relative_to(project_root)
        return True, requested_path, ""
    except ValueError:
        return False, requested_path, "Error: Path is outside project directory"
```

**How it works:**
1. Resolve the absolute path by combining project root + relative path
2. Use `.resolve()` to normalize the path (resolves `..` and symlinks)
3. Check if the resolved path is within the project root using `.relative_to()`
4. Reject any path that would escape the project directory

### 6. Response Formatter
- Formats the LLM response as JSON with required fields:
  - `answer`: The LLM's text response
  - `source`: Reference to the wiki file (e.g., `wiki/git-workflow.md#section`)
  - `tool_calls`: Array of all tool calls made during the agentic loop

### 7. System Prompt Strategy

The system prompt instructs the LLM to:

1. **Use `list_files`** to explore the `wiki/` directory when unsure where to look
2. **Use `read_file`** to read specific files and find answers
3. **Include a source reference** in the final answer (format: `wiki/filename.md#section-anchor`)
4. **Stop making tool calls** once enough information is gathered

Example system prompt:

```
You are a documentation assistant for a software engineering lab.
You have access to two tools:
- list_files: List files in a directory
- read_file: Read the contents of a file

To answer questions:
1. Use list_files to explore the wiki/ directory structure
2. Use read_file to read relevant files and find the answer
3. In your final answer, include:
   - The answer to the question
   - A source reference in format: wiki/filename.md#section-anchor

Do not make up information. Only answer based on what you read from files.
```

## Configuration

### Environment Variables

Create a `.env.agent.secret` file in the project root:

```bash
cp .env.agent.example .env.agent.secret
```

Edit `.env.agent.secret`:

```env
LLM_API_KEY=your-api-key-here
LLM_API_BASE=http://your-vm-ip:8080/v1
LLM_MODEL=qwen3-coder-plus
```

| Variable | Description |
|----------|-------------|
| `LLM_API_KEY` | API key for authentication with the LLM provider |
| `LLM_API_BASE` | Base URL of the OpenAI-compatible API endpoint |
| `LLM_MODEL` | Model name to use for completions |

## Dependencies

- **openai** - Python client for OpenAI-compatible APIs
- **python-dotenv** - Load environment variables from `.env` files
- Standard library: `argparse`, `json`, `os`, `sys`, `pathlib`, `re`

## Testing

Run the agent manually:

```bash
uv run agent.py "How do you resolve a merge conflict?"
```

Run the regression tests:

```bash
uv run pytest test_agent.py -v
```

## Error Handling

The agent handles errors gracefully:

- **Missing environment variables**: Logs error to stderr, exits with code 1
- **Network errors**: Logs error to stderr, exits with code 1
- **API errors** (401, 429, 500): Logs error to stderr, exits with code 1
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

## Example Tool Call Flow

```
User: "How do you resolve a merge conflict?"

1. Agent sends question to LLM with tool definitions
2. LLM responds: tool_call(list_files, {"path": "wiki"})
3. Agent executes list_files("wiki"), returns: "git-workflow.md\n..."
4. Agent sends tool result to LLM
5. LLM responds: tool_call(read_file, {"path": "wiki/git-workflow.md"})
6. Agent executes read_file("wiki/git-workflow.md"), returns file contents
7. Agent sends tool result to LLM
8. LLM responds with final answer (no tool calls)
9. Agent outputs JSON with answer, source, and tool_calls
```

## Future Extensions

Possible extensions for future tasks:

1. **More tools**: `query_api`, `search_code`, `run_tests`
2. **Memory**: Persist conversation history across questions
3. **Multi-file editing**: Tools to modify project files
4. **Enhanced security**: Sandboxed execution, permission levels
