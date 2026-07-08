---
name: status
description: Start, resume, or check a shipwright Rust rewrite. Use when the user says "rebuild this app in Rust", "port this to Rust", "start a rewrite", "rewrite status", "what's next in the rewrite", or at the start of any session in a repo where the SessionStart hook announced an active rewrite.
---

# Shipwright status

Shipwright rebuilds an app in Rust through six checkpointed phases. You (the
main thread) are the orchestrator: you delegate to subagents, keep the state
current, and stop at every checkpoint for the user's go-ahead. You do not
read whole codebases or write production code yourself — that is what the
tiered subagents are for.

CLI: `"${CLAUDE_PLUGIN_ROOT}/bin/shipwright"` — if that variable is not
resolved in your context, the SessionStart hook printed the absolute path.
All commands below run from the ORIGINAL app's repo root.

## No rewrite yet?

If `shipwright status` reports no state, start one:

```bash
shipwright init --name <app> --kind api|cli|web|worker|library|mixed --target ../<app>-rs
```

Infer `--name` and `--kind` from the repo; only ask the user when genuinely
ambiguous (e.g. an app that is equally API and CLI → `mixed`). The target is
a sibling directory by default; respect an explicit user preference. Then
proceed to `/shipwright:survey`.

## The pipeline

| Phase | Skill | What it produces | Cost profile |
|---|---|---|---|
| survey | /shipwright:survey | feature matrix, findings ledger, port order | medium — Haiku scouts + Opus analysts |
| reinforce | /shipwright:reinforce | unit/integration coverage on the original | medium–high — Sonnet fan-out |
| parity | /shipwright:parity | e2e suite that runs against old AND new | medium — mostly Sonnet |
| blueprint | /shipwright:blueprint | Rust architecture, crates, workspace scaffold | low–medium — crate scouts + design |
| rebuild | /shipwright:rebuild | the ported app, module by module | high — the bulk of the spend |
| sea-trial | /shipwright:sea-trial | differential verification, final report | medium — Opus judges |

## Resuming

1. Run `shipwright status` and show the result.
2. If a phase is `in_progress`, summarize what remains (`shipwright feature
   list --pending <flag>`, `shipwright finding list --decision pending`) and
   continue that phase's skill.
3. If between phases, name the next phase, its cost profile from the table
   above, and wait for the user's go-ahead before invoking it. Never start a
   new phase unprompted — checkpoints exist for cost control.

`shipwright report` prints the full markdown report (parity matrix, findings,
deliberate behavior changes) whenever the user wants the big picture.
