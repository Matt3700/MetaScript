"""Simple audit/telemetry for Meta Script autonomous actions.

Records events in-memory for tests and appends newline-delimited JSON to
`metascript_audit.log` in the workspace root for persistence.
"""
from __future__ import annotations

import datetime
import json
import os
from typing import Any, Dict, List

_LOGFILE = os.path.join(os.getcwd(), "metascript_audit.log")
_events: List[Dict[str, Any]] = []


def _now_iso() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def record(event_type: str, actor: str, details: Dict[str, Any] | None = None, outcome: str = "ok") -> Dict[str, Any]:
    """Record an audit event.

    - event_type: short name (e.g. 'tool_call', 'autotune', 'program_run')
    - actor: who/what triggered it ('frontend', 'backend', 'autotuner', etc.)
    - details: additional JSON-serializable data (keep small; do not store secrets)
    - outcome: 'ok'|'error'|'rejected' etc.

    Returns the event dict.
    """
    details = details or {}
    # sanitize common sensitive keys
    sanitized = {k: ("<redacted>" if k.lower() in ("token", "password", "secret") else v) for k, v in details.items()}
    ev = {"ts": _now_iso(), "event": event_type, "actor": actor, "outcome": outcome, "details": sanitized}
    _events.append(ev)
    # append to logfile (best-effort)
    try:
        with open(_LOGFILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev) + "\n")
    except Exception:
        # do not propagate logging failures
        pass
    return ev


def get_events() -> List[Dict[str, Any]]:
    return list(_events)


def clear_events() -> None:
    _events.clear()
    # do not delete logfile by default


def tail(n: int = 50) -> List[Dict[str, Any]]:
    return _events[-n:]
