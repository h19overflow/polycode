from opencode_mcp.routers.gemini import register as register_gemini
from opencode_mcp.routers.opencode import register as register_opencode
from opencode_mcp.routers.qwen import register as register_qwen

__all__ = ["register_gemini", "register_opencode", "register_qwen"]
