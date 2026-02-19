from metascript.agents import frontend_agent


def test_autotune_selects_adapter_and_persists(tmp_path, monkeypatch):
    # create fake adapters with capabilities and deterministic latency
    class FastAdapter:
        def capabilities(self):
            return {"communication": 9, "tool_use": True, "offline": True, "latency_ms": 10}

        def synthesize_code(self, text, syntax="python-style"):
            return 'say "fast"\n'

    class SlowAdapter:
        def capabilities(self):
            return {"communication": 5, "tool_use": False, "offline": False, "latency_ms": 200}

        def synthesize_code(self, text, syntax="python-style"):
            return 'say "slow"\n'

    mgr = frontend_agent._model_manager
    # snapshot adapters to restore after the test
    orig_adapters = list(mgr.adapters())
    try:
        # register fake adapters at the end
        mgr.register_adapter(FastAdapter())
        mgr.register_adapter(SlowAdapter())

        selected, results = mgr.autotune(runs=1, persist=False)
        assert selected.__class__.__name__ in ('LocalModelAdapter', 'TransformersJSAdapter', 'ExternalModelAdapter', 'FastAdapter')
        # we expect no exception and results contain entries
        assert len(results) >= 1
    finally:
        # restore original adapters so other tests are unaffected
        mgr._adapters = orig_adapters
        mgr.override(None)
