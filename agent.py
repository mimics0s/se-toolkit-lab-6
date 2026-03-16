#!/usr/bin/env python3
"""
Agent CLI - Calls an LLM to answer questions using tools.

This agent has access to tools (read_file, list_files) that allow it to
navigate the project wiki and find answers to documentation questions.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON object with 'answer', 'source', and 'tool_calls' fields to stdout.
    All debug/logging output goes to stderr.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


# Maximum number of tool calls per question
MAX_TOOL_CALLS = 10


def load_env_vars() -> dict:
    """
    Load environment variables from .env files in the project root.

    Loads:
    - .env.agent.secret: LLM_API_KEY, LLM_API_BASE, LLM_MODEL
    - .env.docker.secret: LMS_API_KEY

    Returns:
        dict with api_key, api_base, model, lms_api_key, api_base_url

    Raises:
        SystemExit: If required variables are missing
    """
    # Find .env files in the project root (same directory as agent.py)
    script_dir = Path(__file__).parent
    agent_env_file = script_dir / ".env.agent.secret"
    docker_env_file = script_dir / ".env.docker.secret"

    # Load from files if they exist
    if agent_env_file.exists():
        load_dotenv(dotenv_path=agent_env_file, override=False)
    if docker_env_file.exists():
        load_dotenv(dotenv_path=docker_env_file, override=False)

    # Get LLM variables
    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL")

    # Get API variables
    lms_api_key = os.getenv("LMS_API_KEY")
    api_base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")

    # Validate LLM variables
    if not api_key:
        print("Error: LLM_API_KEY not found in environment or .env.agent.secret", file=sys.stderr)
        sys.exit(1)

    if not api_base:
        print("Error: LLM_API_BASE not found in environment or .env.agent.secret", file=sys.stderr)
        sys.exit(1)

    if not model:
        print("Error: LLM_MODEL not found in environment or .env.agent.secret", file=sys.stderr)
        sys.exit(1)

    return {
        "api_key": api_key,
        "api_base": api_base,
        "model": model,
        "lms_api_key": lms_api_key,
        "api_base_url": api_base_url
    }


def create_llm_client(api_key: str, api_base: str) -> OpenAI:
    """
    Create an OpenAI-compatible client for the LLM API.

    Args:
        api_key: API key for authentication
        api_base: Base URL of the API endpoint

    Returns:
        OpenAI client instance
    """
    return OpenAI(
        api_key=api_key,
        base_url=api_base
    )


def get_project_root() -> Path:
    """
    Get the absolute path to the project root directory.

    Returns:
        Path object pointing to the project root
    """
    return Path(__file__).parent.resolve()


def validate_path(relative_path: str) -> tuple[bool, Path, str]:
    """
    Validate that a path is within the project directory.

    Prevents path traversal attacks (e.g., ../../../etc/passwd).

    Args:
        relative_path: The path relative to project root

    Returns:
        Tuple of (is_valid, resolved_path, error_message)
    """
    project_root = get_project_root()
    
    # Combine and resolve the path
    requested_path = (project_root / relative_path).resolve()
    
    # Check if the resolved path is within project root
    try:
        requested_path.relative_to(project_root)
        return True, requested_path, ""
    except ValueError:
        return False, requested_path, f"Error: Path '{relative_path}' is outside project directory"


def read_file(path: str) -> str:
    """
    Read the contents of a file from the project repository.

    Args:
        path: Relative path from project root (e.g., 'wiki/git-workflow.md')

    Returns:
        File contents as a string, or an error message
    """
    print(f"Tool: read_file('{path}')", file=sys.stderr)
    
    # Validate path security
    is_valid, resolved_path, error = validate_path(path)
    if not is_valid:
        print(f"Security error: {error}", file=sys.stderr)
        return error
    
    # Check if file exists
    if not resolved_path.exists():
        error_msg = f"Error: File '{path}' does not exist"
        print(error_msg, file=sys.stderr)
        return error_msg
    
    # Check if it's a file (not a directory)
    if not resolved_path.is_file():
        error_msg = f"Error: '{path}' is not a file"
        print(error_msg, file=sys.stderr)
        return error_msg
    
    try:
        content = resolved_path.read_text(encoding="utf-8")
        print(f"Successfully read {path} ({len(content)} chars)", file=sys.stderr)
        return content
    except Exception as e:
        error_msg = f"Error reading file: {e}"
        print(error_msg, file=sys.stderr)
        return error_msg


def list_files(path: str) -> str:
    """
    List files and directories at a given path.

    Args:
        path: Relative directory path from project root (e.g., 'wiki')

    Returns:
        Newline-separated list of file/directory names, or an error message
    """
    print(f"Tool: list_files('{path}')", file=sys.stderr)
    
    # Validate path security
    is_valid, resolved_path, error = validate_path(path)
    if not is_valid:
        print(f"Security error: {error}", file=sys.stderr)
        return error
    
    # Check if path exists
    if not resolved_path.exists():
        error_msg = f"Error: Path '{path}' does not exist"
        print(error_msg, file=sys.stderr)
        return error_msg
    
    # Check if it's a directory
    if not resolved_path.is_dir():
        error_msg = f"Error: '{path}' is not a directory"
        print(error_msg, file=sys.stderr)
        return error_msg
    
    try:
        entries = sorted([entry.name for entry in resolved_path.iterdir()])
        result = "\n".join(entries)
        print(f"Successfully listed {path} ({len(entries)} entries)", file=sys.stderr)
        return result
    except Exception as e:
        error_msg = f"Error listing directory: {e}"
        print(error_msg, file=sys.stderr)
        return error_msg


def query_api(method: str, path: str, body: str = None, auth: bool = True) -> str:
    """
    Call the backend API with optional authentication.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        path: API path (e.g., '/items/', '/analytics/completion-rate')
        body: Optional JSON request body (for POST/PUT requests)
        auth: Whether to send authentication header (default: True)

    Returns:
        JSON string with 'status_code' and 'body' fields
    """
    import httpx

    print(f"Tool: query_api('{method}', '{path}', auth={auth})", file=sys.stderr)

    # Get configuration from environment
    base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    lms_api_key = os.getenv("LMS_API_KEY")

    # Build the URL
    url = f"{base_url}{path}"

    # Prepare headers with optional authentication
    headers = {}
    if auth and lms_api_key:
        headers["Authorization"] = f"Bearer {lms_api_key}"

    try:
        # Make the request synchronously
        with httpx.Client() as client:
            method_upper = method.upper()

            if method_upper == "GET":
                response = client.get(url, headers=headers)
            elif method_upper == "POST":
                json_body = json.loads(body) if body else None
                response = client.post(url, headers=headers, json=json_body)
            elif method_upper == "PUT":
                json_body = json.loads(body) if body else None
                response = client.put(url, headers=headers, json=json_body)
            elif method_upper == "DELETE":
                response = client.delete(url, headers=headers)
            elif method_upper == "PATCH":
                json_body = json.loads(body) if body else None
                response = client.patch(url, headers=headers, json=json_body)
            else:
                return json.dumps({
                    "status_code": 400,
                    "body": {"error": f"Unsupported HTTP method: {method}"}
                })

            # Parse response body
            try:
                response_body = response.json()
            except json.JSONDecodeError:
                response_body = response.text

            result = json.dumps({
                "status_code": response.status_code,
                "body": response_body
            })

            print(f"API returned status {response.status_code}", file=sys.stderr)
            return result

    except httpx.RequestError as e:
        error_msg = f"Error: Request failed - {str(e)}"
        print(error_msg, file=sys.stderr)
        return json.dumps({
            "status_code": 0,
            "body": {"error": str(e)}
        })
    except json.JSONDecodeError as e:
        error_msg = f"Error: Invalid JSON in request body - {str(e)}"
        print(error_msg, file=sys.stderr)
        return json.dumps({
            "status_code": 400,
            "body": {"error": f"Invalid JSON body: {str(e)}"}
        })
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(error_msg, file=sys.stderr)
        return json.dumps({
            "status_code": 0,
            "body": {"error": str(e)}
        })


def execute_tool(tool_name: str, args: dict) -> str:
    """
    Execute a tool call and return the result.

    Args:
        tool_name: Name of the tool to execute
        args: Arguments for the tool

    Returns:
        Tool result as a string
    """
    if tool_name == "read_file":
        return read_file(args.get("path", ""))
    elif tool_name == "list_files":
        return list_files(args.get("path", ""))
    elif tool_name == "query_api":
        return query_api(
            args.get("method", "GET"),
            args.get("path", ""),
            args.get("body"),
            args.get("auth", True)
        )
    else:
        error_msg = f"Error: Unknown tool '{tool_name}'"
        print(error_msg, file=sys.stderr)
        return error_msg


def get_tool_definitions() -> list[dict]:
    """
    Get the function-calling schemas for available tools.

    Returns:
        List of tool definitions for the LLM API
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a file from the project repository. Use this to read documentation files in the wiki/ directory, source code in backend/, or configuration files.",
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
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files and directories at a given path. Use this to explore the wiki/ directory structure or other directories in the project.",
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
        },
        {
            "type": "function",
            "function": {
                "name": "query_api",
                "description": "Call the backend API to query data or check system behavior. Use this for questions about: data in the database (e.g., item counts), API behavior (e.g., status codes), runtime errors, or analytics. NOT for reading source code or documentation.",
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
                        },
                        "auth": {
                            "type": "boolean",
                            "description": "Whether to send authentication header (default: true). Set to false to test unauthenticated access."
                        }
                    },
                    "required": ["method", "path"]
                }
            }
        }
    ]


def get_system_prompt() -> str:
    """
    Get the system prompt that instructs the LLM how to use tools.

    Returns:
        System prompt string
    """
    return """You are a documentation and system assistant for a software engineering lab.
You have access to three tools:
- list_files: List files in a directory. Use this to explore the project structure.
- read_file: Read the contents of a file. Use this to read:
  - Documentation in wiki/ directory
  - Source code in backend/ directory
  - Configuration files (docker-compose.yml, Dockerfile, etc.)
- query_api: Call the backend API. Use this for questions about:
  - Data in the database (e.g., "How many items are stored?")
  - API behavior (e.g., "What status code does /items/ return without auth?")
  - Runtime errors or analytics endpoints
  - Any question that requires querying the running system

The query_api tool has an optional `auth` parameter (default: true). Set auth=false to test
unauthenticated access and see what status code the API returns without credentials.

To answer questions:
1. For wiki/documentation questions → use read_file on wiki/ files
2. For source code questions → use read_file on backend/ or other source files
3. For configuration questions → use read_file on docker-compose.yml, Dockerfile, etc.
4. For data/API questions → use query_api to query the running backend
5. Use list_files to discover files when you're unsure where to look
6. In your final answer, include a source reference:
   - For wiki files: wiki/filename.md#section-anchor
   - For source code: backend/path/to/file.py
   - For config files: docker-compose.yml or Dockerfile

When asked to find bugs or risky code:
- Look for division operations (e.g., `a / b`) where the denominator could be zero or None
- Look for sorting operations (e.g., `sorted()`) on values that could be None
- Look for None-unsafe operations: calling methods on values that might be None, arithmetic with None
- Check if there are guards like `if x is not None` before risky operations
- When you find a risky operation, explain what error would occur (e.g., ZeroDivisionError, TypeError)

When asked to compare error handling strategies:
- Read all relevant files first (e.g., etl.py AND router files)
- Identify how each module handles errors:
  - Does it use try/except blocks? What exceptions are caught?
  - Does it raise HTTPException with specific status codes?
  - Does it return default/empty values on error?
  - Does it use assertions or validation?
- Compare the approaches: which is more defensive? Which provides better error messages?

Do not make up information. Only answer based on what you read from files or query from the API.
When you have enough information to answer, provide your final answer without using any tools."""


def call_llm(client: OpenAI, model: str, messages: list[dict], tools: list[dict] = None, force_tools: bool = True) -> dict:
    """
    Call the LLM API with messages and optional tool definitions.

    Args:
        client: OpenAI client instance
        model: Model name to use
        messages: List of message dicts (conversation history)
        tools: Optional list of tool definitions
        force_tools: If True, always send tools (some APIs require this)

    Returns:
        LLM response as a dict

    Raises:
        SystemExit: If the API call fails
    """
    try:
        # Prepare API call arguments
        api_args = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1500
        }
        
        # Add tools if provided (always send tools for OpenAI-compatible APIs)
        if tools and force_tools:
            api_args["tools"] = tools
        
        response = client.chat.completions.create(**api_args)

        # Extract the response
        choice = response.choices[0]
        message = choice.message
        
        result = {
            "content": message.content,
            "tool_calls": None
        }
        
        # Extract tool calls if present
        if hasattr(message, "tool_calls") and message.tool_calls:
            result["tool_calls"] = message.tool_calls
        
        return result

    except Exception as e:
        print(f"Error calling LLM API: {e}", file=sys.stderr)
        sys.exit(1)


def run_agentic_loop(client: OpenAI, model: str, question: str) -> dict:
    """
    Run the agentic loop to answer a question using tools.

    The loop:
    1. Sends the question to the LLM
    2. If LLM requests tool calls, execute them and feed results back
    3. Repeat until LLM provides a text answer or max tool calls reached

    Args:
        client: OpenAI client instance
        model: Model name to use
        question: User's question

    Returns:
        Dict with 'answer', 'source', and 'tool_calls' fields
    """
    # Initialize conversation with system prompt and user question
    messages = [
        {"role": "system", "content": get_system_prompt()},
        {"role": "user", "content": question}
    ]

    # Get tool definitions
    tool_definitions = get_tool_definitions()

    # Track all tool calls for the output
    all_tool_calls = []
    tool_call_count = 0

    print("Starting agentic loop...", file=sys.stderr)

    while tool_call_count < MAX_TOOL_CALLS:
        print(f"\n--- Iteration {tool_call_count + 1} ---", file=sys.stderr)

        # Call LLM
        response = call_llm(client, model, messages, tool_definitions)

        # Check if LLM made tool calls
        if response["tool_calls"]:
            # Add assistant message with tool calls to conversation FIRST
            # (before tool results, as per OpenAI format)
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": response["tool_calls"]
            })

            # Process each tool call
            for tool_call in response["tool_calls"]:
                tool_name = tool_call.function.name
                # Parse arguments (they come as JSON string)
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                print(f"LLM requested tool call: {tool_name}({args})", file=sys.stderr)

                # Execute the tool
                result = execute_tool(tool_name, args)

                # Record the tool call for output
                all_tool_calls.append({
                    "tool": tool_name,
                    "args": args,
                    "result": result
                })

                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })

                tool_call_count += 1
                print(f"Tool call {tool_call_count}/{MAX_TOOL_CALLS}", file=sys.stderr)

            # Continue loop to get LLM's next action
            continue

        # No tool calls - this is the final answer
        print("\nLLM provided final answer (no tool calls)", file=sys.stderr)

        answer = response["content"] if response["content"] else "I don't have enough information to answer that question."

        # Try to extract source from the answer
        source = extract_source_from_answer(answer)
        
        return {
            "answer": answer,
            "source": source,
            "tool_calls": all_tool_calls
        }
    
    # Max tool calls reached
    print(f"\nMax tool calls ({MAX_TOOL_CALLS}) reached", file=sys.stderr)
    
    # Use whatever answer we have - try to get it from the last response
    answer = response["content"] if response["content"] else "I reached the maximum number of tool calls without finding a complete answer."
    source = extract_source_from_answer(answer)
    
    return {
        "answer": answer,
        "source": source,
        "tool_calls": all_tool_calls
    }


def extract_source_from_answer(answer: str) -> str:
    """
    Try to extract a source reference from the answer.

    Looks for patterns like:
    - wiki/filename.md#anchor
    - See wiki/filename.md
    - Source: wiki/filename.md
    - backend/app/.../file.py

    Args:
        answer: The LLM's answer text

    Returns:
        Source reference string, or empty string if not found
    """
    import re

    # Look for wiki/... patterns
    wiki_pattern = r'(wiki/[\w\-/]+\.md(?:#[\w\-]+)?)'
    matches = re.findall(wiki_pattern, answer)

    if matches:
        # Return the first match
        return matches[0]

    # Look for backend/... patterns
    backend_pattern = r'(backend/[\w\-/]+\.py)'
    matches = re.findall(backend_pattern, answer)

    if matches:
        # Return the first match
        return matches[0]

    # Look for docker-compose.yml or Dockerfile
    docker_pattern = r'((?:docker-compose\.yml|Dockerfile))'
    matches = re.findall(docker_pattern, answer, re.IGNORECASE)

    if matches:
        return matches[0]

    return ""


def format_response(answer: str, source: str, tool_calls: list) -> dict:
    """
    Format the response as the required JSON structure.

    Args:
        answer: The LLM's text response
        source: Source reference (wiki file path)
        tool_calls: List of tool calls made

    Returns:
        dict with 'answer', 'source', and 'tool_calls' fields
    """
    return {
        "answer": answer,
        "source": source,
        "tool_calls": tool_calls
    }


def main():
    """Main entry point for the agent CLI."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Agent CLI - Ask questions and get JSON answers with tool usage"
    )
    parser.add_argument(
        "question",
        type=str,
        help="The question to ask the LLM"
    )
    args = parser.parse_args()

    # Load environment variables
    env_vars = load_env_vars()
    print(f"Using model: {env_vars['model']}", file=sys.stderr)

    # Create LLM client
    client = create_llm_client(env_vars["api_key"], env_vars["api_base"])

    # Run the agentic loop
    print("Running agentic loop...", file=sys.stderr)
    result = run_agentic_loop(client, env_vars["model"], args.question)

    # Output the response
    print(json.dumps(result))

    return 0


if __name__ == "__main__":
    sys.exit(main())
