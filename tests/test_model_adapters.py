from metascript.agents import frontend_agent


def test_default_uses_local_model_for_simple_intent():
    msg = {"type": "intent-draft", "payload": {"natural_text": "say hello 2 times", "target_syntax": "python-style"}}
    resp = frontend_agent.handle_message(msg)
    code = resp["payload"]["code"]
    assert "range(2)" in code and "EXTERNAL" not in code


def test_fallback_uses_external_model_when_local_cant_handle():
    msg = {"type": "intent-draft", "payload": {"natural_text": "force-fallback say hello 2 times", "target_syntax": "python-style"}}
    resp = frontend_agent.handle_message(msg)
    code = resp["payload"]["code"]
    # accept either the HTTP/external adapter or a local transformers.js bridge as the fallback
    assert ("EXTERNAL" in code) or ("TRANSFORMERSJS" in code) or ("TRANSFORMERSJS-BRIDGE" in code)


def test_cli_inlines_external_on_fallback(tmp_path, capsys):
    path = tmp_path / "fb.ms"
    path.write_text('agent frontend [ "natural_text": "force-fallback say Hello 2 times", "target_syntax": "python-style" ]')
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    from metascript import cli
    cli.run_ms_source(src, {}, run_with_agents=True)
    out = capsys.readouterr().out
    assert ('EXTERNAL: Hello' in out) or ('TRANSFORMERSJS' in out) or ('TRANSFORMERSJS-BRIDGE' in out)
