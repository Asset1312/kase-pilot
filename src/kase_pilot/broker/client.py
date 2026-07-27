"""Central transport layer for the kase_pilot.broker package.

BrokerClient is the single point through which every REST interaction with
the broker API passes.  It owns:

- HTTP session lifecycle (via an injected transport callable).
- Request assembly: merging cmd, params, and the authentication contribution
  produced by the injected auth provider into the final POST body.
- JSON response parsing and envelope validation.
- Mapping of broker application-level error codes to KASE Pilot exceptions.

BrokerClient does NOT:

- Compute signatures or nonces — that is BrokerAuth's responsibility.
- Assume the value of uid or any credential field name — those are unresolved
  (see docs/API_NOTES.md §21 Q2, Q3).
- Add authentication headers — REST authentication is carried in the request
  body only (docs/API_NOTES.md §8).
- Implement retries, security sessions, or WebSocket support.
- Import auth.py, security.py, or any service module.

broker.models may be imported for broker-specific payload types.

Authentication boundary
-----------------------
BrokerClient calls the injected auth provider with an immutable view of the
current request context (cmd + params) and receives a mapping of additional
body fields to merge.  BrokerClient decides where those fields go; BrokerAuth
decides what they contain.  The exact field names (uid, sig, etc.) are
determined by the provider — BrokerClient treats them as opaque.  If any auth
field name collides with a reserved request field (``cmd`` or ``params``), a
ValidationError is raised before the request is sent.

HTTP transport
--------------
BrokerClient does not call urllib directly.  An HTTP transport callable is
injected at construction.  The callable receives a prepared
``urllib.request.Request`` object and returns raw response bytes.  A default
implementation backed by ``urllib.request.urlopen`` is provided for
production use.

See docs/BROKER_ARCHITECTURE.md §3.1 and docs/API_NOTES.md §21.
"""

from __future__ import annotations

import json
import types
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from kase_pilot.broker.models import JsonValue
from kase_pilot.core.exceptions import (
    ApiRequestError,
    AuthenticationError,
    ValidationError,
)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

# Auth provider: receives an immutable request context, returns body fields.
AuthProvider = Callable[[Mapping[str, Any]], Mapping[str, Any]]

# HTTP transport: receives a prepared Request, returns raw response bytes.
HttpTransport = Callable[[urllib.request.Request], bytes]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Reserved request body field names that auth fields must not overwrite.
_RESERVED_FIELDS: frozenset[str] = frozenset({"cmd", "params"})

# Broker application-level error codes that map to AuthenticationError.
# Source: docs/API_NOTES.md §17, Research Log F-08.
_AUTH_ERROR_CODES: frozenset[int] = frozenset({4, 7, 8, 12})

# Broker application-level success code.
_CODE_OK: int = 0


def _default_transport(request: urllib.request.Request) -> bytes:
    """Default HTTP transport using urllib.request.urlopen.

    Raises
    ------
    ApiRequestError
        On any HTTP or network-level error.
    """
    try:
        with urllib.request.urlopen(request) as response:
            return response.read()  # type: ignore[no-any-return]
    except urllib.error.HTTPError as exc:
        raise ApiRequestError(f"HTTP {exc.code} from broker API: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ApiRequestError(
            f"Transport error communicating with broker API: {exc.reason}"
        ) from exc


@dataclass
class BrokerClient:
    """HTTP transport for the Tradernet broker REST API.

    Parameters
    ----------
    base_url:
        Base URL of the broker REST API (e.g. ``https://tradernet.ru/api/``).
    auth_provider:
        Callable ``(request_context) -> body_fields``.  Receives an immutable
        mapping containing ``cmd`` and ``params`` for the current request and
        returns a mapping of authentication fields to merge into the POST
        body.  Injected at construction; never imported from auth.py.
    http_transport:
        Callable ``(urllib.request.Request) -> bytes``.  Performs the actual
        HTTP POST and returns raw response bytes.  Defaults to a
        ``urllib.request.urlopen`` wrapper.  Inject a test double to avoid
        network calls in tests.
    """

    base_url: str
    auth_provider: AuthProvider = field(repr=False)
    http_transport: HttpTransport = field(default=_default_transport, repr=False)

    def request(self, cmd: str, params: dict[str, Any]) -> JsonValue:
        """Send a command to the broker REST API and return the response data.

        A shallow copy of ``params`` is made immediately so that the caller's
        dictionary is not retained or mutated.  The auth provider receives an
        immutable view of the request context via ``types.MappingProxyType``.
        Auth fields are merged after the request fields; any collision with
        ``cmd`` or ``params`` raises ValidationError before the request is
        sent.

        Parameters
        ----------
        cmd:
            The Tradernet command name (e.g. ``"getQuotesHistory"``).
        params:
            Command-specific parameters.  A shallow copy is made; the
            original is not modified or retained.

        Returns
        -------
        JsonValue
            The ``data`` field of the Tradernet JSON response envelope, or
            ``None`` when the broker returns no data payload.

        Raises
        ------
        AuthenticationError
            On broker error codes 4 (bad signature), 7 (unknown uid),
            8 (unknown IP), or 12 (access denied).
        ValidationError
            When an auth field collides with a reserved field name, the
            response body is not valid JSON, or the response envelope is
            malformed.
        ApiRequestError
            On any other broker-level error or HTTP transport failure.
        """
        params_copy: dict[str, Any] = dict(params)

        context: Mapping[str, Any] = types.MappingProxyType(
            {"cmd": cmd, "params": params_copy}
        )

        auth_fields: Mapping[str, Any] = self.auth_provider(context)

        collisions = _RESERVED_FIELDS & auth_fields.keys()
        if collisions:
            raise ValidationError(
                f"Authentication provider returned fields that collide with "
                f"reserved request fields: {sorted(collisions)}"
            )

        body: dict[str, Any] = {"cmd": cmd, "params": params_copy, **auth_fields}

        prepared = urllib.request.Request(
            self.base_url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        raw: bytes = self.http_transport(prepared)
        return self._parse(raw)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse(self, raw: bytes) -> JsonValue:
        """Decode ``raw`` bytes, validate the broker envelope, return data.

        Raises
        ------
        ValidationError
            When ``raw`` is not valid JSON, the envelope is malformed, or
            the ``code`` field is a boolean rather than a proper integer.
        AuthenticationError
            On broker error codes 4, 7, 8, or 12.
        ApiRequestError
            On any other non-zero broker error code.
        """
        try:
            envelope: Any = json.loads(raw)
        except UnicodeDecodeError as exc:
            raise ValidationError(f"Broker response is not valid UTF-8: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Broker response is not valid JSON: {exc}") from exc

        if not isinstance(envelope, dict):
            raise ValidationError(
                f"Unexpected broker response type: {type(envelope).__name__}"
            )

        if "code" not in envelope:
            raise ValidationError(
                "Broker response envelope missing required 'code' field."
            )

        code: Any = envelope["code"]

        # bool is a subclass of int in Python; true/false are not valid codes.
        if isinstance(code, bool) or not isinstance(code, int):
            raise ValidationError(
                f"Broker response 'code' field is not a valid integer: {code!r}"
            )

        err_msg: Any = envelope.get("errMsg")
        if err_msg is not None and not isinstance(err_msg, str):
            raise ValidationError(
                f"Broker response 'errMsg' field is not a string or null: "
                f"{type(err_msg).__name__}"
            )

        if code != _CODE_OK:
            if code in _AUTH_ERROR_CODES:
                raise AuthenticationError(
                    f"Broker authentication error (code {code})"
                    + (f": {err_msg}" if err_msg else "")
                )
            raise ApiRequestError(
                f"Broker returned error code {code}"
                + (f": {err_msg}" if err_msg else "")
            )

        data: JsonValue = envelope.get("data")
        return data
