"""Model selection policy for Meta Script agents.

Chooses the best available model adapter according to configurable
criteria (communication quality, tool-use capability, offline availability,
latency). Implemented as a simple score-based selector for demonstration.
"""
from typing import Iterable, Any


def score_adapter(cap: dict, weights: dict | None = None) -> float:
    w = weights or {}
    wc = w.get("communication", 2.0)
    wt = w.get("tool_use", 10.0)
    wo = w.get("offline", 1.0)
    wl = w.get("latency", 0.01)

    communication = float(cap.get("communication", 5))
    tool = 1.0 if cap.get("tool_use") else 0.0
    offline = 1.0 if cap.get("offline") else 0.0
    latency = float(cap.get("latency_ms", cap.get("latency", 100)))

    return wc * communication + wt * tool + wo * offline - wl * latency


def choose_best_adapter(adapters: Iterable[Any], weights: dict | None = None):
    """Return the adapter instance with the highest score.

    Each adapter should provide a `capabilities()` method returning a dict
    with keys: `communication` (0-10), `tool_use` (bool), `offline` (bool),
    `latency_ms` (int).
    If `capabilities()` is missing, the adapter is scored with defaults.
    """
    best = None
    best_score = float('-inf')
    for a in adapters:
        try:
            cap = a.capabilities() if hasattr(a, "capabilities") else {}
        except Exception:
            cap = {}
        s = score_adapter(cap, weights)
        if s > best_score:
            best_score = s
            best = a
    return best