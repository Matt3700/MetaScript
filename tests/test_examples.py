from metascript import cli


def run_file_and_capture(path, capsys, run_with_agents=True):
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    cli.run_ms_source(src, {}, run_with_agents=run_with_agents)
    return capsys.readouterr()


def test_hello_example(capsys):
    out = run_file_and_capture('hello.ms', capsys, run_with_agents=True)
    assert 'Hello from Meta Script' in out.out


def test_avg_example(capsys):
    out = run_file_and_capture('avg.ms', capsys, run_with_agents=True)
    assert 'Average is 4.0' in out.out


def test_loop_example(capsys):
    out = run_file_and_capture('loop.ms', capsys, run_with_agents=True)
    assert 'Number 1' in out.out and 'Number 5' in out.out


def test_agent_demo_inlines_and_runs(capsys):
    out = run_file_and_capture('agent-demo.ms', capsys, run_with_agents=True)
    # frontend agent explanation should be printed by the CLI before execution
    assert '[frontend agent]' in out.out
    # synthesized code should print Hello 3 times
    assert out.out.count('Hello') >= 3


def test_story_example(capsys):
    out = run_file_and_capture('story.ms', capsys, run_with_agents=True)
    assert 'Once upon a time' in out.out
