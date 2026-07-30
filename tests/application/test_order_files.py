from typing import Any

import pytest

from kase_pilot.application import GetOrderFiles


class FakeMarketService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[object, object]] = []

    def get_order_files(
        self,
        order_id: object,
        internal_id: object,
    ) -> dict[str, Any]:
        self.calls.append((order_id, internal_id))
        return self.response


@pytest.mark.parametrize(
    ("order_id", "internal_id"),
    [(17, None), (None, 23), (17, 23)],
)
def test_execute_delegates_and_preserves_response_identity(
    order_id: int | None,
    internal_id: int | None,
) -> None:
    response = {"result": {"files": [{"name": "document.pdf"}]}}
    market_service = FakeMarketService(response)
    use_case = GetOrderFiles(market_service)  # type: ignore[arg-type]

    result = use_case.execute(order_id, internal_id)

    assert market_service.calls == [(order_id, internal_id)]
    assert result is response


def test_get_order_files_is_available_from_application_package() -> None:
    from kase_pilot.application import GetOrderFiles as PublicGetOrderFiles

    assert PublicGetOrderFiles is GetOrderFiles
