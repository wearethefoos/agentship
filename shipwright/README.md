# shipwright

Rebuild any app in Rust — cost-effectively, without losing behavior on the
way. A shipwright rebuilds a ship plank by plank while it stays seaworthy;
this plugin does the same to software: the original app stays the oracle
until the port proves itself against it.

## How it works

Six checkpointed phases, each a skill. Between phases the pipeline stops,
reports, and waits for your go-ahead — every phase names its cost profile
before it runs.

1. `/shipwright:survey` — map structure, inventory every feature into a
   parity matrix, hunt bugs into a findings ledger, measure coverage.
2. `/shipwright:reinforce` — raise unit/integration coverage on the
   original; those tests become the port's specification.
3. `/shipwright:parity` — one e2e suite that runs against old AND new
   (Bruno for APIs, bats for CLIs, Playwright for web), baselined on the
   original.
4. `/shipwright:blueprint` — you decide preserve-vs-fix for every finding;
   agents research crates (with license checks), design the hexagonal
   architecture, scaffold the workspace.
5. `/shipwright:rebuild` — batches of parallel porter agents, tests first,
   structure-preserving, `TODO(port)` honesty markers, adversarial judge
   review per batch.
6. `/shipwright:sea-trial` — the same e2e questions asked of both
   implementations; every difference must map to a deliberate, documented
   decision.

`/shipwright:status` starts, resumes, or reports a rewrite at any point.

The bundled `rust-codestyle` skill defines the house Rust style the porters
follow (error-stack error handling, structured tracing, `pub(crate)`
defaults, `assert2` tests, a ~140-rule lint table installed verbatim) — and
it triggers on any Rust work, so it is useful outside rewrites too.

Cost control comes from model tiering (Haiku scouts, Sonnet workers, Opus
architects/judges, Fable only as escalation for gnarly modules) and from the
checkpoints: nothing expensive starts without you.

## The CLI

State lives in the original repo under `.shipwright/state.json` (commit it —
it is the rewrite's provenance). The `bin/shipwright` CLI manages it:

```bash
shipwright init --name app --kind api --target ../app-rs
shipwright status                     # phases, matrix, ledger at a glance
shipwright feature add "GET /users" --kind endpoint
shipwright feature set 1 e2e-old on   # flags: e2e-old, tests-ported,
                                      # implemented, documented, e2e-new
shipwright finding add "off-by-one in pagination" --kind bug --severity high
shipwright finding decide 1 fix --note "clearly wrong; new behavior in e2e"
shipwright crate check poem clap      # latest version + license verdict
shipwright report                     # full markdown report
```

Phase gates keep the pipeline honest: `parity` cannot complete until every
feature has a passing e2e test against the original, `blueprint` until every
finding has an explicit preserve/fix decision, `sea-trial` until every
feature passes against the port.

## Integrations (optional, degrade gracefully)

- **memory** plugin — durable facts (stack decisions, behavioral landmines)
  are saved across sessions when installed.
- **scribe** plugin — the plans and reports under `docs/rewrite/` follow its
  documentation conventions when installed.
- **Context7 MCP** — crate scouts verify current crate APIs against live
  docs instead of stale training data.
