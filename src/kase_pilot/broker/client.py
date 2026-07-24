"""Central transport layer for the kase_pilot.broker package.

BrokerClient is the single point through which every REST interaction with
the broker API passes.  It owns request assembly.

Authentication is supplied through constructor injection.  BrokerClient
never imports auth.py.  The shape of the authentication provider and the
authentication contribution it returns are defined once the Tradernet
authentication contract is confirmed.

See docs/BROKER_ARCHITECTURE.md §3.1 and docs/API_NOTES.md §21.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class BrokerClient:
    """Skeleton HTTP transport for the broker.

    Parameters
    ----------
    base_url:
        Base URL of the broker REST API.
    auth_provider:
        Callable that produces authentication data before each request.
        Injected at construction; never imported from auth.py.
    """

    base_url: str
    auth_provider: Callable[..., object] = field(repr=False)

    def request(self, *args: object, **kwargs: object) -> object:
        """Issue a request to the broker REST API.

        Not implemented.  HTTP transport, request assembly, and the mapping
        of authentication data into the request are deferred until the
        broker authentication contract is confirmed.

        Raises
        ------
        NotImplementedError
            Always.
        """
        raise NotImplementedError
