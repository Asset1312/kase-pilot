# API_NOTES.md — Freedom Broker / Tradernet Integration

> **Status:** Draft — research in progress
> **Last updated:** 2025-07-24
> **Maintainer:** KASE Pilot team

---

## 1. Purpose

This document is the working technical map for integrating KASE Pilot with the
Freedom Broker / Tradernet API. It records verified facts, open questions,
architectural decisions, and a running research log.

The document is a living reference. Every claim marked **TBD** must be resolved
through official documentation, sandbox testing, or direct contact with the
broker before the corresponding feature is implemented.

---

## 2. References

- Official Tradernet API documentation portal —
  https://tradernet.ru/tradernet-api/
  *(Confirmed as official — normative source for documented capabilities)*
- Official API-key authentication page —
  https://tradernet.ru/tradernet-api/auth-api
- Tradernet Python SDK — https://pypi.org/project/tradernet-sdk/
  *(Confirmed as linked by the official Tradernet API portal; SDK behaviour is
  supporting evidence, not a normative wire-level contract)*
- Freedom24 mirror — https://freedom24.com/tradernet-api
  *(same content as above)*
- GitHub repository — https://github.com/tradernet/tn.api
  *(observed implementation evidence only; not a normative source unless a
  specific claim is also confirmed by the official portal)*
- Freedom Broker support correspondence — TBD

Evidence in this document is classified by source:

- **Normative official evidence** — statements published by the official
  Tradernet API portal.
- **Official SDK evidence** — behaviour implemented by the officially linked
  `tradernet-sdk`; useful supporting evidence, but not automatically a
  normative wire-level contract.
- **Observed live evidence** — behaviour captured during a dated, controlled
  request. It confirms that specific exchange only and is not generalized to
  other operations or future schema stability.
- **Project assumptions and decisions** — KASE Pilot design choices; these do
  not establish broker API behaviour.

---

## 3. Terminology

**Broker** — Freedom Broker / Tradernet.

**API** — The Tradernet API provided by Freedom Broker / Freedom24.

**Security Session** — Additional authorization required for selected
operations, separate from standard API key authentication.

**MVP** — The first production-ready read-only version of KASE Pilot.

---

## 4. Integration Principles

| # | Principle |
|---|-----------|
| 1 | **Read-only first.** The first version of the integration retrieves data only. No write operations are implemented. |
| 2 | **REST before WebSocket.** The REST layer is built and stabilised before any WebSocket streams are opened. |
| 3 | **FIX is out of scope.** The FIX protocol is not evaluated or implemented at any stage of MVP. |
| 4 | **Trading operations are postponed.** Order creation, modification, and cancellation are explicitly deferred to a future release. |
| 5 | **Validate before storage.** Every API response is validated against an expected schema before it is written to any persistent store. |
| 6 | **Secrets stay out of Git.** API keys, passwords, tokens, and any credentials are never committed to the repository in any form. |
| 7 | **Broker isolation.** All broker-specific code lives exclusively inside the `kase_pilot.broker` package. No broker logic leaks into core or UI layers. |
| 8 | **No undocumented behaviour.** The integration never relies on API behaviour that is not confirmed in official documentation. |

---

## 5. Official API Capabilities

> Normative source: https://tradernet.ru/tradernet-api/. The portal confirms
> that the capability categories below exist. It does not by itself confirm
> their wire-level commands, parameters, schemas, authentication requirements,
> or error contracts.

| Capability | Available | Notes |
|---|---|---|
| REST API | Confirmed | Existence confirmed by the official portal; canonical API base host remains unconfirmed |
| WebSocket streaming | Confirmed | Existence and documented subscription categories confirmed; protocol details and exact event names remain Partially Confirmed |
| API-key authentication | Confirmed | Authentication mode exists; request fields and signature algorithm remain unconfirmed |
| Login/password and SMS authentication | Confirmed | Authentication modes exist; their wire-level contracts are not recorded here |
| Security sessions | Confirmed | The portal documents listing and opening sessions; numeric types and expiry fields remain unconfirmed |
| Quotes and instruments | Confirmed | Current quote, instrument information, and historical candlestick operations exist |
| Portfolio, orders, and trades | Confirmed | Capability categories exist; operation-specific contracts remain unconfirmed |
| Reports and money movements | Confirmed | Capability categories exist; formats and operation-specific contracts remain unconfirmed |
| FIX protocol | TBD | Out of scope regardless |
| Sandbox / test environment | Partially Confirmed | Demo WebSocket server at wsbeta.tradernet.ru; REST sandbox TBD |
| API versioning scheme | TBD | — |
| Official Python SDK | Confirmed | `tradernet-sdk` exists on PyPI and is linked by the official portal; it is supporting rather than normative wire-level evidence |

---

## 6. KASE Pilot MVP Scope

The following capabilities are in scope for the first release. All are
**read-only**.

- Authentication using the safest supported method
- Current session or user information
- Portfolio summary
- Open positions
- Cash balances
- Current quotes
- Historical quotes
- Current orders
- Historical orders
- Trade history
- Broker reports (if the API exposes them)

---

## 7. Out-of-Scope Functionality

The following are explicitly excluded from MVP and must not be implemented:

- Order creation
- Order modification
- Order cancellation
- Stop Loss management
- Take Profit management
- Automated or algorithmic trading
- Portfolio rebalancing with execution
- FIX protocol integration

---

## 8. Authentication

### Method

The official portal confirms that API-key, login/password, and SMS
authentication modes exist. It does not provide enough normative evidence in
the reviewed material to fix a universal REST request-body or HTTP-header
authentication contract. See Research Log F-04 for the external README
description; see F-16 for the finding that REST and WebSocket signing must not
be assumed to share a protocol.

The officially linked Python SDK accepts a public/private key pair. The exact
REST credential identifiers, key provisioning process, and wire-level mapping
remain Partially Confirmed. See Research Log F-05 and F-06.

### REST Signature Algorithm (Partially Confirmed — README only; no code implementation exists)

Source: https://github.com/tradernet/tn.api README — Partially Confirmed
(official ownership of the repository is not yet proven)

The `sig` request body field is described as the MD5 hash of the concatenation
of all `parameter_name=parameter_value` pairs sorted alphabetically by parameter
name (applied recursively for nested parameters), with the `API_SECRET`
appended at the end of the string.

> ⚠️ **Accuracy note:** The README describes this as MD5 of sorted parameters
> with the secret appended. No working REST example exists in the repository
> that implements this algorithm — `tn-crypto.js` is used exclusively for
> WebSocket authentication in all example files. The live REST endpoint may
> use a different algorithm. Do not implement REST signing based on the README
> description alone. See Research Log F-16.

### WebSocket Signature Algorithm (Confirmed)

Source: `examples/tn-crypto.js`, https://github.com/tradernet/tn.api

The WebSocket `auth` event signature is computed using **HMAC-SHA256**:

- The message is the recursive `key=value` representation of the auth data
  object, with keys sorted alphabetically and pairs joined by `&`.
- The secret key is used as the HMAC key (passed to `crypto.createHmac`).
- The output is a hex-encoded string.

This is confirmed from reading the source of `examples/tn-crypto.js` directly.
The `sign` function calls `crypto.createHmac('sha256', key)` — this is true
HMAC-SHA256, not MD5 of any construction.

> ⚠️ **Protocol separation:** REST and WebSocket signing must be treated as
> separate protocols. The repository contains no evidence that `tn-crypto.js`
> is used or intended for REST. Do not introduce a shared generic signing
> abstraction that assumes both protocols use the same algorithm.

### Credential Identifiers (Partially Confirmed)

The repository README uses the terms `public_key`, `api_key`, and `apiKey`
interchangeably in different contexts. The relationship between:

- the `public_key` / `api_key` credential value;
- the `uid` REST request body field;
- the `apiKey` WebSocket auth field;

is not uniformly confirmed. The WebSocket `apiKey` field is confirmed to carry
the public key value — the `examples/auth.js` file explicitly assigns
`apiKey: pubKey` where `pubKey` holds the public key. The relationship between
the public key and the REST `uid` field remains **Unknown** — the README
describes `uid` as an integer type, which conflicts with the assumption that it
carries the public key string. Do not assume `uid` equals the public key until
a verified REST request example confirms it.

### HTTP Authentication Headers

Unknown. The external README describes `uid` and `sig` request-body fields, but
the official evidence reviewed does not establish that all REST authentication
is body-only or that authentication headers are never used.

### Open Questions

- Does the key pair expire? If so, what is the TTL and renewal process?
- Can key pair permissions be restricted to read-only operations?
- Is IP allowlisting mandatory or optional alongside key-based auth?
- What is the exact relationship between `public_key` and `uid` (REST)?
  The WebSocket `apiKey = public_key` mapping is confirmed. The REST `uid`
  mapping remains Unknown.
- Does the REST API return a specific HTTP status code (e.g. 401) on
  authentication failure, or always HTTP 200 with an error code in the body?
- Which specific read-only endpoints require an active security session?

---

## 9. Security Sessions

Security sessions are confirmed to exist by the official portal, which
documents listing open sessions and opening them through SMS, web-token, and
electronic-signature flows. Their exact relationship to API-key
authentication and individual REST operations remains unconfirmed.

Numeric session types described by the external repository README remain
Partially Confirmed rather than normative:

| `safety_type_id` | Type | Notes |
|---|---|---|
| 2 | Hardware token (Aladdin) | External README evidence only |
| 3 | SMS confirmation | External README evidence only; SMS flow existence is officially confirmed |
| 4 | Login/password without additional confirmation | External README evidence only |

The `expire_datetime` and `expire` response fields are described by external
evidence but are not confirmed as a normative official schema.

External implementation evidence describes API-key authentication as bypassing
the normal SMS/token flow. Whether this applies to current REST endpoints,
especially read-only operations, remains **Unknown**.

### Open Questions

- Which REST endpoints require a security session?
- Can a security session opened via the API key pair flow be used to authorise
  read-only requests, or only trading requests?
- Can a security session be refreshed without re-authentication?

---

## 10. REST API Overview

### Base URL (Partially Confirmed)

The official portal confirms REST API existence but does not establish a
single canonical API host in the evidence reviewed. The external repository
README describes:

https://tradernet.ru/api/

HTTP method: POST. GET is stated as permitted for testing only.
Data format: JSON.

> ⚠️ Treat the base host and method rules as Partially Confirmed until the
> official operation documentation establishes the canonical transport
> contract.

### Authentication in Requests

The external README describes authentication through request-body fields, but
the official evidence reviewed does not establish this as the universal REST
authentication contract. Header usage, per-request versus session
authentication, and the exact `uid`/`sig` mapping remain Unknown.

### Common Request Body Fields

| Field | Description | Required |
|---|---|---|
| `uid` | User identifier described by the external README; relationship to public key credential is Unknown — see §8 | Partially Confirmed for non-anonymous requests |
| `cmd` | Command name | Confirmed as an API concept; operation-specific value required |
| `params` | Command parameters | Requiredness and shape are operation-specific and not universally confirmed |
| `sig` | Signature described by the external README; algorithm unconfirmed — see §8 | Partially Confirmed |

### Pagination

TBD — pagination mechanism and parameters are not yet confirmed.

### Endpoint Index

| Resource | Method | Path | Notes |
|---|---|---|---|
| Session / user info | TBD | TBD | — |
| Portfolio information | TBD | TBD | Capability exists; separate summary, positions, and cash commands are not confirmed |
| Current quotes | TBD | TBD | Operation existence Confirmed; wire contract Unknown |
| Instrument information | POST (Confirmed observed) | `https://freedom24.com/api/getSecurityInfo` (Confirmed observed) | Official capability exists; one successful SDK 2.2.0 request observed, full normative contract Unknown |
| Historical candlesticks | TBD | TBD | Operation existence Confirmed; exact command `getQuotesHistory` remains Partially Confirmed |
| Current orders | TBD | TBD | Capability exists; wire contract Unknown |
| Historical orders | TBD | TBD | Capability exists; wire contract Unknown |
| Trade history | TBD | TBD | Capability exists; wire contract Unknown |
| Reports and money movements | TBD | TBD | Capabilities exist; wire contracts Unknown |

### First Read-only REST Use Case Readiness

No candidate operation is currently `READY`. Authentication remains blocked as
described in §8 and `AUTHENTICATION_READINESS.md`; the operation-specific
evidence below does not remove that shared blocker.

| Scenario | Candidate broker service | Command evidence | Parameter evidence | Successful response evidence | Authentication | Status | Missing evidence |
|---|---|---|---|---|---|---|---|
| Portfolio summary | `PortfolioService` | General portfolio-information operation exists; separate command unconfirmed | None | None | Blocked | `BLOCKED` | Separate command or confirmed mapping to the general operation, parameters, response sample and schema |
| Open positions | `PortfolioService` | General portfolio-information operation exists; separate command unconfirmed | None | None | Blocked | `BLOCKED` | Separate command or confirmed mapping to the general operation, parameters, response sample and schema |
| Cash balances | `PortfolioService` | General portfolio-information operation exists; separate command unconfirmed | None | None | Blocked | `BLOCKED` | Separate command or confirmed mapping to the general operation, parameters, response sample and schema |
| Current quote | `MarketService` | Operation existence Confirmed; exact command unconfirmed | None | None | Blocked | `BLOCKED` | Command, parameters, response sample and schema |
| Instrument information | Not assigned | `getSecurityInfo` endpoint Confirmed observed through SDK 2.2.0; normative command contract unconfirmed | `ticker` string and `sup: true` observed once; requiredness, accepted types/formats and `sup` requirement unconfirmed | HTTP 200 operation-specific top-level JSON observed; full sample and confirmed schema unavailable | API-key headers Confirmed observed for this request; algorithm, security-session requirement and general contract unconfirmed | `PARTIAL` | Normative command and parameter contract; authentication/security-session requirements; saved complete sample; confirmed schema; errors; schema stability |
| Historical quotes | `MarketService` | Historical candlestick operation exists; `getQuotesHistory` is Partially Confirmed | `ticker`, `interval`, `from`, `to` are Partially Confirmed; types, formats, timezone and limits Unknown | None | Blocked | `PARTIAL` | Parameter contract, response sample and operation-specific schema and errors |

Command and parameter strings used in transport unit tests are test inputs, not
evidence of the live REST API. Broker service stubs likewise define intended
package responsibilities, not API contracts. Manually invented fixtures do not
increase readiness. The common envelope handled by `BrokerClient` (§16) does not
confirm an operation-specific response schema from the live API.

An operation may be classified as `READY` only when all of the following are
available:

- confirmed command name;
- confirmed required parameters, types and formats;
- confirmed authentication and security-session requirements;
- a saved real successful response sample;
- confirmed response schema;
- confirmed operation-specific errors, or evidence that the common error
  contract applies;
- a safe, controlled verification method that cannot perform trading
  operations.

---

## 11. WebSocket Overview

> REST integration is completed first. WebSocket work begins only after the REST
> layer is stable.

### Protocol (Partially Confirmed — Conflicting Sources, see F-18)

The WebSocket layer uses **Socket.IO**, not a raw WebSocket protocol.
Source: https://github.com/tradernet/tn.api README

> ⚠️ **Conflicting source found 2026-07-31 (F-18):** the official portal
> page for `getSecuritySessions`
> (https://tradernet.global/tradernet-api/security-get-list) documents a
> plain `WebSocket` connection authenticated via a login-issued `SID`
> (cookie or request parameter), explicitly labelled "API V1" — not
> Socket.IO, not HMAC-signed. The two sources describe structurally
> different protocols. Do not implement WebSocket support against either
> description until this is resolved by a live, observed handshake. See
> Research Log F-18/F-19.

### WebSocket Servers (Partially Confirmed)

Production: https://ws.tradernet.ru
Demo: https://wsbeta.tradernet.ru


### Authentication Flow (Confirmed for algorithm; Partially Confirmed for structure)

After connecting, emit an `auth` Socket.IO event with:

data = { apiKey: <public_key>, cmd: 'getAuthInfo', nonce: <timestamp> }
sig = HMAC-SHA256(sorted key=value pairs joined by &, secret_key as HMAC key)
ws.emit('auth', data, sig, callback)


The assignment of `apiKey` to the public key value is **Confirmed** from
`examples/auth.js`. The signature algorithm is **Confirmed** as HMAC-SHA256
from `examples/tn-crypto.js` (see Research Log F-16).

WebSocket signing uses a separate component from REST signing. Do not
introduce a shared generic signing abstraction. When WebSocket support is
implemented it will require its own component that encapsulates HMAC-SHA256.

### Heartbeat / Ping-Pong

TBD — heartbeat interval and expected behaviour are not yet confirmed.

### Available Streams

The official portal previously confirmed only the subscription categories
below with event names as Partially Confirmed from external implementation
evidence. A live capture on 2026-07-31 (F-21) upgraded several of these and
found additional channels not previously recorded.

| Stream | Observed event name | Evidence status |
|---|---|---|
| Stock quotes (subscribe request) | `quotes` | **Confirmed** — live capture, F-21 |
| Stock quotes (push update) | `q` | **Confirmed** — live capture, F-20 |
| Market depth | `notifyOrderBook` / `b` | Category Confirmed; event names Partially Confirmed (not seen in F-20/F-21 capture) |
| Market status | `markets` | **Confirmed** — live capture, F-21 (previously recorded as `notifyMarkets`/`markets`) |
| Security sessions | `notifySessions` / `sessions` | Category Confirmed; event names Partially Confirmed (still not directly captured — see F-18/F-19 unresolved questions) |
| Portfolio updates | `portfolio` | **Confirmed** — live capture, F-21 |
| Calculated portfolio | `calculatedPortfolio` | **Confirmed, newly discovered** — live capture, F-21; not previously documented anywhere in this file |
| Orders updates | `orders` | **Confirmed** — live capture, F-21 |
| Counters (likely account/badge counters) | `counters` | **Confirmed, newly discovered** — live capture, F-21; payload was `[1901279]`, a numeric ID matching the account/session ID seen elsewhere in this session |
| Admin messages | `adminMessage` | **Confirmed, newly discovered** — live capture, F-21 |
| Price alerts | `alerts` | **Confirmed, newly discovered** — live capture, F-21 |
| SMS | `sms` | **Confirmed, newly discovered** — live capture, F-21 |

### Reconnection Policy

TBD

---

## 12. Portfolio Data

The official portal confirms a general portfolio-information operation and
portfolio change subscription. It does not confirm separate REST commands for
the project-level concepts below.

### Open Positions

- **Endpoint:** TBD
- **Method:** TBD
- **Parameters:** TBD
- **Response schema:** TBD

### Cash Balances

- **Endpoint:** TBD
- **Method:** TBD
- **Parameters:** TBD
- **Response schema:** TBD

### Portfolio Summary

- **Endpoint:** TBD
- **Method:** TBD
- **Parameters:** TBD
- **Response schema:** TBD

---

## 13. Quotes and Market Data

### Current Quotes

- **Availability:** Confirmed as an operation category
- **Endpoint/command:** TBD
- **Method:** TBD
- **Parameters:** TBD
- **Response schema:** TBD

### Instrument Information

- **Availability:** Confirmed as an operation category
- **Endpoint/command:** `https://freedom24.com/api/getSecurityInfo`
  (Confirmed observed through `tradernet-sdk` 2.2.0; normative contract
  unconfirmed)
- **Method:** POST (Confirmed observed for one controlled request)
- **Observed request body:** `{"ticker":"AAPL.US","sup":true}`
- **Observed authentication headers:** `X-NtApi-PublicKey`,
  `X-NtApi-Timestamp`, and `X-NtApi-Sig` were present
- **Observed result:** HTTP 200 with an operation-specific top-level JSON
  object; no universal `code`/`data`/`errMsg` envelope was present
- **Observed response fields:** `id`, `nt_ticker`, `short_name`,
  `default_ticker`, `code_nm`, `currency`, `min_step`, `lot`, `mkt_name`,
  `firstDate`, and nested `mrkt`
- **Observed field types:** `min_step` and `lot` were strings; `mrkt` was an
  object
- **Unknown:** signature algorithm and canonicalization, timestamp tolerance,
  complete response schema, whether `sup` is required, error contract, schema
  stability, and authentication/security-session requirements outside this
  exact request

### Historical Quotes

- **Availability:** Historical candlestick operation officially Confirmed
- **Endpoint/command:** `getQuotesHistory` Partially Confirmed
- **Method:** Partially Confirmed
- **Parameters:** `ticker`, `interval`, `from`, `to` (Partially Confirmed)
- **Parameter types/formats, timezone and limits:** Unknown
- **Response schema:** Unknown and operation-specific
- **Operation-specific errors:** Unknown

---

## 14. Orders and Trades

The official portal confirms current and historical orders and trade-history
capability categories. Their wire-level contracts remain Unknown.

### Current Orders

- **Endpoint:** TBD
- **Method:** TBD
- **Parameters:** TBD
- **Response schema:** TBD

### Historical Orders

- **Endpoint:** TBD
- **Method:** TBD
- **Parameters:** TBD
- **Response schema:** TBD

### Trade History

- **Endpoint:** TBD
- **Method:** TBD
- **Parameters:** TBD
- **Response schema:** TBD

---

## 15. Reports

- **Available:** Confirmed — broker and depository reports and money-movement
  operations are documented as capability categories
- **Endpoint/command:** Unknown
- **Formats:** Unknown
- **Parameters:** Unknown
- **Response and error schemas:** Unknown and operation-specific

---

## 16. Response Formats

Source: https://github.com/tradernet/tn.api README

The external README describes the following observed fields. The official
portal evidence reviewed does not establish them as a universal response
envelope, and individual operations may return operation-specific schemas.

| Field | Observed description | Universal requirement |
|---|---|---|
| `code` | Integer application status code | Not officially confirmed |
| `data` | Response payload (type varies by command) | Not officially confirmed |
| `errMsg` | Error message string | Not officially confirmed |

Field naming convention (snake_case vs camelCase) varies by endpoint.
Full conventions are not yet confirmed.

Date/time format: not yet confirmed.

Every operation requires its own confirmed successful response schema and
error contract. The transport-level `BrokerClient` envelope validation is a
project implementation decision and is not evidence of a universal live API
schema.

The controlled `getSecurityInfo` request recorded in Research Log F-17 returned
an operation-specific top-level JSON object without the universal
`code`/`data`/`errMsg` envelope. This is observed live evidence for that
successful request only, not proof that every operation or error response has
the same shape.

---

## 17. Error Handling

### Exception Mapping

Every API error is mapped to a KASE Pilot exception before it propagates beyond
the `kase_pilot.broker` package.

| Condition | KASE Pilot Exception |
|---|---|
| Authentication failure | `AuthenticationError` |
| Invalid or expired security session | `SecuritySessionError` |
| General API request failure | `ApiRequestError` |
| Rate limit exceeded | `RateLimitError` |
| Invalid or unexpected response data | `ValidationError` |

### Broker Error Codes (Partially Confirmed)

Source: https://github.com/tradernet/tn.api README

| Code | Name | Description |
|---|---|---|
| 0 | `ERROR_OK` | Success |
| 1 | `ERROR_INCORRECT_QUERY` | Malformed request or unknown command |
| 2 | `ERROR_BAD_JSON` | Invalid JSON |
| 3 | `ERROR_UNKNOWN_CMD` | Unknown command |
| 4 | `ERROR_BAD_SIGN` | Invalid signature |
| 7 | `ERROR_UNKNOWN_UID` | Unknown user ID |
| 8 | `ERROR_UNKNOWN_IP` | IP not allowlisted |
| 12 | `ERROR_ACCESS_DENIED` | Access denied / authorisation error |
| 14 | `ERROR_BAD_CODE` | Invalid confirmation code |

HTTP status code returned alongside application error codes: **Unknown**.

### Retry Policy

TBD — which application error codes are considered transient and safe to retry?

---

## 18. Rate Limits

| Dimension | Limit | Notes |
|---|---|---|
| Requests per second | TBD | — |
| Requests per minute | TBD | — |
| Requests per day | TBD | — |
| WebSocket messages per second | TBD | — |
| Penalty / backoff policy | TBD | — |

---

## 19. Logging and Secrets Policy

### Permitted in Logs

- Endpoint paths (without query parameters containing credentials)
- HTTP status codes
- Sanitised error messages
- Request timestamps and latency

### Forbidden in Logs

The following must **never** appear in any log output, at any log level:

- API keys (public or secret)
- Passwords
- SMS codes
- Session tokens
- Authorization headers or their values
- Signature values
- Any sensitive account data (account numbers, personal identifiers)

Logging inside the `kase_pilot.broker` package must be reviewed against this
list before every commit.

---

## 20. Data Storage Policy

- API responses are validated before any data is written to storage.
- Raw API responses are not persisted unless explicitly required for debugging
  in a non-production environment.
- Credentials and tokens are never written to the database or log files.
- Storage schema decisions will be documented separately when the storage layer
  is designed.

---

## 21. Open Questions

| # | Question | Priority | Status |
|---|---|---|---|
| 1 | Is the GitHub repository https://github.com/tradernet/tn.api officially maintained by Freedom Broker / Tradernet? | Critical | Open |
| 2 | What is the exact relationship between `public_key` and `uid` (REST)? WebSocket `apiKey = public_key` is Confirmed (F-16). REST `uid` mapping remains Unknown. | Critical | Open |
| 3 | What is the live REST signature algorithm? README describes MD5-with-concatenated-secret, but no REST code implementation exists in the repository. Repository evidence is insufficient to confirm the live algorithm. | Critical | Open |
| 4 | Does the key pair expire? If so, what is the TTL and renewal process? | High | Open |
| 5 | Can key pair permissions be restricted to read-only operations? | High | Open |
| 6 | Is IP allowlisting mandatory or optional for key-based authentication? | High | Open |
| 7 | Which specific REST endpoints require a security session? | High | Open |
| 8 | Does the REST API return HTTP 401 on authentication failure, or always HTTP 200 with an error code? | High | Open |
| 9 | What is the exact algorithm in `tn-crypto.js` for the WebSocket signature? | High | Resolved — HMAC-SHA256 (see F-16) |
| 10 | What is the exact rate limit policy? | High | Open |
| 11 | Is there a REST sandbox or test environment? | Medium | Open |
| 12 | What is the official ownership status of the `tradernet-sdk` PyPI package? | Medium | Open |
| 13 | What date/time format does the API use in responses? | Medium | Open |
| 14 | What is the WebSocket heartbeat interval and reconnection policy? | Medium | Open |
| 15 | Are broker reports available via the REST API? | Medium | Open |
| 16 | Is API versioning used? If so, in the URL path or in headers? | Medium | Open |

---

## 22. Architectural Decisions

| ID | Decision | Rationale |
|---|---|---|
| AD-001 | All broker code is isolated in `kase_pilot.broker`. | Prevents broker-specific logic from leaking into core modules; simplifies future broker swaps. |
| AD-002 | REST is integrated before WebSocket. | REST is simpler to test and debug; WebSocket is added only after the data model is stable. |
| AD-003 | Every API error is mapped to a KASE Pilot exception at the broker boundary. | Callers outside `kase_pilot.broker` never handle raw broker errors; the exception hierarchy is the public contract. |
| AD-004 | Responses are validated before storage. | Prevents corrupted or unexpected data from reaching the database. |
| AD-005 | FIX protocol is out of scope. | Complexity is disproportionate to MVP requirements. |
| AD-006 | `broker/auth.py` will not be fully implemented until the REST signature algorithm and credential mapping are confirmed. The WebSocket signing algorithm is now confirmed (HMAC-SHA256) but WebSocket implementation is post-MVP. | Implementing against unverified assumptions produces a module that appears complete but contains a latent defect. REST and WebSocket signing are separate protocols and must not share a generic abstraction prematurely. |
| AD-007 | REST and WebSocket signing are treated as separate protocols. No shared generic signing abstraction will be introduced until both algorithms are confirmed and a concrete need is demonstrated. | The repository shows the README (REST) and `tn-crypto.js` (WebSocket) describe different constructions. A premature shared abstraction would encode an unverified assumption. |

---

## 23. Research Log

Use this template for every research session. Append entries; do not overwrite.

---

### Entry Template

**Date:** YYYY-MM-DD
**Source:** *(documentation URL, support ticket, sandbox test, colleague)*
**Findings:**

- Finding 1
- Finding 2

**Unresolved questions:**

- Question 1
- Question 2

---

### 2025-07-24 — Initial Setup

**Date:** 2025-07-24
**Source:** Internal — project kickoff
**Findings:**

- Document created; all sections marked TBD pending official API access.

**Unresolved questions:**

- All items listed in Section 21.

---

### 2025-07-24 — Authentication Research

**Date:** 2025-07-24
**Sources consulted:**
- https://tradernet.com/tradernet-api
- https://freedom24.com/tradernet-api
- https://github.com/tradernet/tn.api
- https://pypi.org/project/tradernet-sdk/0.4.2/

---

#### F-01 — Official documentation portal located | Confirmed

Two documentation portals were found:
- https://tradernet.com/tradernet-api
- https://freedom24.com/tradernet-api (mirrors the same content)

A GitHub repository was found at https://github.com/tradernet/tn.api, owned by
the `tradernet` GitHub organisation.

The portal is normative evidence that the documented API capability categories
exist. The GitHub repository remains external implementation evidence unless a
specific claim is independently confirmed by the official portal.

---

#### F-02 — The API is branded as Tradernet API | Confirmed

Freedom Broker (Freedom24) is the parent entity. The API surface is branded
Tradernet. All documentation and SDK references use the Tradernet name.

---

#### F-03 — REST base URL | Partially Confirmed

Source: https://github.com/tradernet/tn.api README

https://tradernet.ru/api/


HTTP method: POST (GET permitted for testing only). Data format: JSON.

Status is Partially Confirmed because official ownership of the repository
source is not yet proven.

---

#### F-04 — Observed REST request-body signature description | Partially Confirmed

Source: https://github.com/tradernet/tn.api README (section "Формирование подписи")

The external README describes a `sig` field in the JSON request body. Official
evidence reviewed later did not establish that authentication is universally
body-only or that HTTP authentication headers are never used.

The `sig` field is described as the MD5 hash of the concatenation of all
`parameter_name=parameter_value` pairs, sorted alphabetically by parameter
name and applied recursively for nested parameters, with the `API_SECRET`
appended at the end of the concatenated string.

> ⚠️ **Accuracy note:** This is the README description only. No REST signing
> implementation exists in the repository — `tn-crypto.js` uses HMAC-SHA256
> and is called exclusively from WebSocket example files. The live REST
> endpoint may use a different algorithm than the README describes. See F-16.

Status: Partially Confirmed (README description only; no code implementation).

---

#### F-05 — Credential is a key pair: public key and secret key | Partially Confirmed

Source: https://github.com/tradernet/tn.api README (Socket.IO Node.js example)

The credential consists of two values:
- A public key (variously called `public_key`, `api_key`, `apiKey`)
- A secret key (variously called `secret_key`, `private_key`, `secKey`)

The secret key is never transmitted. Only the signature derived from it is sent.

**Partially confirmed relationship:** The WebSocket `apiKey` field is confirmed
to carry the public key string — see F-16. The relationship between the public
key and the REST `uid` field remains Unknown. The README describes `uid` as an
integer type, which conflicts with the assumption that it carries the public key
string.

---

#### F-06 — Key pair generated in user profile | Partially Confirmed

Source: https://github.com/tradernet/tn.api README

Generation is done through the user interface. Status: Partially Confirmed.

---

#### F-07 — WebSocket uses Socket.IO; auth via `auth` event with nonce | Partially Confirmed

Source: https://github.com/tradernet/tn.api README (Node.js example)

WebSocket uses the Socket.IO library. After connecting, the client emits an
`auth` event with:
- `data`: `{ apiKey: pubKey, cmd: 'getAuthInfo', nonce: Date.now() }`
- `sig`: a signature computed by `tncrypto.sign(data, secKey)`

The assignment of `apiKey` to `pubKey` (the public key) is confirmed — see
F-16. The exact algorithm inside `tncrypto.sign` is now confirmed as
HMAC-SHA256 — see F-16.

WebSocket servers stated in the README:
- Production: `https://ws.tradernet.ru`
- Demo: `https://wsbeta.tradernet.ru`

---

#### F-08 — Observed REST response fields | Partially Confirmed

Source: https://github.com/tradernet/tn.api README

The external README describes JSON responses using `code`, optional `data`, and
optional `errMsg`. The official evidence reviewed later does not establish
these fields as a universal response envelope; response schemas must be
confirmed per operation.

Relevant application error codes:

| Code | Name | Meaning |
|---|---|---|
| 4 | `ERROR_BAD_SIGN` | Invalid signature |
| 7 | `ERROR_UNKNOWN_UID` | Unknown user ID |
| 8 | `ERROR_UNKNOWN_IP` | IP not in allowlist |
| 12 | `ERROR_ACCESS_DENIED` | Access denied / authorisation error |

HTTP status code returned for authentication errors: **Unknown**.

---

#### F-09 — IP restriction is a supported authentication mode | Partially Confirmed

Source: https://github.com/tradernet/tn.api README

The README states that the `API_SECRET` is set by an administrator for
IP-based access. Whether IP allowlisting is mandatory, optional, or an
alternative to key-based auth is not clarified.

---

#### F-10 — Security sessions exist | Confirmed; fields Partially Confirmed

Source: https://github.com/tradernet/tn.api README (Socket.IO section)

The external README describes security sessions as an additional authorisation
layer and lists the following session types:
- `safety_type_id: 2` — Hardware token (Aladdin)
- `safety_type_id: 3` — SMS confirmation
- `safety_type_id: 4` — Login/password (no additional confirmation)

The official portal confirms that security sessions exist and documents SMS,
web-token, and electronic-signature opening flows. Numeric `safety_type_id`
values and the `expire_datetime` and `expire` fields remain external README
evidence rather than a confirmed normative schema.

The README states that the API key pair flow (programmatic auth) bypasses the
normal security session opening process. Which read-only REST endpoints require
an active session is not enumerated. **Partially Confirmed.**

---

#### F-11 — Officially linked Python SDK exists on PyPI | Confirmed

Source: https://pypi.org/project/tradernet-sdk/

A package named `tradernet-sdk` exists on PyPI and is linked by the official
Tradernet API portal. The SDK supports public/private key credentials and is
supporting evidence for client behaviour, but it is not by itself a normative
wire-level contract. KASE Pilot will not use this package as a dependency.

---

#### Impact on `broker/auth.py`

The research affects the implementation model as follows:

1. **REST header use remains Unknown.** Do not assume authentication is
   universally body-only.
2. **REST request-body signing is Partially Confirmed from external evidence**
   and must not be implemented without a normative contract.
3. **The credential is a key pair**, not a single key.
4. **WebSocket authentication is a distinct protocol** (Socket.IO `auth` event
   with a nonce and HMAC-SHA256 signature — confirmed from `tn-crypto.js`).
5. **The REST signature algorithm and `uid` credential mapping remain
   unconfirmed.** Full implementation of `auth.py` for REST must wait.
6. **REST and WebSocket signing must not share a generic abstraction.**
   When WebSocket support is implemented it will be a separate component.

`src/kase_pilot/broker/auth.py` intentionally remains empty until the live REST
authentication contract is confirmed. A placeholder signer must not be added.

---

**Unresolved questions after this session:**

- Is the GitHub repository https://github.com/tradernet/tn.api officially
  maintained by Freedom Broker / Tradernet?
- What is the live REST signature algorithm? The README describes MD5 but no
  REST code implementation exists.
- What is the exact relationship between `public_key` and `uid` (REST body)?
  The WebSocket `apiKey = public_key` mapping is confirmed (F-16).
- Does the key pair expire? If so, what is the TTL?
- Which specific read-only REST endpoints require a security session?
- Does the REST API return HTTP 401 on authentication failure, or always
  HTTP 200 with `code: 12`?

---

### 2025-07-24 — tn-crypto.js Source Code Analysis

**Date:** 2025-07-24
**Sources consulted:**
- https://raw.githubusercontent.com/tradernet/tn.api/master/examples/tn-crypto.js
  (fetched directly via raw.githubusercontent.com)
- https://raw.githubusercontent.com/tradernet/tn.api/master/examples/auth.js
- https://raw.githubusercontent.com/tradernet/tn.api/master/examples/putOrder.js
- https://raw.githubusercontent.com/tradernet/tn.api/master/nodejs.js
- https://api.github.com/repos/tradernet/tn.api/git/trees/master?recursive=1
  (full repository file tree)

---

#### F-12 — `tn-crypto.js` signing function confirmed as HMAC-SHA256 | Confirmed

Source: `examples/tn-crypto.js`, fetched from
`https://raw.githubusercontent.com/tradernet/tn.api/master/examples/tn-crypto.js`

The complete repository file tree was obtained. The repository contains exactly
four JavaScript files: `nodejs.js`, `examples/tn-crypto.js`,
`examples/auth.js`, `examples/putOrder.js`.

The `sign` function in `examples/tn-crypto.js`:

sign(data, apiSec)
→ hash_hmac('sha256', preSign(data), apiSec)
→ crypto.createHmac('sha256', apiSec).update(preSign(data)).digest('hex')


The `preSign` function recursively sorts object keys alphabetically, formats
each as `key=value`, and joins them with `&`.

**Algorithm:** True HMAC-SHA256. The secret key is the HMAC key
(`crypto.createHmac`). The message is the recursively sorted
`key=value&key=value` string. This is not MD5 of any construction.

Status: **Confirmed** — source code read directly.

---

#### F-13 — WebSocket `apiKey` carries the public key | Confirmed

Source: `examples/auth.js`

```javascript
var pubKey = '*** PUBLIC KEY ***';
var data = { apiKey: pubKey, ... };
var sig = tncrypto.sign(data, secKey);
ws.emit('auth', data, sig, cb);
```

`apiKey` is explicitly assigned from `pubKey` (the public key variable).

Status: **Confirmed** — explicit assignment in source code.

---

#### F-14 — No REST signing implementation exists in the repository | Confirmed

Source: Complete repository file tree and all four JavaScript files read.

All three call sites of `tncrypto.sign` are in WebSocket authentication
examples (`examples/auth.js`, `examples/putOrder.js`, README inline example).
No file constructs or sends a REST request with a computed `sig` field. The
README's MD5 description of the REST algorithm has no corresponding code
implementation in the repository.

**Implication:** The live REST signature algorithm cannot be confirmed from
the repository alone. Q3 remains open. The README description (MD5) and the
only code in the repository (HMAC-SHA256 for WebSocket) are different
constructions used for different protocols.

Status: **Confirmed** finding — no REST code exists. REST algorithm: Open.

---

#### F-15 — REST `uid` field type conflicts with public-key assumption | Partially Confirmed

Source: https://github.com/tradernet/tn.api README, request format table

The README describes `uid` as "id пользователя (int)" — integer type. This
conflicts with the assumption that `uid` carries the public key string. No
example in the repository constructs a REST request that traces the `uid`
value to a named credential variable.

Status: Partially Confirmed — integer type from README; actual mapping Unknown.

---

#### F-16 — REST and WebSocket signing are separate protocols | Confirmed

Source: All four JavaScript files and README read in this session.

The repository consistently uses `tn-crypto.js` (HMAC-SHA256) only for
WebSocket. The README describes a different algorithm (MD5-based) for REST.
No file bridges the two. They are separate protocols and must be implemented
as separate components.

**Architectural impact:**

- `broker/auth.py` remains blocked for REST implementation. Q3 (REST
  algorithm) and Q2 (REST `uid` mapping) are still unresolved.
- WebSocket signing is confirmed as HMAC-SHA256. When WebSocket support is
  implemented (post-MVP), it will use a separate component implementing
  HMAC-SHA256 over the sorted `key=value&key=value` message format.
- No shared generic signing abstraction should be introduced until both
  protocols are confirmed and a concrete need is demonstrated.

Status: **Confirmed** — fully supported by source code evidence.

---

**Unresolved questions after this session:**

- Q2 (REST): What does the `uid` field carry? Integer type in README conflicts
  with public key string assumption. Requires a verified REST request example.
- Q3: What is the live REST signature algorithm? README says MD5-based, but no
  REST implementation exists to verify. Requires a working REST request test
  or direct confirmation from Tradernet.

---

### 2026-07-27 — Controlled `getSecurityInfo` Live Request

**Date:** 2026-07-27

**Evidence class:** Observed live evidence through the officially linked
`tradernet-sdk` 2.2.0. This entry records one successful exchange; it is not a
normative contract and must not be generalized to other REST operations.

#### F-17 — `getSecurityInfo` successful exchange | Confirmed observed

The controlled read-only request used:

- **Endpoint:** `https://freedom24.com/api/getSecurityInfo`
- **HTTP method:** POST
- **Request body:** `{"ticker":"AAPL.US","sup":true}`
- **Observed headers:** `Content-Type: application/json`,
  `X-NtApi-PublicKey`, `X-NtApi-Timestamp`, and `X-NtApi-Sig`
- **HTTP status:** 200

Credential values and the signature were not recorded.

The successful response was an operation-specific top-level JSON object. The
observed fields were `id`, `nt_ticker`, `short_name`, `default_ticker`,
`code_nm`, `currency`, `min_step`, `lot`, `mkt_name`, `firstDate`, and nested
`mrkt`. In this response, `min_step` and `lot` were strings and `mrkt` was an
object. A universal `code`/`data`/`errMsg` envelope was absent.

**Evidence boundaries:**

- The official portal normatively confirms that the instrument-information
  capability exists.
- The official SDK supplies the request construction and authentication
  behaviour used in this observation.
- The live observation confirms only this endpoint, method, request instance,
  header presence, HTTP status, and response shape at the verification date.
- The observation does not confirm the signing algorithm, canonicalization,
  timestamp tolerance, complete or stable response schema, whether `sup` is
  mandatory, the error contract, or authentication/security-session
  requirements for any other operation.

**Readiness assessment:** `PARTIAL`, not `READY`.

The operation now has a reproducible successful observed request, but the
existing `READY` criteria are not fully met. Still missing:

- a normative confirmation of the command and complete parameter contract,
  including required parameters, types and formats;
- confirmed authentication and security-session requirements;
- a saved complete successful response sample suitable for evidence review;
- a confirmed complete response schema and schema-stability expectations;
- confirmed operation-specific errors or proof of an applicable common error
  contract.

---

### 2026-07-31 — WebSocket Protocol Discrepancy (Two Conflicting Sources)

**Date:** 2026-07-31
**Sources consulted:**
- https://github.com/tradernet/tn.api README and `examples/*.js` (previously
  recorded — see F-07, F-12, F-13, F-16)
- https://tradernet.global/tradernet-api/security-get-list (official portal
  page, supplied directly by the project owner in this session)
- Live browser session on `tradernet.global` under a real account (console
  output supplied directly by the project owner)

#### F-18 — Two incompatible documented WebSocket protocols | Confirmed discrepancy, not yet resolved

The previously recorded WebSocket protocol (F-07/F-12/F-13/F-16, from the
`tn.api` GitHub repository) and the official portal page for
`getSecuritySessions` describe **two different connection and authentication
models**:

| Aspect | `tn.api` GitHub repo (previously recorded) | `tradernet.global/tradernet-api/security-get-list` (this session) |
|---|---|---|
| Transport | Socket.IO client | Plain `new WebSocket(url)`, no Socket.IO |
| Auth mechanism | `auth` event: `{apiKey, cmd, nonce}` + HMAC-SHA256 signature | `SID` (session ID from a prior HTTP login), sent via cookie header or as a request parameter |
| Command framing | Socket.IO named events (`emit`/`on`) | Plain JSON array over `ws.send`, e.g. `["sessions"]`; responses framed as `[event, data]` |
| API generation label | Not stated | Explicitly labelled **"API V1"** in the parameter table |

This is not a case of one source being more detailed than the other — the
two describe structurally different protocols (event-based RPC over
Socket.IO with cryptographic signing, vs. a raw WebSocket with a
cookie-style session token). Possible explanations, none yet confirmed:

1. Two live API generations coexist (a legacy "V1" SID-cookie protocol and a
   newer Socket.IO+HMAC protocol), and a client must pick one.
2. The portal page is stale documentation for a retired protocol version.
3. The `tn.api` GitHub repository documents a variant not actually used by
   the production frontend at `tradernet.global`.

**No code should be written against either protocol until this is resolved
by a live, observed WebSocket handshake** — consistent with this project's
existing rule (§8, `AUTHENTICATION_READINESS.md`) against coding against
unconfirmed authentication contracts.

#### F-19 — Real production WebSocket hosts observed via live browser session | Confirmed observed

Source: browser Content-Security-Policy violation report captured from the
project owner's own real, authenticated session on `tradernet.global`
(`connect-src` directive, listing every WebSocket origin the production
frontend is permitted to reach).

The following broker-operated WebSocket hosts are confirmed to exist in the
live CSP allow-list (subset relevant to this project; full list is broader
and includes unrelated third-party regions/brands):

- `wss://wss.tradernet.global`
- `wss://wss.freedombroker.global`
- `wss://wss.tradernet.kz`
- `wss://wss.freedombroker.kz`
- `wss://wss.tradernet.com` (wildcard `wss://*.tradernet.com`)
- `wss://wss.freedom24.com`
- `wss://wss.tradernet.ru`, `wss://wss2.tradernet.ru`

This confirms multiple regional/brand-specific WebSocket hosts exist
side by side. It does **not** confirm which host or protocol variant (see
F-18) is the correct one for a KZT/KASE-scoped account, nor does it capture
any actual WebSocket frame content — the supplied console output was the
browser's Console tab (dominated by unrelated third-party analytics/CSP
noise: Yandex Metrica, Sentry, marketing pixels) and did not include the
Network tab's WebSocket "Messages" view, which is what would show the real
handshake and command/response frames.

**Impact:** Confirms host reachability only. The actual authentication
handshake and command framing for a KASE/KZT account remain unconfirmed.

#### Project scope note

The project owner has confirmed the trading-bot scope is restricted to the
**KASE market, KZT-denominated instruments only** — no multi-exchange,
multi-currency, or options support is in scope. This does not by itself
resolve F-18, but it does mean the relevant host is very likely
`wss://wss.tradernet.kz` or `wss://wss.freedombroker.kz` rather than the
`.com`/`.ru`/`.global` variants, once F-18 is resolved.

#### F-20 — Live WebSocket capture from `wss.tradernet.global`, real account | Confirmed observed

Source: browser DevTools Network tab, WS filter, live authenticated session
on `tradernet.global` under the project owner's real account. Supplied
directly in this session.

**Connection:**

```
GET wss://wss.tradernet.global/?clientLogin=<url-encoded-email>&ctsi=725726
Status: 101 Switching Protocols
```

This is a **fourth distinct auth shape**, matching neither previously
recorded variant exactly:

- Not Socket.IO: the URL has no `/socket.io/` path segment and no
  Engine.IO query parameters (`EIO=`, `transport=`) — the characteristic
  shape of a Socket.IO client connection is absent. This is evidence
  *against* F-07/F-12's Socket.IO claim for this connection, though the
  response headers were not captured and a Socket.IO-over-plain-WebSocket
  configuration cannot be fully excluded from this evidence alone.
- Not the SID-cookie "API V1" shape either: no `SID` parameter or cookie
  was shown; instead the query string carries `clientLogin` (the account's
  plain email address, URL-encoded) and `ctsi` (an opaque numeric value —
  meaning not confirmed; possibly a per-connection or per-session token).
- No HMAC signature, nonce, or `apiKey` field appears anywhere in the
  connection URL.

**No outgoing (client → server) frame was captured in the evidence
supplied** — only inbound server → client messages were shown. Whether the
client sends anything after the connection opens (a subscribe/filter
command, an explicit login confirmation, etc.) is still unobserved.

**Inbound message shape (repeated, unsolicited, immediately after connect):**

Every captured frame is a 3-element JSON array:
```
["q", { ...fields... }, "wstm=2026-07-31T07%3A27%3A20.380Z"]
```

- First element: event name. Only `"q"` observed. This matches the
  previously recorded (external-source) "Available Streams" table entry
  for stock quotes (`notifyQuotes` / `q`) — now **Confirmed by live
  capture**, upgraded from "Category Confirmed; event name Partially
  Confirmed."
- Second element: a data object. Fields observed across samples (not all
  present on every message): `bas`, `bbp`, `bbs`, `baf`, `bbf`, `bap`,
  `ltp`, `ltt`, `c` (instrument code, e.g. `"EUR/USD"`, `"RUBKZT_TOD.KZ"`,
  `"MBG.EU"`), `init`, `n`, `rev`, `type` (integer; `1`, `5`, `6`, `7`
  observed, meaning not confirmed), `vlt`, `vol`, `acc_srv_tm` (server
  timestamp string, e.g. `"2026-07-31 10:27:20.379"`). Field names are
  recorded verbatim, not decoded or guessed.
- Third element: a literal string `"wstm=<url-encoded ISO-8601 timestamp
  with milliseconds>"` — not a clean value, an embedded query-string-style
  fragment inside a JSON array slot. Recorded exactly as observed; the
  reason for this shape is not explained by anything seen so far.

**Instruments observed in this unsolicited burst:** a broad mix of FX pairs
(`EUR/PLN`, `EUR/RUR`, `EUR/SEK`, `EUR/USD`, `GLD/RUR`, `JPY/RUR`,
`MXN/RUR`, `PLN/EUR`, `RUR/AED`, `RUR/AMD`, `RUR/CNY`, `RUR/EUR`), two
KZT/KASE-relevant FX instruments (`EURUSD_TOM.KZ`, `RUBKZT_TOD.KZ` —
`.KZ`-suffixed, `TOD`/`TOM` likely settlement-day markers, meaning not
confirmed), two indices (`FTSE.IDX`, `RTS.MCX`), and one equity
(`MBG.EU`). This looks like a broad default quote firehose pushed
immediately on connect, not scoped to the connecting account or to
KASE/KZT — no subscription/filter command was seen being sent to narrow
it, but none was captured at all, so this cannot be fully explained yet.

**Impact:**

- The `getSecuritySessions`/`sessions` question (F-18) is still
  unresolved — this capture happened to show quote traffic, not a security
  sessions request/response, and showed no outgoing frames at all.
- The Socket.IO+HMAC protocol (F-07/F-12) looks less likely for this
  specific connection based on URL shape, but is not conclusively ruled
  out.
- The SID-cookie "API V1" shape (F-18, from the portal doc) does not match
  either — no `SID` appears.
- A real, working, unsolicited quote stream now exists as evidence,
  independent of the auth-mechanism question: this at least confirms that
  *some* quote data reaches the client without any confirmed explicit
  subscribe step in the visible evidence.

**Unresolved questions after this session:**

- What does the client send, if anything, right after the connection
  opens? (No outgoing frame was captured — need the green "▲" rows in
  DevTools Messages, not just inbound.)
- What is `ctsi`, and how is it obtained? (Likely from a prior HTTP login
  response — not yet traced.)
- Is the quote firehose the default behaviour for every connection, or is
  it already scoped somehow (e.g. by a prior subscription made earlier in
  the session, before this capture started)?
- How is a subscription scoped to KASE/KZT instruments specifically —
  is there a filter/subscribe command, or does the client filter
  client-side from the full firehose?
- Does `getSecuritySessions`/`sessions` (the original F-18 topic) use this
  same connection/auth shape, or a different one? Not yet captured.
- Is this `clientLogin`+`ctsi` shape stable/documented anywhere officially,
  or reverse-engineered purely from this one observed session?

---

#### F-21 — Live-captured subscription burst answers the "how is the firehose scoped" question | Confirmed observed, with new open question

Source: same browser DevTools WS capture session as F-20, same connection
(`wss://wss.tradernet.global/?clientLogin=<email>&ctsi=725726`). Supplied
directly in this session, timestamped ~2 minutes before the F-20 quote
frames.

A burst of nine messages was sent, all at the same timestamp
(`12:25:22.289`), each shaped as a 2-element JSON array
`[channel_name, payload]`:

```
["markets", null]
["portfolio", null]
["calculatedPortfolio", null]
["orders", null]
["counters", [1901279]]
["adminMessage", null]
["alerts", null]
["sms", null]
["quotes", ["AED/USD915015212", "CHF/USD915094478", ... ~370 entries ...]]
```

**Direction:** inferred, not yet explicitly confirmed by the project owner,
to be **outgoing (client → server)** subscription requests — the shape
matches the officially documented `ws.send(JSON.stringify(['sessions']))`
pattern from `tradernet.global/tradernet-api/security-get-list` (a bare
`[command, ...args]` array), and the timing (~2 minutes before the F-20
quote push burst) is consistent with "subscribe once at connect time, then
receive pushes." **This direction should be explicitly confirmed** (e.g.
by checking the arrow/color DevTools shows for these specific rows) before
relying on it.

**This resolves the earlier open question from F-20** ("is the quote
firehose scoped, or a default broadcast?"): it is **not** an unscoped
broadcast — the client explicitly subscribes to a specific list of several
hundred instruments via one `quotes` message immediately after connecting.
Every entry in that list has the shape `"<ticker><internal_id>"` —
ticker and an opaque numeric ID joined by an ASCII ETX (0x03) control
character, e.g. `"HSBK.KZ915092193"`, `"KSPI.KZ915081690"`,
`"EURUSD_TOM.KZ915094727"`.

**New confirmed channels** (not previously recorded anywhere in this file):
`calculatedPortfolio`, `counters`, `adminMessage`, `alerts`, `sms`. The
`counters` channel's payload, `[1901279]`, is a numeric ID — plausibly an
account or session identifier, not yet traced to a confirmed source.

**KASE relevance:** the subscribed list includes numerous `.KZ`-suffixed
tickers confirming KASE instruments are addressed identically through this
same channel — e.g. `HSBK.KZ`, `KSPI.KZ`, `CCBN.KZ`, `KZTK.KZ`, `KZTO.KZ`,
`KEGC.KZ`, `KMGD.KZ`, `ASBN.KZ`, `AIRA.KZ`, `KASE.IDX`, plus several
`*_TOD.KZ`/`*_TOM.KZ` FX pairs (settlement-day markers, meaning not
confirmed).

**Critical new open question — the internal numeric ID:** every subscribed
ticker is paired with a numeric ID (e.g. `915092193` for `HSBK.KZ`) that
does not match anything seen in any REST response captured so far
(`getSecurityInfo`'s `id` field, per F-17, is the ticker string itself,
`"AAPL.US"`, not a numeric ID in this range). **It is not yet known:**

- Whether this numeric ID is required to subscribe (i.e. can a client send
  `"HSBK.KZ"` alone, without the ID, and still get pushes?), or whether
  the ID must be looked up first.
- Where this ID would come from for an instrument not already in the
  client's default watchlist — no confirmed REST or WS response captured
  in this project exposes it yet.
- Whether this ID is stable across sessions/accounts or per-session.

This is now the single most important unresolved blocker for building a
real quote-subscription client: without knowing how to obtain this ID for
an arbitrary ticker, only the ~370 instruments already seen in this one
capture could be subscribed to with confidence.

**Unresolved questions after this session (supersedes the F-20 list):**

- Confirm the direction (outgoing vs incoming) of the nine-message burst
  above using DevTools' own direction indicator, not inferred from shape.
- Where does the ``-joined numeric ID come from for a ticker not
  already in this captured list? Is there a lookup endpoint?
- Can `quotes` be subscribed with just the ticker (no numeric ID), e.g.
  `["quotes", ["HSBK.KZ"]]`?
- What is `counters`' payload `[1901279]` — account ID, session ID, user
  ID? Where else does this number appear (e.g. compare against any REST
  `user-data`/`user_info` response fields)?
- Still open from F-20: what is `ctsi`, and does `getSecuritySessions`
  share this connection/auth shape?

---

### 2026-07-31 (continued) — Official Manual Pages, Supplied Directly by Project Owner

**Sourcing note:** from this point on, the project owner is browsing the
official Tradernet manual/documentation site directly and pasting the
relevant pages into this session on request, instead of this project
searching or guessing at endpoint behaviour. This is the preferred
evidence path going forward — treat any manual page supplied this way as
**Confirmed as an official documented contract**, distinct from the
`tn.api` GitHub repository (external, ownership never proven — see F-01)
and distinct from live-captured evidence (which confirms actual runtime
behaviour but not official intent).

#### F-22 — `getOPQ` documented REST contract is a *third* incompatible REST shape | Confirmed discrepancy, not yet resolved

Source: official manual page for `getOPQ` ("Начальный объект со всеми
данными по пользователю"), supplied directly by the project owner.

**Documented request shape:**
```js
$.getJSON('https://tradernet.com/api/', {q: JSON.stringify(exampleParams)}, callback);
// exampleParams = {"cmd": "getOPQ", "SID": "<SID from prior authorization>", "params": {}}
```
GET request to a single shared endpoint (`https://tradernet.com/api/`),
command and parameters wrapped in one JSON object, passed as the value of
a single query-string parameter `q`. Authentication is via `SID` (a
session identifier obtained from a prior, separately-documented login
step), not a cryptographic signature.

**This is incompatible with two other REST shapes already on record in
this file:**

| Shape | Transport | Auth | Endpoint | Evidence status |
|---|---|---|---|---|
| `tn.api` GitHub README (F-04) | POST, `cmd`/`params`/`sig` in body | MD5(sorted params + secret) | shared `/api/` | Partially Confirmed, no code implementation found (F-14) |
| **Live-confirmed** `getSecurityInfo` (F-17) | POST | Headers: `X-NtApi-PublicKey`/`X-NtApi-Timestamp`/`X-NtApi-Sig` | **per-command URL** (`/api/getSecurityInfo`) | **Confirmed observed**, real live call via the officially-linked SDK |
| `getOPQ` manual page (F-22, this entry) | **GET** | `SID` in the request payload | shared `/api/` | Confirmed as officially documented, **not yet live-tested** |

This is the same pattern already found on the WebSocket side (F-18): the
official documentation site describes multiple, non-overlapping API
generations. **Do not assume `getOPQ`'s documented shape works as written
without a live test** — the same caution that applies to F-18 applies
here. The one shape in this project that is actually trustworthy without
further verification is the live-confirmed `getSecurityInfo` shape
(F-17), precisely because it was tested, not because it is the most
recently documented.

**Does not resolve:** the F-21 open question about the WS `quotes`
subscription's numeric per-ticker ID. The `getOPQ` response's quote
objects (`quotes.q[]`) were reviewed field-by-field
(`acd`, `bap`, `bas`, `c`, `codesub_nm`, `min_step`, `name`, `rev`, ...) —
none matches the 9-digit ID format seen in the F-21 WS subscription
payload (e.g. `915092193` for `HSBK.KZ`). This connection was checked for
and not found; it is not assumed to not exist elsewhere, only that this
particular response does not contain it.

**Other content confirmed by this manual page** (for future reference,
not yet used):

- `codesub_nm` in the quote object carries a human-readable exchange name
  (e.g. `"NASDAQ"`) — a candidate normative source for `exchange`-type
  metadata, distinct from KASE Pilot's own local-catalog `exchange` field.
- `userLists.userStockLists.default` / `stocksArray` — the account's
  saved ticker watchlist(s), as plain ticker strings, no numeric IDs.
- Full account/user profile object (`userInfo`), including PII
  (name, birthday, tax ID equivalents, phone, etc.) — a strong reminder
  that any future caching/logging of this endpoint's response must follow
  the existing secrets/PII logging policy (§19) strictly.

**Unresolved questions after this session:**

- Is `getOPQ`'s documented GET+`SID`+shared-endpoint shape actually live
  today, or is it — like the WebSocket "API V1" SID shape (F-18) — a
  legacy/retired generation?
- Where is `SID` obtained from? (A separate documented login endpoint,
  not yet supplied to this project.)
- Still fully open: the F-21 numeric per-ticker ID for WS `quotes`
  subscriptions.

---

### 2026-07-31 (continued) — Official Manual Pages Confirm REST Auth; SDK Source Resolves WebSocket

**Sources:**
- Official manual pages supplied directly by the project owner: `getSecuritySessions` (with NodeJS and Browser JS examples), `getAllSecurities` ("Справочник бумаг"), and the master "Как работает API" ("How the API works") page.
- Direct source inspection of the installed `tradernet-sdk==2.2.0` package (already a project dependency): `tradernet/tradernet_websocket.py`, `tradernet/common/ws_utils.py`, `tradernet/core.py`.

#### F-23 — `tradernet-sdk`'s `TradernetWebsocket` class resolves the WebSocket protocol question | Confirmed via source code

The SDK already implements a WebSocket client (`TradernetWebsocket`, exported from the package's top-level `__init__.py`, i.e. public API). Reading its implementation directly settles F-18/F-20/F-21 far more reliably than either documentation source, because it is executable, already-depended-upon code, not a claim:

- **Transport:** plain WebSocket via `aiohttp.ClientSession.ws_connect` (`tradernet/common/ws_utils.py::WSUtils.get_stream`). **Not Socket.IO.** This matches the "Browser JS" example on the official manual page (raw `new WebSocket(...)`, plain JSON array commands), not the "NodeJS" example on the same page (which uses `socket.io-client`). The two examples on one official manual page describe different transports; the SDK's choice is the one to trust, since it is maintained by Tradernet and already used successfully for this project's live-confirmed REST calls (F-17).
- **Auth:** the same three fields already confirmed for REST in F-17 — `X-NtApi-PublicKey`, `X-NtApi-Timestamp`, `X-NtApi-Sig` (HMAC-SHA256) — via `Core.websocket_auth()`. **Not SID, not `clientLogin`+`ctsi`, not a Socket.IO `auth` event.** Sent as **query-string parameters** on the WS connection URL (`ws_connect(url, params=self.core.websocket_auth())` — `aiohttp`'s `params` argument controls the query string, not headers).
- **Host:** `wss://wss.{Core.DOMAIN}`, default `DOMAIN = 'freedom24.com'` → `wss://wss.freedom24.com`. `DOMAIN` is a class variable, not a constructor parameter; overriding it requires subclassing. Matches one of the hosts already confirmed reachable in F-19.
- **Command framing:** `self.stringify([command, args...])` sent once via `websocket.send_str(...)` immediately after connecting — e.g. `['quotes', ['FRHC.US']]`, `['markets']`, `['portfolio']`, `['orders']`. This matches the *shape* of the live capture in F-21 exactly (`["markets", null]`, `["quotes", [...]]`, etc.).
- **Response framing:** `event, data, _ = json_loads(message)` — a 3-element array, third element discarded by the SDK. Matches the `["q", {...}, "wstm=..."]` shape observed live in F-20 exactly, including the previously-unexplained third element (the SDK doesn't explain it either — it just ignores it).
- **The F-21 numeric per-ticker ID is resolved: it is not required.** The SDK subscribes with plain ticker strings only (`['quotes', ['FRHC.US']]`), never a ticker+ID pair. The `TICKER<9-digit-id>` shape seen in the live browser capture (F-21) is very likely a web-frontend-internal optimization (e.g. a cache key), not a protocol requirement.

**Methods currently implemented by the SDK:** `quotes(symbols)`, `market_depth(symbol)` (order book — event `b`), `portfolio()`, `orders()`, `markets()`. **Not implemented by the SDK:** `sessions` (security sessions — the original F-18 topic), `news`, `counters`, `alerts`, `sms`, `calculatedPortfolio`. These would need to be added by this project if needed, but now against a confirmed protocol rather than a guessed one — same auth, same host, same framing, just a different first array element.

**Readiness impact:** WebSocket quotes/order-book/portfolio/orders/market-status subscriptions can now be considered `PARTIAL`→ trending toward `READY`: protocol, auth, host, and framing are all confirmed by source code already in this project's dependency tree. What remains before implementation: a live end-to-end test (connect, subscribe, receive at least one real message) using this project's own credentials, and a decision on whether to use `TradernetWebsocket` directly (like `TradernetSdkAdapter` already does for REST) or reimplement the same protocol independently.

#### F-24 — Official master auth page confirms F-17's REST mechanism; `getAllSecurities` is a real documented securities directory

**"How the API works" (master page):**

- Confirms, in official prose (not just observed behaviour), exactly the mechanism already live-confirmed in F-17: endpoint `https://tradernet.com/api/{command}` (per-command URL — "any of domain zones can be used as API endpoint"), authentication via `X-NtApi-PublicKey`/`X-NtApi-Sig`/`X-NtApi-Timestamp` headers, HMAC-SHA256 signature.
- **New detail, not previously recorded:** signing rules differ by HTTP method. For POST/PUT, the signature covers the JSON request body plus the timestamp. For GET, the signature covers **only the timestamp** (request parameters are not included in the GET signature). This was not observable from the single POST-only live sample in F-17.
- States explicitly: "each request is authenticated via signature, so a separate authorization step is not required" — i.e. this mechanism is presented as self-sufficient, not requiring a prior SID/login step. This directly conflicts with the SID-based flows described in the `getSecuritySessions` and `getOPQ` manual pages (F-18, F-22) on the same documentation site. **Resolution for this project:** the header+HMAC mechanism is the one to build against — it is the one independently confirmed by (a) a live test (F-17), (b) this official master page, and (c) the officially-maintained SDK's source code (F-23). The SID-based pages should be treated as documentation for a different, likely legacy, generation unless a live test proves otherwise.
- This resolves Open Question §21 Q3 ("What is the live REST signature algorithm?") — upgrade from Open to **Resolved**.
- This substantially narrows Open Question §21 Q2 (relationship between `public_key` and `uid`): the officially documented and SDK-implemented mechanism has **no `uid` field at all** — only `X-NtApi-PublicKey`. The `uid`/`public_key` ambiguity from the original `tn.api` GitHub README (F-05/F-15) appears to belong to a different, likely-superseded API description. Treat `uid` as not part of the current live contract unless separately proven otherwise.

**`getAllSecurities` ("Справочник бумаг"):**

- A real, documented securities-directory endpoint: `cmd: getAllSecurities`, supports `take`/`skip` pagination, `sort`, and `filter` (operators: `eq`, `neq`, `eqormore`, `eqorless`, `isempty`, `contains`, `doesnotcontain`, `startswith`, `endswith`, `in`, `isnull`, `notnull`). Filterable/sortable fields include `ticker`, `instr_type`, `instr_kind`, `mkt_id`, `mkt_name`, `mkt_short_code`, `face_curr_c`, `fv`, `step_price`, `x_short`.
- **Documented rate limit: 10 requests per minute.** This is the first concrete rate-limit figure recorded anywhere in this file (§18 was entirely TBD).
- Response includes `mkt_short_code` (e.g. `"FIX"` for `AAPL.US`) — this is the same field name already independently chosen for KASE Pilot's own local catalog schema (`catalog/data/instruments.json`'s `market` field concept), though the two are not the same data source and should not be conflated without a live test confirming the value shapes match for KASE instruments specifically.
- **Does not resolve F-21's numeric ID question** (now moot per F-23 — the ID isn't needed). Reviewed field-by-field for completeness: `instr_id` (e.g. `"40000001"`), `id` (e.g. `113`), `mkt_id` (e.g. `"30000000001"`) are all present but none match the 9-digit range seen in the F-21 browser capture; this is recorded for completeness, not because it matters now.
- **Not yet live-tested.** Per this project's own rule (no code without a live-confirmed contract where feasible), this should be tested with real credentials before being relied upon, the same way `getSecurityInfo` was in F-17 — especially since the example `curl` snippet on the same manual page mixes `Cookie: SID=...` with the `q=` POST body style, which is inconsistent with both the master auth page and the SDK.

**Unresolved questions after this session:**

- Live-test `TradernetWebsocket.quotes(["some KASE ticker"])` (or `markets()`, as the simplest possible smoke test) with real credentials — this is now a code/credentials task, not a research task.
- Live-test `getAllSecurities` (ideally via the SDK, if it exposes this command — not yet checked) to confirm it actually returns data for KASE/KZT instruments, unlike `getReadyList`/refbooks.
- The SDK does **not** expose `getAllSecurities` under any dedicated method
  (confirmed by a full-text search of the installed package — no match for
  `getAllSecurities`/`get_all_securities`/`AllSecurities`). It would have
  to be called via the generic `Tradernet.authorized_request('getAllSecurities', {...})`
  method (public, already used internally by every other typed method in
  the SDK), not a purpose-built wrapper.
- `sessions`/`getSecuritySessions` over WebSocket: still not implemented by the SDK and still not live-captured directly (F-20/F-21 captured `quotes`/`markets`/etc., not `sessions`). Protocol is now known by extension (same auth/framing as F-23), but the specific command has not been observed working.

---

### 2026-07-31 (continued) — Live Smoke Test of `TradernetWebsocket.markets()`

**Date:** 2026-07-31
**Source:** Project owner ran the one-off smoke test proposed at the end of
F-23/F-24, using real account credentials, and supplied the result
directly.

#### F-25 — `TradernetWebsocket` confirmed working end-to-end with real credentials | Confirmed observed

```python
core = Tradernet(public_key, private_key)
async with TradernetWebsocket(core) as ws:
    async for quote in ws.markets():
        print(quote)
        break
```

Connected successfully; `markets()` yielded one `dict` message with
top-level keys `t` (snapshot time, e.g. `"2026-07-31T10:30:00"`) and `m`
(a list of market status entries). Market codes seen in the sample
included `AIX`, `AMX`, `ATHEX`, `BIST`, `FIX`, `SPBEX`, `US_OPT`, `WSE`,
"and others" (the full list was not supplied verbatim).

**This is the first fully live, end-to-end confirmation of F-23**: the
SDK's WebSocket implementation (transport, `X-NtApi-*` query-param auth,
`[command, args]` framing, `[event, data, _]` response framing) works
against a real account, not just against SDK source code.

**Open concern — KASE was not seen in the reported sample.** The market
codes reported (`AIX`, `AMX`, `ATHEX`, `BIST`, `FIX`, `SPBEX`, `US_OPT`,
`WSE`) do not include a code that unambiguously reads as `KASE`. Note in
particular: **`AIX` is Astana International Exchange, a distinct legal
entity from KASE (Kazakhstan Stock Exchange)** — they must not be
conflated even though both are Kazakhstani. Since the reported list was
described as truncated ("and others"), this is not evidence that KASE is
absent from `markets()` — only that it wasn't visible in what was reported
here. Given this project's explicit KASE-only scope, this must be checked
with the untruncated `m` list before assuming market-status coverage
includes KASE.

**Unresolved questions after this session:**

- Get the full, untruncated `m` list from the same `markets()` call and
  check specifically for a `KASE` (or similarly-named) entry.
- If KASE is absent from `markets()`, is it absent from the WebSocket
  layer entirely, or just from this particular stream (market status),
  while `quotes()`/instrument-level data still covers KASE tickers (as
  already suggested by the KASE-suffixed tickers seen in the F-21 browser
  capture)?

---

#### F-26 — KASE confirmed present in the full `markets()` payload | Confirmed observed

**Date:** 2026-07-31
**Source:** Project owner supplied the complete, untruncated `m` list from
the same live `markets()` call as F-25.

`KASE` is present and was `OPEN` at capture time:

```
{'mkt_id': 30000000010, 'p': '09:20:00', 'n': 'KASE', 'o': '09:30:00',
 'c': '20:00:00', 'dt': -120, 'tz': 'Asia/Yekaterinburg', 'n2': 'KASE',
 's': 'OPEN', 'post': None, 'date': [...KZ public holidays...],
 'ev': [...gate/open/close events...]}
```

Two related, distinct market codes also appear:

- `KASE.CUR` (`mkt_id: 30000000026`) — likely the KASE currency/FX
  market, given the name pattern (meaning not confirmed from this payload
  alone).
- `KASE.OTC` (`mkt_id: 30000000027`) — likely an OTC segment of KASE
  (meaning not confirmed from this payload alone).

`AIX` (`mkt_id: 30000000025`) is confirmed present as a **separate** entry
from `KASE` — corroborating the earlier caution in F-25 that the two must
not be conflated. Also present: `ITS` and `ITS_MONEY` (`tz: Asia/Almaty`),
whose relationship to KASE, if any, is not confirmed by this payload and
should not be assumed.

**Note on the `tz` field:** `KASE`, `KASE.CUR`, and `AIX` all report
`'tz': 'Asia/Yekaterinburg'`, not `'Asia/Almaty'` — recorded exactly as
observed; this is presumably a UTC-offset-equivalent timezone choice on
Tradernet's side (Yekaterinburg and Almaty currently share the same UTC
offset) rather than an error, but this is not confirmed and should not be
relied upon to mean anything beyond "same offset."

**Impact:** This closes the open question from F-25. WebSocket market
status coverage for KASE is now live-confirmed, on top of the
already-confirmed protocol/auth mechanism (F-23) and the already-confirmed
end-to-end connectivity (F-25). Combined with the KASE-suffixed tickers
already seen in the `quotes` subscription list (F-21 — `HSBK.KZ`,
`KSPI.KZ`, `CCBN.KZ`, etc.), there is now live evidence that both market
status and instrument quotes are available for KASE over this WebSocket
connection.

**Still not live-tested:** `quotes()` specifically for a KASE ticker
through the SDK (only `markets()` has been tested so far), and the
`getAllSecurities` REST endpoint for KASE coverage (F-24).

---

### 2026-07-31 (continued) — `kase-pilot stream-quotes` Live End-to-End Confirmation

**Date:** 2026-07-31
**Source:** Project owner ran the newly implemented
`kase-pilot stream-quotes HSBK.KZ` command against a real account and
supplied the output directly.

#### F-27 — Live quote stream confirmed for a real KASE/KZT instrument through this project's own code | Confirmed observed

Two messages were received for `HSBK.KZ` (Halyk Bank, KASE):

- A full quote message: `base_currency: "KZT"`, `base_ltr: "KASE"`,
  `x_curr: "KZT"`, `marketStatus: "OPEN"`, `name: "Народный банк
  Казахстана"`, live bid/ask/last prices in tenge (`bap`, `bbp`, `ltp`,
  etc.).
- A second, much smaller message for the same ticker (`c`, `init`, `lts`,
  `ltt`, `n`, `rev`, `type`, `acc_srv_tm` only — most fields absent).

**This is the first confirmation that runs entirely through this
project's own code** (`TradernetWebsocketAdapter` → `StreamQuotes` →
`kase-pilot stream-quotes` CLI command), not just SDK source reading
(F-23), a bare Python smoke test (F-25), or a browser capture (F-20/F-21).
It confirms, for a real KASE/KZT instrument specifically: connection,
auth, subscription, and message delivery all work through the
implementation built in this project.

**New confirmed detail — quote messages are partial/delta updates, not
always full snapshots.** The second message shares only 8 of the ~70
fields present in the first. **Implication for any future consumer code:**
no field should be assumed present on every message except `c` (the
ticker) — not even fields as basic as `ltp` (last price) or `bap`/`bbp`
(bid/ask). Any code that aggregates or persists this stream must merge
partial updates onto prior state per ticker, not treat each message as a
complete quote.

**Readiness impact:** the WebSocket quote-streaming capability for
KASE/KZT can now be considered fully confirmed end-to-end for this
project's own implementation, not just the underlying SDK/protocol. What
remains open is entirely downstream of this: persistence/storage design
(explicitly deferred, per the architecture discussion preceding this
implementation) and coverage of the remaining "core" streams (order book,
trades, news) not yet implemented in this project.

---

### 2026-07-31 (continued) — `kase-pilot stream-orderbook` Live End-to-End Confirmation

**Date:** 2026-07-31
**Source:** Project owner ran `kase-pilot stream-orderbook HSBK.KZ`
against a real account and supplied the output directly.

#### F-28 — Live order-book stream confirmed for a real KASE instrument | Confirmed observed

Two messages received for `HSBK.KZ`:

```json
{
  "n": 0, "i": "HSBK.KZ", "min_step": null, "step_price": null,
  "del": [],
  "ins": [
    {"p": 383.96, "s": "S", "q": 249, "k": 0},
    {"p": 383.8, "s": "B", "q": 21, "k": 1}
  ],
  "upd": [], "cnt": 2, "x": 1
}
{
  "n": 1, "i": "HSBK.KZ",
  "del": [{"p": 383.8, "k": 1}, {"p": 383.96, "k": 0}],
  "ins": [
    {"p": 383.98, "s": "S", "q": 974, "k": 0},
    {"p": 383.97, "s": "B", "q": 94, "k": 1}
  ],
  "upd": [], "cnt": 2, "x": 1
}
```

**Message shape (recorded as observed, field meanings inferred from
context only, not officially confirmed):** `n` — sequence number
(increments per message); `i` — ticker; `min_step`/`step_price` — present
only on the first message, `null`, absent afterward; `del`/`ins`/`upd` —
arrays of order-book level changes; each level has `p` (price), `s` (side,
`"B"`/`"S"`), `q` (quantity), `k` (an index/key used to correlate `ins`
and later `del` entries — the second message deletes exactly the two `k`
values inserted by the first); `cnt` — count (meaning of what, not
confirmed); `x` — unexplained integer flag.

**This confirms the order book stream is an incremental diff feed, not a
full-snapshot feed** — same pattern already seen for `quotes` (F-27:
partial updates), but here explicit: the protocol has dedicated
insert/delete/update arrays rather than sparse full-record fields. **Any
future consumer must maintain order-book state per ticker by applying
`del`/`ins`/`upd` to prior state, keyed by `k`** — a single message is not
a usable order book on its own after the first one.

**Readiness impact:** WebSocket order-book streaming for KASE is now
confirmed end-to-end through this project's own implementation
(`TradernetWebsocketAdapter.market_depth` → `StreamOrderBook` →
`kase-pilot stream-orderbook`), mirroring F-27's confirmation for quotes.

---

### 2026-07-31 (continued) — `getHloc` Returns HTTP 403 for This Account (Both Candles and Trades)

**Date:** 2026-07-31
**Source:** Project owner ran `kase-pilot ticks HSBK.KZ` and, as a
diagnostic, `kase-pilot candles HSBK.KZ` against a real account, and
supplied both tracebacks directly.

#### F-29 — `getHloc` forbidden (HTTP 403) regardless of `timeframe` | Confirmed observed

Both requests reached the server (request was correctly authenticated —
otherwise the broker would return its own JSON error envelope, not an
HTTP-level failure) and were rejected with:

```
requests.exceptions.HTTPError: 403 Client Error: Forbidden for url:
https://freedom24.com/api/getHloc
```

This happened for:
- `kase-pilot ticks HSBK.KZ` (`timeframe: -1`, the trades variant added
  this session per the `get-trades` manual page)
- `kase-pilot candles HSBK.KZ` (default `timeframe`, the aggregated-candle
  variant that has existed in this project since earlier sessions)

**This rules out the new trades-specific code as the cause.** Both
variants of the same `getHloc` command fail identically, which means
`kase-pilot candles` was **never actually live-tested end-to-end in this
project before now** — its implementation was based on the SDK's
documented contract and confirmed only via source reading (the original
"historical candles" research task), never a real call with real
credentials. This 403 is the first live signal that `getHloc` may not be
usable at all for this account/key pair as currently authenticated,
independent of the `timeframe` value.

**Not yet known — do not guess:**
- Whether this is an account/API-key permission restriction (e.g.
  historical market data requires a paid tier or explicit enablement) —
  **currently the leading hypothesis**, argued below.
- Whether the "Для API V2" note on the `get-trades` manual page (POST,
  API V2) matters here — though since plain `candles` (no special API
  version implied) fails identically, this looks less likely to be the
  root cause than an account-level restriction.

**Security session requirement considered and de-prioritized (2026-07-31,
project owner + this project):** an elevated security session on top of
key-pair auth (§9) was considered and is judged unlikely to be the cause.
Reasoning: several other operations already work live, over the same
key-pair auth, with no security session involved — `getSecurityInfo`
(F-17), and `markets()`/`quotes()`/`market_depth()` over WebSocket
(F-25–F-28). Historical price/trade data (`getHloc`) is not obviously more
sensitive than those already-working operations (e.g. live personal
quotes), so it would be an unusual asymmetry for `getHloc` specifically to
require a security session while those do not. This is reasoning, not a
confirmed fact — it has not been disproven by directly testing
`getHloc` with an opened security session, only judged less likely than
the account/API-key permission-tier explanation.

**This is not a code defect in this project.** `TradernetSdkAdapter.get_trades`
and `get_candles` both correctly reach the broker and correctly surface the
broker's rejection as `ApiRequestError` (the CLI's generic "Broker/API
operation failed." message, per existing exception-mapping design) — that
part of the implementation is working exactly as intended. What's missing
is broker-side access to `getHloc`, which is outside this project's
control until diagnosed further (e.g. checking API-key permissions in the
Tradernet member area, or confirming whether a security session is
required).

---

### 2026-07-31 (continued) — Official Manual Pages for the Current News API (API V3)

**Date:** 2026-07-31
**Source:** Official manual pages supplied directly by the project owner.

#### F-30 — `tradernet-sdk`'s `get_news` uses a superseded contract; the current API is three separate API V3 commands | Confirmed as officially documented

The SDK's `Tradernet.get_news(query, symbol, story_id, limit)` sends
`cmd: getNews` with `{searchFor, ticker, storyId, limit}` — this is very
likely the reason `news` was blocked in this project's CLI as unsupported
(see CHANGELOG.md's "Известные ограничения" entry, which recorded the
failure but not its cause). The officially documented current news API is
**three separate commands**, none of which match the SDK's shape:

1. **`getNewsProvidersList`** — `POST https://tradernet.com/api/getNewsProvidersList`,
   body `{"lang": "en"}` (or `null`/omitted for current app language).
   Returns `{"list": [{"alias", "name", "newsLanguage"}, ...]}`. Known
   provider aliases: `fbrokerkz`, `Oninvest`, `OninvestCompanyNews`.
2. **`getNewsList`** — `POST https://tradernet.com/api/getNewsList`, body
   `{"ticker", "provider", "lang", "take", "skip"}` (all optional except
   `take`/`skip`; `take` range 1–100). Returns
   `{"list": [NewsItem...], "total", "take", "skip"}`, where `NewsItem`
   has `id`, `title`, `provider`, `providerAlias`, `lang`, `date`, `url`,
   `sentiment` (`negative`/`positive`/`neutral`/`null`; `mixed` is
   normalized to `neutral` server-side), `tickers` (array), `images`
   (array of URLs).
3. **`getNewsDetail`** — `POST https://tradernet.com/api/getNewsDetail`,
   body `{"id": <int>}`. Returns a single `NewsItem`-shaped object plus
   `text` (formatted HTML) and `timeZone`.

All three follow the same per-command-URL, JSON-body POST shape already
confirmed for the live REST contract (F-17/F-24) — labelled "API V3" on
these pages, consistent with `Core.authorized_request`'s default
`version=3`. None of the three are implemented by the SDK — they must be
called via the generic `authorized_request(cmd, params)`, same pattern
already used for `getAllSecurities` (F-24) and `getTrades`/`getHloc`
(this session).

**Error shape differs from the previously-documented common envelope:**
these three commands return `{"error": "...", "code": <int>}` — e.g.
`{"error": "Validation failed", "code": 400}` or
`{"error": "Новость не найдена", "code": 404}` — using an `error` key,
not the `errMsg` key seen in older documentation (§17, F-08). Whether
`code` here maps to HTTP status directly (400, 404) or is a
broker-specific application code that happens to reuse HTTP-like numbers
is not confirmed.

**Not yet live-tested.** Per this project's own rule, these should be
called live with real credentials before being relied upon, the same way
`getSecurityInfo` was in F-17.

---

### 2026-07-31 (continued) — All Three News Commands Also Return HTTP 403

**Date:** 2026-07-31
**Source:** Project owner ran `kase-pilot news-providers`, `news-list`,
and `news-detail` against a real account and supplied all three
tracebacks directly.

#### F-31 — `getNewsProvidersList`, `getNewsList`, `getNewsDetail` all return HTTP 403, same pattern as `getHloc` (F-29) | Confirmed observed

All three commands failed identically to F-29's `getHloc` finding:

```
requests.exceptions.HTTPError: 403 Client Error: Forbidden for url:
https://freedom24.com/api/getNewsProvidersList
https://freedom24.com/api/getNewsList
https://freedom24.com/api/getNewsDetail
```

**This rules out an implementation or protocol issue conclusively.**
Source inspection confirms `Tradernet.security_info()` (F-17, confirmed
**working**) and the generic `authorized_request()` used by
`get_trades`/`get_news_providers`/`list_news`/`get_news_detail` (all
**failing** with 403) go through the exact same code path — same
signing, same header scheme, same default `version=3`. The only variable
between the working and failing calls is the `cmd` value itself.

**This is now a clear pattern, not an isolated failure:** of the REST
commands exercised so far, `getSecurityInfo` succeeds; `getHloc`,
`getNewsProvidersList`, `getNewsList`, `getNewsDetail` all fail with 403.
Meanwhile every WebSocket stream tried (`markets`, `quotes`,
`market_depth`) succeeds. This strengthens the account/API-key
permission-tier hypothesis from F-29 (over the security-session
hypothesis, already de-prioritized there) — it now looks like this
specific API key has access to basic instrument/market data (REST
`getSecurityInfo`, all tried WebSocket streams) but not to a broader set
of REST commands (historical data, news), which is consistent with a
tiered/gated API-key permission model rather than a single all-or-nothing
switch.

**No further code investigation is productive here.** The next step is
account-side: checking API-key permissions/scopes in the Tradernet member
area, or contacting their support, to find out which commands this key is
actually entitled to call. This project's implementations of `get_trades`,
`get_news_providers`, `list_news`, and `get_news_detail` are considered
correct and complete pending that account-side resolution — no code
change is expected to fix this.

---

### 2026-07-31 (continued) — Security Session Opened; `getHloc` Still Returns 403

**Date:** 2026-07-31
**Source:** Project owner opened a security session on the account (exact
method not specified — presumably via the broker's own UI, not this
project's code, since `SecuritySession`/`security.py` remains an
unimplemented skeleton) and re-ran `kase-pilot candles HSBK.KZ`.

#### F-32 — Security session does not resolve the `getHloc` 403 | Confirmed observed, hypothesis disproven

Same failure as F-29, after a security session was opened:

```
requests.exceptions.HTTPError: 403 Client Error: Forbidden for url:
https://freedom24.com/api/getHloc
```

**This empirically disproves the security-session hypothesis** that was
already de-prioritized by reasoning in F-29 — now it is disproven by a
direct test, not just judged unlikely. Opening a security session had no
effect on this 403.

**This leaves the account/API-key permission-tier hypothesis as the only
remaining explanation** consistent with all evidence so far (F-29, F-31,
F-32): `getSecurityInfo` and all tried WebSocket streams work regardless
of session state; `getHloc` and all three news commands fail regardless
of session state. The distinguishing factor is which command is being
called, not the authentication/session state — strongly suggesting a
per-command permission scope tied to the API key itself (e.g. a paid-tier
gate on historical/news data), not anything this project's code or the
account's session state can influence.

**Next step remains account-side, unchanged from F-29/F-31:** check
API-key permissions/scopes or tariff in the Tradernet member area, or
contact their support, to confirm which commands this key is entitled to
call.

---

### 2026-07-31 (continued) — Level 2 (Portfolio/Orders) Verification Begins

**Date:** 2026-07-31
**Source:** Project owner ran `kase-pilot summary` against a real account.

#### F-33 — `getPositionJson` (portfolio/account summary) also returns HTTP 403 | Confirmed observed

```
requests.exceptions.HTTPError: 403 Client Error: Forbidden for url:
https://freedom24.com/api/getPositionJson
```

Same failure shape as F-29/F-31 (`getHloc`, news commands). This extends
the blocked-command list beyond historical/news data into account/
portfolio data, which was not previously tested live in this project.
`GetAccountSummary`/`AccountService.account_summary()` (backing
`summary`/`portfolio`/`watch`) is affected.

**Still to test:** `trades` (`get_trades_history`), `orders`
(`get_placed`), `orders-history` (`get_historical`) — Level 2 items not
yet live-tested at all in this project before this session.

#### F-34 — All remaining Level 2 commands also return HTTP 403; working hypothesis revised to "market-data-only key" | Confirmed observed

Continuing from F-33, the project owner ran the remaining three Level 2
commands. All failed identically:

| Command | Broker `cmd` | Result |
|---|---|---|
| `orders` | `getNotifyOrderJson` | 403 |
| `trades --from ... --to ...` | `getTradesHistory` | 403 |
| `orders-history` | `getOrdersHistory` | 403 |

**Full picture across this session's live testing, all against the same
account/API key:**

| Command | Broker `cmd` | Transport | Result |
|---|---|---|---|
| `info` | `getSecurityInfo` | REST | ✅ Confirmed (F-17) |
| `stream-quotes` | `quotes` | WebSocket | ✅ Confirmed (F-25/F-27) |
| `stream-orderbook` | `orderBook` | WebSocket | ✅ Confirmed (F-28) |
| (markets status smoke test) | `markets` | WebSocket | ✅ Confirmed (F-25/F-26) |
| `candles` / `ticks` | `getHloc` | REST | ❌ 403 (F-29) |
| `news-providers` | `getNewsProvidersList` | REST | ❌ 403 (F-31) |
| `news-list` | `getNewsList` | REST | ❌ 403 (F-31) |
| `news-detail` | `getNewsDetail` | REST | ❌ 403 (F-31) |
| `summary`/`portfolio`/`watch` | `getPositionJson` | REST | ❌ 403 (F-33) |
| `orders` | `getNotifyOrderJson` | REST | ❌ 403 (this entry) |
| `trades` | `getTradesHistory` | REST | ❌ 403 (this entry) |
| `orders-history` | `getOrdersHistory` | REST | ❌ 403 (this entry) |

**Working hypothesis revised.** The earlier framing ("historical/news data
requires a higher tier") undersold the pattern. With account/portfolio/
order data now also blocked, the more accurate description is: **this API
key appears to have market-data-only access** — exactly one REST command
works (`getSecurityInfo`, a single-instrument lookup) plus the WebSocket
streams already confirmed (`quotes`, `orderBook`, `markets`). Every other
REST command tried — spanning historical data, news, and all account/
portfolio/order data — is blocked. This is consistent with a
"market-data" or "quotes-only" API-key tier that explicitly excludes
account-level and historical REST access, as opposed to a full trading
account tier.

**This has scope implications for the project, not just this account.**
Levels 2 and the REST parts of Level 1 (candles/trades/news) cannot be
verified further, and cannot be used by anyone with a similarly-scoped
key, until the key's permissions are resolved account-side. Nothing here
suggests a code defect — every failure follows the same confirmed-correct
request path as the one working REST call.

**Next step unchanged, now higher priority:** check the API key's
permissions/scope/tariff in the Tradernet member area, or contact their
support, specifically asking whether this key can be upgraded/reconfigured
for account and historical-data access, or whether a different key
(e.g. tied to a funded/live trading account rather than a market-data
subscription) is required.

---

### 2026-08-03 — All 403s Resolved; F-29/F-31/F-33/F-34 Conclusions Retracted

**Date:** 2026-08-03
**Source:** Tradernet support replied to the ticket; project owner then
re-ran the previously failing commands.

#### F-35 — Every previously-403 command now succeeds | Confirmed observed; supersedes F-29, F-31, F-33, F-34

**Support's reply (paraphrased):** the API key is a single unified key that
already covers account and history; there is no per-key permissions list in
the member area; the restriction is not tariff-related. They asked for the
403 response body text to diagnose further.

**Before that body could be captured, the 403s stopped occurring.** A
diagnostic script (`tools/research/capture_403_body.py`, gitignored) written
to capture the 403 body instead found every command succeeding:

| Command | Broker `cmd` | Previous | Now |
|---|---|---|---|
| `summary`/`portfolio`/`watch` | `getPositionJson` | 403 (F-33) | ✅ Real portfolio data |
| `candles` | `getHloc` | 403 (F-29) | ✅ Full history |
| `ticks` | `getHloc` (`timeframe: -1`) | 403 (F-29) | ✅ (via same endpoint) |
| `news-providers` | `getNewsProvidersList` | 403 (F-31) | ✅ |
| `news-list` | `getNewsList` | 403 (F-31) | ✅ (empty list for HSBK.KZ) |
| `news-detail` | `getNewsDetail` | 403 (F-31) | ✅ |
| `orders` | `getNotifyOrderJson` | 403 (F-34) | ✅ |
| `trades` | `getTradesHistory` | 403 (F-34) | ✅ |
| `orders-history` | `getOrdersHistory` | 403 (F-34) | ✅ |

**Retracted conclusions.** The "market-data-only API key" hypothesis
(F-34) and the tiered-permission framing (F-29, F-31, F-33) are **wrong**
and are retracted. Support states the key always covered these operations.
Those entries are kept for the record — the observations in them were
accurate; the interpretation built on top of them was not.

**Root cause of the 403 period: not established.** Candidate explanations,
none confirmed, none to be presented as fact:

- A transient server-side or infrastructure condition (WAF, rate limiting,
  deployment) that has since cleared.
- Something changed account-side after the support ticket was opened,
  whether or not support acted deliberately.
- The security session the owner opened (F-32) taking effect later than the
  immediate retest performed at the time.

Since the 403 response body was never captured, this cannot be resolved
retrospectively. **If 403s recur, capture the body first** — the
diagnostic script exists for exactly that.

**Methodological note for this project:** F-34's confident "working
hypothesis revised" section was built by pattern-matching across
observations without any direct evidence about the cause. It read as a
finding but was an inference. Support's one-line correction overturned it
entirely. Observations (what a request returned) and interpretations (why)
should stay clearly separated in this file, and interpretations should be
labelled as provisional even when the pattern looks strong.

#### F-36 — `getHloc` live response shape confirmed for a KASE instrument | Confirmed observed

`kase-pilot candles HSBK.KZ` returned a full historical series. Top-level
keys of the response:

- `hloc` — `{ticker: [[high, low, open, close], ...]}`. Column order
  matches the SDK README's own documented usage
  (`columns=["high", "low", "open", "close"]`), and the sample values are
  consistent with it (e.g. `[364.80000001, 360.90999999, 364.8, 360.91]`).
  Note the visible floating-point noise in the first two columns
  (`364.80000001`, `360.90999999`) — the broker appears to send
  high/low with tiny epsilon offsets; do not assume exact equality with
  open/close values.
- `vl` — `{ticker: [volume, ...]}`, integers, aligned by index with `hloc`.
- `xSeries` — `{ticker: [unix_timestamp_seconds, ...]}`, aligned by index.
  Earliest observed value `1262206800` (Jan 2010) despite `info.firstDate`
  reporting `03.23.2015` — the series predates the reported first date;
  reason not established.
- `info` — `{ticker: {...}}` with the same instrument-metadata shape
  already confirmed for `getSecurityInfo` in F-17 (`id`, `nt_ticker`,
  `short_name`, `currency`, `min_step`, `lot`, `mkt_name`, `firstDate`,
  nested `mrkt`). Confirms `mkt_name: "KASE"`, `currency: "KZT"`.
- `maxSeries` — `{ticker: <latest timestamp>}`.
- `took` — float, server-side processing time.

This is a distinct, richer shape from the `getHloc` trades-mode response
documented for `timeframe: -1` (which the manual describes as returning
`series`/`info`/`took`). The two modes of the same command return
differently-shaped payloads.

#### F-37 — `getNewsList` live response confirmed; empty for HSBK.KZ | Confirmed observed

`kase-pilot news-list --ticker HSBK.KZ --take 5` returned:

```json
{"list": [], "total": 0, "take": 5, "skip": 0}
```

Exactly the documented shape (F-30), including the documented
"empty list plus `total: 0` when nothing matches" behaviour, and echoing
back the requested `take`/`skip`. The command works; this particular
ticker simply has no news from the providers available to this account.
Whether any KASE instrument has news coverage from the known providers
(`fbrokerkz`, `Oninvest`, `OninvestCompanyNews`) is not yet established —
worth testing without a ticker filter, or with a different ticker.
