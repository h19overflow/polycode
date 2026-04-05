from __future__ import annotations

import logging
import os
from typing import Any

import fastmcp
from pydantic import Field

from opencode_mcp.core.client import OpencodeClient
from opencode_mcp.core.process import OpencodeProcess
from opencode_mcp.errors import OpencodeError, format_error
from opencode_mcp.session_manager import SessionManager
from opencode_mcp.tools import (
    handle_end_session,
    handle_gemini_check_auth,
    handle_gemini_list_sessions,
    handle_gemini_prompt,
    handle_get_history,
    handle_list_models,
    handle_list_sessions,
    handle_qwen_check_auth,
    handle_qwen_prompt,
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


def _wrap_error(err: OpencodeError) -> dict[str, Any]:
    logger.error("Tool error: %s — %s", type(err).__name__, err.message)
    return dict(format_error(err))


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
    timeout_seconds: int = Field(default=int(REQUEST_TIMEOUT), description="Seconds to wait for a response"),
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
    """List all models available in opencode, grouped by provider. Only authenticated/connected providers will show models."""
    try:
        result = await handle_list_models()
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
async def gemini_check_auth(
    timeout_seconds: int = Field(default=15, description="Seconds to wait for the auth probe"),
) -> dict[str, Any]:
    """Check whether the Gemini CLI is authenticated. Returns authenticated status, method, and any error detail."""
    try:
        return await handle_gemini_check_auth(timeout_seconds=timeout_seconds)
    except OpencodeError as err:
        return _wrap_error(err)


@mcp.tool()
async def gemini_prompt(
    prompt: str = Field(description="The prompt to send to Gemini CLI"),
    session_id: str = Field(default="", description="Resume a previous Gemini session by its ID. Leave empty to start a new session."),
    model: str = Field(default="", description="Gemini model, e.g. 'gemini-2.5-flash'. Defaults to the CLI's configured model."),
    timeout_seconds: int = Field(default=120, description="Seconds to wait for a response"),
    project_dir: str = Field(default="", description="Working directory for the CLI. Defaults to current directory."),
) -> dict[str, Any]:
    """Send a prompt to Gemini CLI. Returns response, model used, and session_id. Pass session_id to continue a conversation."""
    try:
        return await handle_gemini_prompt(
            prompt=prompt,
            model=model or None,
            timeout_seconds=timeout_seconds,
            project_dir=project_dir or None,
            session_id=session_id or None,
        )
    except OpencodeError as err:
        return _wrap_error(err)


@mcp.tool()
async def gemini_list_sessions(
    project_dir: str = Field(default="", description="Project directory to list sessions for. Defaults to current directory."),
    timeout_seconds: int = Field(default=10, description="Seconds to wait"),
) -> dict[str, Any]:
    """List saved Gemini CLI sessions for the current project."""
    try:
        return await handle_gemini_list_sessions(
            project_dir=project_dir or None,
            timeout_seconds=timeout_seconds,
        )
    except OpencodeError as err:
        return _wrap_error(err)


@mcp.tool()
async def qwen_check_auth(
    timeout_seconds: int = Field(default=15, description="Seconds to wait for the auth check"),
) -> dict[str, Any]:
    """Check whether the Qwen Code CLI is authenticated. Returns authenticated status, method, and any error detail."""
    try:
        return await handle_qwen_check_auth(timeout_seconds=timeout_seconds)
    except OpencodeError as err:
        return _wrap_error(err)


@mcp.tool()
async def qwen_prompt(
    prompt: str = Field(description="The prompt to send to Qwen Code CLI"),
    session_id: str = Field(default="", description="Resume a previous Qwen session by its ID. Leave empty to start a new session."),
    model: str = Field(default="", description="Qwen model, e.g. 'qwen-plus'. Defaults to the CLI's configured model."),
    timeout_seconds: int = Field(default=120, description="Seconds to wait for a response"),
    project_dir: str = Field(default="", description="Working directory for the CLI. Defaults to current directory."),
) -> dict[str, Any]:
    """Send a prompt to Qwen Code CLI. Returns response, model used, and session_id. Pass session_id to continue a conversation."""
    try:
        return await handle_qwen_prompt(
            prompt=prompt,
            model=model or None,
            timeout_seconds=timeout_seconds,
            project_dir=project_dir or None,
            session_id=session_id or None,
        )
    except OpencodeError as err:
        return _wrap_error(err)


@mcp.tool()
async def opencode_shutdown() -> dict[str, Any]:
    """Gracefully stop the opencode server and close all sessions."""
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
