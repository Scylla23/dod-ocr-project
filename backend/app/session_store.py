from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field

from app.schema import FieldDef


@dataclass
class SessionState:
    pdf_bytes: bytes
    page_images: list[bytes]
    schema: list[FieldDef]
    values: dict[str, str | list[str]]
    original_extracted: dict[str, str | list[str]]
    extraction_errors: list[int] = field(default_factory=list)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._lock = threading.Lock()

    def create(self, state: SessionState) -> str:
        sid = uuid.uuid4().hex
        with self._lock:
            self._sessions[sid] = state
        return sid

    def get(self, sid: str) -> SessionState:
        with self._lock:
            state = self._sessions.get(sid)
        if state is None:
            raise KeyError(sid)
        return state

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()


# Module-level singleton used by routes; replaced in tests via dependency injection.
store = SessionStore()
