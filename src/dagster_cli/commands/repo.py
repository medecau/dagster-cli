"""Repository-related commands for Dagster CLI."""

import typer

from dagster_cli.client import DagsterClient
from dagster_cli.constants import (
    DEPLOYMENT_OPTION_HELP,
    DEPLOYMENT_OPTION_NAME,
    DEPLOYMENT_OPTION_SHORT,
)
from dagster_cli.utils.output import (
    console,
    create_spinner,
    print_error,
    print_info,
    print_repos_table,
    print_success,
    print_warning,
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

    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


@app.command("list")
def list_repos(
    profile: str | None = typer.Option(
        None,
        "--profile",
        "-p",
        help="Use specific profile",
    ),
    deployment: str | None = typer.Option(
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

        with create_spinner("Fetching repositories...") as (progress, task):
            info = client.get_deployment_info()
            progress.remove_task(task)

        repos_data = info.get("repositoriesOrError", {}).get("nodes", [])

        if not repos_data:
            print_warning("No repositories found")
            return

        if json_output:
            console.print_json(data=repos_data)
        else:
            total_jobs = 0
            locations: dict = {}
            for repo in repos_data:
                location_name = repo.get("location", {}).get("name", "Unknown")
                repo_name = repo.get("name", "Unknown")
                job_count = len(repo.get("pipelines", []))
                if location_name not in locations:
                    locations[location_name] = {"repos": [], "job_count": 0}
                locations[location_name]["repos"].append(repo_name)
                locations[location_name]["job_count"] += job_count
                total_jobs += job_count

            print_repos_table(locations, info.get("version", "Unknown"), total_jobs)

    except Exception as e:
        print_error(f"Failed to list repositories: {str(e)}")
        raise typer.Exit(1) from e


@app.command()
def reload(
    location: str = typer.Argument(..., help="Repository location to reload"),
    profile: str | None = typer.Option(
        None,
        "--profile",
        "-p",
        help="Use specific profile",
    ),
    deployment: str | None = typer.Option(
        None,
        DEPLOYMENT_OPTION_NAME,
        DEPLOYMENT_OPTION_SHORT,
        help=DEPLOYMENT_OPTION_HELP,
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
        envvar="DGC_ASSUME_YES",
    ),
):
    """Reload a repository location."""
    try:
        if not yes and not typer.confirm(f"Reload repository location '{location}'?"):
            print_warning("Cancelled")
            return

        client = DagsterClient(profile, deployment)

        with create_spinner(f"Reloading '{location}'...") as (progress, task):
            client.reload_repository_location(location)
            progress.remove_task(task)

        print_success(f"Repository location '{location}' reloaded successfully")

    except Exception as e:
        print_error(f"Failed to reload repository: {str(e)}")
        raise typer.Exit(1) from e
