---
name: survey
description: Shipwright phase 1 - analyze the original app before rewriting it in Rust. Maps structure and architecture, inventories every externally observable feature into the parity matrix, measures test coverage, and hunts bugs/anti-patterns into the findings ledger. Use when starting a rewrite or when the user says "survey the app" or "analyze this app for the rewrite".
---

# Survey — know the ship before rebuilding it

Goal: after this phase, the pipeline knows every feature the app has (parity
matrix), every defect and quirk worth a deliberate decision (findings
ledger), where the tests are thin, and in what order to port. The rewrite's
quality ceiling is set here — a feature missed now is a feature silently lost.

CLI: `"${CLAUDE_PLUGIN_ROOT}/bin/shipwright"` (or the path from the
SessionStart hook). Start with:

```bash
shipwright status && shipwright phase start survey
```

## Steps

1. **Inventory (cheap, parallel).** Launch `inventory-scout` agents (Haiku) —
   one for a small repo, one per top-level area for a large one, in a single
   message so they run concurrently. Each returns modules, public surface,
   tests, dependencies, entry points, and records every externally observable
   feature it finds: `shipwright feature add "GET /users" --kind endpoint`.
   Give each agent the CLI path and its exact scope. Feature granularity:
   one entry per thing a user or caller would notice missing — endpoint,
   CLI command, page, scheduled job, notable library function.
2. **Architecture (judgment, Opus).** Launch one `code-surveyor` agent (or
   one per subsystem for large apps) for boundaries, coupling, hidden
   invariants, hexagonal mapping, and a dependency-ordered port sequence
   with complexity ratings (routine / tricky / gnarly).
3. **Bug hunt (adversarial, Opus, parallel with step 2).** Launch
   `bug-hunter` agents, one per area. They record findings with decision
   `pending`. Do not decide preserve-vs-fix now; that is the blueprint
   checkpoint's job.
4. **Coverage.** Run the existing test suite with the project's coverage tool
   if one is configured (pytest --cov, nyc, go test -cover, ...); otherwise
   have an inventory-scout map which modules have no tests. Record the
   weakest areas — they drive the reinforce phase.
5. **Write the survey report** to `docs/rewrite/survey.md` in the original
   repo (scribe conventions apply if installed): architecture summary with a
   mermaid diagram, port order table with complexity ratings, coverage map,
   and a pointer to `shipwright report` for the live matrix/ledger. Do not
   duplicate the matrix into the doc — it changes; link it.
6. **Remember.** If the memory plugin is active (its SessionStart
   announcement lists a CLI), save durable facts: the app's kind and target,
   the gnarly modules, and any behavioral landmines
   (`memory add "..." --type project --project <app>`).

## Checkpoint

```bash
shipwright phase complete survey
```

(The gate requires a non-empty feature matrix.) Then report to the user:
feature count by kind, findings by severity, coverage picture, the 3 riskiest
modules — and stop. Name the next phase (`/shipwright:reinforce`, Sonnet
fan-out, cost scales with coverage gaps) and wait for the go-ahead.
