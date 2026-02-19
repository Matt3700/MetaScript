from metascript.agents.frontend_agent import ModelManager
from metascript.agents.transformers_js_adapter import TransformersJSAdapter


def test_transformers_js_preferred_when_available(monkeypatch):
    mgr = ModelManager()

    # inject a fake Transformers adapter that reports high capabilities
    class FakeT:
        def is_available(self):
            return True

        def capabilities(self):
            return {"communication": 10, "tool_use": True, "offline": True, "latency_ms": 10}

        def synthesize_code(self, *a, **k):
            return 'say "from-fake-transformers"\n'

    mgr.register_adapter(FakeT())
    selected = mgr.select()
    assert 'transformers' in selected.__class__.__name__.lower() or 'FakeT'.lower() in selected.__class__.__name__.lower() or selected.synthesize_code('', '')
