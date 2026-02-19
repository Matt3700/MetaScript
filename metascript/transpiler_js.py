from __future__ import annotations
from . import ast as msast
from typing import List
from . import macros as ms_macros


def _emit_expr(e) -> str:
    if isinstance(e, msast.LiteralString):
        return '"' + e.value.replace('"', '\\"') + '"'
    if isinstance(e, msast.LiteralInt):
        return str(e.value)
    if isinstance(e, msast.NameExpr):
        return e.id
    if isinstance(e, msast.ListLiteral):
        return '[' + ', '.join([_emit_expr(x) for x in e.elements]) + ']'
    if isinstance(e, msast.FunctionCall):
        return f"{e.name}({', '.join([_emit_expr(a) for a in e.args])})"
    if isinstance(e, msast.BinaryOp):
        return f"({_emit_expr(e.left)} {e.op} {_emit_expr(e.right)})"
    if isinstance(e, msast.Await):
        return f"await {_emit_expr(e.expr)}"
    return 'undefined'


def _emit_pattern_match_check(subject_var: str, pat) -> (str, List[str]):
    # return (condition_js, bindings_js_lines)
    if isinstance(pat, msast.WildcardPattern):
        return ('true', [])
    if isinstance(pat, msast.LiteralPattern):
        lit = pat.value
        if isinstance(lit, msast.LiteralInt):
            return (f'{subject_var} === {lit.value}', [])
        if isinstance(lit, msast.LiteralString):
            return (f'{subject_var} === "{lit.value}"', [])
    if isinstance(pat, msast.NamePattern):
        # bind the name to subject
        return ('true', [f'let {pat.name} = {subject_var};'])
    if isinstance(pat, msast.ListPattern):
        checks = []
        binds = []
        checks.append(f'Array.isArray({subject_var})')
        checks.append(f'{subject_var}.length === {len(pat.elements)}')
        for idx, subpat in enumerate(pat.elements):
            if isinstance(subpat, msast.NamePattern):
                binds.append(f'let {subpat.name} = {subject_var}[{idx}];')
            elif isinstance(subpat, msast.LiteralPattern) and isinstance(subpat.value, msast.LiteralInt):
                checks.append(f'{subject_var}[{idx}] === {subpat.value.value}')
            elif isinstance(subpat, msast.LiteralPattern) and isinstance(subpat.value, msast.LiteralString):
                checks.append(f'{subject_var}[{idx}] === "{subpat.value.value}"')
        cond = ' && '.join(checks) if checks else 'true'
        return (cond, binds)
    return ('false', [])


def _emit_node(n) -> str:
    if isinstance(n, msast.Program):
        return "\n".join([_emit_node(s) for s in n.statements])
    if isinstance(n, msast.Say) or isinstance(n, msast.Print):
        return f'console.log({_emit_expr(n.text)});'
    if isinstance(n, msast.Assign):
        return f'let {n.name} = {_emit_expr(n.value)};'
    if isinstance(n, msast.If):
        cond = _emit_expr(n.cond)
        body = '\n'.join([_emit_node(s) for s in n.body])
        orelse = ''
        if n.orelse:
            orelse = ' else { ' + '\n'.join([_emit_node(s) for s in n.orelse]) + ' }'
        return f'if ({cond}) {{ {body} }}{orelse}'
    if isinstance(n, msast.While):
        return f'while ({_emit_expr(n.cond)}) {{ ' + '\n'.join([_emit_node(s) for s in n.body]) + ' }'
    if isinstance(n, msast.ForLoop):
        body = '\n'.join([_emit_node(s) for s in n.body])
        # numeric ranges
        if isinstance(n.end, msast.FunctionCall) and getattr(n.end, 'name', '') == 'range':
            args = n.end.args
            if len(args) == 1:
                stop = _emit_expr(args[0])
                return f'for (let {n.var}=0; {n.var}<{stop}; {n.var}++) {{ {body} }}'
            if len(args) == 2:
                start = _emit_expr(args[0])
                stop = _emit_expr(args[1])
                return f'for (let {n.var}={start}; {n.var}<{stop}; {n.var}++) {{ {body} }}'
            if len(args) == 3:
                start = _emit_expr(args[0])
                stop = _emit_expr(args[1])
                step = _emit_expr(args[2])
                return f'for (let {n.var}={start}; {n.var}<{stop}; {n.var}+= {step}) {{ {body} }}'
            # fallback
            end_expr = _emit_expr(n.end)
            return f'for (let {n.var}=0; {n.var}<{end_expr}; {n.var}++) {{ {body} }}'
        # integer literal end
        if isinstance(n.end, msast.LiteralInt):
            end_expr = _emit_expr(n.end)
            return f'for (let {n.var}=0; {n.var}<{end_expr}; {n.var}++) {{ {body} }}'
        # iterable -> for-of
        end_expr = _emit_expr(n.end)
        return f'for (const {n.var} of {end_expr}) {{ {body} }}'
    if isinstance(n, msast.FunctionDef):
        params = ', '.join(n.params)
        body = '\n'.join([_emit_node(s) for s in n.body])
        prefix = 'async ' if getattr(n, 'is_async', False) else ''
        return f'{prefix}function {n.name}({params}) {{ {body} }}'
    if isinstance(n, msast.Return):
        return f'return {_emit_expr(n.value)};'
    if isinstance(n, msast.DoBlock):
        return '\n'.join([_emit_node(s) for s in n.body])
    if isinstance(n, msast.Match):
        subj_var = '__ms_match_val'
        out = [f'const {subj_var} = {_emit_expr(n.subject)};']
        first = True
        for case in n.cases:
            cond, binds = _emit_pattern_match_check(subj_var, case.pattern)
            prefix = 'if' if first else 'else if'
            first = False
            out.append(f'{prefix} ({cond}) {{')
            for b in binds:
                out.append(b)
            for stmt in case.body:
                out.append(_emit_node(stmt))
            out.append('}')
        return '\n'.join(out)
    if isinstance(n, msast.FunctionCall):
        return _emit_expr(n) + ';'
    if isinstance(n, msast.Await):
        return f'await {_emit_expr(n.expr)};'
    if isinstance(n, msast.AgentCall):
        return f'agentCall("{n.agent}", JSON.parse("{n.payload.replace("\"", "\\\"")}"));'
    if isinstance(n, msast.MacroDef):
        # compile-time macros are represented as runtime helpers for now
        params = ', '.join(n.params)
        body = '\n'.join([_emit_node(s) for s in n.body])
        return f'function __macro_{n.name}({params}) {{ {body} }}'
    if isinstance(n, msast.MacroCall):
        args = ', '.join([_emit_expr(a) for a in n.args])
        return f'__macro_{n.name}({args});'
    return '/* unsupported */'


def transpile(program: msast.Program) -> str:
    # Expand compile-time macros before emitting code
    program = ms_macros.expand_macros(program)

    header = "// Transpiled by metascript transpiler_js (expanded features)\n"
    body = _emit_node(program)
    return header + body + "\n"
