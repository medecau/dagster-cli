"""Custom exceptions for Dagster CLI."""


class DagsterCLIError(Exception):
    """Base exception for Dagster CLI."""

    pass


class ConfigError(DagsterCLIError):
    """Configuration related errors."""

    pass


class AuthenticationError(DagsterCLIError):
    """Authentication related errors."""

    pass


class APIError(DagsterCLIError):
    """API communication errors."""

    pass


class ValidationError(DagsterCLIError):
    """Input validation errors."""

    pass
