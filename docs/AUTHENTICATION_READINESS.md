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
- An external README describes REST authentication in the request body without
  an HTTP authentication header, but this is not yet a confirmed live REST
  contract (`API_NOTES.md` §8).

The architectural and security rules above are confirmed project decisions.
Broker-specific behaviour derived from the external README remains only
partially confirmed.

---

## 2. Unknowns

The following information is required to implement `BrokerAuth` but is not
yet confirmed by any source.

| # | Unknown |
|---|---------|
| 1 | Whether the external README's body-based, no-header description matches the live REST API |
| 2 | Whether authentication uses an API key, a session token, or another scheme |
| 3 | Whether the API key is long-lived or expires |
| 4 | The API key TTL if expiration exists |
| 5 | Whether credential renewal is required and how it works |
| 6 | Whether authentication data is computed and supplied for every request or established once for a session |
| 7 | Whether a login endpoint must be called to exchange credentials for a token |
| 8 | Whether two-factor authentication is required for API access |
| 9 | Which operations require a security session on top of standard auth |
| 10 | Whether WebSocket connections use the same auth scheme as REST |
| 11 | What error response the broker returns on authentication failure (status code, body schema) |
| 12 | Whether IP restriction affects authentication behaviour |
| 13 | The official API documentation URL |

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

Everything that touches the actual HTTP contract — the header name, the value
format, the authentication scheme — cannot be written without inventing
behaviour that may be wrong.

The correct interim state is the current one:
`src/kase_pilot/broker/auth.py` intentionally remains empty until the live REST
contract is confirmed. No placeholder signer or speculative provider should be
added.

---

## 5. Next Research Steps

The following must be resolved, in order, before implementation can proceed.

- [ ] Obtain the official Freedom Broker / Tradernet API documentation URL.
      This is the prerequisite for every item below.
- [ ] Confirm whether the external README's body-based authentication
      description matches the live REST API.
- [ ] Confirm the authentication scheme and exact REST contract from an
      authoritative source.
- [ ] Confirm whether the API key expires. If yes, record the TTL and the
      renewal mechanism.
- [ ] Confirm whether authentication data is computed and supplied for every
      request or established once for a session.
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
