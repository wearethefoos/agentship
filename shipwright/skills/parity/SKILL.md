---
name: parity
description: Shipwright phase 3 - build the e2e parity suite that runs identically against the original app and the future Rust port (bats for APIs and CLIs, Playwright for web apps), and record golden baselines from the original. Use after reinforce, or when the user says "e2e plan", "parity tests", "golden master".
---

# Parity — one e2e suite, two implementations

The original app is the oracle. This phase builds ONE end-to-end suite that
can point at either implementation via a single switch (base URL, binary
path), then records the original's answers as golden baselines. At sea-trial,
the same suite runs against the Rust port and every difference must be
explained. Do not write two suites — the whole point is that identical
questions get asked of both.

CLI: `"${CLAUDE_PLUGIN_ROOT}/bin/shipwright"` (or the SessionStart hook's
path). Start with:

```bash
shipwright status && shipwright phase start parity
```

## Harness by app kind

- **api** — [bats-core](https://github.com/bats-core/bats-core) (MIT) under
  `e2e/api/`, scenarios as `curl` + `jq` assertions against `$BASE_URL`;
  plain shell, so it needs no extra runtime and agents can run and debug it
  directly. Factor shared request/assertion helpers into a `helpers.bash` so
  scenarios stay one-screen readable. (A Bruno collection is an acceptable
  substitute only when the project already maintains one.)
- **cli** — [bats-core](https://github.com/bats-core/bats-core) (MIT) under
  `e2e/cli/`, binary under test from `$APP_UNDER_TEST`; assert on exact
  stdout/stderr/exit codes (language-agnostic, so it runs against both
  binaries unchanged).
- **web** — [Playwright](https://playwright.dev) (Apache-2.0) under
  `e2e/web/`, base URL from config/env. (Use Cypress instead only if the
  project already has it.)
- **worker/library** — golden files: a runner script feeds recorded inputs
  and diffs outputs against `e2e/golden/`.
- **mixed** — combine the above per surface.

The suite lives in the ORIGINAL repo (it outlives the port as the new app's
e2e suite — plan for that in naming and layout).

## Steps

1. **Plan.** Map every feature in `shipwright feature list` to at least one
   e2e scenario: happy path plus the error/edge cases that matter for that
   feature. Check the chosen harness's current usage with Context7 if unsure.
   Write the plan to `docs/rewrite/parity-plan.md`: harness choice and why,
   the switch mechanism, scenario table (feature id → scenarios), how to run,
   and a **Deliberate behavior changes** section (empty for now — the
   blueprint phase fills it as findings get decided `fix`).
2. **Build (Sonnet fan-out).** Launch `test-smith` agents, one per feature
   group, each owning its collection/spec files exclusively. Tests assert
   CURRENT behavior — quirks included, tagged with finding ids, exactly as
   in reinforce. Each agent runs its scenarios against the original app and
   must finish green.
3. **Baseline.** Run the full suite against the original yourself; commit
   goldens/recordings. Flip matrix flags as features get covered:
   `shipwright feature set <id> e2e-old on`. Flaky scenarios are findings
   (`--kind risk`) — a flaky oracle cannot verify a port.
4. **Deterministic by design.** Freeze time, seed randomness, pin fixture
   data where the harness allows; normalize legitimately-variable output
   (timestamps, ids) in assertions rather than deleting the assertion.

## Checkpoint

```bash
shipwright phase complete parity
```

(The gate requires every feature to have `e2e-old` on — if it refuses,
`shipwright feature list --pending e2e-old` lists the stragglers; cover them
or, for the rare untestable-end-to-end feature, record a finding explaining
why and use `--force` with the user's consent.) Report scenario counts and
runtime, then stop. Next phase: `/shipwright:blueprint` (crate research +
architecture, low–medium cost, needs YOUR preserve/fix decisions). Wait for
the go-ahead.
