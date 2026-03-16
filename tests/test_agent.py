"""
Regression tests for agent.py

These tests verify that the agent:
1. Outputs valid JSON
2. Includes required fields: 'answer' and 'tool_calls'
3. Runs successfully with a question argument
"""

import json
import subprocess
import sys
from pathlib import Path


def get_agent_path() -> Path:
    """Get the path to agent.py in the project root."""
    return Path(__file__).parent.parent / "agent.py"


def run_agent(question: str) -> tuple[str, str, int]:
    """
    Run the agent with a question and capture output.
    
    Args:
        question: The question to ask the agent
        
    Returns:
        Tuple of (stdout, stderr, return_code)
    """
    agent_path = get_agent_path()
    result = subprocess.run(
        [sys.executable, "-m", "uv", "run", str(agent_path), question],
        capture_output=True,
        text=True,
        timeout=60
    )
    return result.stdout, result.stderr, result.returncode


def test_agent_outputs_valid_json():
    """Test that the agent outputs valid JSON with required fields."""
    # Run the agent with a simple question
    stdout, stderr, return_code = run_agent("What is 2+2?")
    
    # Check that the agent exited successfully
    assert return_code == 0, f"Agent failed with stderr: {stderr}"
    
    # Parse the JSON output
    try:
        response = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {stdout}") from e
    
    # Check that 'answer' field exists and is non-empty
    assert "answer" in response, "Response missing 'answer' field"
    assert response["answer"], "Answer field is empty"
    assert isinstance(response["answer"], str), "Answer should be a string"
    
    # Check that 'tool_calls' field exists and is an array
    assert "tool_calls" in response, "Response missing 'tool_calls' field"
    assert isinstance(response["tool_calls"], list), "tool_calls should be an array"


def test_agent_handles_different_questions():
    """Test that the agent can handle different types of questions."""
    questions = [
        "What does API stand for?",
        "Explain what a REST API is in one sentence.",
    ]
    
    for question in questions:
        stdout, stderr, return_code = run_agent(question)
        
        # Check success
        assert return_code == 0, f"Agent failed for question '{question}': {stderr}"
        
        # Parse and validate response
        response = json.loads(stdout)
        assert "answer" in response, f"Missing 'answer' for question: {question}"
        assert "tool_calls" in response, f"Missing 'tool_calls' for question: {question}"
