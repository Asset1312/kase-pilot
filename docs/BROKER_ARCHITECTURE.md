# BROKER_ARCHITECTURE.md — `kase_pilot.broker` Package Design

> **Status:** Revised — implementation status aligned; REST contract pending
> **Last updated:** 2026-07-27
> **Scope:** Architecture and current implementation status.

---

## 1. Purpose

This document defines the architecture of the `kase_pilot.broker` package and
records which parts currently exist. It establishes module responsibilities,
dependency rules, and the public API surface so that every implementation
decision has a clear place to belong.

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
    ├── websocket.py  (planned; not present)
    └── models.py
```

Nine modules currently exist. `websocket.py` is planned for post-MVP. Each
module owns exactly one concern.

---

## 3. Module Responsibilities

---

### 3.1 `client.py` — The Central Transport Layer

**Responsibility**

`client.py` is the single point through which every implemented HTTP
interaction with the broker API passes. It currently owns base URL handling,
request assembly, an injectable transport callable, response decoding, and
conversion of transport and API errors into KASE Pilot exceptions. Timeout,
retry, and persistent-session policies are not yet implemented. Service modules
receive `BrokerClient` through constructor injection but remain stubs.

**Why it is the central component**

Without a shared client, every module would independently manage connections,
headers, and error handling. Changes to the API base URL, header format, or
timeout policy would require edits across the entire package. The central client
means that concern changes in exactly one place.

**What belongs in `client.py`**

- HTTP transport and resource cleanup
- Base URL handling
- Calling the injected auth provider to obtain an authentication contribution
  before each request
- **The sole authority over request assembly** — `BrokerClient` determines
  exactly where and how authentication artefacts are placed in the request
  (headers, body, query parameters). This is not delegated to any other
  component.
- Unified HTTP error handling — mapping broker HTTP errors to KASE Pilot
  exceptions from `core/exceptions.py`
- Request timeout and retry policy once their requirements are confirmed
- A single generic request method that service modules call

**What does NOT belong in `client.py`**

- Knowledge of any specific endpoint path or resource
- Business logic (parsing a portfolio, interpreting order status)
- Authentication credential management — that is `auth.py`
- Computing signatures or generating nonces — that belongs to `BrokerAuth`
- Mutating or modifying the contribution object — it reads it immutably
- Knowledge of which cryptographic algorithm was used — it only knows the
  output shape
- Security session lifecycle — that is `security.py`
- Domain model definitions — those belong in `models.py` once response schemas
  are confirmed
- WebSocket connections — that is `websocket.py`
- Any import of `auth.py` or `security.py`

**Constructor injection — eliminating the cycle**

`BrokerClient` never imports `auth.py`. Instead, it receives an auth provider
at construction time. The provider is a callable or a minimal object that
returns a broker-specific authentication contribution. `client.py` has no
knowledge of how that contribution is produced.

**The authentication boundary**

`BrokerClient` receives a complete contribution object from its auth provider —
not raw headers, not a mutable params dict. The contribution contains
broker-specific authentication artefacts as named, typed fields. `BrokerClient`
then maps these artefacts into the protocol-specific request representation.

The key separation:

- `BrokerAuth` knows how to **produce** authentication artefacts.
- `BrokerClient` knows how to **place** them in the request.
- Neither knows how to do the other's job.

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
injection or a future factory. Their API methods are currently stubs and do not
yet call the client. Once implemented, service modules call the generic request
method and never construct HTTP requests themselves.

**Public surface**

- `BrokerClient` class — the only public class in this module.

**Dependencies**

- `models.py` — the `JsonValue` response type
- `core/exceptions.py` — exception mapping

**Must NOT import**

- `auth.py`, `security.py`, or any service module

`client.py` imports only the broker-independent `JsonValue` alias from
`models.py`; it does not depend on any broker domain model. Mapping raw values
to future domain types remains a service-layer responsibility.

---

### 3.2 `auth.py` — Credential Management

**Responsibility**

`auth.py` is currently intentionally empty. Its planned responsibility is the
broker credential lifecycle, but implementation remains blocked until the REST
authentication contract is confirmed. The descriptions below define the
architectural boundary, not existing behaviour.

**`auth.py` does not import `client.py`**

`BrokerAuth` is constructed before `BrokerClient` and injected into it.
`auth.py` has no dependency on the transport layer in normal operation.

If the broker authentication process itself requires an HTTP call (token
exchange, login endpoint), that transport is supplied to the auth object from
outside — for example, a minimal transport callable passed in at construction.
`auth.py` does not import `client.py` to obtain it.

**Critical design rule — `BrokerAuth` does not assemble requests**

`BrokerAuth` receives only the information required to compute authentication
artefacts (for example, a signing input containing the credential and request
context). It does not assemble, modify, or mutate any transport structure. Its
sole responsibility is producing a broker-specific contribution object
containing the computed artefacts.

**What `BrokerAuth` does:**

- Reads the API key from configuration (or receives it via injection)
- Computes the authentication artefacts required by the broker
- Returns a typed object with named fields representing these artefacts
- Uses immutable data and pure computation where possible

**What `BrokerAuth` does NOT do:**

- Know where artefacts should be placed in the request (headers, body, etc.)
- Modify the request params, headers, or body
- Have any knowledge of HTTP, sessions, or transport
- Import `client.py` or depend on it in any way

**Interaction with `security.py`**

`auth.py` does not import `security.py`. The relationship is coordinative, not
hierarchical. When a service module determines that an operation requires an
elevated security session, it obtains a session token from `security.py`
independently. `auth.py` produces API-key-level credentials only.

**Authentication Contribution Type — Broker-Specific**

Each broker defines its own contribution type with explicitly typed fields
matching its authentication artefacts. Field names match the authentication
artefacts produced by the cryptographic algorithm, not transport placement
names. Transport placement mapping is exclusively the responsibility of
`BrokerClient`.

This type is broker-specific by design and internal — not exported from
`__init__.py`. If a second broker is introduced, it defines its own
contribution type in its own package. No shared contribution base type exists
for MVP — broker-specificity is explicit and type-checked.

**Public surface**

- None currently. `BrokerAuth` and its contribution type are planned, not
  implemented.

**Dependencies**

- None currently. Future dependencies cannot be fixed before the REST
  authentication contract is confirmed.

**Must NOT import**

- `client.py`, `security.py`, or any service module

**Visibility**

Internal to the `broker` package. Not exported from `__init__.py`. The
future application boundary (factory or composition root) will construct
`BrokerAuth` and inject it into `BrokerClient`; external callers will not need
to instantiate it directly.

---

### 3.3 `security.py` — Security Session Lifecycle

**Responsibility**

`security.py` is an infrastructure skeleton for a future elevated security
session lifecycle. Its `open`, `confirm`, `is_valid`, and `close` methods
currently raise `NotImplementedError`. The protocol and confirmation method
remain TBD pending API research.

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

- `SecuritySession` class — internal infrastructure skeleton with unimplemented
  lifecycle methods.

**Dependencies**

- A minimal transport callable injected at construction (same pattern as
  `auth.py`) — `security.py` does not import `client.py`
- Standard library only in the current skeleton

**Must NOT import**

- `client.py`, `auth.py`, or any service module

**Visibility**

Internal. Not exported from `__init__.py`.

---

### 3.4 `models.py` — JSON Types and Future Integration Models

**Responsibility**

`models.py` currently defines only `JsonScalar`, `JsonValue`, and `RawPayload`
type aliases for decoded JSON. No Freedom Broker domain models exist yet.
Domain models may be added only after their fields are verified against an
authoritative REST contract.

**Scope note**

Future integration models will reflect Freedom Broker's verified API structure.
They will not be declared broker-neutral prematurely. If a second broker is
introduced, shared abstractions may be extracted only when that need is
demonstrated.

**What belongs here**

- Broker-independent aliases for JSON-decoded values
- Future immutable response representations whose fields are confirmed
- Future enumerations only for confirmed fixed value sets

**What must never be placed here**

- HTTP logic of any kind
- Validation logic beyond type constraints
- Business rules
- References to `client.py`, `auth.py`, or any service module
- External library dependencies

**Are dataclasses preferable for MVP?**

For future domain models, `@dataclass(frozen=True)` remains the preferred
starting point once fields are confirmed:

- Immutability prevents accidental mutation of API response data.
- No external dependencies.
- `__repr__` and `__eq__` are generated automatically, aiding debugging and
  testing.
- Migration to a validation library is straightforward if requirements grow.

**Dependencies**

- Standard library only.
- No imports from any other `broker` module.

**Visibility**

No model types are currently exported from `__init__.py`. Any future exported
set must be enumerated explicitly to keep the public contract controlled.

---

### 3.5 `portfolio.py` — Portfolio Service

**Responsibility**

Intended to retrieve and structure portfolio data after commands and response
schemas are confirmed. The class currently stores an injected `BrokerClient`;
all service methods raise `NotImplementedError`.

**Why separate from other services**

Portfolio data has its own endpoint group, its own update cadence, and its own
domain concepts. Mixing it with market data or orders would make each harder to
test and evolve independently.

**Public surface**

- `PortfolioService` class — methods for positions, balances, and summary.

**Dependencies**

- `client.py` — all HTTP calls go through `BrokerClient`
- Future model and security-session dependencies remain blocked on the REST
  contract

---

### 3.6 `market.py` — Market Data Service

**Responsibility**

Intended to retrieve current and historical quotes. The class currently stores
an injected `BrokerClient`; both service methods raise `NotImplementedError`.

**Why separate**

Market data endpoints are read-only, often have different rate limits than
account endpoints, and may eventually be served via WebSocket. Isolating them
makes that future transition contained.

**Public surface**

- `MarketService` class — methods for current quotes and historical quotes.

**Dependencies**

- `client.py`
- Future model dependencies remain blocked on confirmed response schemas

---

### 3.7 `orders.py` — Orders and Trades Service

**Responsibility**

Intended to retrieve current orders, historical orders, and trade history. The
class currently stores an injected `BrokerClient`; all service methods raise
`NotImplementedError`. Write operations remain explicitly out of scope.

**Why separate**

Orders and trades represent account activity — distinct from static portfolio
state and from market-wide data. Separating them allows write operations to be
added later in one well-scoped module without touching portfolio or market
logic.

**Public surface**

- `OrdersService` class — methods for current orders, historical orders, trades.

**Dependencies**

- `client.py`
- Future model dependencies remain blocked on confirmed response schemas

---

### 3.8 `reports.py` — Reports Service

**Responsibility**

Intended to retrieve broker-generated reports if the API exposes them. The
class currently stores an injected `BrokerClient`; `get_reports` raises
`NotImplementedError`. Format and availability remain TBD.

**Why separate**

Reports are a distinct capability with their own endpoint group and potentially
different response formats (binary vs JSON). Isolating them avoids complicating
the other service modules.

**Public surface**

- `ReportsService` class — methods for available reports.

**Dependencies**

- `client.py`
- Future model dependencies remain blocked on confirmed response schemas

---

### 3.9 `websocket.py` — WebSocket Client

**Responsibility**

Planned to manage the WebSocket connection to the broker for real-time data
streams. The module and `BrokerWebSocket` class do not currently exist and
remain out of MVP scope.

**Why separated from REST**

WebSocket is a fundamentally different protocol with its own connection
lifecycle, heartbeat mechanism, and error model. Mixing it with `client.py`
would make both harder to reason about and test. REST can be used without any
WebSocket infrastructure being initialised.

**How it coexists with `client.py`**

If implemented, `websocket.py` and `client.py` will be parallel components and
will not import each other. Configuration and authentication dependencies
remain blocked on the unconfirmed WebSocket and REST contracts.

**Future features this module will own**

- Connection establishment and teardown
- Heartbeat / ping-pong management
- Stream subscription and unsubscription
- Reconnection with backoff
- Dispatching incoming messages to registered handlers

**Public surface**

- `BrokerWebSocket` class — deferred to post-MVP.

**Dependencies**

- Not fixed; the module does not exist and its protocol contract is
  unconfirmed.

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

No model types are currently exported.

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
__init__.py ──► client.py, portfolio.py, market.py, orders.py, reports.py

portfolio.py ──► client.py
market.py    ──► client.py
orders.py    ──► client.py
reports.py   ──► client.py

client.py ──► models.py (`JsonValue`)
client.py ──► core/exceptions.py

security.py ──► standard library only
auth.py     ──► no imports (intentionally empty)

websocket.py: planned; not present
```

**Reading the diagram**

- Arrows point from dependent to dependency.
- `models.py` has no dependencies within the `broker` package.
- Service classes store an injected `BrokerClient`, but their methods remain
  unimplemented.
- `BrokerClient` accepts an injected authentication provider callable without
  importing `auth.py`.
- `SecuritySession` accepts an injected transport but is not connected to the
  client or services.
- The current import graph is acyclic.

---

## 5. Import Rules

| Module | May import | Must NOT import |
|---|---|---|
| `models.py` | `stdlib` only | Anything from `broker` |
| `client.py` | `stdlib`, HTTP library, `models.JsonValue`, `core.exceptions` | `auth`, `security`, service modules |
| `auth.py` | Nothing currently | All package modules until the REST contract is confirmed |
| `security.py` | `stdlib` only | `client`, `auth`, service modules |
| `portfolio.py` | `client` | `auth`, `security`, other services |
| `market.py` | `client` | `auth`, `security`, other services |
| `orders.py` | `client` | `auth`, `security`, other services |
| `reports.py` | `client` | `auth`, `security`, other services |
| `websocket.py` | Planned; not present | — |
| `__init__.py` | `client` and the four service modules | Internal types |

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

Each module is assigned one concern. `client.py` owns HTTP transport.
`auth.py` is reserved for API-key credentials, `security.py` for an elevated
session lifecycle, and `models.py` for JSON types and future confirmed domain
models. The latter two lifecycle areas are not implemented.

### Separation of Concerns

Transport, identity, elevated sessions, domain data, and four service domains
are in separate modules. Changes in one area do not ripple into others.

### Dependency Inversion

Service modules depend on the stable public interface of `BrokerClient`, not on
a concrete HTTP library. When the HTTP implementation changes, service modules
do not change.

`BrokerClient` does not depend on `BrokerAuth` directly — it accepts an auth
provider callable. A future `BrokerAuth` may satisfy that interface after the
REST contract is confirmed.

Note: for MVP, no explicit `Protocol` class is introduced. The interface is
defined by convention — the callable or object shape that `BrokerClient`
expects. A formal `Protocol` can be introduced when a second auth strategy or
a second broker makes it necessary.

### Boundary Clarity — Production vs Assembly

A key architectural boundary separates the production of authentication
artefacts from their assembly into transport structures:

- A future `BrokerAuth` produces a contribution object containing named
  authentication artefacts.
- `BrokerClient` assembles requests by mapping these artefacts to
  protocol-specific locations.
- Neither component does the other's job. This boundary is enforced by the
  type system and the import rules.

This boundary exists for a single-broker MVP and is not over-abstracted. If a
second broker is introduced, the same pattern is repeated with broker-specific
contribution types, and a common interface is extracted only when demonstrated
to be needed.

### Low Coupling

No two service modules import each other. `client.py` does not import
`auth.py`. `auth.py` does not import `client.py`. `models.py` imports nothing
from the package. The dependency graph is shallow and acyclic.

The planned `BrokerAuth` and existing `BrokerClient` are decoupled at the
module level. No contribution type exists yet; their future relationship will
use injection at construction time. This allows:

- Independent testing of authentication logic without HTTP
- Independent testing of transport logic without cryptographic computation
- Changes to the cryptographic algorithm without affecting transport code
- Changes to the transport protocol without affecting authentication code

### High Cohesion

Everything inside `portfolio.py` is about portfolio data. Everything inside
`auth.py` is about credential management. Each module's contents belong
together and would change together for the same reasons.

---

## 7. Future Extensibility — Adding a Second Broker

For the MVP, `models.py` currently contains only JSON type aliases. Future
Freedom Broker integration models will not be declared broker-neutral.

If a second broker is introduced, broker-neutral domain models may be extracted
into a shared package such as `kase_pilot.domain` or `kase_pilot.broker_base`.
This extraction should not be performed before it is needed. Premature
abstraction adds complexity without demonstrated benefit.

When a second broker is added, its authentication types can be designed from
that broker's confirmed contract. There is no existing Tradernet contribution
type to generalise today.

If a generic handler that processes contributions without broker knowledge is
later required, a common protocol or base class can be introduced
retroactively without changing the existing types. This is a controlled,
non-speculative addition that preserves type safety.

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

## 8. Authentication Contribution Genericity Decision

**Decision:** Each broker defines its own contribution type with explicitly
typed fields matching its authentication artefacts. No shared generic container.

| Aspect | Broker-specific (Chosen) | Generic Container (Rejected) |
|---|---|---|
| Type safety | Field names checked at definition time | String keys checked at runtime |
| Correctness enforcement | Compiler prevents typos | Runtime `KeyError` possible |
| Adding a broker | New type with typed fields; no breaking changes | New string keys; no breaking changes |
| Multi-broker generic handling | Common interface added only if needed | Already generic by design |
| Cost per broker | One additional type (fixed cost) | String key conventions (ongoing maintenance) |
| Documentation | Field names self-document | String keys must be documented separately |

**Implementation rule:** The contribution type is broker-specific and internal
— not exported from `__init__.py`. Implementation details (dataclass,
NamedTuple, or other) are not specified at the architecture level. Field names
are determined by the verified authentication artefacts, not by this document.
No contribution type currently exists; this decision applies only after the
REST authentication contract is confirmed.

---

## 9. Open Architecture Questions

| # | Question | Impact |
|---|---|---|
| 1 | Does the broker API require a persistent session or stateless requests? | Affects `BrokerClient` session design |
| 2 | Are authentication headers per-request or per-session? | Affects `BrokerAuth` provider interface |
| 3 | Which endpoints require a security session? | Affects service modules — each must know its own requirements |
| 4 | Is WebSocket authenticated separately from REST? | Affects how `BrokerAuth` is injected into `websocket.py` |
| 5 | Do service modules share a rate limit quota, or is it per-endpoint? | Affects whether rate limiting belongs in `client.py` or per-service |
| 6 | Does obtaining a security session require an HTTP call? | Affects the injected transport interface in `security.py` |

---

## 10. Decision Record

| Date | Decision | Status |
|---|---|---|
| 2025-07-24 | Frozen dataclasses for future confirmed domain models | Accepted |
| 2025-07-24 | `BrokerClient` as central transport; all services depend on it | Accepted |
| 2025-07-24 | `BrokerAuth` produces typed artefacts, not headers or modified params | Accepted |
| 2025-07-24 | `BrokerClient` sole owner of request assembly and placement mapping | Accepted |
| 2025-07-24 | Authentication contributions are broker-specific typed objects, not generic containers | Accepted |
| 2025-07-24 | `BrokerAuth` never modifies transport structures | Accepted |
| 2025-07-24 | `BrokerClient` never computes authentication artefacts | Accepted |
| 2025-07-24 | `SecuritySession` reserved for elevated session lifecycle; currently a skeleton | Accepted |
| 2025-07-24 | No generic contribution base type for MVP | Accepted |
| 2025-07-24 | WebSocket layer out of MVP scope | Accepted |
