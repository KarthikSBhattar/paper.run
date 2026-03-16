from __future__ import annotations

from .ast import (
    AssignStmt,
    BinaryExpr,
    BinaryOp,
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
    UnaryOp,
    WhileStmt,
)
from .errors import PaperError
from .lexer import Token, TokenKind


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.cursor = 0

    def parse_program(self) -> Program:
        functions: list[Function] = []
        top_level = []

        self._skip_newlines()
        while not self._check(TokenKind.EOF):
            if self._check(TokenKind.DEF):
                functions.append(self._parse_function())
            else:
                top_level.append(self._parse_stmt())
            self._skip_newlines()

        return Program(functions=functions, top_level=top_level)

    def _parse_function(self) -> Function:
        self._expect(TokenKind.DEF, "expected `def`")
        name = self._expect_identifier("expected a function name after `def`")
        self._expect(TokenKind.LEFT_PAREN, "expected `(` after function name")
        params: list[str] = []
        if not self._check(TokenKind.RIGHT_PAREN):
            while True:
                params.append(self._expect_identifier("expected a parameter name"))
                if not self._match(TokenKind.COMMA):
                    break
        self._expect(TokenKind.RIGHT_PAREN, "expected `)` after function name")
        self._expect(TokenKind.COLON, "expected `:` after function signature")
        self._expect(TokenKind.NEWLINE, "expected a newline after function signature")
        self._expect(TokenKind.INDENT, "expected an indented function body")
        return Function(name=name, params=params, body=self._parse_block())

    def _parse_stmt(self):
        if self._match(TokenKind.IF):
            condition = self._parse_expr()
            self._expect(TokenKind.COLON, "expected `:` after if condition")
            self._expect(TokenKind.NEWLINE, "expected a newline after if condition")
            self._expect(TokenKind.INDENT, "expected an indented if body")
            then_body = self._parse_block()
            else_body = []
            if self._match(TokenKind.ELSE):
                self._expect(TokenKind.COLON, "expected `:` after `else`")
                self._expect(TokenKind.NEWLINE, "expected a newline after `else:`")
                self._expect(TokenKind.INDENT, "expected an indented else body")
                else_body = self._parse_block()
            return IfStmt(condition=condition, then_body=then_body, else_body=else_body)

        if self._match(TokenKind.WHILE):
            condition = self._parse_expr()
            self._expect(TokenKind.COLON, "expected `:` after while condition")
            self._expect(TokenKind.NEWLINE, "expected a newline after while condition")
            self._expect(TokenKind.INDENT, "expected an indented while body")
            return WhileStmt(condition=condition, body=self._parse_block())

        if self._match(TokenKind.RETURN):
            expr = self._parse_expr()
            self._expect(TokenKind.NEWLINE, "expected a newline after return")
            return ReturnStmt(expr=expr)

        if self._is_assignment_start():
            name = self._expect_identifier("expected an assignment target")
            self._expect(TokenKind.EQUAL, "expected `=` in assignment")
            expr = self._parse_expr()
            self._expect(TokenKind.NEWLINE, "expected a newline after assignment")
            return AssignStmt(name=name, expr=expr)

        expr = self._parse_expr()
        self._expect(TokenKind.NEWLINE, "expected a newline after expression")
        return ExprStmt(expr=expr)

    def _parse_expr(self) -> Expr:
        return self._parse_or()

    def _parse_or(self) -> Expr:
        expr = self._parse_and()
        while self._match(TokenKind.OR):
            expr = BinaryExpr(left=expr, op=BinaryOp.OR, right=self._parse_and())
        return expr

    def _parse_and(self) -> Expr:
        expr = self._parse_not()
        while self._match(TokenKind.AND):
            expr = BinaryExpr(left=expr, op=BinaryOp.AND, right=self._parse_not())
        return expr

    def _parse_not(self) -> Expr:
        if self._match(TokenKind.NOT):
            return UnaryExpr(op=UnaryOp.NOT, expr=self._parse_not())
        return self._parse_comparison()

    def _parse_comparison(self) -> Expr:
        expr = self._parse_additive()
        while True:
            if self._match(TokenKind.EQUAL_EQUAL):
                expr = BinaryExpr(left=expr, op=BinaryOp.EQ, right=self._parse_additive())
            elif self._match(TokenKind.BANG_EQUAL):
                expr = BinaryExpr(left=expr, op=BinaryOp.NE, right=self._parse_additive())
            elif self._match(TokenKind.LESS_EQUAL):
                expr = BinaryExpr(left=expr, op=BinaryOp.LE, right=self._parse_additive())
            elif self._match(TokenKind.LESS):
                expr = BinaryExpr(left=expr, op=BinaryOp.LT, right=self._parse_additive())
            elif self._match(TokenKind.GREATER_EQUAL):
                expr = BinaryExpr(left=expr, op=BinaryOp.GE, right=self._parse_additive())
            elif self._match(TokenKind.GREATER):
                expr = BinaryExpr(left=expr, op=BinaryOp.GT, right=self._parse_additive())
            else:
                break
        return expr

    def _parse_additive(self) -> Expr:
        expr = self._parse_multiplicative()
        while True:
            if self._match(TokenKind.PLUS):
                expr = BinaryExpr(left=expr, op=BinaryOp.ADD, right=self._parse_multiplicative())
            elif self._match(TokenKind.MINUS):
                expr = BinaryExpr(left=expr, op=BinaryOp.SUB, right=self._parse_multiplicative())
            else:
                break
        return expr

    def _parse_multiplicative(self) -> Expr:
        expr = self._parse_unary()
        while True:
            if self._match(TokenKind.STAR):
                expr = BinaryExpr(left=expr, op=BinaryOp.MUL, right=self._parse_unary())
            elif self._match(TokenKind.SLASH):
                expr = BinaryExpr(left=expr, op=BinaryOp.DIV, right=self._parse_unary())
            else:
                break
        return expr

    def _parse_unary(self) -> Expr:
        if self._match(TokenKind.PLUS):
            return UnaryExpr(op=UnaryOp.PLUS, expr=self._parse_unary())
        if self._match(TokenKind.MINUS):
            return UnaryExpr(op=UnaryOp.MINUS, expr=self._parse_unary())
        return self._parse_primary()

    def _parse_primary(self) -> Expr:
        if self._match(TokenKind.LEFT_PAREN):
            expr = self._parse_expr()
            self._expect(TokenKind.RIGHT_PAREN, "expected `)` to close expression")
            return expr

        number = self._match_number()
        if number is not None:
            return NumberExpr(number)

        string = self._match_string()
        if string is not None:
            return StringExpr(string)

        if self._match(TokenKind.TRUE):
            return BooleanExpr(True)
        if self._match(TokenKind.FALSE):
            return BooleanExpr(False)
        if self._match(TokenKind.NONE):
            return NoneExpr()

        name = self._match_identifier()
        if name is not None:
            if self._match(TokenKind.LEFT_PAREN):
                args: list[Expr] = []
                if not self._check(TokenKind.RIGHT_PAREN):
                    while True:
                        args.append(self._parse_expr())
                        if not self._match(TokenKind.COMMA):
                            break
                self._expect(TokenKind.RIGHT_PAREN, "expected `)` after arguments")
                return CallExpr(callee=name, args=args)
            return IdentifierExpr(name)

        raise self._error_here(
            "expected a number, string, identifier, call expression, or parenthesized expression"
        )

    def _parse_block(self) -> list:
        body = []
        self._skip_newlines()
        while not self._check(TokenKind.DEDENT) and not self._check(TokenKind.EOF):
            body.append(self._parse_stmt())
            self._skip_newlines()
        self._expect(TokenKind.DEDENT, "expected the block to be dedented")
        if not body:
            raise self._error_here("block cannot be empty")
        return body

    def _skip_newlines(self) -> None:
        while self._match(TokenKind.NEWLINE):
            pass

    def _is_assignment_start(self) -> bool:
        current = self.tokens[self.cursor] if self.cursor < len(self.tokens) else None
        nxt = self.tokens[self.cursor + 1] if self.cursor + 1 < len(self.tokens) else None
        return bool(
            current
            and nxt
            and current.kind is TokenKind.IDENTIFIER
            and nxt.kind is TokenKind.EQUAL
        )

    def _check(self, expected: TokenKind) -> bool:
        return self.cursor < len(self.tokens) and self.tokens[self.cursor].kind is expected

    def _match(self, expected: TokenKind) -> bool:
        if self._check(expected):
            self.cursor += 1
            return True
        return False

    def _match_number(self) -> float | None:
        if self._check(TokenKind.NUMBER):
            token = self.tokens[self.cursor]
            self.cursor += 1
            return float(token.value)
        return None

    def _match_string(self) -> str | None:
        if self._check(TokenKind.STRING):
            token = self.tokens[self.cursor]
            self.cursor += 1
            return str(token.value)
        return None

    def _match_identifier(self) -> str | None:
        if self._check(TokenKind.IDENTIFIER):
            token = self.tokens[self.cursor]
            self.cursor += 1
            return str(token.value)
        return None

    def _expect_identifier(self, message: str) -> str:
        value = self._match_identifier()
        if value is None:
            raise self._error_here(message)
        return value

    def _expect(self, expected: TokenKind, message: str) -> None:
        if not self._match(expected):
            raise self._error_here(message)

    def _error_here(self, message: str) -> PaperError:
        token = self.tokens[self.cursor] if self.cursor < len(self.tokens) else self.tokens[-1]
        return PaperError(f"line {token.line}, column {token.column}: {message}")
