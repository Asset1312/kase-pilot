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

- Official Freedom Broker API documentation — TBD
- Official Tradernet documentation — TBD
- Freedom Broker support correspondence

---

## 3. Terminology

**Broker** — Freedom Broker / Tradernet.

**API** — The official HTTP API provided by Freedom Broker.

**Security Session** — Additional authorization required for selected operations.

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

## 3. Official API Capabilities

> Source: TBD — official Freedom Broker / Tradernet API documentation URL not yet confirmed.

| Capability | Available | Notes |
|---|---|---|
| REST API | TBD | — |
| WebSocket streaming | TBD | — |
| FIX protocol | TBD | Out of scope regardless |
| Sandbox / test environment | TBD | — |
| API versioning scheme | TBD | — |
| Official SDK | TBD | — |

---

## 4. KASE Pilot MVP Scope

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

## 5. Out-of-Scope Functionality

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

## 6. Authentication

### Method

TBD — the safest authentication method supported by the API will be used once
confirmed.

### Open Questions

- How is an API key created? Via the web portal, API call, or support request?
- Can API key permissions be restricted to read-only operations?
- Does the API key expire? If so, what is the TTL and renewal process?
- Is IP allowlisting or IP restriction supported?
- Which HTTP headers are required to authenticate a request?
- Is two-factor authentication required for API access?
- Which specific operations require an active security session in addition to
  the API key?

### Known Headers

| Header | Value | Notes |
|---|---|---|
| TBD | TBD | — |

### Base URL

```
TBD
```

---

## 7. Security Sessions

The API may require a security session for certain operations. The following
confirmation methods have been mentioned in preliminary research but their exact
behaviour is not yet verified:

- **SMS code** — a one-time code delivered via SMS
- **Web token** — a token issued through a web-based flow
- **Electronic digital signature (EDS)** — a cryptographic signature

> ⚠️ No claims are made about how these methods work until verified against
> official documentation or sandbox testing.

### Open Questions

- Which endpoints require an active security session?
- How is a security session initiated and confirmed?
- What is the lifetime of a security session?
- How is session expiry communicated in the API response?
- Can a security session be refreshed without re-authentication?

---

## 8. REST API Overview

### Base URL

```
TBD
```

### Common Request Headers

| Header | Value |
|---|---|
| TBD | TBD |

### Pagination

TBD — pagination mechanism (cursor, offset, page number) and relevant
parameters are not yet confirmed.

### Endpoint Index

| Resource | Method | Path | Notes |
|---|---|---|---|
| Session / user info | TBD | TBD | — |
| Portfolio summary | TBD | TBD | — |
| Open positions | TBD | TBD | — |
| Cash balances | TBD | TBD | — |
| Current quotes | TBD | TBD | — |
| Historical quotes | TBD | TBD | — |
| Current orders | TBD | TBD | — |
| Historical orders | TBD | TBD | — |
| Trade history | TBD | TBD | — |
| Reports | TBD | TBD | — |

---

## 9. WebSocket Overview

> REST integration is completed first. WebSocket work begins only after the REST
> layer is stable.

### WebSocket URL

```
TBD
```

### Heartbeat / Ping-Pong

TBD — heartbeat interval and expected behaviour are not yet confirmed.

### Available Streams

| Stream | Description | Notes |
|---|---|---|
| TBD | TBD | — |

### Reconnection Policy

TBD

---

## 10. Portfolio Data

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

## 11. Quotes and Market Data

### Current Quotes

- **Endpoint:** TBD
- **Method:** TBD
- **Parameters:** TBD
- **Response schema:** TBD

### Historical Quotes

- **Endpoint:** TBD
- **Method:** TBD
- **Parameters:** TBD — expected: ticker, interval, date range
- **Response schema:** TBD

---

## 12. Orders and Trades

### Current Orders

- **Endpoint:** TBD
- **Method:** TBD
- **Parameters:** TBD
- **Response schema:** TBD

### Historical Orders

- **Endpoint:** TBD
- **Method:** TBD
- **Parameters:** TBD — expected: date range, status filter
- **Response schema:** TBD

### Trade History

- **Endpoint:** TBD
- **Method:** TBD
- **Parameters:** TBD
- **Response schema:** TBD

---

## 13. Reports

- **Available:** TBD
- **Endpoint:** TBD
- **Formats:** TBD (PDF, CSV, JSON?)
- **Parameters:** TBD

---

## 14. Response Formats

TBD — expected JSON; exact envelope structure, field naming convention
(snake_case vs camelCase), and date/time format not yet confirmed.

### Anticipated Envelope

```
TBD
```

---

## 15. Error Handling

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

### Broker Error Response Schema

TBD — expected fields: error code, error message. Exact structure not confirmed.

### Retry Policy

TBD — which error codes are considered transient and safe to retry?

---

## 16. Rate Limits

| Dimension | Limit | Notes |
|---|---|---|
| Requests per second | TBD | — |
| Requests per minute | TBD | — |
| Requests per day | TBD | — |
| WebSocket messages per second | TBD | — |
| Penalty / backoff policy | TBD | — |

---

## 17. Logging and Secrets Policy

### Permitted in Logs

- Endpoint paths (without query parameters containing credentials)
- HTTP status codes
- Sanitised error messages
- Request timestamps and latency

### Forbidden in Logs

The following must **never** appear in any log output, at any log level:

- API keys
- Passwords
- SMS codes
- Session tokens
- Authorization headers or their values
- Any sensitive account data (account numbers, personal identifiers)

Logging inside the `kase_pilot.broker` package must be reviewed against this
list before every commit.

---

## 18. Data Storage Policy

- API responses are validated before any data is written to storage.
- Raw API responses are not persisted unless explicitly required for debugging
  in a non-production environment.
- Credentials and tokens are never written to the database or log files.
- Storage schema decisions will be documented separately when the storage layer
  is designed.

---

## 19. Open Questions

| # | Question | Priority | Status |
|---|---|---|---|
| 1 | What is the official API documentation URL? | Critical | Open |
| 2 | Is a sandbox or test environment available? | Critical | Open |
| 3 | How is an API key created and scoped? | Critical | Open |
| 4 | Can API keys be restricted to read-only? | High | Open |
| 5 | What is the API key TTL and renewal process? | High | Open |
| 6 | Is IP restriction supported for API keys? | High | Open |
| 7 | Which endpoints require a security session? | High | Open |
| 8 | What is the security session lifetime? | High | Open |
| 9 | What is the exact rate limit policy? | High | Open |
| 10 | What is the WebSocket heartbeat interval? | Medium | Open |
| 11 | Are broker reports available via API? | Medium | Open |
| 12 | What date/time format does the API use? | Medium | Open |
| 13 | What is the field naming convention in responses? | Medium | Open |
| 14 | Is API versioning in the URL path or headers? | Medium | Open |

---

## 20. Architectural Decisions

| ID | Decision | Rationale |
|---|---|---|
| AD-001 | All broker code is isolated in `kase_pilot.broker`. | Prevents broker-specific logic from leaking into core modules; simplifies future broker swaps. |
| AD-002 | REST is integrated before WebSocket. | REST is simpler to test and debug; WebSocket is added only after the data model is stable. |
| AD-003 | Every API error is mapped to a KASE Pilot exception at the broker boundary. | Callers outside `kase_pilot.broker` never handle raw broker errors; the exception hierarchy is the public contract. |
| AD-004 | Responses are validated before storage. | Prevents corrupted or unexpected data from reaching the database. |
| AD-005 | FIX protocol is out of scope. | Complexity is disproportionate to MVP requirements. |

---

## 21. Research Log

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

- All items listed in Section 19.