from __future__ import annotations


class OpencodeError(Exception):
    def __init__(
        self,
        message: str = "",
        detail: dict | None = None,
        recoverable: bool = False,
        suggestion: str = "",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}
        self.recoverable = recoverable
        self.suggestion = suggestion


class OpencodeBinaryNotFoundError(OpencodeError):
    def __init__(self, message: str = "opencode binary not found on PATH") -> None:
        super().__init__(
            message=message,
            recoverable=False,
            suggestion="Install opencode via: npm install -g opencode-ai",
        )


class OpencodePortError(OpencodeError):
    def __init__(self, message: str = "", ports: list[int] | None = None) -> None:
        super().__init__(
            message=message or "Could not bind opencode server to any available port",
            detail={"attempted_ports": ports or []},
            recoverable=False,
            suggestion="Free a port or set OPENCODE_PORT to a specific available port",
        )


class OpencodeModelError(OpencodeError):
    pass


class OpencodeStartupError(OpencodeError):
    pass


class OpencodeTimeoutError(OpencodeError):
    def __init__(self, message: str = "", partial: str = "") -> None:
        super().__init__(
            message=message or "Response timed out",
            detail={"partial_response": partial},
            recoverable=True,
            suggestion="Increase OPENCODE_REQUEST_TIMEOUT or simplify your prompt",
        )


class OpencodeRecoveryError(OpencodeError):
    pass


class OpencodeSessionError(OpencodeError):
    pass


class OpencodeValidationError(OpencodeError):
    pass


class OpencodeProtocolError(OpencodeError):
    pass


def format_error(err: OpencodeError) -> dict:
    return {
        "error": type(err).__name__,
        "message": err.message,
        "detail": err.detail,
        "recoverable": err.recoverable,
        "suggestion": err.suggestion,
    }
