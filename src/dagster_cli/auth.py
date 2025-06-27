"""Authentication commands for Dagster CLI."""

import typer
from typing import Optional

from dagster_cli.config import Config
from dagster_cli.client import DagsterClient
from dagster_cli.utils.output import (
    console,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_profiles_table,
)
from dagster_cli.utils.errors import ConfigError
from dagster_cli.utils.tldr import print_tldr


app = typer.Typer(
    help="""[bold]Authentication management[/bold]

[bold cyan]Available commands:[/bold cyan]
  [green]login[/green]    Authenticate with Dagster+ [dim](--url, --token, --profile)[/dim]
  [green]logout[/green]   Remove stored credentials [dim][--profile][/dim]
  [green]status[/green]   Show authentication status
  [green]switch[/green]   Switch between profiles [dim]PROFILE_NAME[/dim]

[dim]Use 'dgc auth COMMAND --help' for detailed options[/dim]""",
    rich_markup_mode="rich",
)


@app.callback(invoke_without_command=True)
def auth_callback(
    ctx: typer.Context,
    tldr: bool = typer.Option(
        False,
        "--tldr",
        help="Show practical examples and exit",
        is_eager=True,
    ),
):
    """Authentication management callback."""
    if tldr:
        print_tldr("auth")
        raise typer.Exit()

    # If no command was provided, show help
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


@app.command()
def login(
    url: Optional[str] = typer.Option(
        None, "--url", help="Dagster+ deployment URL (e.g., org.dagster.cloud/prod)"
    ),
    token: Optional[str] = typer.Option(
        None, "--token", help="Dagster+ User Token", hide_input=True
    ),
    profile: str = typer.Option(
        "default", "--profile", "-p", help="Profile name to save credentials"
    ),
    location: Optional[str] = typer.Option(
        None, "--location", "-l", help="Default repository location"
    ),
    repository: Optional[str] = typer.Option(
        None, "--repository", "-r", help="Default repository name"
    ),
):
    """Authenticate with Dagster+."""
    # Interactive prompts if not provided
    if not url:
        url = typer.prompt("Dagster+ URL", type=str)
    if not token:
        token = typer.prompt("User Token", type=str, hide_input=True)

    # Validate by attempting to connect
    with console.status("Validating credentials..."):
        try:
            # Create temporary client to test credentials
            config = Config()
            config.set_profile(profile, url, token, location, repository)

            # Test the connection
            client = DagsterClient(profile)
            info = client.get_deployment_info()

            # If we didn't get location/repository, try to detect them
            if not location or not repository:
                if repos := info.get("repositoriesOrError", {}).get("nodes", []):
                    first_repo = repos[0]
                    if not location:
                        location = first_repo.get("location", {}).get("name")
                    if not repository:
                        repository = first_repo.get("name", "__repository__")

                    # Update profile with discovered values
                    if location or repository:
                        config.set_profile(profile, url, token, location, repository)

            # Set as current profile
            config.set_current_profile(profile)

            print_success("Successfully authenticated to Dagster+!")
            print_info(f"Profile '{profile}' saved and set as current")

            if location:
                print_info(f"Default location: {location}")
            if repository:
                print_info(f"Default repository: {repository}")

        except Exception as e:
            # Clean up failed profile
            try:
                config.delete_profile(profile)
            except ConfigError:
                pass
            print_error(f"Authentication failed: {str(e)}")
            raise typer.Exit(1) from e


@app.command()
def logout(
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Profile to logout (default: current profile)"
    ),
    all: bool = typer.Option(False, "--all", help="Logout from all profiles"),
):
    """Clear stored credentials."""
    config = Config()

    if all:
        # Clear all profiles
        profiles = list(config.list_profiles().keys())
        if not profiles:
            print_warning("No profiles found")
            return

        if typer.confirm(f"Remove all {len(profiles)} profiles?"):
            for prof in profiles:
                config.delete_profile(prof)
            print_success("All profiles removed")
    else:
        # Clear specific profile
        if not profile:
            profile = config.get_current_profile_name()

        if profile not in config.list_profiles():
            print_error(f"Profile '{profile}' not found")
            raise typer.Exit(1)

        config.delete_profile(profile)
        print_success(f"Logged out from profile '{profile}'")


@app.command()
def status():
    """Show authentication status."""
    config = Config()
    current = config.get_current_profile_name()
    profiles = config.list_profiles()

    if not profiles:
        print_warning("No authentication profiles found")
        print_info("Run 'dgc auth login' to authenticate")
        return

    print_info(f"Current profile: {current}")
    console.print()

    # Test current profile connection
    if current in profiles:
        try:
            client = DagsterClient()
            info = client.get_deployment_info()
            version = info.get("version", "Unknown")
            print_success(f"Connected to Dagster+ (version: {version})")
        except Exception as e:
            print_error(f"Connection failed: {str(e)}")

    # Show all profiles
    console.print("\n[bold]Profiles:[/bold]")
    print_profiles_table(profiles, current)


@app.command()
def switch(profile: str = typer.Argument(..., help="Profile name to switch to")):
    """Switch to a different profile."""
    config = Config()

    if profile not in config.list_profiles():
        print_error(f"Profile '{profile}' not found")
        print_info("Available profiles:")
        for p in config.list_profiles():
            print_info(f"  - {p}")
        raise typer.Exit(1)

    config.set_current_profile(profile)
    print_success(f"Switched to profile '{profile}'")
