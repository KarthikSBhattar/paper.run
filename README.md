# paper.run

![paper.run logo](./logo.png)

`paper.run` is an experimental Python-like language compiler written in Python that emits LLVM IR and produces native binaries with `clang`.

The long-term goal is to evolve it toward a self-hosting compiler while keeping the language shape close to Python.

## Current Status

`paper.run` currently supports:

- top-level execution
- function definitions and calls
- local variables
- arithmetic
- comparisons
- `if` / `else`
- `while`
- booleans
- `None`
- strings
- `print(...)`

It compiles source files to LLVM IR and links them into native executables.

## Requirements

- Python 3.11+
- `clang`
- macOS SDK tools available through `xcrun`

## Run

Compile and run an example:

```bash
python3 -m paper compile examples/strings.py -o strings_native
./strings_native
```

## Test

Run the test suite:

```bash
python3 -m unittest discover -s tests -v
```

## Benchmark

Run the local benchmark:

```bash
python3 tests/benchmark_paper.py
```

Latest local result on M2 Mac Mini for `examples/bench_sum.py`:

- `cpython`: mean `0.557663s`, median `0.556860s`
- `paper-native`: mean `0.075533s`, median `0.038656s`
- reported speedup: `7.38x`

## Project Layout

- `paper/` — compiler implementation
- `examples/` — sample input programs
- `tests/` — regression tests and benchmark harness

## Notes

This is a VERY experimental compiler. Many parts of Python are not implemented yet.
