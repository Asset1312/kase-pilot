"""Custom exception hierarchy for KASE Pilot project."""


class KasePilotError(Exception):
    """Base exception for all KASE Pilot errors."""


class ConfigurationError(KasePilotError):
    """Raised when project configuration is invalid or missing."""


class BrokerError(KasePilotError):
    """Base exception for broker-related errors."""


class AuthenticationError(BrokerError):
    """Raised when broker authentication is rejected."""


class SecuritySessionError(BrokerError):
    """Raised when a broker security session is invalid or expired."""


class ApiRequestError(BrokerError):
    """Raised when a broker API request fails."""


class RateLimitError(BrokerError):
    """Raised when the broker rate limit is exceeded."""


class StorageError(KasePilotError):
    """Base exception for storage-related errors."""


class DatabaseError(StorageError):
    """Raised when a database operation fails."""


class DataIntegrityError(StorageError):
    """Raised when stored data fails an integrity check."""


class ValidationError(KasePilotError):
    """Raised when input data fails validation."""
