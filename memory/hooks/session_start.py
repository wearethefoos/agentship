#!/usr/bin/env python3
"""SessionStart hook: announce the memory tool, its CLI path, and recent memories."""

import subprocess
import sys
from pathlib import Path

CLI = Path(__file__).resolve().parent.parent / "bin" / "memory"


def run(*args):
    try:
        result = subprocess.run(
            [sys.executable, str(CLI), *args],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, OSError):
        return ""


def main():
    stats = run("stats")
    if not stats:
        return
    recent = run("list", "-n", "3", "--format", "context")
    print(f"agentix memory tool active. CLI: {CLI}")
    print("Save durable facts/preferences with: memory add \"...\" --type preference --tags a,b")
    print("Recall with: memory search \"...\" (hybrid FTS+vector). Relevant memories are also "
          "auto-injected on each prompt via keyword match.")
    print(stats.splitlines()[1] if len(stats.splitlines()) > 1 else stats)
    if recent:
        print("Most recent memories:")
        print(recent)


if __name__ == "__main__":
    main()
