"""Frontend meta-agent (stub)
Simple, synchronous helper used by the CLI and tests to demonstrate the
`agent-first` handshake.  This is intentionally small and deterministic.
"""
from typing import Dict, Any
from metascript.agents import tools


def synthesize_code_from_intent(natural_text: str, syntax: str = "python-style") -> str:
    """Create a tiny Meta Script snippet from a plain-English intent.
    This is a very small heuristic implementation for demo/testing.
    """
    text = (natural_text or "").lower()
    # very small set of heuristics for examples
    if "say" in text and "times" in text:
        # "say hello 5 times" -> loop
        import re
        m = re.search(r"(\d+)", text)
        n = int(m.group(1)) if m else 1
        # pick a simple phrase if present
        phrase_match = re.search(r"say\s+\"?([^\"]+)\"?", natural_text, re.IGNORECASE)
        phrase = phrase_match.group(1) if phrase_match else "Hello"
        return f"for i in range({n}):\n    say \"{phrase}\"\n"
    # fallback - echo intent as a say
    return f'say "I heard: {natural_text.strip()}"\n'


def explain_code(code: str) -> str:
    """Return a one-line, kid-friendly explanation of the provided code.
    Very small heuristic: describe loops and prints.
    """
    s = (code or "").strip()
    if not s:
        return "(empty program)"
    if s.startswith("for ") or "range(" in s:
        return "This program repeats an action several times."
    if s.startswith("say ") or 'print(' in s:
        return "This program prints words to the screen."
    return "This program performs simple steps in order."


# -----------------------------
# Model adapters (local-first, external-backup)
# -----------------------------
class BaseModelAdapter:
    """Adapter interface for NL models."""

    def synthesize_code(self, natural_text: str, syntax: str = "python-style") -> str:
        raise NotImplementedError

    def explain(self, code: str) -> str:
        raise NotImplementedError


class LocalModelAdapter(BaseModelAdapter):
    """Local heuristic model used by default. Fast, offline, deterministic.

    Behaviour: returns an empty string when the input includes the token
    'force-fallback' so tests can exercise the external fallback path.
    """

    def synthesize_code(self, natural_text: str, syntax: str = "python-style") -> str:
        if natural_text and "force-fallback" in natural_text:
            return ""  # indicate inability to handle
        return synthesize_code_from_intent(natural_text, syntax)

    def explain(self, code: str) -> str:
        return explain_code(code)


class ExternalModelAdapter(BaseModelAdapter):
    """External model adapter — uses a local HTTP model if configured via
    `VLLM_API_URL` or via persisted `metascript_config.json`; otherwise falls
    back to a deterministic simulated reply.

    The HTTP client is optional; if the `requests` package is unavailable the
    adapter will use the simulated response so the system remains testable.
    """

    def _parse_response(self, data: dict) -> str:
        # accept several common response shapes
        if not data:
            return ""
        if "generated_text" in data:
            return data["generated_text"]
        if "text" in data:
            return data["text"]
        if "outputs" in data and isinstance(data["outputs"], list) and data["outputs"]:
            first = data["outputs"][0]
            if isinstance(first, dict) and "text" in first:
                return first["text"]
            if isinstance(first, dict) and "output_text" in first:
                return first["output_text"]
        if "results" in data and isinstance(data["results"], list) and data["results"]:
            r = data["results"][0]
            if isinstance(r, dict) and "text" in r:
                return r["text"]
        return ""

    def _configured_api_url(self) -> str | None:
        import os
        # env var preferred
        url = os.environ.get("VLLM_API_URL")
        if url:
            return url
        # try persisted config
        try:
            from metascript.agents.discovery import load_persisted_vllm_url
            return load_persisted_vllm_url()
        except Exception:
            return None

    def synthesize_code(self, natural_text: str, syntax: str = "python-style") -> str:
        api_url = self._configured_api_url()
        if api_url:
            # try to call the local HTTP model (best-effort)
            try:
                import requests
                endpoints = ["/v1/generate", "/generate", "/v1/completions", ""]
                headers = {"Content-Type": "application/json"}
                payload = {"input": natural_text}
                for ep in endpoints:
                    url = api_url.rstrip("/") + ep
                    try:
                        r = requests.post(url, json=payload, headers=headers, timeout=3)
                        if r.status_code == 200:
                            got = r.json()
                            parsed = self._parse_response(got)
                            if parsed:
                                return parsed
                    except Exception:
                        continue
            except Exception:
                # requests not available — fall back to simulated behaviour
                pass

        # simulated deterministic fallback used in tests and when HTTP is not set
        import re
        m = re.search(r"(\d+)", (natural_text or ""))
        n = int(m.group(1)) if m else 1
        phrase_match = re.search(r"say\s+\"?([^\"]+)\"?", (natural_text or ""), re.IGNORECASE)
        phrase = phrase_match.group(1) if phrase_match else (natural_text or "(external)")
        return f"for i in range({n}):\n    say \"EXTERNAL: {phrase}\"\n"

    def explain(self, code: str) -> str:
        return "(external model explanation)"


class FallbackModelAdapter(BaseModelAdapter):
    """Try primary adapter first; if it returns falsy or raises, use backup."""

    def __init__(self, primary: BaseModelAdapter, backup: BaseModelAdapter):
        self.primary = primary
        self.backup = backup

    def synthesize_code(self, natural_text: str, syntax: str = "python-style") -> str:
        try:
            out = self.primary.synthesize_code(natural_text, syntax)
            if out:
                return out
        except Exception:
            pass
        return self.backup.synthesize_code(natural_text, syntax)

    def explain(self, code: str) -> str:
        try:
            out = self.primary.explain(code)
            if out:
                return out
        except Exception:
            pass
        return self.backup.explain(code)


# -----------------------------
# Model manager + selection
# -----------------------------
from metascript.agents.transformers_js_adapter import TransformersJSAdapter
from metascript.agents import model_selection


class ModelManager:
    """Registry + selector for available adapters. Uses the selection policy
    to pick the best adapter automatically and supports a runtime autotune
    benchmark that chooses the best adapter and can persist that choice.
    """

    def __init__(self):
        self._adapters = []
        # register defaults
        self.register_adapter(LocalModelAdapter())
        # register transformers.js adapter if available
        try:
            t = TransformersJSAdapter()
            if t.is_available():
                self.register_adapter(t)
        except Exception:
            pass
        self.register_adapter(ExternalModelAdapter())
        self._override = None

        # load persisted preferred adapter if any
        try:
            from metascript.agents.discovery import load_config
            cfg = load_config()
            pref = cfg.get("selected_adapter")
            if pref:
                for a in self._adapters:
                    if a.__class__.__name__ == pref:
                        self.override(a)
                        break
        except Exception:
            pass

    def register_adapter(self, adapter: BaseModelAdapter) -> None:
        self._adapters.append(adapter)

    def adapters(self):
        return list(self._adapters)

    def select(self):
        if self._override:
            return self._override
        return model_selection.choose_best_adapter(self._adapters)

    def override(self, adapter: BaseModelAdapter | None) -> None:
        self._override = adapter

    def autotune(self, sample_text: str = "say hello 2 times", runs: int = 2, persist: bool = False):
        """Benchmark available adapters and choose the best one.

        - Measures synthesize latency and uses capability scores to pick the
          best adapter. Optionally persists the selected adapter name to
          `metascript_config.json` when persist=True.
        - Returns (selected_adapter, results_dict)
        """
        import time
        results = []
        for a in self._adapters:
            cap = {}
            try:
                cap = a.capabilities() if hasattr(a, "capabilities") else {}
            except Exception:
                cap = {}
            # measure latency on a few runs
            latencies = []
            success = True
            for _ in range(max(1, runs)):
                try:
                    t0 = time.perf_counter()
                    out = a.synthesize_code(sample_text)
                    t1 = time.perf_counter()
                    latencies.append((t1 - t0) * 1000.0)
                    if not out:
                        success = False
                except Exception:
                    success = False
                    latencies.append(float('inf'))
            avg_latency = sum(latencies) / len(latencies) if latencies else float('inf')
            # combine advertised capabilities with measured latency
            cap['latency_ms'] = avg_latency
            cap['measurement_ok'] = success
            score = model_selection.score_adapter(cap)
            results.append({'adapter': a, 'cap': cap, 'score': score})

        # pick best by score
        best = max(results, key=lambda r: r['score'])
        selected = best['adapter']
        if persist:
            try:
                from metascript.agents.discovery import load_config, save_config
                cfg = load_config()
                cfg['selected_adapter'] = selected.__class__.__name__
                save_config(cfg)
            except Exception:
                pass
        # apply override so subsequent selects use it
        self.override(selected)
        return selected, results


_model_manager = ModelManager()


def set_model_adapter(adapter: BaseModelAdapter) -> None:
    """Override the automatic adapter selection (used by tests/integration)."""
    _model_manager.override(adapter)


def get_model_adapter() -> BaseModelAdapter:
    return _model_manager.select()


def run_autotune(runs: int = 2, persist: bool = False):
    """Convenience wrapper used by the CLI/tests to run autotune."""
    return _model_manager.autotune(runs=runs, persist=persist)


# -----------------------------
# Tool helpers exposed to callers
# -----------------------------
def list_tools() -> Dict[str, str]:
    """Return the available built-in tools and descriptions."""
    return tools.list_tools()


from metascript import audit

def call_tool(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Call a built-in tool by name. Records an agent-level audit event and
    delegates to the tools layer (which also records detailed audit events).
    """
    audit.record('agent_call_tool', actor='frontend', details={'tool': tool_name})
    res = tools.call_tool(tool_name, params)
    audit.record('agent_call_tool_result', actor='frontend', details={'tool': tool_name, 'result_ok': res.get('ok', True)})
    return res


def handle_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Accepts a JSON-like message and returns a JSON-like reply.
    Recognizes `intent-draft`, `explain`, and `call_tool` requests used by the CLI.
    Uses the installed model adapter when available.
    """
    msg_type = message.get("type") or message.get("action")
    payload = message.get("payload") or {}

    if msg_type == "intent-draft":
        natural = payload.get("natural_text") if isinstance(payload, dict) else None
        syntax = payload.get("target_syntax") if isinstance(payload, dict) else "python-style"
        adapter = get_model_adapter()
        code = adapter.synthesize_code(natural or "", syntax)
        return {"type": "ms-snippet", "from": "frontend", "payload": {"language": "meta-script", "syntax": syntax, "code": code}}

    if msg_type == "explain":
        code = payload.get("code") if isinstance(payload, dict) else payload
        adapter = get_model_adapter()
        return {"type": "explanation", "from": "frontend", "payload": {"explanation": adapter.explain(code)}}

    if msg_type == "call_tool":
        tool = payload.get("tool")
        params = payload.get("params", {}) if isinstance(payload, dict) else {}
        res = call_tool(tool, params)
        return {"type": "tool_result", "from": "frontend", "payload": {"tool": tool, "result": res}}

    # default echo reply
    return {"type": "ack", "from": "frontend", "payload": {"received": message}}
