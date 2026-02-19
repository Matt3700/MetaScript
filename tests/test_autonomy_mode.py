from metascript import cli
from metascript.agents import tools


def test_agent_call_tool_runs_when_autonomy_enabled(tmp_path, capsys):
    p = tmp_path / "out.txt"
    src = 'agent frontend [ "type": "call_tool", "payload": { "tool": "write_file", "params": { "path": "%s", "content": "autonomous" } } ]' % str(p)
    env = {}
    # run with agents and autonomy
    cli.run_ms_source(src, env, run_with_agents=True, run_autonomy=True)
    # file should be written by the tool
    assert p.read_text() == 'autonomous'


def test_agent_call_tool_blocked_when_autonomy_disabled(tmp_path, capsys):
    p = tmp_path / "out2.txt"
    src = 'agent frontend [ "type": "call_tool", "payload": { "tool": "write_file", "params": { "path": "%s", "content": "nope" } } ]' % str(p)
    env = {}
    cli.run_ms_source(src, env, run_with_agents=True, run_autonomy=False)
    # file should NOT be written
    assert not p.exists()
