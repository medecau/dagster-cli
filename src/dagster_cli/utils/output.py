"""Output formatting utilities using Rich."""

from typing import List, Dict, Any

from rich import box
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax

from dagster_cli.client import DagsterClient


console = Console()


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]✓[/green] {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[red]✗[/red] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue]ℹ[/blue] {message}")


def print_jobs_table(jobs: List[Dict[str, Any]], show_location: bool = False) -> None:
    """Print jobs in a formatted table."""
    table = Table(box=box.ROUNDED)

    table.add_column("Job Name", style="cyan")
    if show_location:
        table.add_column("Location", style="magenta")
        table.add_column("Repository", style="blue")
    table.add_column("Description", style="white")

    for job in jobs:
        row = [job["name"]]
        if show_location:
            row.extend([job.get("location", ""), job.get("repository", "")])
        row.append(job.get("description", ""))
        table.add_row(*row)

    console.print(table)


def print_runs_table(runs: List[Dict[str, Any]]) -> None:
    """Print runs in a formatted table."""
    table = Table(box=box.ROUNDED)

    table.add_column("Run ID", style="cyan", no_wrap=True)
    table.add_column("Job", style="magenta")
    table.add_column("Status", style="white")
    table.add_column("Started", style="white")
    table.add_column("Duration", style="white")

    for run in runs:
        run_id = run["id"][:8] + "..." if len(run["id"]) > 8 else run["id"]
        job_name = run.get("pipeline", {}).get("name", "Unknown")
        status = run.get("status", "Unknown")

        # Color code status
        if status == "SUCCESS":
            status_display = f"[green]{status}[/green]"
        elif status == "FAILURE":
            status_display = f"[red]{status}[/red]"
        elif status in ["STARTED", "QUEUED"]:
            status_display = f"[yellow]{status}[/yellow]"
        else:
            status_display = status

        # Format timestamps
        start_time = DagsterClient.format_timestamp(run.get("startTime"))

        # Calculate duration
        if run.get("startTime") and run.get("endTime"):
            start = run["startTime"]
            end = run["endTime"]
            # Convert to seconds if needed
            if start > 10000000000:
                start = start / 1000
                end = end / 1000
            duration = int(end - start)
            hours, remainder = divmod(duration, 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours:
                duration_str = f"{hours}h {minutes}m {seconds}s"
            elif minutes:
                duration_str = f"{minutes}m {seconds}s"
            else:
                duration_str = f"{seconds}s"
        else:
            duration_str = "—"

        table.add_row(run_id, job_name, status_display, start_time, duration_str)

    console.print(table)


def print_run_details(run: Dict[str, Any]) -> None:
    """Print detailed run information in a panel."""
    run_id = run["id"]
    job_name = run.get("pipeline", {}).get("name", "Unknown")
    # Add note for internal asset job
    if job_name == "__ASSET_JOB":
        job_name = "__ASSET_JOB (asset job)"
    status = run.get("status", "Unknown")

    # Color code status
    if status == "SUCCESS":
        status_display = f"[green]{status} ✓[/green]"
    elif status == "FAILURE":
        status_display = f"[red]{status} ✗[/red]"
    elif status in ["STARTED", "QUEUED"]:
        status_display = f"[yellow]{status} ⏳[/yellow]"
    else:
        status_display = status

    # Build content
    content = f"""[cyan]ID:[/cyan]     {run_id}
[cyan]Job:[/cyan]    {job_name}
[cyan]Status:[/cyan] {status_display}
[cyan]Started:[/cyan] {DagsterClient.format_timestamp(run.get("startTime"))}
[cyan]Ended:[/cyan]   {DagsterClient.format_timestamp(run.get("endTime"))}"""

    if stats := run.get("stats", {}):
        steps_succeeded = stats.get("stepsSucceeded", 0)
        steps_failed = stats.get("stepsFailed", 0)
        content += (
            f"\n[cyan]Steps:[/cyan]  {steps_succeeded} succeeded, {steps_failed} failed"
        )

    panel = Panel(content, title="Run Details", box=box.ROUNDED)
    console.print(panel)


def print_config_json(config: Dict[str, Any]) -> None:
    """Print configuration as syntax-highlighted JSON."""
    import json

    json_str = json.dumps(config, indent=2)
    syntax = Syntax(json_str, "json", theme="monokai", line_numbers=True)
    console.print(syntax)


def create_spinner(message: str) -> Progress:
    """Create a spinner progress indicator."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    )


def print_profiles_table(profiles: Dict[str, Dict[str, str]], current: str) -> None:
    """Print profiles in a formatted table."""
    table = Table(box=box.ROUNDED)

    table.add_column("Profile", style="cyan")
    table.add_column("URL", style="magenta")
    table.add_column("Location", style="blue")
    table.add_column("Current", style="green")

    for name, profile in profiles.items():
        is_current = "✓" if name == current else ""
        location = profile.get("location", "—")
        # Mask token in URL display
        url = profile.get("url", "")

        table.add_row(name, url, location, is_current)

    console.print(table)
