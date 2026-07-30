from typing import Any

from kase_pilot.application import GetTariffs


class FakeMarketService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls = 0

    def get_tariffs(self) -> dict[str, Any]:
        self.calls += 1
        return self.response


def test_execute_delegates_and_preserves_response_identity() -> None:
    response = {"result": {"tariffs": [{"name": "Investor"}]}}
    market_service = FakeMarketService(response)
    use_case = GetTariffs(market_service)  # type: ignore[arg-type]

    result = use_case.execute()

    assert market_service.calls == 1
    assert result is response


def test_get_tariffs_is_available_from_application_package() -> None:
    from kase_pilot.application import GetTariffs as PublicGetTariffs

    assert PublicGetTariffs is GetTariffs
