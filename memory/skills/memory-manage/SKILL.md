---
name: memory-manage
description: Maintain the agentship memory store - list, edit, delete memories, view stats, backfill embeddings, or change the embedding provider. Use when the user says "forget that", "update that memory", "clean up your memories", "memory stats", or asks to configure memory embeddings.
---

# Memory management

CLI: `"${CLAUDE_PLUGIN_ROOT}/bin/memory"` (absolute path also printed by the
SessionStart hook). Storage lives in `~/.config/agentship/memory/`.

## Commands

```bash
memory list -n 20 [--type T] [--project P] [--tag T]
memory get ID
memory edit ID --content "..." [--type T] [--tags a,b] [--project P]
memory delete ID
memory stats                       # counts, embedded coverage, provider
memory embed                       # backfill embeddings for un-embedded memories
memory config                      # show config
memory config --set embedding.provider=openai --set embedding.model=text-embedding-3-small
```

## Guidance

- **Forget**: find the memory first (`memory search` / `memory list`), show the
  user which one(s) match, then `memory delete ID`. Deleting is irreversible —
  if multiple candidates match, confirm which before deleting.
- **Update**: prefer `memory edit` over delete+add; it keeps the id and
  re-embeds automatically when content changes.
- **Wrong/stale memories**: when a recalled memory contradicts current reality,
  fix or delete it proactively and tell the user.
- **Embedding provider setup** (vector search):
  - Ollama (local, default): `systemctl start ollama && ollama pull nomic-embed-text`,
    then `memory embed` to backfill.
  - OpenAI-compatible API: `memory config --set embedding.provider=openai
    --set embedding.url=https://api.openai.com --set embedding.model=text-embedding-3-small`
    (key read from `$OPENAI_API_KEY`; override var name with
    `--set embedding.api_key_env=NAME`).
  - After switching models, run `memory embed` — vectors from other models are
    ignored at search time.
