from typing import Any

import pytest

from kase_pilot.application import ExportSecurities


class FakeMarketService:
    def __init__(self, response: list[dict[str, Any]]) -> None:
        self.response = response
        self.calls: list[tuple[object, object]] = []

    def export_securities(
        self,
        symbols: object,
        fields: object = None,
    ) -> list[dict[str, Any]]:
        self.calls.append((symbols, fields))
        return self.response


@pytest.mark.parametrize("fields", [None, ["ticker", "ltp"]])
def test_execute_delegates_and_preserves_response_identity(
    fields: list[str] | None,
) -> None:
    symbols = ["AAPL", "MSFT"]
    response = [{"ticker": "AAPL"}, {"ticker": "MSFT"}]
    market_service = FakeMarketService(response)
    use_case = ExportSecurities(market_service)  # type: ignore[arg-type]

    result = use_case.execute(symbols, fields)

    assert market_service.calls == [(symbols, fields)]
    assert market_service.calls[0][0] is symbols
    assert market_service.calls[0][1] is fields
    assert result is response


def test_export_securities_is_available_from_application_package() -> None:
    from kase_pilot.application import ExportSecurities as PublicExportSecurities

    assert PublicExportSecurities is ExportSecurities
