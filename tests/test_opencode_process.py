import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from opencode_mcp.opencode_process import OpencodeProcess
from opencode_mcp.errors import OpencodeBinaryNotFoundError, OpencodeStartupError


@pytest.fixture
def process():
    return OpencodeProcess(model="ollama/qwen3.5:cloud", startup_timeout=5)


@pytest.mark.asyncio
async def test_raises_binary_not_found_when_opencode_missing(process):
    with patch("opencode_mcp.opencode_process.shutil.which", return_value=None):
        with pytest.raises(OpencodeBinaryNotFoundError):
            await process.start()


@pytest.mark.asyncio
async def test_raises_startup_error_when_health_check_fails(process):
    with patch("opencode_mcp.opencode_process.shutil.which", return_value="/usr/bin/opencode"):
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
