from metascript import parser, transpiler_js


def test_transpile_say_to_console_log():
    p = parser.parse('say "Hello"')
    js = transpiler_js.transpile(p)
    assert 'console.log("Hello");' in js


def test_transpile_for_loop():
    p = parser.parse('for i in range(2): say "X"')
    js = transpiler_js.transpile(p)
    assert 'for (let i=0; i<2; i++)' in js
    assert 'console.log("X");' in js


def test_transpile_for_range_with_args():
    p = parser.parse('for i in range(1, 4): say "A"')
    js = transpiler_js.transpile(p)
    assert 'for (let i=1; i<4; i++)' in js
    assert 'console.log("A");' in js


def test_transpile_for_iterable():
    p = parser.parse('for x in items: say "Z"')
    js = transpiler_js.transpile(p)
    assert 'for (const x of items)' in js
    assert 'console.log("Z");' in js


def test_transpile_if_and_function():
    p = parser.parse('def add(a, b): return a + b')
    js = transpiler_js.transpile(p)
    assert 'function add' in js
    assert 'return' in js


def test_transpile_list_and_agent():
    p = parser.parse('let arr = [1, 2]')
    js = transpiler_js.transpile(p)
    assert '[1, 2]' in js

    p2 = parser.parse('agent frontend ["{\"type\": \"intent-draft\"}"]')
    js2 = transpiler_js.transpile(p2)
    assert 'agentCall("frontend"' in js2


def test_transpile_async_await():
    p = parser.parse('async def fetch(): return await get()')
    js = transpiler_js.transpile(p)
    assert 'async function fetch' in js
    assert 'await get' in js


def test_transpile_match_and_patterns():
    p = parser.parse('match x: case 1: say "one" case _: say "other"')
    js = transpiler_js.transpile(p)
    assert 'const __ms_match_val' in js
    assert '__ms_match_val === 1' in js
    assert 'console.log("one")' in js


def test_transpile_macro_def_and_call():
    p = parser.parse('macro twice(x): say x\n@twice("Hi")')
    js = transpiler_js.transpile(p)
    # macro should be expanded at compile time and inlined
    assert 'console.log("Hi");' in js
    assert '__macro_twice' not in js


def test_transpile_for_range_with_step():
    p = parser.parse('for i in range(0, 10, 2): say "S"')
    js = transpiler_js.transpile(p)
    assert ('i+= 2' in js) or ('i += 2' in js)
    assert 'console.log("S");' in js


def test_transpile_macro_expands_to_forloop():
    p = parser.parse('macro mk(n): for j in range(n): say j\n@mk(2)')
    js = transpiler_js.transpile(p)
    # macro should be expanded; hygiene may rename local `j` so accept either form
    assert ('for (let j=0; j<2; j++)' in js) or ('__ms_macro_j_' in js)
    assert '__macro_mk' not in js
