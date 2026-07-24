"""Security session lifecycle skeleton for the kase_pilot.broker package.

SecuritySession owns the lifecycle of an elevated security session.  It is
separate from the standard API-key authentication lifecycle owned by
BrokerAuth.

SecuritySession does not decide which endpoints require an elevated session.
That knowledge belongs to each service module.  SecuritySession only manages
the session itself once a service module determines one is needed.

Transport interaction required to open or confirm a session is supplied
through constructor injection.  SecuritySession never imports client.py or
auth.py.

All methods are deferred until the Tradernet security session protocol is
confirmed from official documentation.

See docs/BROKER_ARCHITECTURE.md §3.3 and docs/API_NOTES.md §9.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class SecuritySession:
    """Skeleton security session lifecycle manager.

    Parameters
    ----------
    transport:
        Callable used to perform any network interaction required to open
        or confirm a session.  Injected at construction; never imported
        from client.py or auth.py.
    """

    transport: Callable[..., object] = field(repr=False)

    def open(self) -> object:
        """Initiate a security session.

        Not implemented.  The Tradernet security session initiation
        protocol has not been confirmed from official documentation.

        Raises
        ------
        NotImplementedError
            Always.
        """
        raise NotImplementedError

    def confirm(self) -> object:
        """Confirm a pending security session.

        Not implemented.  Confirmation method, payload shape, and response
        structure are deferred until the protocol is confirmed.

        Raises
        ------
        NotImplementedError
            Always.
        """
        raise NotImplementedError

    def is_valid(self) -> object:
        """Return whether the current session is still valid.

        Not implemented.  Session lifetime fields and validity criteria
        are deferred until the protocol is confirmed.

        Raises
        ------
        NotImplementedError
            Always.
        """
        raise NotImplementedError

    def close(self) -> object:
        """Close the current security session.

        Not implemented.  Session termination protocol is deferred until
        the Tradernet security session contract is confirmed.

        Raises
        ------
        NotImplementedError
            Always.
        """
        raise NotImplementedError
