from metascript import parser, ast


def test_parse_match_with_list_and_wildcard():
    p = parser.parse('match arr: case [a, b]: say a case _: say "other"')
    m = p.statements[0]
    assert isinstance(m, ast.Match)
    assert len(m.cases) == 2
    first = m.cases[0]
    assert isinstance(first.pattern, ast.ListPattern)
    assert len(first.pattern.elements) == 2
    assert isinstance(first.pattern.elements[0], ast.NamePattern)


def test_parse_async_def_and_await_return():
    p = parser.parse('async def fetch(): return await get()')
    fn = p.statements[0]
    assert isinstance(fn, ast.FunctionDef)
    assert fn.is_async is True
    ret = fn.body[0]
    assert isinstance(ret, ast.Return)
    assert isinstance(ret.value, ast.Await)
    assert isinstance(ret.value.expr, ast.FunctionCall)


def test_parse_macro_def_and_call():
    p = parser.parse('macro twice(x): say x')
    m = p.statements[0]
    assert isinstance(m, ast.MacroDef)
    assert m.name == 'twice'
    assert m.params == ['x']

    p2 = parser.parse('@twice("Hi")')
    call = p2.statements[0]
    assert isinstance(call, ast.MacroCall)
    assert call.name == 'twice'


def test_macro_expansion_inlines_body():
    from metascript import macros
    p = parser.parse('macro twice(x): say x\n@twice("Hi")')
    expanded = macros.expand_macros(p)
    # MacroDef removed, call replaced by inlined statement
    assert len(expanded.statements) == 1
    s = expanded.statements[0]
    assert isinstance(s, ast.Say)
    assert isinstance(s.text, ast.LiteralString)
    assert s.text.value == 'Hi'


def test_macro_hygiene():
    from metascript import macros
    src = 'let tmp = 99\nmacro m(x): let tmp = x\n@m(1)'
    p = parser.parse(src)
    expanded = macros.expand_macros(p)
    assigns = [s for s in expanded.statements if isinstance(s, ast.Assign)]
    # should have two assigns: original 'tmp' and a renamed macro-local tmp
    names = [a.name for a in assigns]
    assert 'tmp' in names
    assert any(n != 'tmp' for n in names)


def test_macro_scoping():
    # construct AST with macro defined inside a function scope
    from metascript import macros as ms_macros
    macro_def = ast.MacroDef('inner', ['x'], [ast.Say(ast.NameExpr('x'))])
    func = ast.FunctionDef('f', [], [macro_def, ast.MacroCall('inner', [ast.LiteralString('a')])])
    prog_local = ast.Program([func])

    expanded_local = ms_macros.expand_macros(prog_local)
    # macro inside function should be expanded and MacroDef removed from body
    fnode = expanded_local.statements[0]
    assert isinstance(fnode, ast.FunctionDef)
    assert not any(isinstance(s, ast.MacroDef) for s in fnode.body)
    assert any(isinstance(s, ast.Say) for s in fnode.body)

    # top-level call to 'inner' (undefined) should raise
    prog_bad = ast.Program([func, ast.MacroCall('inner', [ast.LiteralString('b')])])
    try:
        ms_macros.expand_macros(prog_bad)
        assert False, 'Expected undefined macro error'
    except ValueError:
        pass


def test_macro_hygiene_forloop_var_collision():
    from metascript import macros as ms_macros
    src = 'macro inner(): for i in range(2): say i\nfor i in range(3): @inner()'
    p = parser.parse(src)
    expanded = ms_macros.expand_macros(p)

    def _collect_forloops(node):
        res = []
        if isinstance(node, ast.ForLoop):
            res.append(node)
            for s in node.body:
                res.extend(_collect_forloops(s))
        elif hasattr(node, 'body') and isinstance(getattr(node, 'body', None), list):
            for s in node.body:
                res.extend(_collect_forloops(s))
        return res

    loops = []
    for s in expanded.statements:
        loops.extend(_collect_forloops(s))

    assert len(loops) == 2
    outer, inner = loops[0], loops[1]
    assert outer.var == 'i'
    assert inner.var != 'i'  # hygiene: inner loop var renamed