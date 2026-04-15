#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Set


INPUT_RE = re.compile(
    r"""\\input\s*(?:\{([^}]+)\}|([^\s%]+))"""
)


def strip_comments(line: str) -> str:
    """
    Remove LaTeX comments from a line, respecting escaped percent signs.
    """
    result = []
    escaped = False
    for ch in line:
        if ch == "%" and not escaped:
            break
        result.append(ch)
        escaped = (ch == "\\" and not escaped)
        if ch != "\\":
            escaped = False
    return "".join(result)


def normalise_input_name(name: str, british: bool) -> str:
    """
    Add .tex if no suffix is present.
    Translate \sourcedir to US or BE based on british flag
    """
    name = re.sub(r"\\sourcedir\b","BE" if british else "US", name)
    p = Path(name)
    if p.suffix:
        return name
    return name + ".tex"


def is_in_current_directory(path_str: str) -> bool:
    """
    Return True if the path is just a filename in the current directory,
    not a path into another directory.
    """
    p = Path(path_str)
    return len(p.parts) == 1


def find_inputs(tex_file: Path, british: bool) -> List[str]:
    """
    Find all uncommented \\input occurrences in a TeX file.
    """
    inputs: List[str] = []
    try:
        text = tex_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"Warning: file not found: {tex_file}", file=sys.stderr)
        return inputs

    for line in text.splitlines():
        uncommented = strip_comments(line)
        for m in INPUT_RE.finditer(uncommented):
            name = m.group(1) or m.group(2)
            if name:
                inputs.append(normalise_input_name(name.strip(), british))
    return inputs


def walk_inputs(start_file: Path, british: bool, parent: Path) -> List[str]:
    """
    Recursively collect input files, following only files in the current directory.
    Files outside the current directory are listed but not followed.
    """
    seen: Set[Path] = set()
    listed: List[str] = []

    def visit(tex_file: Path, parent: Path) -> None:
        resolved = tex_file.resolve()
        if resolved in seen:
            return
        seen.add(resolved)

        for inp in find_inputs(tex_file, british):
            listed.append(parent / inp)
            if is_in_current_directory(inp):
                child = tex_file.parent / inp
                if child.exists():
                    visit(child, parent)

    visit(start_file, parent)
    return listed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List files included by LaTeX \\input commands."
    )
    parser.add_argument("texfile", help="Starting .tex file")
    parser.add_argument("--british", "-b", action="store_true")
    args = parser.parse_args()

    start_file = Path(args.texfile)
    if not start_file.exists():
        print(f"Error: file not found: {start_file}", file=sys.stderr)
        sys.exit(1)

    parent = start_file.parent
    for name in walk_inputs(start_file, args.british, parent):
        print(name, end=" ")
    print(start_file)

if __name__ == "__main__":
    main()
