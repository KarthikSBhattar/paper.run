from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


@dataclass(frozen=True)
class Program:
    functions: list["Function"]
    top_level: list["Stmt"]


@dataclass(frozen=True)
class Function:
    name: str
    params: list[str]
    body: list["Stmt"]


class UnaryOp(Enum):
    PLUS = auto()
    MINUS = auto()
    NOT = auto()


class BinaryOp(Enum):
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    EQ = auto()
    NE = auto()
    LT = auto()
    LE = auto()
    GT = auto()
    GE = auto()
    AND = auto()
    OR = auto()


class Expr:
    pass


@dataclass(frozen=True)
class BooleanExpr(Expr):
    value: bool


@dataclass(frozen=True)
class NoneExpr(Expr):
    pass


@dataclass(frozen=True)
class NumberExpr(Expr):
    value: float


@dataclass(frozen=True)
class StringExpr(Expr):
    value: str


@dataclass(frozen=True)
class IdentifierExpr(Expr):
    name: str


@dataclass(frozen=True)
class CallExpr(Expr):
    callee: str
    args: list[Expr]


@dataclass(frozen=True)
class UnaryExpr(Expr):
    op: UnaryOp
    expr: Expr


@dataclass(frozen=True)
class BinaryExpr(Expr):
    left: Expr
    op: BinaryOp
    right: Expr


class Stmt:
    pass


@dataclass(frozen=True)
class AssignStmt(Stmt):
    name: str
    expr: Expr


@dataclass(frozen=True)
class IfStmt(Stmt):
    condition: Expr
    then_body: list[Stmt]
    else_body: list[Stmt]


@dataclass(frozen=True)
class ReturnStmt(Stmt):
    expr: Expr


@dataclass(frozen=True)
class ExprStmt(Stmt):
    expr: Expr


@dataclass(frozen=True)
class WhileStmt(Stmt):
    condition: Expr
    body: list[Stmt]
