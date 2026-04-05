import pytest
from opencode_mcp.errors import (
    OpencodeError,
    OpencodeBinaryNotFoundError,
    OpencodePortError,
    OpencodeModelError,
    OpencodeStartupError,
    OpencodeTimeoutError,
    OpencodeRecoveryError,
    OpencodeSessionError,
    OpencodeValidationError,
    OpencodeProtocolError,
    format_error,
)


def test_all_errors_are_subclasses_of_base():
    errors = [
        OpencodeBinaryNotFoundError,
        OpencodePortError,
        OpencodeModelError,
        OpencodeStartupError,
        OpencodeTimeoutError,
        OpencodeRecoveryError,
        OpencodeSessionError,
        OpencodeValidationError,
        OpencodeProtocolError,
    ]
    for error_class in errors:
        assert issubclass(error_class, OpencodeError)


def test_format_error_returns_required_fields():
    err = OpencodeModelError("Model not found", detail={"attempted": "bad/model"}, recoverable=True, suggestion="Call opencode_list_models")
    result = format_error(err)
    assert result["error"] == "OpencodeModelError"
    assert result["message"] == "Model not found"
    assert result["detail"] == {"attempted": "bad/model"}
    assert result["recoverable"] is True
    assert result["suggestion"] == "Call opencode_list_models"


def test_format_error_defaults():
    err = OpencodeSessionError("Session not found")
    result = format_error(err)
    assert result["error"] == "OpencodeSessionError"
    assert result["message"] == "Session not found"
    assert result["detail"] == {}
    assert result["recoverable"] is False
    assert result["suggestion"] == ""


def test_binary_not_found_includes_install_hint():
    err = OpencodeBinaryNotFoundError()
    result = format_error(err)
    assert "npm install -g opencode-ai" in result["suggestion"]
