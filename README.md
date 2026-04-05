# opencode-mcp

A production-grade MCP (Model Context Protocol) server that lets Claude Code (or any MCP client) control [opencode](https://opencode.ai) — an AI coding agent — programmatically. Start sessions, send multi-turn prompts, and get responses back as structured tool results.

**Default model:** `ollama/qwen3.5:cloud`  
**Supports:** Any model opencode supports — Ollama, OpenAI, Anthropic, Gemini, and 70+ others.

---

## How It Works

```
Claude Code
    │  calls tools (MCP stdio)
    ▼
opencode-mcp server  (this package — auto-started by Claude Code)
    │  spawns + manages
    ▼
opencode serve  (headless HTTP server)
    │  sends prompts to
    ▼
ollama/qwen3.5:cloud  (or any model)
```

You talk to Claude Code. Claude Code auto-starts this MCP server when needed, which in turn spawns the opencode HTTP server. You never start anything manually.

---

## Requirements

Before installing, you need:

1. **Python 3.11+**
   ```bash
   python --version  # must be 3.11 or higher
   ```

2. **opencode CLI**
   ```bash
   npm install -g opencode-ai
   opencode --version  # verify: should print 1.x.x
   ```

3. **A model provider** — for `ollama/qwen3.5:cloud` (the default), Ollama must be running locally:
   ```bash
   ollama list  # should show your installed models
   ```
   To use OpenAI, Anthropic, or another provider instead, see [Changing the Model](#changing-the-model).

---

## Installation

```bash
pip install opencode-mcp
```

Or without installing (requires `uv`):

```bash
uvx opencode-mcp
```

Verify it works:

```bash
opencode-mcp --help
```

---

## Claude Code Setup

Claude Code automatically starts and stops the MCP server — you never run it manually. All you do is register it once in your config.

### Step 1 — Find your Claude config file

| Platform | Path |
|----------|------|
| Windows | `C:\Users\<you>\.claude.json` |
| macOS / Linux | `~/.claude.json` |

### Step 2 — Add the MCP server

Open `~/.claude.json` and add an `mcpServers` entry. If the key doesn't exist yet, create it.

**macOS / Linux:**
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

**Windows** — use the full path to the binary (find it with `where opencode-mcp`):
```json
{
  "mcpServers": {
    "opencode": {
      "command": "C:\\Users\\YourName\\AppData\\Local\\Programs\\Python\\Python313\\Scripts\\opencode-mcp.exe",
      "env": {
        "OPENCODE_DEFAULT_MODEL": "ollama/qwen3.5:cloud"
      }
    }
  }
}
```

### Step 3 — Restart Claude Code

The 8 `opencode_*` tools will appear automatically. From that point on:
- Claude Code starts `opencode-mcp` when the session begins
- `opencode-mcp` spawns `opencode serve` on first tool call
- Everything shuts down cleanly when Claude Code exits

You never have to start or stop anything manually.

---

## Gemini CLI Setup

**Config file:** `~/.gemini/settings.json` (user-level) or `.gemini/settings.json` (project-level)

**macOS / Linux:**
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

**Windows** — use the full path (find it with `where opencode-mcp`):
```json
{
  "mcpServers": {
    "opencode": {
      "command": "C:\\Users\\YourName\\AppData\\Local\\Programs\\Python\\Python313\\Scripts\\opencode-mcp.exe",
      "env": {
        "OPENCODE_DEFAULT_MODEL": "ollama/qwen3.5:cloud"
      }
    }
  }
}
```

Restart Gemini CLI after saving. Verify with `/mcp list` — `opencode` should appear as connected.

---

## Qwen Code Setup

**Qwen Code** ([QwenLM/qwen-code](https://github.com/QwenLM/qwen-code)) is Alibaba's coding CLI, a fork of Gemini CLI tuned for Qwen models.

**Config file:** `~/.qwen/settings.json` (user-level) or `.qwen/settings.json` (project-level)

**macOS / Linux:**
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

**Windows** — use the full path:
```json
{
  "mcpServers": {
    "opencode": {
      "command": "C:\\Users\\YourName\\AppData\\Local\\Programs\\Python\\Python313\\Scripts\\opencode-mcp.exe",
      "env": {
        "OPENCODE_DEFAULT_MODEL": "ollama/qwen3.5:cloud"
      }
    }
  }
}
```

Optionally restrict which MCP servers are active with the `mcp.allowed` list:
```json
{
  "mcpServers": { ... },
  "mcp": {
    "allowed": ["opencode"]
  }
}
```

Restart Qwen Code after saving. The `opencode_*` tools will appear automatically.

---

## Using the Tools

### Typical workflow

```
1. opencode_start_session   → get a session_id
2. opencode_send_message    → send a prompt, get a response
3. opencode_send_message    → continue the conversation
4. opencode_get_history     → review the full exchange
5. opencode_end_session     → close when done
```

### All 8 tools

#### `opencode_start_session`
Start a new opencode session. Returns a `session_id` you use for all subsequent calls.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_dir` | string | No | Absolute path to your project. Defaults to current working directory. |
| `model` | string | No | Model in `provider/model` format. Defaults to `OPENCODE_DEFAULT_MODEL`. |

**Returns:**
```json
{
  "session_id": "ses_2a29...",
  "model": "ollama/qwen3.5:cloud",
  "project_dir": "/path/to/project"
}
```

---

#### `opencode_send_message`
Send a prompt to an active session. Blocks until opencode finishes responding.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | Yes | Session ID from `opencode_start_session`. |
| `message` | string | Yes | Your prompt. |
| `timeout_seconds` | int | No | How long to wait for a response. Default: `120`. |

**Returns:**
```json
{
  "response": "Here is the updated function...",
  "session_id": "ses_2a29...",
  "message_index": 1,
  "partial": false
}
```

---

#### `opencode_get_history`
Retrieve the full message history for a session.

| Parameter | Type | Required |
|-----------|------|----------|
| `session_id` | string | Yes |

**Returns:**
```json
{
  "session_id": "ses_2a29...",
  "messages": [
    {"role": "user", "content": "...", "timestamp": "2026-04-05T19:00:00Z"},
    {"role": "assistant", "content": "...", "timestamp": "2026-04-05T19:00:05Z"}
  ]
}
```

---

#### `opencode_list_sessions`
List all active sessions.

**Returns:**
```json
{
  "sessions": [
    {
      "session_id": "ses_2a29...",
      "model": "ollama/qwen3.5:cloud",
      "project_dir": "/path/to/project",
      "message_count": 4,
      "created_at": "2026-04-05T19:00:00Z"
    }
  ]
}
```

---

#### `opencode_end_session`
Close a session and free its resources.

| Parameter | Type | Required |
|-----------|------|----------|
| `session_id` | string | Yes |

**Returns:** `{"session_id": "ses_2a29...", "closed": true}`

---

#### `opencode_list_models`
List all available models from the ollama provider.

**Returns:**
```json
{
  "models": ["ollama/qwen3.5:cloud", "ollama/kimi-k2.5:cloud"],
  "default_model": "ollama/qwen3.5:cloud"
}
```

---

#### `opencode_set_model`
Change the default model for new sessions. Takes effect immediately for all subsequent `opencode_start_session` calls.

| Parameter | Type | Required | Example |
|-----------|------|----------|---------|
| `model` | string | Yes | `ollama/qwen3.5:cloud` |

**Returns:** `{"previous_model": "ollama/...", "new_model": "ollama/..."}`

---

#### `opencode_shutdown`
Gracefully stop the opencode server and close all active sessions.

**Returns:** `{"stopped": true, "sessions_closed": 2}`

---

## Changing the Model

The model format is `provider/model-name`. Set it via env var in your MCP config:

```json
"env": {
  "OPENCODE_DEFAULT_MODEL": "openai/gpt-4o"
}
```

Or call `opencode_set_model` at runtime.

**Common models:**

| Provider | Model string |
|----------|-------------|
| Ollama (local) | `ollama/qwen3.5:cloud` |
| Ollama (local) | `ollama/llama3.2:latest` |
| OpenAI | `openai/gpt-4o` |
| Anthropic | `anthropic/claude-sonnet-4-5` |
| Google | `google/gemini-2.0-flash` |

To see what's available on your ollama installation, call `opencode_list_models`.

---

## Configuration

All configuration is via environment variables in your MCP config's `env` block:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENCODE_DEFAULT_MODEL` | `ollama/qwen3.5:cloud` | Default model for new sessions |
| `OPENCODE_PORT` | `0` (random) | Port for the opencode server. `0` picks a free port automatically. |
| `OPENCODE_STARTUP_TIMEOUT` | `10` | Seconds to wait for opencode to start before giving up |
| `OPENCODE_REQUEST_TIMEOUT` | `120` | Seconds before a slow generation times out |
| `OPENCODE_LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `OPENCODE_SERVER_PASSWORD` | _(unset)_ | Optional HTTP Basic Auth password for the opencode server |

---

## Error Handling

Every tool always returns a structured response — never a raw exception. If something goes wrong, you get:

```json
{
  "error": "OpencodeModelError",
  "message": "Model 'bad/model' is not available",
  "detail": { "attempted_model": "bad/model" },
  "recoverable": true,
  "suggestion": "Call opencode_list_models to see available options"
}
```

The `recoverable` field tells you whether retrying makes sense. The `suggestion` field tells you what to do next.

**Common errors and fixes:**

| Error | Cause | Fix |
|-------|-------|-----|
| `OpencodeBinaryNotFoundError` | `opencode` not on PATH | Run `npm install -g opencode-ai` |
| `OpencodeStartupError` | opencode failed to start | Check `opencode serve` runs manually; try increasing `OPENCODE_STARTUP_TIMEOUT` |
| `OpencodeModelError` | Model not available | Call `opencode_list_models` to see what's available |
| `OpencodeTimeoutError` | Generation took too long | Increase `OPENCODE_REQUEST_TIMEOUT` or simplify your prompt |
| `OpencodeSessionError` | Session ID not found | Call `opencode_list_sessions` to see active sessions |
| `OpencodeValidationError` | Bad input (e.g. wrong model format) | Model must be `provider/model` — e.g. `ollama/qwen3.5:cloud` |

---

## Troubleshooting

### "opencode-mcp not found" on Windows

Use the full path in your MCP config. Find it with:
```powershell
where opencode-mcp
```
Then use that full path (with double backslashes) as the `command` value.

### opencode server times out on startup

The cloud models (`qwen3.5:cloud`, `kimi-k2.5:cloud`) do a network handshake on first request. If startup is slow, increase the timeout:
```json
"env": {
  "OPENCODE_STARTUP_TIMEOUT": "30"
}
```

### Tools appear but calls hang or time out

This can happen if the opencode subprocess inherits a blocked stdin. Make sure you're on `opencode-mcp >= 0.1.0` which explicitly sets `stdin=DEVNULL` on all subprocesses — a fix required for Windows MCP stdio environments.

### Seeing fewer models than expected

`opencode_list_models` only lists **ollama** models. For OpenAI, Anthropic, or other providers, set the model directly with `opencode_set_model` using the `provider/model` format.

---

## Running Tests

```bash
# Clone and install
git clone https://github.com/h19overflow/opencode-mcp
cd opencode-mcp
pip install -e ".[dev]"

# Unit tests — no opencode or ollama required
pytest tests/ --ignore=tests/test_integration.py -v

# Integration tests — requires opencode + ollama running locally
pytest tests/test_integration.py -m integration -v
```

---

## Contributing

1. Fork the repo
2. Install dev deps: `pip install -e ".[dev]"`
3. Write tests first (TDD)
4. Run `pytest tests/ --ignore=tests/test_integration.py` before submitting
5. Open a PR

---

## License

MIT — see [LICENSE](LICENSE)
