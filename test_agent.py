#!/usr/bin/env python3
"""
Regression tests for the Documentation Agent (Task 2).

These tests verify that the agent correctly uses tools (read_file, list_files)
and returns properly formatted JSON responses.

Usage:
    uv run pytest test_agent.py -v
"""

import json
import subprocess
import sys
from pathlib import Path


def run_agent(question: str) -> dict:
    """
    Run the agent with a question and parse the JSON output.

    Args:
        question: The question to ask the agent

    Returns:
        Parsed JSON response as a dict

    Raises:
        AssertionError: If the agent fails or returns invalid JSON
    """
    # Get the project root directory (parent of test file)
    project_root = Path(__file__).parent.resolve()
    
    # Run the agent as a subprocess using uv run
    result = subprocess.run(
        ["uv", "run", "agent.py", question],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=project_root
    )

    # Check that the agent didn't crash
    assert result.returncode == 0, f"Agent crashed with code {result.returncode}\nStderr: {result.stderr}"

    # Parse the JSON output (stdout should be a single JSON line)
    try:
        response = json.loads(result.stdout.strip())
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {e}\nStdout: {result.stdout}")

    return response


def test_merge_conflict_question():
    """
    Test that the agent uses read_file to answer a merge conflict question.

    Expected behavior:
    - Agent should call read_file with a path containing 'git-workflow.md'
    - Source should reference wiki/git-workflow.md or wiki/git.md
    """
    question = "How do you resolve a merge conflict?"
    print(f"\nRunning test: {question}", file=sys.stderr)

    response = run_agent(question)

    # Verify response structure
    assert "answer" in response, "Response missing 'answer' field"
    assert "source" in response, "Response missing 'source' field"
    assert "tool_calls" in response, "Response missing 'tool_calls' field"

    # Verify tool_calls is not empty (agent should have used tools)
    tool_calls = response["tool_calls"]
    assert len(tool_calls) > 0, "Expected agent to use at least one tool"

    # Verify that read_file was called with git-workflow.md
    # (The agent may also read other files, but git-workflow.md should be among them)
    read_file_calls = [
        tc for tc in tool_calls
        if tc.get("tool") == "read_file"
    ]
    assert len(read_file_calls) > 0, "Expected agent to call read_file"

    # Check that at least one read_file call has git-workflow.md in the path
    found_git_workflow = False
    for call in read_file_calls:
        path = call.get("args", {}).get("path", "")
        if "git-workflow.md" in path:
            found_git_workflow = True
            break

    assert found_git_workflow, (
        f"Expected read_file to be called with path containing 'git-workflow.md'. "
        f"Actual paths: {[tc.get('args', {}).get('path', '') for tc in read_file_calls]}"
    )

    # Verify source references a wiki file (should contain wiki/ and .md)
    source = response["source"]
    assert "wiki/" in source and ".md" in source, (
        f"Expected source to reference a wiki file (e.g., wiki/git.md), got: {source}"
    )

    # Verify answer is not empty
    assert len(response["answer"]) > 0, "Answer should not be empty"

    print(f"Test passed! Answer: {response['answer'][:100]}...", file=sys.stderr)
    print(f"Source: {source}", file=sys.stderr)
    print(f"Tool calls: {len(tool_calls)}", file=sys.stderr)


def test_wiki_files_question():
    """
    Test that the agent uses list_files to answer a wiki files question.

    Expected behavior:
    - Agent should call list_files with path "wiki" or similar
    - Result should contain expected wiki files
    """
    question = "What files are in the wiki?"
    print(f"\nRunning test: {question}", file=sys.stderr)

    response = run_agent(question)

    # Verify response structure
    assert "answer" in response, "Response missing 'answer' field"
    assert "source" in response, "Response missing 'source' field"
    assert "tool_calls" in response, "Response missing 'tool_calls' field"

    # Verify tool_calls is not empty
    tool_calls = response["tool_calls"]
    assert len(tool_calls) > 0, "Expected agent to use at least one tool"

    # Verify that list_files was called
    list_files_calls = [
        tc for tc in tool_calls
        if tc.get("tool") == "list_files"
    ]
    assert len(list_files_calls) > 0, "Expected agent to call list_files"

    # Check that at least one list_files call has "wiki" in the path
    found_wiki_path = False
    for call in list_files_calls:
        path = call.get("args", {}).get("path", "")
        if "wiki" in path.lower():
            found_wiki_path = True
            break

    assert found_wiki_path, (
        f"Expected list_files to be called with path containing 'wiki'. "
        f"Actual paths: {[tc.get('args', {}).get('path', '') for tc in list_files_calls]}"
    )

    # Verify that the result contains expected wiki files
    wiki_result = None
    for call in list_files_calls:
        path = call.get("args", {}).get("path", "")
        if "wiki" in path.lower():
            wiki_result = call.get("result", "")
            break

    assert wiki_result, "Expected list_files to return a result"
    assert "git-workflow.md" in wiki_result, (
        f"Expected wiki listing to contain 'git-workflow.md'. Got: {wiki_result[:200]}"
    )

    # Verify answer is not empty
    assert len(response["answer"]) > 0, "Answer should not be empty"

    print(f"Test passed! Answer: {response['answer'][:100]}...", file=sys.stderr)
    print(f"Wiki files found: {len(wiki_result.split())}", file=sys.stderr)
    print(f"Tool calls: {len(tool_calls)}", file=sys.stderr)


if __name__ == "__main__":
    # Run tests if executed directly
    import pytest
    pytest.main([__file__, "-v"])
