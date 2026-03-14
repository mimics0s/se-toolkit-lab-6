#!/usr/bin/env python3
"""
Agent script that calls LLM via OpenAI-compatible proxy.

Usage:
    uv run agent.py "your question here"

Output:
    JSON to stdout: {"answer": "...", "tool_calls": []}
    All debug/output to stderr
"""

import json
import sys
import os
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv


def log_debug(message: str) -> None:
    """Write debug message to stderr."""
    print(f"[DEBUG] {message}", file=sys.stderr)


def log_error(message: str) -> None:
    """Write error message to stderr."""
    print(f"[ERROR] {message}", file=sys.stderr)


def load_config() -> dict:
    """Load configuration from environment variables or .env.agent.secret file."""
    # First try to load from environment variables (for autochecker)
    config = {
        "api_key": os.getenv("LLM_API_KEY"),
        "api_base": os.getenv("LLM_API_BASE"),
        "model": os.getenv("LLM_MODEL"),
    }
    
    # If not set via environment, try to load from .env file (for local dev)
    if not all(config.values()):
        env_path = Path(__file__).parent / ".env.agent.secret"
        if env_path.exists():
            load_dotenv(env_path)
            config = {
                "api_key": os.getenv("LLM_API_KEY"),
                "api_base": os.getenv("LLM_API_BASE"),
                "model": os.getenv("LLM_MODEL"),
            }
    
    missing = [k for k, v in config.items() if not v]
    if missing:
        log_error(f"Missing required config: {', '.join(missing)}")
        sys.exit(1)
    
    return config


def call_lllm(question: str, config: dict) -> dict:
    """Call LLM and return response."""
    log_debug(f"Calling LLM with model: {config['model']}")
    log_debug(f"API Base: {config['api_base']}")
    log_debug(f"Question: {question}")
    
    client = OpenAI(
        api_key=config["api_key"],
        base_url=config["api_base"],
        timeout=60.0,
    )
    
    try:
        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "user", "content": question}
            ],
            temperature=0.7,
        )
        
        answer = response.choices[0].message.content
        tool_calls = []
        
        if response.choices[0].message.tool_calls:
            tool_calls = [
                {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
                for tc in response.choices[0].message.tool_calls
            ]
        
        log_debug(f"Response received, answer length: {len(answer) if answer else 0}")
        
        return {
            "answer": answer,
            "tool_calls": tool_calls,
        }
        
    except Exception as e:
        log_error(f"LLM call failed: {str(e)}")
        raise


def main() -> None:
    """Main entry point."""
    if len(sys.argv) != 2:
        log_error("Usage: uv run agent.py \"<question>\"")
        sys.exit(1)
    
    question = sys.argv[1]
    
    if not question.strip():
        log_error("Question cannot be empty")
        sys.exit(1)
    
    config = load_config()
    result = call_lllm(question, config)
    
    # Output clean JSON to stdout
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
