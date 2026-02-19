"""Adapter for running local transformers.js (Node) models via a small bridge.

This adapter prefers a local JavaScript bridge script (tools/transformers_js_bridge.js)
and will fall back to a deterministic simulated response for tests when Node
or the bridge is not available.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
from typing import Optional


class TransformersJSAdapter:
    """Adapter that delegates to a Node bridge when available."""

    def is_available(self) -> bool:
        # available if a bridge script exists and node is callable
        bridge = os.path.join(os.getcwd(), "tools", "transformers_js_bridge.js")
        if not os.path.exists(bridge):
            return False
        # check for `node` on PATH (best-effort)
        try:
            subprocess.run(["node", "-v"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
            return True
        except Exception:
            return False

    def capabilities(self) -> dict:
        return {"communication": 9, "tool_use": True, "offline": True, "latency_ms": 50}

    def synthesize_code(self, natural_text: str, syntax: str = "python-style") -> str:
        """Try the Node bridge, otherwise simulate a deterministic response."""
        bridge = os.path.join(os.getcwd(), "tools", "transformers_js_bridge.js")
        if os.path.exists(bridge):
            try:
                payload = {"input": natural_text, "syntax": syntax}
                proc = subprocess.run(["node", bridge], input=json.dumps(payload).encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=5)
                out = proc.stdout.decode("utf-8").strip()
                if out:
                    # expect JSON or plain text
                    try:
                        j = json.loads(out)
                        # accept several possible keys
                        for key in ("generated_text", "text", "code"):
                            if key in j:
                                return j[key]
                        # fallback to stringified json
                        return json.dumps(j)
                    except Exception:
                        return out
            except Exception:
                pass
        # deterministic simulated fallback
        # reuse simple loop synthesis
        import re
        m = re.search(r"(\d+)", (natural_text or ""))
        n = int(m.group(1)) if m else 1
        phrase_match = re.search(r"say\s+\"?([^\"]+)\"?", (natural_text or ""), re.IGNORECASE)
        phrase = phrase_match.group(1) if phrase_match else (natural_text or "(transformers-js)")
        return f"for i in range({n}):\n    say \"TRANSFORMERSJS: {phrase}\"\n"

    def explain(self, code: str) -> str:
        return "(transformers.js explanation)"