import types
import subprocess

from metascript.agents import discovery


def test_start_vllm_if_missing_calls_start_and_detects(monkeypatch):
    calls = {"probe": 0}

    def fake_probe(timeout=0.1):
        # first call: not running; subsequent calls: running
        calls["probe"] += 1
        return None if calls["probe"] == 1 else "http://localhost:8080"

    monkeypatch.setattr(discovery, "probe_vllm_hosts", fake_probe)
    monkeypatch.setattr(discovery, "is_vllm_installed", lambda: True)

    started = {"called": False}

    def fake_start(cmd=None, cwd=None):
        started["called"] = True
        # return a dummy Popen-like object
        class P:
            def terminate(self):
                pass
        return P()

    monkeypatch.setattr(discovery, "start_vllm_server", fake_start)

    url = discovery.start_vllm_if_missing(wait_seconds=1.0)
    assert started["called"]
    assert url == "http://localhost:8080"