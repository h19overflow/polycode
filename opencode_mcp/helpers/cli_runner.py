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


def _run_subprocess(cmd: list[str], timeout: float, project_dir: str | None, cli_name: str) -> subprocess.CompletedProcess[str]:
    """Run a CLI subprocess, converting common errors to typed OpencodeErrors."""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            cwd=project_dir,
        )
    except subprocess.TimeoutExpired as error:
        raise OpencodeTimeoutError(
            message=f"{cli_name} CLI timed out after {timeout}s"
        ) from error


def _assert_zero_exit(result: subprocess.CompletedProcess[str], cli_name: str, auth_hint: str) -> None:
    """Raise OpencodeValidationError if the subprocess exited non-zero."""
    if result.returncode != 0:
        stderr = result.stderr.strip()
        is_auth = any(w in stderr.lower() for w in ("auth", "key", "login", "credential", "token", "unauthorized", "403", "401"))
        raise OpencodeValidationError(
            message=f"{cli_name} CLI exited with code {result.returncode}",
            detail={"stderr": stderr[:500]},
            recoverable=True,
            suggestion=auth_hint if is_auth else f"Run '{cli_name} --help' or check your API key.",
        )


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

def run_gemini_prompt(
    prompt: str,
    model: str | None = None,
    timeout: float = 120.0,
    project_dir: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    Run a prompt through the Gemini CLI.

    If session_id is provided, resumes that session (--resume <id>).
    Otherwise starts a fresh session.
    Returns: { response, model, session_id }
    """
    binary = _resolve_binary("gemini", "npm install -g @google/gemini-cli")
    cmd = [binary, "-p", prompt, "--yolo", "--output-format", "json"]
    if model:
        cmd += ["-m", model]
    if session_id:
        cmd += ["--resume", session_id]

    result = _run_subprocess(cmd, timeout, project_dir, "gemini")
    _assert_zero_exit(result, "gemini", "Run `gemini` interactively to authenticate, or set GEMINI_API_KEY.")

    try:
        data: dict[str, Any] = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise OpencodeProtocolError(
            message="gemini CLI returned unexpected non-JSON output",
            detail={"raw": result.stdout[:500]},
            recoverable=False,
            suggestion="Ensure gemini CLI >= 0.36.0 and use --output-format json.",
        ) from error

    return {
        "response": data.get("response", ""),
        "model": _extract_gemini_model(data),
        "session_id": data.get("session_id", ""),
    }


def check_gemini_auth(timeout: float = 15.0) -> dict[str, Any]:
    """
    Check Gemini CLI authentication status by running a minimal probe.
    Returns: { authenticated: bool, method: str, detail: str }
    """
    binary = _resolve_binary("gemini", "npm install -g @google/gemini-cli")
    # Gemini has no `auth status` subcommand — probe with a minimal prompt
    result = _run_subprocess(
        [binary, "-p", "hi", "--yolo", "--output-format", "json"],
        timeout, None, "gemini",
    )
    if result.returncode != 0:
        return {
            "authenticated": False,
            "method": "unknown",
            "detail": result.stderr.strip()[:300] or "Non-zero exit. Set GEMINI_API_KEY or run `gemini` to authenticate.",
            "suggestion": "Set GEMINI_API_KEY env var or run `gemini` interactively to complete OAuth.",
        }
    try:
        data = json.loads(result.stdout)
        model = _extract_gemini_model(data)
        return {
            "authenticated": True,
            "method": "api_key_or_oauth",
            "detail": f"OK — model: {model}",
            "suggestion": "",
        }
    except (json.JSONDecodeError, KeyError):
        return {
            "authenticated": False,
            "method": "unknown",
            "detail": "Could not parse gemini response.",
            "suggestion": "Set GEMINI_API_KEY or run `gemini` interactively to authenticate.",
        }


def list_gemini_sessions(project_dir: str | None = None, timeout: float = 10.0) -> list[dict[str, Any]]:
    """
    List saved Gemini CLI sessions using --list-sessions.
    Returns a list of session dicts with index and preview.
    """
    binary = _resolve_binary("gemini", "npm install -g @google/gemini-cli")
    result = _run_subprocess(
        [binary, "--list-sessions"],
        timeout, project_dir, "gemini",
    )
    # Output is plain text lines like: "  0: [2026-04-05] first message preview..."
    sessions = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped:
            sessions.append({"raw": stripped})
    return sessions


# ---------------------------------------------------------------------------
# Qwen
# ---------------------------------------------------------------------------

def run_qwen_prompt(
    prompt: str,
    model: str | None = None,
    timeout: float = 120.0,
    project_dir: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    Run a prompt through the Qwen Code CLI.

    If session_id is provided, resumes that session (--resume <id> --chat-recording).
    Otherwise starts a fresh session with --chat-recording enabled.
    Returns: { response, model, session_id }
    """
    binary = _resolve_binary("qwen", "npm install -g @qwen-code/qwen-code")
    cmd = [binary, prompt, "--yolo", "--output-format", "json", "--chat-recording"]
    if model:
        cmd += ["-m", model]
    if session_id:
        cmd += ["--resume", session_id]

    result = _run_subprocess(cmd, timeout, project_dir, "qwen")
    _assert_zero_exit(result, "qwen", "Run `qwen auth qwen-oauth` or `qwen auth coding-plan` to authenticate.")

    try:
        events: list[dict[str, Any]] = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise OpencodeProtocolError(
            message="qwen CLI returned unexpected non-JSON output",
            detail={"raw": result.stdout[:500]},
            recoverable=False,
            suggestion="Ensure qwen CLI >= 0.14.0 and use --output-format json.",
        ) from error

    return _parse_qwen_events(events)


def check_qwen_auth(timeout: float = 15.0) -> dict[str, Any]:
    """
    Check Qwen CLI authentication status using `qwen auth status`.
    Returns: { authenticated: bool, method: str, detail: str }
    """
    binary = _resolve_binary("qwen", "npm install -g @qwen-code/qwen-code")
    result = _run_subprocess([binary, "auth", "status"], timeout, None, "qwen")

    output = result.stdout.strip() + result.stderr.strip()
    authenticated = result.returncode == 0 and "✓" in output

    return {
        "authenticated": authenticated,
        "method": _extract_qwen_auth_method(output),
        "detail": output[:300],
        "suggestion": "" if authenticated else "Run `qwen auth qwen-oauth` or `qwen auth coding-plan` to authenticate.",
    }


# ---------------------------------------------------------------------------
# Parsers / helpers
# ---------------------------------------------------------------------------

def _extract_gemini_model(data: dict[str, Any]) -> str:
    """Extract model name from gemini JSON stats block."""
    models = data.get("stats", {}).get("models", {})
    return next(iter(models), "")


def _parse_qwen_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Extract response, model, and session_id from qwen --output-format json event stream.
    Stream is a list of typed events; pulls from 'result' and 'assistant' events.
    """
    response_text = ""
    model_name = ""
    session_id = ""

    for event in events:
        event_type = event.get("type")
        if event_type == "result":
            response_text = event.get("result", "")
            session_id = event.get("session_id", "")
            if event.get("is_error"):
                raise OpencodeValidationError(
                    message=f"qwen CLI reported an error: {response_text}",
                    detail={"event": event},
                    recoverable=True,
                    suggestion="Check your prompt or authentication status with qwen_check_auth.",
                )
        if event_type == "assistant":
            session_id = session_id or event.get("session_id", "")
            model_name = model_name or event.get("message", {}).get("model", "")

    return {"response": response_text, "model": model_name, "session_id": session_id}


def _extract_qwen_auth_method(output: str) -> str:
    """Parse auth method from qwen auth status output."""
    lower = output.lower()
    if "qwen-oauth" in lower or "qwen oauth" in lower:
        return "qwen-oauth"
    if "coding-plan" in lower or "alibaba" in lower:
        return "coding-plan"
    if "api key" in lower or "dashscope" in lower:
        return "api-key"
    return "unknown"
