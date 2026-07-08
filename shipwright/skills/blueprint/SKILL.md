---
name: blueprint
description: Shipwright phase 4 - design the Rust rewrite. Forces preserve/fix decisions on every finding, researches crates with license checks, designs the hexagonal architecture and lint policy, scaffolds the workspace, and fixes the port order with model tiers. Use after parity, or when the user says "rewrite plan", "design the Rust app", "blueprint".
---

# Blueprint — decide everything before the expensive phase

The rebuild phase fans out many agents; anything undecided here gets decided
by whichever agent hits it first, differently each time. The blueprint makes
every cross-cutting decision once, in writing.

CLI: `"${CLAUDE_PLUGIN_ROOT}/bin/shipwright"` (or the SessionStart hook's
path). Start with:

```bash
shipwright status && shipwright phase start blueprint
```

## Steps

1. **Decide the findings (with the user — this is why blueprint is a
   checkpoint).** For every `shipwright finding list --decision pending`
   entry, the user chooses `preserve` (bug-for-bug compatibility) or `fix`.
   Present them grouped with your recommendation — default to **preserve**
   for anything callers might depend on; recommend **fix** only for clear
   defects (security holes, crashes, data corruption). Batch via
   AskUserQuestion where sensible; record each:
   `shipwright finding decide <id> fix --note "why"`.
   For every `fix`: update the parity suite so the scenario asserts the OLD
   behavior against `original` and the CORRECTED behavior against `rust`
   (env-switched expectation, tagged with the finding id), and list it in the
   **Deliberate behavior changes** section of `docs/rewrite/parity-plan.md`.
2. **Crate research (Sonnet).** Derive the needs list from the survey
   (HTTP server, DB, serialization, auth, ...) and launch `crate-scout`
   agents — one per 3–5 needs, concurrently. House defaults, scouts verify
   current versions rather than re-litigating: **poem**/**poem-openapi** for
   APIs, **clap** (derive) for CLIs, **tokio** runtime, **serde**,
   **error-stack** + **thiserror** (derive only) for library errors with
   **eyre**/**color-eyre** in main, **tracing**, **secrecy** for secrets,
   **o2o** for DTO conversions; testing: **assert2**, **insta**,
   **proptest**, **cargo-nextest**, **mockall**, **wiremock**,
   **testcontainers**. Any `REVIEW-LICENSE` verdict goes to the user —
   never adopt copyleft silently.
3. **Architecture.** Loosely hexagonal, mapped from the survey: `domain/`
   (pure logic, no IO), ports as traits owned by the domain, adapters
   (HTTP handlers, repositories, CLI shell) at the edges, composition in
   `main`. Loosely means: traits where the survey found real seams
   (DB, external services, clock), not a trait for everything — over-abstraction
   is the classic hexagonal failure. Cargo workspace when the app has real
   subsystem boundaries; single crate with modules otherwise.
4. **Policy.** The house style is the `rust-codestyle` skill bundled with
   this plugin — read its `reference.md` now; it governs error handling,
   tracing, visibility, derives, naming, and tests for everything the
   porters write.
   - Latest stable Rust: `rust-toolchain.toml` pinning the current stable
     (check with `rustup check` or the releases page), newest edition.
   - Lints: install the skill's `lints.toml`
     (`"${CLAUDE_PLUGIN_ROOT}/skills/rust-codestyle/lints.toml"`) verbatim
     into the workspace `Cargo.toml`, with `[lints] workspace = true` per
     crate. Hard tabs (`.editorconfig` + `rustfmt.toml`). Prefer
     `#[expect(...)]` over `#[allow(...)]`, always with a justification.
   - **cargo-deny**: license allowlist (permissive only, or as the user
     decided), advisories, and bans on duplicate major versions.
   - Phase A porting rules (the porter agent enforces them): structure-
     preserving, `TODO(port)`/`PERF(port)`/`SAFETY:` markers, PORT STATUS
     footers, tests-first.
5. **Port plan.** Fix the module order (dependency-sorted from the survey)
   into batches of independent modules. Assign a model tier per module:
   routine → Sonnet; tricky → Sonnet with mandatory judge review; gnarly
   (heavy concurrency, metaprogramming, algorithmic subtlety) → **Fable**.
   Note shared files (lib.rs, workspace Cargo.toml) as orchestrator-owned.
6. **Scaffold.** Create the target workspace (path in `shipwright status`):
   cargo init, directory skeleton, toolchain + lints + deny config, CI script
   (`fmt --check`, `clippy`, `nextest run`, `cargo deny check`), empty port
   modules with PORT STATUS stubs. It must compile clean before the phase
   ends. Start the new repo's `docs/` (scribe conventions): architecture
   page with a mermaid diagram of the hexagon.
7. **Write `docs/rewrite/blueprint.md`** in the original repo: module mapping
   table (old path → new crate/module → batch → model tier), crate table
   (crate, version, license, why), policy summary, and the behavior-changes
   list. If the memory plugin is active, save the stack decisions
   (`memory add "..." --type project`).

## Checkpoint

```bash
shipwright phase complete blueprint
```

(The gate refuses while any finding is still `pending`.) Report the stack,
the batches, and the model-tier split — then stop. Next phase:
`/shipwright:rebuild` — the bulk of the token spend; estimate agent count
from the batch plan so the user decides with numbers. Wait for the go-ahead.
