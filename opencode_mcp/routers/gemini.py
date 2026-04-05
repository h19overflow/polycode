from __future__ import annotations

import logging
from typing import Any

from pydantic import Field

from opencode_mcp.errors import OpencodeError, format_error
from opencode_mcp.tools import (
    handle_gemini_check_auth,
    handle_gemini_list_sessions,
    handle_gemini_prompt,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MODEL ROUTING GUIDE
# ---------------------------------------------------------------------------
#   gemini-3-flash-preview    DEFAULT — fast, capable, handles most tasks.
#                             Use for: Q&A, code review, summaries, single-file
#                             edits, writing, straightforward tasks.
#
#   gemini-3.1-pro-preview    COMPLEX — deepest reasoning, best for hard problems.
#                             Use for: architecture design, multi-file refactors,
#                             debugging subtle bugs, long-form analysis, tasks
#                             where quality matters more than speed.
#
#   gemini-2.5-flash-lite     BULK — fastest and cheapest for high volume.
#                             Use for: batch processing, repetitive tasks, simple
#                             lookups, classification, tasks run in a loop.
# ---------------------------------------------------------------------------


def _wrap(err: OpencodeError) -> dict[str, Any]:
    logger.error("Tool error: %s — %s", type(err).__name__, err.message)
    return dict(format_error(err))


def register(mcp: Any) -> None:
    """Register all gemini_* tools onto the FastMCP instance."""

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
            return _wrap(err)

    @mcp.tool()
    async def gemini_prompt(
        prompt: str = Field(
            description=(
                "The full, detailed prompt for Gemini. ALWAYS write in detail — never vague. "
                "Rules: "
                "(1) Include exact file paths for any files involved. "
                "(2) Number each step when asking for multi-step work. "
                "(3) Specify the exact output format: 'return a JSON object with keys X, Y, Z', "
                "'return a markdown table', 'return only the fixed code block'. "
                "(4) Paste the relevant code, error message, or data directly into the prompt — "
                "do not say 'the error' without including it. "
                "Example GOOD: 'Review the following Python function and identify any bugs. "
                "Return a JSON array where each item has fields: line (int), issue (str), fix (str). "
                "Function: def calc(x, y): return x / y' "
                "Example BAD: 'Review my function.'"
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
                "Gemini model to use. Choose based on task complexity:\n"
                "'gemini-3-flash-preview' — DEFAULT. Fast and capable. "
                "Use for: Q&A, code review, summaries, single-file edits, writing.\n"
                "'gemini-3.1-pro-preview' — COMPLEX tasks requiring deep reasoning: "
                "architecture design, multi-file refactors, subtle bug analysis, long-form analysis.\n"
                "'gemini-2.5-flash-lite' — BULK tasks: batch processing, repetitive lookups, "
                "classification, tasks run in a loop where speed and cost matter most.\n"
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
          - Default work    → gemini-3-flash-preview    (fast, capable, most tasks)
          - Complex work    → gemini-3.1-pro-preview    (deep reasoning, architecture, hard bugs)
          - Bulk/batch work → gemini-2.5-flash-lite     (fastest, cheapest, high-volume tasks)

        SESSION CONTINUITY:
          First call returns a session_id. Pass it back on the next call to continue the conversation.
          Gemini persists session history to disk — context is preserved across calls.

        ALWAYS write detailed prompts. Include file paths, numbered steps, and output format.
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
            return _wrap(err)

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
            return _wrap(err)
