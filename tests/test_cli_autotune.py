from metascript import cli
from metascript.agents import frontend_agent
import json


def test_cli_autotune_persists_and_can_enable_autonomy(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    # ensure model manager has at least one adapter
    mgr = frontend_agent._model_manager
    # run autotune via CLI and save selection + enable autonomy
    import sys
    old_argv = sys.argv
    try:
        sys.argv = ['metascript', 'autotune', '--save', '--enable-autonomy']
        cli.main()
        captured = capsys.readouterr()
        assert 'Selected adapter:' in captured.out
        # config file should exist and contain autonomy_enabled true
        cfg = json.loads((tmp_path / 'metascript_config.json').read_text())
        assert cfg.get('autonomy_enabled') is True
        assert 'selected_adapter' in cfg
    finally:
        sys.argv = old_argv