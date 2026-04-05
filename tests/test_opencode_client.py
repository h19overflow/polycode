import pytest
import respx
import httpx
from opencode_mcp.opencode_client import OpencodeClient
from opencode_mcp.errors import OpencodeProtocolError, OpencodeTimeoutError


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


@pytest.mark.asyncio
@respx.mock
async def test_send_message_raises_timeout_error(client):
    respx.post(f"{BASE_URL}/session/sess-abc/message").mock(
        side_effect=httpx.TimeoutException("timed out")
    )
    with pytest.raises(OpencodeTimeoutError):
        await client.send_message(session_id="sess-abc", message="Hello")
