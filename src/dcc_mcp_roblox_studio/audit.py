"""Bounded operation audit trail for the Roblox Studio adapter."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from threading import RLock
from time import perf_counter
from typing import Any, Deque, Dict, Optional, Tuple
from uuid import uuid4

_SENSITIVE_KEYS = {"source", "new_source", "script", "code", "content"}


def _redact(value: Any, key: str = "") -> Any:
    if key.lower() in _SENSITIVE_KEYS:
        return "[redacted]"
    if isinstance(value, dict):
        return {str(name): _redact(item, str(name)) for name, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


class OperationAudit:
    """Store recent adapter operations without retaining source content."""

    def __init__(self, max_entries: int = 1000) -> None:
        self._entries: Deque[Dict[str, Any]] = deque(maxlen=max_entries)
        self._lock = RLock()

    def begin(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[str, float, str]:
        """Create an operation ID and capture its start metadata."""
        return str(uuid4()), perf_counter(), datetime.now(timezone.utc).isoformat()

    def finish(
        self,
        operation_id: str,
        started_at: float,
        started_iso: str,
        tool_name: str,
        arguments: Dict[str, Any],
        *,
        success: bool,
        result: Any = None,
        error: Optional[str] = None,
        dry_run: bool = False,
    ) -> None:
        entry: Dict[str, Any] = {
            "operation_id": operation_id,
            "tool": tool_name,
            "started_at": started_iso,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": round((perf_counter() - started_at) * 1000, 3),
            "success": success,
            "dry_run": dry_run,
            "arguments": _redact(arguments),
        }
        if error:
            entry["error"] = error
        elif isinstance(result, dict):
            entry["result"] = _redact({key: value for key, value in result.items() if key not in {"source", "content"}})
        with self._lock:
            self._entries.append(entry)

    def entries(self, limit: int = 100) -> list[Dict[str, Any]]:
        """Return recent entries, newest first."""
        bounded = max(1, min(int(limit), 1000))
        with self._lock:
            return list(reversed(list(self._entries)))[:bounded]
