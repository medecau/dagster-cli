"""Run-related commands for Dagster CLI."""

import contextlib
from pathlib import Path

import typer
from rich.panel import Panel

from dagster_cli.client import DagsterClient
from dagster_cli.constants import (
    DEFAULT_RUN_LIMIT,
    DEPLOYMENT_OPTION_HELP,
    DEPLOYMENT_OPTION_NAME,
    DEPLOYMENT_OPTION_SHORT,
)
from dagster_cli.utils.format import format_timestamp
from dagster_cli.utils.output import (
    console,
    create_spinner,
    print_error,
    print_info,
    print_run_details,
    print_runs_table,
    print_warning,
)
from dagster_cli.utils.run_utils import resolve_run_id
from dagster_cli.utils.tldr import print_tldr

# Log level hierarchy for filtering
LEVEL_HIERARCHY = {
    "DEBUG": 0,
    "INFO": 1,
    "WARNING": 2,
    "ERROR": 3,
    "CRITICAL": 4,
}

# Map event types to log levels
EVENT_TYPE_LEVELS = {
    "ExecutionStepFailureEvent": "ERROR",
    "RunFailureEvent": "ERROR",
    "ExecutionStepSuccessEvent": "INFO",
    "RunSuccessEvent": "INFO",
    "MaterializationEvent": "INFO",
    "AssetMaterializationPlannedEvent": "INFO",
    "HandledOutputEvent": "INFO",
    "EngineEvent": "INFO",
    "RunStartEvent": "INFO",
    "AlertStartEvent": "WARNING",
    "AlertSuccessEvent": "INFO",
    "AlertFailureEvent": "ERROR",
}


def should_include_event(event, min_level):
    """Check if an event should be included based on the minimum log level."""
    if not min_level:
        return True

    # Get the event's level
    event_level = event.get("level")

    # If no level field, check event type mapping
    if not event_level:
        event_type = event.get("__typename")
        event_level = EVENT_TYPE_LEVELS.get(event_type)

    # If still no level, include it
    if not event_level or min_level not in LEVEL_HIERARCHY:
        return True

    # Compare levels
    return LEVEL_HIERARCHY.get(event_level, -1) >= LEVEL_HIERARCHY.get(min_level, 0)


app = typer.Typer(
    help="""[bold]Run management[/bold]

[bold cyan]Available commands:[/bold cyan]
  [green]list[/green]     List recent runs [dim](--limit, --status, --json)[/dim]
  [green]view[/green]     View run details [dim]RUN_ID [--json][/dim]
  [green]logs[/green]     View run logs [dim]RUN_ID [--stdout] [--stderr] [--json][/dim]
  [green]cancel[/green]   Cancel a running job [dim]RUN_ID [--yes][/dim]

[dim]Use 'dgc run COMMAND --help' for detailed options[/dim]""",
    rich_markup_mode="rich",
)


@app.callback(invoke_without_command=True)
def run_callback(ctx: typer.Context):
    """Run management callback."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        print_tldr("run")
        raise typer.Exit()


@app.command("list")
def list_runs(
    limit: int = typer.Option(
        DEFAULT_RUN_LIMIT,
        "--limit",
        "-n",
        help="Number of runs to show",
    ),
    status: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status (SUCCESS, FAILURE, STARTED, etc.)",
    ),
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
    """List recent runs."""
    try:
        client = DagsterClient(profile, deployment)

        with create_spinner("Fetching runs...") as (progress, task):
            runs = client.get_recent_runs(limit=limit, status=status)
            progress.remove_task(task)

        if not runs:
            print_warning("No runs found")
            return

        if json_output:
            console.print_json(data=runs)
        else:
            if status:
                print_info(f"Showing {len(runs)} {status} runs")
            else:
                print_info(f"Showing {len(runs)} recent runs")
            print_runs_table(runs)

    except Exception as e:
        print_error(f"Failed to list runs: {str(e)}")
        raise typer.Exit(1) from e


@app.command()
def view(
    run_id: str = typer.Argument(
        ...,
        help="Run ID to view (can be partial, or 'latest', 'last-failure')",
    ),
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
    no_errors: bool = typer.Option(
        False,
        "--no-errors",
        help="Skip inline error details for failed runs",
    ),
):
    """View run details.

    For failed runs, automatically shows the most recent error events inline.
    Use --no-errors to suppress this behaviour.
    """
    try:
        client = DagsterClient(profile, deployment)

        with create_spinner("Finding run...") as (progress, task):
            full_run_id, error_msg, matching_runs = resolve_run_id(client, run_id)
            progress.remove_task(task)

        if error_msg:
            print_error(error_msg)
            if matching_runs:
                for r in matching_runs:
                    print_info(f"  - {r['id'][:16]}... ({r['pipeline']['name']})")
            raise typer.Exit(1)

        with create_spinner("Fetching run details...") as (progress, task):
            run = client.get_run_status(full_run_id)
            progress.remove_task(task)

        if not run:
            print_error(f"Run '{run_id}' not found")
            raise typer.Exit(1)

        if json_output:
            console.print_json(data=run)
        else:
            print_run_details(run)

            # Inline recent errors for failed runs
            if run.get("status") == "FAILURE" and not no_errors:
                _print_inline_errors(client, full_run_id)

    except Exception as e:
        print_error(f"Failed to view run: {str(e)}")
        raise typer.Exit(1) from e


def _print_inline_errors(client: DagsterClient, run_id: str) -> None:
    """Fetch and display error events inline, without aborting if logs fail."""
    with contextlib.suppress(Exception):  # never mask the run details above
        logs_data = client.get_run_logs(run_id, limit=200)
        error_events = [
            e
            for e in logs_data.get("events", [])
            if e.get("__typename") in ["ExecutionStepFailureEvent", "RunFailureEvent"]
        ]
        if not error_events:
            return

        lines = []
        for event in error_events:
            event_type = event.get("__typename", "").replace("Event", "")
            step = event.get("stepKey")
            msg = event.get("message", "")
            header = f"[bold red]{event_type}[/bold red]"
            if step:
                header += f" [dim](step: {step})[/dim]"
            lines.append(header)
            if msg:
                lines.append(msg)
            if err := event.get("error", {}):
                if err.get("message"):
                    lines.append(f"[red]{err['message']}[/red]")
                if err.get("stack"):
                    stack = err["stack"]
                    if isinstance(stack, list):
                        stack = "\n".join(stack)
                    lines.append(f"[dim]{stack}[/dim]")
            lines.append("")

        console.print(
            Panel(
                "\n".join(lines).rstrip(),
                title="Recent Errors",
                border_style="red",
                expand=False,
            )
        )
        print_info(
            "Use 'dgc run logs --errors-only' for full details. "
            "Pass --no-errors to suppress this panel."
        )


@app.command()
def cancel(
    run_id: str = typer.Argument(
        ...,
        help="Run ID to cancel (can be partial, or 'latest')",
    ),
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
    """Cancel a running job."""
    try:
        client = DagsterClient(profile, deployment)

        with create_spinner("Finding run...") as (progress, task):
            full_run_id, error_msg, matching_runs = resolve_run_id(client, run_id)
            progress.remove_task(task)

        if error_msg:
            print_error(error_msg)
            if matching_runs:
                for r in matching_runs:
                    print_info(f"  - {r['id'][:16]}... ({r['pipeline']['name']})")
            raise typer.Exit(1)

        if not yes and not typer.confirm(f"Cancel run {full_run_id[:8]}...?"):
            print_warning("Cancelled")
            return

        with create_spinner("Cancelling run...") as (progress, task):
            client.cancel_run(full_run_id)
            progress.remove_task(task)

        from dagster_cli.utils.output import print_success

        print_success(f"Run {full_run_id[:8]}... cancelled")

    except Exception as e:
        print_error(f"Failed to cancel run: {str(e)}")
        raise typer.Exit(1) from e


@app.command()
def logs(  # noqa: C901
    run_id: str = typer.Argument(..., help="Run ID to view logs (can be partial)"),
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
    stdout: bool = typer.Option(
        False,
        "--stdout",
        help="Show stdout instead of events",
    ),
    stderr: bool = typer.Option(
        False,
        "--stderr",
        help="Show stderr instead of events",
    ),
    events_only: bool = typer.Option(
        False,
        "--events-only",
        help="Only show events, don't auto-fetch stderr on errors",
    ),
    level: str | None = typer.Option(
        None,
        "--level",
        "-l",
        help="Minimum log level to show (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    ),
    errors_only: bool = typer.Option(
        False,
        "--errors-only",
        help="Show only errors and critical events (shortcut for --level ERROR)",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Save logs to file instead of displaying",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    no_stack: bool = typer.Option(
        False,
        "--no-stack",
        help="Hide stack traces in error output",
    ),
):
    """View run logs.

    Displays event logs for a Dagster run. For failed runs, automatically shows
    Python stack traces when available (use --no-stack to hide them).

    By default shows all log levels. Use --level to filter by minimum severity.
    Examples:
      dgc run logs <run-id> --level WARNING  # Show warnings and above
      dgc run logs <run-id> --errors-only    # Show only errors and critical
    """
    import requests
    from rich.table import Table

    try:
        client = DagsterClient(profile, deployment)

        # Resolve partial run ID if needed
        with create_spinner("Finding run...") as (progress, task):
            full_run_id, error_msg, matching_runs = resolve_run_id(client, run_id)
            progress.remove_task(task)

        if error_msg:
            print_error(error_msg)
            if matching_runs:
                for r in matching_runs:
                    print_info(f"  - {r['id'][:16]}... ({r['pipeline']['name']})")
            raise typer.Exit(1)

        # Handle mutually exclusive options
        if stdout and stderr:
            print_error("Cannot specify both --stdout and --stderr")
            raise typer.Exit(1)

        # Handle level filtering options
        filter_level = None
        if errors_only:
            filter_level = "ERROR"
        elif level:
            filter_level = level.upper()
            if filter_level not in LEVEL_HIERARCHY:
                print_error(f"Invalid log level: {level}")
                print_info("Valid levels are: DEBUG, INFO, WARNING, ERROR, CRITICAL")
                raise typer.Exit(1)

        # Get compute logs if requested
        if stdout or stderr:
            with create_spinner("Fetching compute log URLs...") as (progress, task):
                log_urls = client.get_compute_log_urls(full_run_id)
                progress.remove_task(task)

            url = log_urls.get("stdout_url" if stdout else "stderr_url")
            if not url:
                log_type = "stdout" if stdout else "stderr"
                print_warning(f"No {log_type} logs available for this run")
                print_info(
                    "Compute logs may only be available for Dagster+ deployments",
                )
                raise typer.Exit(1)

            # Download log content
            with create_spinner(
                f"Downloading {'stdout' if stdout else 'stderr'}...",
            ) as (progress, task):
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                log_content = response.text
                progress.remove_task(task)

            if output:
                with Path(output).open("w") as f:
                    f.write(log_content)
                print_info(f"Logs saved to {output}")
            elif json_output:
                console.print_json(
                    data={
                        "type": "stdout" if stdout else "stderr",
                        "content": log_content,
                    },
                )
            else:
                console.print(
                    Panel(
                        log_content,
                        title=f"{'stdout' if stdout else 'stderr'} logs",
                        expand=False,
                    ),
                )

        else:
            # Default: show event logs
            # Initialize counters
            level_counts = {level: 0 for level in LEVEL_HIERARCHY}
            all_events = []
            filtered_events = []
            cursor = None
            has_more = True
            total_fetched = 0

            # Paginate through all events
            with create_spinner("Fetching event logs...") as (progress, task):
                while has_more:
                    # Fetch next page
                    logs_data = client.get_run_logs(
                        full_run_id,
                        limit=100,
                        cursor=cursor,
                    )
                    events = logs_data.get("events", [])

                    # Update total fetched
                    total_fetched += len(events)
                    progress.update(
                        task,
                        description=f"Fetching event logs... ({total_fetched} events)",
                    )

                    # Count all events by level
                    for event in events:
                        event_level = event.get("level")
                        if not event_level:
                            event_type = event.get("__typename")
                            event_level = EVENT_TYPE_LEVELS.get(event_type)

                        if event_level and event_level in level_counts:
                            level_counts[event_level] += 1

                    # Filter events if level specified
                    if filter_level:
                        for event in events:
                            if should_include_event(event, filter_level):
                                filtered_events.append(event)  # noqa: PERF401
                    else:
                        all_events.extend(events)

                    # Check for more pages
                    has_more = logs_data.get("hasMore", False)
                    cursor = logs_data.get("cursor")

                progress.remove_task(task)

            # Use filtered events if filtering was applied
            events_to_display = filtered_events if filter_level else all_events

            if not events_to_display and filter_level:
                print_warning(f"No events found at {filter_level} level or above")
                # Still show summary
                console.print("\n[bold]Log Summary:[/bold]")
                for lvl in LEVEL_HIERARCHY:
                    count = level_counts.get(lvl, 0)
                    console.print(f"  {lvl}: {count}")
                console.print(f"\nTotal events: {total_fetched}")
                raise typer.Exit(1)
            if not events_to_display:
                print_warning("No log events found for this run")
                raise typer.Exit(1)

            # Check for errors
            has_errors = any(
                event.get("level") in ["ERROR", "CRITICAL"]
                or event.get("__typename")
                in ["ExecutionStepFailureEvent", "RunFailureEvent"]
                for event in events_to_display
            )

            if json_output:
                # Include statistics in JSON output
                json_data = {
                    "run_id": full_run_id,
                    "events": events_to_display,
                    "statistics": {
                        "total_events": total_fetched,
                        "levels": level_counts,
                        "filter_applied": filter_level,
                        "events_shown": len(events_to_display),
                    },
                }
                console.print_json(data=json_data)
            else:
                # Display events in a table
                title = f"Event Logs for Run {full_run_id[:8]}..."
                if filter_level:
                    title += f" (Filtered: {filter_level} and above)"

                table = Table(title=title)
                table.add_column("Time", style="cyan", no_wrap=True)
                table.add_column("Level", style="yellow")
                table.add_column("Type", style="blue")
                table.add_column("Message", style="white")

                # Collect stack traces for display after table
                stack_traces = []

                for event in events_to_display:
                    timestamp = format_timestamp(event.get("timestamp"))
                    level = event.get("level", "")
                    event_type = event.get("__typename", "").replace("Event", "")
                    message = event.get("message", "")

                    # Add additional context for specific event types
                    if event.get("__typename") == "ExecutionStepFailureEvent":
                        error = event.get("error") or {}
                        if error.get("message"):
                            message = f"{message}\nError: {error['message']}"
                        # Collect stack trace for later display
                        if error.get("stack") and not no_stack:
                            stack = error["stack"]
                            # Handle case where stack might be a list of lines
                            if isinstance(stack, list):
                                stack = "\n".join(stack)
                            stack_traces.append(
                                {
                                    "type": "Step Failure",
                                    "step": event.get("stepKey", "Unknown"),
                                    "stack": stack,
                                },
                            )
                    elif event.get("__typename") == "RunFailureEvent":
                        error = event.get("error") or {}
                        if error.get("message"):
                            message = f"{message}\nError: {error['message']}"
                        # Collect stack trace for later display
                        if error.get("stack") and not no_stack:
                            stack = error["stack"]
                            # Handle case where stack might be a list of lines
                            if isinstance(stack, list):
                                stack = "\n".join(stack)
                            stack_traces.append(
                                {"type": "Run Failure", "step": None, "stack": stack},
                            )

                    # Color code based on level
                    if level == "ERROR" or event_type in [
                        "ExecutionStepFailure",
                        "RunFailure",
                    ]:
                        level_style = "red bold"
                    elif level == "WARNING":
                        level_style = "yellow"
                    elif level == "INFO":
                        level_style = "green"
                    else:
                        level_style = "white"

                    table.add_row(
                        timestamp,
                        f"[{level_style}]{level}[/{level_style}]" if level else "",
                        event_type,
                        message,
                    )

                console.print(table)

                # Display collected stack traces
                if stack_traces:
                    console.print()  # Add spacing
                    for trace_info in stack_traces:
                        title = f"Stack Trace - {trace_info['type']}"
                        if trace_info.get("step"):
                            title += f" (Step: {trace_info['step']})"

                        console.print(
                            Panel(
                                trace_info["stack"],
                                title=title,
                                border_style="red",
                                expand=False,
                            ),
                        )
                        console.print()  # Add spacing between stack traces

                    # Add note about potential truncation
                    print_info("Note: Stack trace may be truncated")

                # Display log summary
                console.print("\n[dim]─[/dim]" * 50)
                console.print(
                    f"\n[bold]Log Summary[/bold] (Total events: {total_fetched}):",
                )
                for lvl in LEVEL_HIERARCHY:
                    count = level_counts.get(lvl, 0)
                    if count > 0:
                        if lvl in ["ERROR", "CRITICAL"]:
                            style = "red"
                        elif lvl == "WARNING":
                            style = "yellow"
                        elif lvl == "INFO":
                            style = "green"
                        else:
                            style = "dim"
                        console.print(f"  [{style}]• {lvl}: {count}[/{style}]")

                if filter_level:
                    n = len(events_to_display)
                    console.print(
                        f"\n[dim]Showing: {filter_level} and above ({n} events)[/dim]"
                    )
                else:
                    console.print("\n[dim]Showing: ALL levels[/dim]")
                console.print("[dim]─[/dim]" * 50)

            # Auto-fetch stderr if there are errors (unless --events-only)
            if has_errors and not events_only and not json_output:
                print_info("\nErrors detected. Fetching stderr logs...")

                log_urls = client.get_compute_log_urls(full_run_id)
                if stderr_url := log_urls.get("stderr_url"):
                    try:
                        response = requests.get(stderr_url, timeout=30)
                        response.raise_for_status()
                        if stderr_content := response.text.strip():
                            console.print("\n")
                            console.print(
                                Panel(
                                    stderr_content,
                                    title="stderr output",
                                    expand=False,
                                    border_style="red",
                                ),
                            )
                        else:
                            print_info("stderr is empty")
                    except Exception as e:
                        print_warning(f"Failed to fetch stderr: {e}")
                else:
                    print_info("stderr logs not available (may require Dagster+)")

    except Exception as e:
        print_error(f"Failed to view logs: {str(e)}")
        raise typer.Exit(1) from e
