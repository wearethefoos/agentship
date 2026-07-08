# Rust codestyle reference

Terse pattern reference. Rules first, code only where syntax is ambiguous.
For full examples and templates see [guide.md](guide.md) and
[minimal-service.md](minimal-service.md); for the error-handling rationale
see [error-handling.md](error-handling.md).

## Architecture

Two service types. Both use `tokio`, `clap`, `eyre`, `tracing`.

**API** (HTTP, poem/poem-openapi) — vertical slices over a shared layered
core:

```text
src/main.rs                    # CLI, server, type aliases wiring adapters
src/features/{entity}/mod.rs   # Submodule per entity
src/features/{entity}/{op}.rs  # One file per operation (get, create, update, delete, list)
src/adapter/                   # Shared middleware, auth, web utilities
src/core/                      # Cross-cutting services and business logic
src/persistence/               # Repository traits, entities, persistence errors
src/persistence/adapters/      # Concrete impls (postgres, http clients, ...)
```

Each operation file is self-contained: request/response DTOs, the handler,
and its tests live together. Cross-entity business logic goes in `core/`,
never in a feature file.

**Background service** (worker/daemon): flat or domain-grouped, no layer
split required.

## Layer wiring

- Persistence defines **traits** with bounds `Clone + Send + Sync + 'static`.
- Core defines **generic structs** parameterized by those traits.
- `main.rs` defines **type aliases** that wire concrete adapters to generic
  services.
- Each layer defines its own error enums. Errors never leak across layers —
  they are explicitly converted.

## Error handling

| Crate | Purpose | Layer |
|---|---|---|
| `thiserror` | `Error` + `Display` derive only | All |
| `error-stack` | `Report<T>`, `.change_context()`, `.attach()` | Persistence, core |
| `eyre` / `color-eyre` | Top-level startup `Result` | `main.rs` only |

**Rules:**

- Never use `#[from]` or `#[source]` from thiserror — all conversion is
  explicit via `error-stack`.
- Persistence errors: small `thiserror` enums, opaque markers. Return
  `Result<T, Report<E>>`.
- Core errors: business-meaningful variants. Return `Result<T, Report<E>>`.
- Startup errors (`main.rs`): use `.wrap_err("message")?` from `eyre`.
- Authorization/invariant checks: `error_stack::ensure!(condition, ErrorVariant)`.
- Attach context via `.attach("description")` or `.attach_with(|| format!(...))`.

**Persistence → core conversion** — always this shape:

```rust
.map_err(|error| match error.current_context() {
    PersistenceError::VariantA => error.change_context(CoreError::VariantX),
    PersistenceError::VariantB => error.change_context(CoreError::VariantY),
})?;
```

**Core → API conversion** — match inline in the handler on
`error.current_context()`. Log unexpected errors with
`tracing::error!(?error, "message")` before returning a 500. One HTTP status
per error variant.

## API endpoints (poem)

- Handler struct: `#[derive(Debug, Clone, Copy)]` unit struct, e.g.
  `struct OrderApi;`.
- Annotate impl block with `#[OpenApi(prefix_path = "...", tag = "...")]`.
- Each method: `#[oai(method = "get", path = "/...", operation_id = "camelCase")]`.
- Return `Result<{Operation}Response, {Operation}Error>`.
- Response enums: `#[derive(Debug, ApiResponse)]` with `#[oai(status = N)]`
  per variant.
- DTO structs: `#[derive(Debug, Clone, Object, o2o::o2o)]` with
  `#[from_owned(...)]` for conversions; `#[map(~.into())]` or
  `#[map(~.into_iter().map(Into::into).collect())]` for nested conversions.

## Main entry point

Use [minimal-service.md](minimal-service.md) as the template. Key rules:

- API services have `Spec` and `Server` subcommands via `clap` (`Spec`
  prints the OpenAPI document).
- `color_eyre::install()` first, then TLS crypto provider (if needed), then
  parse CLI.
- Server function: init tracing → create connections → build services →
  build `Route` → run `Server`.
- Middleware order: swagger UI → nest API → health endpoints → data → CORS →
  trace layer → metrics.
- Health: `/_health/liveness` (always 200), `/_health/readiness` (checks
  dependencies).

## Configuration

- `clap` with `#[clap(long, env = "...", default_value = "...")]` for all
  config fields.
- Group related config in sub-structs using `#[clap(flatten)]`.
- Secrets: `SecretBox<str>` from `secrecy`, with `hide_env_values = true`.
  Access via `.expose_secret()`.

## Visibility

- Default to `pub(crate)` for all types and fields within a service.
- Use `pub` only for lib.rs exports (integration tests, shared crates).

## Derives

Order: `Debug, Clone, PartialEq, Eq, Serialize, Deserialize` (include only
what's needed).

| Kind | Derives |
|---|---|
| Data struct | `Debug, Clone, PartialEq, Eq` |
| Serializable | add `Serialize, Deserialize` |
| API DTO | add `Object` (poem-openapi) |
| API response | `Debug, ApiResponse` (optionally `PartialEq, Eq`) |
| Error enum | `Debug, thiserror::Error` |
| Conversion | add `o2o::o2o` |

## Comments

No inline `//` comments explaining what code does — if the information is
useful at runtime, log it; otherwise delete it. Doc comments (`///`, `//!`)
on public API items and genuinely non-obvious internals are fine.

## Tracing

- Annotate key functions with `#[instrument]`. Skip large/sensitive args:
  `#[instrument(skip(service))]`.
- Values go as **structured fields**, never interpolated in the message
  string.

```rust
tracing::info!(user_id = %user_id, count = items.len(), "Processing");   // CORRECT
tracing::info!("Processing user {}", user_id);                           // WRONG
```

- `%` for Display, `?` for Debug, bare for numeric/string literals.
- Log errors at the API boundary: `tracing::error!(?error, "description")`.

## Testing

- **Location**: inline `#[cfg(test)] mod tests` at the bottom of the file
  for unit tests; `tests/` directory for integration tests.
- **Naming**: `it_should_` prefix — e.g. `it_should_reject_invalid_email`.
- **Assertions**: `assert2::check!` for value comparisons (better error
  output, soft-fail — the test continues). Standard `assert_eq!`/`assert!`
  for simple equality.
- **Pattern matching**: `assert2::assert!(let pattern = expr)` for
  destructuring assertions; fails immediately if the pattern doesn't match.
  Common shape: `assert!` to destructure, then `check!` to verify fields.

```rust
assert2::assert!(let Some(periods) = result.get(&1));
assert2::check!(periods.len() == 3);

assert2::assert!(let Some(Ok(parsed)) = stream.next().await);
assert2::assert!(let Err(error) = response);
assert2::assert!(let Some(Order { total, .. }) = latest_order);
assert2::check!(total == 42);
```

- **Mocking**: `#[cfg_attr(test, automock)]` on traits without a `Clone`
  bound; manual `mockall::mock!` block when the trait requires `Clone`.
- **Database tests**: `#[sqlx::test(fixtures("path/to/schema.sql",
  "path/to/fixture.sql"))]` with a `pool: PgPool` parameter.
- **Test macros**: `macro_rules!` for repetitive parameterized test patterns.
- **Coverage**: `cargo-llvm-cov` available but not mandatory; useful for
  finding untested paths.

## Dependencies

- Pin full versions: `thiserror = "2.0.12"`, not `thiserror = "2"`.
- Use workspace dependencies for shared crates: `poem = { workspace = true }`.
- Explicitly enable required features.

## Linting and formatting

- Lint table: [lints.toml](lints.toml) — copy into the workspace Cargo.toml,
  inherit per crate with `[lints] workspace = true`. Notable: `unsafe_code`
  and `unused_crate_dependencies` are denied.
- Format: `cargo fmt`, hard tabs (`indent_style = tab` in `.editorconfig`,
  `hard_tabs = true` in `rustfmt.toml`).
- Prefer `#[expect(...)]` over `#[allow(...)]` for temporary overrides.

## Naming conventions

| Kind | Pattern | Example |
|---|---|---|
| Service struct | `{Entity}Service` | `OrderService` |
| API handler | `{Entity}Api` | `OrderApi` |
| Repository trait | `{Read\|Mutate}{Entity}Repository` | `ReadOrderRepository` |
| Core error | `{Operation}{Entity}Error` | `CreateOrderError` |
| Response enum | `{Operation}{Entity}Response` | `CreateOrderResponse` |
| DTO struct | `{Entity}Dto` or `Api{Entity}` | `OrderDto`, `ApiOrder` |
