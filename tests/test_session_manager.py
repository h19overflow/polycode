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
    assert isinstance(exc_info.value.detail, dict)


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
