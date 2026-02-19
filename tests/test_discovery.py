import os
import types

from metascript.agents import discovery


class DummyResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json


def test_probe_vllm_hosts_detects(monkeypatch):
    # fake requests with a successful endpoint
    def fake_post(url, json=None, timeout=None):
        return DummyResponse(200, {"generated_text": "ok"})

    fake_requests = types.SimpleNamespace(post=fake_post, get=lambda *a, **k: DummyResponse(404))
    monkeypatch.setitem(__import__("sys").modules, "requests", fake_requests)

    url = discovery.probe_vllm_hosts(timeout=0.1)
    assert url is not None


def test_configure_and_load_persist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    discovery.configure_vllm("http://localhost:1234/generate", persist=True)
    loaded = discovery.load_persisted_vllm_url()
    assert loaded == "http://localhost:1234/generate"
    # cleanup
    os.remove(tmp_path / "metascript_config.json")
