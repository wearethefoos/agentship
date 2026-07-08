---
name: rust-codestyle
description: Opinionated Rust conventions for writing or reviewing Rust code - error handling with error-stack, structured tracing, layered services, strict lints. Use when creating or modifying .rs files, adding a Rust service, changing Cargo.toml, defining errors, adding poem/poem-openapi endpoints, writing Rust tests, or reviewing Rust diffs - including every shipwright blueprint/rebuild phase. Also use when the user mentions error-stack, thiserror, eyre, tracing, o2o, sqlx, tokio, clap, secrecy, or Rust code style.
---

# Rust codestyle

Authoritative sources are bundled next to this file — read them before
writing code, do not paraphrase from memory:

- [reference.md](reference.md) — terse rule lookup (read first)
- [guide.md](guide.md) — full guide with examples (consult for details/templates)
- [minimal-service.md](minimal-service.md) — new-service template
- [error-handling.md](error-handling.md) — error-handling rationale
- [lints.toml](lints.toml) — the workspace lint table to install verbatim

Load the reference at the start of any non-trivial Rust task. Load the full
guide only when the reference is ambiguous or you need a concrete example.

## Non-negotiable rules

These trip up new code most often. Verify each one before finishing.

1. **Error handling.** All persistence/core APIs return `Result<T, Report<E>>`
   from `error-stack`. Errors are `#[derive(thiserror::Error)]` with
   `#[error("...")]`. **Never** use `#[from]` or `#[source]` — conversion is
   explicit via `.change_context()`. Convert persistence → core with
   `.map_err(|e| match e.current_context() { ... })`. `main.rs` returns
   `eyre::Result<()>` with `.wrap_err("...")`. Invariant and authorization
   checks use `error_stack::ensure!(cond, ErrorVariant)`.
2. **Tracing.** Values go as **structured fields**, never interpolated:
   `tracing::info!(user_id = %user_id, "…")` — not
   `tracing::info!("user {}", user_id)`. Use `%` for Display, `?` for Debug.
   Log at the API boundary with `tracing::error!(?error, "message")` before
   returning 500s. Annotate key functions with `#[instrument(skip(large_arg))]`.
3. **No inline comments.** Don't add `//` comments explaining what code does;
   log something useful instead. Doc comments (`///`, `//!`) on public API
   items and non-obvious internals are fine.
4. **Visibility.** Default to `pub(crate)` for everything inside a service.
   `pub` only for lib.rs exports (integration tests) or shared crates.
5. **API architecture.** Vertical slices: one file per operation under
   `features/{entity}/`, containing DTOs, handler, and tests. Cross-cutting
   logic in `core/`, repository traits in `persistence/`, concrete adapters
   wired via type aliases in `main.rs`.
6. **Derive order.** `Debug, Clone, PartialEq, Eq, Serialize, Deserialize` —
   only what's needed. Error enums: `Debug, thiserror::Error`. API DTOs add
   `Object` (poem-openapi). Use `o2o::o2o` with `#[from_owned(...)]` for
   conversions.
7. **Secrets.** `SecretBox<str>` from `secrecy`,
   `#[clap(long, env = "…", hide_env_values = true)]`, access via
   `.expose_secret()`.
8. **Dependencies.** Pin full versions (`thiserror = "2.0.12"`, not `"2"`).
   Prefer `{ workspace = true }` for shared crates and explicitly enable
   features.
9. **Tests.** `#[cfg(test)] mod tests` at the bottom of the file. Names:
   `it_should_…`. Use `assert2::check!` for value comparisons (soft-fail,
   better output) and `assert2::assert!(let pattern = expr)` for
   destructuring. Database tests: `#[sqlx::test(fixtures(...))]` with
   `pool: PgPool`.
10. **Lints.** Install [lints.toml](lints.toml) in the workspace Cargo.toml
    (`[lints] workspace = true` per crate). `unsafe_code` is denied. Prefer
    `#[expect(...)]` over `#[allow(...)]` for temporary overrides. Format
    with `cargo fmt`, hard tabs.

## Workflow

For any Rust task, before writing code:

1. Read [reference.md](reference.md).
2. Identify what you are building: API service (vertical-slice features over
   layered core), background service (flat), or library crate.
3. In an existing codebase, find the closest analogue (an existing feature
   file, an existing repository trait) and mirror its shape rather than
   inventing.
4. For a new service, follow [minimal-service.md](minimal-service.md).

After writing code, verify:

- `cargo fmt` clean.
- `cargo clippy` clean under the workspace lint table.
- New behavior has a test with an `it_should_…` name.
- Errors propagate through `.change_context()` / `.attach()` — no `?` on raw
  external errors that would leak into a `Report<CoreError>` chain without
  conversion.
- All `tracing::` calls use structured fields.

## Common mistakes

- Using `#[from]` on a thiserror variant to auto-convert a persistence error
  into a core error → **wrong**, use `.map_err` + `.change_context()`.
- Two error variants mapping to the same HTTP status in one response enum →
  group them under one variant.
- Interpolating values into tracing message strings → not queryable; use
  fields.
- Wrapping middleware/services that return `BoxError` → define an error type
  at the boundary and convert internally; fallback
  `Report::new(MyError::Variant).attach(e.to_string())`.
- Adding inline `//` comments explaining what code does → delete them, log
  if useful.
- Leaving `Result<T, Box<dyn Error>>` or `anyhow::Result` in library code →
  use `Result<T, Report<E>>`.
