---
name: remember
description: Save a durable memory to the agentship memory store. Use when the user says "remember this", "save this for later", "note that I prefer...", or when the user states a lasting fact, preference, or project constraint worth keeping across sessions. Do NOT use for facts already in the repo (code, git history, CLAUDE.md) or things only relevant to the current conversation.
---

# Remember

Save a memory with the agentship memory CLI:

```bash
"${CLAUDE_PLUGIN_ROOT}/bin/memory" add "CONTENT" --type TYPE --tags tag1,tag2 --project PROJECT
```

If `${CLAUDE_PLUGIN_ROOT}` is not resolved in your context, the absolute CLI path
was printed by the SessionStart hook ("agentship memory tool active. CLI: ...").

## Steps

1. **Check for duplicates first**: run
   `memory search "key terms" --mode fts -n 5`.
   If an existing memory covers the same fact, update it instead:
   `memory edit ID --content "..."` — do not create a near-duplicate.
2. Write the content as one self-contained fact. Convert relative dates to
   absolute (e.g. "next week" → "week of 2026-07-13"). Include the *why* when
   the user gives feedback or a correction.
3. Pick a type:
   - `preference` — how the user likes things done
   - `fact` — durable fact about the user, their systems, or environment
   - `project` — goals, constraints, status of ongoing work (set `--project`)
   - `reference` — pointer to URL, ticket, dashboard
   - `note` — anything else
4. Add 1–4 lowercase tags for findability.
5. Confirm to the user what was saved, with its id.

## What not to save

- Anything derivable from the repo (code structure, git history, CLAUDE.md).
- Secrets, API keys, passwords.
- Session-only context ("the bug we're fixing right now").

If the embed step warns "stored without embedding", the memory is still saved
and full-text searchable; mention that vector search needs the embedding
provider (see `memory stats`) and that `memory embed` backfills later.
