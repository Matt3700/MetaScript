import pytest

from metascript.agents import frontend_agent, backend_agent


def test_frontend_synthesize_loop():
    code = frontend_agent.synthesize_code_from_intent('Say hello 3 times', 'python-style')
    assert 'range(3)' in code
    assert 'say' in code.lower()


def test_frontend_explain_loop():
    explanation = frontend_agent.explain_code('for i in range(3):\n    say "Hi"')
    assert 'repeat' in explanation or 'repeats' in explanation


def test_frontend_handle_intent_draft():
    msg = {'type': 'intent-draft', 'payload': {'natural_text': 'say hi 2 times', 'target_syntax': 'python-style'}}
    resp = frontend_agent.handle_message(msg)
    assert resp['type'] == 'ms-snippet'
    assert 'code' in resp['payload']


def test_backend_rejects_open():
    code = 'open("secrets.txt").read()'
    res = backend_agent.validate_execution(code)
    assert res['approved'] is False


def test_backend_allows_with_permission():
    code = 'open("secrets.txt").read()'
    res = backend_agent.validate_execution(code, permissions={'allow_unsafe': True})
    assert res['approved'] is True


def test_backend_network_rejection():
    code = 'import socket; s.connect(("example.com",80))'
    res = backend_agent.validate_execution(code, permissions={})
    assert res['approved'] is False


def test_backend_plan_scaling():
    short = backend_agent.validate_execution('say "hi"')['plan']
    long_code = 'print("x")\n' * 200
    long_plan = backend_agent.validate_execution(long_code)['plan']
    assert long_plan['cpu_ms'] >= short['cpu_ms']


def test_backend_validate_execution_audit_rejects_unsafe():
    # clear prior events and trigger a rejected validation
    from metascript import audit
    audit.clear_events()

    code = 'open("secrets.txt").read()'
    res = backend_agent.validate_execution(code)
    assert res['approved'] is False

    events = audit.get_events()
    # find the last validate_execution event
    ve = next((e for e in reversed(events) if e['event'] == 'validate_execution'), None)
    assert ve is not None
    assert ve['actor'] == 'backend'
    assert ve['outcome'] == 'rejected'
    assert ve['details'].get('reason') == 'danger_detected'


def test_backend_validate_execution_audit_approves():
    # clear prior events and trigger an approved validation
    from metascript import audit
    audit.clear_events()

    code = 'say "hi"'
    res = backend_agent.validate_execution(code, permissions={'allow_unsafe': True})
    assert res['approved'] is True

    events = audit.get_events()
    ve = next((e for e in reversed(events) if e['event'] == 'validate_execution'), None)
    assert ve is not None
    assert ve['actor'] == 'backend'
    assert ve['outcome'] == 'approved'
    assert isinstance(ve['details'].get('plan'), dict)
