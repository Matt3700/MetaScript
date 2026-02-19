import io
import sys

from metascript import cli


def test_run_ms_with_agents_prints_explanation_and_output(capsys):
    source = 'say "Hello from test"'
    env = {}
    cli.run_ms_source(source, env, run_with_agents=True)
    captured = capsys.readouterr()
    assert '[frontend agent]' in captured.out
    assert 'Hello from test' in captured.out


def test_run_ms_rejected_by_backend(capsys):
    source = 'open("secret").read()'
    env = {}
    cli.run_ms_source(source, env, run_with_agents=True)
    captured = capsys.readouterr()
    assert '[backend agent] Execution rejected' in captured.out


def test_run_ms_no_agent_runs(capsys):
    source = 'say "ok"'
    env = {}
    cli.run_ms_source(source, env, run_with_agents=False)
    captured = capsys.readouterr()
    assert 'ok' in captured.out


def test_run_ms_macros_in_python_target(capsys):
    src = 'macro twice(x): say x\n@twice("Hi")'
    cli.run_ms_source(src, {}, run_with_agents=False)
    captured = capsys.readouterr()
    assert 'Hi' in captured.out


def test_compile_expand_macros(tmp_path, capsys):
    p = tmp_path / 'm.ms'
    p.write_text('macro twice(x): say x\n@twice("Hi")')
    import sys
    old_argv = sys.argv
    try:
        sys.argv = ['metascript', 'compile', str(p), '--expand-macros']
        cli.main()
        out = capsys.readouterr().out
        assert 'say "Hi"' in out
    finally:
        sys.argv = old_argv
