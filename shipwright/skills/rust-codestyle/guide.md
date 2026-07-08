# Rust codestyle guide

This document outlines code style conventions for Rust services. These guidelines ensure consistency, maintainability, and readability across a codebase.

## Introduction

Services are built on three core principles that guide every architectural and implementation decision:

### Core principles

**1. Observability-first design**

Every service is instrumented from the ground up for production visibility:

- Distributed tracing with `#[instrument]` on key functions
- Structured logging with field-based events
- Health endpoints (liveness/readiness) at every layer

**2. Explicit error handling with context**

Errors are treated as first-class citizens with rich context:

- Every operation returns typed `Result<T, Report<Error>>` using `error-stack`
- Error context flows through the stack with `.change_context()` and `.attach()`
- Each layer defines its own error types
- Pattern matching on `.current_context()` for precise error handling

**3. Clean architecture**

Services follow a layered (hexagonal) architecture with vertical-slice API operations:

- Persistence layer behind traits (data access)
- Core layer generic over those traits (business logic)
- API surface as vertical slices: one file per operation with DTOs, handler, and tests co-located
- Type aliases in `main.rs` wire concrete adapters into generic services

### Quality attributes

The codebase prioritizes three quality attributes:

**Observability** - Critical for debugging production issues in a distributed system. Every service provides comprehensive telemetry through tracing, metrics, and health checks.

**Resilience** - Services handle failures gracefully without cascading. Async-first design, comprehensive error handling, and graceful degradation ensure system stability.

**Maintainability** - Consistent structure across services enables team productivity. Clear separation of concerns, type-safe configuration, and standardized patterns make services easy to understand and modify.

## Project structure

There are two types of applications:

### APIs (web services)

API services expose HTTP endpoints and combine a layered core with a vertical-slice API surface:

```text
services/api-name/
├── Cargo.toml
├── src/
│   ├── main.rs                # Entry point: CLI args, server setup, type aliases
│   ├── features/              # Vertical slices: one file per API operation
│   │   ├── mod.rs             # Entity module declarations, shared DTO types
│   │   └── user/
│   │       ├── mod.rs         # Submodule declarations, shared constants
│   │       ├── create.rs      # POST /users
│   │       ├── get.rs         # GET /users/:id
│   │       ├── list.rs        # GET /users
│   │       ├── update.rs      # PUT /users/:id
│   │       └── delete.rs      # DELETE /users/:id
│   ├── adapter/               # Shared middleware, auth, web utilities
│   ├── core/                  # Business logic
│   │   ├── mod.rs
│   │   ├── user.rs
│   │   └── order.rs
│   └── persistence/           # Data access layer
│       ├── mod.rs
│       └── adapter/
│           ├── postgres.rs
│           └── opensearch.rs
```

**Architecture layers:**

1. **Feature layer** (`features/`): One self-contained file per API operation — request/response DTOs, error responses, the handler function, and its tests
2. **Adapter layer** (`adapter/`): Shared external-interface code (auth middleware, common web utilities)
3. **Core layer** (`core/`): Business logic and domain models, generic over persistence traits
4. **Persistence layer** (`persistence/`): Data access traits and their concrete adapter implementations

#### Vertical slices for API operations

Each API operation lives in its own file under `features/{entity}/{operation}.rs`. The file is self-contained: it declares the request and response DTOs, the error response enum, the handler, and the tests for that operation. This keeps everything you need to understand one endpoint in one place, and keeps files small.

Each operation file defines its own endpoint struct with a `#[OpenApi]` impl. `main.rs` combines them into one service via the tuple form of `OpenApiService::new`:

```rust
let api_service = OpenApiService::new(
    (
        features::user::create::CreateUserEndpoint,
        features::user::get::GetUserEndpoint,
        features::user::list::ListUsersEndpoint,
        features::order::create::CreateOrderEndpoint,
    ),
    "My API",
    env!("CARGO_PKG_VERSION"),
);
```

A complete operation file:

```rust
//! POST /users — create a new user.

use error_stack::Report;
use poem::web::Data;
use poem_openapi::{payload::Json, ApiResponse, Object, OpenApi};
use tracing::instrument;

#[derive(Debug, Clone, PartialEq, Eq, Object)]
pub(crate) struct CreateUserDto {
    pub(crate) name: String,
    pub(crate) email: String,
}

#[derive(Debug, ApiResponse)]
pub(crate) enum CreateUserResponse {
    /// The user was created
    #[oai(status = 201)]
    Created(Json<ApiUser>),
}

#[derive(Debug, thiserror::Error, ApiResponse)]
pub(crate) enum CreateUserError {
    /// The provided email address or role is invalid
    #[error("The provided email address or role is invalid")]
    #[oai(status = 400)]
    BadRequest,
    /// The active user is not allowed to perform this action
    #[error("The active user is not allowed to perform this action")]
    #[oai(status = 403)]
    Unauthorized,
    /// Something went wrong
    #[error("Something went wrong")]
    #[oai(status = 500)]
    InternalServerError,
}

#[derive(Debug, Clone, Copy)]
pub(crate) struct CreateUserEndpoint;

#[OpenApi(tag = "crate::ApiTags::User")]
impl CreateUserEndpoint {
    /// Create a user
    #[oai(path = "/users", method = "post", operation_id = "create_user")]
    #[instrument(skip(service))]
    pub(crate) async fn create_user(
        &self,
        Json(request): Json<CreateUserDto>,
        Data(service): Data<&crate::UserService>,
        user: AuthenticatedUser,
    ) -> Result<CreateUserResponse, CreateUserError> {
        match service.create_user(request.into(), user).await {
            Ok(created) => Ok(CreateUserResponse::Created(Json(created.into()))),
            Err(error) => Err(match error.current_context() {
                crate::core::user::CreateUserError::InvalidEmail
                | crate::core::user::CreateUserError::InvalidRole => {
                    CreateUserError::BadRequest
                }
                crate::core::user::CreateUserError::Unauthorized => {
                    CreateUserError::Unauthorized
                }
                _ => {
                    tracing::error!(?error, "Error creating user");
                    CreateUserError::InternalServerError
                }
            }),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Tests for this operation live here, next to the handler.
}
```

#### What goes where

| Location | Contains |
|---|---|
| `features/{entity}/{op}.rs` | Endpoint struct, request/response DTOs, error enum, handler, tests |
| `features/{entity}/mod.rs` | Submodule declarations, shared constants |
| `features/mod.rs` | Entity module declarations, shared DTO types (if reused across features) |
| `adapter/` | Auth middleware, shared web utilities |
| `core/` | Business logic services, domain models, core error types |
| `persistence/` | Repository traits, entities, adapter implementations |
| `main.rs` | CLI args, config, type aliases, `OpenApiService` wiring, `ApiTags` |

### Services (background workers)

Services are background workers, data processors, or daemons that don't necessarily expose HTTP APIs. Their structure is more flexible and organized based on their specific needs.

**Standard service structure:**

```text
services/service-name/
├── Cargo.toml
├── src/
│   ├── main.rs              # Entry point - calls lib function
│   └── ...                  # Modules organized by functionality
```

**Service with integration tests/benchmarks:**

```text
services/service-name/
├── Cargo.toml
├── src/
│   ├── lib.rs               # Library exports, including main function
│   ├── main.rs              # Calls lib::main() or lib::run_server()
│   └── ...                  # Internal modules
├── tests/
│   └── integration_test.rs  # Integration tests
└── benches/
    └── benchmark.rs         # Benchmarks
```

**When to use the lib.rs pattern:**

- Service has integration tests that need access to internal functions
- Service has benchmarks that need to call internal code
- Service needs to export functions for testing purposes

## Code organization

### Persistence traits and generic core services

Core services are generic over persistence traits. The trait lives in the persistence layer, the core service takes it as a type parameter, and `main.rs` picks the concrete adapter:

```rust
// persistence/mod.rs
#[cfg_attr(test, mockall::automock)]
pub(crate) trait UserRepository {
    async fn create(
        &self,
        data: NewUser,
        tx: &mut Transaction<'_>,
    ) -> Result<User, Report<UserRepositoryCreateError>>;
}

// core/user.rs
pub(crate) struct UserService<R> {
    repository: R,
}

impl<R: UserRepository> UserService<R> {
    pub(crate) async fn create_user(
        &self,
        data: NewUser,
        user: AuthenticatedUser,
    ) -> Result<User, Report<CreateUserError>> {
        // Business logic here
    }
}
```

### Type aliases

Define service type aliases at the top of `main.rs` to wire concrete adapters into the generic core services, and for better readability everywhere else:

```rust
type OrderService =
    core::order::OrderService<OpenSearch, OpenSearch, ReferenceService, PdfRenderServiceImpl>;

type UserService = core::user::UserService<Postgres, Postgres>;
```

Handlers and other consumers refer to `crate::UserService` instead of spelling out the generics.

## Naming conventions

### General rules

- **Types** (structs, enums, traits): `PascalCase`
- **Functions and methods**: `snake_case`
- **Constants**: `SCREAMING_SNAKE_CASE`
- **Modules**: `snake_case`
- **Type parameters**: Single uppercase letter or `PascalCase`

### Service-specific naming

- Services: `{Entity}Service` (e.g., `OrderService`, `UserService`)
- Endpoints: `{Operation}{Entity}Endpoint` (e.g., `CreateUserEndpoint`, `ListOrdersEndpoint`)
- Repositories: `{Entity}Repository` trait
- Errors: `{Operation}{Entity}Error` (e.g., `CreateUserError`, `ListOrdersError`)
- Response types: `{Operation}Response` (e.g., `CreateUserResponse`, `OrderByReferenceResponse`)
- API models: `Api{Entity}` (e.g., `ApiOrder`, `ApiUser`)

## Type definitions

### Visibility

Default to `pub(crate)`. Use it for internal API types and models that shouldn't be exposed outside the crate; reach for `pub` only when something genuinely needs to be consumed by another crate (e.g., a lib.rs exposing functions to integration tests):

```rust
pub(crate) struct ApiOrder {
    pub(crate) external_id: uuid::Uuid,
    pub(crate) title: String,
    pub(crate) description: Option<String>,
}
```

### Derive macros

Order derive macros consistently:

```rust
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
```

Common patterns:

- Data structures: `Debug, Clone, PartialEq, Eq`
- Serializable types: Add `Serialize, Deserialize`
- API types: Add `Object` (poem-openapi)
- Error types: Use `Error` from `thiserror`

### Struct field attributes

For API models, use attributes to control serialization:

```rust
#[derive(Debug, Serialize, Object)]
pub(crate) struct ApiOrder {
    pub(crate) title: String,
    #[oai(skip_serializing_if_is_none)]
    #[serde(skip_serializing_if = "Option::is_none")]
    pub(crate) description: Option<String>,
}
```

### Type conversions with o2o

Use the `o2o` crate for automatic type conversions between layers (core model → API model, persistence entity → core model):

```rust
#[derive(Debug, PartialEq, Eq, o2o::o2o)]
#[from_owned(crate::core::order::OrderData)]
pub(crate) struct ApiOrder {
    pub(crate) external_id: uuid::Uuid,
    #[map(~.into())]
    pub(crate) customer: ApiOrderCustomer,
    #[map(~.into_iter().map(|r| r.into()).collect())]
    pub(crate) line_items: Vec<ApiLineItem>,
}
```

## Error handling

See also the dedicated [error handling reference](./error-handling.md).

### Error handling crates

Use three error handling crates, each serving a specific purpose at different architectural layers:

| Crate                 | Purpose                                                               | Where used                               |
| --------------------- | --------------------------------------------------------------------- | ---------------------------------------- |
| `thiserror`           | Derive `Error` trait + `Display` on error types                       | All layers (persistence, core, adapter)  |
| `error-stack`         | Error propagation with `Report<T>`, `.change_context()`, `.attach()`  | Persistence and core layers              |
| `eyre` / `color-eyre` | Top-level `Result` type for server startup                            | `main.rs` only                           |

**Do not use `#[from]` or `#[source]` attributes** from `thiserror` for error wrapping. All error conversion is done explicitly through `error-stack`'s `.change_context()`. The `thiserror` derive is used for the `Error` trait and `Display` message only.

### Persistence layer errors

Persistence errors are simple `thiserror` unit structs or small enums. They serve as opaque markers -- the underlying external error (sqlx, reqwest, etc.) is preserved in the `error-stack` report chain but not exposed in the error type.

Return `Result<T, Report<PersistenceError>>` using `error-stack::Report`.

```rust
#[derive(Debug, Error)]
#[error("Failed to create order")]
pub(crate) struct CreateOrderError;

#[derive(Debug, Error)]
pub(crate) enum UserRepositoryCreateError {
    #[error("The email address is unsupported")]
    UnsupportedEmail,
    #[error("The user role is unsupported")]
    UnsupportedRole,
    #[error("An unexpected error occurred")]
    PersistenceError,
}
```

Wrap external errors using `.change_context()`:

```rust
entity
    .insert(&mut **transaction)
    .await
    .change_context(CreateOrderError)?;
```

Add context strings with `.attach()` or `.attach_with()`:

```rust
StoragePath::from_absolute_path(format!("/{path}"))
    .change_context(FileStorageError::InvalidPath)
    .attach_with(|| format!("Failed to parse path: {path}"))?;
```

### Core layer errors (all services)

Core errors are `thiserror` enums with business-meaningful variants. They return `Result<T, Report<CoreError>>` using `error-stack::Report`.

```rust
#[derive(Debug, Error)]
pub(crate) enum CreateUserError {
    #[error("The email address is invalid")]
    InvalidEmail,
    #[error("The user role is invalid")]
    InvalidRole,
    #[error("The user is not allowed to perform this action")]
    Unauthorized,
    #[error("Something went wrong")]
    Unexpected,
}
```

**Converting persistence errors to core errors** uses `.map_err()` with `.current_context()` matching and `.change_context()`:

```rust
self.repository
    .create(data, &mut tx)
    .await
    .map_err(|report| match report.current_context() {
        UserRepositoryCreateError::UnsupportedEmail => {
            report.change_context(CreateUserError::InvalidEmail)
        }
        UserRepositoryCreateError::UnsupportedRole => {
            report.change_context(CreateUserError::InvalidRole)
        }
        UserRepositoryCreateError::PersistenceError => {
            report.change_context(CreateUserError::Unexpected)
        }
    })?;
```

**Adding context** with `.attach()`:

```rust
self.repository
    .begin()
    .await
    .change_context(CreateUserError::Unexpected)
    .attach("Could not obtain transaction")?;
```

**Authorization checks** with `error_stack::ensure!()`:

```rust
error_stack::ensure!(
    user.has_permission(Permission::ManageUsers),
    CreateUserError::Unauthorized
);
```

### API error responses

API error response types are `thiserror` + `poem_openapi::ApiResponse` enums defined in the operation's feature file:

```rust
#[derive(Debug, thiserror::Error, ApiResponse)]
pub(crate) enum CreateUserError {
    /// Either the email address or user role is invalid
    #[error("Either the email address or user role is invalid")]
    #[oai(status = 400)]
    BadRequest,
    /// The active user is not allowed to perform this action
    #[error("The active user is not allowed to perform this action")]
    #[oai(status = 403)]
    Unauthorized,
    /// Something went wrong
    #[error("Something went wrong")]
    #[oai(status = 500)]
    InternalServerError,
}
```

**Important rules:**

- Each status code must map to exactly **one** error variant. Multiple variants with the same status code break downstream client code generation.
- ❌ BAD:

  ```rust
  BadRequestEmail,    // 400
  BadRequestRole,     // 400  ❌ Duplicate 400
  ```

- ✅ GOOD: Group related errors under one variant with a message covering both:

  ```rust
  /// Either the email address or user role is invalid
  BadRequest,         // 400
  ```

### Converting core errors to API errors (APIs only)

Convert core errors to API errors **inline in the handler** by matching on `error.current_context()`. Do not use `From` implementations -- `error_stack::Report<T>` requires inspecting `.current_context()` to determine the error variant.

```rust
#[oai(path = "/users", method = "post", operation_id = "create_user")]
#[instrument(skip(service))]
pub(crate) async fn create_user(
    &self,
    Json(request): Json<CreateUserDto>,
    Data(service): Data<&UserService>,
    user: AuthenticatedUser,
) -> Result<CreateUserResponse, CreateUserError> {
    match service.create_user(request.into(), user).await {
        Ok(_) => Ok(CreateUserResponse::Created),
        Err(error) => Err(match error.current_context() {
            crate::core::user::CreateUserError::InvalidEmail
            | crate::core::user::CreateUserError::InvalidRole => {
                CreateUserError::BadRequest
            }
            crate::core::user::CreateUserError::Unauthorized => {
                CreateUserError::Unauthorized
            }
            _ => {
                tracing::error!(?error, "Error creating user");
                CreateUserError::InternalServerError
            }
        }),
    }
}
```

### Error propagation

**In business logic (core/persistence):** Use `error-stack`'s `.change_context()` and `.attach()`:

```rust
self.repository
    .create(data, &mut tx)
    .await
    .change_context(CreateUserError::Unexpected)
    .attach("Failed to persist user")?;
```

**In server startup (`main.rs`):** Use `eyre`'s `.wrap_err()`:

```rust
let pool = PgPool::connect(config.database.database_url.expose_secret())
    .await
    .wrap_err("Could not create a database pool")?;
```

### Handling external error types (BoxError)

Some external crates (notably `tower`) use `Box<dyn Error + Send + Sync>` (aka `BoxError`) as their error type. This is incompatible with `Report::new()` and `.change_context()` because error-stack's `Context` trait requires `Sized`.

**Preferred: Push `Report<T>` into the utility layer.** Define a proper error type at the utility boundary and convert external errors internally, so consumers never see `BoxError`:

```rust
#[derive(Debug, Error)]
pub(crate) enum RequestError {
    #[error("Request failed")]
    Request,
    #[error("Request failed with status `{0}`")]
    Status(u16),
    #[error("Could not store file")]
    Store,
}

impl Service<Url> for RequestServiceImpl {
    type Response = reqwest::Response;
    type Error = Report<RequestError>;

    fn call(&mut self, url: Url) -> Self::Future {
        let client = self.client.clone();
        Box::pin(async move {
            client.get(url).send().await.change_context(RequestError::Request)
        })
    }
}
```

Also avoid middleware that changes the error type to `BoxError`. For example, use reqwest's built-in timeout instead of wrapping the service with `tower::timeout::Timeout`.

**Fallback:** If you cannot avoid `BoxError` inline, attach it as a string since `Report::new()` requires a `Sized` type:

```rust
service
    .call(request)
    .await
    .map_err(|e| Report::new(MyError::Variant).attach(e.to_string()))?;
```

### Error logging

Log errors at the API boundary when converting to HTTP error responses. Use `tracing::error!` with the `?` debug format as a structured field:

```rust
_ => {
    tracing::error!(?error, "Error creating user");
    CreateUserError::InternalServerError
}
```

### Background service errors

Background services (workers, data processors) follow the same layered error pattern but without API error responses. Errors propagate through a pipeline using hierarchical `.change_context()` chaining.

**Define pipeline-step error enums:**

```rust
#[derive(Debug, Error)]
pub(crate) enum ImportError {
    #[error("Failed to set up the import")]
    Prepare,
    #[error("Failed to download source data")]
    Download,
    #[error("Failed to transform records")]
    Transform,
    #[error("Could not store the resulting records")]
    Store,
    #[error("Failed to perform cleanup")]
    Cleanup,
}
```

**Chain errors through the pipeline:**

```rust
async fn import_inner(&self, req: &ImportRequest) -> Result<(), Report<ImportError>> {
    let ctx = self.setup(req).await.change_context(ImportError::Prepare)?;

    let batch = self
        .importer
        .download(ctx, req)
        .await
        .change_context(ImportError::Download)?;

    let batch = self
        .transform_records(batch)
        .await
        .change_context(ImportError::Transform)?;

    self.store_records(batch)
        .await
        .change_context(ImportError::Store)?;

    self.cleanup(req).await.change_context(ImportError::Cleanup)?;

    Ok(())
}
```

**Error recovery pattern** -- set status before propagating:

```rust
async fn import(&self, req: ImportRequest) -> Result<(), Report<ImportError>> {
    let result = self.import_inner(&req).await;
    if result.is_err() {
        let _ = self.update_status(&req, ImportStatus::Error).await;
    }
    result
}
```

If the background service also exposes an HTTP endpoint (e.g., to trigger a run), define an `ApiResponse` error enum for that endpoint and match on `error.current_context()` as in API services.

## Dependencies

### Version pinning

Pin the full version number:

```toml
[dependencies]
thiserror = "2.0.12"
error-stack = "0.6.0"
eyre = "0.6.15"
tracing = "0.1.40"
```

### Workspace dependencies

In a workspace, use workspace dependencies for common crates:

```toml
[dependencies]
poem = { workspace = true }
poem-openapi = { workspace = true, features = ["chrono", "url"] }
sqlx = { workspace = true, features = ["chrono", "uuid"] }
tokio = { workspace = true, features = ["full"] }
```

### Feature flags

Explicitly enable required features:

```toml
[dependencies.serde]
version = "1.0.219"
features = ["derive"]

[dependencies.sqlx]
workspace = true
features = ["postgres", "chrono", "uuid"]
```

## Documentation

### Comments

**Do not write inline comments in function bodies.** If something is worth noting at a point in the code, it is usually worth observing at runtime — emit a structured trace event instead:

```rust
// ❌ Bad
// Fall back to the default locale
let locale = requested.unwrap_or(DEFAULT_LOCALE);

// ✅ Good
let locale = requested.unwrap_or_else(|| {
    tracing::debug!(default = %DEFAULT_LOCALE, "Falling back to default locale");
    DEFAULT_LOCALE
});
```

Doc comments (`///` and `//!`) on public items are fine and encouraged — they document the interface, not the implementation.

### Module documentation

Add module-level doc comments (`//!`) at the top of main entry points (`main.rs`, `lib.rs`) and for modules that benefit from high-level explanation:

```rust
//! # Billing API
//!
//! The billing API is the main API for orders and invoices on the platform.
```

Not every module file needs documentation - use your judgment based on complexity and whether it aids understanding.

### Function documentation

Document **public API functions** and **complex internal functions** where the purpose isn't immediately obvious:

```rust
/// Fetch orders by reference
///
/// Returns the order matching the provided reference and language.
#[instrument(skip(order_service))]
pub(crate) async fn order_by_reference(
    &self,
    Path(language): Path<ApiLanguage>,
    Path(reference): Path<Reference>,
    Data(order_service): Data<&OrderService>,
) -> Result<OrderByReferenceResponse, OrderByReferenceError> {
    // Implementation
}
```

Simple helper functions and self-explanatory methods don't need doc comments.

### Type documentation

For **API types** (exposed via OpenAPI), document the type and its fields for generated documentation:

```rust
/// Order struct describing an order document.
#[derive(Debug, Serialize, Object)]
pub(crate) struct ApiOrder {
    /// The external ID of the order.
    pub(crate) external_id: uuid::Uuid,
    /// The title of the order.
    pub(crate) title: String,
    /// Discount data for the order.
    #[oai(skip_serializing_if_is_none)]
    pub(crate) discount: Option<ApiDiscount>,
}
```

For **internal types**, document when it adds clarity - not every struct needs documentation if the fields are self-explanatory.

## Testing

Run tests with [cargo-nextest](https://nexte.st/):

```shell
cargo nextest run
```

### Testing principles

**Test new features**: All new features must have tests that verify the expected behavior.

**Regression tests**: When fixing a bug, add a test that:

1. Would have caught the bug
2. Verifies the fix
3. Prevents the bug from reoccurring

**Unit testability**: Design functions to be testable at the unit level whenever possible.

### Designing for testability

Functions should be testable in isolation. Extract business logic from framework code.

**❌ Bad: Business logic buried in framework glue**

```rust
async fn handle_event(event: RawEvent) -> Result<(), Error> {
    let payload: OrderPlaced = serde_json::from_slice(&event.data)?;
    // Complex business logic here that can't be easily tested
    database.insert(payload).await?;
    Ok(())
}
```

**✅ Good: Testable business logic separated**

```rust
// Framework code - thin wrapper
async fn handle_event(event: RawEvent) -> Result<(), Error> {
    let payload: OrderPlaced = serde_json::from_slice(&event.data)?;
    process_order_placed(payload, &database).await
}

// Business logic - easily testable
async fn process_order_placed(order: OrderPlaced, db: &Database) -> Result<(), Error> {
    // Complex business logic here
    db.insert(order).await
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn it_should_process_a_placed_order() {
        // Test business logic without framework complexity
    }
}
```

### Test module structure

Place tests in a module at the bottom of the file:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn it_should_translate_field_correctly() {
        let field = translate_field(&langid!("nl-NL"), test_field).unwrap();
        assert_eq!(field, "expected");
    }
}
```

In the feature architecture, each operation's tests live inline in that operation's file, next to the DTOs and handler they exercise. The endpoint struct is callable directly:

```rust
CreateUserEndpoint
    .create_user(Json(body), Data(&user_service(pool)), admin_user())
    .await
    .expect("Failed to create user");
```

### Test naming

Use descriptive test names with `it_should_` prefix:

```rust
#[test]
fn it_should_prefer_the_provided_locale_if_present() {
    // Test implementation
}

#[test]
fn it_should_fallback_to_english_if_the_language_is_not_available() {
    // Test implementation
}

#[test]
fn it_should_handle_empty_input_without_panicking() {
    // Regression test for bug #123
    let result = process_empty_data();
    assert!(result.is_ok());
}
```

### Test macros

Use macros for repetitive test patterns:

```rust
macro_rules! test_translations {
    ( $( $name:ident ( $locale:expr, $field:expr ) -> $expected:expr ),* $(,)? ) => {
        $(
            #[test]
            fn $name() {
                let field = translate_field($locale, $field).unwrap();
                assert_eq!(field, $expected)
            }
        )*
    };
}

test_translations! {
    it_should_prefer_exact_locale(&langid!("nl-NL"), test_field) -> "Mijn waarde",
    it_should_use_same_language(&langid!("nl-BE"), test_field) -> "Andere waarde",
}
```

### Feature tests

When implementing a new feature, write tests that cover:

- Happy path
- Edge cases
- Error conditions

```rust
#[cfg(test)]
mod tests {
    use super::*;

    // Feature: User creation
    #[test]
    fn it_should_create_user_with_valid_data() {
        let user = create_user("John", "john@example.com").unwrap();
        assert_eq!(user.name, "John");
    }

    #[test]
    fn it_should_reject_invalid_email() {
        let result = create_user("John", "invalid-email");
        assert!(result.is_err());
    }

    #[test]
    fn it_should_handle_empty_name() {
        let result = create_user("", "john@example.com");
        assert!(result.is_err());
    }
}
```

### Assertions

For simple assertions, use standard `assert_eq!` and `assert!` macros. For more complex assertions, use `assert2` which provides better error messages and more expressive syntax.

**Install as dev dependency:**

```toml
[dev-dependencies]
assert2 = "0.3.16"
```

#### `assert2::check!` — value comparisons (soft-fail)

Use `check!` for value comparisons. It provides better error output than `assert_eq!` and is a soft assertion — the test continues after a failure, so you see all failing checks at once.

```rust
use assert2::check;

check!(items.contains(&"bar"));
check!(items.len() == 3);
check!(value > 0);
```

#### `assert2::assert!` — pattern matching (hard-fail)

Use `assert!(let pattern = expr)` for destructuring assertions. Fails immediately if the pattern doesn't match. This is the primary tool for pattern matching in tests.

Common pattern: `assert!` to destructure, then `check!` to verify fields on the extracted value.

```rust
use assert2::{assert, check};

// Option unwrap — extract the inner value
assert!(let Some(periods) = result.get(&1));
check!(periods.len() == 3);

// Nested Result-in-Option (e.g. stream items)
assert!(let Some(Ok(parsed)) = stream.next().await);

// Error branch
assert!(let Err(error) = response);

// Enum variant destructuring
assert!(let GetUserResponse::Ok(Json(content)) = result);
check!(content.profile.name == "Test User".to_string());

// Struct destructuring
assert!(let Some(Category { name, .. }) = misc_category);
check!(name == "Other");
```

> **Note:** When importing `assert2::assert`, it shadows the standard `assert!` macro. You can also use the fully qualified `assert2::assert!(let ...)` form to avoid shadowing.

#### When to use which

| Macro | Use case | Behavior |
|---|---|---|
| `assert_eq!(a, b)` | Simple equality | Hard-fail, standard library |
| `assert!(condition)` | Simple boolean | Hard-fail, standard library |
| `assert2::check!(expr)` | Value comparisons | Soft-fail, better error output |
| `assert2::assert!(let pat = expr)` | Pattern matching / destructuring | Hard-fail, extracts bindings |

### Mocking with mockall

Mock persistence traits in core-layer tests with `mockall`. Annotate the trait with `#[cfg_attr(test, mockall::automock)]` so the mock is only generated for test builds:

```rust
#[cfg_attr(test, mockall::automock)]
pub(crate) trait UserRepository {
    async fn find_by_id(&self, id: i32) -> Result<Option<User>, Report<FindUserError>>;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn it_should_return_not_found_for_missing_user() {
        let mut repository = MockUserRepository::new();
        repository
            .expect_find_by_id()
            .returning(|_| Ok(None));

        let service = UserService::new(repository);
        let result = service.get_user(42).await;

        assert2::assert!(let Err(error) = result);
        check!(matches!(error.current_context(), GetUserError::NotFound));
    }
}
```

**Install as dev dependency:**

```toml
[dev-dependencies]
mockall = "0.13.1"
```

### Database tests with sqlx

For tests that exercise real queries, use `#[sqlx::test]`. It provisions an isolated database per test, runs migrations, applies the named fixtures, and hands you a `PgPool`:

```rust
#[sqlx::test(fixtures("users", "orders"))]
async fn it_should_list_orders_for_a_user(pool: PgPool) {
    let repository = PostgresOrderRepository::new(pool);

    let orders = repository.list_for_user(1).await.unwrap();

    check!(orders.len() == 2);
}
```

Fixtures are SQL files in a `fixtures/` directory next to the test (e.g. `fixtures/users.sql`).

### Test coverage

Use `cargo-llvm-cov` to check test coverage with branch coverage enabled. While it's not mandatory to check coverage locally, it's available as a tool to identify untested code paths.

**Install:**

```shell
cargo binstall cargo-llvm-cov
```

**Run coverage:**

```shell
# Generate coverage report
cargo llvm-cov

# Generate HTML report
cargo llvm-cov --html

# With branch coverage
cargo llvm-cov --branch
```

Coverage is useful for:

- Identifying untested code paths
- Verifying feature test completeness
- Finding edge cases that lack coverage

Note: High coverage doesn't guarantee good tests, but low coverage often indicates missing tests.

## Web services (poem) - APIs only

The following patterns apply only to services that expose HTTP endpoints (APIs). Background services do not need these patterns. For a complete runnable example, see [minimal service](./minimal-service.md).

### Main entry point structure

```rust
#[derive(Debug, Parser)]
struct AppArgs {
    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Dump the openapi specification to stdout
    Spec,
    /// Start the application. Defaults to this
    Server(Box<ServerConfig>),
}

#[tokio::main]
async fn main() -> eyre::Result<()> {
    color_eyre::install()?;

    rustls::crypto::aws_lc_rs::default_provider()
        .install_default()
        .map_err(|_| eyre::eyre!("Failed to install default crypto provider"))?;

    match AppArgs::parse().command {
        #[expect(clippy::print_stdout)]
        Command::Spec => {
            println!("{}", api_service().spec());
        }
        Command::Server(config) => {
            server(*config).await?;
        }
    }

    Ok(())
}
```

### Configuration

Use `clap` for configuration with environment variable support, and `#[clap(flatten)]` to group related settings:

```rust
#[derive(Debug, Parser)]
struct ServerConfig {
    #[clap(long, env = "HOST", default_value = "127.0.0.1")]
    host: String,
    #[clap(long, env = "PORT", default_value = "9002")]
    port: u16,
    #[clap(flatten)]
    database: DbConfig,
}

#[derive(Debug, Args)]
struct DbConfig {
    #[clap(long, env = "DATABASE_URL", hide_env_values = true)]
    database_url: SecretBox<str>,
}
```

### Health endpoints

Implement standard health check endpoints. Liveness answers "is the process up", readiness answers "can it serve traffic" (dependencies reachable):

```rust
#[handler]
#[instrument]
async fn liveness() -> StatusCode {
    StatusCode::OK
}

#[handler]
#[instrument(skip(pool))]
async fn readiness(Data(pool): Data<&PgPool>) -> StatusCode {
    match sqlx::query("SELECT 1").execute(pool).await {
        Ok(_) => StatusCode::OK,
        Err(error) => {
            tracing::error!(?error, "Readiness check failed");
            StatusCode::SERVICE_UNAVAILABLE
        }
    }
}
```

### API endpoints

Define API endpoints using the `OpenApi` trait:

```rust
#[derive(Debug, Clone, Copy)]
pub(crate) struct OrderByReferenceEndpoint;

#[OpenApi(tag = "crate::ApiTags::Order")]
impl OrderByReferenceEndpoint {
    /// Fetch orders by reference
    #[oai(
        path = "/:language/orders/:reference",
        method = "get",
        operation_id = "orderByReference"
    )]
    #[instrument(skip(order_service))]
    pub(crate) async fn order_by_reference(
        &self,
        Path(language): Path<ApiLanguage>,
        Path(reference): Path<Reference>,
        Data(order_service): Data<&OrderService>,
    ) -> Result<OrderByReferenceResponse, OrderByReferenceError> {
        tracing::info!("Calling order by reference");

        let order = order_service
            .get_by_reference(language.into(), reference)
            .await;

        match order {
            Ok(order) => Ok(OrderByReferenceResponse::Ok(
                Json(order.into()),
                CACHE_INDEFINITE.to_string(),
            )),
            Err(error) => Err(match error.current_context() {
                GetOrderError::InvalidReference => {
                    OrderByReferenceError::InvalidReference
                }
                GetOrderError::NotFound => OrderByReferenceError::NotFound,
                _ => {
                    tracing::error!(?error, "Error fetching order");
                    OrderByReferenceError::InternalServerError
                }
            }),
        }
    }
}
```

### Server setup

```rust
#[instrument]
async fn server(config: ServerConfig) -> eyre::Result<()> {
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::from_default_env())
        .with(tracing_subscriber::fmt::layer())
        .try_init()
        .wrap_err("Failed to set up tracing")?;

    let api_service = api_service()
        .server(format!("http://{}:{}", config.host, config.port));

    let ui = api_service.swagger_ui();

    let app = Route::new()
        .nest("/docs", ui)
        .nest("/", api_service)
        .at("/health/live", get(liveness))
        .at("/health/ready", get(readiness))
        .data(order_service)
        .with(cors(&config))
        .with(Tracing);

    Server::new(TcpListener::bind(format!("{}:{}", config.host, config.port)))
        .run(app)
        .await
        .wrap_err("Could not run server")?;

    Ok(())
}
```

## CORS configuration (APIs only)

```rust
fn cors(config: &ServerConfig) -> Cors {
    Cors::new()
        .allow_methods([Method::GET, Method::POST])
        .allow_origins(&config.cors_allowed_origins)
        .allow_credentials(true)
}
```

## Linting and formatting

Use `rustfmt` for code formatting and `cargo clippy` for linting. Both are enforced locally during development and in CI. See [lints.toml](./lints.toml) for the recommended lint configuration.

### Formatting with rustfmt

Format your code before committing:

```shell
cargo fmt
```

Check formatting without applying changes:

```shell
cargo fmt --check
```

**Configuration**: Use tabs for indentation (specify `indent_style = tab` in `.editorconfig` and `hard_tabs = true` in `rustfmt.toml`). Import ordering and other formatting rules are handled automatically by `rustfmt`.

### Clippy

Run clippy over all targets before committing:

```shell
cargo clippy --all-targets
```

Use `#[expect(...)]` instead of `#[allow(...)]` for temporary overrides — `#[expect]` warns when the lint no longer fires, so stale overrides get cleaned up:

```rust
#[expect(clippy::print_stdout)]
Command::Spec => {
    println!("{}", api_service().spec());
}
```

### Services with integration tests and benchmarks

Some services need integration tests or benchmarks that require access to internal functions. These services use a `lib.rs` pattern.

#### Library structure

**lib.rs exports the main function:**

```rust
//! # Import Worker
//!
//! Service description here

// Re-export main function for binary
pub async fn run_server() -> eyre::Result<()> {
    // Main server logic here
    Ok(())
}

// Export internal functions for testing
pub mod workflow {
    pub use crate::internal_workflow::*;
}

// Internal modules
mod internal_workflow;
mod models;
```

**main.rs calls the library:**

```rust
#![allow(unused_crate_dependencies)]
#![allow(missing_docs)]

#[tokio::main]
async fn main() -> eyre::Result<()> {
    import_worker::run_server().await
}
```

#### Making functions public for testing

When functions need to be accessed by integration tests, make them `pub` in the library:

```rust
// In lib.rs
pub mod workflow {
    pub async fn process_batch(data: BatchData) -> Result<(), Error> {
        // Implementation
    }
}

// In tests/integration_test.rs
use import_worker::workflow::process_batch;

#[tokio::test]
async fn test_batch_processing() {
    let result = process_batch(test_data).await;
    assert!(result.is_ok());
}
```

#### Integration test structure

```rust
// tests/integration_test.rs
use import_worker::{workflow, models::BatchData};

#[tokio::test]
async fn test_complete_workflow() {
    // Test using exported functions
}
```

## Additional best practices

### Tracing

Use the `#[instrument]` macro on functions for automatic tracing. Skip arguments that are large, sensitive, or not `Debug` (injected services, pools, payloads):

```rust
#[instrument(skip(order_service))]
pub(crate) async fn order_by_reference(
    &self,
    Path(language): Path<ApiLanguage>,
    Path(reference): Path<Reference>,
    Data(order_service): Data<&OrderService>,
) -> Result<OrderByReferenceResponse, OrderByReferenceError> {
    tracing::info!("Calling order by reference");
    // Implementation
}
```

#### Structured fields in traces

**Always prefer to add trace values as structured fields rather than in the message string.** This makes logs queryable and enables better observability.

**❌ Bad: Values in message string**

```rust
tracing::info!("Processing user {} with status {}", user_id, status);
tracing::error!("Failed to connect to database at {}", db_url);
```

**✅ Good: Structured fields**

```rust
tracing::info!(user_id = %user_id, status = %status, "Processing user");
tracing::error!(db_url = %db_url, "Failed to connect to database");
```

**Using different field formats:**

```rust
// Display format (%)
tracing::info!(user_id = %user_id, "Processing user");

// Debug format (?)
tracing::debug!(request = ?request, "Received request");

// Direct value
tracing::info!(count = items.len(), "Processed items");

// Multiple fields
tracing::warn!(
    user_id = %user_id,
    attempt = retry_count,
    error = %err,
    "Retry attempt failed"
);
```

**Benefits of structured fields:**

- Queryable in log aggregation systems
- Type-safe and consistent
- Better performance (no string formatting unless needed)
- Easier to filter and analyze

### Secret management

Use the `secrecy` crate for sensitive data. Combined with `hide_env_values = true` in clap, secrets never appear in `--help` output, debug output, or logs:

```rust
use secrecy::{ExposeSecret, SecretBox};

#[derive(Debug, Args)]
struct DbConfig {
    #[clap(long, env = "DATABASE_URL", hide_env_values = true)]
    database_url: SecretBox<str>,
}

// Access the secret only when needed
let connection_string = config.database_url.expose_secret();
```

### Async/await

- Use `tokio` as the async runtime
- Prefer `async/await` over manual future handling
- Use `#[tokio::main]` for the main function

### Constants

Define constants for configuration strings and magic values:

```rust
const CACHE_INDEFINITE: &str = "public, max-age=31536000, immutable";
const DATE_FORMAT: &str = "%Y-%m-%dT%H:%M:%S%.9fZ";
```

### LazyLock for singletons

Use `LazyLock` for singleton instances:

```rust
use std::sync::LazyLock;

static METRIC_REGISTRY: LazyLock<Arc<Registry>> =
    LazyLock::new(|| Arc::new(Registry::new()));
```

## See also

- [Quick reference](./reference.md)
- [Minimal service walkthrough](./minimal-service.md)
- [Error handling reference](./error-handling.md)
- [Lint configuration](./lints.toml)
