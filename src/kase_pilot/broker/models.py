"""Broker-independent type aliases for JSON-decoded API responses.

These aliases describe the structure of raw payloads as returned by
``json.loads`` before any validation or mapping to domain models.

Domain models (Position, Order, Quote, etc.) are defined separately once
their fields are verified against official Freedom Broker API documentation.
"""

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
type RawPayload = dict[str, JsonValue]
