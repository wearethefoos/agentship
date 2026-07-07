#!/usr/bin/env python3
"""PostToolUse hook (Write|Edit): after a markdown file under ./docs changes,
link-check the whole docs tree. Broken links are fed back to Claude via a
"block" decision so they get fixed immediately.

Checks the whole tree, not only the edited file, so links elsewhere that the
edit just broke (renames, deleted headings) are caught too. External http(s)
links are skipped here for speed — the audit-docs skill covers those.
"""

import json
import subprocess
import sys
from pathlib import Path

MAX_REASON = 3000

def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    file_path = (data.get("tool_input") or {}).get("file_path", "")
    cwd = Path(data.get("cwd") or ".")
    docs = (cwd / "docs").resolve()
    if not file_path or not docs.is_dir():
        return
    try:
        target = Path(file_path).resolve()
        target.relative_to(docs)
    except ValueError:
        return  # not under ./docs
    if target.suffix.lower() not in (".md", ".markdown"):
        return

    checker = Path(__file__).resolve().parent.parent / "bin" / "check_links"
    try:
        result = subprocess.run(
            [sys.executable, str(checker), str(docs), "--root", str(cwd)],
            capture_output=True, text=True, timeout=20, cwd=str(cwd),
        )
    except (subprocess.TimeoutExpired, OSError):
        return
    if result.returncode == 0:
        return

    report = result.stdout.strip()[:MAX_REASON]
    print(json.dumps({
        "decision": "block",
        "reason": ("Docs link check failed after this edit. Fix these (update the "
                   "links, or the files/headings they point to):\n" + report),
    }))


if __name__ == "__main__":
    main()
