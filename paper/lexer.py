from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from .errors import PaperError


class TokenKind(Enum):
    AND = auto()
    DEF = auto()
    ELSE = auto()
    FALSE = auto()
    IF = auto()
    NONE = auto()
    NOT = auto()
    OR = auto()
    RETURN = auto()
    TRUE = auto()
    WHILE = auto()
    IDENTIFIER = auto()
    NUMBER = auto()
    STRING = auto()
    LEFT_PAREN = auto()
    RIGHT_PAREN = auto()
    COLON = auto()
    COMMA = auto()
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    EQUAL = auto()
    EQUAL_EQUAL = auto()
    BANG_EQUAL = auto()
    LESS = auto()
    LESS_EQUAL = auto()
    GREATER = auto()
    GREATER_EQUAL = auto()
    NEWLINE = auto()
    INDENT = auto()
    DEDENT = auto()
    EOF = auto()


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    line: int
    column: int
    value: str | float | None = None


KEYWORDS = {
    "and": TokenKind.AND,
    "def": TokenKind.DEF,
    "else": TokenKind.ELSE,
    "False": TokenKind.FALSE,
    "if": TokenKind.IF,
    "None": TokenKind.NONE,
    "not": TokenKind.NOT,
    "or": TokenKind.OR,
    "return": TokenKind.RETURN,
    "True": TokenKind.TRUE,
    "while": TokenKind.WHILE,
}


class Lexer:
    def __init__(self, source: str) -> None:
        self.source = source

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        indent_stack = [0]
        lines = self.source.splitlines()

        for line_index, raw_line in enumerate(lines, start=1):
            indent = len(raw_line) - len(raw_line.lstrip(" "))
            if indent % 4 != 0:
                raise PaperError(
                    f"line {line_index}: indentation must use multiples of four spaces"
                )

            trimmed = raw_line.strip()
            if not trimmed:
                continue

            current_indent = indent_stack[-1]
            if indent > current_indent:
                if indent != current_indent + 4:
                    raise PaperError(
                        f"line {line_index}: indentation can only increase by one level"
                    )
                indent_stack.append(indent)
                tokens.append(Token(TokenKind.INDENT, line_index, 1))
            elif indent < current_indent:
                while indent < indent_stack[-1]:
                    indent_stack.pop()
                    tokens.append(Token(TokenKind.DEDENT, line_index, 1))
                if indent != indent_stack[-1]:
                    raise PaperError(f"line {line_index}: inconsistent indentation")

            tokens.extend(self._tokenize_line(trimmed, line_index, indent + 1))
            tokens.append(Token(TokenKind.NEWLINE, line_index, len(raw_line) + 1))

        eof_line = len(lines) + 1
        while len(indent_stack) > 1:
            indent_stack.pop()
            tokens.append(Token(TokenKind.DEDENT, eof_line, 1))
        tokens.append(Token(TokenKind.EOF, eof_line, 1))
        return tokens

    def _tokenize_line(self, line: str, line_number: int, column_offset: int) -> list[Token]:
        tokens: list[Token] = []
        index = 0

        while index < len(line):
            ch = line[index]
            column = column_offset + index

            if ch in {" ", "\t"}:
                index += 1
                continue
            if ch == "(":
                tokens.append(Token(TokenKind.LEFT_PAREN, line_number, column))
                index += 1
                continue
            if ch == ")":
                tokens.append(Token(TokenKind.RIGHT_PAREN, line_number, column))
                index += 1
                continue
            if ch == ":":
                tokens.append(Token(TokenKind.COLON, line_number, column))
                index += 1
                continue
            if ch == ",":
                tokens.append(Token(TokenKind.COMMA, line_number, column))
                index += 1
                continue
            if ch == "+":
                tokens.append(Token(TokenKind.PLUS, line_number, column))
                index += 1
                continue
            if ch == "-":
                tokens.append(Token(TokenKind.MINUS, line_number, column))
                index += 1
                continue
            if ch == "*":
                tokens.append(Token(TokenKind.STAR, line_number, column))
                index += 1
                continue
            if ch == "/":
                tokens.append(Token(TokenKind.SLASH, line_number, column))
                index += 1
                continue
            if ch == "=":
                if index + 1 < len(line) and line[index + 1] == "=":
                    tokens.append(Token(TokenKind.EQUAL_EQUAL, line_number, column))
                    index += 2
                else:
                    tokens.append(Token(TokenKind.EQUAL, line_number, column))
                    index += 1
                continue
            if ch == "!":
                if index + 1 < len(line) and line[index + 1] == "=":
                    tokens.append(Token(TokenKind.BANG_EQUAL, line_number, column))
                    index += 2
                    continue
                raise PaperError(
                    f"line {line_number}, column {column}: unexpected character `{ch}`"
                )
            if ch == "<":
                if index + 1 < len(line) and line[index + 1] == "=":
                    tokens.append(Token(TokenKind.LESS_EQUAL, line_number, column))
                    index += 2
                else:
                    tokens.append(Token(TokenKind.LESS, line_number, column))
                    index += 1
                continue
            if ch == ">":
                if index + 1 < len(line) and line[index + 1] == "=":
                    tokens.append(Token(TokenKind.GREATER_EQUAL, line_number, column))
                    index += 2
                else:
                    tokens.append(Token(TokenKind.GREATER, line_number, column))
                    index += 1
                continue
            if ch.isdigit():
                start = index
                seen_dot = False
                while index < len(line):
                    current = line[index]
                    if current.isdigit():
                        index += 1
                    elif current == "." and not seen_dot:
                        seen_dot = True
                        index += 1
                    else:
                        break
                literal = line[start:index]
                try:
                    number = float(literal)
                except ValueError as err:
                    raise PaperError(
                        f"line {line_number}, column {column}: invalid number `{literal}`"
                    ) from err
                tokens.append(Token(TokenKind.NUMBER, line_number, column, number))
                continue
            if ch == '"':
                index += 1
                chars: list[str] = []
                terminated = False
                while index < len(line):
                    current = line[index]
                    if current == '"':
                        terminated = True
                        index += 1
                        break
                    if current == "\\":
                        index += 1
                        if index >= len(line):
                            raise PaperError(
                                f"line {line_number}, column {column}: unterminated string escape"
                            )
                        escaped = line[index]
                        if escaped == '"':
                            chars.append('"')
                        elif escaped == "\\":
                            chars.append("\\")
                        elif escaped == "n":
                            chars.append("\n")
                        elif escaped == "t":
                            chars.append("\t")
                        else:
                            raise PaperError(
                                f"line {line_number}, column {column_offset + index}: unsupported escape `\\{escaped}`"
                            )
                    else:
                        chars.append(current)
                    index += 1
                if not terminated:
                    raise PaperError(
                        f"line {line_number}, column {column}: unterminated string literal"
                    )
                tokens.append(Token(TokenKind.STRING, line_number, column, "".join(chars)))
                continue
            if ch.isalpha() or ch == "_":
                start = index
                index += 1
                while index < len(line) and (line[index].isalnum() or line[index] == "_"):
                    index += 1
                ident = line[start:index]
                kind = KEYWORDS.get(ident, TokenKind.IDENTIFIER)
                value = ident if kind is TokenKind.IDENTIFIER else None
                tokens.append(Token(kind, line_number, column, value))
                continue

            raise PaperError(
                f"line {line_number}, column {column}: unexpected character `{ch}`"
            )

        return tokens
