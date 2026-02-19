from __future__ import annotations
from typing import List, Optional
from . import ast as msast
import pkgutil

# Parser implementation (Lark transformer + robust fallback) — expanded to
# handle pattern matching, async/await, and macros for the project's AST.
try:
    from lark import Lark, Transformer, v_args, Tree
    _has_lark = True
except Exception:
    Lark = None  # type: ignore
    Transformer = object  # type: ignore
    v_args = lambda *a, **k: (lambda f: f)
    _has_lark = False

if _has_lark:
    _grammar_text = pkgutil.get_data(__name__, "grammar.lark").decode("utf-8")
    _parser = Lark(_grammar_text, start="start", parser="lalr")

    @v_args(inline=True)
    class _MS_Transformer(Transformer):
        def start(self, prog):
            return prog

        def program(self, *statements):
            return msast.Program(list(statements))

        def say_stmt(self, expr):
            return msast.Say(expr)

        def print_stmt(self, expr):
            return msast.Print(expr)

        def let_stmt(self, name, _eq, expr):
            return msast.Assign(name.value, expr)

        def assign_stmt(self, name, _eq, expr):
            return msast.Assign(name.value, expr)

        def return_stmt(self, expr):
            return msast.Return(expr)

        def if_stmt(self, cond, _colon, body, else_part=None):
            orelse = None
            if else_part is not None:
                orelse = else_part.children[-1]
            return msast.If(cond, body if isinstance(body, list) else [body], orelse)

        def while_stmt(self, cond, _colon, body):
            return msast.While(cond, body if isinstance(body, list) else [body])

        def for_stmt(self, name, _in, end, _colon, body):
            return msast.ForLoop(name.value, end, body if isinstance(body, list) else [body])

        def def_stmt(self, name, _lp=None, params=None, _rp=None, _colon=None, body=None):
            params_list = []
            if params is not None:
                params_list = [p.value for p in params.children]
            return msast.FunctionDef(name.value, params_list, body if isinstance(body, list) else [body], is_async=False)

        def async_def(self, _async_kw, defnode):
            defnode.is_async = True
            return defnode

        def function_call(self, name, _lp=None, args=None, _rp=None):
            args_list = []
            if args is not None:
                args_list = args if isinstance(args, list) else [args]
            return msast.FunctionCall(name.value, args_list)

        def agent_call(self, _agent_kw, name, _lb, payload, _rb):
            return msast.AgentCall(name.value, payload[1:-1])

        def match_stmt(self, _kw, subject, _colon, *cases):
            return msast.Match(subject, list(cases))

        def match_case(self, _case_kw, pattern, _colon, body):
            return msast.MatchCase(pattern, body if isinstance(body, list) else [body])

        def wildcard_pattern(self):
            return msast.WildcardPattern()

        def name_pattern(self, t):
            return msast.NamePattern(t.value)

        def int_pattern(self, t):
            return msast.LiteralPattern(msast.LiteralInt(int(t)))

        def string_pattern(self, s):
            return msast.LiteralPattern(msast.LiteralString(s[1:-1]))

        def list_pattern(self, _lb, *elems):
            items = []
            for e in elems:
                if isinstance(e, list):
                    items.extend(e)
                else:
                    items.append(e)
            return msast.ListPattern(items)

        def range_literal(self, left, _dots, right):
            # transform `INT .. INT` into `range(start, end+1)`
            # left/right are already transformed AST nodes (LiteralInt)
            return msast.FunctionCall('range', [left, msast.BinaryOp('+', right, msast.LiteralInt(1))])

        def macro_def(self, _kw, name, _lp=None, params=None, _rp=None, _colon=None, body=None):
            params_list = []
            if params is not None:
                params_list = [p.value for p in params.children]
            return msast.MacroDef(name.value, params_list, body if isinstance(body, list) else [body])

        def await_expr(self, _await, atom):
            return msast.Await(atom)

        def string(self, s):
            return msast.LiteralString(s[1:-1])

        def int(self, t):
            return msast.LiteralInt(int(t))

        def name(self, t):
            return msast.NameExpr(t.value)

        def add(self, a, b):
            return msast.BinaryOp('+', a, b)

        def sub(self, a, b):
            return msast.BinaryOp('-', a, b)

        def mul(self, a, b):
            return msast.BinaryOp('*', a, b)

        def div(self, a, b):
            return msast.BinaryOp('/', a, b)

        def list_literal(self, _lb, *elems):
            items = []
            for e in elems:
                if isinstance(e, list):
                    items.extend(e)
                else:
                    items.append(e)
            return msast.ListLiteral(items)


def _parse_with_lark(source: str) -> msast.Program:
    tree = _parser.parse(source)
    return _MS_Transformer().transform(tree)


# Fallback parser (supports single-line compound statements + patterns/macros/await)
class _ExprParser:
    def __init__(self, s: str):
        self.s = s.strip()
        self.i = 0

    def peek(self) -> Optional[str]:
        return self.s[self.i] if self.i < len(self.s) else None

    def consume_ws(self):
        while self.peek() and self.peek().isspace():
            self.i += 1

    def parse_number_or_name(self):
        import re
        m = re.match(r"\d+", self.s[self.i:])
        if m:
            val = int(m.group(0))
            self.i += len(m.group(0))
            return msast.LiteralInt(val)
        m = re.match(r"[A-Za-z_]\w*", self.s[self.i:])
        if m:
            tok = m.group(0)
            self.i += len(tok)
            return msast.NameExpr(tok)
        return None

    def parse_name_or_call(self):
        import re
        # number literal
        m = re.match(r"\d+", self.s[self.i:])
        if m:
            val = int(m.group(0))
            self.i += len(m.group(0))
            return msast.LiteralInt(val)
        # name or function call
        m = re.match(r"[A-Za-z_]\w*", self.s[self.i:])
        if m:
            name = m.group(0)
            self.i += len(name)
            self.consume_ws()
            if self.peek() == '(':
                self.i += 1
                args = []
                while True:
                    self.consume_ws()
                    if self.peek() == ')':
                        self.i += 1
                        break
                    args.append(self.parse_expr())
                    self.consume_ws()
                    if self.peek() == ',':
                        self.i += 1
                        continue
                    if self.peek() == ')':
                        self.i += 1
                        break
                return msast.FunctionCall(name, args)
            return msast.NameExpr(name)
        return None

    def parse_atom(self):
        self.consume_ws()
        # support `await <atom>` at expression level
        if self.s[self.i:self.i+6] == 'await ':
            self.i += 6
            atom = self.parse_atom()
            return msast.Await(atom)
        ch = self.peek()
        if ch == '"' or ch == "'":
            quote = ch
            end = self.s.find(quote, self.i + 1)
            if end == -1:
                raise ValueError("Unterminated string")
            val = self.s[self.i + 1:end]
            self.i = end + 1
            return msast.LiteralString(val)
        if ch == '[':
            self.i += 1
            elems = []
            while True:
                self.consume_ws()
                if self.peek() == ']':
                    self.i += 1
                    break
                elem = self.parse_expr()
                elems.append(elem)
                self.consume_ws()
                if self.peek() == ',':
                    self.i += 1
                    continue
                if self.peek() == ']':
                    self.i += 1
                    break
            return msast.ListLiteral(elems)
        if ch == '(':
            self.i += 1
            expr = self.parse_expr()
            if self.peek() == ')':
                self.i += 1
            return expr
        return self.parse_name_or_call()

    def parse_term(self):
        left = self.parse_atom()
        while True:
            self.consume_ws()
            if self.s[self.i:self.i+1] == '*':
                self.i += 1
                right = self.parse_atom()
                left = msast.BinaryOp('*', left, right)
                continue
            if self.s[self.i:self.i+1] == '/':
                self.i += 1
                right = self.parse_atom()
                left = msast.BinaryOp('/', left, right)
                continue
            break
        return left

    def parse_expr(self):
        left = self.parse_term()
        while True:
            self.consume_ws()
            if self.s[self.i:self.i+1] == '+':
                self.i += 1
                right = self.parse_term()
                left = msast.BinaryOp('+', left, right)
                continue
            if self.s[self.i:self.i+1] == '-':
                self.i += 1
                right = self.parse_term()
                left = msast.BinaryOp('-', left, right)
                continue
            break
        return left


def _strip_quotes(s: str) -> str:
    return s[1:-1] if len(s) >= 2 and s[0] in ('"', "'") and s[-1] in ('"', "'") else s


def _parse_pattern(pat_src: str):
    pat_src = pat_src.strip()
    if pat_src == '_':
        return msast.WildcardPattern()
    if pat_src.isdigit():
        return msast.LiteralPattern(msast.LiteralInt(int(pat_src)))
    if (pat_src.startswith('"') and pat_src.endswith('"')) or (pat_src.startswith("'") and pat_src.endswith("'")):
        return msast.LiteralPattern(msast.LiteralString(_strip_quotes(pat_src)))
    if pat_src.startswith('[') and pat_src.endswith(']'):
        inner = pat_src[1:-1].strip()
        if not inner:
            return msast.ListPattern([])
        parts = [p.strip() for p in inner.split(',')]
        elems = [_parse_pattern(p) for p in parts]
        return msast.ListPattern(elems)
    return msast.NamePattern(pat_src)


def _parse_line(line: str) -> Optional[msast.Node]:
    line = line.strip()
    if not line:
        return None
    # say / print
    if line.startswith("say "):
        expr = line[4:].strip()
        val = _ExprParser(expr).parse_expr()
        return msast.Say(val)
    if line.startswith("print "):
        expr = line[6:].strip()
        val = _ExprParser(expr).parse_expr()
        return msast.Print(val)
    # let
    if line.startswith("let "):
        rest = line[4:]
        if "=" in rest:
            name, expr = rest.split("=", 1)
            name = name.strip()
            val = _ExprParser(expr.strip()).parse_expr()
            return msast.Assign(name, val)
    # macro def (single-line)
    if line.startswith("macro "):
        import re
        m = re.match(r"macro\s+(\w+)\s*\(([^)]*)\)\s*:\s*(.+)", line)
        if m:
            name = m.group(1)
            params = [p.strip() for p in m.group(2).split(",") if p.strip()]
            body_src = m.group(3)
            body_node = _parse_line(body_src)
            body = [body_node] if body_node is not None else []
            return msast.MacroDef(name, params, body)
    # macro call: @name(...)
    if line.startswith("@") and "(" in line:
        name, rest = line[1:].split("(", 1)
        name = name.strip()
        args_text = rest[:-1].strip()
        args = []
        if args_text:
            for a in args_text.split(','):
                args.append(_ExprParser(a.strip()).parse_expr())
        return msast.MacroCall(name, args)
    # async def single-line
    if line.startswith("async def "):
        import re
        m = re.match(r"async\s+def\s+(\w+)\s*\(([^)]*)\)\s*:\s*(.+)", line)
        if m:
            name = m.group(1)
            params = [p.strip() for p in m.group(2).split(",") if p.strip()]
            body_src = m.group(3)
            body_node = _parse_line(body_src)
            body = [body_node] if body_node is not None else []
            return msast.FunctionDef(name, params, body, is_async=True)
    # def (single-line body only)
    if line.startswith("def "):
        import re
        m = re.match(r"def\s+(\w+)\s*\(([^)]*)\)\s*:\s*(.+)", line)
        if m:
            name = m.group(1)
            params = [p.strip() for p in m.group(2).split(",") if p.strip()]
            body_src = m.group(3)
            body_node = _parse_line(body_src)
            body = [body_node] if body_node is not None else []
            return msast.FunctionDef(name, params, body)
    # return
    if line.startswith("return "):
        expr = line[len("return "):].strip()
        return msast.Return(_ExprParser(expr).parse_expr())
    # match single-line: match <expr>: case P: STMT [case P: STMT]...
    if line.startswith("match "):
        import re
        m = re.match(r"match\s+(.+?)\s*:\s*(.+)", line)
        if m:
            subj_src = m.group(1)
            cases_src = m.group(2)
            subj = _ExprParser(subj_src).parse_expr()
            case_parts = [c.strip() for c in re.split(r'\bcase\b', cases_src) if c.strip()]
            cases = []
            for cp in case_parts:
                cm = re.match(r"(.+?)\s*:\s*(.+)$", cp)
                if not cm:
                    continue
                pat_src = cm.group(1).strip()
                stmt_src = cm.group(2).strip()
                pat = _parse_pattern(pat_src)
                body_node = _parse_line(stmt_src)
                cases.append(msast.MatchCase(pat, [body_node] if body_node else []))
            return msast.Match(subj, cases)
    # if single-line: if COND: stmt [else: stmt]
    if line.startswith("if "):
        import re
        m = re.match(r"if\s+(.+?)\s*:\s*(.+?)(?:\s+else\s*:\s*(.+))?$", line)
        if m:
            cond_src = m.group(1)
            then_src = m.group(2)
            else_src = m.group(3)
            cond = _ExprParser(cond_src).parse_expr()
            then_node = _parse_line(then_src)
            else_node = _parse_line(else_src) if else_src else None
            return msast.If(cond, [then_node] if then_node else [], [else_node] if else_node else None)
    # while single-line
    if line.startswith("while "):
        import re
        m = re.match(r"while\s+(.+?)\s*:\s*(.+)", line)
        if m:
            cond = _ExprParser(m.group(1)).parse_expr()
            body = _parse_line(m.group(2))
            return msast.While(cond, [body] if body else [])
    # for single-line — support range(expr), range(start,stop[,step]), iterable names/list literals, and `start..end` ranges
    if line.startswith("for "):
        import re
        # range(...) with arbitrary inner expression(s)
        m = re.match(r"for\s+(\w+)\s+in\s+range\(([^)]*)\)\s*:\s*(.+)", line)
        if m:
            var = m.group(1)
            inner = m.group(2).strip()
            body_src = m.group(3)
            body = _parse_line(body_src)
            # multiple args -> FunctionCall('range', args...)
            if "," in inner:
                parts = [p.strip() for p in inner.split(',') if p.strip()]
                args = [_ExprParser(p).parse_expr() for p in parts]
                return msast.ForLoop(var, msast.FunctionCall('range', args), [body] if body else [])
            # single expression -> use as-is
            end_expr = _ExprParser(inner).parse_expr() if inner else msast.LiteralInt(0)
            return msast.ForLoop(var, end_expr, [body] if body else [])
        # generic iterable or start..end literal
        m2 = re.match(r"for\s+(\w+)\s+in\s+(.+?)\s*:\s*(.+)", line)
        if m2:
            var = m2.group(1)
            iterable_src = m2.group(2).strip()
            body_src = m2.group(3)
            # start..end literal -> convert to range(start, end+1)
            rd = re.match(r"(.+)\.\.\s*(.+)", iterable_src)
            if rd:
                left = rd.group(1).strip()
                right = rd.group(2).strip()
                start_e = _ExprParser(left).parse_expr()
                end_e = _ExprParser(right).parse_expr()
                # make range(start, end+1) to represent inclusive ..
                end_plus_one = msast.BinaryOp('+', end_e, msast.LiteralInt(1))
                return msast.ForLoop(var, msast.FunctionCall('range', [start_e, end_plus_one]), [_parse_line(body_src)] if _parse_line(body_src) else [])
            # otherwise parse iterable expression (name, list literal, etc.)
            iter_expr = _ExprParser(iterable_src).parse_expr()
            return msast.ForLoop(var, iter_expr, [_parse_line(body_src)] if _parse_line(body_src) else [])
    # agent call: agent name "payload"
    if line.startswith("agent "):
        import re
        m = re.match(r"agent\s+(\w+)\s*\[(.+)\]", line)
        if m:
            agent = m.group(1)
            payload = m.group(2).strip()
            # only strip outer quotes when payload is a single string (no key/value colons);
            # don't remove quotes that belong to JSON-like payloads
            if ((payload.startswith('"') and payload.endswith('"')) or (payload.startswith("'") and payload.endswith("'"))) and (':' not in payload):
                payload = _strip_quotes(payload)
            return msast.AgentCall(agent, payload)
    # assignment with '='
    if "=" in line:
        name, expr = line.split("=", 1)
        name = name.strip()
        val = _ExprParser(expr.strip()).parse_expr()
        return msast.Assign(name, val)
    # function call
    if line.endswith(")") and "(" in line:
        name, rest = line.split("(", 1)
        name = name.strip()
        args_text = rest[:-1].strip()
        args = []
        if args_text:
            for a in args_text.split(","):
                tok = a.strip()
                args.append(_ExprParser(tok).parse_expr())
        return msast.FunctionCall(name, args)
    return msast.NameExpr(line)


def _parse_fallback(text: str) -> msast.Program:
    # Support a small, indentation-aware fallback: join a header line ending with
    # ':' with its immediately following indented body lines so single-line
    # parsing routines can handle simple multi-line blocks.
    raw_lines = text.splitlines()
    processed_lines: List[str] = []
    i = 0
    while i < len(raw_lines):
        ln = raw_lines[i]
        if not ln.strip():
            i += 1
            continue
        # join following indented lines to the header (simple heuristic)
        if ln.rstrip().endswith(':'):
            j = i + 1
            blocks: List[str] = []
            while j < len(raw_lines):
                nxt = raw_lines[j]
                indent_len = len(nxt) - len(nxt.lstrip(' \t'))
                if indent_len > 0 and nxt.strip():
                    blocks.append(nxt.lstrip())
                    j += 1
                    continue
                break
            if blocks:
                combined = ln.strip() + ' ' + ' '.join(blocks)
                processed_lines.append(combined)
                i = j
                continue
        processed_lines.append(ln.strip())
        i += 1

    stmts: List[msast.Node] = []
    for ln in processed_lines:
        node = _parse_line(ln)
        if node is None:
            continue
        stmts.append(node)
    return msast.Program(stmts)


def parse(source: str) -> msast.Program:
    """Parse Meta Script source into an AST Program (subset).

    Uses Lark if available; otherwise uses the enhanced fallback parser so the
    repository remains usable without external packages. The fallback supports
    single-line compound statements and simple expressions used in examples
    and tests.
    """
    if _has_lark:
        return _parse_with_lark(source)
    return _parse_fallback(source)

