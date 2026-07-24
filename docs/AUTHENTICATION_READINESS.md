# Authentication Readiness Review

> **Date:** 2025-07-24
> **Purpose:** Determine what must be confirmed before `broker/auth.py` can be
> safely implemented.
> **Sources reviewed:** `docs/API_NOTES.md`, `docs/BROKER_ARCHITECTURE.md`

---

## 1. Confirmed Facts

The following are explicitly stated in the project documentation. Nothing is
inferred.

- Authentication using the safest supported method is in scope for MVP
  (`API_NOTES.md` §4).
- API keys, passwords, SMS codes, session tokens, and authorisation headers
  must never appear in log output at any level (`API_NOTES.md` §17).
- Secrets must never be committed to the repository in any form
  (`API_NOTES.md` §4, Principle 6).
- `BrokerAuth` must not import `BrokerClient`. If future authentication
  requires network interaction, the architecture allows a transport abstraction
  to be injected (`BROKER_ARCHITECTURE.md` §3.2).
- `BrokerAuth` is internal to the `broker` package and is not exported from
  `__init__.py` (`BROKER_ARCHITECTURE.md` §3.10).
- Authentication failure must raise `AuthenticationError`
  (`API_NOTES.md` §15).
- The authentication method, header names, and header value format are all
  marked TBD (`API_NOTES.md` §6).

That is the complete set of confirmed facts. Every other aspect of
authentication is unknown.

---

## 2. Unknowns

The following information is required to implement `BrokerAuth` but is not
yet confirmed by any source.

| # | Unknown |
|---|---------|
| 1 | The exact HTTP header name that carries the credential |
| 2 | The header value format (raw key, `Bearer <token>`, custom prefix, etc.) |
| 3 | Whether authentication uses an API key, a session token, or another scheme |
| 4 | Whether the API key is long-lived or expires |
| 5 | The API key TTL if expiration exists |
| 6 | Whether credential renewal is required and how it works |
| 7 | Whether additional companion headers are required alongside the auth header |
| 8 | Whether authentication is per-request or per-session |
| 9 | Whether a login endpoint must be called to exchange credentials for a token |
| 10 | Whether two-factor authentication is required for API access |
| 11 | Which operations require a security session on top of standard auth |
| 12 | Whether WebSocket connections use the same auth scheme as REST |
| 13 | What error response the broker returns on authentication failure (status code, body schema) |
| 14 | Whether IP restriction affects authentication behaviour |
| 15 | The official API documentation URL |

---

## 3. Impact on Architecture

| Unknown | BrokerAuth | BrokerClient | SecuritySession | WebSocket | Service modules |
|---------|------------|--------------|-----------------|-----------|-----------------|
| Exact header name | Direct — cannot produce headers without it | Indirect — injects whatever BrokerAuth provides | None | Indirect — same provider injected | None |
| Header value format | Direct — determines how the key is serialised | None | None | Indirect | None |
| Auth scheme (key vs token vs other) | Direct — determines class structure | Indirect — affects what the injected provider produces | None | Indirect | None |
| Key expiration and renewal | Direct — determines whether a refresh path must exist | None | None | None | None |
| Companion headers | Direct — `__call__` must return all required headers | None | None | Indirect | None |
| Per-request vs per-session | Direct — affects whether state must be held between calls | Direct — affects session lifecycle | None | Indirect | None |
| Login endpoint required | Direct — would require an injected transport callable | Direct — would handle the resulting token | None | Indirect | None |
| 2FA requirement | Potentially direct — may add a confirmation step | None | Potentially direct | None | None |
| Which ops need security session | None | None | Direct — determines scope of `SecuritySession` | None | Direct — each service must know its own requirements |
| WebSocket auth scheme | None | None | None | Direct | None |
| Auth failure response schema | Indirect — affects error mapping | Direct — determines when to raise `AuthenticationError` | None | Indirect | None |

---

## 4. Implementation Readiness

**`broker/auth.py` should not be fully implemented now.**

Shipping a placeholder header name (e.g. `"<BROKER_AUTH_HEADER_NAME>"`) is not
a safe interim state: it creates a module that appears complete but contains a
defect that will fail silently if the placeholder is not replaced before the
first real API call. A placeholder is itself an assumption, and therefore
violates the core project principle: never turn assumptions about the Freedom
Broker API into code.

The only parts that can be written without assumptions are:

- The structural skeleton: a minimal authentication provider implementation
  that accepts a credential value and exposes a callable interface.
- Validation that the credential is non-empty.
- The secrets policy enforcement: `__repr__` suppression, no logging of
  values.
- Raising `AuthenticationError` on invalid configuration.

Everything that touches the actual HTTP contract — the header name, the value
format, the authentication scheme — cannot be written without inventing
behaviour that may be wrong.

The correct interim state is the current one: a skeleton with the structural
contract defined and the HTTP-specific part left unimplemented and clearly
marked in the architecture documents as blocked on API research.

---

## 5. Next Research Steps

The following must be resolved, in order, before implementation can proceed.

- [ ] Obtain the official Freedom Broker / Tradernet API documentation URL.
      This is the prerequisite for every item below.
- [ ] Locate the authentication section of the documentation. Confirm the
      exact name and format of the authorisation header.
- [ ] Confirm the authentication scheme: static API key, short-lived token,
      session cookie, or other.
- [ ] Confirm whether the API key expires. If yes, record the TTL and the
      renewal mechanism.
- [ ] Confirm whether any companion headers are required alongside the auth
      header (e.g. client ID, account ID, content type).
- [ ] Confirm whether authentication is per-request (header on every call) or
      per-session (one login call, then a session identifier).
- [ ] If a login endpoint exists, record its path, request schema, and
      response schema.
- [ ] Confirm whether two-factor authentication is required for API access.
- [ ] Confirm which specific endpoints require a security session in addition
      to standard authentication.
- [ ] Confirm the HTTP status code and response body structure returned on
      authentication failure.
- [ ] Confirm whether WebSocket connections use the same authentication scheme
      as REST or a separate one.
- [ ] Record all findings in `docs/API_NOTES.md` Research Log before writing
      any code.