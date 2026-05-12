"""Custom exceptions for Dagster CLI."""


class DagsterCLIError(Exception):
    """Base exception for Dagster CLI."""


class ConfigError(DagsterCLIError):
    """Configuration related errors."""


class AuthenticationError(DagsterCLIError):
    """Authentication related errors."""


class APIError(DagsterCLIError):
    """API communication errors."""


class NotFoundError(APIError):
    """Resource not found — raised by explicit-lookup methods (not list endpoints)."""


class ValidationError(DagsterCLIError):
    """Input validation errors."""
