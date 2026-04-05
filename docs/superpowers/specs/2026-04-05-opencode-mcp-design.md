# opencode-mcp Design Spec

**Date:** 2026-04-05  
**Status:** Approved  
**Location:** `C:\Users\User\publicprojects\opencode-mcp\`

---

## 1. Purpose

`opencode-mcp` is a production-grade MCP (Model Context Protocol) server that wraps the `opencode` CLI tool's headless HTTP server. It allows Claude Code (or any MCP client) to programmatically start sessions, send multi-turn prompts, and receive responses from any opencode-supported model — defaulting to `ollama/qwen3.5:cloud`.

---

## 2. Architecture

```
MCP Client (Claude Code)
    │
    │  stdio transport (MCP protocol)
    ▼
opencode-mcp server (Python)
    ├── tools.py          — MCP tool definitions + handlers
    ├── session_manager.py — session registry + history
    ├── opencode_client.py — async HTTP client for opencode REST API
    └── opencode_process.py — opencode subprocess lifecycle manager
    │
    │  HTTP REST API
    ▼
opencode serve --port <N> --model <model>
    (stateful, persistent, one process per MCP server instance)
```

### Key decisions

- **Language:** Python 3.11+
- **Transport:** stdio (standard for local MCP servers, zero config for users)
- **HTTP client:** `httpx` (async)
- **MCP SDK:** `fastmcp` (Pythonic MCP framework, decorator-based tool definitions)
- **Validation:** `pydantic` v2 for all tool inputs
- **opencode process:** one instance spawned at MCP server startup, managed for its full lifetime
- **Sessions:** created on demand, persisted until explicitly closed or server shutdown
- **Default model:** `ollama/qwen3.5:cloud` (overridable via `OPENCODE_DEFAULT_MODEL` env var)

---

## 3. MCP Tools

### `opencode_start_session`
Spawns the opencode server if not already running, then creates a new session.

**Inputs:**
| Field | Type | Required | Default |
|-------|------|----------|---------|
| `project_dir` | `str` | No | Caller's cwd |
| `model` | `str` | No | `OPENCODE_DEFAULT_MODEL` |

**Returns:** `{ session_id: str, model: str, project_dir: str }`

---

### `opencode_send_message`
Sends a prompt to an existing session and blocks until the full response is received.

**Inputs:**
| Field | Type | Required | Default |
|-------|------|----------|---------|
| `session_id` | `str` | Yes | — |
| `message` | `str` | Yes | — |
| `timeout_seconds` | `int` | No | `120` |

**Returns:** `{ response: str, session_id: str, message_index: int, partial: bool }`

---

### `opencode_get_history`
Returns the full message history for a session.

**Inputs:** `session_id: str`

**Returns:** `{ session_id: str, messages: [{ role, content, timestamp }] }`

---

### `opencode_list_sessions`
Lists all active sessions.

**Returns:** `{ sessions: [{ session_id, model, project_dir, message_count, created_at }] }`

---

### `opencode_end_session`
Closes a session and frees its resources.

**Inputs:** `session_id: str`

**Returns:** `{ session_id: str, closed: bool }`

---

### `opencode_list_models`
Lists all models available via the ollama provider (calls `opencode models ollama`).

**Returns:** `{ models: [str], default_model: str }`

---

### `opencode_set_model`
Changes the default model for new sessions. Persists for the MCP server process lifetime.

**Inputs:** `model: str` (format: `provider/model`)

**Returns:** `{ previous_model: str, new_model: str }`

---

### `opencode_shutdown`
Gracefully stops the opencode server process and cleans up all sessions.

**Returns:** `{ stopped: bool, sessions_closed: int }`

---

## 4. Error Handling

### Error Hierarchy

```
OpencodeError (base)
├── OpencodeBinaryNotFoundError
├── OpencodePortError
├── OpencodeModelError
├── OpencodeStartupError
├── OpencodeTimeoutError
├── OpencodeRecoveryError
├── OpencodeSessionError
├── OpencodeValidationError
└── OpencodeProtocolError
```

### Error Response Format

Every error returned to the MCP client is structured:

```json
{
  "error": "OpencodeModelError",
  "message": "Human-readable explanation of what went wrong",
  "detail": { "attempted_model": "...", "available_models": ["..."] },
  "recoverable": true,
  "suggestion": "Call opencode_list_models to see available options"
}
```

### Error Scenarios & Fallbacks

| Scenario | Fallback | Error Type |
|----------|----------|------------|
| `opencode` binary not on PATH | Fail fast at startup with install instructions | `OpencodeBinaryNotFoundError` |
| Port already in use | Auto-retry on 3 random ports, then fail | `OpencodePortError` |
| Model not available | List available models in error | `OpencodeModelError` |
| Server takes >10s to become healthy | Kill process, report with diagnostics | `OpencodeStartupError` |
| Generation times out | Return partial response if available, flag `partial: true` | `OpencodeTimeoutError` |
| opencode process crashes mid-session | Auto-restart, replay last message; surface if replay fails | `OpencodeRecoveryError` |
| Session ID not found | Return active session list in error | `OpencodeSessionError` |
| Invalid tool input (bad model format, bad path) | Pydantic validation before any subprocess call | `OpencodeValidationError` |
| Unexpected REST response schema | Log raw response, raise structured error | `OpencodeProtocolError` |

### Startup Health Check

On server start, the MCP server polls `GET /health` on the opencode REST API every 500ms for up to 10 seconds. If the server does not respond healthy within that window, the process is killed and `OpencodeStartupError` is raised with the captured stderr output.

### Crash Recovery

If the opencode process exits unexpectedly while sessions are active:
1. Log the crash with stderr output
2. Attempt to restart the server (once)
3. If restart succeeds, replay the last message of each active session
4. If restart fails, raise `OpencodeRecoveryError` but preserve all session history in memory so the caller can inspect it

---

## 5. Configuration

All configuration via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENCODE_DEFAULT_MODEL` | `ollama/qwen3.5:cloud` | Default model for new sessions |
| `OPENCODE_PORT` | `0` (random) | Port for opencode server (0 = auto-assign) |
| `OPENCODE_STARTUP_TIMEOUT` | `10` | Seconds to wait for opencode to become healthy |
| `OPENCODE_REQUEST_TIMEOUT` | `120` | Seconds before a generation times out |
| `OPENCODE_LOG_LEVEL` | `INFO` | Log level: DEBUG, INFO, WARN, ERROR |

---

## 6. Project Structure

```
publicprojects/opencode-mcp/
├── opencode_mcp/
│   ├── __init__.py
│   ├── server.py              # MCP server entrypoint (stdio transport)
│   ├── opencode_process.py    # opencode subprocess lifecycle manager
│   ├── opencode_client.py     # async HTTP client for opencode REST API
│   ├── session_manager.py     # session registry + in-memory history
│   ├── tools.py               # MCP tool definitions + handlers
│   └── errors.py              # error hierarchy + structured error formatter
├── tests/
│   ├── conftest.py            # shared fixtures (mock opencode server, mcp client)
│   ├── test_opencode_client.py
│   ├── test_session_manager.py
│   ├── test_tools.py
│   └── test_integration.py    # marked with @pytest.mark.integration
├── pyproject.toml             # installable via pip / uvx
├── .env.example               # documents all env vars
└── README.md                  # quickstart + Claude Code MCP config snippet
```

---

## 7. Installation

### For users

```bash
pip install opencode-mcp
# or (no install needed)
uvx opencode-mcp
```

Requires: `opencode` on PATH (`npm install -g opencode-ai`), Python 3.11+.

### Claude Code MCP config (`~/.claude/mcp_config.json`)

```json
{
  "mcpServers": {
    "opencode": {
      "command": "opencode-mcp",
      "env": {
        "OPENCODE_DEFAULT_MODEL": "ollama/qwen3.5:cloud"
      }
    }
  }
}
```

---

## 8. Testing Strategy

### Tiers

| Tier | Scope | Marker | Requires opencode |
|------|-------|--------|-------------------|
| Unit | `session_manager`, `opencode_client` parsing, error formatting, tool input validation | _(default)_ | No (mocked) |
| Integration | Full tool calls against a real `opencode serve` process | `@pytest.mark.integration` | Yes |
| E2E | Full MCP client ↔ server round-trip | `@pytest.mark.e2e` | Yes |

### Coverage target: 80% core logic

### Test categories per module (5-category framework)

- **Positive:** happy path (session created, message sent, response received)
- **Negative:** bad inputs, missing session, wrong model format
- **Edge:** empty message, very long response, simultaneous sessions
- **Contract:** MCP tool schema matches handler signature, error format is always structured
- **Regression:** crash recovery, timeout with partial response, port retry

---

## 9. Success Criteria

- [ ] Claude Code can start a session, send 3+ messages, and receive coherent responses
- [ ] All 8 MCP tools are callable and return structured output
- [ ] Every error scenario in section 4 returns a structured error (not a raw exception)
- [ ] `pip install opencode-mcp` + MCP config is the only setup a new user needs
- [ ] Unit tests pass without opencode installed
- [ ] Integration tests pass with `opencode` on PATH and `ollama/qwen3.5:cloud` available
