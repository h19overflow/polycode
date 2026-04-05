from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from opencode_mcp.errors import OpencodeSessionError


@dataclass
class Session:
    session_id: str
    model: str
    project_dir: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    _messages: list[dict[str, Any]] = field(default_factory=list, repr=False)

    @property
    def message_count(self) -> int:
        return len(self._messages)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create_session(self, session_id: str, model: str, project_dir: str) -> Session:
        session = Session(session_id=session_id, model=model, project_dir=project_dir)
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            active_ids = list(self._sessions.keys())
            raise OpencodeSessionError(
                message=f"Session '{session_id}' not found",
                detail={"active_sessions": active_ids},
                recoverable=True,
                suggestion=f"Active sessions: {active_ids}. Call opencode_list_sessions to see all.",
            )
        return self._sessions[session_id]

    def add_message(self, session_id: str, role: str, content: str) -> None:
        session = self.get_session(session_id)
        session._messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_history(self, session_id: str) -> list[dict[str, Any]]:
        session = self.get_session(session_id)
        return list(session._messages)

    def close_session(self, session_id: str) -> None:
        self.get_session(session_id)
        del self._sessions[session_id]

    def list_sessions(self) -> list[dict[str, Any]]:
        return [
            {
                "session_id": s.session_id,
                "model": s.model,
                "project_dir": s.project_dir,
                "message_count": s.message_count,
                "created_at": s.created_at,
            }
            for s in self._sessions.values()
        ]

    def close_all_sessions(self) -> int:
        count = len(self._sessions)
        self._sessions.clear()
        return count
