from typing import Any

from kase_pilot.application import ListSecuritySessions


class FakeMarketService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls = 0

    def list_security_sessions(self) -> dict[str, Any]:
        self.calls += 1
        return self.response


def test_execute_delegates_and_preserves_response_identity() -> None:
    response = {"result": {"sessions": [{"market": "KASE"}]}}
    market_service = FakeMarketService(response)
    use_case = ListSecuritySessions(market_service)  # type: ignore[arg-type]

    result = use_case.execute()

    assert market_service.calls == 1
    assert result is response


def test_list_security_sessions_is_available_from_application_package() -> None:
    from kase_pilot.application import (
        ListSecuritySessions as PublicListSecuritySessions,
    )

    assert PublicListSecuritySessions is ListSecuritySessions
