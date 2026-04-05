from __future__ import annotations

import logging
import os
from typing import Any, Callable

from pydantic import Field

from opencode_mcp.errors import OpencodeError, format_error
from opencode_mcp.tools import (
    handle_end_session,
    handle_get_history,
    handle_list_models,
    handle_list_sessions,
    handle_send_message,
    handle_set_model,
    handle_start_session,
)

logger = logging.getLogger(__name__)


def _wrap(err: OpencodeError) -> dict[str, Any]:
    logger.error("Tool error: %s — %s", type(err).__name__, err.message)
    return dict(format_error(err))


def register(
    mcp: Any,
    *,
    state: dict[str, Any],
    get_client: Callable,
    process: Any,
    session_manager: Any,
    request_timeout: float,
) -> None:
    """Register all opencode_* tools (except shutdown) onto the FastMCP instance."""

    @mcp.tool()
    async def opencode_start_session(
        project_dir: str = Field(
            default="",
            description=(
                "Absolute path to the project directory the agent will work in. "
                "Example: 'C:/Users/User/projects/myapp'. "
                "Defaults to current working directory if omitted."
            ),
        ),
        model: str = Field(
            default="",
            description=(
                "Model in 'provider/model' format. "
                "Call opencode_list_models to see all available models. "
                "Defaults to OPENCODE_DEFAULT_MODEL env var if omitted."
            ),
        ),
    ) -> dict[str, Any]:
        """
        Start a new opencode session. Call this before opencode_send_message.

        Returns session_id, model, and project_dir. Store session_id — every subsequent
        call to opencode_send_message requires it.

        Use opencode for coding tasks: writing, editing, refactoring, debugging, explaining code.
        For tasks requiring reasoning or research, prefer gemini_prompt or qwen_prompt instead.
        """
        resolved_dir = project_dir or os.getcwd()
        resolved_model = model or state["default_model"]
        if not process.is_running:
            await process.start()
        try:
            return await handle_start_session(
                project_dir=resolved_dir,
                model=resolved_model,
                session_manager=session_manager,
                client=get_client(),
                process=process,
                default_model=state["default_model"],
            )
        except OpencodeError as err:
            return _wrap(err)

    @mcp.tool()
    async def opencode_send_message(
        session_id: str = Field(description="Session ID returned by opencode_start_session."),
        message: str = Field(
            description=(
                "The full, detailed instruction for opencode. "
                "ALWAYS include: (1) exact file paths for every file to read or modify, "
                "(2) step-by-step instructions — one action per step, "
                "(3) expected output format or file structure. "
                "Vague prompts produce vague results. "
                "Example GOOD: 'Read C:/projects/app/src/auth.py. "
                "Add function validate_token(token: str) -> bool checking JWT expiry. "
                "Write back to the same file. Return the updated function as a code block.' "
                "Example BAD: 'Fix the auth module.'"
            ),
        ),
        timeout_seconds: int = Field(
            default=int(request_timeout),
            description="Seconds to wait for a response. Increase for long code generation tasks.",
        ),
    ) -> dict[str, Any]:
        """
        Send a detailed instruction to an active opencode session and return the response.

        PROMPTING RULES:
        - Specify EXACT file paths (absolute). Never say 'the config file' — say the full path.
        - Break multi-step work into numbered steps within the same message.
        - Specify the output format: 'return a code block', 'return JSON', 'list changed files'.
        - If the task involves multiple files, list all of them explicitly.
        - If you want opencode to run a command, say exactly which command and in which directory.
        """
        try:
            return await handle_send_message(
                session_id=session_id,
                message=message,
                timeout_seconds=timeout_seconds,
                session_manager=session_manager,
                client=get_client(),
            )
        except OpencodeError as err:
            return _wrap(err)

    @mcp.tool()
    async def opencode_get_history(
        session_id: str = Field(description="Session ID to retrieve history for."),
    ) -> dict[str, Any]:
        """
        Return the full message history for an opencode session (tracked in-process).

        Each message has: role (user/assistant), content, timestamp.
        Use this to review what has been sent and received before sending the next message.
        """
        try:
            return await handle_get_history(session_id=session_id, session_manager=session_manager)
        except OpencodeError as err:
            return _wrap(err)

    @mcp.tool()
    async def opencode_list_sessions() -> dict[str, Any]:
        """
        List all currently active opencode sessions with session_id, model, project_dir,
        message count, and creation time.

        Use this to find a session_id if you have lost track of it.
        """
        return await handle_list_sessions(session_manager=session_manager)

    @mcp.tool()
    async def opencode_end_session(
        session_id: str = Field(description="Session ID to close."),
    ) -> dict[str, Any]:
        """
        Close an opencode session and free its resources.

        Call this when a task is complete. Do not leave sessions open indefinitely.
        """
        try:
            return await handle_end_session(session_id=session_id, session_manager=session_manager)
        except OpencodeError as err:
            return _wrap(err)

    @mcp.tool()
    async def opencode_list_models() -> dict[str, Any]:
        """
        List all models available in opencode across all connected providers, grouped by provider.

        Only providers you are authenticated with will return models.
        Returns: models (flat list), by_provider (grouped dict), total count, default_model.

        Use this before opencode_start_session to pick the right model for the task.
        """
        try:
            result = await handle_list_models()
            result["default_model"] = state["default_model"]
            return result
        except OpencodeError as err:
            return _wrap(err)

    @mcp.tool()
    async def opencode_set_model(
        model: str = Field(
            description=(
                "Model in 'provider/model' format. "
                "Call opencode_list_models to see valid options. "
                "Example: 'ollama/qwen3.5:cloud', 'openai/gpt-4o', 'google/gemini-2.5-flash'."
            ),
        ),
    ) -> dict[str, Any]:
        """
        Change the default model used for all new opencode sessions.

        Takes effect immediately for all subsequent opencode_start_session calls.
        Does not affect already-open sessions.
        """
        try:
            return await handle_set_model(model=model, state=state)
        except OpencodeError as err:
            return _wrap(err)
