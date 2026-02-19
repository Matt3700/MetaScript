"""Backend meta-agent (stub)
Small validation/sandboxing helpers used by the CLI. Returns simple
`approved`/`rejected` responses for demonstration and testing.
"""
from typing import Dict, Any

from metascript.agents import tools

DANGEROUS_PATTERNS = [
    "open(", "exec(", "eval(", "__import__", "subprocess", "socket", "requests", "os.system", "os.exec"
]


def _contains_danger(code: str) -> bool:
    s = (code or "").lower()
    return any(p in s for p in DANGEROUS_PATTERNS)


def _contains_network(code: str) -> bool:
    s = (code or "").lower()
    return any(x in s for x in ("socket", "requests", "http", "urllib"))


def _compute_plan(code: str) -> Dict[str, int]:
    """Return a simple resource plan scaled to code length/complexity."""
    lines = len((code or "").splitlines())
    cpu_ms = max(200, min(20000, 100 * max(1, lines)))
    memory_mb = max(16, min(1024, 10 + lines // 2))
    return {"cpu_ms": cpu_ms, "memory_mb": memory_mb}


from metascript import audit


def validate_execution(code: str, permissions: Dict[str, Any] = None) -> Dict[str, Any]:
    """Validate whether the provided code should be allowed to run.
    Returns a dict: {approved: bool, reason: str, plan: ...}
    This is a conservative stub: disallow common unsafe calls.
    """
    permissions = permissions or {}
    if _contains_danger(code) and not permissions.get("allow_unsafe"):
        res = {"approved": False, "reason": "Unsafe operations detected (file/exec/network).", "plan": None}
        audit.record('validate_execution', actor='backend', details={'code_len': len(code), 'reason': 'danger_detected'}, outcome='rejected')
        return res

    if _contains_network(code) and not permissions.get("allow_network"):
        res = {"approved": False, "reason": "Network operations detected but not permitted.", "plan": None}
        audit.record('validate_execution', actor='backend', details={'code_len': len(code), 'reason': 'network_blocked'}, outcome='rejected')
        return res

    plan = _compute_plan(code)
    res = {"approved": True, "reason": "OK", "plan": plan}
    audit.record('validate_execution', actor='backend', details={'code_len': len(code), 'plan': plan}, outcome='approved')
    return res


def handle_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Handle backend messages: 'validate', 'plan', or 'call_tool'.
    """
    action = message.get("action") or message.get("type")
    payload = message.get("payload") or {}

    if action == "validate":
        code = payload.get("code", "") if isinstance(payload, dict) else ""
        return validate_execution(code, payload.get("permissions") if isinstance(payload, dict) else None)

    if action == "plan":
        code = payload.get("code", "") if isinstance(payload, dict) else ""
        # prefer centralized tool plan when available
        tool_res = tools.call_tool("get_plan", {"code": code})
        if tool_res.get("ok"):
            return {"plan": tool_res.get("plan")}
        return {"plan": _compute_plan(code)}

    if action == "call_tool":
        tool = payload.get("tool")
        params = payload.get("params", {}) if isinstance(payload, dict) else {}
        return tools.call_tool(tool, params)

    # default response
    return {"status": "ok", "received": message}
