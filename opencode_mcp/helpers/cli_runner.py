from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from opencode_mcp.errors import (
    OpencodeBinaryNotFoundError,
    OpencodeTimeoutError,
    OpencodeProtocolError,
    OpencodeValidationError,
)


def _resolve_binary(name: str, install_hint: str) -> str:
    """Resolve a binary to its full path, raising OpencodeBinaryNotFoundError if missing."""
    path = shutil.which(name)
    if path is None:
        raise OpencodeBinaryNotFoundError(
            f"{name} CLI not found on PATH. Install: {install_hint}"
        )
    return path


def run_gemini_prompt(
    prompt: str,
    model: str | None = None,
    timeout: float = 120.0,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """
    Run a one-shot prompt through the Gemini CLI.

    Invokes: gemini -p <prompt> --yolo --output-format json [-m <model>]
    Returns parsed response text and metadata from JSON output.
    """
    binary = _resolve_binary("gemini", "npm install -g @google/gemini-cli")
    cmd = [binary, "-p", prompt, "--yolo", "--output-format", "json"]
    if model:
        cmd += ["-m", model]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            cwd=project_dir,
        )
    except subprocess.TimeoutExpired as error:
        raise OpencodeTimeoutError(
            message=f"gemini CLI timed out after {timeout}s"
        ) from error

    if result.returncode != 0:
        raise OpencodeValidationError(
            message=f"gemini CLI exited with code {result.returncode}",
            detail={"stderr": result.stderr[:500]},
            recoverable=True,
            suggestion="Check GEMINI_API_KEY is set and the model name is valid.",
        )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise OpencodeProtocolError(
            message="gemini CLI returned unexpected non-JSON output",
            detail={"raw": result.stdout[:500]},
            recoverable=False,
            suggestion="Ensure gemini CLI version >= 0.36.0 supports --output-format json.",
        ) from error

    return {
        "response": data.get("response", ""),
        "model": _extract_gemini_model(data),
        "session_id": data.get("session_id", ""),
    }


def run_qwen_prompt(
    prompt: str,
    model: str | None = None,
    timeout: float = 120.0,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """
    Run a one-shot prompt through the Qwen Code CLI.

    Invokes: qwen <prompt> --yolo --output-format json [-m <model>]
    Returns parsed response text and metadata from JSON output.
    """
    binary = _resolve_binary("qwen", "npm install -g @qwen-code/qwen-code")
    cmd = [binary, prompt, "--yolo", "--output-format", "json"]
    if model:
        cmd += ["-m", model]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            cwd=project_dir,
        )
    except subprocess.TimeoutExpired as error:
        raise OpencodeTimeoutError(
            message=f"qwen CLI timed out after {timeout}s"
        ) from error

    if result.returncode != 0:
        raise OpencodeValidationError(
            message=f"qwen CLI exited with code {result.returncode}",
            detail={"stderr": result.stderr[:500]},
            recoverable=True,
            suggestion="Check DASHSCOPE_API_KEY is set and the model name is valid.",
        )

    try:
        events: list[dict[str, Any]] = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise OpencodeProtocolError(
            message="qwen CLI returned unexpected non-JSON output",
            detail={"raw": result.stdout[:500]},
            recoverable=False,
            suggestion="Ensure qwen CLI version >= 0.14.0 supports --output-format json.",
        ) from error

    return _parse_qwen_events(events)


def _extract_gemini_model(data: dict[str, Any]) -> str:
    """Extract model name from gemini JSON stats block."""
    models = data.get("stats", {}).get("models", {})
    return next(iter(models), "")


def _parse_qwen_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Extract response text, model, and session_id from qwen --output-format json event stream.
    The stream is a list of typed events; we pull from the 'result' and 'assistant' events.
    """
    response_text = ""
    model_name = ""
    session_id = ""

    for event in events:
        event_type = event.get("type")
        if event_type == "result":
            response_text = event.get("result", "")
            session_id = event.get("session_id", "")
        if event_type == "assistant":
            session_id = session_id or event.get("session_id", "")
            model_name = model_name or event.get("message", {}).get("model", "")

    return {"response": response_text, "model": model_name, "session_id": session_id}
