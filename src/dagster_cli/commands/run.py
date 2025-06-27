"""Run-related commands for Dagster CLI."""

import typer
from typing import Optional

from dagster_cli.client import DagsterClient
from dagster_cli.constants import (
    DEFAULT_RUN_LIMIT,
    DEPLOYMENT_OPTION_NAME,
    DEPLOYMENT_OPTION_SHORT,
    DEPLOYMENT_OPTION_HELP,
)
from dagster_cli.utils.output import (
    console,
    print_error,
    print_warning,
    print_info,
    print_runs_table,
    print_run_details,
    create_spinner,
)
from dagster_cli.utils.run_utils import resolve_run_id
from dagster_cli.utils.tldr import print_tldr


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
def run_callback(
    ctx: typer.Context,
    tldr: bool = typer.Option(
        False,
        "--tldr",
        help="Show practical examples and exit",
        is_eager=True,
    ),
):
    """Run management callback."""
    if tldr:
        print_tldr("run")
        raise typer.Exit()

    # If no command was provided, show help
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


@app.command("list")
def list_runs(
    limit: int = typer.Option(
        DEFAULT_RUN_LIMIT, "--limit", "-n", help="Number of runs to show"
    ),
    status: Optional[str] = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status (SUCCESS, FAILURE, STARTED, etc.)",
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
    """List recent runs."""
    try:
        client = DagsterClient(profile, deployment)

        with create_spinner("Fetching runs...") as progress:
            task = progress.add_task("Fetching runs...", total=None)
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
    run_id: str = typer.Argument(..., help="Run ID to view (can be partial)"),
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
    """View run details."""
    try:
        client = DagsterClient(profile, deployment)

        # Resolve partial run ID if needed
        with create_spinner("Finding run...") as progress:
            task = progress.add_task("Finding run...", total=None)
            full_run_id, error_msg, matching_runs = resolve_run_id(client, run_id)
            progress.remove_task(task)

        if error_msg:
            print_error(error_msg)
            if matching_runs:
                for r in matching_runs:
                    print_info(f"  - {r['id'][:16]}... ({r['pipeline']['name']})")
            raise typer.Exit(1)

        with create_spinner("Fetching run details...") as progress:
            task = progress.add_task("Fetching run details...", total=None)
            run = client.get_run_status(full_run_id)
            progress.remove_task(task)

        if not run:
            print_error(f"Run '{run_id}' not found")
            raise typer.Exit(1)

        if json_output:
            console.print_json(data=run)
        else:
            print_run_details(run)

    except Exception as e:
        print_error(f"Failed to view run: {str(e)}")
        raise typer.Exit(1) from e


@app.command()
def cancel(
    run_id: str = typer.Argument(..., help="Run ID to cancel (can be partial)"),
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
    """Cancel a running job."""
    print_warning("Run cancellation is not yet implemented in the GraphQL client")
    print_info("This feature will be added in a future version")
    raise typer.Exit(1)


@app.command()
def logs(
    run_id: str = typer.Argument(..., help="Run ID to view logs (can be partial)"),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Use specific profile"
    ),
    deployment: Optional[str] = typer.Option(
        None,
        DEPLOYMENT_OPTION_NAME,
        DEPLOYMENT_OPTION_SHORT,
        help=DEPLOYMENT_OPTION_HELP,
    ),
    stdout: bool = typer.Option(
        False, "--stdout", help="Show stdout instead of events"
    ),
    stderr: bool = typer.Option(
        False, "--stderr", help="Show stderr instead of events"
    ),
    events_only: bool = typer.Option(
        False,
        "--events-only",
        help="Only show events, don't auto-fetch stderr on errors",
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Save logs to file instead of displaying"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    no_stack: bool = typer.Option(
        False, "--no-stack", help="Hide stack traces in error output"
    ),
):
    """View run logs.

    Displays event logs for a Dagster run. For failed runs, automatically shows
    Python stack traces when available (use --no-stack to hide them).
    """
    import requests
    from rich.panel import Panel
    from rich.table import Table

    try:
        client = DagsterClient(profile, deployment)

        # Resolve partial run ID if needed
        with create_spinner("Finding run...") as progress:
            task = progress.add_task("Finding run...", total=None)
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

        # Get compute logs if requested
        if stdout or stderr:
            with create_spinner("Fetching compute log URLs...") as progress:
                task = progress.add_task("Fetching compute log URLs...", total=None)
                log_urls = client.get_compute_log_urls(full_run_id)
                progress.remove_task(task)

            url = log_urls.get("stdout_url" if stdout else "stderr_url")
            if not url:
                print_warning(
                    f"No {'stdout' if stdout else 'stderr'} logs available for this run"
                )
                print_info(
                    "Compute logs may only be available for Dagster+ deployments"
                )
                raise typer.Exit(1)

            # Download log content
            with create_spinner(
                f"Downloading {'stdout' if stdout else 'stderr'}..."
            ) as progress:
                task = progress.add_task(
                    f"Downloading {'stdout' if stdout else 'stderr'}...", total=None
                )
                response = requests.get(url)
                response.raise_for_status()
                log_content = response.text
                progress.remove_task(task)

            if output:
                with open(output, "w") as f:
                    f.write(log_content)
                print_info(f"Logs saved to {output}")
            elif json_output:
                console.print_json(
                    data={
                        "type": "stdout" if stdout else "stderr",
                        "content": log_content,
                    }
                )
            else:
                console.print(
                    Panel(
                        log_content,
                        title=f"{'stdout' if stdout else 'stderr'} logs",
                        expand=False,
                    )
                )

        else:
            # Default: show event logs
            with create_spinner("Fetching event logs...") as progress:
                task = progress.add_task("Fetching event logs...", total=None)
                logs_data = client.get_run_logs(full_run_id, limit=100)
                progress.remove_task(task)

            events = logs_data.get("events", [])
            if not events:
                print_warning("No log events found for this run")
                raise typer.Exit(1)

            # Check for errors
            has_errors = any(
                event.get("level") in ["ERROR", "CRITICAL"]
                or event.get("__typename")
                in ["ExecutionStepFailureEvent", "RunFailureEvent"]
                for event in events
            )

            if json_output:
                console.print_json(data=events)
            else:
                # Display events in a table
                table = Table(title=f"Event Logs for Run {full_run_id[:8]}...")
                table.add_column("Time", style="cyan", no_wrap=True)
                table.add_column("Level", style="yellow")
                table.add_column("Type", style="blue")
                table.add_column("Message", style="white")

                # Collect stack traces for display after table
                stack_traces = []

                for event in events:
                    timestamp = client.format_timestamp(event.get("timestamp"))
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
                                }
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
                                {"type": "Run Failure", "step": None, "stack": stack}
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
                            )
                        )
                        console.print()  # Add spacing between stack traces

                    # Add note about potential truncation
                    print_info("Note: Stack trace may be truncated")

                # If there are more events, indicate it
                if logs_data.get("hasMore"):
                    print_info(
                        f"\nShowing first {len(events)} events. More events available."
                    )

            # Auto-fetch stderr if there are errors (unless --events-only)
            if has_errors and not events_only and not json_output:
                print_info("\nErrors detected. Fetching stderr logs...")

                log_urls = client.get_compute_log_urls(full_run_id)
                if stderr_url := log_urls.get("stderr_url"):
                    try:
                        response = requests.get(stderr_url)
                        response.raise_for_status()
                        if stderr_content := response.text.strip():
                            console.print("\n")
                            console.print(
                                Panel(
                                    stderr_content,
                                    title="stderr output",
                                    expand=False,
                                    border_style="red",
                                )
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
