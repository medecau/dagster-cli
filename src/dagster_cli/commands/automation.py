"""Automation-related commands for Dagster CLI."""

import typer

from dagster_cli.client import DagsterClient
from dagster_cli.utils.output import (
    console,
    create_spinner,
    print_automation_details,
    print_automation_ticks_table,
    print_automations_table,
    print_error,
    print_info,
    print_runs_table,
    print_warning,
)
from dagster_cli.utils.tldr import TLDR_CONTENT
from dagster_cli.utils.typer_utils import Typer

app = Typer(
    help="Automation management (schedules and sensors)",
    epilog=TLDR_CONTENT["automation"],
    rich_markup_mode="rich",
)


@app.callback(invoke_without_command=True)
def automation_callback(ctx: typer.Context):
    """Automation management callback."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


@app.command("list")
def list_automations(
    profile: str | None = typer.Option(
        None,
        "--profile",
        "-p",
        help="Use specific profile",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all automations (schedules and sensors)."""
    try:
        client = DagsterClient(profile)

        with create_spinner("Fetching automations...") as (progress, task):
            automations = client.list_automations()
            progress.remove_task(task)

        if not automations:
            print_warning("No automations found")
            return

        if json_output:
            console.print_json(data=automations)
        else:
            print_info(f"Found {len(automations)} automations")
            print_automations_table(automations)

    except Exception as e:
        print_error(f"Failed to list automations: {str(e)}")
        raise typer.Exit(1) from e


@app.command()
def view(
    name: str = typer.Argument(..., help="Automation name"),
    profile: str | None = typer.Option(
        None,
        "--profile",
        "-p",
        help="Use specific profile",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """View automation details."""
    try:
        client = DagsterClient(profile)

        with create_spinner("Fetching automation details...") as (progress, task):
            automation = client.get_automation_details(name)
            progress.remove_task(task)

        if not automation:
            from difflib import get_close_matches

            try:
                all_names = [a["name"] for a in client.list_automations()]
                close = get_close_matches(name, all_names, n=3, cutoff=0.6)
            except Exception:  # noqa: BLE001
                close = []
            print_error(f"Automation '{name}' not found")
            if close:
                print_info(f"Did you mean: {', '.join(close)}?")
            else:
                print_info("Use 'dgc automation list' to see available automations")
            raise typer.Exit(1)

        if json_output:
            console.print_json(data=automation)
        else:
            print_automation_details(automation)

    except Exception as e:
        print_error(f"Failed to view automation: {str(e)}")
        raise typer.Exit(1) from e


@app.command()
def history(
    name: str = typer.Argument(..., help="Automation name"),
    profile: str | None = typer.Option(
        None,
        "--profile",
        "-p",
        help="Use specific profile",
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of entries to show"),
    ticks: bool = typer.Option(
        False,
        "--ticks",
        help="Show tick history instead of runs",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """View automation history (runs or ticks)."""
    try:
        client = DagsterClient(profile)

        if ticks:
            with create_spinner("Fetching tick history...") as (progress, task):
                ticks_data = client.get_automation_ticks(name, limit=limit)
                progress.remove_task(task)

            if not ticks_data:
                print_warning(f"No tick history found for '{name}'")
                return

            if json_output:
                console.print_json(data=ticks_data)
            else:
                print_info(f"Showing {len(ticks_data)} ticks for '{name}'")
                print_automation_ticks_table(ticks_data)
        else:
            with create_spinner("Fetching run history...") as (progress, task):
                runs = client.get_automation_runs(name, limit=limit)
                progress.remove_task(task)

            if not runs:
                print_warning(f"No runs found for automation '{name}'")
                return

            if json_output:
                console.print_json(data=runs)
            else:
                print_info(f"Showing {len(runs)} runs for '{name}'")
                print_runs_table(runs)

    except Exception as e:
        print_error(f"Failed to get automation history: {str(e)}")
        raise typer.Exit(1) from e
