# Setup

## Prerequisites

- Claude Code with plugin support
- `python3` on PATH (any recent version; plugins are stdlib-only)
- Optional, for memory's vector search: [Ollama](https://ollama.com) or an
  OpenAI-compatible embeddings API

## Installing

Add this repo as a plugin marketplace, then install the plugins you want:

```text
/plugin marketplace add wearethefoos/agentship
/plugin install memory@agentship
/plugin install scribe@agentship
/plugin install shipwright@agentship
/reload-plugins
```

Working from a local clone instead: `/plugin marketplace add /path/to/agentship`.

### Memory: enable vector search (optional)

Full-text search works out of the box. For semantic search:

```bash
systemctl start ollama
ollama pull nomic-embed-text
memory embed        # backfill memories saved before setup
```

Other providers: see [embeddings](memory.md#embeddings).

### CLI on PATH (optional)

From a clone of this repo:

```bash
ln -s "$(pwd)/memory/bin/memory" ~/.local/bin/memory
ln -s "$(pwd)/scribe/bin/check_links" ~/.local/bin/check_links
ln -s "$(pwd)/shipwright/bin/shipwright" ~/.local/bin/shipwright
```

## Developing

Claude Code installs plugins by copying them into its cache, so changes in
this repo do not apply automatically:

```text
/plugin marketplace update agentship
/plugin install <plugin>@agentship     # first install of a new plugin
/reload-plugins                        # apply changes to the running session
```

For plugin development, add the marketplace from a local clone
(`/plugin marketplace add /path/to/agentship`) so updates come from your
working tree instead of GitHub.

New plugins must also be registered in `.claude-plugin/marketplace.json` at
the repo root, or the marketplace will not offer them.

### Testing without touching real state

Both CLIs are plain Python scripts, testable from the shell:

```bash
AGENTSHIP_MEMORY_DIR=/tmp/mem-test memory/bin/memory add "test" --type note
scribe/bin/check_links docs
```

Hooks read their event JSON from stdin, so they can be exercised directly:

```bash
echo '{"prompt":"what about postgres?"}' | python3 memory/hooks/recall.py
echo '{"tool_input":{"file_path":"docs/x.md"},"cwd":"."}' \
  | python3 scribe/hooks/post_write_check.py
```

For memory's embedding paths without a real provider, point
`embedding.url` at a stub server that answers `/api/embed`.
