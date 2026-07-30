from typing import Any

from kase_pilot.application import GetOptions


class FakeMarketService:
    def __init__(self, response: list[dict[str, Any]]) -> None:
        self.response = response
        self.calls: list[tuple[object, object]] = []

    def get_options(
        self,
        underlying: object,
        exchange: object,
    ) -> list[dict[str, Any]]:
        self.calls.append((underlying, exchange))
        return self.response


def test_execute_delegates_and_preserves_response_identity() -> None:
    underlying = " AaPl "
    exchange = " UsA "
    response = [{"ticker": "AAPL.US"}]
    market_service = FakeMarketService(response)
    use_case = GetOptions(market_service)  # type: ignore[arg-type]

    result = use_case.execute(underlying, exchange)

    assert market_service.calls == [(underlying, exchange)]
    assert market_service.calls[0][0] is underlying
    assert market_service.calls[0][1] is exchange
    assert result is response


def test_get_options_is_available_from_application_package() -> None:
    from kase_pilot.application import GetOptions as PublicGetOptions

    assert PublicGetOptions is GetOptions
