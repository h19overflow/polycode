from __future__ import annotations

import logging
import os
from typing import Any

import fastmcp
from pydantic import Field

from opencode_mcp.core.client import OpencodeClient
from opencode_mcp.core.process import OpencodeProcess
from opencode_mcp.errors import OpencodeError, format_error
from opencode_mcp.routers.gemini import register as register_gemini
from opencode_mcp.routers.opencode import register as register_opencode
from opencode_mcp.routers.qwen import register as register_qwen
from opencode_mcp.session_manager import SessionManager
from opencode_mcp.tools import handle_shutdown

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


def _wrap_error(err: OpencodeError) -> dict[str, Any]:
    logger.error("Tool error: %s — %s", type(err).__name__, err.message)
    return dict(format_error(err))


# Register tools from each provider router
register_opencode(
    mcp,
    state=_state,
    get_client=_get_client,
    process=_process,
    session_manager=_session_manager,
    request_timeout=REQUEST_TIMEOUT,
)
register_gemini(mcp)
register_qwen(mcp)


# Shutdown lives here because it owns the client lifecycle
@mcp.tool()
async def opencode_shutdown() -> dict[str, Any]:
    """
    Gracefully stop the opencode server and close all active sessions.

    Call this when you are done with all opencode work in the current session.
    Gemini and Qwen CLI tools are not affected — they are stateless subprocesses.
    """
    global _client
    try:
        result = await handle_shutdown(session_manager=_session_manager, process=_process)
        if _client is not None:
            await _client.aclose()
            _client = None
        return result
    except OpencodeError as err:
        return _wrap_error(err)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
