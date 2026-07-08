# agentship

Agent tools. The name is a play on the Dutch word *agentschap* ("agency"):
an agency of agents, pronounced almost the same — and in English it reads as
a ship crewed by agents.

The repo doubles as a Claude Code plugin marketplace.
Full documentation in [docs/](docs/README.md).

Install:

```
/plugin marketplace add wearethefoos/agentship
```

## Tools

- [memory](memory/) — long-term memory: SQLite + FTS5 + vector search,
  auto-recall hooks, remember/recall skills.
- [scribe](scribe/) — docs discipline: clean markdown under `./docs`, mermaid
  for flows/hierarchy, auto link-check after every docs edit.
- [shipwright](shipwright/) — rebuild any app in Rust: checkpointed six-phase
  agent pipeline with a feature parity matrix, findings ledger, and
  cost-tiered subagents.

## License

[MIT](LICENSE)
