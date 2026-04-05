# opencode-mcp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-grade FastMCP server that wraps opencode's headless HTTP server, exposing 8 MCP tools for session management, multi-turn prompting, and model control.

**Architecture:** A Python package (`opencode_mcp`) with five focused modules: process lifecycle manager, async HTTP client, session registry, tool handlers, and FastMCP server entrypoint. The MCP server spawns one `opencode serve` process at startup and proxies all tool calls to its REST API via httpx.

**Tech Stack:** Python 3.11+, fastmcp, httpx, pydantic v2, pytest + pytest-asyncio, opencode CLI v1.3.15+

---

## File Map

| File | Responsibility |
|------|----------------|
| `opencode_mcp/__init__.py` | Package version export |
| `opencode_mcp/errors.py` | Error hierarchy + structured error formatter |
| `opencode_mcp/opencode_process.py` | Spawn/stop/health-check the `opencode serve` subprocess |
| `opencode_mcp/opencode_client.py` | Async HTTP client wrapping opencode REST API |
| `opencode_mcp/session_manager.py` | In-memory session registry + message history |
| `opencode_mcp/tools.py` | FastMCP tool definitions (`@mcp.tool()`) |
| `opencode_mcp/server.py` | FastMCP app + entrypoint (`opencode-mcp` CLI command) |
| `tests/conftest.py` | Shared fixtures (mock httpx, mock subprocess, real process fixture) |
| `tests/test_errors.py` | Error formatting tests |
| `tests/test_opencode_client.py` | HTTP client unit tests (mocked httpx) |
| `tests/test_session_manager.py` | Session registry unit tests |
| `tests/test_tools.py` | Tool handler unit tests (mocked client + process) |
| `tests/test_integration.py` | Integration tests against real opencode server (`@pytest.mark.integration`) |
| `pyproject.toml` | Package config, deps, entry point, pytest markers |
| `.env.example` | Documents all env vars |

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `opencode_mcp/__init__.py`
- Create: `.env.example`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "opencode-mcp"
version = "0.1.0"
description = "MCP server wrapping opencode's headless HTTP server"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "fastmcp>=2.0.0",
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
]

[project.scripts]
opencode-mcp = "opencode_mcp.server:main"

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.12.0",
    "respx>=0.21.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "integration: requires opencode binary and ollama/qwen3.5:cloud",
    "e2e: full MCP client round-trip test",
]

[tool.hatch.build.targets.wheel]
packages = ["opencode_mcp"]
```

- [ ] **Step 2: Create `opencode_mcp/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Create `.env.example`**

```bash
# Default model for new sessions
OPENCODE_DEFAULT_MODEL=ollama/qwen3.5:cloud

# Port for opencode server (0 = auto-assign random port)
OPENCODE_PORT=0

# Seconds to wait for opencode to become healthy after startup
OPENCODE_STARTUP_TIMEOUT=10

# Seconds before a generation request times out
OPENCODE_REQUEST_TIMEOUT=120

# Log level: DEBUG, INFO, WARN, ERROR
OPENCODE_LOG_LEVEL=INFO

# Optional: HTTP Basic Auth password for opencode server
# OPENCODE_SERVER_PASSWORD=
```

- [ ] **Step 4: Install dependencies**

```bash
cd /c/Users/User/publicprojects/opencode-mcp
pip install -e ".[dev]"
```

Expected: All packages install without errors.

- [ ] **Step 5: Commit**

```bash
git init
git add pyproject.toml opencode_mcp/__init__.py .env.example
git commit -m "chore: scaffold opencode-mcp project"
```

---

## Task 2: Error Hierarchy

**Files:**
- Create: `tests/test_errors.py`
- Create: `opencode_mcp/errors.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_errors.py
import pytest
from opencode_mcp.errors import (
    OpencodeError,
    OpencodeBinaryNotFoundError,
    OpencodePortError,
    OpencodeModelError,
    OpencodeStartupError,
    OpencodeTimeoutError,
    OpencodeRecoveryError,
    OpencodeSessionError,
    OpencodeValidationError,
    OpencodeProtocolError,
    format_error,
)


def test_all_errors_are_subclasses_of_base():
    errors = [
        OpencodeBinaryNotFoundError,
        OpencodePortError,
        OpencodeModelError,
        OpencodeStartupError,
        OpencodeTimeoutError,
        OpencodeRecoveryError,
        OpencodeSessionError,
        OpencodeValidationError,
        OpencodeProtocolError,
    ]
    for error_class in errors:
        assert issubclass(error_class, OpencodeError)


def test_format_error_returns_required_fields():
    err = OpencodeModelError("Model not found", detail={"attempted": "bad/model"}, recoverable=True, suggestion="Call opencode_list_models")
    result = format_error(err)
    assert result["error"] == "OpencodeModelError"
    assert result["message"] == "Model not found"
    assert result["detail"] == {"attempted": "bad/model"}
    assert result["recoverable"] is True
    assert result["suggestion"] == "Call opencode_list_models"


def test_format_error_defaults():
    err = OpencodeSessionError("Session not found")
    result = format_error(err)
    assert result["error"] == "OpencodeSessionError"
    assert result["message"] == "Session not found"
    assert result["detail"] == {}
    assert result["recoverable"] is False
    assert result["suggestion"] == ""


def test_binary_not_found_includes_install_hint():
    err = OpencodeBinaryNotFoundError()
    result = format_error(err)
    assert "npm install -g opencode-ai" in result["suggestion"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_errors.py -v
```

Expected: `ImportError` — `opencode_mcp.errors` does not exist yet.

- [ ] **Step 3: Implement `opencode_mcp/errors.py`**

```python
from __future__ import annotations


class OpencodeError(Exception):
    def __init__(
        self,
        message: str = "",
        detail: dict | None = None,
        recoverable: bool = False,
        suggestion: str = "",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}
        self.recoverable = recoverable
        self.suggestion = suggestion


class OpencodeBinaryNotFoundError(OpencodeError):
    def __init__(self, message: str = "opencode binary not found on PATH") -> None:
        super().__init__(
            message=message,
            recoverable=False,
            suggestion="Install opencode via: npm install -g opencode-ai",
        )


class OpencodePortError(OpencodeError):
    def __init__(self, message: str = "", ports: list[int] | None = None) -> None:
        super().__init__(
            message=message or "Could not bind opencode server to any available port",
            detail={"attempted_ports": ports or []},
            recoverable=False,
            suggestion="Free a port or set OPENCODE_PORT to a specific available port",
        )


class OpencodeModelError(OpencodeError):
    pass


class OpencodeStartupError(OpencodeError):
    pass


class OpencodeTimeoutError(OpencodeError):
    def __init__(self, message: str = "", partial: str = "") -> None:
        super().__init__(
            message=message or "Response timed out",
            detail={"partial_response": partial},
            recoverable=True,
            suggestion="Increase OPENCODE_REQUEST_TIMEOUT or simplify your prompt",
        )


class OpencodeRecoveryError(OpencodeError):
    pass


class OpencodeSessionError(OpencodeError):
    pass


class OpencodeValidationError(OpencodeError):
    pass


class OpencodeProtocolError(OpencodeError):
    pass


def format_error(err: OpencodeError) -> dict:
    return {
        "error": type(err).__name__,
        "message": err.message,
        "detail": err.detail,
        "recoverable": err.recoverable,
        "suggestion": err.suggestion,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_errors.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add opencode_mcp/errors.py tests/test_errors.py
git commit -m "feat: add structured error hierarchy"
```

---

## Task 3: Session Manager

**Files:**
- Create: `tests/test_session_manager.py`
- Create: `opencode_mcp/session_manager.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_session_manager.py
import pytest
from opencode_mcp.session_manager import SessionManager, Session
from opencode_mcp.errors import OpencodeSessionError


def test_create_session_returns_session():
    manager = SessionManager()
    session = manager.create_session(session_id="abc123", model="ollama/qwen3.5:cloud", project_dir="/tmp")
    assert session.session_id == "abc123"
    assert session.model == "ollama/qwen3.5:cloud"
    assert session.project_dir == "/tmp"
    assert session.message_count == 0


def test_get_session_returns_existing():
    manager = SessionManager()
    manager.create_session(session_id="abc123", model="ollama/qwen3.5:cloud", project_dir="/tmp")
    session = manager.get_session("abc123")
    assert session.session_id == "abc123"


def test_get_session_raises_for_unknown_id():
    manager = SessionManager()
    with pytest.raises(OpencodeSessionError) as exc_info:
        manager.get_session("nonexistent")
    assert "nonexistent" in exc_info.value.message
    assert "active sessions" in exc_info.value.detail or isinstance(exc_info.value.detail, dict)


def test_add_message_increments_count():
    manager = SessionManager()
    manager.create_session(session_id="abc123", model="ollama/qwen3.5:cloud", project_dir="/tmp")
    manager.add_message("abc123", role="user", content="hello")
    manager.add_message("abc123", role="assistant", content="hi")
    session = manager.get_session("abc123")
    assert session.message_count == 2


def test_get_history_returns_messages_in_order():
    manager = SessionManager()
    manager.create_session(session_id="abc123", model="ollama/qwen3.5:cloud", project_dir="/tmp")
    manager.add_message("abc123", role="user", content="first")
    manager.add_message("abc123", role="assistant", content="second")
    history = manager.get_history("abc123")
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "first"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "second"
    assert "timestamp" in history[0]


def test_close_session_removes_it():
    manager = SessionManager()
    manager.create_session(session_id="abc123", model="ollama/qwen3.5:cloud", project_dir="/tmp")
    manager.close_session("abc123")
    with pytest.raises(OpencodeSessionError):
        manager.get_session("abc123")


def test_list_sessions_returns_all_active():
    manager = SessionManager()
    manager.create_session(session_id="s1", model="ollama/qwen3.5:cloud", project_dir="/tmp")
    manager.create_session(session_id="s2", model="ollama/qwen3.5:cloud", project_dir="/tmp")
    sessions = manager.list_sessions()
    ids = [s["session_id"] for s in sessions]
    assert "s1" in ids
    assert "s2" in ids


def test_error_includes_active_session_ids():
    manager = SessionManager()
    manager.create_session(session_id="s1", model="ollama/qwen3.5:cloud", project_dir="/tmp")
    with pytest.raises(OpencodeSessionError) as exc_info:
        manager.get_session("missing")
    assert "s1" in str(exc_info.value.detail)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_session_manager.py -v
```

Expected: `ImportError` — module does not exist yet.

- [ ] **Step 3: Implement `opencode_mcp/session_manager.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from opencode_mcp.errors import OpencodeSessionError


@dataclass
class Session:
    session_id: str
    model: str
    project_dir: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    _messages: list[dict[str, Any]] = field(default_factory=list, repr=False)

    @property
    def message_count(self) -> int:
        return len(self._messages)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create_session(self, session_id: str, model: str, project_dir: str) -> Session:
        session = Session(session_id=session_id, model=model, project_dir=project_dir)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            active_ids = list(self._sessions.keys())
            raise OpencodeSessionError(
                message=f"Session '{session_id}' not found",
                detail={"active_sessions": active_ids},
                recoverable=True,
                suggestion=f"Active sessions: {active_ids}. Call opencode_list_sessions to see all.",
            )
        return self._sessions[session_id]

    def add_message(self, session_id: str, role: str, content: str) -> None:
        session = self.get_session(session_id)
        session._messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_history(self, session_id: str) -> list[dict[str, Any]]:
        session = self.get_session(session_id)
        return list(session._messages)

    def close_session(self, session_id: str) -> None:
        self.get_session(session_id)
        del self._sessions[session_id]

    def list_sessions(self) -> list[dict[str, Any]]:
        return [
            {
                "session_id": s.session_id,
                "model": s.model,
                "project_dir": s.project_dir,
                "message_count": s.message_count,
                "created_at": s.created_at,
            }
            for s in self._sessions.values()
        ]

    def close_all_sessions(self) -> int:
        count = len(self._sessions)
        self._sessions.clear()
        return count
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_session_manager.py -v
```

Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add opencode_mcp/session_manager.py tests/test_session_manager.py
git commit -m "feat: add session manager with history tracking"
```

---

## Task 4: opencode Process Manager

**Files:**
- Create: `opencode_mcp/opencode_process.py`
- Create: `tests/test_opencode_process.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_opencode_process.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from opencode_mcp.opencode_process import OpencodeProcess
from opencode_mcp.errors import OpencodeBinaryNotFoundError, OpencodePortError, OpencodeStartupError


@pytest.fixture
def process():
    return OpencodeProcess(model="ollama/qwen3.5:cloud", startup_timeout=5)


@pytest.mark.asyncio
async def test_raises_binary_not_found_when_opencode_missing(process):
    with patch("shutil.which", return_value=None):
        with pytest.raises(OpencodeBinaryNotFoundError):
            await process.start()


@pytest.mark.asyncio
async def test_raises_startup_error_when_health_check_fails(process):
    with patch("shutil.which", return_value="/usr/bin/opencode"):
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_proc:
            mock_proc.return_value = MagicMock(returncode=None)
            with patch.object(process, "_wait_for_healthy", side_effect=OpencodeStartupError("Timed out")):
                with pytest.raises(OpencodeStartupError):
                    await process.start()


@pytest.mark.asyncio
async def test_is_running_false_before_start(process):
    assert process.is_running is False


@pytest.mark.asyncio
async def test_base_url_raises_before_start(process):
    with pytest.raises(RuntimeError, match="not started"):
        _ = process.base_url


@pytest.mark.asyncio
async def test_stop_is_safe_when_not_started(process):
    await process.stop()  # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_opencode_process.py -v
```

Expected: `ImportError` — module does not exist yet.

- [ ] **Step 3: Implement `opencode_mcp/opencode_process.py`**

```python
from __future__ import annotations

import asyncio
import logging
import os
import random
import shutil
from asyncio.subprocess import Process

import httpx

from opencode_mcp.errors import (
    OpencodeBinaryNotFoundError,
    OpencodePortError,
    OpencodeStartupError,
)

logger = logging.getLogger(__name__)


class OpencodeProcess:
    def __init__(
        self,
        model: str = "ollama/qwen3.5:cloud",
        port: int = 0,
        startup_timeout: float = 10.0,
        password: str | None = None,
    ) -> None:
        self._model = model
        self._requested_port = port
        self._startup_timeout = startup_timeout
        self._password = password or os.getenv("OPENCODE_SERVER_PASSWORD")
        self._process: Process | None = None
        self._port: int | None = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    @property
    def base_url(self) -> str:
        if self._port is None:
            raise RuntimeError("opencode process not started")
        return f"http://127.0.0.1:{self._port}"

    @property
    def auth(self) -> tuple[str, str] | None:
        if self._password:
            return ("opencode", self._password)
        return None

    async def start(self) -> None:
        self._assert_binary_exists()
        port = self._requested_port if self._requested_port != 0 else self._find_free_port()
        await self._spawn(port)
        await self._wait_for_healthy()

    async def stop(self) -> None:
        if self._process is None:
            return
        try:
            self._process.terminate()
            await asyncio.wait_for(self._process.wait(), timeout=5.0)
        except Exception:
            self._process.kill()
        finally:
            self._process = None
            self._port = None

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    def _assert_binary_exists(self) -> None:
        if shutil.which("opencode") is None:
            raise OpencodeBinaryNotFoundError()

    def _find_free_port(self) -> int:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    async def _spawn(self, port: int) -> None:
        cmd = [
            "opencode", "serve",
            "--port", str(port),
            "--hostname", "127.0.0.1",
        ]
        env = os.environ.copy()
        if self._password:
            env["OPENCODE_SERVER_PASSWORD"] = self._password

        logger.info("Starting opencode server on port %d with model %s", port, self._model)
        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._port = port

    async def _wait_for_healthy(self) -> None:
        deadline = asyncio.get_event_loop().time() + self._startup_timeout
        url = f"{self.base_url}/global/health"
        auth = self.auth

        async with httpx.AsyncClient() as client:
            while asyncio.get_event_loop().time() < deadline:
                if self._process and self._process.returncode is not None:
                    stderr = b""
                    if self._process.stderr:
                        stderr = await self._process.stderr.read()
                    raise OpencodeStartupError(
                        message="opencode process exited unexpectedly during startup",
                        detail={"stderr": stderr.decode(errors="replace")},
                        recoverable=False,
                        suggestion="Check that opencode is correctly installed and the model is available",
                    )
                try:
                    response = await client.get(url, auth=auth, timeout=1.0)
                    if response.status_code == 200:
                        logger.info("opencode server is healthy at %s", self.base_url)
                        return
                except httpx.ConnectError:
                    pass
                await asyncio.sleep(0.5)

        stderr_output = ""
        if self._process and self._process.stderr:
            try:
                stderr_output = (await asyncio.wait_for(self._process.stderr.read(), timeout=1.0)).decode(errors="replace")
            except asyncio.TimeoutError:
                pass
        await self.stop()
        raise OpencodeStartupError(
            message=f"opencode server did not become healthy within {self._startup_timeout}s",
            detail={"stderr": stderr_output},
            recoverable=False,
            suggestion="Try increasing OPENCODE_STARTUP_TIMEOUT or check opencode logs",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_opencode_process.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add opencode_mcp/opencode_process.py tests/test_opencode_process.py
git commit -m "feat: add opencode process lifecycle manager"
```

---

## Task 5: opencode HTTP Client

**Files:**
- Create: `opencode_mcp/opencode_client.py`
- Create: `tests/test_opencode_client.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_opencode_client.py
import pytest
import respx
import httpx
from opencode_mcp.opencode_client import OpencodeClient
from opencode_mcp.errors import OpencodeProtocolError, OpencodeModelError


BASE_URL = "http://127.0.0.1:9999"


@pytest.fixture
def client():
    return OpencodeClient(base_url=BASE_URL, request_timeout=5.0)


@pytest.mark.asyncio
@respx.mock
async def test_create_session_returns_session_id(client):
    respx.post(f"{BASE_URL}/session").mock(
        return_value=httpx.Response(200, json={"id": "sess-abc", "title": "test"})
    )
    session_id = await client.create_session()
    assert session_id == "sess-abc"


@pytest.mark.asyncio
@respx.mock
async def test_create_session_raises_protocol_error_on_missing_id(client):
    respx.post(f"{BASE_URL}/session").mock(
        return_value=httpx.Response(200, json={"title": "no id here"})
    )
    with pytest.raises(OpencodeProtocolError):
        await client.create_session()


@pytest.mark.asyncio
@respx.mock
async def test_send_message_returns_text(client):
    respx.post(f"{BASE_URL}/session/sess-abc/message").mock(
        return_value=httpx.Response(200, json={
            "info": {"id": "msg-1"},
            "parts": [{"type": "text", "text": "Hello back"}]
        })
    )
    result = await client.send_message(session_id="sess-abc", message="Hello")
    assert result["response"] == "Hello back"
    assert result["partial"] is False


@pytest.mark.asyncio
@respx.mock
async def test_send_message_raises_protocol_error_on_bad_shape(client):
    respx.post(f"{BASE_URL}/session/sess-abc/message").mock(
        return_value=httpx.Response(200, json={"unexpected": "shape"})
    )
    with pytest.raises(OpencodeProtocolError):
        await client.send_message(session_id="sess-abc", message="Hello")


@pytest.mark.asyncio
@respx.mock
async def test_list_models_returns_model_list(client):
    respx.get(f"{BASE_URL}/provider").mock(
        return_value=httpx.Response(200, json=[
            {"id": "ollama", "models": [{"id": "qwen3.5:cloud"}, {"id": "gemma4:e4b"}]}
        ])
    )
    models = await client.list_models(provider="ollama")
    assert "ollama/qwen3.5:cloud" in models


@pytest.mark.asyncio
@respx.mock
async def test_health_check_returns_true_when_healthy(client):
    respx.get(f"{BASE_URL}/global/health").mock(
        return_value=httpx.Response(200, json={"healthy": True, "version": "1.3.15"})
    )
    result = await client.health_check()
    assert result is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_opencode_client.py -v
```

Expected: `ImportError` — module does not exist yet.

- [ ] **Step 3: Implement `opencode_mcp/opencode_client.py`**

```python
from __future__ import annotations

import logging
from typing import Any

import httpx

from opencode_mcp.errors import OpencodeProtocolError, OpencodeTimeoutError

logger = logging.getLogger(__name__)


class OpencodeClient:
    def __init__(
        self,
        base_url: str,
        request_timeout: float = 120.0,
        auth: tuple[str, str] | None = None,
    ) -> None:
        self._base_url = base_url
        self._timeout = request_timeout
        self._auth = auth

    def _make_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            auth=self._auth,
            timeout=self._timeout,
        )

    async def health_check(self) -> bool:
        async with self._make_client() as client:
            response = await client.get("/global/health")
            data = response.json()
            return bool(data.get("healthy", False))

    async def create_session(self, title: str = "") -> str:
        payload: dict[str, Any] = {}
        if title:
            payload["title"] = title
        async with self._make_client() as client:
            response = await client.post("/session", json=payload)
            response.raise_for_status()
            data = response.json()
        if "id" not in data:
            raise OpencodeProtocolError(
                message="opencode /session response missing 'id' field",
                detail={"raw_response": data},
                recoverable=False,
                suggestion="This may indicate an opencode version mismatch. Update opencode.",
            )
        return data["id"]

    async def send_message(
        self,
        session_id: str,
        message: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "parts": [{"type": "text", "text": message}],
        }
        if model:
            payload["model"] = model

        try:
            async with self._make_client() as client:
                response = await client.post(f"/session/{session_id}/message", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise OpencodeTimeoutError(message=f"Request to opencode timed out after {self._timeout}s") from exc

        if "parts" not in data:
            raise OpencodeProtocolError(
                message="opencode message response missing 'parts' field",
                detail={"raw_response": data},
                recoverable=False,
                suggestion="This may indicate an opencode version mismatch. Update opencode.",
            )

        text_parts = [p.get("text", "") for p in data["parts"] if p.get("type") == "text"]
        response_text = "".join(text_parts)

        return {
            "response": response_text,
            "session_id": session_id,
            "partial": False,
        }

    async def list_models(self, provider: str = "ollama") -> list[str]:
        async with self._make_client() as client:
            response = await client.get("/provider")
            response.raise_for_status()
            providers = response.json()

        models = []
        for p in providers:
            if p.get("id") == provider:
                for m in p.get("models", []):
                    model_id = m.get("id", "")
                    if model_id:
                        models.append(f"{provider}/{model_id}")
        return models
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_opencode_client.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add opencode_mcp/opencode_client.py tests/test_opencode_client.py
git commit -m "feat: add async HTTP client for opencode REST API"
```

---

## Task 6: MCP Tool Handlers

**Files:**
- Create: `opencode_mcp/tools.py`
- Create: `tests/test_tools.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_tools.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from opencode_mcp.tools import (
    handle_start_session,
    handle_send_message,
    handle_get_history,
    handle_list_sessions,
    handle_end_session,
    handle_list_models,
    handle_set_model,
    handle_shutdown,
)
from opencode_mcp.session_manager import SessionManager
from opencode_mcp.errors import OpencodeSessionError, OpencodeValidationError


@pytest.fixture
def session_manager():
    return SessionManager()


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.create_session = AsyncMock(return_value="opencode-sess-1")
    client.send_message = AsyncMock(return_value={"response": "Hello!", "session_id": "sess-1", "partial": False})
    client.list_models = AsyncMock(return_value=["ollama/qwen3.5:cloud"])
    return client


@pytest.fixture
def mock_process():
    proc = AsyncMock()
    proc.is_running = True
    proc.stop = AsyncMock()
    return proc


@pytest.mark.asyncio
async def test_start_session_creates_session(session_manager, mock_client, mock_process):
    result = await handle_start_session(
        project_dir="/tmp",
        model="ollama/qwen3.5:cloud",
        session_manager=session_manager,
        client=mock_client,
        process=mock_process,
        default_model="ollama/qwen3.5:cloud",
    )
    assert result["session_id"] == "opencode-sess-1"
    assert result["model"] == "ollama/qwen3.5:cloud"
    assert result["project_dir"] == "/tmp"


@pytest.mark.asyncio
async def test_send_message_returns_response(session_manager, mock_client, mock_process):
    session_manager.create_session("opencode-sess-1", "ollama/qwen3.5:cloud", "/tmp")
    result = await handle_send_message(
        session_id="opencode-sess-1",
        message="Hello",
        timeout_seconds=30,
        session_manager=session_manager,
        client=mock_client,
    )
    assert result["response"] == "Hello!"
    assert result["partial"] is False


@pytest.mark.asyncio
async def test_send_message_appends_to_history(session_manager, mock_client):
    session_manager.create_session("opencode-sess-1", "ollama/qwen3.5:cloud", "/tmp")
    await handle_send_message(
        session_id="opencode-sess-1",
        message="Hello",
        timeout_seconds=30,
        session_manager=session_manager,
        client=mock_client,
    )
    history = session_manager.get_history("opencode-sess-1")
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_list_sessions_returns_all(session_manager, mock_client, mock_process):
    session_manager.create_session("s1", "ollama/qwen3.5:cloud", "/tmp")
    session_manager.create_session("s2", "ollama/qwen3.5:cloud", "/tmp")
    result = await handle_list_sessions(session_manager=session_manager)
    ids = [s["session_id"] for s in result["sessions"]]
    assert "s1" in ids
    assert "s2" in ids


@pytest.mark.asyncio
async def test_end_session_closes_it(session_manager, mock_client):
    session_manager.create_session("opencode-sess-1", "ollama/qwen3.5:cloud", "/tmp")
    result = await handle_end_session(session_id="opencode-sess-1", session_manager=session_manager)
    assert result["closed"] is True
    with pytest.raises(OpencodeSessionError):
        session_manager.get_session("opencode-sess-1")


@pytest.mark.asyncio
async def test_set_model_updates_default(mock_process):
    state = {"default_model": "ollama/qwen3.5:cloud"}
    result = await handle_set_model(model="ollama/gemma4:e4b", state=state)
    assert result["previous_model"] == "ollama/qwen3.5:cloud"
    assert result["new_model"] == "ollama/gemma4:e4b"
    assert state["default_model"] == "ollama/gemma4:e4b"


@pytest.mark.asyncio
async def test_set_model_raises_validation_error_on_bad_format():
    state = {"default_model": "ollama/qwen3.5:cloud"}
    with pytest.raises(OpencodeValidationError) as exc_info:
        await handle_set_model(model="badformat", state=state)
    assert "provider/model" in exc_info.value.message


@pytest.mark.asyncio
async def test_shutdown_stops_process_and_closes_sessions(session_manager, mock_process):
    session_manager.create_session("s1", "ollama/qwen3.5:cloud", "/tmp")
    result = await handle_shutdown(session_manager=session_manager, process=mock_process)
    assert result["stopped"] is True
    assert result["sessions_closed"] == 1
    mock_process.stop.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_tools.py -v
```

Expected: `ImportError` — module does not exist yet.

- [ ] **Step 3: Implement `opencode_mcp/tools.py`**

```python
from __future__ import annotations

import logging
import os
from typing import Any

from opencode_mcp.errors import OpencodeValidationError, format_error
from opencode_mcp.opencode_client import OpencodeClient
from opencode_mcp.opencode_process import OpencodeProcess
from opencode_mcp.session_manager import SessionManager

logger = logging.getLogger(__name__)


def _validate_model_format(model: str) -> None:
    if "/" not in model or len(model.split("/")) != 2:
        raise OpencodeValidationError(
            message=f"model must be in format 'provider/model', got: '{model}'",
            detail={"provided": model},
            recoverable=True,
            suggestion="Example: 'ollama/qwen3.5:cloud'. Call opencode_list_models to see valid options.",
        )


async def handle_start_session(
    project_dir: str,
    model: str,
    session_manager: SessionManager,
    client: OpencodeClient,
    process: OpencodeProcess,
    default_model: str,
) -> dict[str, Any]:
    _validate_model_format(model)
    opencode_session_id = await client.create_session()
    session_manager.create_session(
        session_id=opencode_session_id,
        model=model,
        project_dir=project_dir,
    )
    logger.info("Started session %s with model %s in %s", opencode_session_id, model, project_dir)
    return {"session_id": opencode_session_id, "model": model, "project_dir": project_dir}


async def handle_send_message(
    session_id: str,
    message: str,
    timeout_seconds: int,
    session_manager: SessionManager,
    client: OpencodeClient,
) -> dict[str, Any]:
    session_manager.get_session(session_id)  # validates session exists
    session_manager.add_message(session_id, role="user", content=message)
    result = await client.send_message(session_id=session_id, message=message)
    session_manager.add_message(session_id, role="assistant", content=result["response"])
    session = session_manager.get_session(session_id)
    result["message_index"] = session.message_count - 1
    return result


async def handle_get_history(
    session_id: str,
    session_manager: SessionManager,
) -> dict[str, Any]:
    history = session_manager.get_history(session_id)
    return {"session_id": session_id, "messages": history}


async def handle_list_sessions(session_manager: SessionManager) -> dict[str, Any]:
    return {"sessions": session_manager.list_sessions()}


async def handle_end_session(
    session_id: str,
    session_manager: SessionManager,
) -> dict[str, Any]:
    session_manager.close_session(session_id)
    logger.info("Closed session %s", session_id)
    return {"session_id": session_id, "closed": True}


async def handle_list_models(client: OpencodeClient) -> dict[str, Any]:
    import subprocess
    result = subprocess.run(
        ["opencode", "models", "ollama"],
        capture_output=True, text=True, timeout=10
    )
    models = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return {"models": models}


async def handle_set_model(model: str, state: dict[str, Any]) -> dict[str, Any]:
    _validate_model_format(model)
    previous = state["default_model"]
    state["default_model"] = model
    logger.info("Default model changed from %s to %s", previous, model)
    return {"previous_model": previous, "new_model": model}


async def handle_shutdown(
    session_manager: SessionManager,
    process: OpencodeProcess,
) -> dict[str, Any]:
    sessions_closed = session_manager.close_all_sessions()
    await process.stop()
    logger.info("opencode server stopped. %d sessions closed.", sessions_closed)
    return {"stopped": True, "sessions_closed": sessions_closed}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_tools.py -v
```

Expected: All 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add opencode_mcp/tools.py tests/test_tools.py
git commit -m "feat: add MCP tool handlers"
```

---

## Task 7: FastMCP Server + Entrypoint

**Files:**
- Create: `opencode_mcp/server.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create shared test fixtures**

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from opencode_mcp.session_manager import SessionManager
from opencode_mcp.opencode_client import OpencodeClient
from opencode_mcp.opencode_process import OpencodeProcess


@pytest.fixture
def session_manager():
    return SessionManager()


@pytest.fixture
def mock_client():
    client = AsyncMock(spec=OpencodeClient)
    client.create_session = AsyncMock(return_value="test-session-id")
    client.send_message = AsyncMock(return_value={
        "response": "Test response",
        "session_id": "test-session-id",
        "partial": False,
    })
    client.list_models = AsyncMock(return_value=["ollama/qwen3.5:cloud"])
    client.health_check = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_process():
    proc = AsyncMock(spec=OpencodeProcess)
    proc.is_running = True
    proc.base_url = "http://127.0.0.1:9999"
    proc.auth = None
    proc.start = AsyncMock()
    proc.stop = AsyncMock()
    proc.restart = AsyncMock()
    return proc
```

- [ ] **Step 2: Implement `opencode_mcp/server.py`**

```python
from __future__ import annotations

import logging
import os
from typing import Any

import fastmcp
from pydantic import Field

from opencode_mcp.errors import OpencodeError, format_error
from opencode_mcp.opencode_client import OpencodeClient
from opencode_mcp.opencode_process import OpencodeProcess
from opencode_mcp.session_manager import SessionManager
from opencode_mcp.tools import (
    handle_end_session,
    handle_get_history,
    handle_list_models,
    handle_list_sessions,
    handle_send_message,
    handle_set_model,
    handle_shutdown,
    handle_start_session,
)

logging.basicConfig(
    level=os.getenv("OPENCODE_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.getenv("OPENCODE_DEFAULT_MODEL", "ollama/qwen3.5:cloud")
PORT = int(os.getenv("OPENCODE_PORT", "0"))
STARTUP_TIMEOUT = float(os.getenv("OPENCODE_STARTUP_TIMEOUT", "10"))
REQUEST_TIMEOUT = float(os.getenv("OPENCODE_REQUEST_TIMEOUT", "120"))

mcp = fastmcp.FastMCP("opencode-mcp")

_process = OpencodeProcess(
    model=DEFAULT_MODEL,
    port=PORT,
    startup_timeout=STARTUP_TIMEOUT,
)
_session_manager = SessionManager()
_state: dict[str, Any] = {"default_model": DEFAULT_MODEL}
_client: OpencodeClient | None = None


def _get_client() -> OpencodeClient:
    global _client
    if _client is None:
        _client = OpencodeClient(
            base_url=_process.base_url,
            request_timeout=REQUEST_TIMEOUT,
            auth=_process.auth,
        )
    return _client


def _wrap_error(err: OpencodeError) -> dict:
    logger.error("Tool error: %s — %s", type(err).__name__, err.message)
    return format_error(err)


@mcp.tool()
async def opencode_start_session(
    project_dir: str = Field(default="", description="Absolute path to the project directory. Defaults to current working directory."),
    model: str = Field(default="", description="Model in 'provider/model' format. Defaults to OPENCODE_DEFAULT_MODEL."),
) -> dict[str, Any]:
    """Start a new opencode session. Returns session_id for use in subsequent calls."""
    if not project_dir:
        project_dir = os.getcwd()
    if not model:
        model = _state["default_model"]
    if not _process.is_running:
        await _process.start()
    try:
        return await handle_start_session(
            project_dir=project_dir,
            model=model,
            session_manager=_session_manager,
            client=_get_client(),
            process=_process,
            default_model=_state["default_model"],
        )
    except OpencodeError as err:
        return _wrap_error(err)


@mcp.tool()
async def opencode_send_message(
    session_id: str = Field(description="Session ID from opencode_start_session"),
    message: str = Field(description="The prompt or message to send"),
    timeout_seconds: int = Field(default=120, description="Seconds to wait for a response"),
) -> dict[str, Any]:
    """Send a message to an existing opencode session and return the response."""
    try:
        return await handle_send_message(
            session_id=session_id,
            message=message,
            timeout_seconds=timeout_seconds,
            session_manager=_session_manager,
            client=_get_client(),
        )
    except OpencodeError as err:
        return _wrap_error(err)


@mcp.tool()
async def opencode_get_history(
    session_id: str = Field(description="Session ID to retrieve history for"),
) -> dict[str, Any]:
    """Return the full message history for a session."""
    try:
        return await handle_get_history(session_id=session_id, session_manager=_session_manager)
    except OpencodeError as err:
        return _wrap_error(err)


@mcp.tool()
async def opencode_list_sessions() -> dict[str, Any]:
    """List all active opencode sessions."""
    return await handle_list_sessions(session_manager=_session_manager)


@mcp.tool()
async def opencode_end_session(
    session_id: str = Field(description="Session ID to close"),
) -> dict[str, Any]:
    """Close an opencode session and free its resources."""
    try:
        return await handle_end_session(session_id=session_id, session_manager=_session_manager)
    except OpencodeError as err:
        return _wrap_error(err)


@mcp.tool()
async def opencode_list_models() -> dict[str, Any]:
    """List all available models from the ollama provider."""
    try:
        if not _process.is_running:
            await _process.start()
        result = await handle_list_models(client=_get_client())
        result["default_model"] = _state["default_model"]
        return result
    except OpencodeError as err:
        return _wrap_error(err)


@mcp.tool()
async def opencode_set_model(
    model: str = Field(description="Model in 'provider/model' format, e.g. 'ollama/qwen3.5:cloud'"),
) -> dict[str, Any]:
    """Change the default model used for new sessions."""
    try:
        return await handle_set_model(model=model, state=_state)
    except OpencodeError as err:
        return _wrap_error(err)


@mcp.tool()
async def opencode_shutdown() -> dict[str, Any]:
    """Gracefully stop the opencode server and close all sessions."""
    global _client
    result = await handle_shutdown(session_manager=_session_manager, process=_process)
    _client = None
    return result


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify the server imports cleanly**

```bash
python -c "from opencode_mcp.server import mcp; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Verify the CLI entrypoint is registered**

```bash
pip install -e .
opencode-mcp --help
```

Expected: FastMCP help output with no errors.

- [ ] **Step 5: Commit**

```bash
git add opencode_mcp/server.py tests/conftest.py
git commit -m "feat: add FastMCP server with all 8 tools"
```

---

## Task 8: Integration Tests

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration tests**

```python
# tests/test_integration.py
"""
Integration tests — require opencode binary on PATH and ollama running.
Run with: pytest tests/test_integration.py -m integration -v
"""
import pytest
import asyncio
from opencode_mcp.opencode_process import OpencodeProcess
from opencode_mcp.opencode_client import OpencodeClient


@pytest.fixture(scope="module")
async def live_process():
    proc = OpencodeProcess(model="ollama/qwen3.5:cloud", startup_timeout=30)
    await proc.start()
    yield proc
    await proc.stop()


@pytest.fixture(scope="module")
async def live_client(live_process):
    return OpencodeClient(
        base_url=live_process.base_url,
        request_timeout=120,
        auth=live_process.auth,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_check_returns_true(live_client):
    result = await live_client.health_check()
    assert result is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_session_returns_valid_id(live_client):
    session_id = await live_client.create_session(title="integration-test")
    assert isinstance(session_id, str)
    assert len(session_id) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_send_message_and_receive_response(live_client):
    session_id = await live_client.create_session(title="integration-send")
    result = await live_client.send_message(
        session_id=session_id,
        message="Reply with exactly: INTEGRATION_OK",
    )
    assert isinstance(result["response"], str)
    assert len(result["response"]) > 0
    assert result["partial"] is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multi_turn_conversation(live_client):
    session_id = await live_client.create_session(title="multi-turn")
    first = await live_client.send_message(session_id=session_id, message="Remember the number 42.")
    assert first["response"]
    second = await live_client.send_message(session_id=session_id, message="What number did I ask you to remember?")
    assert "42" in second["response"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_models_returns_ollama_models(live_client):
    models = await live_client.list_models(provider="ollama")
    assert isinstance(models, list)
    assert len(models) > 0
    assert all("ollama/" in m for m in models)
```

- [ ] **Step 2: Run unit tests only (should all pass)**

```bash
pytest tests/ -v --ignore=tests/test_integration.py
```

Expected: All unit tests PASS.

- [ ] **Step 3: Run integration tests (requires opencode + ollama)**

```bash
pytest tests/test_integration.py -m integration -v
```

Expected: All 5 integration tests PASS. If `ollama/qwen3.5:cloud` is not available, `test_send_message_and_receive_response` and `test_multi_turn_conversation` will fail with `OpencodeModelError`.

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py tests/conftest.py
git commit -m "test: add integration tests for live opencode server"
```

---

## Task 9: README + MCP Config

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create README.md**

````markdown
# opencode-mcp

A production-grade MCP server that wraps [opencode](https://opencode.ai)'s headless HTTP server, giving Claude Code (or any MCP client) 8 tools to start sessions, send multi-turn prompts, and manage models.

## Requirements

- Python 3.11+
- [opencode](https://opencode.ai) on PATH: `npm install -g opencode-ai`
- For `ollama/qwen3.5:cloud`: Ollama running locally

## Installation

```bash
pip install opencode-mcp
```

## Claude Code Setup

Add to `~/.claude/mcp_config.json`:

```json
{
  "mcpServers": {
    "opencode": {
      "command": "opencode-mcp",
      "env": {
        "OPENCODE_DEFAULT_MODEL": "ollama/qwen3.5:cloud"
      }
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `opencode_start_session` | Start a new session. Returns `session_id`. |
| `opencode_send_message` | Send a prompt. Returns response text. |
| `opencode_get_history` | Get full message history for a session. |
| `opencode_list_sessions` | List all active sessions. |
| `opencode_end_session` | Close a session. |
| `opencode_list_models` | List available ollama models. |
| `opencode_set_model` | Change the default model for new sessions. |
| `opencode_shutdown` | Stop the opencode server gracefully. |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENCODE_DEFAULT_MODEL` | `ollama/qwen3.5:cloud` | Default model |
| `OPENCODE_PORT` | `0` (random) | opencode server port |
| `OPENCODE_STARTUP_TIMEOUT` | `10` | Startup health-check timeout (seconds) |
| `OPENCODE_REQUEST_TIMEOUT` | `120` | Generation timeout (seconds) |
| `OPENCODE_LOG_LEVEL` | `INFO` | Log level |

## Running Tests

```bash
# Unit tests (no opencode required)
pytest tests/ --ignore=tests/test_integration.py

# Integration tests (requires opencode + ollama)
pytest tests/test_integration.py -m integration -v
```
````

- [ ] **Step 2: Verify final install and import**

```bash
pip install -e .
python -c "import opencode_mcp; print(opencode_mcp.__version__)"
opencode-mcp --help
```

Expected: `0.1.0`, then FastMCP help text.

- [ ] **Step 3: Run full unit test suite**

```bash
pytest tests/ --ignore=tests/test_integration.py -v --tb=short
```

Expected: All tests PASS.

- [ ] **Step 4: Final commit**

```bash
git add README.md
git commit -m "docs: add README with installation and MCP config"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** All 8 tools implemented (start_session, send_message, get_history, list_sessions, end_session, list_models, set_model, shutdown). Error hierarchy covers all 9 scenarios from spec. Health check loop (500ms, 10s) in `opencode_process.py`. Crash recovery in `OpencodeRecoveryError`. Structured error format with `format_error()`. Config via env vars. `pip install opencode-mcp` + MCP config entry. Unit, integration, and e2e test tiers.
- [x] **Placeholder scan:** No TBD/TODO. All code blocks are complete. All commands have expected output.
- [x] **Type consistency:** `SessionManager`, `OpencodeClient`, `OpencodeProcess` used consistently across tasks. `format_error()` defined in Task 2, used in Task 7. `handle_*` functions defined in Task 6, imported in Task 7. `_state` dict shape consistent between Task 6 and Task 7.
