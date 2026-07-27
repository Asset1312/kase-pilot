"""Tests for kase_pilot.broker.client.BrokerClient."""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

import pytest

from kase_pilot.broker.client import BrokerClient
from kase_pilot.core.exceptions import (
    ApiRequestError,
    AuthenticationError,
    ValidationError,
)

AuthProvider = Callable[[Mapping[str, Any]], Mapping[str, Any]]
HttpTransport = Callable[[urllib.request.Request], bytes]


def _response(payload: Any) -> bytes:
    """Encode a payload as JSON response bytes."""
    return json.dumps(payload).encode("utf-8")


def _ok(data: Any = None) -> bytes:
    """Build a successful broker response envelope."""
    envelope: dict[str, Any] = {"code": 0}
    if data is not None:
        envelope["data"] = data
    return _response(envelope)


def _error(code: int, message: str = "something went wrong") -> bytes:
    """Build an unsuccessful broker response envelope."""
    return _response({"code": code, "errMsg": message})


def _capturing_transport(
    response_bytes: bytes,
) -> tuple[list[urllib.request.Request], HttpTransport]:
    """Return captured requests and a fake transport."""
    captured: list[urllib.request.Request] = []

    def transport(request: urllib.request.Request) -> bytes:
        captured.append(request)
        return response_bytes

    return captured, transport


def _noop_auth(context: Mapping[str, Any]) -> dict[str, Any]:
    """Return one opaque authentication field."""
    return {"sig": "deadbeef"}


def _no_auth(context: Mapping[str, Any]) -> dict[str, Any]:
    """Return no authentication fields."""
    return {}


def _make_client(
    response_bytes: bytes,
    auth_provider: AuthProvider = _noop_auth,
    base_url: str = "https://example.com/api/",
) -> tuple[BrokerClient, list[urllib.request.Request]]:
    """Return a client connected to a capturing fake transport."""
    captured, transport = _capturing_transport(response_bytes)
    client = BrokerClient(
        base_url=base_url,
        auth_provider=auth_provider,
        http_transport=transport,
    )
    return client, captured


class TestRequestAssembly:
    def test_uses_post(self) -> None:
        client, captured = _make_client(_ok({"price": 100}))
        client.request("getQuote", {"ticker": "SBER"})
        assert captured[0].get_method() == "POST"

    def test_url_equals_base_url(self) -> None:
        client, captured = _make_client(_ok({"price": 100}))
        client.request("getQuote", {"ticker": "SBER"})
        assert captured[0].full_url == "https://example.com/api/"

    def test_content_type_header(self) -> None:
        client, captured = _make_client(_ok({"price": 100}))
        client.request("getQuote", {"ticker": "SBER"})
        assert captured[0].get_header("Content-type") == "application/json"

    def test_body_contains_cmd_params_and_auth_fields(self) -> None:
        client, captured = _make_client(_ok({"price": 100}))
        client.request("getQuote", {"ticker": "SBER"})

        assert captured[0].data is not None
        body = json.loads(captured[0].data)
        assert body == {
            "cmd": "getQuote",
            "params": {"ticker": "SBER"},
            "sig": "deadbeef",
        }

    def test_returns_data_mapping(self) -> None:
        client, _ = _make_client(_ok({"price": 100}))
        result = client.request("getQuote", {"ticker": "SBER"})
        assert result == {"price": 100}


class TestAuthProviderContext:
    def test_provider_receives_cmd_and_params(self) -> None:
        received: list[Mapping[str, Any]] = []

        def capturing_auth(context: Mapping[str, Any]) -> dict[str, Any]:
            received.append(context)
            return {}

        client, _ = _make_client(_ok(), auth_provider=capturing_auth)
        client.request("myCmd", {"k": "v"})

        assert received[0]["cmd"] == "myCmd"
        assert received[0]["params"] == {"k": "v"}

    def test_outer_context_is_immutable(self) -> None:
        mutation_error: list[BaseException] = []

        def mutating_auth(context: Mapping[str, Any]) -> dict[str, Any]:
            try:
                context["injected"] = "x"  # type: ignore[index]
            except (TypeError, AttributeError) as exc:
                mutation_error.append(exc)
            return {}

        client, _ = _make_client(_ok(), auth_provider=mutating_auth)
        client.request("myCmd", {})

        assert mutation_error

    def test_original_params_are_not_modified(self) -> None:
        original: dict[str, Any] = {"ticker": "SBER"}
        client, _ = _make_client(_ok(), auth_provider=_no_auth)
        client.request("myCmd", original)
        assert original == {"ticker": "SBER"}


@pytest.mark.parametrize("reserved", ["cmd", "params"])
class TestAuthFieldCollisions:
    def test_collision_raises_validation_error(self, reserved: str) -> None:
        def colliding_auth(context: Mapping[str, Any]) -> dict[str, Any]:
            return {reserved: "injected"}

        client, _ = _make_client(_ok(), auth_provider=colliding_auth)

        with pytest.raises(ValidationError):
            client.request("myCmd", {})

    def test_transport_is_not_called(self, reserved: str) -> None:
        def colliding_auth(context: Mapping[str, Any]) -> dict[str, Any]:
            return {reserved: "injected"}

        client, captured = _make_client(
            _ok(),
            auth_provider=colliding_auth,
        )

        with pytest.raises(ValidationError):
            client.request("myCmd", {})

        assert captured == []


@pytest.mark.parametrize("payload", [{"code": 0}, {"code": 0, "data": None}])
def test_empty_successful_data_returns_none(payload: dict[str, Any]) -> None:
    client, _ = _make_client(_response(payload), auth_provider=_no_auth)
    assert client.request("cmd", {}) is None


def test_list_data_returns_unchanged() -> None:
    data = [1, "two", None, {"nested": True}]
    client, _ = _make_client(_ok(data), auth_provider=_no_auth)
    assert client.request("cmd", {}) == data


@pytest.mark.parametrize("data", ["value", 42, 12.5])
def test_scalar_data_returns_unchanged(data: str | float) -> None:
    client, _ = _make_client(_ok(data), auth_provider=_no_auth)
    assert client.request("cmd", {}) == data


@pytest.mark.parametrize("data", [True, False])
def test_bool_data_returns_unchanged(data: bool) -> None:
    client, _ = _make_client(_ok(data), auth_provider=_no_auth)
    assert client.request("cmd", {}) is data


@pytest.mark.parametrize("code", [4, 7, 8, 12])
def test_authentication_error_mapping(code: int) -> None:
    client, _ = _make_client(
        _error(code, "auth failed"),
        auth_provider=_no_auth,
    )

    with pytest.raises(AuthenticationError) as exc_info:
        client.request("cmd", {})

    message = str(exc_info.value)
    assert str(code) in message
    assert "auth failed" in message


def test_general_broker_error_mapping() -> None:
    client, _ = _make_client(
        _error(99, "boom"),
        auth_provider=_no_auth,
    )

    with pytest.raises(ApiRequestError) as exc_info:
        client.request("cmd", {})

    message = str(exc_info.value)
    assert "99" in message
    assert "boom" in message


@pytest.mark.parametrize("err_msg", [123, True, ["error"], {"message": "error"}])
def test_non_string_err_msg_raises_validation_error(err_msg: Any) -> None:
    client, _ = _make_client(
        _response({"code": 99, "errMsg": err_msg}),
        auth_provider=_no_auth,
    )

    with pytest.raises(ValidationError):
        client.request("cmd", {})


def test_invalid_json_raises_validation_error() -> None:
    client, _ = _make_client(b"not json", auth_provider=_no_auth)

    with pytest.raises(ValidationError):
        client.request("cmd", {})


@pytest.mark.parametrize(
    "payload",
    [
        [{"code": 0}],
        {"data": "missing code"},
        {"code": "zero", "data": {}},
        {"code": True, "data": {}},
        {"code": False, "data": {}},
    ],
)
def test_invalid_envelope_shape_raises_validation_error(
    payload: Any,
) -> None:
    client, _ = _make_client(_response(payload), auth_provider=_no_auth)

    with pytest.raises(ValidationError):
        client.request("cmd", {})


def test_transport_api_request_error_propagates_unchanged() -> None:
    original = ApiRequestError("network failure")

    def failing_transport(request: urllib.request.Request) -> bytes:
        raise original

    client = BrokerClient(
        base_url="https://example.com/api/",
        auth_provider=_no_auth,
        http_transport=failing_transport,
    )

    with pytest.raises(ApiRequestError) as exc_info:
        client.request("cmd", {})

    assert exc_info.value is original


class TestCallerParamsIsolation:
    def test_auth_provider_receives_a_different_outer_dict(self) -> None:
        received_params: list[Any] = []

        def capturing_auth(context: Mapping[str, Any]) -> dict[str, Any]:
            received_params.append(context["params"])
            return {}

        caller_params: dict[str, Any] = {"ticker": "SBER"}
        client, _ = _make_client(_ok(), auth_provider=capturing_auth)
        client.request("cmd", caller_params)

        assert received_params[0] is not caller_params

    def test_top_level_addition_does_not_affect_caller(self) -> None:
        def mutating_auth(context: Mapping[str, Any]) -> dict[str, Any]:
            copied_params = context["params"]
            assert isinstance(copied_params, dict)
            copied_params["injected"] = "x"
            return {}

        caller_params: dict[str, Any] = {"ticker": "SBER"}
        client, _ = _make_client(_ok(), auth_provider=mutating_auth)
        client.request("cmd", caller_params)

        assert caller_params == {"ticker": "SBER"}

    def test_top_level_removal_does_not_affect_caller(self) -> None:
        def mutating_auth(context: Mapping[str, Any]) -> dict[str, Any]:
            copied_params = context["params"]
            assert isinstance(copied_params, dict)
            copied_params.pop("ticker", None)
            return {}

        caller_params: dict[str, Any] = {"ticker": "SBER"}
        client, _ = _make_client(_ok(), auth_provider=mutating_auth)
        client.request("cmd", caller_params)

        assert caller_params == {"ticker": "SBER"}
