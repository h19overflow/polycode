from __future__ import annotations

import logging
from typing import Any

from pydantic import Field

from opencode_mcp.errors import OpencodeError, format_error
from opencode_mcp.tools import (
    handle_qwen_check_auth,
    handle_qwen_prompt,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MODEL ROUTING GUIDE
# ---------------------------------------------------------------------------
#   (empty string)    DEFAULT — CLI picks the best model for your auth tier
#                     automatically. Free OAuth tier uses the latest Qwen coder
#                     model. Recommended for most tasks.
#
#   'qwen-max'        COMPLEX — highest capability. Use for architecture design,
#                     multi-file refactors, deep analysis, hard debugging.
#
#   'qwen-plus'       STANDARD — balanced capability and speed. Use for most
#                     coding tasks, code review, writing, summaries.
#
#   'qwen-turbo'      BULK — fastest and cheapest. Use for batch processing,
#                     repetitive tasks, classification, tasks run in a loop.
# ---------------------------------------------------------------------------


def _wrap(err: OpencodeError) -> dict[str, Any]:
    logger.error("Tool error: %s — %s", type(err).__name__, err.message)
    return dict(format_error(err))


def register(mcp: Any) -> None:
    """Register all qwen_* tools onto the FastMCP instance."""

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
            return _wrap(err)

    @mcp.tool()
    async def qwen_prompt(
        prompt: str = Field(
            description=(
                "The full, detailed prompt for Qwen Code. ALWAYS write in detail — never vague. "
                "Rules: "
                "(1) Include exact file paths for any files involved. "
                "(2) Number each step when asking for multi-step work. "
                "(3) Specify the exact output format: 'return a JSON object', "
                "'return only the modified function as a code block', 'list changed files'. "
                "(4) Paste the relevant code, error message, or data directly into the prompt. "
                "Example GOOD: 'Read C:/projects/app/utils/parser.py. "
                "Step 1: Find the function parse_date(s: str). "
                "Step 2: Add handling for ISO 8601 format (YYYY-MM-DDTHH:MM:SS). "
                "Step 3: Return the complete updated function as a Python code block.' "
                "Example BAD: 'Fix the date parser.'"
            ),
        ),
        session_id: str = Field(
            default="",
            description=(
                "Resume a previous Qwen session by its ID (from a prior qwen_prompt response). "
                "Leave empty to start a fresh session. "
                "Pass the same session_id on every subsequent turn of a multi-turn conversation. "
                "Qwen persists session history to disk — context is preserved across calls."
            ),
        ),
        model: str = Field(
            default="",
            description=(
                "Qwen model to use. Leave empty to use the CLI default (recommended).\n"
                "'' (empty) — DEFAULT. CLI picks the best model for your auth tier automatically.\n"
                "'qwen-max'   — COMPLEX tasks: architecture, multi-file refactors, deep analysis.\n"
                "'qwen-plus'  — STANDARD: balanced capability and speed for most coding tasks.\n"
                "'qwen-turbo' — BULK: fastest and cheapest for batch/repetitive/loop tasks."
            ),
        ),
        timeout_seconds: int = Field(
            default=120,
            description=(
                "Seconds to wait for a response. "
                "Increase to 300 for qwen-max on complex tasks."
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

        MODEL SELECTION:
          - Default work    → leave model empty  (CLI picks best for your tier)
          - Complex work    → qwen-max            (deep reasoning, architecture, hard bugs)
          - Standard work   → qwen-plus           (balanced, most coding tasks)
          - Bulk/batch work → qwen-turbo          (fastest, cheapest, high-volume tasks)

        SESSION CONTINUITY:
          First call returns a session_id. Pass it back on the next call to continue the conversation.
          Qwen persists session history to disk — context is preserved across calls.

        ALWAYS write detailed prompts. Include file paths, numbered steps, and output format.
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
            return _wrap(err)
