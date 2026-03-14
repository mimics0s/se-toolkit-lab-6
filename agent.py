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
    Load environment variables from .env.agent.secret in the project root.

    Returns:
        dict with LLM_API_KEY, LLM_API_BASE, LLM_MODEL

    Raises:
        SystemExit: If required variables are missing
    """
    # Find .env.agent.secret in the project root (same directory as agent.py)
    script_dir = Path(__file__).parent
    env_file = script_dir / ".env.agent.secret"

    # Load from file if it exists
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)

    # Get required variables
    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL")

    # Validate
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
        "model": model
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
                "description": "Read the contents of a file from the project repository. Use this to read documentation files in the wiki/ directory.",
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
                "description": "List files and directories at a given path. Use this to explore the wiki/ directory structure.",
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
    ]


def get_system_prompt() -> str:
    """
    Get the system prompt that instructs the LLM how to use tools.

    Returns:
        System prompt string
    """
    return """You are a documentation assistant for a software engineering lab.
You have access to two tools:
- list_files: List files in a directory
- read_file: Read the contents of a file

To answer questions:
1. Use list_files to explore the wiki/ directory structure if you're unsure where to look
2. Use read_file to read relevant files and find the answer
3. In your final answer (when you stop using tools), include:
   - The answer to the question
   - A source reference in format: wiki/filename.md#section-anchor

Do not make up information. Only answer based on what you read from files.
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
