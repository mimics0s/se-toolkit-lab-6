#!/usr/bin/env python3
"""
Regression tests for agent.py

Tests verify that agent.py returns valid JSON with required fields.
"""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_output_is_valid_json():
    """Test that agent.py returns valid JSON output."""
    agent_path = Path(__file__).parent / "agent.py"
    
    if not agent_path.exists():
        print("SKIP: agent.py not found", file=sys.stderr)
        return
    
    env_file = Path(__file__).parent / ".env.agent.secret"
    if not env_file.exists():
        print("SKIP: .env.agent.secret not found, create from .env.agent.secret.example", file=sys.stderr)
        return
    
    result = subprocess.run(
        ["uv", "run", str(agent_path), "What is 2 + 2?"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    
    print(f"stdout: {result.stdout}", file=sys.stderr)
    print(f"stderr: {result.stderr}", file=sys.stderr)
    print(f"returncode: {result.returncode}", file=sys.stderr)
    
    assert result.returncode == 0, f"agent.py failed with code {result.returncode}: {result.stderr}"
    
    try:
        output = json.loads(result.stdout.strip())
    except json.JSONDecodeError as e:
        assert False, f"Output is not valid JSON: {e}\nOutput: {result.stdout}"
    
    assert "answer" in output, "Missing 'answer' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be a list"
    
    print("PASS: Output is valid JSON with required fields", file=sys.stderr)
    print(f"Answer preview: {output['answer'][:100]}...", file=sys.stderr)


def test_agent_empty_question_fails():
    """Test that agent.py fails with empty question."""
    agent_path = Path(__file__).parent / "agent.py"
    
    if not agent_path.exists():
        print("SKIP: agent.py not found", file=sys.stderr)
        return
    
    result = subprocess.run(
        ["uv", "run", str(agent_path), ""],
        capture_output=True,
        text=True,
        timeout=30,
    )
    
    assert result.returncode != 0, "agent.py should fail with empty question"
    print("PASS: Empty question correctly rejected", file=sys.stderr)


def test_agent_missing_args_fails():
    """Test that agent.py fails without arguments."""
    agent_path = Path(__file__).parent / "agent.py"
    
    if not agent_path.exists():
        print("SKIP: agent.py not found", file=sys.stderr)
        return
    
    result = subprocess.run(
        ["uv", "run", str(agent_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    
    assert result.returncode != 0, "agent.py should fail without arguments"
    print("PASS: Missing arguments correctly rejected", file=sys.stderr)


if __name__ == "__main__":
    print("Running regression tests for agent.py", file=sys.stderr)
    print("=" * 50, file=sys.stderr)
    
    try:
        test_agent_output_is_valid_json()
    except AssertionError as e:
        print(f"FAIL: test_agent_output_is_valid_json - {e}", file=sys.stderr)
        sys.exit(1)
    
    try:
        test_agent_empty_question_fails()
    except AssertionError as e:
        print(f"FAIL: test_agent_empty_question_fails - {e}", file=sys.stderr)
        sys.exit(1)
    
    try:
        test_agent_missing_args_fails()
    except AssertionError as e:
        print(f"FAIL: test_agent_missing_args_fails - {e}", file=sys.stderr)
        sys.exit(1)
    
    print("=" * 50, file=sys.stderr)
    print("All tests passed!", file=sys.stderr)
