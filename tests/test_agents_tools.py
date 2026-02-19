from metascript.agents import frontend_agent, backend_agent


def test_frontend_call_tool_compute_stats():
    msg = {"type": "call_tool", "payload": {"tool": "compute_stats", "params": {"text": "a\nb\nc"}}}
    resp = frontend_agent.handle_message(msg)
    assert resp["type"] == "tool_result"
    assert resp["payload"]["result"]["ok"]
    assert resp["payload"]["result"]["lines"] == 3


def test_backend_call_tool_get_plan():
    msg = {"action": "call_tool", "payload": {"tool": "get_plan", "params": {"code": "say \"hi\"\n"}}}
    resp = backend_agent.handle_message(msg)
    assert resp["ok"]
    assert "plan" in resp
