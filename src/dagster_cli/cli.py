"""Main CLI application for Dagster CLI."""

import typer
from typing import Optional

from dagster_cli import __version__
from dagster_cli.auth import app as auth_app
from dagster_cli.commands.job import app as job_app
from dagster_cli.commands.run import app as run_app
from dagster_cli.commands.repo import app as repo_app
from dagster_cli.commands.asset import app as asset_app
from dagster_cli.commands.deployment import app as deployment_app
from dagster_cli.commands.mcp import app as mcp_app
from dagster_cli.config import Config
from dagster_cli.constants import (
    DEPLOYMENT_OPTION_NAME,
    DEPLOYMENT_OPTION_SHORT,
    DEPLOYMENT_OPTION_HELP,
)
from dagster_cli.utils.output import console, print_info
from dagster_cli.utils.tldr import print_tldr


app = typer.Typer(
    name="dgc",
    help="Dagster CLI - A command-line interface for Dagster+",
    no_args_is_help=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
    pretty_exceptions_enable=False,
)

# Add subcommands
app.add_typer(
    auth_app,
    name="auth",
    help="Authentication management - login, logout, switch profiles",
)
app.add_typer(
    job_app, name="job", help="Job operations - list, view details, run with config"
)
app.add_typer(
    run_app, name="run", help="Run management - list, view logs, check status"
)
app.add_typer(
    repo_app, name="repo", help="Repository management - list locations, reload"
)
app.add_typer(
    asset_app, name="asset", help="Asset operations - list, materialize, check health"
)
app.add_typer(
    deployment_app,
    name="deployment",
    help="Deployment management - list available deployments",
)
app.add_typer(
    mcp_app, name="mcp", help="MCP operations - start server (stdio or --http mode)"
)


def version_callback(show: bool):
    """Show version and exit."""
    if show:
        console.print(f"Dagster CLI version {__version__}")
        raise typer.Exit()


def tldr_callback(show: bool):
    """Show TLDR examples and exit."""
    if show:
        print_tldr("main")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
    tldr: bool = typer.Option(
        False,
        "--tldr",
        help="Show practical examples and exit",
        callback=tldr_callback,
        is_eager=True,
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Use specific profile", envvar="DGC_PROFILE"
    ),
):
    """
    Dagster CLI - A command-line interface for Dagster+

    Similar to GitHub's 'gh' CLI, but for Dagster+ operations.

    Get started with:

        dgc auth login

    Then explore available commands:

        dgc job list
        dgc run list
        dgc repo list

    For help on any command, use:

        dgc [command] --help
    """
    # Profile handling is done per-command, this is just for the callback
    pass


@app.command()
def status(
    deployment: Optional[str] = typer.Option(
        None,
        DEPLOYMENT_OPTION_NAME,
        DEPLOYMENT_OPTION_SHORT,
        help=DEPLOYMENT_OPTION_HELP,
    ),
):
    """Show current status and configuration."""
    config = Config()

    # Show version
    console.print(f"[bold]Dagster CLI[/bold] version {__version__}")
    console.print()

    # Check authentication
    if config.has_auth():
        profile_name = config.get_current_profile_name()
        profile = config.get_profile()

        print_info(f"Authenticated as profile '{profile_name}'")

        # Show URL with deployment if specified
        url = profile.get("url", "Unknown")
        if deployment and deployment != "prod" and url != "Unknown":
            url = url.replace("/prod", f"/{deployment}")
            print_info(f"Connected to: {url} (with --deployment {deployment})")
        else:
            print_info(f"Connected to: {url}")

        if profile.get("location"):
            print_info(f"Default location: {profile['location']}")
        if profile.get("repository"):
            print_info(f"Default repository: {profile['repository']}")
    else:
        console.print("[yellow]Not authenticated[/yellow]")
        console.print("Run 'dgc auth login' to get started")


@app.command()
def config(
    key: Optional[str] = typer.Argument(None, help="Configuration key to get/set"),
    value: Optional[str] = typer.Argument(None, help="Value to set"),
    list_all: bool = typer.Option(
        False, "--list", "-l", help="List all configuration values"
    ),
):
    """Get or set configuration values."""
    config_obj = Config()

    if list_all:
        profile = config_obj.get_profile()
        console.print("[bold]Current configuration:[/bold]")
        for k, v in profile.items():
            if k != "token":  # Don't show token
                console.print(f"  {k}: {v}")
    elif key and value:
        # Setting a value - implement in future
        print_info("Configuration setting not yet implemented")
    elif key:
        # Getting a value
        profile = config_obj.get_profile()
        if key in profile and key != "token":
            console.print(profile[key])
        else:
            console.print(f"Unknown configuration key: {key}")
    else:
        console.print("Specify a key to get, or use --list to see all")


if __name__ == "__main__":
    app()
