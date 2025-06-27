"""Job-related commands for Dagster CLI."""

import json
import typer
from typing import Optional

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
    print_jobs_table,
    create_spinner,
)
from dagster_cli.utils.tldr import print_tldr


app = typer.Typer(
    help="""[bold]Job operations[/bold]

[bold cyan]Available commands:[/bold cyan]
  [green]list[/green]     List all jobs [dim](--location, --json)[/dim]
  [green]view[/green]     View job details [dim]JOB_NAME [--json][/dim]
  [green]run[/green]      Run a job [dim]JOB_NAME [--config FILE] [--tags][/dim]

[dim]Use 'dgc job COMMAND --help' for detailed options[/dim]""",
    rich_markup_mode="rich",
)


@app.callback(invoke_without_command=True)
def job_callback(
    ctx: typer.Context,
    tldr: bool = typer.Option(
        False,
        "--tldr",
        help="Show practical examples and exit",
        is_eager=True,
    ),
):
    """Job operations callback."""
    if tldr:
        print_tldr("job")
        raise typer.Exit()

    # If no command was provided, show help
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


@app.command("list")
def list_jobs(
    location: Optional[str] = typer.Option(
        None, "--location", "-l", help="Filter by repository location"
    ),
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
    """List all available jobs."""
    try:
        client = DagsterClient(profile, deployment)

        with create_spinner("Fetching jobs...") as progress:
            task = progress.add_task("Fetching jobs...", total=None)
            jobs = client.list_jobs(location)
            progress.remove_task(task)

        if not jobs:
            print_warning("No jobs found")
            return

        if json_output:
            console.print_json(data=jobs)
        else:
            print_info(f"Found {len(jobs)} jobs")
            print_jobs_table(jobs, show_location=(location is None))

    except Exception as e:
        print_error(f"Failed to list jobs: {str(e)}")
        raise typer.Exit(1) from e


@app.command()
def run(
    job_name: str = typer.Argument(..., help="Name of the job to run"),
    config: Optional[str] = typer.Option(
        None, "--config", "-c", help="Run configuration as JSON string"
    ),
    config_file: Optional[typer.FileText] = typer.Option(
        None, "--config-file", "-f", help="Run configuration from file"
    ),
    location: Optional[str] = typer.Option(
        None, "--location", "-l", help="Repository location (overrides profile default)"
    ),
    repository: Optional[str] = typer.Option(
        None, "--repository", "-r", help="Repository name (overrides profile default)"
    ),
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
    """Submit a job for execution."""
    try:
        # Parse run configuration
        run_config = {}
        if config:
            try:
                run_config = json.loads(config)
            except json.JSONDecodeError as e:
                print_error(f"Invalid JSON in --config: {e}")
                raise typer.Exit(1) from e
        elif config_file:
            try:
                run_config = json.load(config_file)
            except json.JSONDecodeError as e:
                print_error(f"Invalid JSON in config file: {e}")
                raise typer.Exit(1) from e

        # Show what we're about to do
        print_info(f"Job: {job_name}")
        if location:
            print_info(f"Location: {location}")
        if repository:
            print_info(f"Repository: {repository}")
        if run_config:
            print_info("Run configuration provided")

        # Confirmation
        if not yes and not typer.confirm("Submit this job?"):
            print_warning("Cancelled")
            return

        client = DagsterClient(profile, deployment)

        with create_spinner("Submitting job...") as progress:
            task = progress.add_task("Submitting job...", total=None)
            run_id = client.submit_job_run(
                job_name=job_name,
                run_config=run_config,
                repository_location_name=location,
                repository_name=repository,
            )
            progress.remove_task(task)

        print_success("Job submitted successfully!")
        print_info(f"Run ID: {run_id}")

        if base_url := client.profile.get("url", ""):
            # Apply deployment to URL
            url = base_url
            if client.deployment and client.deployment != "prod":
                url = url.replace("/prod", f"/{client.deployment}")
            if not url.startswith("http"):
                url = f"https://{url}"
            print_info(f"View at: {url}/runs/{run_id}")

    except Exception as e:
        print_error(f"Failed to submit job: {str(e)}")
        raise typer.Exit(1) from e


@app.command()
def view(
    job_name: str = typer.Argument(..., help="Name of the job to view"),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Use specific profile"
    ),
    deployment: Optional[str] = typer.Option(
        None,
        DEPLOYMENT_OPTION_NAME,
        DEPLOYMENT_OPTION_SHORT,
        help=DEPLOYMENT_OPTION_HELP,
    ),
):
    """View job details."""
    try:
        client = DagsterClient(profile, deployment)

        with create_spinner("Fetching job details...") as progress:
            task = progress.add_task("Fetching job details...", total=None)
            jobs = client.list_jobs()
            progress.remove_task(task)

        job = next((j for j in jobs if j["name"] == job_name), None)
        if not job:
            print_error(f"Job '{job_name}' not found")
            raise typer.Exit(1)

        # Display job information
        console.print(f"\n[bold cyan]Job: {job['name']}[/bold cyan]")
        if job.get("description"):
            console.print(f"[white]Description:[/white] {job['description']}")
        console.print(f"[white]Location:[/white] {job.get('location', 'Unknown')}")
        console.print(f"[white]Repository:[/white] {job.get('repository', 'Unknown')}")

    except Exception as e:
        print_error(f"Failed to view job: {str(e)}")
        raise typer.Exit(1) from e
