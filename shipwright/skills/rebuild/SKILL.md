---
name: rebuild
description: Shipwright phase 5 - port the app to Rust module by module, tests first, in batches of parallel porter agents with judge review between batches. The bulk of the rewrite's cost. Use after blueprint, or when the user says "start porting", "implement the Rust app", "continue the rebuild".
---

# Rebuild — many small ports, verified continuously

The blueprint decided everything; this phase executes it as a loop of small,
independently verified ports. Hundreds of scoped prompts beat one heroic
agent: each porter gets one module, ports its tests first, and finishes
green. You (the main thread) orchestrate — you own the shared files and the
loop, and you write no module code yourself.

CLI: `"${CLAUDE_PLUGIN_ROOT}/bin/shipwright"` (or the SessionStart hook's
path). Start with:

```bash
shipwright status && shipwright phase start rebuild
```

Resume-safe: the parity matrix knows what is done. On re-entry, continue
with the first batch containing features where `tests-ported` or
`implemented` is off.

## The batch loop

For each batch in the blueprint's port plan:

1. **Prepare (serial, you).** Declare the batch's modules in lib.rs/mod.rs,
   add any batch-new crates to Cargo.toml (blueprint-listed only), commit a
   compiling skeleton. Porters never touch shared files.
2. **Fan out `porter` agents** — one per module, one message, each with: its
   blueprint section, original module path, relevant finding ids and
   decisions, the CLI path, the codestyle reference path
   (`"${CLAUDE_PLUGIN_ROOT}/skills/rust-codestyle/reference.md"` — resolve
   it before passing), and its exclusive file list. Model per the
   blueprint tier: routine/tricky → default (Sonnet), gnarly → pass
   `model: fable` on the Agent call. Porters port the module's tests first,
   then implement until green, with `TODO(port)` honesty markers, and flip
   their matrix flags (`tests-ported`, `implemented`).
3. **Gate (serial, you).** `cargo fmt --check && cargo clippy --all-targets
   && cargo nextest run && cargo deny check` on the whole workspace.
4. **Judge.** Launch one `sea-trial-judge` (Opus) per batch — for tricky/
   gnarly modules or any porter reporting low confidence, one per module.
   The judge diffs behavior against the original module (the oracle),
   audits markers and dependencies, and flips flags OFF where claims don't
   hold.
5. **Repair loop.** Judge failures go back to a porter with the judge's
   evidence. After two failed repair attempts on the same module, escalate:
   relaunch with `model: fable` and both prior failure reports. Never let an
   agent grind past that — a third identical retry is burned tokens.
6. **Checkpoint the batch.** Commit, then a one-line progress report to the
   user (`shipwright status`). Between batches is the natural pause point if
   the user wants to spread cost over sessions.

## Documentation (with the batch, not after)

Each batch's porter documents its module: rustdoc on public items, and the
new repo's `docs/` updated per scribe conventions. Modules whose findings
were decided `fix` must say so in their docs, with the finding id and the
old-vs-new behavior. Flip `documented` per feature as it lands. The final
batch includes the new app's README, setup, and architecture pages.

## Checkpoint

```bash
shipwright phase complete rebuild
```

(The gate requires `tests-ported`, `implemented`, and `documented` on every
feature.) Report: modules ported, total TODO(port) markers remaining (grep
the workspace — surface the count honestly), judge verdicts — then stop.
Next phase: `/shipwright:sea-trial` (differential verification, Opus-heavy,
medium cost). Wait for the go-ahead.
