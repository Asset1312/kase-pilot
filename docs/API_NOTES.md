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

- Tradernet API documentation portal — https://tradernet.com/tradernet-api
  *(Partially Confirmed as official — see Research Log F-01)*
- Freedom24 mirror — https://freedom24.com/tradernet-api
  *(same content as above)*
- GitHub repository — https://github.com/tradernet/tn.api
  *(Partially Confirmed as official — see Research Log F-01)*
- Freedom Broker support correspondence — TBD

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

> Source: https://tradernet.com/tradernet-api and https://github.com/tradernet/tn.api
> (Partially Confirmed as official — see Research Log F-01)

| Capability | Available | Notes |
|---|---|---|
| REST API | Partially Confirmed | Base URL confirmed from repository README; official ownership of source not yet proven |
| WebSocket streaming | Partially Confirmed | Socket.IO-based; servers confirmed from repository README |
| FIX protocol | TBD | Out of scope regardless |
| Sandbox / test environment | Partially Confirmed | Demo WebSocket server at wsbeta.tradernet.ru; REST sandbox TBD |
| API versioning scheme | TBD | — |
| Official Python SDK | Partially Confirmed | `tradernet-sdk` package exists on PyPI; official ownership not yet confirmed |

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

The REST API uses an MD5-based signature scheme embedded in the request body.
There is no HTTP authentication header for REST requests. See Research Log F-04
for details.

A credential key pair is required: a public key and a secret key, generated
via the user profile interface. See Research Log F-05 and F-06.

### REST Signature Algorithm (Partially Confirmed)

Source: https://github.com/tradernet/tn.api README — Partially Confirmed
(official ownership of the repository is not yet proven)

The `sig` request body field is described as the MD5 hash of the concatenation
of all `parameter_name=parameter_value` pairs sorted alphabetically by parameter
name (applied recursively for nested parameters), with the `API_SECRET`
appended at the end of the string.

> ⚠️ The official documentation describes this as MD5 of a concatenated string
> with an appended secret. This is **not the same as HMAC-MD5**. It is a
> keyed MD5 constructed by concatenation. Whether the implementation in
> `tn-crypto.js` differs is not yet confirmed — the source has not been read.
> Until verified, this is described as an "MD5-based signature algorithm".

### Credential Identifiers (Partially Confirmed)

The repository README uses the terms `public_key`, `api_key`, and `apiKey`
interchangeably in different contexts. The relationship between:

- the `public_key` / `api_key` credential value;
- the `uid` REST request body field;
- the `apiKey` WebSocket auth field;

is **not yet confirmed** from an authoritative request example or verified
source code. These may be the same value or may differ. Do not assume identity
until confirmed.

### HTTP Authentication Headers

No authentication header is used in the REST protocol. Authentication is
carried entirely in the request body (`uid` and `sig` fields).

### Open Questions

- Does the key pair expire? If so, what is the TTL and renewal process?
- Can key pair permissions be restricted to read-only operations?
- Is IP allowlisting mandatory or optional alongside key-based auth?
- What is the exact relationship between `public_key`, `uid`, and `apiKey`?
- Does the REST API return a specific HTTP status code (e.g. 401) on
  authentication failure, or always HTTP 200 with an error code in the body?
- What is the exact algorithm in `tn-crypto.js` for the WebSocket signature?
- Which specific read-only endpoints require an active security session?

---

## 9. Security Sessions

Security sessions are an additional authorisation layer confirmed to exist in
the API. They are separate from the standard key-pair authentication.
See Research Log F-10.

Confirmed session types (from repository README):

| `safety_type_id` | Type | Notes |
|---|---|---|
| 2 | Hardware token (Aladdin) | May not be enabled for all accounts |
| 3 | SMS confirmation | Confirmed enabled |
| 4 | Login/password without additional confirmation | Confirmed enabled |

Security sessions have a finite lifetime: fields `expire_datetime` and `expire`
(remaining milliseconds) are confirmed in API responses.

Authentication via the API key pair (programmatic Node.js flow) is documented
as bypassing the need to open a security session through the normal
SMS/token flow. The exact scope of this bypass for read-only REST endpoints
is **Partially Confirmed**.

### Open Questions

- Which REST endpoints require a security session?
- Can a security session opened via the API key pair flow be used to authorise
  read-only requests, or only trading requests?
- Can a security session be refreshed without re-authentication?

---

## 10. REST API Overview

### Base URL (Partially Confirmed)

Source: https://github.com/tradernet/tn.api README

```
https://tradernet.ru/api/
```

HTTP method: POST. GET is stated as permitted for testing only.
Data format: JSON.

> ⚠️ This URL is from the repository README. Official ownership of the
> repository is not yet proven. Treat as Partially Confirmed until verified
> from the documentation portal directly.

### Authentication in Requests

Authentication is embedded in the JSON request body via the `sig` field.
No HTTP authentication header is used.

### Common Request Body Fields

| Field | Description | Required |
|---|---|---|
| `uid` | User identifier | Yes, for non-anonymous requests |
| `cmd` | Command name | Yes |
| `params` | Command parameters (object) | Yes |
| `sig` | MD5-based signature | Yes |

### Pagination

TBD — pagination mechanism and parameters are not yet confirmed.

### Endpoint Index

| Resource | Method | Path | Notes |
|---|---|---|---|
| Session / user info | TBD | TBD | — |
| Portfolio summary | TBD | TBD | — |
| Open positions | TBD | TBD | — |
| Cash balances | TBD | TBD | — |
| Current quotes | TBD | TBD | — |
| Historical quotes | TBD | TBD | Confirmed command name: `getQuotesHistory` |
| Current orders | TBD | TBD | — |
| Historical orders | TBD | TBD | — |
| Trade history | TBD | TBD | — |
| Reports | TBD | TBD | — |

---

## 11. WebSocket Overview

> REST integration is completed first. WebSocket work begins only after the REST
> layer is stable.

### Protocol (Partially Confirmed)

The WebSocket layer uses **Socket.IO**, not a raw WebSocket protocol.
Source: https://github.com/tradernet/tn.api README

### WebSocket Servers (Partially Confirmed)

```
Production: https://ws.tradernet.ru
Demo:       https://wsbeta.tradernet.ru
```

### Authentication Flow (Partially Confirmed)

After connecting, emit an `auth` Socket.IO event with:

```
data = { apiKey: <public_key>, cmd: 'getAuthInfo', nonce: <timestamp> }
sig  = <MD5-based signature computed with secret_key>
ws.emit('auth', data, sig, callback)
```

The exact signature algorithm used for WebSocket (`tn-crypto.js`) has not yet
been verified from source code.

### Heartbeat / Ping-Pong

TBD — heartbeat interval and expected behaviour are not yet confirmed.

### Available Streams (Partially Confirmed)

| Stream | Event name | Notes |
|---|---|---|
| Stock quotes | `notifyQuotes` / `q` | Confirmed |
| Market depth | `notifyOrderBook` / `b` | Confirmed |
| Market status | `notifyMarkets` / `markets` | Confirmed |
| Security sessions | `notifySessions` / `sessions` | Confirmed |
| Portfolio updates | `notifyPortfolio` / `portfolio` | Confirmed |
| Orders updates | `notifyOrders` / `orders` | Confirmed |

### Reconnection Policy

TBD

---

## 12. Portfolio Data

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

- **Endpoint:** TBD
- **Method:** TBD
- **Parameters:** TBD
- **Response schema:** TBD

### Historical Quotes

- **Endpoint:** Confirmed command `getQuotesHistory` via POST to base URL
- **Method:** POST
- **Parameters:** `ticker`, `interval`, `from`, `to` (Partially Confirmed)
- **Response schema:** TBD

---

## 14. Orders and Trades

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

- **Available:** TBD
- **Endpoint:** TBD
- **Formats:** TBD (PDF, CSV, JSON?)
- **Parameters:** TBD

---

## 16. Response Formats (Partially Confirmed)

Source: https://github.com/tradernet/tn.api README

All REST responses are JSON with the following confirmed envelope:

| Field | Description | Required |
|---|---|---|
| `code` | Integer application status code | Yes |
| `data` | Response payload (type varies by command) | No |
| `errMsg` | Error message string | No |

Field naming convention (snake_case vs camelCase) varies by endpoint.
Full conventions are not yet confirmed.

Date/time format: not yet confirmed.

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
| 2 | What is the exact relationship between `public_key`, `uid` (REST), and `apiKey` (WebSocket)? | Critical | Open |
| 3 | Is the REST signature plain MD5-with-concatenated-secret, or true HMAC-MD5? | Critical | Open |
| 4 | Does the key pair expire? If so, what is the TTL and renewal process? | High | Open |
| 5 | Can key pair permissions be restricted to read-only operations? | High | Open |
| 6 | Is IP allowlisting mandatory or optional for key-based authentication? | High | Open |
| 7 | Which specific REST endpoints require a security session? | High | Open |
| 8 | Does the REST API return HTTP 401 on authentication failure, or always HTTP 200 with an error code? | High | Open |
| 9 | What is the exact algorithm in `tn-crypto.js` for the WebSocket signature? | High | Open |
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
| AD-006 | `broker/auth.py` will not be fully implemented until the signature algorithm and credential mapping are confirmed. | Implementing against unverified assumptions produces a module that appears complete but contains a latent defect. |

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

#### F-01 — Documentation portal and GitHub repository located | Partially Confirmed

Two documentation portals were found:
- https://tradernet.com/tradernet-api
- https://freedom24.com/tradernet-api (mirrors the same content)

A GitHub repository was found at https://github.com/tradernet/tn.api, owned by
the `tradernet` GitHub organisation.

**Limitation:** The documentation portal pages render navigation only; content
is loaded client-side via JavaScript and is not accessible to automated
fetching. The fact that the GitHub organisation is named `tradernet` does not
by itself prove the repository is officially maintained. No explicit link from
the documentation portal to the GitHub repository was confirmed. Official
ownership requires either a verified domain link or an explicit statement from
Freedom Broker. Until then, this repository is treated as **Partially
Confirmed** as official.

---

#### F-02 — The API is branded as Tradernet API | Confirmed

Freedom Broker (Freedom24) is the parent entity. The API surface is branded
Tradernet. All documentation and SDK references use the Tradernet name.

---

#### F-03 — REST base URL | Partially Confirmed

Source: https://github.com/tradernet/tn.api README

```
https://tradernet.ru/api/
```

HTTP method: POST (GET permitted for testing only). Data format: JSON.

Status is Partially Confirmed because official ownership of the repository
source is not yet proven.

---

#### F-04 — REST authentication: MD5-based signature in request body, no HTTP header | Partially Confirmed

Source: https://github.com/tradernet/tn.api README (section "Формирование подписи")

The REST API does not use an HTTP authentication header. Authentication uses a
`sig` field in the JSON request body.

The `sig` field is described as the MD5 hash of the concatenation of all
`parameter_name=parameter_value` pairs, sorted alphabetically by parameter
name and applied recursively for nested parameters, with the `API_SECRET`
appended at the end of the concatenated string.

> ⚠️ **Accuracy note:** This construction — MD5 of (sorted parameters +
> appended secret) — is **not HMAC-MD5**. HMAC uses a defined padding and
> XOR construction around the hash function. This is a keyed MD5 by
> concatenation, which is a different and weaker construction. It is described
> here as an "MD5-based signature algorithm" until the source code of
> `tn-crypto.js` is read and the exact algorithm is verified.

Status: Partially Confirmed (source ownership not yet proven).

---

#### F-05 — Credential is a key pair: public key and secret key | Partially Confirmed

Source: https://github.com/tradernet/tn.api README (Socket.IO Node.js example)

The credential consists of two values:
- A public key (variously called `public_key`, `api_key`, `apiKey`)
- A secret key (variously called `secret_key`, `private_key`, `secKey`)

The secret key is never transmitted. Only the signature derived from it is sent.

**Unconfirmed relationship:** The repository README uses `uid` as a REST request
body field and `apiKey` as a WebSocket field, both appearing to carry the
public key value. However, no authoritative request example explicitly confirms
that `public_key == uid == apiKey`. This mapping is **Unknown** until a
verified request example or source code confirms it.

---

#### F-06 — Key pair generated in user profile | Partially Confirmed

Source: https://github.com/tradernet/tn.api README

> "Сгенерировать публичный и секретный ключи на странице профиля."

Generation is done through the user interface. Status: Partially Confirmed.

---

#### F-07 — WebSocket uses Socket.IO; auth via `auth` event with nonce | Partially Confirmed

Source: https://github.com/tradernet/tn.api README (Node.js example)

WebSocket uses the Socket.IO library. After connecting, the client emits an
`auth` event with:
- `data`: `{ apiKey: pubKey, cmd: 'getAuthInfo', nonce: Date.now() }`
- `sig`: a signature computed by `tncrypto.sign(data, secKey)`

The exact algorithm inside `tncrypto.sign` has not yet been verified from
source code.

WebSocket servers stated in the README:
- Production: `https://ws.tradernet.ru`
- Demo: `https://wsbeta.tradernet.ru`

---

#### F-08 — REST error response envelope | Partially Confirmed

Source: https://github.com/tradernet/tn.api README

All REST responses are JSON with fields `code` (int), `data` (mixed, optional),
and `errMsg` (string, optional).

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

#### F-10 — Security sessions exist and have a finite lifetime | Partially Confirmed

Source: https://github.com/tradernet/tn.api README (Socket.IO section)

Security sessions are an additional authorisation layer. Confirmed session
types:
- `safety_type_id: 2` — Hardware token (Aladdin)
- `safety_type_id: 3` — SMS confirmation
- `safety_type_id: 4` — Login/password (no additional confirmation)

Session responses include `expire_datetime` and `expire` (remaining ms),
confirming finite lifetime.

The README states that the API key pair flow (programmatic auth) bypasses the
normal security session opening process. Which read-only REST endpoints require
an active session is not enumerated. **Partially Confirmed.**

---

#### F-11 — A Python SDK package exists on PyPI; official ownership not confirmed | Partially Confirmed

Source: https://pypi.org/project/tradernet-sdk/0.4.2/

A package named `tradernet-sdk` exists on PyPI and accepts `public_key`,
`secret_key`, `login`, and `passwd` as credentials, consistent with the
key-pair model. Official ownership by Freedom Broker / Tradernet is not
confirmed. KASE Pilot will not use this package as a dependency.

---

#### Impact on `broker/auth.py`

The research changes the implementation model in the following confirmed ways:

1. **No HTTP header for REST.** The current `auth.py` design — a callable
   returning a header dict — is the wrong abstraction for this API.
2. **REST authentication requires signing the request body**, not injecting a
   header.
3. **The credential is a key pair**, not a single key.
4. **WebSocket authentication is a distinct protocol** (Socket.IO `auth` event
   with a nonce and signature).
5. **The exact signature algorithm and credential field mapping remain
   unconfirmed.** Full implementation of `auth.py` must wait until these are
   verified.

---

**Unresolved questions after this session:**

- Is the GitHub repository https://github.com/tradernet/tn.api officially
  maintained by Freedom Broker / Tradernet?
- What is the exact algorithm in `tn-crypto.js`? Is it keyed MD5 by
  concatenation, or true HMAC-MD5?
- What is the exact relationship between `public_key`, `uid` (REST body),
  and `apiKey` (WebSocket)?
- Does the key pair expire? If so, what is the TTL?
- Which specific read-only REST endpoints require a security session?
- Does the REST API return HTTP 401 on authentication failure, or always
  HTTP 200 with `code: 12`?