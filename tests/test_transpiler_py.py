from metascript import parser, transpiler_py


def test_transpile_say_to_print():
    p = parser.parse('say "Hello"')
    py = transpiler_py.transpile(p)
    assert 'print(' in py and 'Hello' in py


def test_transpile_async_await_py():
    p = parser.parse('async def fetch(): return await get()')
    py = transpiler_py.transpile(p)
    assert 'async def fetch' in py
    assert 'await get' in py


def test_transpile_for_range_args_py():
    p = parser.parse('for i in range(1, 4): say "A"')
    py = transpiler_py.transpile(p)
    assert 'for i in range(1, 4):' in py


def test_transpile_for_range_step_py():
    p = parser.parse('for i in range(0, 10, 2): say "S"')
    py = transpiler_py.transpile(p)
    assert 'for i in range(0, 10, 2):' in py


def test_transpile_for_iterable_py():
    p = parser.parse('for x in items: say "Z"')
    py = transpiler_py.transpile(p)
    assert 'for x in items:' in py


def test_transpile_macro_expands_to_for_py():
    p = parser.parse('macro mk(n): for j in range(n): say j\n@mk(2)')
    py = transpiler_py.transpile(p)
    # macros are expanded and hygiene may rename the loop variable
    assert ('for j in range(2):' in py) or ('__ms_macro_j_' in py)
    assert '__macro_mk' not in py


