"""Automation-related commands for Dagster CLI."""

from typing import Optional

import typer

from dagster_cli.client import DagsterClient
from dagster_cli.utils.output import (
    console,
    create_spinner,
    print_error,
    print_info,
    print_runs_table,
    print_warning,
)

app = typer.Typer(
    help="Automation management (schedules and sensors)", no_args_is_help=True
)


@app.command("list")
def list_automations(
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Use specific profile"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all automations (schedules and sensors)."""
    try:
        client = DagsterClient(profile)

        with create_spinner("Fetching automations...") as progress:
            task = progress.add_task("Fetching automations...", total=None)
            automations = client.list_automations()
            progress.remove_task(task)

        if not automations:
            print_warning("No automations found")
            return

        if json_output:
            console.print_json(data=automations)
        else:
            print_info(f"Found {len(automations)} automations")
            from dagster_cli.utils.output import print_automations_table

            print_automations_table(automations)

    except Exception as e:
        print_error(f"Failed to list automations: {str(e)}")
        raise typer.Exit(1) from e


@app.command()
def view(
    name: str = typer.Argument(..., help="Automation name"),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Use specific profile"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """View automation details."""
    try:
        client = DagsterClient(profile)

        with create_spinner("Fetching automation details...") as progress:
            task = progress.add_task("Fetching automation details...", total=None)
            automation = client.get_automation_details(name)
            progress.remove_task(task)

        if not automation:
            print_error(f"Automation '{name}' not found")
            raise typer.Exit(1)

        if json_output:
            console.print_json(data=automation)
        else:
            from dagster_cli.utils.output import print_automation_details

            print_automation_details(automation)

    except Exception as e:
        print_error(f"Failed to view automation: {str(e)}")
        raise typer.Exit(1) from e


@app.command()
def history(
    name: str = typer.Argument(..., help="Automation name"),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Use specific profile"
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of entries to show"),
    ticks: bool = typer.Option(
        False, "--ticks", help="Show tick history instead of runs"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """View automation history (runs or ticks)."""
    try:
        client = DagsterClient(profile)

        if ticks:
            with create_spinner("Fetching tick history...") as progress:
                task = progress.add_task("Fetching tick history...", total=None)
                ticks_data = client.get_automation_ticks(name, limit=limit)
                progress.remove_task(task)

            if not ticks_data:
                print_warning(f"No tick history found for '{name}'")
                return

            if json_output:
                console.print_json(data=ticks_data)
            else:
                print_info(f"Showing {len(ticks_data)} ticks for '{name}'")
                from dagster_cli.utils.output import print_automation_ticks_table

                print_automation_ticks_table(ticks_data)
        else:
            # Default: show runs
            with create_spinner("Fetching run history...") as progress:
                task = progress.add_task("Fetching run history...", total=None)
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
