# Task 2 Plan: The Documentation Agent

## Overview

This plan describes how to extend the Task 1 agent with tools (`read_file`, `list_files`) and an agentic loop that allows the LLM to iteratively query the project wiki before providing a final answer.

## Tool Schemas

### `read_file`

**Purpose:** Read the contents of a file from the project repository.

**Parameters:**
- `path` (string, required): Relative path from project root (e.g., `wiki/git-workflow.md`)

**Returns:** 
- Success: File contents as a string
- Error: Error message if file doesn't exist or path is invalid

**Security (Path Traversal Protection):**
- Resolve the full path using `Path.resolve()`
- Check that the resolved path starts with the project root directory
- Reject any path containing `..` that would escape the project directory
- Return an error message instead of raising an exception

**Function-calling schema:**
```python
{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read the contents of a file from the project repository",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
                }
            },
            "required": ["path"]
        }
    }
}
```

### `list_files`

**Purpose:** List files and directories at a given path in the project.

**Parameters:**
- `path` (string, required): Relative directory path from project root (e.g., `wiki`)

**Returns:**
- Success: Newline-separated list of file/directory names
- Error: Error message if path doesn't exist or is not a directory

**Security (Path Traversal Protection):**
- Same approach as `read_file`
- Resolve and validate the path before listing
- Prevent access to files outside project root

**Function-calling schema:**
```python
{
    "type": "function",
    "function": {
        "name": "list_files",
        "description": "List files and directories at a given path",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative directory path from project root (e.g., 'wiki')"
                }
            },
            "required": ["path"]
        }
    }
}
```

## Agentic Loop Implementation

### Loop Structure

```
1. Initialize messages list with system prompt + user question
2. Set tool_call_count = 0
3. Loop (max 10 iterations):
   a. Call LLM with messages + tool definitions
   b. If response has tool_calls:
      - Increment tool_call_count
      - For each tool_call:
        * Execute the tool function
        * Append result as {"role": "tool", "tool_call_id": ..., "content": ...}
      - Add assistant message with tool_calls to messages
      - Continue loop
   c. If response has no tool_calls (text answer):
      - This is the final answer
      - Extract answer and source
      - Break loop
4. Format and output JSON response
```

### Maximum Tool Calls

- Limit: 10 tool calls per question
- If limit is reached, use whatever answer is available
- Log warning to stderr when approaching limit

### Message Format

Messages sent to the LLM follow OpenAI format:

```python
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_question},
    # After tool calls:
    {"role": "assistant", "content": None, "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "content": "..."},
]
```

## Path Security Implementation

### Security Strategy

To prevent path traversal attacks (e.g., `../../../etc/passwd`):

1. **Define project root:** Use `Path(__file__).parent.resolve()` to get the absolute project root
2. **Resolve the requested path:** Combine project root + relative path, then call `.resolve()`
3. **Validate:** Check that the resolved path starts with the project root
4. **Reject invalid paths:** Return error message instead of accessing the file

### Implementation

```python
def validate_path(relative_path: str) -> tuple[bool, Path, str]:
    """
    Validate that a path is within the project directory.
    
    Returns:
        (is_valid, resolved_path, error_message)
    """
    project_root = Path(__file__).parent.resolve()
    requested_path = (project_root / relative_path).resolve()
    
    # Check for path traversal
    try:
        requested_path.relative_to(project_root)
        return True, requested_path, ""
    except ValueError:
        return False, requested_path, f"Error: Path '{relative_path}' is outside project directory"
```

## Updated agent.py Structure

### New Functions

1. **`get_tool_definitions()`** - Returns the list of tool schemas for the LLM
2. **`execute_tool(tool_name, args)`** - Executes a tool call and returns the result
3. **`validate_path(relative_path)`** - Security helper for path validation
4. **`run_agentic_loop(question)`** - Main loop that handles tool calls iteratively

### Modified Functions

1. **`call_llm()`** - Now accepts messages list and tools parameter
2. **`format_response()`** - Now includes source field and tool_calls history
3. **`main()`** - Calls agentic loop instead of single LLM call

### System Prompt Strategy

The system prompt should instruct the LLM to:

1. Use `list_files` to discover wiki files when unsure where to look
2. Use `read_file` to read specific files and find answers
3. Include a `source` field in the final answer referencing the wiki file and section anchor
4. Stop making tool calls once enough information is gathered

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

## Testing Strategy

### Test 1: Merge Conflict Question

**Question:** "How do you resolve a merge conflict?"

**Expected behavior:**
- LLM should call `read_file` with path containing `git-workflow.md`
- Source should reference `wiki/git-workflow.md`

**Assertions:**
- `tool_calls` contains at least one `read_file` call
- The `args.path` contains `git-workflow.md`
- `source` contains `wiki/git-workflow.md`

### Test 2: Wiki Files Question

**Question:** "What files are in the wiki?"

**Expected behavior:**
- LLM should call `list_files` with `path: "wiki"`
- Result should list wiki files

**Assertions:**
- `tool_calls` contains at least one `list_files` call
- The `args.path` is `"wiki"` or similar
- `result` contains expected filenames like `git-workflow.md`

## Acceptance Criteria Checklist

- [ ] `plans/task-2.md` exists with implementation plan
- [ ] `agent.py` defines `read_file` and `list_files` tool schemas
- [ ] Agentic loop executes tool calls and feeds results back
- [ ] `tool_calls` array is populated in output
- [ ] `source` field correctly identifies wiki section
- [ ] Tools have path traversal protection
- [ ] `AGENT.md` documents tools and agentic loop
- [ ] 2 regression tests exist and pass
- [ ] Git workflow followed (issue, branch, PR with `Closes #2`)
