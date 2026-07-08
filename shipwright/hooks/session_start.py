#!/usr/bin/env python3
"""SessionStart hook: if the project has an active shipwright rewrite, announce
its status and the CLI path so a fresh session can resume where it left off.
Silent when there is no .shipwright/state.json anywhere up the tree."""

import json
import subprocess
import sys
from pathlib import Path

CLI = Path(__file__).resolve().parent.parent / "bin" / "shipwright"


def find_state(start: Path):
    for parent in [start, *start.parents]:
        if (parent / ".shipwright" / "state.json").is_file():
            return parent
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        data = {}
    cwd = Path(data.get("cwd") or Path.cwd())
    root = find_state(cwd)
    if root is None:
        return
    try:
        result = subprocess.run(
            [sys.executable, str(CLI), "status", "--format", "context"],
            capture_output=True, text=True, timeout=8, cwd=str(root),
        )
    except (subprocess.TimeoutExpired, OSError):
        return
    if result.returncode != 0 or not result.stdout.strip():
        return
    print(result.stdout.strip())
    print(f"CLI: {CLI}")
    print("Resume with /shipwright:status, or the phase named above.")


if __name__ == "__main__":
    main()
