from __future__ import annotations

import asyncio
import logging
from typing import Any

from opencode_mcp.core.client import OpencodeClient
from opencode_mcp.core.process import OpencodeProcess
from opencode_mcp.helpers.cli_runner import (
    check_gemini_auth,
    check_qwen_auth,
    list_gemini_sessions,
    run_gemini_prompt,
    run_qwen_prompt,
)
from opencode_mcp.helpers.models import list_all_models
from opencode_mcp.helpers.validation import validate_model_format
from opencode_mcp.session_manager import SessionManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# opencode session tools
# ---------------------------------------------------------------------------

async def handle_start_session(
    project_dir: str,
    model: str,
    session_manager: SessionManager,
    client: OpencodeClient,
    process: OpencodeProcess,
    default_model: str,
) -> dict[str, Any]:
    validate_model_format(model)
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
    logger.info("Sending message to session %s", session_id)
    session_manager.get_session(session_id)
    session_manager.add_message(session_id, role="user", content=message)
    result = await client.send_message(session_id=session_id, message=message, timeout=float(timeout_seconds))
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


async def handle_list_models() -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, list_all_models)


async def handle_set_model(model: str, state: dict[str, Any]) -> dict[str, Any]:
    validate_model_format(model)
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


# ---------------------------------------------------------------------------
# Gemini CLI tools
# ---------------------------------------------------------------------------

async def handle_gemini_prompt(
    prompt: str,
    model: str | None,
    timeout_seconds: int,
    project_dir: str | None,
    session_id: str | None = None,
) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: run_gemini_prompt(prompt, model, float(timeout_seconds), project_dir, session_id),
    )


async def handle_gemini_check_auth(timeout_seconds: int) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: check_gemini_auth(float(timeout_seconds)),
    )


async def handle_gemini_list_sessions(
    project_dir: str | None,
    timeout_seconds: int,
) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    sessions = await loop.run_in_executor(
        None,
        lambda: list_gemini_sessions(project_dir, float(timeout_seconds)),
    )
    return {"sessions": sessions}


# ---------------------------------------------------------------------------
# Qwen CLI tools
# ---------------------------------------------------------------------------

async def handle_qwen_prompt(
    prompt: str,
    model: str | None,
    timeout_seconds: int,
    project_dir: str | None,
    session_id: str | None = None,
) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: run_qwen_prompt(prompt, model, float(timeout_seconds), project_dir, session_id),
    )


async def handle_qwen_check_auth(timeout_seconds: int) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: check_qwen_auth(float(timeout_seconds)),
    )
