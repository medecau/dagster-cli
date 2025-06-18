"""Test version information."""

from dagster_cli import __version__


def test_version():
    """Test that version is accessible."""
    # When running tests, the package might not be installed,
    # so we might get "dev" or the actual version
    assert __version__ in ("0.1.0", "dev")
    assert isinstance(__version__, str)
