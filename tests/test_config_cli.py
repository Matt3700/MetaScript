import json
import os
from metascript import cli


def test_config_set_and_get_cli(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # set a start_command
    cli_args = ['config', 'set', 'start_command', 'vllm serve --foo']
    monkeypatch.setenv('PYTEST_RUNNING', '1')
    # call main via module entry with args simulated by argparse by directly calling functions
    from metascript.cli import main as cli_main

    # simulate argv
    import sys
    old_argv = sys.argv
    try:
        sys.argv = ['metascript'] + cli_args
        cli_main()
        captured = capsys.readouterr()
        assert 'Saved start_command' in captured.out
        # now get the value
        sys.argv = ['metascript', 'config', 'get', 'start_command']
        cli_main()
        captured = capsys.readouterr()
        assert 'vllm serve --foo' in captured.out
        # config file exists
        cfg = json.loads((tmp_path / 'metascript_config.json').read_text())
        assert cfg['start_command'] == 'vllm serve --foo'
    finally:
        sys.argv = old_argv