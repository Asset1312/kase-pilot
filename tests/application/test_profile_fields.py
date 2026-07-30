from typing import Any

from kase_pilot.application import GetProfileFields


class FakeMarketService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[object] = []

    def get_profile_fields(self, reception: object) -> dict[str, Any]:
        self.calls.append(reception)
        return self.response


def test_execute_delegates_and_preserves_response_identity() -> None:
    reception = 17
    response = {"result": {"fields": [{"name": "address"}]}}
    market_service = FakeMarketService(response)
    use_case = GetProfileFields(market_service)  # type: ignore[arg-type]

    result = use_case.execute(reception)

    assert market_service.calls == [reception]
    assert result is response


def test_get_profile_fields_is_available_from_application_package() -> None:
    from kase_pilot.application import GetProfileFields as PublicGetProfileFields

    assert PublicGetProfileFields is GetProfileFields
