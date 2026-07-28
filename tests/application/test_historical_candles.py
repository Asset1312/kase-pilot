"""Tests for the historical-candles application use case."""

from __future__ import annotations

from typing import Any

import pytest

from kase_pilot.application import GetHistoricalCandles


class FakeMarketService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[object, dict[str, object]]] = []

    def get_candles(
        self,
        symbol: object,
        **kwargs: object,
    ) -> dict[str, Any]:
        self.calls.append((symbol, kwargs))
        return self.response


def test_execute_uses_broker_defaults_without_transforming_symbol_or_response() -> None:
    symbol = "  aApL.Us  "
    candles = [
        {
            "timestamp": "2024-01-01T09:30:00Z",
            "open": "185.10",
            "high": "186.20",
            "low": "184.90",
            "close": "186.00",
            "unknown_field": {"nested": [True, None]},
        },
        {
            "timestamp": "2024-01-01T10:30:00Z",
            "open": "186.00",
            "high": "187.00",
            "low": "185.80",
            "close": "186.75",
        },
    ]
    response = {"candles": candles}
    market_service = FakeMarketService(response)
    use_case = GetHistoricalCandles(market_service)  # type: ignore[arg-type]

    result = use_case.execute(symbol)

    assert market_service.calls == [(symbol, {})]
    assert market_service.calls[0][0] is symbol
    assert result is response
    assert result["candles"] is candles
    assert result["candles"][0]["open"] == "185.10"  # type: ignore[index]
    assert result["candles"][0]["timestamp"] == "2024-01-01T09:30:00Z"  # type: ignore[index]


def test_execute_passes_explicit_timeframe_without_start_or_end() -> None:
    symbol = "AAPL.US"
    timeframe = int("3600")
    response = {"candles": []}
    market_service = FakeMarketService(response)
    use_case = GetHistoricalCandles(market_service)  # type: ignore[arg-type]

    result = use_case.execute(symbol, timeframe=timeframe)

    assert market_service.calls == [(symbol, {"timeframe": timeframe})]
    assert market_service.calls[0][0] is symbol
    assert market_service.calls[0][1]["timeframe"] is timeframe
    assert "start" not in market_service.calls[0][1]
    assert "end" not in market_service.calls[0][1]
    assert result is response


@pytest.mark.parametrize("timeframe", [0, -1])
def test_execute_does_not_validate_timeframe(timeframe: int) -> None:
    market_service = FakeMarketService({"candles": []})
    use_case = GetHistoricalCandles(market_service)  # type: ignore[arg-type]

    use_case.execute("AAPL.US", timeframe=timeframe)

    assert market_service.calls == [
        ("AAPL.US", {"timeframe": timeframe}),
    ]


def test_market_service_exception_propagates_unchanged_without_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    original = RuntimeError("market service failed")

    class FailingMarketService:
        def get_candles(self, symbol: object) -> dict[str, Any]:
            raise original

    use_case = GetHistoricalCandles(FailingMarketService())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        use_case.execute("AAPL.US")

    assert exc_info.value is original
    assert capsys.readouterr() == ("", "")


def test_get_historical_candles_is_public_application_export() -> None:
    from kase_pilot import application

    assert application.GetHistoricalCandles is GetHistoricalCandles
