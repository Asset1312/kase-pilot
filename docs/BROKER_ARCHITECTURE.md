# BROKER_ARCHITECTURE.md — `kase_pilot.broker` Package Design

> **Status:** Approved — implementation baseline
> **Last updated:** 2025-07-24
> **Scope:** Architecture only. No implementation details.

---

## 1. Purpose

This document defines the architecture of the `kase_pilot.broker` package before
any code is written. It establishes module responsibilities, dependency rules,
and the public API surface so that every implementation decision has a clear
place to belong.

---

## 2. Package Overview

```
kase_pilot/
└── broker/
    ├── __init__.py
    ├── client.py
    ├── auth.py
    ├── security.py
    ├── portfolio.py
    ├── market.py
    ├── orders.py
    ├── reports.py
    ├── websocket.py
    └── models.py
```

Ten modules. Each owns exactly one concern. None owns more than one.

---

## 3. Module Responsibilities

---

### 3.1 `client.py` — The Central Transport Layer

**Responsibility**

`client.py` is the single point through which every HTTP interaction with the
broker API passes. It owns the transport: base URL, session lifecycle, header
assembly, timeout policy, retry policy, and the conversion of raw HTTP errors
into KASE Pilot exceptions. Every service module calls `client.py`; no other
module touches an HTTP library directly.

**Why it is the central component**

Without a shared client, every module would independently manage connections,
headers, and error handling. Changes to the API base URL, header format, or
timeout policy would require edits across the entire package. The central client
means that concern changes in exactly one place.

**What belongs in `client.py`**

- HTTP session management (creation, reuse, teardown)
- Base URL and timeout configuration, sourced from `core/config.py`
- Calling the injected auth provider to obtain headers before each request
- Unified HTTP error handling — mapping broker HTTP errors to KASE Pilot
  exceptions from `core/exceptions.py`
- Request timeout and retry policy
- A single generic request method that service modules call

**What does NOT belong in `client.py`**

- Knowledge of any specific endpoint path or resource
- Business logic (parsing a portfolio, interpreting order status)
- Authentication credential management — that is `auth.py`
- Security session lifecycle — that is `security.py`
- Data models — that is `models.py`
- WebSocket connections — that is `websocket.py`
- Any import of `auth.py` or `security.py`

**Constructor injection — eliminating the cycle**

`BrokerClient` never imports `auth.py`. Instead, it receives an auth provider
at construction time. The provider is a callable or a minimal object that
returns the headers required for the current request. `client.py` has no
knowledge of how those headers are produced.

Conceptually:

```
BrokerAuth (constructed externally)
    │
    │ injected as auth_provider at construction
    ▼
BrokerClient
```

This removes the `client → auth → client` cycle entirely. The composition of
`BrokerAuth` and `BrokerClient` happens at the application boundary, not inside
either module.

**How other modules use it**

Every service module (`portfolio.py`, `market.py`, `orders.py`, `reports.py`)
receives a fully constructed `BrokerClient` instance — through constructor
injection or a factory — and calls its generic request method with an endpoint
path and parameters. The service module never constructs requests itself.

**Public surface**

- `BrokerClient` class — the only public class in this module.

**Dependencies**

- `core/config.py` — base URL and timeout settings
- `core/exceptions.py` — exception mapping
- `core/logger.py` — request/response logging

**Must NOT import**

- `auth.py`, `security.py`, `models.py`, or any service module

Keeping `models.py` out of `client.py` preserves transport independence from
domain structure. Raw responses (dicts, bytes) are returned to the caller;
the service module maps them to domain types.

---

### 3.2 `auth.py` — Credential Management

**Responsibility**

`auth.py` owns the broker credential lifecycle: reading the API key from
configuration, producing the correct authorisation headers for each request, and
refreshing or replacing credentials if the verified broker authentication scheme
supports expiration and renewal.

**`auth.py` does not import `client.py`**

`BrokerAuth` is constructed before `BrokerClient` and injected into it.
`auth.py` has no dependency on the transport layer in normal operation.

If the broker authentication process itself requires an HTTP call (token
exchange, login endpoint), that transport is supplied to the auth object from
outside — for example, a minimal transport callable passed in at construction.
`auth.py` does not import `client.py` to obtain it.

**Interaction with `security.py`**

`auth.py` does not import `security.py`. The relationship is coordinative, not
hierarchical. When a service module determines that an operation requires an
elevated security session, it obtains a session token from `security.py`
independently and passes it alongside the standard headers. `auth.py` produces
API-key-level credentials only.

**Public surface**

- `BrokerAuth` class — produces auth headers; implements the provider interface
  that `BrokerClient` accepts.

**Dependencies**

- `core/config.py` — API key source
- `core/exceptions.py` — raises `AuthenticationError` on failure
- `core/logger.py` — logs authentication events, never credential values

**Must NOT import**

- `client.py`, `security.py`, or any service module

**Visibility**

Internal to the `broker` package. Not exported from `__init__.py`. The
application boundary (factory or composition root) constructs `BrokerAuth` and
injects it into `BrokerClient`; external callers never need to instantiate it
directly.

---

### 3.3 `security.py` — Security Session Lifecycle

**Responsibility**

`security.py` owns the lifecycle of an elevated security session: opening a
session, confirming it via the required method, tracking its validity, and
closing it. The confirmation method (SMS, web token, electronic digital
signature) is TBD pending API research.

`security.py` does not decide which business endpoints require an elevated
session. That knowledge belongs to the service module that calls the endpoint.
`security.py` only answers: "given that a session is needed, here is one."

**Why it should be isolated**

Security session behaviour is the most likely part of the integration to change
independently of the REST surface. Broker-side changes to confirmation methods
are confined to this one module.

**Future features this module will own**

- SMS code confirmation flow
- Web token confirmation flow
- Electronic digital signature confirmation flow
- Session lifetime tracking and renewal

**What this module will NOT own**

- Decisions about which endpoints require a security session — those belong to
  the service modules
- API key credential management — that belongs to `auth.py`

**Public surface**

- `SecuritySession` class — lifecycle management and confirmation methods.

**Dependencies**

- A minimal transport callable injected at construction (same pattern as
  `auth.py`) — `security.py` does not import `client.py`
- `core/exceptions.py` — raises `SecuritySessionError` on failure
- `core/logger.py`

**Must NOT import**

- `client.py`, `auth.py`, or any service module

**Visibility**

Internal. Not exported from `__init__.py`.

---

### 3.4 `models.py` — Freedom Broker Integration Models

**Responsibility**

`models.py` defines the data structures that represent Freedom Broker domain
concepts in the MVP: portfolio positions, cash balances, quotes, orders, trades,
and reports. It is the shared vocabulary of the entire `broker` package for
this integration.

**Scope note**

These models reflect Freedom Broker's API structure. They are not declared as
broker-neutral domain models. If a second broker is introduced in the future,
broker-neutral abstractions may be extracted into a shared package such as
`kase_pilot.domain` — but only when that need is demonstrated, not
speculatively.

**What belongs here**

- Immutable representations of API response data
- Domain types shared across service modules
- Enumerations for fixed value sets (order status, asset type, etc.)

**What must never be placed here**

- HTTP logic of any kind
- Validation logic beyond type constraints
- Business rules
- References to `client.py`, `auth.py`, or any service module
- External library dependencies

**Are dataclasses preferable for MVP?**

Yes. `@dataclass(frozen=True)` is the right choice:

- Immutability prevents accidental mutation of API response data.
- No external dependencies.
- `__repr__` and `__eq__` are generated automatically, aiding debugging and
  testing.
- Migration to a validation library is straightforward if requirements grow.

**Dependencies**

- Standard library only (`dataclasses`, `typing`, `enum`, `datetime`).
- No imports from any other `broker` module.

**Visibility**

Selected types exported from `__init__.py`. The exported set is enumerated
explicitly — not "all models" — to keep the public contract controlled.

---

### 3.5 `portfolio.py` — Portfolio Service

**Responsibility**

Retrieves and structures portfolio data: open positions, cash balances, and
portfolio summary. Translates raw client responses into `models.py` types.
Knows which of its endpoints require a security session; obtains one from
`security.py` when needed.

**Why separate from other services**

Portfolio data has its own endpoint group, its own update cadence, and its own
domain concepts. Mixing it with market data or orders would make each harder to
test and evolve independently.

**Public surface**

- `PortfolioService` class — methods for positions, balances, and summary.

**Dependencies**

- `client.py` — all HTTP calls go through `BrokerClient`
- Security-session provider — injected where required, not imported at module
  level (see general injection rule in Section 5)
- `models.py` — return types
- `core/exceptions.py`
- `core/logger.py`

---

### 3.6 `market.py` — Market Data Service

**Responsibility**

Retrieves current and historical quotes and any other market data the API
exposes. Does not read account state or place orders.

**Why separate**

Market data endpoints are read-only, often have different rate limits than
account endpoints, and may eventually be served via WebSocket. Isolating them
makes that future transition contained.

**Public surface**

- `MarketService` class — methods for current quotes and historical quotes.

**Dependencies**

- `client.py`
- `models.py`
- `core/exceptions.py`
- `core/logger.py`

---

### 3.7 `orders.py` — Orders and Trades Service

**Responsibility**

Retrieves current orders, historical orders, and trade history. In the MVP this
is entirely read-only. Write operations (create, modify, cancel) are explicitly
out of scope.

**Why separate**

Orders and trades represent account activity — distinct from static portfolio
state and from market-wide data. Separating them allows write operations to be
added later in one well-scoped module without touching portfolio or market
logic.

**Public surface**

- `OrdersService` class — methods for current orders, historical orders, trades.

**Dependencies**

- `client.py`
- `models.py`
- `core/exceptions.py`
- `core/logger.py`

---

### 3.8 `reports.py` — Reports Service

**Responsibility**

Retrieves broker-generated reports if the API exposes them. Format and
availability are TBD.

**Why separate**

Reports are a distinct capability with their own endpoint group and potentially
different response formats (binary vs JSON). Isolating them avoids complicating
the other service modules.

**Public surface**

- `ReportsService` class — methods for available reports.

**Dependencies**

- `client.py`
- `models.py`
- `core/exceptions.py`
- `core/logger.py`

---

### 3.9 `websocket.py` — WebSocket Client

**Responsibility**

Manages the WebSocket connection to the broker for real-time data streams. Not
implemented in the MVP — the REST layer is fully stabilised first.

**Why separated from REST**

WebSocket is a fundamentally different protocol with its own connection
lifecycle, heartbeat mechanism, and error model. Mixing it with `client.py`
would make both harder to reason about and test. REST can be used without any
WebSocket infrastructure being initialised.

**How it coexists with `client.py`**

`websocket.py` and `client.py` are parallel components. Neither imports the
other. They share configuration sourced from `core/config.py`. Both receive
auth headers from `auth.py` — `BrokerAuth` is injected into each independently.

**Future features this module will own**

- Connection establishment and teardown
- Heartbeat / ping-pong management
- Stream subscription and unsubscription
- Reconnection with backoff
- Dispatching incoming messages to registered handlers

**Public surface**

- `BrokerWebSocket` class — deferred to post-MVP.

**Dependencies**

- An auth provider callable or object injected at construction — `websocket.py`
  does not import `auth.py`. The same injection pattern as `client.py` applies.
- `models.py`
- `core/config.py`
- `core/exceptions.py`
- `core/logger.py`

**Must NOT import**

- `client.py`, `auth.py`, or any service module

---

### 3.10 `__init__.py` — Public API Gateway

**Responsibility**

Defines what the rest of KASE Pilot sees when it imports `kase_pilot.broker`.
Re-exports only the stable public surface; internal modules remain hidden.

**What is exported**

Services:
```
BrokerClient        from .client
PortfolioService    from .portfolio
MarketService       from .market
OrdersService       from .orders
ReportsService      from .reports
```

Selected models (enumerated explicitly):
```
Position, Balance, Quote, Order, Trade, Report   from .models
```

**What is NOT exported**

- `BrokerAuth` — internal; composed at the application boundary by a future
  factory or facade, not by external callers directly
- `SecuritySession` — internal implementation detail
- `BrokerWebSocket` — deferred to post-MVP
- Any private helper or intermediate type

**Composition note**

`__init__.py` does not construct any objects. A future factory or facade module
(outside the MVP scope) will own the composition of `BrokerAuth`,
`BrokerClient`, and the service instances. Until then, construction happens at
the application entry point.

---

## 4. Dependency Diagram

```
core/config.py   core/logger.py   core/exceptions.py
      │                │                  │
      └────────────────┴──────────────────┘
                       │
              ─────────┼──────────
             │                   │
          auth.py           security.py
             │                   │
             │  (injected)        │  (injected)
             └────────┬───────────┘
                      │
                 client.py
                      ▲
         ┌────────────┼────────────┬──────────────┐
         │            │            │               │
   portfolio.py  market.py   orders.py       reports.py
         │            │            │               │
         └────────────┴────────────┴───────────────┘
                      │
                  models.py
                (no upward imports)

websocket.py ──► models.py
             ──► core/*
             (auth provider injected at construction — no import of auth.py)
```

**Reading the diagram**

- Arrows point from dependent to dependency.
- `auth.py` and `security.py` are injected into `client.py` — neither is
  imported by `client.py` at module level.
- `models.py` has no dependencies within the `broker` package.
- `websocket.py` is parallel to `client.py`; neither imports the other.
- The graph is a true directed acyclic graph. No cycles are possible.

---

## 5. Import Rules

| Module | May import | Must NOT import |
|---|---|---|
| `models.py` | `stdlib` only | Anything from `broker` |
| `client.py` | `stdlib`, HTTP library, `core/*` | `auth`, `security`, `models`, `portfolio`, `market`, `orders`, `reports`, `websocket` |
| `auth.py` | `core/*` | `client`, `security`, `portfolio`, `market`, `orders`, `reports`, `websocket` |
| `security.py` | `core/*` | `client`, `auth`, `portfolio`, `market`, `orders`, `reports`, `websocket` |
| `portfolio.py` | `client`, `models`, `core/*` | `auth`, `security`*, `market`, `orders`, `reports`, `websocket` |
| `market.py` | `client`, `models`, `core/*` | `auth`, `security`, `portfolio`, `orders`, `reports`, `websocket` |
| `orders.py` | `client`, `models`, `core/*` | `auth`, `security`, `portfolio`, `market`, `reports`, `websocket` |
| `reports.py` | `client`, `models`, `core/*` | `auth`, `security`, `portfolio`, `market`, `orders`, `websocket` |
| `websocket.py` | `models`, `core/*` | `client`, `auth`, `portfolio`, `market`, `orders`, `reports` |
| `__init__.py` | Any `broker` module | — |

Any service module that requires an elevated session may receive a
security-session provider through constructor or method injection. Service
modules must not construct security sessions themselves. This applies equally
to `portfolio.py`, `orders.py`, `reports.py`, and any future account-level
service.

**Why these rules produce a DAG**

`client.py` does not import `auth.py` or `security.py`. `auth.py` does not
import `client.py` or `security.py`. `security.py` does not import `client.py`
or `auth.py`. Service modules never import each other. `models.py` imports
nothing from the package. There is no path from any module back to itself.

---

## 6. Design Principles

### Single Responsibility Principle

Each module owns one concern and one concern only. `client.py` owns HTTP
transport. `auth.py` owns API-key credentials. `security.py` owns elevated
session lifecycle. `models.py` owns data structures. No module has two reasons
to change.

### Separation of Concerns

Transport, identity, elevated sessions, domain data, and four service domains
are in separate modules. Changes in one area do not ripple into others.

### Dependency Inversion

Service modules depend on the stable public interface of `BrokerClient`, not on
a concrete HTTP library. When the HTTP implementation changes, service modules
do not change.

`BrokerClient` does not depend on `BrokerAuth` directly — it depends on an
auth provider interface that `BrokerAuth` satisfies. This is the correct
application of dependency inversion: the higher-level module (`BrokerClient`)
defines the shape it needs; the lower-level module (`BrokerAuth`) conforms to
it.

Note: for MVP, no explicit `Protocol` class is introduced. The interface is
defined by convention — the callable or object shape that `BrokerClient`
expects. A formal `Protocol` can be introduced when a second auth strategy or
a second broker makes it necessary.

### Low Coupling

No two service modules import each other. `client.py` does not import
`auth.py`. `auth.py` does not import `client.py`. `models.py` imports nothing
from the package. The dependency graph is shallow and acyclic.

### High Cohesion

Everything inside `portfolio.py` is about portfolio data. Everything inside
`auth.py` is about credential management. Each module's contents belong
together and would change together for the same reasons.

---

## 7. Future Extensibility — Adding a Second Broker

For the MVP, `models.py` contains Freedom Broker integration models. They are
not declared broker-neutral.

If a second broker is introduced, broker-neutral domain models may be extracted
into a shared package such as `kase_pilot.domain` or `kase_pilot.broker_base`.
This extraction should not be performed before it is needed. Premature
abstraction adds complexity without demonstrated benefit.

When the time comes:

1. Create a parallel package: `kase_pilot.broker_alpaca` or similar.
2. Extract shared model types into `kase_pilot.domain`.
3. Introduce formal `Protocol` classes for services if the calling layer needs
   to switch brokers at runtime.
4. The calling layer selects the broker package via configuration, with no
   changes to `core`, UI, or storage layers.

This path is open because broker-specific code is already isolated inside
`kase_pilot.broker` from the start.

---

## 8. Open Architecture Questions

| # | Question | Impact |
|---|---|---|
| 1 | Does the broker API require a persistent session or stateless requests? | Affects `BrokerClient` session design |
| 2 | Are authentication headers per-request or per-session? | Affects `BrokerAuth` provider interface |
| 3 | Which endpoints require a security session? | Affects service modules — each must know its own requirements |
| 4 | Is WebSocket authenticated separately from REST? | Affects how `BrokerAuth` is injected into `websocket.py` |
| 5 | Do service modules share a rate limit quota, or is it per-endpoint? | Affects whether rate limiting belongs in `client.py` or per-service |
| 6 | Does obtaining a security session require an HTTP call? | Affects the injected transport interface in `security.py` |