from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .codegen import Codegen
from .errors import PaperError
from .lexer import Lexer
from .parser import Parser
from .semantic import validate_program


def main(argv: list[str] | None = None) -> int:
    try:
        return run(argv or sys.argv[1:])
    except PaperError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="paper")
    subparsers = parser.add_subparsers(dest="command", required=True)
    compile_parser = subparsers.add_parser("compile")
    compile_parser.add_argument("input")
    compile_parser.add_argument("-o", "--output")
    args = parser.parse_args(argv)

    if args.command != "compile":
        raise PaperError(f"unknown command `{args.command}`")

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else Path(input_path.stem)
    source = input_path.read_text()

    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse_program()
    validate_program(program)
    ir = Codegen(program).emit()

    ir_path = output_path.with_suffix(".ll")
    ir_path.write_text(ir)

    sdk_path = macos_sdk_path()
    status = subprocess.run(
        [
            "clang",
            "-Wno-override-module",
            "-isysroot",
            sdk_path,
            "-x",
            "ir",
            str(ir_path),
            "-o",
            str(output_path),
        ],
        check=False,
    )
    if status.returncode != 0:
        raise PaperError(f"clang failed while compiling {ir_path}")

    print(f"wrote {output_path}")
    print(f"llvm ir {ir_path}")
    return 0


def macos_sdk_path() -> str:
    result = subprocess.run(
        ["xcrun", "--show-sdk-path"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise PaperError("xcrun --show-sdk-path failed to locate a macOS SDK")
    path = result.stdout.strip()
    if not path:
        raise PaperError("xcrun returned an empty macOS SDK path")
    return path
