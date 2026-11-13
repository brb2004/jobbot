"""Warn (never fail) about files over 100 lines and functions over 20, the house rule of thumb.

python tools/check_size.py app          # GitHub Actions shows each line as a warning annotation
"""

import ast
import sys
from pathlib import Path

MAX_FILE, MAX_FUNC = 100, 20


def report(root: str) -> list[str]:
    out = []
    for path in sorted(Path(root).rglob("*.py")):
        src = path.read_text()
        if (n := src.count("\n")) > MAX_FILE:
            out.append(f"::warning file={path}::{n} lines (rule of thumb: {MAX_FILE})")
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                length = node.end_lineno - node.lineno + 1
                if length > MAX_FUNC:
                    out.append(f"::warning file={path},line={node.lineno}::{node.name} is {length} lines")
    return out


if __name__ == "__main__":
    lines = report(sys.argv[1] if len(sys.argv) > 1 else "app")
    print("\n".join(lines) or "all files and functions within the size rules")
