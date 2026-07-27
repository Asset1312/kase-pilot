"""Internal adapter for the officially linked Tradernet SDK."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from tradernet import Tradernet

from kase_pilot.broker.models import JsonValue
from kase_pilot.core.exceptions import ApiRequestError, ValidationError


class TradernetSdkAdapter:
    """Expose the confirmed ``getSecurityInfo`` operation through the SDK."""

    def __init__(self, client: Tradernet) -> None:
        self._client = client

    def get_security_info(
        self,
        ticker: str,
        *,
        sup: bool = True,
    ) -> dict[str, JsonValue]:
        try:
            response: Any = self._client.security_info(ticker, sup=sup)
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        if not isinstance(response, Mapping):
            raise ValidationError(
                "Tradernet SDK returned a non-mapping security information response"
            )

        return cast(dict[str, JsonValue], dict(response))
