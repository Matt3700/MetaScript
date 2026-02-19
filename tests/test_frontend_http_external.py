import os
import types

from metascript.agents.frontend_agent import ExternalModelAdapter


class DummyResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json = json_data

    def json(self):
        return self._json


def test_external_adapter_uses_http_when_env_set(monkeypatch):
    # set env to point to local model
    os.environ["VLLM_API_URL"] = "http://localhost:1234"

    # create a fake requests module
    def fake_post(url, json=None, headers=None, timeout=None):
        assert "localhost:1234" in url
        return DummyResponse(200, {"generated_text": "for i in range(2):\n    say \"VLLM-HTTP\"\n"})

    fake_requests = types.SimpleNamespace(post=fake_post)
    monkeypatch.setitem(__import__("sys").modules, "requests", fake_requests)

    adapter = ExternalModelAdapter()
    out = adapter.synthesize_code("say hello 2 times")
    assert "VLLM-HTTP" in out

    del os.environ["VLLM_API_URL"]
