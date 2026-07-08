# Minimal Rust service template

This document is the template for scaffolding a new Rust service. It defines the minimum structure every service starts from, so that services stay consistent, observable, and operationally ready. Copy the relevant template, rename the placeholder domain types (user, order, invoice, ...), and build from there.

## Table of contents

- [Core requirements](#core-requirements)
- [Minimal worker template](#minimal-worker-template)
- [Minimal API template](#minimal-api-template)
- [Configuration](#configuration)
- [Health endpoints](#health-endpoints)
- [Tracing](#tracing)
- [OpenAPI specification](#openapi-specification)
- [CORS configuration](#cors-configuration)
- [Cargo.toml conventions](#cargotoml-conventions)

## Core requirements

All Rust services (both background workers and APIs) must include:

1. **Error handling** - `eyre::Result<()>` in `main`, `color_eyre::install()` first, errors wrapped with `.wrap_err(...)`
2. **Tracing** - structured logging with `tracing` + `tracing-subscriber` (`EnvFilter` + `fmt`)
3. **CLI interface** - configuration via `clap`, with every option backed by an environment variable

Additional requirements for HTTP APIs:

4. **Health endpoints** - `/_health/liveness` and `/_health/readiness` probes
5. **`Spec` and `Server` subcommands** - `Spec` prints the OpenAPI spec, `Server` runs the service
6. **OpenAPI specification** - generated from endpoint definitions with `poem-openapi`
7. **CORS configuration** - configurable allowed origins
8. **Swagger UI** - interactive API documentation

## Minimal worker template

A background service that doesn't expose HTTP endpoints (e.g., schedulers, batch processors).

```rust
//! # My Worker
//!
//! Brief description of what this service does.

use clap::{Parser, Subcommand};
use eyre::Context;
use tracing::instrument;

#[derive(Debug, Parser)]
struct AppArgs {
    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Start the service
    Run(Box<ServiceConfig>),
}

#[derive(Debug, Parser)]
struct ServiceConfig {
    #[clap(long, env = "POD_NAME", default_value = "my-worker")]
    pod_name: String,
    // Add service-specific configuration here
}

#[tokio::main]
async fn main() -> eyre::Result<()> {
    color_eyre::install()?;

    match AppArgs::parse().command {
        Command::Run(config) => {
            run(*config).await?;
        }
    }

    Ok(())
}

#[instrument]
async fn run(config: ServiceConfig) -> eyre::Result<()> {
    init_tracing().wrap_err("Failed to set up tracing")?;

    // Service logic here
    tracing::info!("Service started");

    Ok(())
}

fn init_tracing() -> eyre::Result<()> {
    use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};

    tracing_subscriber::registry()
        .with(EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")))
        .with(tracing_subscriber::fmt::layer())
        .try_init()
        .wrap_err("Failed to initialize tracing subscriber")?;

    Ok(())
}
```

## Minimal API template

A web service that exposes HTTP endpoints with health checks, OpenAPI spec, and observability.

The `server` function follows a fixed order: init tracing → open connections → build services → build the `Route` → run the `Server`. The middleware order is also fixed: Swagger UI → nest API → health endpoints → shared data → CORS → trace layer → (optional) metrics.

```rust
//! # My API
//!
//! Brief description of what this API does.

use clap::{Args, Parser, Subcommand};
use eyre::Context;
use poem::{
    get, handler,
    http::{Method, StatusCode},
    listener::TcpListener,
    middleware::{Cors, Tracing},
    EndpointExt, Route, Server,
};
use poem_openapi::{OpenApi, OpenApiService};
use tracing::instrument;

#[derive(Debug, Parser)]
struct AppArgs {
    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    /// Dump OpenAPI specification to stdout
    Spec,
    /// Start the API server
    Server(Box<ServerConfig>),
}

#[derive(Debug, Parser)]
struct ServerConfig {
    #[clap(long, env = "HOST", default_value = "127.0.0.1")]
    host: String,
    #[clap(long, env = "PORT", default_value = "9000")]
    port: u16,
    #[clap(
        long,
        env = "CORS_ALLOWED_ORIGINS",
        default_value = "http://127.0.0.1:9000,http://localhost:9000",
        value_delimiter = ','
    )]
    cors_allowed_origins: Vec<String>,
    #[clap(long, env = "SWAGGER_UI_URL", default_value = "/swagger-ui")]
    swagger_ui_url: String,
    #[clap(flatten)]
    health: HealthConfig,
}

#[derive(Debug, Args)]
struct HealthConfig {
    #[clap(long, env = "HEALTH_LIVENESS_URL", default_value = "/_health/liveness")]
    liveness_url: String,
    #[clap(
        long,
        env = "HEALTH_READINESS_URL",
        default_value = "/_health/readiness"
    )]
    readiness_url: String,
}

#[tokio::main]
async fn main() -> eyre::Result<()> {
    color_eyre::install()?;

    // Only needed when the service makes or terminates TLS connections
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

#[derive(Debug, Clone, Copy)]
struct MyApi;

#[OpenApi]
impl MyApi {
    // Define your API endpoints here
}

fn api_service() -> OpenApiService<MyApi, ()> {
    OpenApiService::new(MyApi, env!("CARGO_PKG_NAME"), env!("CARGO_PKG_VERSION"))
}

#[instrument]
async fn server(config: ServerConfig) -> eyre::Result<()> {
    init_tracing().wrap_err("Failed to set up tracing")?;

    // Open connections here (database pools, HTTP clients, ...)
    // let db_pool = connect(&config).await.wrap_err("Could not connect to database")?;

    // Build services here (domain services that endpoints depend on)

    let api_service = api_service().server(format!("http://{}:{}", config.host, config.port));
    let swagger_ui = api_service.swagger_ui();

    let app = Route::new()
        .nest(&config.swagger_ui_url, swagger_ui)
        .nest("/", api_service)
        .at(&config.health.liveness_url, get(liveness))
        .at(&config.health.readiness_url, get(readiness))
        // .data(db_pool)
        .with(cors(&config))
        .with(Tracing);
    // Optional: metrics middleware (e.g. poem's OpenTelemetryMetrics) goes last

    Server::new(TcpListener::bind(format!(
        "{}:{}",
        config.host, config.port
    )))
    .run(app)
    .await
    .wrap_err("Could not run server")?;

    Ok(())
}

#[handler]
#[instrument]
async fn liveness() -> StatusCode {
    StatusCode::OK
}

#[handler]
#[instrument]
async fn readiness() -> StatusCode {
    // Add dependency health checks here if needed
    StatusCode::OK
}

fn cors(config: &ServerConfig) -> Cors {
    Cors::new()
        .allow_methods([Method::GET, Method::POST])
        .allow_origins(&config.cors_allowed_origins)
}

fn init_tracing() -> eyre::Result<()> {
    use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};

    tracing_subscriber::registry()
        .with(EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")))
        .with(tracing_subscriber::fmt::layer())
        .try_init()
        .wrap_err("Failed to initialize tracing subscriber")?;

    Ok(())
}
```

## Configuration

### Environment variables

All services support configuration via environment variables, declared on the `clap` structs:

```rust
#[derive(Debug, Parser)]
struct ServerConfig {
    #[clap(long, env = "HOST", default_value = "127.0.0.1")]
    host: String,
    #[clap(long, env = "PORT", default_value = "9000")]
    port: u16,
    // Service-specific config
}
```

### Secrets

Use the `secrecy` crate for sensitive values so they are redacted from `Debug` output and hidden from `--help`:

```rust
use secrecy::{ExposeSecret, SecretBox};

#[derive(Debug, Args)]
struct DbConfig {
    #[clap(long, env = "DATABASE_URL", hide_env_values = true)]
    database_url: SecretBox<str>,
}

// Access only when needed
let url = config.database_url.expose_secret();
```

## Health endpoints

### Liveness probe

Indicates the service is running. Always returns `200 OK` if the process is alive:

```rust
#[handler]
#[instrument]
async fn liveness() -> StatusCode {
    StatusCode::OK
}
```

Path: `/_health/liveness` (configurable via `HEALTH_LIVENESS_URL`)

### Readiness probe

Indicates the service is ready to accept requests. Check dependencies (database, upstream services) and return `503` when any of them fails:

```rust
use poem::web::Data;
use sqlx::PgPool;

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

Path: `/_health/readiness` (configurable via `HEALTH_READINESS_URL`)

## Tracing

### Tracing setup

Initialize a `tracing-subscriber` registry with an `EnvFilter` (driven by `RUST_LOG`, defaulting to `info`) and a `fmt` layer, before any other work in the server/run function:

```rust
fn init_tracing() -> eyre::Result<()> {
    use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};

    tracing_subscriber::registry()
        .with(EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")))
        .with(tracing_subscriber::fmt::layer())
        .try_init()
        .wrap_err("Failed to initialize tracing subscriber")?;

    Ok(())
}
```

For production deployments, add `.json()` to the `fmt` layer (requires the `json` feature of `tracing-subscriber`) or extend the registry with OpenTelemetry layers - the init function is the single place to do so.

### Instrumentation

Use `#[instrument]` on key functions, skipping non-`Debug` or noisy arguments:

```rust
#[instrument(skip(service))]
async fn get_order(
    Path(id): Path<String>,
    Data(service): Data<&OrderService>,
) -> Result<Response, Error> {
    tracing::info!("Fetching order");
    // Implementation
}
```

### HTTP middleware

Add poem's `Tracing` middleware so every request gets a span with method, path, and status:

```rust
use poem::middleware::Tracing;

let app = Route::new()
    .nest("/", api_service)
    .with(Tracing);
```

## OpenAPI specification

### Generate specification

Every API has a `Spec` command that prints the OpenAPI spec to stdout:

```rust
#[derive(Debug, Subcommand)]
enum Command {
    /// Dump OpenAPI specification to stdout
    Spec,
    /// Start the API server
    Server(Box<ServerConfig>),
}

#[tokio::main]
async fn main() -> eyre::Result<()> {
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

Usage:

```shell
cargo run --bin my-api -- spec > openapi.json
```

### Swagger UI

Serve the Swagger UI generated by `poem-openapi` (requires the `swagger-ui` feature) for interactive documentation:

```rust
let api_service = api_service().server(format!("http://{}:{}", config.host, config.port));
let swagger_ui = api_service.swagger_ui();

let app = Route::new()
    .nest(&config.swagger_ui_url, swagger_ui)
    .nest("/", api_service);
```

Path: `/swagger-ui` (configurable via `SWAGGER_UI_URL`). Consider disabling it in production via a CLI flag.

## CORS configuration

### Basic CORS setup

Configure CORS with allowed origins from the environment:

```rust
#[derive(Debug, Parser)]
struct ServerConfig {
    #[clap(
        long,
        env = "CORS_ALLOWED_ORIGINS",
        default_value = "http://127.0.0.1:9000,http://localhost:9000",
        value_delimiter = ','
    )]
    cors_allowed_origins: Vec<String>,
}

fn cors(config: &ServerConfig) -> Cors {
    Cors::new()
        .allow_methods([Method::GET, Method::POST])
        .allow_origins(&config.cors_allowed_origins)
}
```

### CORS with credentials

For APIs that use cookies or authentication:

```rust
fn cors(config: &ServerConfig) -> Cors {
    Cors::new()
        .allow_methods([Method::GET, Method::POST, Method::PUT, Method::DELETE])
        .allow_origins(&config.cors_allowed_origins)
        .allow_credentials(true)
}
```

### Public APIs

For public APIs, allow all origins (use with caution):

```rust
fn cors(_config: &ServerConfig) -> Cors {
    Cors::new()
        .allow_methods([Method::GET, Method::POST])
        .allow_origin("*")
}
```

## Cargo.toml conventions

Pin full three-component versions and enable features explicitly. In a workspace, hoist shared dependencies to `[workspace.dependencies]` in the root `Cargo.toml` and inherit them with `workspace = true`; single-crate projects declare them directly. Always inherit lints from the workspace. Check crates.io for current versions when scaffolding - the versions below are examples of the pinning style, not a lockfile.

Root `Cargo.toml` of a standalone workspace:

```toml
[workspace]
members = ["crates/*"]
resolver = "3"

[workspace.dependencies]
tokio = { version = "1.45.1", features = ["full"] }
clap = { version = "4.5.40", features = ["derive", "env"] }
poem = "3.1.10"
poem-openapi = { version = "5.1.14", features = ["swagger-ui"] }

[workspace.lints.clippy]
# Shared lint configuration - see lints.toml for the full recommended set
```

Service crate `Cargo.toml`:

```toml
[package]
name = "my-api"
version = "0.1.0"
edition = "2024"

[lints]
workspace = true

[dependencies]
tokio = { workspace = true }
clap = { workspace = true }
eyre = "0.6.12"
color-eyre = "0.6.5"
secrecy = "0.10.3"
tracing = "0.1.41"
tracing-subscriber = { version = "0.3.19", features = ["env-filter"] }

# For APIs only
poem = { workspace = true }
poem-openapi = { workspace = true }
rustls = "0.23.27"
```

## See also

- [Code style reference](./reference.md)
- [Guide](./guide.md)
- [Error handling](./error-handling.md)
- [Lint configuration](./lints.toml)
