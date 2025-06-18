"""Asset-related commands for Dagster CLI."""

import typer
from typing import Optional
from datetime import datetime, timedelta
from rich import box
from rich.table import Table

from dagster_cli.client import DagsterClient
from dagster_cli.utils.output import (
    console,
    print_success,
    print_error,
    print_warning,
    print_info,
    create_spinner,
)


app = typer.Typer(help="Asset operations", no_args_is_help=True)


@app.command("list")
def list_assets(
    prefix: Optional[str] = typer.Option(
        None, "--prefix", "-p", help="Filter assets by prefix"
    ),
    group: Optional[str] = typer.Option(
        None, "--group", "-g", help="Filter by asset group"
    ),
    location: Optional[str] = typer.Option(
        None, "--location", "-l", help="Filter by repository location"
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Use specific profile"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """List all assets."""
    try:
        client = DagsterClient(profile)

        with create_spinner("Fetching assets...") as progress:
            task = progress.add_task("Fetching assets...", total=None)
            assets = client.list_assets(prefix=prefix, group=group, location=location)
            progress.remove_task(task)

        if not assets:
            print_warning("No assets found")
            return

        if json_output:
            console.print_json(data=assets)
        else:
            # Create table
            table = Table(box=box.ROUNDED)
            table.add_column("Asset Key", style="cyan")
            table.add_column("Group", style="magenta")
            table.add_column("Location", style="blue")
            table.add_column("Compute Kind", style="white")
            table.add_column("Materialized", style="green")

            for asset in assets:
                asset_key = asset.get("key", {}).get("path", [])
                asset_key_str = (
                    "/".join(asset_key)
                    if isinstance(asset_key, list)
                    else str(asset_key)
                )
                group_name = asset.get("groupName", "—")
                location_name = asset.get("location", "—")
                compute_kind = asset.get("computeKind", "—")

                # Check if materialized
                latest_run = asset.get("latestMaterializationRun")
                if latest_run:
                    status = latest_run.get("status", "")
                    if status == "SUCCESS":
                        materialized = "✓"
                    else:
                        materialized = "✗"
                else:
                    materialized = "—"

                table.add_row(
                    asset_key_str, group_name, location_name, compute_kind, materialized
                )

            print_info(f"Found {len(assets)} assets")
            console.print(table)

    except Exception as e:
        print_error(f"Failed to list assets: {str(e)}")
        raise typer.Exit(1)


@app.command()
def view(
    asset_key: str = typer.Argument(
        ..., help="Asset key (e.g., 'my_asset' or 'prefix/my_asset')"
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Use specific profile"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """View asset details."""
    try:
        client = DagsterClient(profile)

        with create_spinner("Fetching asset details...") as progress:
            task = progress.add_task("Fetching asset details...", total=None)
            asset = client.get_asset_details(asset_key)
            progress.remove_task(task)

        if not asset:
            print_error(f"Asset '{asset_key}' not found")
            raise typer.Exit(1)

        if json_output:
            console.print_json(data=asset)
        else:
            # Display asset information
            console.print(f"\n[bold cyan]Asset: {asset_key}[/bold cyan]")

            if asset.get("description"):
                console.print(f"[white]Description:[/white] {asset['description']}")

            if asset.get("groupName"):
                console.print(f"[white]Group:[/white] {asset['groupName']}")

            if asset.get("computeKind"):
                console.print(f"[white]Compute Kind:[/white] {asset['computeKind']}")

            # Dependencies
            deps = asset.get("dependencies", [])
            if deps:
                console.print(f"\n[white]Dependencies ({len(deps)}):[/white]")
                for dep in deps:
                    dep_asset = dep.get("asset", {})
                    dep_key = dep_asset.get("assetKey", {}).get("path", [])
                    dep_key_str = (
                        "/".join(dep_key) if isinstance(dep_key, list) else str(dep_key)
                    )
                    
                    # Get status from latest materialization
                    status = "NEVER"
                    materializations = dep_asset.get("assetMaterializations", [])
                    if materializations and len(materializations) > 0:
                        run_info = materializations[0].get("runOrError", {})
                        if run_info and run_info.get("__typename") == "Run":
                            status = run_info.get("status", "UNKNOWN")
                    
                    # Format status with color
                    if status == "SUCCESS":
                        status_display = f"[green][{status}][/green]"
                    elif status == "FAILURE":
                        status_display = f"[red][{status}][/red]"
                    elif status == "STARTED":
                        status_display = f"[yellow][{status}][/yellow]"
                    elif status == "NEVER":
                        status_display = f"[dim][{status}][/dim]"
                    else:
                        status_display = f"[white][{status}][/white]"
                    
                    console.print(f"  - {dep_key_str} {status_display}")

            # Dependents (downstream assets)
            dependents = asset.get("dependedBy", [])
            if dependents:
                console.print(f"\n[white]Dependents ({len(dependents)}):[/white]")
                for dependent in dependents:
                    dep_asset = dependent.get("asset", {})
                    dep_key = dep_asset.get("assetKey", {}).get("path", [])
                    dep_key_str = (
                        "/".join(dep_key) if isinstance(dep_key, list) else str(dep_key)
                    )
                    
                    # Get status from latest materialization
                    status = "NEVER"
                    materializations = dep_asset.get("assetMaterializations", [])
                    if materializations and len(materializations) > 0:
                        run_info = materializations[0].get("runOrError", {})
                        if run_info and run_info.get("__typename") == "Run":
                            status = run_info.get("status", "UNKNOWN")
                    
                    # Format status with color
                    if status == "SUCCESS":
                        status_display = f"[green][{status}][/green]"
                    elif status == "FAILURE":
                        status_display = f"[red][{status}][/red]"
                    elif status == "STARTED":
                        status_display = f"[yellow][{status}][/yellow]"
                    elif status == "NEVER":
                        status_display = f"[dim][{status}][/dim]"
                    else:
                        status_display = f"[white][{status}][/white]"
                    
                    console.print(f"  - {dep_key_str} {status_display}")

            # Latest materialization
            materializations = asset.get("assetMaterializations", [])
            if materializations and len(materializations) > 0:
                latest = materializations[0]
                run_info = latest.get("runOrError", {})

                console.print("\n[white]Latest Materialization:[/white]")
                console.print(f"  Run ID: {latest.get('runId', 'Unknown')}")

                if "status" in run_info:
                    status = run_info["status"]
                    if status == "SUCCESS":
                        status_display = f"[green]{status}[/green]"
                    elif status == "FAILURE":
                        status_display = f"[red]{status}[/red]"
                    else:
                        status_display = f"[yellow]{status}[/yellow]"
                    console.print(f"  Status: {status_display}")

                timestamp = latest.get("timestamp")
                if timestamp:
                    # Convert timestamp string to datetime
                    time_str = client.format_timestamp(float(timestamp))
                    console.print(f"  Time: {time_str}")
            else:
                console.print("\n[yellow]Never materialized[/yellow]")

    except Exception as e:
        print_error(f"Failed to view asset: {str(e)}")
        raise typer.Exit(1)


@app.command()
def materialize(
    asset_key: str = typer.Argument(..., help="Asset key to materialize"),
    partition: Optional[str] = typer.Option(
        None, "--partition", "-p", help="Partition to materialize"
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Use specific profile"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Materialize an asset."""
    try:
        # Show what we're about to do
        print_info(f"Asset: {asset_key}")
        if partition:
            print_info(f"Partition: {partition}")

        # Confirmation
        if not yes:
            if not typer.confirm("Materialize this asset?"):
                print_warning("Cancelled")
                return

        client = DagsterClient(profile)

        with create_spinner("Submitting materialization...") as progress:
            task = progress.add_task("Submitting materialization...", total=None)
            run_id = client.materialize_asset(
                asset_key=asset_key, partition_key=partition
            )
            progress.remove_task(task)

        print_success("Materialization submitted successfully!")
        print_info(f"Run ID: {run_id}")

        # Construct URL if possible
        url = client.profile.get("url", "")
        if url:
            if not url.startswith("http"):
                url = f"https://{url}"
            print_info(f"View at: {url}/runs/{run_id}")

    except Exception as e:
        print_error(f"Failed to materialize asset: {str(e)}")
        raise typer.Exit(1)


@app.command()
def health(
    all_assets: bool = typer.Option(
        False, "--all", "-a", help="Show all assets (default: unhealthy only)"
    ),
    stale_hours: int = typer.Option(
        24, "--stale-hours", help="Hours before asset is considered stale"
    ),
    group: Optional[str] = typer.Option(
        None, "--group", "-g", help="Filter by asset group"
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Use specific profile"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Check asset health status."""
    try:
        client = DagsterClient(profile)

        with create_spinner("Checking asset health...") as progress:
            task = progress.add_task("Checking asset health...", total=None)
            assets = client.get_asset_health(group=group)
            progress.remove_task(task)

        if not assets:
            print_warning("No assets found")
            return

        # Calculate health status for each asset
        now = datetime.now()
        stale_threshold = now - timedelta(hours=stale_hours)

        healthy_assets = []
        stale_assets = []
        failed_assets = []
        never_materialized = []

        for asset in assets:
            asset_key = asset.get("key", {}).get("path", [])
            asset_key_str = (
                "/".join(asset_key) if isinstance(asset_key, list) else str(asset_key)
            )

            materializations = asset.get("assetMaterializations", [])

            if not materializations:
                never_materialized.append(
                    {
                        "key": asset_key_str,
                        "group": asset.get("groupName", "—"),
                        "status": "Never Materialized",
                        "last_update": "—",
                    }
                )
            else:
                latest = materializations[0]
                run_info = latest.get("runOrError", {})
                status = run_info.get("status", "UNKNOWN")
                timestamp = latest.get("timestamp")

                if timestamp:
                    last_update = datetime.fromtimestamp(float(timestamp) / 1000)
                    last_update_str = last_update.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    last_update = None
                    last_update_str = "Unknown"

                asset_info = {
                    "key": asset_key_str,
                    "group": asset.get("groupName", "—"),
                    "last_update": last_update_str,
                    "run_id": latest.get("runId", ""),
                }

                if status == "FAILURE":
                    asset_info["status"] = "Failed"
                    failed_assets.append(asset_info)
                elif last_update and last_update < stale_threshold:
                    asset_info["status"] = "Stale"
                    stale_assets.append(asset_info)
                else:
                    asset_info["status"] = "Healthy"
                    healthy_assets.append(asset_info)

        # Prepare output
        all_assets_list = (
            failed_assets + never_materialized + stale_assets + healthy_assets
        )
        unhealthy_count = (
            len(failed_assets) + len(never_materialized) + len(stale_assets)
        )

        if json_output:
            output = {
                "summary": {
                    "total": len(assets),
                    "healthy": len(healthy_assets),
                    "stale": len(stale_assets),
                    "failed": len(failed_assets),
                    "never_materialized": len(never_materialized),
                },
                "assets": all_assets_list
                if all_assets
                else (failed_assets + never_materialized + stale_assets),
            }
            console.print_json(data=output)
        else:
            # Print summary
            console.print("\n[bold]Asset Health Summary[/bold]")
            console.print(f"Total Assets: {len(assets)}")
            console.print(f"[green]Healthy: {len(healthy_assets)}[/green]")
            console.print(f"[yellow]Stale: {len(stale_assets)}[/yellow]")
            console.print(f"[red]Failed: {len(failed_assets)}[/red]")
            console.print(f"[red]Never Materialized: {len(never_materialized)}[/red]")

            # Create table
            assets_to_show = (
                all_assets_list
                if all_assets
                else (failed_assets + never_materialized + stale_assets)
            )

            if assets_to_show:
                console.print("\n[bold]Asset Details[/bold]")
                if not all_assets:
                    console.print(
                        f"[dim]Showing {unhealthy_count} unhealthy assets (use --all to see all)[/dim]"
                    )

                table = Table(box=box.ROUNDED)
                table.add_column("Asset Key", style="cyan")
                table.add_column("Group", style="magenta")
                table.add_column("Status", style="white")
                table.add_column("Last Update", style="white")

                for asset_info in assets_to_show:
                    status = asset_info["status"]

                    # Color code status
                    if status == "Healthy":
                        status_display = f"[green]{status}[/green]"
                    elif status == "Stale":
                        status_display = f"[yellow]{status}[/yellow]"
                    else:
                        status_display = f"[red]{status}[/red]"

                    table.add_row(
                        asset_info["key"],
                        asset_info["group"],
                        status_display,
                        asset_info["last_update"],
                    )

                console.print(table)

                if stale_assets and not all_assets:
                    console.print(f"\n[dim]Stale threshold: {stale_hours} hours[/dim]")
            else:
                if all_assets:
                    print_success("All assets are healthy!")
                else:
                    print_success("No unhealthy assets found!")

    except Exception as e:
        print_error(f"Failed to check asset health: {str(e)}")
        raise typer.Exit(1)
