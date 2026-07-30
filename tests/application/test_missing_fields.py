from typing import Any

from kase_pilot.application import CheckMissingFields


class FakeMarketService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[object, object]] = []

    def check_missing_fields(
        self,
        step: object,
        office: object,
    ) -> dict[str, Any]:
        self.calls.append((step, office))
        return self.response


def test_execute_delegates_and_preserves_response_identity() -> None:
    step = 3
    office = " Almaty "
    response = {"result": {"not_completed": [{"name": "address"}]}}
    market_service = FakeMarketService(response)
    use_case = CheckMissingFields(market_service)  # type: ignore[arg-type]

    result = use_case.execute(step, office)

    assert market_service.calls == [(step, office)]
    assert market_service.calls[0][1] is office
    assert result is response


def test_check_missing_fields_is_available_from_application_package() -> None:
    from kase_pilot.application import (
        CheckMissingFields as PublicCheckMissingFields,
    )

    assert PublicCheckMissingFields is CheckMissingFields
