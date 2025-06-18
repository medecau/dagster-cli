"""Dagster CLI - A command-line interface for Dagster+."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("dagster-cli")
except PackageNotFoundError:
    # Package is not installed, fall back to a default
    __version__ = "dev"

__author__ = "Pedro"
__email__ = "me@pdbr.org"

from dagster_cli.cli import app

__all__ = ["app", "__version__"]
