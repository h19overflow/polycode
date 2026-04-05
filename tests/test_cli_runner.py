# tests/test_cli_runner.py
import json
import pytest
from opencode_mcp.helpers.cli_runner import run_gemini_prompt, run_qwen_prompt, _parse_qwen_events
from opencode_mcp.errors import OpencodeBinaryNotFoundError, OpencodeTimeoutError, OpencodeProtocolError, OpencodeValidationError
import subprocess


# --- Gemini ---

def test_run_gemini_prompt_returns_response(monkeypatch):
    payload = json.dumps({
        "session_id": "sess-1",
        "response": "GEMINI_OK",
        "stats": {"models": {"gemini-2.5-flash": {}}},
    })

    def fake_which(name):
        return f"/usr/bin/{name}"

    def fake_run(*args, **kwargs):
        class R:
            returncode = 0
            stdout = payload
            stderr = ""
        return R()

    monkeypatch.setattr("opencode_mcp.helpers.cli_runner.shutil.which", fake_which)
    monkeypatch.setattr("opencode_mcp.helpers.cli_runner.subprocess.run", fake_run)

    result = run_gemini_prompt("hello")
    assert result["response"] == "GEMINI_OK"
    assert result["model"] == "gemini-2.5-flash"
    assert result["session_id"] == "sess-1"


def test_run_gemini_prompt_raises_when_binary_missing(monkeypatch):
    monkeypatch.setattr("opencode_mcp.helpers.cli_runner.shutil.which", lambda n: None)
    with pytest.raises(OpencodeBinaryNotFoundError):
        run_gemini_prompt("hello")


def test_run_gemini_prompt_raises_on_timeout(monkeypatch):
    monkeypatch.setattr("opencode_mcp.helpers.cli_runner.shutil.which", lambda n: "/usr/bin/gemini")

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="gemini", timeout=1)

    monkeypatch.setattr("opencode_mcp.helpers.cli_runner.subprocess.run", fake_run)
    with pytest.raises(OpencodeTimeoutError):
        run_gemini_prompt("hello", timeout=1)


def test_run_gemini_prompt_raises_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr("opencode_mcp.helpers.cli_runner.shutil.which", lambda n: "/usr/bin/gemini")

    def fake_run(*args, **kwargs):
        class R:
            returncode = 1
            stdout = ""
            stderr = "auth error"
        return R()

    monkeypatch.setattr("opencode_mcp.helpers.cli_runner.subprocess.run", fake_run)
    with pytest.raises(OpencodeValidationError):
        run_gemini_prompt("hello")


def test_run_gemini_prompt_raises_on_bad_json(monkeypatch):
    monkeypatch.setattr("opencode_mcp.helpers.cli_runner.shutil.which", lambda n: "/usr/bin/gemini")

    def fake_run(*args, **kwargs):
        class R:
            returncode = 0
            stdout = "not json"
            stderr = ""
        return R()

    monkeypatch.setattr("opencode_mcp.helpers.cli_runner.subprocess.run", fake_run)
    with pytest.raises(OpencodeProtocolError):
        run_gemini_prompt("hello")


# --- Qwen ---

def test_parse_qwen_events_extracts_response():
    events = [
        {"type": "system", "subtype": "init", "session_id": "s1"},
        {"type": "assistant", "session_id": "s1", "message": {"model": "qwen-plus", "content": []}},
        {"type": "result", "subtype": "success", "session_id": "s1", "result": "QWEN_OK", "is_error": False},
    ]
    result = _parse_qwen_events(events)
    assert result["response"] == "QWEN_OK"
    assert result["model"] == "qwen-plus"
    assert result["session_id"] == "s1"


def test_run_qwen_prompt_returns_response(monkeypatch):
    events = [
        {"type": "assistant", "session_id": "s2", "message": {"model": "qwen-turbo", "content": []}},
        {"type": "result", "session_id": "s2", "result": "QWEN_OK", "is_error": False},
    ]

    def fake_which(name):
        return f"/usr/bin/{name}"

    def fake_run(*args, **kwargs):
        class R:
            returncode = 0
            stdout = json.dumps(events)
            stderr = ""
        return R()

    monkeypatch.setattr("opencode_mcp.helpers.cli_runner.shutil.which", fake_which)
    monkeypatch.setattr("opencode_mcp.helpers.cli_runner.subprocess.run", fake_run)

    result = run_qwen_prompt("hello")
    assert result["response"] == "QWEN_OK"
    assert result["model"] == "qwen-turbo"


def test_run_qwen_prompt_raises_when_binary_missing(monkeypatch):
    monkeypatch.setattr("opencode_mcp.helpers.cli_runner.shutil.which", lambda n: None)
    with pytest.raises(OpencodeBinaryNotFoundError):
        run_qwen_prompt("hello")


def test_run_qwen_prompt_raises_on_timeout(monkeypatch):
    monkeypatch.setattr("opencode_mcp.helpers.cli_runner.shutil.which", lambda n: "/usr/bin/qwen")

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="qwen", timeout=1)

    monkeypatch.setattr("opencode_mcp.helpers.cli_runner.subprocess.run", fake_run)
    with pytest.raises(OpencodeTimeoutError):
        run_qwen_prompt("hello", timeout=1)


def test_run_qwen_prompt_raises_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr("opencode_mcp.helpers.cli_runner.shutil.which", lambda n: "/usr/bin/qwen")

    def fake_run(*args, **kwargs):
        class R:
            returncode = 1
            stdout = ""
            stderr = "auth error"
        return R()

    monkeypatch.setattr("opencode_mcp.helpers.cli_runner.subprocess.run", fake_run)
    with pytest.raises(OpencodeValidationError):
        run_qwen_prompt("hello")


def test_run_qwen_prompt_raises_on_bad_json(monkeypatch):
    monkeypatch.setattr("opencode_mcp.helpers.cli_runner.shutil.which", lambda n: "/usr/bin/qwen")

    def fake_run(*args, **kwargs):
        class R:
            returncode = 0
            stdout = "not json"
            stderr = ""
        return R()

    monkeypatch.setattr("opencode_mcp.helpers.cli_runner.subprocess.run", fake_run)
    with pytest.raises(OpencodeProtocolError):
        run_qwen_prompt("hello")
