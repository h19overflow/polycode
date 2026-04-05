# opencode-mcp

A production-grade MCP (Model Context Protocol) server that wraps [opencode](https://opencode.ai)'s headless HTTP server, giving Claude Code (or any MCP client) 8 tools to start sessions, send multi-turn prompts, and manage models — defaulting to `ollama/qwen3.5:cloud`.

## Requirements

- Python 3.11+
- [opencode](https://opencode.ai) on PATH: `npm install -g opencode-ai`
- Ollama running locally (for `ollama/qwen3.5:cloud` and other ollama models)

## Installation

```bash
pip install opencode-mcp
```

Or run without installing (requires `uv`):

```bash
uvx opencode-mcp
```

## Claude Code Setup

Add to `~/.claude/mcp_config.json`:

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

Then restart Claude Code. The 8 `opencode_*` tools will appear automatically.

## Quick Start

Once configured, Claude Code can use opencode like this:

1. **Start a session** — `opencode_start_session` with your project path
2. **Send messages** — `opencode_send_message` with your prompt, get the response
3. **Check history** — `opencode_get_history` to review the conversation
4. **Switch models** — `opencode_set_model` then start a new session
5. **Clean up** — `opencode_end_session` or `opencode_shutdown`

## Available Tools

| Tool | Description |
|------|-------------|
| `opencode_start_session` | Start a new session. Returns `session_id`. |
| `opencode_send_message` | Send a prompt. Returns the response text. |
| `opencode_get_history` | Get full message history for a session. |
| `opencode_list_sessions` | List all active sessions. |
| `opencode_end_session` | Close a session and free its resources. |
| `opencode_list_models` | List available ollama models. |
| `opencode_set_model` | Change the default model for new sessions. |
| `opencode_shutdown` | Stop the opencode server gracefully. |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENCODE_DEFAULT_MODEL` | `ollama/qwen3.5:cloud` | Default model for new sessions |
| `OPENCODE_PORT` | `0` (random) | Port for the opencode server |
| `OPENCODE_STARTUP_TIMEOUT` | `10` | Seconds to wait for opencode to start |
| `OPENCODE_REQUEST_TIMEOUT` | `120` | Seconds before a generation times out |
| `OPENCODE_LOG_LEVEL` | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR |
| `OPENCODE_SERVER_PASSWORD` | _(unset)_ | Optional HTTP Basic Auth password |

## Error Handling

All tools return structured errors — never raw exceptions:

```json
{
  "error": "OpencodeModelError",
  "message": "Model 'bad/model' is not available",
  "detail": { "attempted_model": "bad/model" },
  "recoverable": true,
  "suggestion": "Call opencode_list_models to see available options"
}
```

## Running Tests

```bash
# Unit tests — no opencode or ollama required
pytest tests/ --ignore=tests/test_integration.py

# Integration tests — requires opencode + ollama running
pytest tests/test_integration.py -m integration -v
```

## Contributing

```bash
git clone https://github.com/h19overflow/opencode-mcp
cd opencode-mcp
pip install -e ".[dev]"
pytest tests/ --ignore=tests/test_integration.py
```

## License

MIT
