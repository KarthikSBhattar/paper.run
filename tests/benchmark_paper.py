from __future__ import annotations

import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "bench_sum.py"


def compile_native(output_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "paper", "compile", str(EXAMPLE), "-o", str(output_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            "native compile failed\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def benchmark(command: list[str], runs: int) -> tuple[list[float], int]:
    timings: list[float] = []
    returncode = 0
    for _ in range(runs):
        start = time.perf_counter()
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        elapsed = time.perf_counter() - start
        timings.append(elapsed)
        returncode = result.returncode
        if result.returncode != 0:
            raise SystemExit(
                f"command failed: {' '.join(command)}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
    return timings, returncode


def format_stats(name: str, samples: list[float]) -> str:
    mean = statistics.mean(samples)
    median = statistics.median(samples)
    stdev = statistics.stdev(samples) if len(samples) > 1 else 0.0
    return (
        f"{name}: mean={mean:.6f}s median={median:.6f}s stdev={stdev:.6f}s "
        f"runs={len(samples)}"
    )


def main() -> int:
    runs = 5
    with tempfile.TemporaryDirectory(prefix="paper_bench_") as tmp:
        native_path = Path(tmp) / "bench_sum_native"
        compile_native(native_path)

        python_samples, _ = benchmark([sys.executable, str(EXAMPLE)], runs)
        native_samples, _ = benchmark([str(native_path)], runs)

    python_mean = statistics.mean(python_samples)
    native_mean = statistics.mean(native_samples)
    speedup = python_mean / native_mean if native_mean else float("inf")

    print(format_stats("cpython", python_samples))
    print(format_stats("paper-native", native_samples))
    print(f"speedup: {speedup:.2f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
