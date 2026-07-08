# Error handling: error-stack + thiserror + eyre

This document explains the error-handling architecture for Rust services built with a layered design (web → core → persistence). It covers what the pattern is, why it was chosen over the alternatives, and how to apply it. For a complete runnable example, see [minimal-service.md](minimal-service.md).

## The pattern in one paragraph

Three crates, each with one narrow job:

- **thiserror** — derives `Error` + `Display` for error enums. That is all it is used for: never `#[from]`, never `#[source]`.
- **error-stack** — `Report<E>` is the propagation type in the persistence and core layers. Every fallible function there returns `Result<T, Report<E>>`. Errors are converted at layer boundaries explicitly with `.change_context()`, enriched with `.attach()` / `.attach_with()`, and invariants are checked with `error_stack::ensure!`.
- **eyre / color-eyre** — used only in `main.rs`, with `.wrap_err()`, for process setup and top-level reporting. Never in library or service code.

Error enums contain **only domain variants** (the ones that map to distinct HTTP status codes) plus exactly **one `Unexpected` variant** that absorbs every infrastructure failure (database, serialization, I/O, transactions — everything that maps to HTTP 500).

## The problem this solves

A layered service that uses `thiserror` alone, with `#[from]` conversions between layers, develops several predictable problems:

1. **No error traceability.** When an error occurs deep in the call stack, the chain of where it originated and what the code was trying to do is lost.
2. **Information loss.** Domain errors (like `UserNotFound`) get collapsed into generic variants when crossing layer boundaries, so the web layer can no longer map them to precise HTTP status codes.
3. **Excessive boilerplate.** Each operation grows 3–5 error enums, manual `From` implementations, and long match statements — easily 40–60 lines per operation.
4. **Infrastructure errors leak across layers.** `#[from] sqlx::Error` in a core-layer enum means the domain layer now depends on the database driver, violating the layering.
5. **Too many infrastructure variants.** `DatabaseError`, `SerializationError`, `TransactionError`, `FileStorageError`… all map to HTTP 500 anyway. They clutter every enum and every match.

```rust
// The anti-pattern this document exists to prevent:
#[derive(Debug, Error)]
pub enum UpdateUserError {
    #[error("Something went wrong in the database")]
    DatabaseError(#[from] sqlx::Error), // ❌ sqlx leaks into the core layer
    #[error("The user was not found")]
    UserNotFound,
}

// And the variant explosion that comes with it:
enum MyError {
    DatabaseError(sqlx::Error),             // ❌ maps to 500
    SerializationError(serde_json::Error),  // ❌ maps to 500
    TransactionError,                        // ❌ maps to 500
    FileStorageError(std::io::Error),        // ❌ maps to 500
    // Only these matter for HTTP mapping:
    NotFound,       // → 404
    InvalidInput,   // → 400
}
```

What is needed instead:

1. Error traceability throughout the call stack.
2. Domain error information preserved across layers (for HTTP status mapping).
3. All infrastructure/unexpected errors wrapped in a **single variant**.
4. Less boilerplate, not more.

## Alternatives considered

### thiserror alone (with `#[from]` between layers)

Plain `thiserror` enums with `From` implementations at each boundary.

- Good: no extra dependencies.
- Good: widely known pattern; works well for small, flat programs.
- Bad: no built-in error traceability.
- Bad: significant boilerplate (3–5 error types per feature, manual `From` impls).
- Bad: information loss when converting between layers.
- Bad: `#[from]` silently threads infrastructure types (`sqlx::Error`) into domain enums.
- Bad: difficult to debug production issues — you get the final error, not the story.

### anyhow / eyre everywhere

Use a dynamic error type (`anyhow::Error` / `eyre::Report`) as the universal return type, adding context strings with `.context()` / `.wrap_err()`.

```rust
use eyre::{Result, WrapErr};

fn update_user() -> Result<()> {
    database_operation().wrap_err("Failed to update user")?;
    Ok(())
}
```

- Good: minimal boilerplate; any `std::error::Error` propagates with `?`.
- Good: guaranteed backtraces and customizable report handlers.
- Bad: the generic `Result<T>` erases the error type — callers cannot know which errors can occur.
- Bad: no compile-time guarantee that a handler covers all error cases.
- Bad: mapping specific errors to HTTP status codes at the web layer requires fragile downcasting.
- Bad: error propagation becomes implicit; the layering disappears from the signatures.

This is the right tool **for binaries** — a `main.rs` that only needs to report failure well — but the wrong tool for library and service layers that need typed errors. That is exactly how it is used in this pattern.

### error-stack (chosen)

[`error-stack`](https://docs.rs/error-stack) wraps a typed context (`Report<E>` where `E` is your thiserror enum) in a report that accumulates the full chain of contexts and attachments as the error propagates upward.

```rust
// Domain errors still defined with thiserror — Display only
#[derive(Debug, Error)]
pub enum UserError {
    #[error("User with id {0} not found")]
    NotFound(i64),
    #[error("Invalid country code: {0}")]
    InvalidCountryCode(String),
}
```

A propagated report prints the whole story:

```text
Error: User with id 42 not found
├─▶ at src/core/user.rs:123
├─▶ Failed to update user
└─▶ caused by: Persistence operation failed
    ├─▶ at src/persistence/postgres.rs:456
    └─▶ caused by: no rows returned
```

- Good: automatic traceability with the full context chain and capture locations.
- Good: preserves typed error information through the layers — the current context is always a concrete enum you can match on.
- Good: large reduction in error-handling code (no `From` impls, no infrastructure variants).
- Good: works with existing `thiserror` enums; type-safe, compile-time checked.
- Good: integrates well with `tracing`; inline context via `.attach()`.
- Good: infrastructure errors stay encapsulated — persistence details never leak into core.
- Neutral: a small new API surface to learn (`.change_context()`, `.attach()`, `.current_context()`).
- Neutral: minimal overhead (~2–5%, in error paths only).
- Bad: one additional dependency.

**Why error-stack over eyre for the layers:** in a layered service, the web layer must map domain errors to specific HTTP responses. That requires typed errors across boundaries, which eyre erases. error-stack keeps the type (`Report<UpdateUserError>`) while still carrying the rich context chain that eyre gives you.

## The rules

1. **thiserror is for `derive(Error)` + `Display` only.** Never use `#[from]`. Never use `#[source]`. Chaining and causality are error-stack's job; the enum is just the typed context.
2. **Persistence and core functions return `Result<T, Report<E>>`.** `E` is the layer's own error enum.
3. **Error enums contain domain variants + exactly one `Unexpected` variant.** Domain variants are those that map to distinct HTTP status codes (`NotFound` → 404, `InvalidInput` → 400, `Unauthorized` → 401/403). Everything else — database, serialization, I/O, transactions — becomes `Unexpected` (→ 500).
4. **Convert errors explicitly at every layer boundary** with `.map_err(|report| match report.current_context() { … report.change_context(…) })`. Conversion is a deliberate, visible decision — never automatic.
5. **Add context with `.attach()`** (or `.attach_with(|| …)` when building the message is expensive). Every `.change_context(…::Unexpected)` should carry an attachment saying what the code was doing.
6. **Check invariants and authorization with `error_stack::ensure!`.**
7. **eyre / color-eyre live only in `main.rs`**, wrapping setup steps with `.wrap_err()`. Library and service code never returns `eyre::Result`.

## Why explicit conversion beats `#[from]`

`#[from]` makes error conversion invisible: any function that can produce an `sqlx::Error` can now silently become a `CoreError::DatabaseError` via `?`, from anywhere, without anyone deciding that this is the right classification. Consequences:

- Infrastructure types propagate upward unnoticed — the core layer ends up with a compile-time dependency on the database driver.
- New error cases added in a lower layer are absorbed by the blanket conversion instead of forcing the boundary code to decide how to classify them.
- Reading a function no longer tells you which errors it can actually surface.

Explicit `.map_err` + `match report.current_context()` at the boundary inverts all of this: adding a variant to a persistence enum breaks compilation at exactly the boundary that must decide its meaning in the layer above. Domain errors are promoted deliberately; everything else falls into the `_ => …Unexpected` arm. Nothing leaks by accident.

## Why `Report<E>` beats bare enums

A bare enum can only tell you *what* the final classification was. A `Report<E>`:

- carries the **entire chain of contexts** it passed through (persistence error → core error), each with its capture location;
- carries **attachments** — human-readable breadcrumbs (`"Failed to update user 42"`) added at each step;
- captures **backtraces** without needing `RUST_BACKTRACE` gymnastics;
- still exposes the typed current context via `.current_context()`, so matching stays exhaustive and compile-checked.

You lose nothing (the type is still there) and gain the full debugging story for the errors that matter most — the unexpected ones.

## End-to-end example

A complete example across all three layers, for an `update_user` operation.

```rust
// ============================================================================
// PERSISTENCE LAYER (src/persistence/user.rs)
// ============================================================================

use error_stack::Report;
use thiserror::Error;

// Persistence errors: domain-relevant variants extracted from the database,
// plus one catch-all for everything else.
#[derive(Debug, Error)]
pub enum PersistenceError {
    #[error("Invalid country code")]
    InvalidCountryCode,
    #[error("Invalid role")]
    InvalidRole,
    #[error("Database operation failed")]
    DatabaseError,
}

pub trait UserRepository {
    async fn update_user(
        &self,
        id: i64,
        data: UpdateData,
    ) -> Result<User, Report<PersistenceError>>;
}

impl UserRepository for PostgresRepository {
    async fn update_user(
        &self,
        id: i64,
        data: UpdateData,
    ) -> Result<User, Report<PersistenceError>> {
        sqlx::query!(/* ... */)
            .execute(&self.pool)
            .await
            .map_err(|error| match error {
                // Extract domain errors from DB constraint violations
                sqlx::Error::Database(ref db_err)
                    if db_err.constraint() == Some("user_country_code_fkey") =>
                {
                    Report::new(PersistenceError::InvalidCountryCode)
                }
                sqlx::Error::Database(ref db_err)
                    if db_err.constraint() == Some("user_role_fkey") =>
                {
                    Report::new(PersistenceError::InvalidRole)
                }
                // All other DB errors are infrastructure issues
                _ => Report::new(error).change_context(PersistenceError::DatabaseError),
            })
    }
}

// ============================================================================
// CORE LAYER (src/core/user.rs)
// ============================================================================

// Core errors: ONLY domain logic + ONE Unexpected variant
#[derive(Debug, Error)]
pub enum UpdateUserError {
    // Domain errors (map to specific HTTP codes)
    #[error("User with id {user_id} not found")]
    NotFound { user_id: i64 },
    #[error("Invalid country code")]
    InvalidCountryCode,
    #[error("Invalid role")]
    InvalidRole,
    #[error("Unauthorized")]
    Unauthorized,

    // ALL infrastructure errors wrapped here
    #[error("An unexpected error occurred")]
    Unexpected, // DB, serialization, transactions, file I/O, etc.
}

pub async fn update_user(
    repository: &impl UserRepository,
    id: i64,
    data: UpdateData,
    actor: Actor,
) -> Result<(), Report<UpdateUserError>> {
    // Authorization check
    error_stack::ensure!(
        actor.has_permission("user:update"),
        UpdateUserError::Unauthorized
    );

    // Check existence (domain error)
    let _existing = repository
        .get_user(id)
        .await
        .change_context(UpdateUserError::Unexpected)
        .attach_with(|| format!("Failed to fetch user {id}"))?
        .ok_or_else(|| Report::new(UpdateUserError::NotFound { user_id: id }))?;

    // Update operation — convert errors explicitly at the boundary
    repository
        .update_user(id, data)
        .await
        .map_err(|report| match report.current_context() {
            // Promote domain errors
            PersistenceError::InvalidCountryCode => {
                report.change_context(UpdateUserError::InvalidCountryCode)
            }
            PersistenceError::InvalidRole => {
                report.change_context(UpdateUserError::InvalidRole)
            }
            // Everything else → Unexpected
            _ => report
                .change_context(UpdateUserError::Unexpected)
                .attach_with(|| format!("Failed to update user {id}")),
        })?;

    Ok(())
}

// ============================================================================
// WEB LAYER (src/web/user.rs)
// ============================================================================

use poem_openapi::{ApiResponse, Object, OpenApi, param::Path, payload::Json};

#[derive(Debug, Object)]
pub struct ErrorBody {
    pub message: String,
}

// One ApiResponse enum covering success and error statuses
#[derive(Debug, ApiResponse)]
pub enum UpdateUserResponse {
    #[oai(status = 200)]
    Updated,
    #[oai(status = 400)]
    BadRequest(Json<ErrorBody>),
    #[oai(status = 401)]
    Unauthorized,
    #[oai(status = 404)]
    NotFound(Json<ErrorBody>),
    #[oai(status = 500)]
    InternalServerError,
}

pub struct UserApi {
    service: UserService,
}

#[OpenApi]
impl UserApi {
    #[oai(path = "/users/:id", method = "put")]
    async fn update_user(
        &self,
        Path(id): Path<i64>,
        Json(data): Json<UpdateRequest>,
        actor: AuthenticatedActor,
    ) -> UpdateUserResponse {
        match self.service.update_user(id, data.into(), actor.into()).await {
            Ok(_) => UpdateUserResponse::Updated,

            // Map core errors to HTTP responses
            Err(error) => match error.current_context() {
                core::UpdateUserError::NotFound { user_id } => {
                    UpdateUserResponse::NotFound(Json(ErrorBody {
                        message: format!("User {user_id} not found"),
                    }))
                }
                core::UpdateUserError::InvalidCountryCode
                | core::UpdateUserError::InvalidRole => {
                    UpdateUserResponse::BadRequest(Json(ErrorBody {
                        message: "Invalid input provided".into(),
                    }))
                }
                core::UpdateUserError::Unauthorized => UpdateUserResponse::Unauthorized,

                // Unexpected errors → 500, with the full error chain logged
                core::UpdateUserError::Unexpected => {
                    tracing::error!(?error, "Unexpected error updating user");
                    UpdateUserResponse::InternalServerError
                }
            },
        }
    }
}
```

Key takeaways:

1. **Persistence layer**: extract domain errors from DB constraints; wrap the rest in a generic persistence error.
2. **Core layer**: only domain variants + one `Unexpected` variant; explicit boundary conversion.
3. **Web layer**: match on `.current_context()` and map domain variants to HTTP statuses; log the full report only for `Unexpected`.
4. **All infrastructure concerns** (DB, serialization, I/O, transactions) end up in `Unexpected`.

## How to apply the pattern

### Dependencies

```toml
[dependencies]
thiserror = "2"
error-stack = "0.6"

# Binary crates only:
color-eyre = "0.6"
```

### Shape the error types

Domain variants + one `Unexpected` variant, per operation or per feature:

```rust
#[derive(Debug, Error)]
pub enum MyError {
    // Domain errors only
    #[error("Entity with id {id} not found")]
    NotFound { id: i64 },
    #[error("Invalid input provided")]
    InvalidInput,

    // Single catch-all for infrastructure
    #[error("An unexpected error occurred")]
    Unexpected,
}
```

Include relevant data in the variants (`{ id: i64 }`) — it improves both the `Display` message and the report.

### Function signatures

```rust
// Core and persistence layers
async fn my_function() -> Result<Data, Report<MyError>>
```

### Convert at layer boundaries

```rust
repository
    .get_data()
    .await
    .map_err(|report| match report.current_context() {
        RepoError::NotFound { id } => {
            report.change_context(ServiceError::NotFound { id: *id })
        }
        // All other errors (DB, serialization, ...) → Unexpected
        _ => report.change_context(ServiceError::Unexpected),
    })?
```

When there are no domain errors to promote, the conversion collapses to a single call:

```rust
repository
    .list_users(page)
    .await
    .change_context(ListUsersError::Unexpected)
    .attach_with(|| format!("Failed to list users page={}", page.number))?
```

### Match on errors

Always match on `.current_context()`, never on the `Report` itself:

```rust
match result {
    Ok(value) => /* ... */,
    Err(error) => match error.current_context() {
        MyError::NotFound { .. } => handle_not_found(),   // 404
        MyError::InvalidInput => handle_bad_request(),    // 400
        MyError::Unexpected => {
            tracing::error!(?error, "Unexpected error");
            handle_internal_error()                       // 500
        }
    },
}
```

### Invariants and authorization

```rust
error_stack::ensure!(
    actor.has_permission("user:update"),
    UpdateUserError::Unauthorized
);
```

Domain errors may also be created directly where they arise:

```rust
if !is_valid_input(&input) {
    return Err(Report::new(MyError::InvalidInput));
}
```

### main.rs: eyre at the top

The binary boundary is where dynamic error handling is appropriate. Install color-eyre, and wrap setup steps with `.wrap_err()`:

```rust
use color_eyre::eyre::{self, WrapErr};

#[tokio::main]
async fn main() -> eyre::Result<()> {
    color_eyre::install()?;

    let config = Config::load().wrap_err("Failed to load configuration")?;

    let pool = connect(&config.database_url)
        .await
        .wrap_err("Failed to connect to the database")?;

    serve(config, pool).await.wrap_err("Server exited with an error")
}
```

If a top-level call returns a `Report<E>`, convert it at this boundary (e.g. `.map_err(|report| eyre::eyre!("{report:?}"))`); do not let `eyre::Result` spread into the layers below.

### Logging

Log the full report — which includes the whole context chain — for unexpected errors; domain errors can be logged simply:

```rust
match error.current_context() {
    MyError::Unexpected => {
        // Full error chain helps debug infrastructure issues
        tracing::error!(?error, "Unexpected error occurred");
    }
    _ => {
        tracing::warn!("Domain error: {}", error);
    }
}
```

### Backtraces

Do not set `RUST_BACKTRACE=1` in scripts, containers, or CI. error-stack captures its own traces through `Report`; the global variable is redundant and its output is noisier than the report itself.

### Testing

Assert on `.current_context()`:

```rust
#[tokio::test]
async fn test_not_found() {
    let result = service.get_item(999).await;
    assert!(matches!(
        result.unwrap_err().current_context(),
        GetItemError::NotFound { id: 999 }
    ));
}
```

## Common patterns

### Option to Result with a domain error

```rust
repository
    .get(id)
    .await
    .change_context(MyError::Unexpected) // DB/network errors
    .and_then(|item| {
        item.ok_or_else(|| Report::new(MyError::NotFound { id })) // Domain error
    })
```

### Chaining operations

```rust
self.repository
    .list_items(page)
    .await
    .map(|items| items.into_iter().map(Item::from).collect())
    .change_context(ListItemsError::Unexpected)
    .attach_with(|| format!("Failed to list items: page={}, size={}", page.number, page.size))
```

### Transactions

Transaction errors are infrastructure errors:

```rust
self.repository
    .commit_transaction(transaction)
    .await
    .change_context(MyError::Unexpected)
    .attach("Failed to commit transaction")?;
```

## Do and don't

### Do

**Add meaningful context whenever wrapping into `Unexpected`:**

```rust
self.repository
    .get_user(id)
    .await
    .change_context(ServiceError::Unexpected)
    .attach_with(|| format!("Failed to fetch user {id}"))
```

**Include relevant data in error variants:**

```rust
#[error("User with id {user_id} not found")]
NotFound { user_id: i64 }
```

**Keep exactly one variant for all infrastructure errors:**

```rust
// ✅ Single variant for all unexpected errors
#[error("An unexpected error occurred")]
Unexpected

// ❌ Not: PersistenceError, SerializationError, TransactionError, ...
```

**Map domain errors to specific HTTP codes:**

```rust
match error.current_context() {
    MyError::NotFound { .. } => StatusCode::NOT_FOUND,        // 404
    MyError::InvalidInput => StatusCode::BAD_REQUEST,         // 400
    MyError::Unauthorized => StatusCode::UNAUTHORIZED,        // 401
    MyError::Unexpected => StatusCode::INTERNAL_SERVER_ERROR, // 500
}
```

### Don't

**Don't use `#[from]` or `#[source]` — ever:**

```rust
// ❌ Bad — infrastructure leaks and conversion becomes implicit
#[error("Database error")]
DatabaseError(#[from] sqlx::Error),

// ✅ Good — the enum is pure; error-stack carries the cause
#[error("An unexpected error occurred")]
Unexpected,
```

**Don't discard the error chain:**

```rust
// ❌ Bad — loses the underlying report
.map_err(|_| MyError::Unexpected)?

// ✅ Good — preserves the chain and adds context
.change_context(MyError::Unexpected)
.attach("During user validation")?
```

**Don't match on the `Report` itself:**

```rust
// ❌ Bad
match result {
    Err(report) if matches!(report, /* Report<...> patterns */) => { /* ... */ }
}

// ✅ Good
match result {
    Err(error) => match error.current_context() {
        MyError::NotFound { .. } => { /* ... */ }
        _ => { /* ... */ }
    },
}
```

**Don't create `Unexpected` reports out of thin air:**

```rust
// ❌ Bad — Unexpected should always wrap a real underlying failure
return Err(Report::new(MyError::Unexpected));

// ✅ Good — Unexpected comes from a wrapped infrastructure error
repository.operation()
    .await
    .change_context(MyError::Unexpected)
    .attach("During initialization")?;

// ✅ Also good — domain errors can be created directly
if !is_valid_input(&input) {
    return Err(Report::new(MyError::InvalidInput));
}
```

## When to use which crate

- **HTTP services and any layered library code**: thiserror enums + `Report<E>` as described here. Typed errors are required wherever a caller must distinguish error cases (HTTP mapping, retry decisions).
- **Binaries (`main.rs`), one-shot CLI tools, scripts**: eyre / color-eyre with `.wrap_err()`. When the only consumer of an error is a human reading the process output, dynamic errors are simpler and sufficient.
- **Never**: `anyhow::Result` / `eyre::Result` as the return type of library or service-layer functions.

## See also

- [reference.md](reference.md) — codestyle reference for the rest of the service.
- [guide.md](guide.md) — step-by-step guide to structuring a service.
- [minimal-service.md](minimal-service.md) — a complete minimal service using this pattern.
