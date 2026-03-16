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
