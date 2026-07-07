# Agentix documentation

Agentix is a collection of agent tools for Claude Code, packaged as plugins
and distributed from this repo, which doubles as a plugin marketplace.

## Start here

- [Setup](setup.md) — install the marketplace and plugins, optional vector
  search, development workflow.
- [Architecture](architecture.md) — repo layout, plugin anatomy, and the
  conventions every plugin follows.

## Plugins

- [Memory](memory.md) — long-term memory: SQLite storage, full-text (FTS5)
  and vector search, auto-recall hooks, remember/recall skills.
- [Scribe](scribe.md) — documentation discipline: clean markdown under
  `./docs`, mermaid diagrams, automatic link checking after every docs edit.
