from metascript import parser
from metascript import ast


def test_parse_say_produces_ast():
    p = parser.parse('say "Hello"')
    assert isinstance(p, ast.Program)
    assert len(p.statements) == 1
    s = p.statements[0]
    assert isinstance(s, ast.Say)
    assert isinstance(s.text, ast.LiteralString)
    assert s.text.value == "Hello"


def test_parse_for_single_statement():
    p = parser.parse('for i in range(3): say "Hi"')
    assert isinstance(p.statements[0], ast.ForLoop)
    f = p.statements[0]
    assert f.var == 'i' and isinstance(f.end, ast.LiteralInt)
    assert isinstance(f.body[0], ast.Say)


def test_parse_for_complex_range_expression():
    p = parser.parse('for i in range(1 + n*2, max(5, m)): say "C"')
    f = p.statements[0]
    assert isinstance(f.end, ast.FunctionCall) and f.end.name == 'range'
    # expect a BinaryOp and a FunctionCall among args
    assert any(isinstance(a, ast.BinaryOp) for a in f.end.args)
    assert any(isinstance(a, ast.FunctionCall) for a in f.end.args)



def test_parse_for_with_range_args():
    p = parser.parse('for i in range(1, 4): say "Hi"')
    f = p.statements[0]
    assert isinstance(f.end, ast.FunctionCall) and f.end.name == 'range'
    assert len(f.end.args) == 2


def test_parse_for_iterable_name_and_list():
    p = parser.parse('for x in items: say "Hi"')
    f = p.statements[0]
    assert isinstance(f.end, ast.NameExpr)

    p2 = parser.parse('for y in [1, 2, 3]: say "Y"')
    f2 = p2.statements[0]
    assert isinstance(f2.end, ast.ListLiteral)


def test_parse_for_range_literal():
    p = parser.parse('for i in 1..3: say "R"')
    f = p.statements[0]
    assert isinstance(f.end, ast.FunctionCall) and f.end.name == 'range' and len(f.end.args) == 2


def test_parse_let_and_list():
    p = parser.parse('let arr = [1, 2, 3]')
    a = p.statements[0]
    assert isinstance(a, ast.Assign)
    assert a.name == 'arr'
    assert isinstance(a.value, ast.ListLiteral)
    assert len(a.value.elements) == 3


def test_parse_if_else_and_binaryop():
    p = parser.parse('if 1 + 2: say "Yes" else: say "No"')
    node = p.statements[0]
    assert isinstance(node, ast.If)
    assert isinstance(node.cond, ast.BinaryOp)
    assert node.orelse is not None


def test_parse_function_def_and_return():
    p = parser.parse('def add(a, b): return a + b')
    fn = p.statements[0]
    assert isinstance(fn, ast.FunctionDef)
    assert fn.name == 'add'
    assert fn.params == ['a', 'b']
    assert isinstance(fn.body[0], ast.Return)


def test_parse_agent_call():
    p = parser.parse('agent frontend ["{\"type\": \"intent-draft\"}"]')
    ac = p.statements[0]
    assert isinstance(ac, ast.AgentCall)
    assert ac.agent == 'frontend'
