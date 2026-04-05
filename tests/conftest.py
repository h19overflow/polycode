# tests/conftest.py
import pytest
from unittest.mock import AsyncMock
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
