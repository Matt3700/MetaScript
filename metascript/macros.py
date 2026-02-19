from __future__ import annotations
from typing import Dict, List, Any
from . import ast as msast
import copy


def _substitute_expr(expr, mapping: Dict[str, msast.Node]):
    # returns a substituted copy of expr
    if expr is None:
        return None
    if isinstance(expr, msast.NameExpr):
        if expr.id in mapping:
            # clone mapped AST node
            return copy.deepcopy(mapping[expr.id])
        return msast.NameExpr(expr.id)
    if isinstance(expr, msast.LiteralString):
        return msast.LiteralString(expr.value)
    if isinstance(expr, msast.LiteralInt):
        return msast.LiteralInt(expr.value)
    if isinstance(expr, msast.ListLiteral):
        return msast.ListLiteral([_substitute_expr(e, mapping) for e in expr.elements])
    if isinstance(expr, msast.FunctionCall):
        return msast.FunctionCall(expr.name, [_substitute_expr(a, mapping) for a in expr.args])
    if isinstance(expr, msast.BinaryOp):
        return msast.BinaryOp(expr.op, _substitute_expr(expr.left, mapping), _substitute_expr(expr.right, mapping))
    if isinstance(expr, msast.UnaryOp):
        return msast.UnaryOp(expr.op, _substitute_expr(expr.operand, mapping))
    if isinstance(expr, msast.Await):
        return msast.Await(_substitute_expr(expr.expr, mapping))
    # fallback: deep copy
    return copy.deepcopy(expr)


def _substitute_node(node, mapping: Dict[str, msast.Node]):
    # returns a deep-copied node with parameter substitution applied
    if node is None:
        return None
    if isinstance(node, msast.Say):
        return msast.Say(_substitute_expr(node.text, mapping))
    if isinstance(node, msast.Print):
        return msast.Print(_substitute_expr(node.text, mapping))
    if isinstance(node, msast.Assign):
        return msast.Assign(node.name, _substitute_expr(node.value, mapping))
    if isinstance(node, msast.Return):
        return msast.Return(_substitute_expr(node.value, mapping))
    if isinstance(node, msast.FunctionCall):
        return msast.FunctionCall(node.name, [_substitute_expr(a, mapping) for a in node.args])
    if isinstance(node, msast.BinaryOp):
        return msast.BinaryOp(node.op, _substitute_expr(node.left, mapping), _substitute_expr(node.right, mapping))
    if isinstance(node, msast.ListLiteral):
        return msast.ListLiteral([_substitute_expr(e, mapping) for e in node.elements])
    if isinstance(node, msast.If):
        body = [_substitute_node(s, mapping) for s in node.body]
        orelse = [_substitute_node(s, mapping) for s in node.orelse] if node.orelse else None
        return msast.If(_substitute_expr(node.cond, mapping), body, orelse)
    if isinstance(node, msast.While):
        return msast.While(_substitute_expr(node.cond, mapping), [_substitute_node(s, mapping) for s in node.body])
    if isinstance(node, msast.ForLoop):
        return msast.ForLoop(node.var, _substitute_expr(node.end, mapping), [_substitute_node(s, mapping) for s in node.body])
    if isinstance(node, msast.FunctionDef):
        return msast.FunctionDef(node.name, list(node.params), [_substitute_node(s, mapping) for s in node.body], is_async=getattr(node, 'is_async', False))
    if isinstance(node, msast.DoBlock):
        return msast.DoBlock([_substitute_node(s, mapping) for s in node.body])
    if isinstance(node, msast.MatchCase):
        return msast.MatchCase(node.pattern, [_substitute_node(s, mapping) for s in node.body])
    if isinstance(node, msast.Match):
        return msast.Match(_substitute_expr(node.subject, mapping), [_substitute_node(c, mapping) for c in node.cases])
    if isinstance(node, msast.AgentCall):
        # payload is raw text; no substitution currently
        return msast.AgentCall(node.agent, node.payload)
    # MacroCall should not remain inside macro bodies in this simple model,
    # but if present, leave it as-is (it will be expanded by the caller)
    if isinstance(node, msast.MacroCall):
        return msast.MacroCall(node.name, [_substitute_expr(a, mapping) for a in node.args])
    if isinstance(node, msast.MacroDef):
        # copy macro def as-is
        return msast.MacroDef(node.name, list(node.params), [_substitute_node(s, mapping) for s in node.body])
    # fallback: deep copy
    return copy.deepcopy(node)


def _fresh_name(base: str, counter: List[int]) -> str:
    counter[0] += 1
    return f"__ms_macro_{base}_{counter[0]}"


def _collect_local_bindings(node: msast.Node, acc: set):
    """Collect names that are *declared* inside a node (assign targets,
    function names, for-loop vars, pattern names)."""
    if node is None:
        return
    if isinstance(node, msast.Assign):
        acc.add(node.name)
    if isinstance(node, msast.FunctionDef):
        acc.add(node.name)
        for p in node.params:
            acc.add(p)
        for s in node.body:
            _collect_local_bindings(s, acc)
    if isinstance(node, msast.ForLoop):
        acc.add(node.var)
        for s in node.body:
            _collect_local_bindings(s, acc)
    if isinstance(node, msast.MatchCase):
        pat = node.pattern
        if isinstance(pat, msast.NamePattern):
            acc.add(pat.name)
        if isinstance(pat, msast.ListPattern):
            for e in pat.elements:
                if isinstance(e, msast.NamePattern):
                    acc.add(e.name)
    if isinstance(node, msast.DoBlock):
        for s in node.body:
            _collect_local_bindings(s, acc)
    if isinstance(node, msast.If) or isinstance(node, msast.While) or isinstance(node, msast.Match):
        for s in getattr(node, 'body', []) or []:
            _collect_local_bindings(s, acc)
        for s in getattr(node, 'orelse', []) or []:
            _collect_local_bindings(s, acc)


def _rename_bound_identifiers(node: msast.Node, rename_map: Dict[str, str], params: set):
    """Recursively rename bound identifier *occurrences* in `node` using
    `rename_map`. Parameter names in `params` are excluded from renaming.
    This mutates and returns a copy-safe transformed node (assumes caller
    passed a deep copy if needed).
    """
    if node is None:
        return node
    # expressions
    if isinstance(node, msast.NameExpr):
        if node.id in rename_map and node.id not in params:
            return msast.NameExpr(rename_map[node.id])
        return node
    if isinstance(node, msast.LiteralString) or isinstance(node, msast.LiteralInt):
        return node
    if isinstance(node, msast.ListLiteral):
        return msast.ListLiteral([_rename_bound_identifiers(e, rename_map, params) for e in node.elements])
    if isinstance(node, msast.FunctionCall):
        return msast.FunctionCall(node.name, [_rename_bound_identifiers(a, rename_map, params) for a in node.args])
    if isinstance(node, msast.BinaryOp):
        return msast.BinaryOp(node.op, _rename_bound_identifiers(node.left, rename_map, params), _rename_bound_identifiers(node.right, rename_map, params))
    if isinstance(node, msast.Await):
        return msast.Await(_rename_bound_identifiers(node.expr, rename_map, params))

    # statements / bindings
    if isinstance(node, msast.Assign):
        tgt = node.name
        if tgt in rename_map and tgt not in params:
            tgt = rename_map[tgt]
        return msast.Assign(tgt, _rename_bound_identifiers(node.value, rename_map, params))
    if isinstance(node, msast.Say):
        return msast.Say(_rename_bound_identifiers(node.text, rename_map, params))
    if isinstance(node, msast.Print):
        return msast.Print(_rename_bound_identifiers(node.text, rename_map, params))
    if isinstance(node, msast.Return):
        return msast.Return(_rename_bound_identifiers(node.value, rename_map, params))
    if isinstance(node, msast.FunctionDef):
        name = node.name
        if name in rename_map and name not in params:
            name = rename_map[name]
        # rename params if present in rename_map (but params are usually excluded)
        params_list = [rename_map.get(p, p) for p in node.params]
        body = [_rename_bound_identifiers(s, rename_map, params) for s in node.body]
        return msast.FunctionDef(name, params_list, body, is_async=getattr(node, 'is_async', False))
    if isinstance(node, msast.ForLoop):
        var = node.var
        if var in rename_map and var not in params:
            var = rename_map[var]
        return msast.ForLoop(var, _rename_bound_identifiers(node.end, rename_map, params), [_rename_bound_identifiers(s, rename_map, params) for s in node.body])
    if isinstance(node, msast.MatchCase):
        pat = node.pattern
        if isinstance(pat, msast.NamePattern) and pat.name in rename_map and pat.name not in params:
            pat = msast.NamePattern(rename_map[pat.name])
        if isinstance(pat, msast.ListPattern):
            new_elems = []
            for e in pat.elements:
                if isinstance(e, msast.NamePattern) and e.name in rename_map and e.name not in params:
                    new_elems.append(msast.NamePattern(rename_map[e.name]))
                else:
                    new_elems.append(e)
            pat = msast.ListPattern(new_elems)
        return msast.MatchCase(pat, [_rename_bound_identifiers(s, rename_map, params) for s in node.body])
    if isinstance(node, msast.Match):
        return msast.Match(_rename_bound_identifiers(node.subject, rename_map, params), [_rename_bound_identifiers(c, rename_map, params) for c in node.cases])
    if isinstance(node, msast.If):
        return msast.If(_rename_bound_identifiers(node.cond, rename_map, params), [_rename_bound_identifiers(s, rename_map, params) for s in node.body], [_rename_bound_identifiers(s, rename_map, params) for s in node.orelse] if node.orelse else None)
    if isinstance(node, msast.While):
        return msast.While(_rename_bound_identifiers(node.cond, rename_map, params), [_rename_bound_identifiers(s, rename_map, params) for s in node.body])
    if isinstance(node, msast.DoBlock):
        return msast.DoBlock([_rename_bound_identifiers(s, rename_map, params) for s in node.body])
    if isinstance(node, msast.MacroCall):
        return msast.MacroCall(node.name, [_rename_bound_identifiers(a, rename_map, params) for a in node.args])
    # fallback
    return copy.deepcopy(node)


def expand_macros(program: msast.Program) -> msast.Program:
    """Expand compile-time macros in `program` with hygiene and scoping.

    - Supports scoped macro definitions (macros defined inside blocks/functions
      are visible only within that scope).
    - Performs alpha-renaming (non-hygienic) for macro-local bindings to avoid
      accidental collisions with surrounding code.
    """
    uid = [0]

    def make_fresh(orig: str) -> str:
        return _fresh_name(orig, uid)

    def lookup_macro(name: str, env_stack: List[Dict[str, msast.MacroDef]]):
        for env in reversed(env_stack):
            if name in env:
                return env[name]
        return None

    def expand_stmt_list(stmts: List[msast.Node], env_stack: List[Dict[str, msast.MacroDef]]) -> List[msast.Node]:
        out: List[msast.Node] = []
        # local macro table for this block
        local_env: Dict[str, msast.MacroDef] = {}
        env_stack.append(local_env)
        try:
            for s in stmts:
                # if this statement is a macro def, register it in local_env
                if isinstance(s, msast.MacroDef):
                    local_env[s.name] = s
                    # macro defs do not emit runtime nodes
                    continue
                res = expand_node(s, env_stack)
                if isinstance(res, list):
                    out.extend(res)
                elif res is not None:
                    out.append(res)
        finally:
            env_stack.pop()
        return out

    def expand_node(node: msast.Node, env_stack: List[Dict[str, msast.MacroDef]]):
        # Macro call: find macro in current lexical environment
        if isinstance(node, msast.MacroCall):
            macro = lookup_macro(node.name, env_stack)
            if macro is None:
                raise ValueError(f"Undefined macro '{node.name}'")
            # alpha-rename local bindings inside macro body to fresh names
            bound_names = set()
            for b in macro.body:
                _collect_local_bindings(b, bound_names)
            # exclude macro parameters from renaming
            params = set(macro.params)
            rename_map: Dict[str, str] = {}
            for nm in bound_names:
                if nm in params:
                    continue
                rename_map[nm] = make_fresh(nm)
            # apply renaming to a deep copy of the macro body
            renamed_body = [_rename_bound_identifiers(copy.deepcopy(b), rename_map, params) for b in macro.body]
            # prepare substitution mapping for parameters
            mapping: Dict[str, msast.Node] = {}
            for i, pname in enumerate(macro.params):
                if i < len(node.args):
                    mapping[pname] = node.args[i]
                else:
                    mapping[pname] = msast.NameExpr(pname)
            # substitute and then recursively expand the substituted nodes
            expanded: List[msast.Node] = []
            for b in renamed_body:
                sub = _substitute_node(b, mapping)
                sub_expanded = expand_node(sub, env_stack)
                if isinstance(sub_expanded, list):
                    expanded.extend(sub_expanded)
                elif sub_expanded is not None:
                    expanded.append(sub_expanded)
            return expanded

        # Recurse into containers and respect lexical scoping for nested blocks
        if isinstance(node, msast.FunctionDef):
            body = expand_stmt_list(node.body, env_stack)
            return msast.FunctionDef(node.name, list(node.params), body, is_async=getattr(node, 'is_async', False))
        if isinstance(node, msast.DoBlock):
            return msast.DoBlock(expand_stmt_list(node.body, env_stack))
        if isinstance(node, msast.If):
            cond = _substitute_expr(node.cond, {})
            body = expand_stmt_list(node.body, env_stack)
            orelse = expand_stmt_list(node.orelse, env_stack) if node.orelse else None
            return msast.If(cond, body, orelse)
        if isinstance(node, msast.While):
            return msast.While(_substitute_expr(node.cond, {}), expand_stmt_list(node.body, env_stack))
        if isinstance(node, msast.ForLoop):
            return msast.ForLoop(node.var, _substitute_expr(node.end, {}), expand_stmt_list(node.body, env_stack))
        if isinstance(node, msast.Match):
            cases = []
            for c in node.cases:
                cases.append(msast.MatchCase(c.pattern, expand_stmt_list(c.body, env_stack)))
            return msast.Match(_substitute_expr(node.subject, {}), cases)

        # Simple recursion/substitution for expressions and non-block statements
        if isinstance(node, msast.Say):
            return msast.Say(_substitute_expr(node.text, {}))
        if isinstance(node, msast.Print):
            return msast.Print(_substitute_expr(node.text, {}))
        if isinstance(node, msast.Assign):
            return msast.Assign(node.name, _substitute_expr(node.value, {}))
        if isinstance(node, msast.Return):
            return msast.Return(_substitute_expr(node.value, {}))
        if isinstance(node, msast.FunctionCall):
            return msast.FunctionCall(node.name, [_substitute_expr(a, {}) for a in node.args])
        # fallback: copy node
        return copy.deepcopy(node)

    # start with an empty global macro environment
    env_stack: List[Dict[str, msast.MacroDef]] = [{}]
    out = expand_stmt_list(program.statements, env_stack)
    return msast.Program(out)
