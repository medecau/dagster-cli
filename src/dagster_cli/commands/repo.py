"""Repository-related commands for Dagster CLI."""

import typer
from typing import Optional
from rich import box
from rich.table import Table

from dagster_cli.client import DagsterClient
from dagster_cli.constants import (
    DEPLOYMENT_OPTION_NAME,
    DEPLOYMENT_OPTION_SHORT,
    DEPLOYMENT_OPTION_HELP,
)
from dagster_cli.utils.output import (
    console,
    print_success,
    print_error,
    print_warning,
    print_info,
    create_spinner,
)
from dagster_cli.utils.tldr import print_tldr


app = typer.Typer(
    help="""[bold]Repository management[/bold]

[bold cyan]Available commands:[/bold cyan]
  [green]list[/green]     List repository locations [dim](--json)[/dim]
  [green]reload[/green]   Reload a repository location [dim]LOCATION_NAME[/dim]

[dim]Use 'dgc repo COMMAND --help' for detailed options[/dim]""",
    rich_markup_mode="rich",
)


@app.callback(invoke_without_command=True)
def repo_callback(
    ctx: typer.Context,
    tldr: bool = typer.Option(
        False,
        "--tldr",
        help="Show practical examples and exit",
        is_eager=True,
    ),
):
    """Repository management callback."""
    if tldr:
        print_tldr("repo")
        raise typer.Exit()

    # If no command was provided, show help
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


@app.command("list")
def list_repos(
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Use specific profile"
    ),
    deployment: Optional[str] = typer.Option(
        None,
        DEPLOYMENT_OPTION_NAME,
        DEPLOYMENT_OPTION_SHORT,
        help=DEPLOYMENT_OPTION_HELP,
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List repositories and locations."""
    try:
        client = DagsterClient(profile, deployment)

        with create_spinner("Fetching repositories...") as progress:
            task = progress.add_task("Fetching repositories...", total=None)
            info = client.get_deployment_info()
            progress.remove_task(task)

        repos_data = info.get("repositoriesOrError", {}).get("nodes", [])

        if not repos_data:
            print_warning("No repositories found")
            return

        if json_output:
            console.print_json(data=repos_data)
        else:
            # Create table
            table = Table(box=box.ROUNDED)
            table.add_column("Code Location", style="cyan")
            table.add_column("Jobs", style="white", justify="right")

            total_jobs = 0
            locations = {}

            # Group by location since repository names are usually __repository__
            for repo in repos_data:
                location_name = repo.get("location", {}).get("name", "Unknown")
                repo_name = repo.get("name", "Unknown")
                job_count = len(repo.get("pipelines", []))

                if location_name not in locations:
                    locations[location_name] = {"repos": [], "job_count": 0}

                locations[location_name]["repos"].append(repo_name)
                locations[location_name]["job_count"] += job_count
                total_jobs += job_count

            for location_name, data in locations.items():
                table.add_row(location_name, str(data["job_count"]))

            print_info(
                f"Dagster+ deployment (version: {info.get('version', 'Unknown')})"
            )
            console.print(table)
            print_info(f"Total: {len(locations)} code locations, {total_jobs} jobs")

    except Exception as e:
        print_error(f"Failed to list repositories: {str(e)}")
        raise typer.Exit(1) from e


@app.command()
def reload(
    location: str = typer.Argument(..., help="Repository location to reload"),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Use specific profile"
    ),
    deployment: Optional[str] = typer.Option(
        None,
        DEPLOYMENT_OPTION_NAME,
        DEPLOYMENT_OPTION_SHORT,
        help=DEPLOYMENT_OPTION_HELP,
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Reload a repository location."""
    try:
        # Confirmation
        if not yes and not typer.confirm(f"Reload repository location '{location}'?"):
            print_warning("Cancelled")
            return

        client = DagsterClient(profile, deployment)

        with create_spinner(f"Reloading '{location}'...") as progress:
            task = progress.add_task(f"Reloading '{location}'...", total=None)
            success = client.reload_repository_location(location)
            progress.remove_task(task)

        if success:
            print_success(f"Repository location '{location}' reloaded successfully")
        else:
            print_error(f"Failed to reload repository location '{location}'")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Failed to reload repository: {str(e)}")
        raise typer.Exit(1) from e
