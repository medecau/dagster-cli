"""Deployment-related commands for Dagster CLI."""

import typer
from typing import Optional
from rich import box
from rich.table import Table

from dagster_cli.client import DagsterClient
from dagster_cli.utils.output import (
    console,
    print_error,
    print_warning,
    print_info,
    print_success,
    create_spinner,
)
from dagster_cli.utils.tldr import print_tldr


app = typer.Typer(
    help="""[bold]Deployment management[/bold]

[bold cyan]Available commands:[/bold cyan]
  [green]list[/green]     List available deployments [dim](--json)[/dim]

[dim]Use 'dgc deployment COMMAND --help' for detailed options[/dim]""",
    rich_markup_mode="rich",
)


@app.callback(invoke_without_command=True)
def deployment_callback(
    ctx: typer.Context,
    tldr: bool = typer.Option(
        False,
        "--tldr",
        help="Show practical examples and exit",
        is_eager=True,
    ),
):
    """Deployment management callback."""
    if tldr:
        print_tldr("deployment")
        raise typer.Exit()

    # If no command was provided, show help
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


def _format_deployment_name(deployment: dict) -> tuple[str, str]:
    """Format deployment name for display.

    Args:
        deployment: Deployment dict with metadata

    Returns:
        Tuple of (display_name, deployment_type)
    """
    deployment_name = deployment["deploymentName"]

    # Check if it's a branch deployment with metadata
    if deployment.get("isBranchDeployment") and deployment.get(
        "branchDeploymentGitMetadata"
    ):
        metadata = deployment["branchDeploymentGitMetadata"]
        branch_name = metadata.get("branchName", "unknown")
        short_sha = (
            deployment_name[:8] if len(deployment_name) >= 8 else deployment_name
        )

        # Format based on available info
        if branch_name and branch_name != "unknown":
            return (f"{branch_name} ({short_sha}...)", "Branch")
        else:
            return (f"branch ({short_sha}...)", "Branch")

    # Named deployments
    if deployment_name == "prod":
        return ("prod", "Production")
    elif deployment_name == "staging":
        return (deployment_name, "Staging")
    elif len(deployment_name) == 40 and deployment_name.isalnum():
        # Commit SHA without metadata (shouldn't happen but fallback)
        short_sha = deployment_name[:8]
        return (f"branch ({short_sha}...)", "Branch")
    else:
        # Other named deployments
        return (deployment_name, "Custom")


@app.command("list")
def list_deployments(
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Use specific profile"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all available deployments."""
    try:
        # Create client without deployment parameter to access base URL
        client = DagsterClient(profile)

        with create_spinner("Fetching deployments...") as progress:
            task = progress.add_task("Fetching deployments...", total=None)
            deployments = client.list_deployments()
            progress.remove_task(task)

        if not deployments:
            print_warning("No deployments found")
            return

        # Sort deployments: prod first, then staging, then others
        def sort_key(d):
            name = d["deploymentName"]
            if name == "prod":
                return (0, name)
            elif name == "staging":
                return (1, name)
            else:
                return (2, name)

        deployments = sorted(deployments, key=sort_key)

        if json_output:
            console.print_json(data=deployments)
        else:
            # Create table
            table = Table(box=box.ROUNDED)
            table.add_column("Deployment Name", style="cyan")
            table.add_column("Type", style="magenta")
            table.add_column("Status", style="white")
            table.add_column("ID", style="dim")

            for deployment in deployments:
                display_name, deployment_type = _format_deployment_name(deployment)
                status = deployment["deploymentStatus"]

                # Color code status
                if status == "ACTIVE":
                    status_display = f"[green]{status}[/green]"
                else:
                    status_display = f"[yellow]{status}[/yellow]"

                # Add additional info for branch deployments
                extra_info = ""
                if deployment.get("branchDeploymentGitMetadata"):
                    metadata = deployment["branchDeploymentGitMetadata"]
                    if pr_num := metadata.get("pullRequestNumber"):
                        extra_info = f" PR #{pr_num}"

                table.add_row(
                    display_name + extra_info,
                    deployment_type,
                    status_display,
                    str(deployment["deploymentId"]),
                )

            print_info(f"Found {len(deployments)} deployments")
            console.print(table)
            console.print()
            print_info(
                "Use --deployment flag with any command to access a specific deployment"
            )
            print_info("Example: dgc run list --deployment staging")

    except Exception as e:
        print_error(f"Failed to list deployments: {str(e)}")
        raise typer.Exit(1) from e


@app.command()
def test(
    deployment_name: str = typer.Argument(..., help="Deployment name to test"),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Use specific profile"
    ),
):
    """Test if a deployment exists and is accessible."""
    try:
        # Try to create a client with the specified deployment
        with create_spinner(f"Testing deployment '{deployment_name}'...") as progress:
            task = progress.add_task(
                f"Testing deployment '{deployment_name}'...", total=None
            )

            try:
                # Create client with the deployment
                client = DagsterClient(profile, deployment_name)

                # Try a simple query to verify access
                info = client.get_deployment_info()

                progress.remove_task(task)

                print_success(f"Deployment '{deployment_name}' is accessible!")

                # Show some info about the deployment
                if repos := info.get("repositoriesOrError", {}).get("nodes", []):
                    print_info(f"Found {len(repos)} repository location(s):")
                    for repo in repos:
                        location = repo.get("location", {}).get("name", "Unknown")
                        job_count = len(repo.get("pipelines", []))
                        print_info(f"  - {location} ({job_count} jobs)")

            except Exception as e:
                progress.remove_task(task)
                print_error(f"Deployment '{deployment_name}' is not accessible")
                print_error(f"Error: {str(e)}")

                # Suggest listing deployments
                print_info(
                    "\nTip: Use 'dgc deployment list' to see available deployments"
                )
                raise typer.Exit(1) from e

    except Exception as e:
        # This shouldn't happen as inner try/catch handles errors
        print_error(f"Unexpected error: {str(e)}")
        raise typer.Exit(1) from e
