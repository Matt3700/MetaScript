import os
import time
import requests
import pytest

from metascript.agents import frontend_agent
from metascript import cli


@pytest.mark.skipif(os.getenv('RUN_VLLM_INTEGRATION') != '1', reason='integration vllm tests disabled')
def test_vllm_server_responds_and_agents_use_it():
    # determine API URL (CI sets VLLM_API_URL or default to localhost:8080)
    url = os.getenv('VLLM_API_URL', 'http://127.0.0.1:8080')

    # wait a short while for the server to be healthy
    deadline = time.time() + 30.0
    ok = False
    while time.time() < deadline:
        try:
            r = requests.get(url.rstrip('/') + '/health', timeout=3)
            if r.status_code == 200:
                ok = True
                break
        except Exception:
            try:
                r = requests.post(url.rstrip('/') + '/v1/generate', json={'input': 'ping'}, timeout=3)
                if r.status_code == 200:
                    ok = True
                    break
            except Exception:
                pass
        time.sleep(0.5)

    assert ok, f'vLLM server not responding at {url}'

    # ask the frontend agent to synthesize code via the external adapter
    os.environ['VLLM_API_URL'] = url
    msg = {'type': 'intent-draft', 'payload': {'natural_text': 'say hello 2 times', 'target_syntax': 'python-style'}}
    resp = frontend_agent.handle_message(msg)
    code = resp['payload']['code']
    assert 'say' in code.lower() or 'print' in code.lower()

    # run the generated snippet through the CLI to ensure end-to-end
    # (agent-first handshake will be used since we set VLLM_API_URL)
    cli.run_ms_source(code, {}, run_with_agents=True)

    # also test a small metascript file that triggers the frontend external adapter
    ms = 'agent frontend [ "natural_text": "say hello 2 times", "target_syntax": "python-style" ]'
    cli.run_ms_source(ms, {}, run_with_agents=True)
