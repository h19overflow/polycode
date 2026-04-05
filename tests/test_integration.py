# tests/test_integration.py
"""
Integration tests — require opencode binary on PATH and ollama running.
Run with: pytest tests/test_integration.py -m integration -v
"""
import pytest
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
