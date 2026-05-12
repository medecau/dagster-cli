"""Output formatting utilities using Rich."""

import json
from types import TracebackType
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TaskID, TextColumn
from rich.syntax import Syntax
from rich.table import Table

from dagster_cli.utils.format import (
    colorize_status,
    format_asset_key,
    format_duration,
    format_job_name,
    format_timestamp,
)

console = Console()


def print_success(message: str) -> None:
    console.print(f"[green]✓[/green] {message}")


def print_error(message: str) -> None:
    console.print(f"[red]✗[/red] {message}")


def print_warning(message: str) -> None:
    console.print(f"[yellow]⚠[/yellow] {message}")


def print_info(message: str) -> None:
    console.print(f"[blue]ℹ[/blue] {message}")


class _SpinnerContext:
    """Context manager returned by create_spinner."""

    def __init__(self, message: str) -> None:
        self._message = message
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        )

    def __enter__(self) -> tuple[Progress, TaskID]:
        self._progress.__enter__()
        task = self._progress.add_task(self._message, total=None)
        return self._progress, task

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._progress.__exit__(exc_type, exc_val, exc_tb)


def create_spinner(message: str) -> _SpinnerContext:
    """Return a context manager that shows *message* in a spinner.

    Usage::

        with create_spinner("Loading...") as (progress, task):
            result = do_work()
            progress.remove_task(task)
    """
    return _SpinnerContext(message)


def print_jobs_table(jobs: list[dict[str, Any]], show_location: bool = False) -> None:
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


def print_runs_table(runs: list[dict[str, Any]]) -> None:
    table = Table(box=box.ROUNDED)
    table.add_column("Run ID", style="cyan", no_wrap=True)
    table.add_column("Job", style="magenta")
    table.add_column("Status", style="white")
    table.add_column("Started", style="white")
    table.add_column("Duration", style="white")

    for run in runs:
        run_id = run["id"][:8] + "..." if len(run["id"]) > 8 else run["id"]
        job_name = format_job_name(run.get("pipeline", {}).get("name", "Unknown"))
        status = run.get("status", "Unknown")
        start_time = format_timestamp(run.get("startTime"))
        duration_str = format_duration(run.get("startTime"), run.get("endTime"))
        table.add_row(
            run_id, job_name, colorize_status(status), start_time, duration_str
        )

    console.print(table)


def print_run_details(run: dict[str, Any]) -> None:
    run_id = run["id"]
    job_name = format_job_name(run.get("pipeline", {}).get("name", "Unknown"))
    status = run.get("status", "Unknown")

    content = f"""[cyan]ID:[/cyan]     {run_id}
[cyan]Job:[/cyan]    {job_name}
[cyan]Status:[/cyan] {colorize_status(status, with_icon=True)}
[cyan]Started:[/cyan] {format_timestamp(run.get("startTime"))}
[cyan]Ended:[/cyan]   {format_timestamp(run.get("endTime"))}"""

    if stats := run.get("stats", {}):
        steps_succeeded = stats.get("stepsSucceeded", 0)
        steps_failed = stats.get("stepsFailed", 0)
        content += (
            f"\n[cyan]Steps:[/cyan]  {steps_succeeded} succeeded, {steps_failed} failed"
        )

    console.print(Panel(content, title="Run Details", box=box.ROUNDED))


def print_config_json(config: dict[str, Any]) -> None:
    json_str = json.dumps(config, indent=2)
    syntax = Syntax(json_str, "json", theme="monokai", line_numbers=True)
    console.print(syntax)


def print_profiles_table(profiles: dict[str, dict[str, str]], current: str) -> None:
    table = Table(box=box.ROUNDED)
    table.add_column("Profile", style="cyan")
    table.add_column("URL", style="magenta")
    table.add_column("Location", style="blue")
    table.add_column("Current", style="green")

    for name, profile in profiles.items():
        is_current = "✓" if name == current else ""
        location = profile.get("location", "—")
        url = profile.get("url", "")
        table.add_row(name, url, location, is_current)

    console.print(table)


def print_automations_table(automations: list[dict[str, Any]]) -> None:
    table = Table(box=box.ROUNDED)
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Target", style="blue")
    table.add_column("Status", style="white")
    table.add_column("Last Tick", style="white")
    table.add_column("Last Run", style="white")

    for automation in automations:
        name = automation["name"]
        target = automation["target"]
        status = automation.get("status", "STOPPED")

        if automation["type"] == "Schedule":
            type_display = automation.get("cron_schedule", "Schedule")
        else:
            type_display = "Sensor"

        status_display = colorize_status(status)

        tick_status = automation.get("tick_status")
        tick_run_count = automation.get("tick_run_count", 0)
        if not automation.get("last_tick"):
            last_tick_display = "—"
        elif tick_status == "FAILURE":
            last_tick_display = colorize_status("FAILURE")
        elif tick_run_count > 0:
            last_tick_display = (
                f"{tick_run_count} run{'s' if tick_run_count != 1 else ''}"
            )
        else:
            last_tick_display = "[dim]SKIPPED[/dim]"

        last_run_status = automation.get("last_run_status", "—")
        if last_run_timestamp := automation.get("last_run_timestamp"):
            formatted_time = format_timestamp(last_run_timestamp)
            if last_run_status == "SUCCESS":
                last_run_display = f"[green]{formatted_time}[/green]"
            elif last_run_status == "FAILURE":
                last_run_display = f"[red]{formatted_time}[/red]"
            else:
                last_run_display = formatted_time
        else:
            last_run_display = "—"

        table.add_row(
            name,
            type_display,
            target,
            status_display,
            last_tick_display,
            last_run_display,
        )

    console.print(table)


def print_automation_details(automation: dict[str, Any]) -> None:
    name = automation["name"]
    auto_type = automation["type"]
    target = automation["target"]
    status = automation.get("status", "STOPPED")

    content = f"""[cyan]Name:[/cyan]        {name}
[cyan]Type:[/cyan]        {auto_type}
[cyan]Target:[/cyan]      {target}
[cyan]Status:[/cyan]      {colorize_status(status, with_icon=True)}
[cyan]Location:[/cyan]    {automation.get("location", "Unknown")}
[cyan]Repository:[/cyan]  {automation.get("repository", "Unknown")}"""

    if auto_type == "Schedule":
        content += (
            f"\n[cyan]Schedule:[/cyan]    {automation.get('cron_schedule', 'N/A')}"
        )
        if automation.get("execution_timezone"):
            content += f"\n[cyan]Timezone:[/cyan]    {automation['execution_timezone']}"
    elif auto_type == "Sensor":
        if automation.get("min_interval_seconds"):
            content += (
                f"\n[cyan]Min Interval:[/cyan] {automation['min_interval_seconds']}s"
            )

    if automation.get("description"):
        content += f"\n[cyan]Description:[/cyan] {automation['description']}"

    if recent_ticks := automation.get("recent_ticks", []):
        success_count = sum(t.get("status") == "SUCCESS" for t in recent_ticks)
        failure_count = sum(t.get("status") == "FAILURE" for t in recent_ticks)
        skip_count = sum(t.get("status") == "SKIPPED" for t in recent_ticks)
        content += "\n\n[cyan]Recent Activity:[/cyan]"
        content += (
            f"\n  Last {len(recent_ticks)} ticks:"
            f" {success_count} success, {failure_count} failed, {skip_count} skipped"
        )

    console.print(Panel(content, title=f"{auto_type} Details", box=box.ROUNDED))


def print_automation_ticks_table(ticks: list[dict[str, Any]]) -> None:
    table = Table(box=box.ROUNDED)
    table.add_column("Timestamp", style="cyan", no_wrap=True)
    table.add_column("Status", style="white")
    table.add_column("Runs", style="magenta")
    table.add_column("Error", style="red")

    for tick in ticks:
        timestamp = format_timestamp(tick.get("timestamp"))
        status = tick.get("status", "SKIPPED")
        status_display = colorize_status(status)
        run_count = tick.get("run_count", 0)
        run_display = (
            f"{run_count} run{'s' if run_count != 1 else ''}" if run_count > 0 else "—"
        )
        error = tick.get("error", "")
        if error and len(error) > 50:
            error = f"{error[:47]}..."
        table.add_row(timestamp, status_display, run_display, error or "—")

    console.print(table)


def print_assets_table(assets: list[dict[str, Any]]) -> None:
    """Print an asset list in a formatted table."""
    table = Table(box=box.ROUNDED)
    table.add_column("Asset Key", style="cyan")
    table.add_column("Group", style="magenta")
    table.add_column("Location", style="blue")
    table.add_column("Compute Kind", style="white")
    table.add_column("Materialized", style="green")

    for asset in assets:
        asset_key_str = format_asset_key(asset.get("key", {}).get("path", []))
        group_name = asset.get("groupName", "—")
        location_name = asset.get("location", "—")
        compute_kind = asset.get("computeKind", "—")
        if latest_run := asset.get("latestMaterializationRun"):
            materialized = "✓" if latest_run.get("status") == "SUCCESS" else "✗"
        else:
            materialized = "—"
        table.add_row(
            asset_key_str, group_name, location_name, compute_kind, materialized
        )

    console.print(table)


def print_asset_health_table(assets_to_show: list[dict[str, Any]]) -> None:
    """Print the health status table for assets."""
    table = Table(box=box.ROUNDED)
    table.add_column("Asset Key", style="cyan")
    table.add_column("Group", style="magenta")
    table.add_column("Status", style="white")
    table.add_column("Last Update", style="white")

    for asset_info in assets_to_show:
        status = asset_info["status"]
        status_display = (
            f"[green]{status}[/green]"
            if status == "Healthy"
            else f"[red]{status}[/red]"
        )
        table.add_row(
            asset_info["key"],
            asset_info["group"],
            status_display,
            asset_info["last_update"],
        )

    console.print(table)


def print_repos_table(
    locations: dict[str, dict], version: str, total_jobs: int
) -> None:
    """Print repository locations in a formatted table."""
    table = Table(box=box.ROUNDED)
    table.add_column("Code Location", style="cyan")
    table.add_column("Jobs", style="white", justify="right")

    for location_name, data in locations.items():
        table.add_row(location_name, str(data["job_count"]))

    print_info(f"Dagster+ deployment (version: {version})")
    console.print(table)
    print_info(f"Total: {len(locations)} code locations, {total_jobs} jobs")


def print_deployments_table(deployments: list[dict[str, Any]]) -> None:
    """Print Dagster+ deployments in a formatted table."""
    from dagster_cli.commands.deployment import _format_deployment_name

    table = Table(box=box.ROUNDED)
    table.add_column("Deployment Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Status", style="white")
    table.add_column("ID", style="dim")

    for deployment in deployments:
        display_name, deployment_type = _format_deployment_name(deployment)
        status = deployment["deploymentStatus"]
        status_display = colorize_status(status)

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

    console.print(table)
