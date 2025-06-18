"""Test version information."""

import re
from dagster_cli import __version__


def test_version():
    """Test that version is accessible and valid."""
    assert isinstance(__version__, str)
    assert len(__version__) > 0

    # Should be either "dev" or a valid semantic version
    if __version__ != "dev":
        # Validate semantic versioning pattern (e.g., 0.1.0, 1.0.0, 1.2.3-alpha)
        semver_pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$"
        assert re.match(semver_pattern, __version__), (
            f"Invalid version format: {__version__}"
        )
