from typing import Any

import pytest

from kase_pilot.application import GetSymbol


class FakeMarketService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[object, object]] = []

    def get_symbol(
        self,
        symbol: object,
        lang: object = None,
    ) -> dict[str, Any]:
        self.calls.append((symbol, lang))
        return self.response


@pytest.mark.parametrize("lang", [None, " ru "])
def test_execute_delegates_and_preserves_response_identity(
    lang: str | None,
) -> None:
    symbol = " AAPL.US "
    response = {"result": {"ticker": "AAPL.US", "name": "Apple"}}
    market_service = FakeMarketService(response)
    use_case = GetSymbol(market_service)  # type: ignore[arg-type]

    result = use_case.execute(symbol, lang)

    assert market_service.calls == [(symbol, lang)]
    assert market_service.calls[0][0] is symbol
    assert market_service.calls[0][1] is lang
    assert result is response


def test_get_symbol_is_available_from_application_package() -> None:
    from kase_pilot.application import GetSymbol as PublicGetSymbol

    assert PublicGetSymbol is GetSymbol
