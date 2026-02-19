"""Built-in agent tools for Meta Script agents.

These are deterministic, sandbox-aware helpers the frontend/backend agents
can call. Designed to be safe for unit tests and to illustrate how real tools
could be integrated.

Each tool accepts a params dict and returns JSON-serializable results.
Agents call them via tools.call_tool(name, params).
"""
from __future__ import annotations

import ast
import json
import os
import textwrap
from typing import Any, Dict, Callable
import tempfile

# Workspace safety: allow workspace and system temp (tests may use tmp_path)
_WORKSPACE_ROOT = os.path.abspath(os.getcwd())


def _is_within_workspace(path: str) -> bool:
    try:
        ab = os.path.abspath(path)
        return ab.startswith(_WORKSPACE_ROOT) or ab.startswith(tempfile.gettempdir())
    except Exception:
        return False


def read_file(params: Dict[str, Any]) -> Dict[str, Any]:
    path = params.get("path")
    if not path:
        raise ValueError("'path' is required")
    if not _is_within_workspace(path):
        return {"ok": False, "error": "path out of workspace"}
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        return {"ok": True, "text": text}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def write_file(params: Dict[str, Any]) -> Dict[str, Any]:
    path = params.get("path")
    content = params.get("content", "")
    if not path:
        raise ValueError("'path' is required")
    if not _is_within_workspace(path):
        return {"ok": False, "error": "path out of workspace"}
    try:
        # create parent directories if needed
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(content))
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_dir(params: Dict[str, Any]) -> Dict[str, Any]:
    path = params.get("path", "./")
    if not _is_within_workspace(path):
        return {"ok": False, "error": "path out of workspace"}
    try:
        entries = os.listdir(path)
        return {"ok": True, "entries": entries}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def compute_stats(params: Dict[str, Any]) -> Dict[str, Any]:
    text = params.get("text", "")
    if text is None:
        return {"ok": False, "error": "text is required"}
    lines = text.count("\n") + (1 if text else 0)
    words = len(text.split())
    chars = len(text)
    return {"ok": True, "lines": lines, "words": words, "chars": chars}


def safe_eval(params: Dict[str, Any]) -> Dict[str, Any]:
    expr = params.get("expr")
    if expr is None:
        return {"ok": False, "error": "expr is required"}
    # parse and allow only arithmetic expressions
    try:
        node = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        return {"ok": False, "error": f"syntax: {e}"}

    allowed_nodes = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Mod,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.Load,
        ast.Tuple,
    )

    for n in ast.walk(node):
        if not isinstance(n, allowed_nodes):
            return {"ok": False, "error": f"disallowed node: {type(n).__name__}"}
    try:
        value = eval(compile(node, "<safe_eval>", mode="eval"), {})
        return {"ok": True, "result": value}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def http_get(params: Dict[str, Any]) -> Dict[str, Any]:
    url = params.get("url")
    if not url:
        return {"ok": False, "error": "url required"}
    # Simulate network for safety in unit tests; respond to example.com
    if "example.com" in url:
        return {"ok": True, "status": 200, "body": "<html>Example Domain</html>"}
    return {"ok": False, "error": "network disabled in built-in tool"}


def format_code(params: Dict[str, Any]) -> Dict[str, Any]:
    code = params.get("code", "")
    lang = params.get("lang", "python")
    if lang == "python":
        try:
            parsed = ast.parse(code)
            # ast.unparse is available in modern Python
            formatted = ast.unparse(parsed)
            return {"ok": True, "code": formatted}
        except Exception:
            # fallback: tidy whitespace
            return {"ok": True, "code": textwrap.dedent(code).strip()}
    # default: return trimmed
    return {"ok": True, "code": textwrap.dedent(code).strip()}


def simulate_run(params: Dict[str, Any]) -> Dict[str, Any]:
    code = params.get("code", "")
    # do not execute — only simulate: check for dangerous patterns
    dangerous = any(x in code.lower() for x in ("open(", "exec(", "socket", "requests", "subprocess"))
    if dangerous:
        return {"ok": False, "stderr": "dangerous operations detected", "exit_code": 2}
    # produce a fake stdout based on simple prints
    lines = [l for l in code.splitlines() if l.strip().startswith('say ')]
    stdout = []
    for ln in lines:
        content = ln.strip()[4:]
        stdout.append(content.strip('"'))
    return {"ok": True, "stdout": "\n".join(stdout), "exit_code": 0}


def get_plan_for_code(params: Dict[str, Any]) -> Dict[str, Any]:
    code = params.get("code", "")
    lines = len(code.splitlines())
    cpu_ms = max(200, min(20000, 100 * max(1, lines)))
    memory_mb = max(16, min(1024, 10 + lines // 2))
    return {"ok": True, "plan": {"cpu_ms": cpu_ms, "memory_mb": memory_mb}}


def get_plan(params: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience wrapper used by tests and agents."""
    return get_plan_for_code(params)


# Public registry of tools
from metascript import audit

TOOLS: Dict[str, Dict[str, Any]] = {
    "read_file": {"func": read_file, "description": "Read a workspace file"},
    "write_file": {"func": write_file, "description": "Write a workspace file"},
    "list_dir": {"func": list_dir, "description": "List directory entries"},
    "compute_stats": {"func": compute_stats, "description": "Compute lines/words/chars"},
    "safe_eval": {"func": safe_eval, "description": "Evaluate arithmetic expressions safely"},
    "http_get": {"func": http_get, "description": "Safe (simulated) HTTP GET"},
    "format_code": {"func": format_code, "description": "Format code (python)"},
    "simulate_run": {"func": simulate_run, "description": "Simulate running MS code"},
    "get_plan": {"func": get_plan_for_code, "description": "Return a resource plan for code"},
}


def list_tools() -> Dict[str, str]:
    return {k: v["description"] for k, v in TOOLS.items()}


def call_tool(name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Call a tool and emit audit records for autonomous use.

    The tools layer is the authoritative place to audit tool calls (both
    successes and failures)."""
    tool = TOOLS.get(name)
    if not tool:
        ev = audit.record('tool_call', actor='tools', details={'tool': name, 'params': params}, outcome='unknown_tool')
        return {"ok": False, "error": "unknown tool"}
    # record attempt
    audit.record('tool_call', actor='tools', details={'tool': name, 'params': params})
    try:
        res = tool["func"](params or {})
        outcome = 'ok' if res.get('ok', True) else 'error'
        # record result (trim large payloads)
        summary = {k: (v if (isinstance(v, (str, int, bool)) and len(str(v)) < 500) else '<large>') for k, v in (res.items() if isinstance(res, dict) else [])}
        audit.record('tool_result', actor='tools', details={'tool': name, 'summary': summary}, outcome=outcome)
        return res
    except Exception as e:
        audit.record('tool_result', actor='tools', details={'tool': name, 'error': str(e)}, outcome='exception')
        return {"ok": False, "error": str(e)}
