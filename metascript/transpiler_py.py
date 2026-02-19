from __future__ import annotations
from . import ast as msast
from . import macros as ms_macros


def _emit_expr(e: msast.Node) -> str:
    if isinstance(e, msast.LiteralString):
        return repr(e.value)
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
    return 'None'


def _emit_stmt(n: msast.Node, indent: int = 0) -> str:
    pad = ' ' * (4 * indent)
    if isinstance(n, msast.Say) or isinstance(n, msast.Print):
        return pad + f'print({_emit_expr(n.text)})'
    if isinstance(n, msast.Assign):
        return pad + f'{n.name} = {_emit_expr(n.value)}'
    if isinstance(n, msast.FunctionDef):
        prefix = 'async ' if getattr(n, 'is_async', False) else ''
        head = pad + f'{prefix}def {n.name}({', '.join(n.params)}):'
        body = '\n'.join([_emit_stmt(s, indent + 1) for s in n.body]) if n.body else pad + '    pass'
        return head + '\n' + body
    if isinstance(n, msast.Return):
        return pad + f'return {_emit_expr(n.value)}'
    if isinstance(n, msast.ForLoop):
        body = '\n'.join([_emit_stmt(s, indent + 1) for s in n.body])
        # Function-call range: emit directly
        if isinstance(n.end, msast.FunctionCall) and getattr(n.end, 'name', '') == 'range':
            return pad + f'for {n.var} in {_emit_expr(n.end)}:\n' + body
        # integer literal -> range(end)
        if isinstance(n.end, msast.LiteralInt):
            return pad + f'for {n.var} in range({_emit_expr(n.end)}):\n' + body
        # iterable (name, list, etc.) -> iterate directly
        return pad + f'for {n.var} in {_emit_expr(n.end)}:\n' + body
    if isinstance(n, msast.If):
        head = pad + f'if {_emit_expr(n.cond)}:'
        body = '\n'.join([_emit_stmt(s, indent + 1) for s in n.body])
        o = head + '\n' + body
        if n.orelse:
            o += '\n' + pad + 'else:\n' + '\n'.join([_emit_stmt(s, indent + 1) for s in n.orelse])
        return o
    if isinstance(n, msast.FunctionCall):
        return pad + _emit_expr(n)
    if isinstance(n, msast.Match):
        # naive translation: assign subject and emit if/elif chains
        subj = '__ms_match_val'
        out_lines = [pad + f'{subj} = {_emit_expr(n.subject)}']
        first = True
        for case in n.cases:
            pat = case.pattern
            if isinstance(pat, msast.LiteralPattern) and isinstance(pat.value, msast.LiteralInt):
                cond = f'{subj} == {pat.value.value}'
                binds = []
            elif isinstance(pat, msast.WildcardPattern):
                cond = 'True'
                binds = []
            elif isinstance(pat, msast.NamePattern):
                cond = 'True'
                binds = [f'{pat.name} = {subj}']
            else:
                cond = 'False'
                binds = []
            prefix = 'if' if first else 'elif'
            first = False
            out_lines.append(pad + f'{prefix} {cond}:')
            for b in binds:
                out_lines.append(pad + '    ' + b)
            for stmt in case.body:
                out_lines.append(_emit_stmt(stmt, indent + 1))
        return '\n'.join(out_lines)

    if isinstance(n, msast.AgentCall):
        # robustly parse payload (bracket-display or JSON string)
        import json
        payload_obj = None
        try:
            payload_obj = json.loads(n.payload)
        except Exception:
            try:
                payload_obj = json.loads('{' + n.payload + '}')
            except Exception:
                # tolerate unescaped backslashes (Windows paths) by escaping them
                try:
                    payload_obj = json.loads('{' + n.payload.replace("\\", "\\\\") + '}')
                except Exception:
                    payload_obj = None

        if n.agent == 'frontend':
            # tool call
            if isinstance(payload_obj, dict) and (payload_obj.get('type') == 'call_tool' or payload_obj.get('action') == 'call_tool'):
                body = payload_obj.get('payload') or {}
                tool_name = body.get('tool') or body.get('name')
                params = body.get('params', {}) if isinstance(body, dict) else {}
                out = []
                out.append(pad + 'from metascript.agents import frontend_agent as __ms_frontend')
                out.append(pad + 'if globals().get("AUTONOMY_ENABLED", False):')
                out.append(pad + f'    __ms_res = __ms_frontend.call_tool({repr(tool_name)}, {repr(params)})')
                out.append(pad + '    print(' + repr('[agent frontend] tool_result: ') + ' + str(__ms_res))')
                out.append(pad + 'else:')
                out.append(pad + '    print(' + repr('[agent frontend] tool_call blocked (autonomy disabled)') + ')')
                return '\n'.join(out)
            # natural_text / intent -> ask frontend at transpile-time and inline returned MS
            if isinstance(payload_obj, dict) and ('natural_text' in payload_obj or 'intent' in payload_obj):
                natural = payload_obj.get('natural_text') or payload_obj.get('intent')
                from metascript import parser as _ms_parser, transpiler_py as _ms_transpiler, agents as _ms_agents
                try:
                    resp = _ms_agents.frontend_agent.handle_message({'type': 'intent-draft', 'payload': {'natural_text': natural, 'target_syntax': payload_obj.get('target_syntax', 'python-style')}})
                    code_snippet = resp.get('payload', {}).get('code', '') if isinstance(resp, dict) else ''
                    if code_snippet:
                        # parse and transpile snippet and inline Python
                        return _ms_transpiler.transpile(_ms_parser.parse(code_snippet))
                except Exception:
                    return pad + f'print({repr("[agent frontend] (error producing explanation)")})'
            # fallback: echo payload
            return pad + f'print({repr("[agent frontend] " + str(payload_obj if payload_obj is not None else n.payload))})'

        if n.agent == 'backend':
            # attempt to validate/plan at transpile time
            if isinstance(payload_obj, dict) and payload_obj.get('action') == 'validate':
                from metascript.agents import backend_agent as __ms_backend
                res = __ms_backend.handle_message({'action': 'validate', 'payload': payload_obj})
                if not res.get('approved'):
                    return pad + 'print(' + repr('[agent backend] Execution rejected: ' + res.get('reason', '')) + ')\n' + pad + 'raise SystemExit(1)'
                return pad + 'print(' + repr('[agent backend] Approved: ') + ' + ' + repr(str(res.get('plan'))) + ')'
            # fallback
            return pad + f'print({repr("[agent backend] " + str(payload_obj if payload_obj is not None else n.payload))})'

    # fallback
    return pad + '# unsupported-stmt'


def transpile(program: msast.Program) -> str:
    # expand compile-time macros first (parity with JS backend)
    try:
        program = ms_macros.expand_macros(program)
    except Exception:
        pass

    header = '# Transpiled by metascript transpiler_py\n'
    body = '\n'.join([_emit_stmt(s, 0) for s in program.statements])
    return header + body + '\n'