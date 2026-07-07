#!/usr/bin/env python3
"""UserPromptSubmit hook: inject memories relevant to the prompt as context.

Uses full-text search only — it runs on every prompt and must stay fast;
semantic (vector) search is available on demand via the memory CLI/skills.
Prints nothing when there is nothing relevant.
"""

import json
import subprocess
import sys
from pathlib import Path

MIN_PROMPT_LEN = 12
LIMIT = 4

def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    prompt = (data.get("prompt") or "").strip()
    if len(prompt) < MIN_PROMPT_LEN or prompt.startswith("/"):
        return

    cli = Path(__file__).resolve().parent.parent / "bin" / "memory"
    try:
        result = subprocess.run(
            [sys.executable, str(cli), "search", prompt,
             "--mode", "fts", "-n", str(LIMIT), "--format", "context"],
            capture_output=True, text=True, timeout=8,
        )
    except (subprocess.TimeoutExpired, OSError):
        return
    hits = result.stdout.strip()
    if result.returncode != 0 or not hits:
        return

    print("Recalled memories (agentix memory, keyword match — ignore any that are "
          "irrelevant to the request):")
    print(hits)


if __name__ == "__main__":
    main()
