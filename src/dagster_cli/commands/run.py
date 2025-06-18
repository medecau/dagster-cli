"""Run-related commands for Dagster CLI."""

import typer
from typing import Optional

from dagster_cli.client import DagsterClient
from dagster_cli.constants import DEFAULT_RUN_LIMIT
from dagster_cli.utils.output import (
    console, print_success, print_error, print_warning,
    print_info, print_runs_table, print_run_details, create_spinner
)
from dagster_cli.utils.errors import APIError


app = typer.Typer(
    help="Run management",
    no_args_is_help=True
)


@app.command("list")
def list_runs(
    limit: int = typer.Option(
        DEFAULT_RUN_LIMIT,
        "--limit", "-n",
        help="Number of runs to show"
    ),
    status: Optional[str] = typer.Option(
        None,
        "--status", "-s",
        help="Filter by status (SUCCESS, FAILURE, STARTED, etc.)"
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile", "-p",
        help="Use specific profile"
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON"
    )
):
    """List recent runs."""
    try:
        client = DagsterClient(profile)
        
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
        raise typer.Exit(1)


@app.command()
def view(
    run_id: str = typer.Argument(..., help="Run ID to view (can be partial)"),
    profile: Optional[str] = typer.Option(
        None,
        "--profile", "-p",
        help="Use specific profile"
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON"
    )
):
    """View run details."""
    try:
        client = DagsterClient(profile)
        
        # If partial ID provided, try to find full ID
        full_run_id = run_id
        if len(run_id) < 20:  # Likely a partial ID
            with create_spinner("Finding run...") as progress:
                task = progress.add_task("Finding run...", total=None)
                recent_runs = client.get_recent_runs(limit=50)
                progress.remove_task(task)
                
            matching_runs = [r for r in recent_runs if r["id"].startswith(run_id)]
            
            if not matching_runs:
                print_error(f"No runs found matching '{run_id}'")
                raise typer.Exit(1)
            elif len(matching_runs) > 1:
                print_error(f"Multiple runs found matching '{run_id}':")
                for r in matching_runs[:5]:
                    print_info(f"  - {r['id'][:16]}... ({r['pipeline']['name']})")
                raise typer.Exit(1)
            else:
                full_run_id = matching_runs[0]["id"]
        
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
        raise typer.Exit(1)


@app.command()
def cancel(
    run_id: str = typer.Argument(..., help="Run ID to cancel (can be partial)"),
    profile: Optional[str] = typer.Option(
        None,
        "--profile", "-p",
        help="Use specific profile"
    ),
    yes: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Skip confirmation prompt"
    )
):
    """Cancel a running job."""
    print_warning("Run cancellation is not yet implemented in the GraphQL client")
    print_info("This feature will be added in a future version")
    raise typer.Exit(1)


@app.command()
def logs(
    run_id: str = typer.Argument(..., help="Run ID to view logs (can be partial)"),
    profile: Optional[str] = typer.Option(
        None,
        "--profile", "-p",
        help="Use specific profile"
    ),
    follow: bool = typer.Option(
        False,
        "--follow", "-f",
        help="Follow log output (not yet implemented)"
    )
):
    """View run logs."""
    print_warning("Run logs viewing is not yet implemented")
    print_info("This feature will be added in a future version")
    print_info(f"For now, view logs in the Dagster+ UI")
    
    # Try to construct URL
    try:
        client = DagsterClient(profile)
        url = client.profile.get("url", "")
        if url:
            if not url.startswith("http"):
                url = f"https://{url}"
            print_info(f"View at: {url}/runs/{run_id}")
    except:
        pass
    
    raise typer.Exit(1)