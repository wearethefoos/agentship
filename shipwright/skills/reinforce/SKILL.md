---
name: reinforce
description: Shipwright phase 2 - raise unit and integration test coverage on the ORIGINAL app before porting, so the tests can be ported as the specification. Use after the survey phase, or when the user says "reinforce the tests", "improve coverage before the port".
---

# Reinforce — tests are the spec the port will be checked against

Every behavior pinned by a test now gets ported faithfully later; every
untested behavior relies on an agent reading code correctly. The ported test
suite is the primary spec of the rewrite (the tests-as-spec principle), so
spend here saves multiples in the rebuild phase.

CLI: `"${CLAUDE_PLUGIN_ROOT}/bin/shipwright"` (or the SessionStart hook's
path). Start with:

```bash
shipwright status && shipwright phase start reinforce
```

## Steps

1. **Target selection.** From the survey's coverage map, list the modules
   that are (a) poorly covered AND (b) early or risky in the port order.
   Skip dead code and framework glue — do not chase a coverage number;
   chase pinned behavior where the port can go wrong: edge cases, error
   paths, boundary values, quirks.
2. **Confirm scope with the user** (one short message, not a question per
   module): which modules get reinforced, roughly how many test-writer
   agents that means. This is the phase's cost lever.
3. **Fan out `test-smith` agents (Sonnet)** — one per module or coherent
   module group, launched together. Each owns its test files exclusively;
   never assign two agents tests in the same file. Give each: the CLI path,
   its modules, the survey's notes on those modules, relevant finding ids
   (quirks must be pinned as quirks, named and commented with the finding
   id), and how to run the suite.
4. **Verify the whole.** After the fan-out, run the FULL test suite yourself.
   Fix-ups for cross-agent collisions (fixture conflicts, flaky ordering) go
   to a single follow-up test-smith, not another broad fan-out.
5. **Record.** Append a short coverage-delta section to
   `docs/rewrite/survey.md` (before/after per reinforced module). New bugs
   discovered while writing tests become findings:
   `shipwright finding add ... --kind bug`.

## Checkpoint

```bash
shipwright phase complete reinforce
```

Report: tests added, modules reinforced, quirks pinned (finding ids), suite
status — then stop. Next phase: `/shipwright:parity` (e2e suite, mostly
Sonnet, cost scales with feature count). Wait for the go-ahead.
