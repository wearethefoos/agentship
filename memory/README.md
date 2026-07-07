# memory

Long-term memory for Claude Code. SQLite storage, FTS5 full-text search,
vector (semantic) search, auto-recall hooks, and remember/recall skills.
Pure Python stdlib — no dependencies.

## Storage

`~/.config/agentix/memory/` (override with `AGENTIX_MEMORY_DIR`):

- `memory.db` — SQLite: `memories` table, `memories_fts` FTS5 index (kept in
  sync by triggers), `embeddings` table (float32 blobs, tagged by model).
- `config.json` — embedding provider config.

## CLI

```bash
memory add "User prefers rebase over merge" --type preference --tags git
memory search "git workflow"                 # hybrid (FTS + vector, RRF-fused)
memory search "rebase" --mode fts            # keyword only, no embedder needed
memory search "how do I like to merge" --mode vector
memory list -n 20 --type preference
memory get 3 / memory edit 3 --content "..." / memory delete 3
memory embed                                 # backfill missing embeddings
memory stats
memory config --set embedding.provider=openai
```

Types: `note` (default), `fact`, `preference`, `project`, `reference`.
Filters on search/list: `--type`, `--project`, `--tag`.
`--format json|context|text` for scripting, hook injection, or humans.

## Vector search setup

Default provider is local Ollama:

```bash
systemctl start ollama          # or: ollama serve
ollama pull nomic-embed-text
memory embed                    # backfill anything saved before setup
```

Or any OpenAI-compatible endpoint:

```bash
memory config --set embedding.provider=openai \
              --set embedding.url=https://api.openai.com \
              --set embedding.model=text-embedding-3-small
# key read from $OPENAI_API_KEY (change with --set embedding.api_key_env=NAME)
```

Everything degrades gracefully: with no embedder reachable, `add` stores
without a vector (backfill later with `memory embed`) and hybrid search falls
back to full-text.

## Claude Code integration

Install as a plugin (this repo is a marketplace):

```
/plugin marketplace add /home/wouter/Work/agentix
/plugin install memory@agentix
```

You get:

- **Hooks** — `SessionStart` announces the tool and recent memories;
  `UserPromptSubmit` injects keyword-relevant memories into context on every
  prompt (FTS only, so it stays fast; skipped for slash commands and short
  prompts).
- **Skills** — `remember` (save, with dedupe-first discipline), `recall`
  (deliberate/semantic lookup), `memory-manage` (edit, forget, stats,
  embedding config).

Optionally symlink the CLI onto your PATH:

```bash
ln -s /home/wouter/Work/agentix/memory/bin/memory ~/.local/bin/memory
```
