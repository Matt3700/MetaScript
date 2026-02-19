from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Any, Optional


class Node:
    pass


@dataclass
class Program(Node):
    statements: List[Node] = field(default_factory=list)


# Statements / control flow
@dataclass
class Say(Node):
    text: Any  # expression


@dataclass
class Print(Node):
    text: Any


@dataclass
class Assign(Node):
    name: str
    value: Any


@dataclass
class If(Node):
    cond: Any
    body: List[Node]
    orelse: Optional[List[Node]] = None


@dataclass
class While(Node):
    cond: Any
    body: List[Node]


@dataclass
class ForLoop(Node):
    var: str
    end: Any
    body: List[Node]


@dataclass
class FunctionDef(Node):
    name: str
    params: List[str]
    body: List[Node]
    is_async: bool = False


@dataclass
class Return(Node):
    value: Any


@dataclass
class DoBlock(Node):
    body: List[Node]


@dataclass
class AgentCall(Node):
    agent: str
    payload: str  # raw JSON-like string for now


@dataclass
class MatchCase(Node):
    pattern: Any
    body: List[Node]


@dataclass
class Match(Node):
    subject: Any
    cases: List[MatchCase]


# Pattern nodes
@dataclass
class WildcardPattern(Node):
    pass


@dataclass
class NamePattern(Node):
    name: str


@dataclass
class LiteralPattern(Node):
    value: Any


@dataclass
class ListPattern(Node):
    elements: List[Any]


# Expressions
@dataclass
class FunctionCall(Node):
    name: str
    args: List[Any]


@dataclass
class BinaryOp(Node):
    op: str
    left: Any
    right: Any


@dataclass
class UnaryOp(Node):
    op: str
    operand: Any


@dataclass
class Await(Node):
    expr: Any


@dataclass
class ListLiteral(Node):
    elements: List[Any]


@dataclass
class LiteralString(Node):
    value: str


@dataclass
class LiteralInt(Node):
    value: int


@dataclass
class NameExpr(Node):
    id: str


@dataclass
class MacroDef(Node):
    name: str
    params: List[str]
    body: List[Node]


@dataclass
class MacroCall(Node):
    name: str
    args: List[Any]


# helpers
def node_to_dict(n: Node) -> Any:
    if isinstance(n, Program):
        return {"Program": [node_to_dict(s) for s in n.statements]}
    if isinstance(n, Say):
        return {"Say": node_to_dict(n.text)}
    if isinstance(n, Print):
        return {"Print": node_to_dict(n.text)}
    if isinstance(n, Assign):
        return {"Assign": {"name": n.name, "value": node_to_dict(n.value)}}
    if isinstance(n, If):
        return {"If": {"cond": node_to_dict(n.cond), "body": [node_to_dict(s) for s in n.body], "orelse": ([node_to_dict(s) for s in n.orelse] if n.orelse else None)}}
    if isinstance(n, While):
        return {"While": {"cond": node_to_dict(n.cond), "body": [node_to_dict(s) for s in n.body]}}
    if isinstance(n, ForLoop):
        return {"ForLoop": {"var": n.var, "end": node_to_dict(n.end), "body": [node_to_dict(s) for s in n.body]}}
    if isinstance(n, FunctionDef):
        return {"FunctionDef": {"name": n.name, "params": n.params, "is_async": n.is_async, "body": [node_to_dict(s) for s in n.body]}}
    if isinstance(n, Return):
        return {"Return": node_to_dict(n.value)}
    if isinstance(n, DoBlock):
        return {"DoBlock": [node_to_dict(s) for s in n.body]}
    if isinstance(n, AgentCall):
        return {"AgentCall": {"agent": n.agent, "payload": n.payload}}
    if isinstance(n, Match):
        return {"Match": {"subject": node_to_dict(n.subject), "cases": [{"pattern": node_to_dict(c.pattern), "body": [node_to_dict(s) for s in c.body]} for c in n.cases]}}
    if isinstance(n, MatchCase):
        return {"MatchCase": {"pattern": node_to_dict(n.pattern), "body": [node_to_dict(s) for s in n.body]}}
    if isinstance(n, WildcardPattern):
        return {"Pattern": "_"}
    if isinstance(n, NamePattern):
        return {"Pattern": {"name": n.name}}
    if isinstance(n, LiteralPattern):
        return {"Pattern": {"lit": node_to_dict(n.value)}}
    if isinstance(n, ListPattern):
        return {"Pattern": [node_to_dict(e) for e in n.elements]}
    if isinstance(n, FunctionCall):
        return {"FunctionCall": {"name": n.name, "args": [node_to_dict(a) for a in n.args]}}
    if isinstance(n, BinaryOp):
        return {"BinaryOp": {"op": n.op, "left": node_to_dict(n.left), "right": node_to_dict(n.right)}}
    if isinstance(n, UnaryOp):
        return {"UnaryOp": {"op": n.op, "operand": node_to_dict(n.operand)}}
    if isinstance(n, Await):
        return {"Await": node_to_dict(n.expr)}
    if isinstance(n, ListLiteral):
        return {"List": [node_to_dict(e) for e in n.elements]}
    if isinstance(n, LiteralString):
        return {"String": n.value}
    if isinstance(n, LiteralInt):
        return {"Int": n.value}
    if isinstance(n, NameExpr):
        return {"Name": n.id}
    if isinstance(n, MacroDef):
        return {"MacroDef": {"name": n.name, "params": n.params, "body": [node_to_dict(s) for s in n.body]}}
    if isinstance(n, MacroCall):
        return {"MacroCall": {"name": n.name, "args": [node_to_dict(a) for a in n.args]}}
    return str(n)

