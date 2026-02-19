from __future__ import annotations
from . import ast as msast


def _unparse_expr(e: msast.Node) -> str:
    if isinstance(e, msast.LiteralString):
        return '"' + e.value.replace('"', '\\"') + '"'
    if isinstance(e, msast.LiteralInt):
        return str(e.value)
    if isinstance(e, msast.NameExpr):
        return e.id
    if isinstance(e, msast.ListLiteral):
        return '[' + ', '.join([_unparse_expr(x) for x in e.elements]) + ']'
    if isinstance(e, msast.FunctionCall):
        return f"{e.name}({', '.join([_unparse_expr(a) for a in e.args])})"
    if isinstance(e, msast.BinaryOp):
        return f"({_unparse_expr(e.left)} {e.op} {_unparse_expr(e.right)})"
    if isinstance(e, msast.Await):
        return 'await ' + _unparse_expr(e.expr)
    return 'None'


def _unparse_stmt(n: msast.Node, indent: int = 0) -> str:
    pad = ' ' * (4 * indent)
    if isinstance(n, msast.Say):
        return pad + f'say {_unparse_expr(n.text)}'
    if isinstance(n, msast.Print):
        return pad + f'print {_unparse_expr(n.text)}'
    if isinstance(n, msast.Assign):
        return pad + f'let {n.name} = {_unparse_expr(n.value)}'
    if isinstance(n, msast.FunctionDef):
        head = pad + f'def {n.name}({", ".join(n.params)}):'
        body = '\n'.join([_unparse_stmt(s, indent + 1) for s in n.body]) if n.body else pad + '    pass'
        return head + '\n' + body
    if isinstance(n, msast.Return):
        return pad + f'return {_unparse_expr(n.value)}'
    if isinstance(n, msast.ForLoop):
        # emit depending on end form
        if isinstance(n.end, msast.FunctionCall) and getattr(n.end, 'name', '') == 'range':
            return pad + f'for {n.var} in {_unparse_expr(n.end)}:\n' + '\n'.join([_unparse_stmt(s, indent + 1) for s in n.body])
        if isinstance(n.end, msast.LiteralInt):
            return pad + f'for {n.var} in range({_unparse_expr(n.end)}):\n' + '\n'.join([_unparse_stmt(s, indent + 1) for s in n.body])
        return pad + f'for {n.var} in {_unparse_expr(n.end)}:\n' + '\n'.join([_unparse_stmt(s, indent + 1) for s in n.body])
    if isinstance(n, msast.If):
        head = pad + f'if {_unparse_expr(n.cond)}:'
        body = '\n'.join([_unparse_stmt(s, indent + 1) for s in n.body])
        o = head + '\n' + body
        if n.orelse:
            o += '\n' + pad + 'else:' + '\n' + '\n'.join([_unparse_stmt(s, indent + 1) for s in n.orelse])
        return o
    if isinstance(n, msast.FunctionCall):
        return pad + _unparse_expr(n)
    if isinstance(n, msast.Match):
        out = pad + f'match {_unparse_expr(n.subject)}:'
        for c in n.cases:
            pat = c.pattern
            if isinstance(pat, msast.WildcardPattern):
                psrc = '_'
            elif isinstance(pat, msast.NamePattern):
                psrc = pat.name
            elif isinstance(pat, msast.LiteralPattern) and isinstance(pat.value, msast.LiteralInt):
                psrc = str(pat.value.value)
            elif isinstance(pat, msast.ListPattern):
                psrc = '[' + ', '.join([ (e.name if isinstance(e, msast.NamePattern) else (str(e.value.value) if isinstance(e, msast.LiteralPattern) and isinstance(e.value, msast.LiteralInt) else '?')) for e in pat.elements]) + ']'
            else:
                psrc = '_'
            out += '\n' + pad + f'    case {psrc}: ' + '\n'.join([_unparse_stmt(s, indent + 2) for s in c.body])
        return out
    return pad + '# unsupported'


def unparse(program: msast.Program) -> str:
    return '\n'.join([_unparse_stmt(s, 0) for s in program.statements]) + '\n'