from __future__ import annotations

from .ast import (
    AssignStmt,
    BinaryExpr,
    BooleanExpr,
    CallExpr,
    Expr,
    ExprStmt,
    Function,
    IdentifierExpr,
    IfStmt,
    NoneExpr,
    NumberExpr,
    Program,
    ReturnStmt,
    StringExpr,
    UnaryExpr,
    WhileStmt,
)
from .errors import PaperError


def validate_program(program: Program) -> None:
    function_names: set[str] = set()
    arities: dict[str, int] = {}
    for function in program.functions:
        if function.name in function_names:
            raise PaperError(f"duplicate function definition `{function.name}`")
        function_names.add(function.name)
        arities[function.name] = len(function.params)

    for function in program.functions:
        locals_scope = function_scope(function)
        for stmt in function.body:
            validate_stmt(stmt, function_names, arities, locals_scope, allow_return=True)

    top_level_scope = block_scope(program.top_level)
    for stmt in program.top_level:
        validate_stmt(stmt, function_names, arities, top_level_scope, allow_return=False)


def validate_stmt(
    stmt,
    function_names: set[str],
    arities: dict[str, int],
    locals_scope: set[str],
    *,
    allow_return: bool,
) -> None:
    if isinstance(stmt, AssignStmt | ExprStmt):
        validate_expr(stmt.expr, function_names, arities, locals_scope)
        return

    if isinstance(stmt, ReturnStmt):
        if not allow_return:
            raise PaperError("top-level return is not allowed; return only inside functions")
        validate_expr(stmt.expr, function_names, arities, locals_scope)
        return

    if isinstance(stmt, IfStmt):
        validate_expr(stmt.condition, function_names, arities, locals_scope)
        for child in stmt.then_body:
            validate_stmt(child, function_names, arities, locals_scope, allow_return=allow_return)
        for child in stmt.else_body:
            validate_stmt(child, function_names, arities, locals_scope, allow_return=allow_return)
        return

    if isinstance(stmt, WhileStmt):
        validate_expr(stmt.condition, function_names, arities, locals_scope)
        for child in stmt.body:
            validate_stmt(child, function_names, arities, locals_scope, allow_return=allow_return)
        return

    raise AssertionError(f"unsupported statement: {type(stmt).__name__}")


def validate_expr(
    expr: Expr, function_names: set[str], arities: dict[str, int], locals_scope: set[str]
) -> None:
    if isinstance(expr, (BooleanExpr, NoneExpr, NumberExpr, StringExpr)):
        return
    if isinstance(expr, IdentifierExpr):
        if expr.name not in locals_scope:
            raise PaperError(f"use of undefined variable `{expr.name}`")
        return
    if isinstance(expr, UnaryExpr):
        validate_expr(expr.expr, function_names, arities, locals_scope)
        return
    if isinstance(expr, BinaryExpr):
        validate_expr(expr.left, function_names, arities, locals_scope)
        validate_expr(expr.right, function_names, arities, locals_scope)
        return
    if isinstance(expr, CallExpr):
        if expr.callee == "print":
            if len(expr.args) != 1:
                raise PaperError(
                    f"builtin `print` expects 1 argument, got {len(expr.args)}"
                )
            validate_expr(expr.args[0], function_names, arities, locals_scope)
            return
        if expr.callee not in function_names:
            raise PaperError(f"call to undefined function `{expr.callee}`")
        expected_arity = arities[expr.callee]
        if len(expr.args) != expected_arity:
            raise PaperError(
                f"function `{expr.callee}` expects {expected_arity} argument(s), got {len(expr.args)}"
            )
        for arg in expr.args:
            validate_expr(arg, function_names, arities, locals_scope)
        return

    raise AssertionError(f"unsupported expression: {type(expr).__name__}")


def function_scope(function: Function) -> set[str]:
    scope = set(function.params)
    scope.update(block_scope(function.body))
    return scope


def block_scope(statements: list) -> set[str]:
    scope: set[str] = set()
    for stmt in statements:
        if isinstance(stmt, AssignStmt):
            scope.add(stmt.name)
        elif isinstance(stmt, IfStmt):
            scope.update(block_scope(stmt.then_body))
            scope.update(block_scope(stmt.else_body))
        elif isinstance(stmt, WhileStmt):
            scope.update(block_scope(stmt.body))
    return scope
