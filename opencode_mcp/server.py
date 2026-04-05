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


# ---------------------------------------------------------------------------
# opencode tools
# ---------------------------------------------------------------------------

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
    session_id: str = Field(
        description="Session ID returned by opencode_start_session.",
    ),
    message: str = Field(
        description=(
            "The full, detailed instruction for opencode. "
            "ALWAYS include: (1) exact file paths for every file to read or modify, "
            "(2) step-by-step instructions — one action per step, "
            "(3) expected output format or file structure. "
            "Vague prompts produce vague results. "
            "Example of a GOOD prompt: "
            "'Read C:/projects/app/src/auth.py. "
            "Add a function validate_token(token: str) -> bool that checks the JWT expiry. "
            "Write the result back to the same file. "
            "Return the full updated function as a code block.' "
            "Example of a BAD prompt: 'Fix the auth module.'"
        ),
    ),
    timeout_seconds: int = Field(
        default=int(REQUEST_TIMEOUT),
        description="Seconds to wait for a response. Increase for long code generation tasks.",
    ),
) -> dict[str, Any]:
    """
    Send a detailed instruction to an active opencode session and return the response.

    PROMPTING RULES — always follow these when constructing the message:
    - Specify EXACT file paths (absolute). Never say 'the config file' — say the full path.
    - Break multi-step work into numbered steps within the same message.
    - Specify the output format: 'return a code block', 'return JSON', 'list changed files'.
    - If the task involves multiple files, list all of them explicitly.
    - If you want opencode to run a command, say exactly which command and in which directory.

    Returns: response text, session_id, message_index, partial flag.
    """
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
    session_id: str = Field(description="Session ID to retrieve history for."),
) -> dict[str, Any]:
    """
    Return the full message history for an opencode session (tracked in-process).

    Each message has: role (user/assistant), content, timestamp.
    Use this to review what has been sent and received in a session before sending the next message.
    """
    try:
        return await handle_get_history(session_id=session_id, session_manager=_session_manager)
    except OpencodeError as err:
        return _wrap_error(err)


@mcp.tool()
async def opencode_list_sessions() -> dict[str, Any]:
    """
    List all currently active opencode sessions with their session_id, model, project_dir,
    message count, and creation time.

    Use this to find a session_id if you have lost track of it.
    """
    return await handle_list_sessions(session_manager=_session_manager)


@mcp.tool()
async def opencode_end_session(
    session_id: str = Field(description="Session ID to close."),
) -> dict[str, Any]:
    """
    Close an opencode session and free its resources.

    Call this when a task is complete. Do not leave sessions open indefinitely.
    """
    try:
        return await handle_end_session(session_id=session_id, session_manager=_session_manager)
    except OpencodeError as err:
        return _wrap_error(err)


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
        result["default_model"] = _state["default_model"]
        return result
    except OpencodeError as err:
        return _wrap_error(err)


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
        return await handle_set_model(model=model, state=_state)
    except OpencodeError as err:
        return _wrap_error(err)


# ---------------------------------------------------------------------------
# Gemini CLI tools
# ---------------------------------------------------------------------------
#
# MODEL ROUTING GUIDE — choose the right Gemini model for the job:
#
#   gemini-3-flash-preview    DEFAULT — fast, capable, handles most tasks well.
#                             Use for: standard Q&A, code review, summaries,
#                             writing, single-file edits, straightforward tasks.
#
#   gemini-3.1-pro-preview    COMPLEX — deepest reasoning, best for hard problems.
#                             Use for: architecture design, multi-file refactors,
#                             debugging subtle bugs, long-form analysis, tasks
#                             where quality matters more than speed.
#
#   gemini-2.5-flash-lite     BULK — fastest and cheapest, good for high volume.
#                             Use for: batch processing, repetitive tasks, simple
#                             lookups, classification, tasks run in a loop.
#
# PROMPTING RULES (apply to every gemini_prompt call):
#   1. Be specific — include file paths, function names, class names.
#   2. Number your steps — "Step 1: ..., Step 2: ..." for multi-step tasks.
#   3. State the output format — "return JSON", "return a code block", "list each item".
#   4. Include context — paste the relevant code or error message directly in the prompt.
#   5. Never ask Gemini to "fix it" without explaining what "it" means in full detail.
# ---------------------------------------------------------------------------

@mcp.tool()
async def gemini_check_auth(
    timeout_seconds: int = Field(
        default=15,
        description="Seconds to wait for the auth probe. Increase if the CLI is slow to start.",
    ),
) -> dict[str, Any]:
    """
    Check whether the Gemini CLI is authenticated before making any gemini_prompt calls.

    Always call this first if you are unsure whether Gemini is set up.
    Returns: authenticated (bool), method, detail, suggestion.
    If authenticated is false, read the suggestion field — it contains the exact fix.
    """
    try:
        return await handle_gemini_check_auth(timeout_seconds=timeout_seconds)
    except OpencodeError as err:
        return _wrap_error(err)


@mcp.tool()
async def gemini_prompt(
    prompt: str = Field(
        description=(
            "The full, detailed prompt for Gemini. "
            "ALWAYS write prompts in detail — never vague. Rules: "
            "(1) Include exact file paths for any files involved. "
            "(2) Number each step when asking for multi-step work. "
            "(3) Specify the exact output format: 'return a JSON object with keys X, Y, Z', "
            "'return a markdown table', 'return only the fixed code block'. "
            "(4) Paste the relevant code, error message, or data directly into the prompt — "
            "do not say 'the error' without including it. "
            "Example GOOD prompt: "
            "'Review the following Python function and identify any bugs. "
            "Return a JSON array where each item has fields: line (int), issue (str), fix (str). "
            "Function: def calc(x, y): return x / y' "
            "Example BAD prompt: 'Review my function.'"
        ),
    ),
    session_id: str = Field(
        default="",
        description=(
            "Resume a previous Gemini session by its ID (from a prior gemini_prompt response). "
            "Leave empty to start a fresh session. "
            "Pass the same session_id on every subsequent turn of a multi-turn conversation."
        ),
    ),
    model: str = Field(
        default="gemini-3-flash-preview",
        description=(
            "Gemini model to use. Choose based on task complexity: "
            "'gemini-3-flash-preview' — DEFAULT. Fast and capable. Use for most tasks: "
            "standard Q&A, code review, summaries, single-file edits, writing. "
            "'gemini-3.1-pro-preview' — COMPLEX tasks requiring deep reasoning: "
            "architecture design, multi-file refactors, subtle bug analysis, long-form analysis. "
            "'gemini-2.5-flash-lite' — BULK tasks: batch processing, repetitive lookups, "
            "classification, tasks run in a loop where speed and cost matter most. "
            "Other valid values: 'gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-3.1-flash-lite-preview'."
        ),
    ),
    timeout_seconds: int = Field(
        default=120,
        description=(
            "Seconds to wait for a response. "
            "Increase to 300 for gemini-3.1-pro-preview on complex tasks."
        ),
    ),
    project_dir: str = Field(
        default="",
        description=(
            "Absolute path to the working directory for this call. "
            "Set this when your prompt references files in a specific project. "
            "Example: 'C:/Users/User/projects/myapp'. Defaults to current directory."
        ),
    ),
) -> dict[str, Any]:
    """
    Send a detailed prompt to the Gemini CLI. Returns response text, model used, and session_id.

    MODEL SELECTION:
      - Default work      → gemini-3-flash-preview    (fast, capable, most tasks)
      - Complex work      → gemini-3.1-pro-preview    (deep reasoning, architecture, hard bugs)
      - Bulk/batch work   → gemini-2.5-flash-lite     (fastest, cheapest, high-volume tasks)

    SESSION CONTINUITY:
      First call returns a session_id. Pass it back on the next call to continue the conversation.
      Gemini persists session history to disk — context is preserved across calls.

    ALWAYS write detailed prompts. Include file paths, numbered steps, and output format.
    Vague prompts produce vague results.
    """
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
    project_dir: str = Field(
        default="",
        description="Absolute path to the project directory. Defaults to current directory.",
    ),
    timeout_seconds: int = Field(default=10, description="Seconds to wait."),
) -> dict[str, Any]:
    """
    List saved Gemini CLI sessions for the current project.

    Returns a list of sessions with their index and first-message preview.
    Use this to find a session_id to resume a previous conversation.
    """
    try:
        return await handle_gemini_list_sessions(
            project_dir=project_dir or None,
            timeout_seconds=timeout_seconds,
        )
    except OpencodeError as err:
        return _wrap_error(err)


# ---------------------------------------------------------------------------
# Qwen Code CLI tools
# ---------------------------------------------------------------------------
#
# MODEL ROUTING GUIDE:
#   Pass model= to qwen_prompt to select the model. Available models depend on
#   your Qwen auth tier. With the free OAuth tier, the CLI uses the default
#   'coder-model' automatically.
#
# PROMPTING RULES (same as Gemini — apply to every qwen_prompt call):
#   1. Be specific — include file paths, function names, class names.
#   2. Number your steps for multi-step tasks.
#   3. State the output format explicitly.
#   4. Include the relevant code or error message directly in the prompt.
#   5. Never ask Qwen to "fix it" without full context.
# ---------------------------------------------------------------------------

@mcp.tool()
async def qwen_check_auth(
    timeout_seconds: int = Field(
        default=15,
        description="Seconds to wait for the auth check.",
    ),
) -> dict[str, Any]:
    """
    Check whether the Qwen Code CLI is authenticated before making any qwen_prompt calls.

    Always call this first if you are unsure whether Qwen is set up.
    Returns: authenticated (bool), method (qwen-oauth / coding-plan / api-key), detail, suggestion.
    If authenticated is false, read the suggestion field — it contains the exact command to run.
    """
    try:
        return await handle_qwen_check_auth(timeout_seconds=timeout_seconds)
    except OpencodeError as err:
        return _wrap_error(err)


@mcp.tool()
async def qwen_prompt(
    prompt: str = Field(
        description=(
            "The full, detailed prompt for Qwen Code. "
            "ALWAYS write prompts in detail — never vague. Rules: "
            "(1) Include exact file paths for any files involved. "
            "(2) Number each step when asking for multi-step work. "
            "(3) Specify the exact output format: 'return a JSON object', "
            "'return only the modified function as a code block', 'list changed files'. "
            "(4) Paste the relevant code, error message, or data directly into the prompt. "
            "Example GOOD prompt: "
            "'Read C:/projects/app/utils/parser.py. "
            "Step 1: Find the function parse_date(s: str). "
            "Step 2: Add handling for ISO 8601 format (YYYY-MM-DDTHH:MM:SS). "
            "Step 3: Return the complete updated function as a Python code block.' "
            "Example BAD prompt: 'Fix the date parser.'"
        ),
    ),
    session_id: str = Field(
        default="",
        description=(
            "Resume a previous Qwen session by its ID (from a prior qwen_prompt response). "
            "Leave empty to start a fresh session. "
            "Pass the same session_id on every subsequent turn of a multi-turn conversation. "
            "Qwen persists session history to disk when --chat-recording is enabled (always on here)."
        ),
    ),
    model: str = Field(
        default="",
        description=(
            "Qwen model to use. Leave empty to use the CLI's default model (recommended). "
            "The default model is determined by your auth tier: "
            "Free OAuth tier uses the latest Qwen coder model automatically. "
            "To specify explicitly, use values like 'qwen-plus', 'qwen-max', 'qwen-turbo'. "
            "Use 'qwen-max' for complex reasoning tasks, 'qwen-turbo' for fast bulk tasks."
        ),
    ),
    timeout_seconds: int = Field(
        default=120,
        description=(
            "Seconds to wait for a response. "
            "Increase to 300 for long multi-step tasks."
        ),
    ),
    project_dir: str = Field(
        default="",
        description=(
            "Absolute path to the working directory for this call. "
            "Set this when your prompt references files in a specific project. "
            "Example: 'C:/Users/User/projects/myapp'. Defaults to current directory."
        ),
    ),
) -> dict[str, Any]:
    """
    Send a detailed prompt to the Qwen Code CLI. Returns response text, model used, and session_id.

    SESSION CONTINUITY:
      First call returns a session_id. Pass it back on the next call to continue the conversation.
      Qwen persists session history to disk — context is preserved across calls.

    ALWAYS write detailed prompts. Include file paths, numbered steps, and output format.
    Vague prompts produce vague results.
    """
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
