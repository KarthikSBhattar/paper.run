from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


def compile_example(name: str) -> Path:
    output_dir = Path(tempfile.mkdtemp(prefix="paper_py_"))
    output_path = output_dir / name
    result = subprocess.run(
        [sys.executable, "-m", "paper", "compile", str(EXAMPLES / f"{name}.py"), "-o", str(output_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"compile failed for {name}:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
    return output_path


def run_binary(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class ExampleCompilationTests(unittest.TestCase):
    def test_print_sum(self) -> None:
        binary = compile_example("print_sum")
        result = run_binary(binary)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "15\n")

    def test_strings(self) -> None:
        binary = compile_example("strings")
        result = run_binary(binary)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "paper.run\nhello\nTrue\nFalse\nempty\n")

    def test_python_values(self) -> None:
        binary = compile_example("python_values")
        result = run_binary(binary)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "True\nFalse\nNone\nTrue\nNone\nNone\n")

    def test_add_script_exits_zero(self) -> None:
        binary = compile_example("add")
        result = run_binary(binary)
        self.assertEqual(result.returncode, 0)

    def test_if_else_script_exits_zero(self) -> None:
        binary = compile_example("if_else")
        result = run_binary(binary)
        self.assertEqual(result.returncode, 0)

    def test_while_sum_script_exits_zero(self) -> None:
        binary = compile_example("while_sum")
        result = run_binary(binary)
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
