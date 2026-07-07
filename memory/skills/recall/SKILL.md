---
name: recall
description: Search the agentship memory store. Use when the user asks "do you remember...", "what did I tell you about...", "check your memory", or when starting work that likely has stored context (preferences, project constraints, past decisions) not found in the repo. Keyword-relevant memories are auto-injected per prompt by a hook; use this skill for deliberate or semantic (meaning-based) lookups.
---

# Recall

Search memories with the agentship memory CLI:

```bash
"${CLAUDE_PLUGIN_ROOT}/bin/memory" search "QUERY" --mode hybrid -n 8
```

If `${CLAUDE_PLUGIN_ROOT}` is not resolved in your context, the absolute CLI path
was printed by the SessionStart hook ("agentship memory tool active. CLI: ...").

## Modes

- `--mode hybrid` (default) — full-text + vector search fused with reciprocal
  rank fusion. Best general choice; falls back to full-text automatically if
  the embedding provider is down.
- `--mode fts` — exact keyword match (FTS5, bm25-ranked). Fast, no embedding
  provider needed. Use for names, ids, error strings.
- `--mode vector` — pure semantic similarity. Use when the user's phrasing
  likely differs from the stored wording.

## Filters and formats

```bash
memory search "deploy" --type project --project agentship --tag infra
memory search "editor" --format json          # machine-readable
memory list -n 20 --type preference           # browse without a query
memory get 42                                 # full record
```

## Guidance

- Search with several distinct key terms, not full sentences, for fts;
  full sentences are fine for vector/hybrid.
- No hits ≠ no memory: retry once with synonyms or `--mode vector` before
  telling the user nothing is stored.
- Quote recalled memories by id (e.g. "#12") so the user can edit/delete them.
