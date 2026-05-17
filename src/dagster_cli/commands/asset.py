"""Asset-related commands for Dagster CLI."""

from datetime import datetime, timezone

import typer

from dagster_cli.client import DagsterClient
from dagster_cli.constants import (
    DEFAULT_LIST_LIMIT,
    DEPLOYMENT_OPTION_HELP,
    DEPLOYMENT_OPTION_NAME,
    DEPLOYMENT_OPTION_SHORT,
)
from dagster_cli.utils.format import colorize_status, format_asset_key, format_timestamp
from dagster_cli.utils.output import (
    console,
    create_spinner,
    print_asset_health_table,
    print_assets_table,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from dagster_cli.utils.tldr import TLDR_CONTENT
from dagster_cli.utils.typer_utils import Typer

app = Typer(
    help="""[bold]Asset operations[/bold]

[bold cyan]Available commands:[/bold cyan]
  [green]list[/green]         List all assets [dim](--prefix, --group, --location)[/dim]
  [green]view[/green]         View asset details [dim]ASSET_KEY [--json][/dim]
  [green]materialize[/green]  Materialize an asset [dim]ASSET_KEY [--partition][/dim]
  [green]health[/green]       Check asset health status [dim](--all, --group)[/dim]

[dim]Use 'dgc asset COMMAND --help' for detailed options[/dim]""",
    epilog=TLDR_CONTENT["asset"],
    rich_markup_mode="rich",
)


@app.callback(invoke_without_command=True)
def asset_callback(ctx: typer.Context):
    """Asset operations callback."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


@app.command("list")
def list_assets(
    prefix: str | None = typer.Option(
        None,
        "--prefix",
        help="Filter assets by prefix",
    ),
    group: str | None = typer.Option(
        None,
        "--group",
        "-g",
        help="Filter by asset group",
    ),
    location: str | None = typer.Option(
        None,
        "--location",
        "-l",
        help="Filter by repository location",
    ),
    limit: int = typer.Option(
        DEFAULT_LIST_LIMIT,
        "--limit",
        "-n",
        help="Maximum number of assets to show",
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
    """List all assets."""
    try:
        client = DagsterClient(profile, deployment)

        with create_spinner("Fetching assets...") as (progress, task):
            assets = client.list_assets(prefix=prefix, group=group, location=location)
            progress.remove_task(task)

        assets = assets[:limit]

        if not assets:
            print_warning("No assets found")
            return

        if json_output:
            console.print_json(data=assets)
        else:
            print_info(f"Found {len(assets)} assets")
            print_assets_table(assets)

    except Exception as e:
        print_error(f"Failed to list assets: {str(e)}")
        raise typer.Exit(1) from e


@app.command()
def view(  # noqa: C901
    asset_key: str = typer.Argument(
        ...,
        help="Asset key (e.g., 'my_asset' or 'prefix/my_asset')",
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
    """View asset details."""
    try:
        client = DagsterClient(profile, deployment)

        with create_spinner("Fetching asset details...") as (progress, task):
            asset = client.get_asset_details(asset_key)
            progress.remove_task(task)

        if not asset:
            print_error(f"Asset '{asset_key}' not found")
            print_info("Use 'dgc asset list' to see available assets")
            raise typer.Exit(1)

        if json_output:
            console.print_json(data=asset)
        else:
            console.print(f"\n[bold cyan]Asset: {asset_key}[/bold cyan]")

            if asset.get("description"):
                console.print(f"[white]Description:[/white] {asset['description']}")
            if asset.get("groupName"):
                console.print(f"[white]Group:[/white] {asset['groupName']}")
            if asset.get("computeKind"):
                console.print(f"[white]Compute Kind:[/white] {asset['computeKind']}")

            if deps := asset.get("dependencies", []):
                console.print(f"\n[white]Dependencies ({len(deps)}):[/white]")
                for dep in deps:
                    dep_asset = dep.get("asset", {})
                    dep_key_str = format_asset_key(
                        dep_asset.get("assetKey", {}).get("path", [])
                    )
                    status = "NEVER"
                    materializations = dep_asset.get("assetMaterializations", [])
                    if materializations:
                        run_info = materializations[0].get("runOrError", {})
                        if run_info and run_info.get("__typename") == "Run":
                            status = run_info.get("status", "UNKNOWN")
                    status_display = colorize_status(status)
                    console.print(f"  - {dep_key_str} [{status_display}]")

            if dependents := asset.get("dependedBy", []):
                console.print(f"\n[white]Dependents ({len(dependents)}):[/white]")
                for dependent in dependents:
                    dep_asset = dependent.get("asset", {})
                    dep_key_str = format_asset_key(
                        dep_asset.get("assetKey", {}).get("path", [])
                    )
                    status = "NEVER"
                    materializations = dep_asset.get("assetMaterializations", [])
                    if materializations:
                        run_info = materializations[0].get("runOrError", {})
                        if run_info and run_info.get("__typename") == "Run":
                            status = run_info.get("status", "UNKNOWN")
                    status_display = colorize_status(status)
                    console.print(f"  - {dep_key_str} [{status_display}]")

            materializations = asset.get("assetMaterializations", [])
            if materializations:
                latest = materializations[0]
                run_info = latest.get("runOrError", {})
                console.print("\n[white]Latest Materialization:[/white]")
                console.print(f"  Run ID: {latest.get('runId', 'Unknown')}")
                if "status" in run_info:
                    console.print(f"  Status: {colorize_status(run_info['status'])}")
                if timestamp := latest.get("timestamp"):
                    console.print(f"  Time: {format_timestamp(float(timestamp))}")
            else:
                console.print("\n[yellow]Never materialized[/yellow]")

    except Exception as e:
        print_error(f"Failed to view asset: {str(e)}")
        raise typer.Exit(1) from e


@app.command()
def materialize(
    asset_key: str = typer.Argument(..., help="Asset key to materialize"),
    partition: str | None = typer.Option(
        None,
        "--partition",
        "-P",  # -P to avoid collision with --profile / -p
        help="Partition to materialize",
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
    watch: bool = typer.Option(
        False,
        "--watch",
        "-w",
        help="Watch run progress until completion",
    ),
):
    """Materialize an asset."""
    try:
        print_info(f"Asset: {asset_key}")
        if partition:
            print_info(f"Partition: {partition}")

        if not yes and not typer.confirm("Materialize this asset?"):
            print_warning("Cancelled")
            return

        client = DagsterClient(profile, deployment)

        with create_spinner("Submitting materialization...") as (progress, task):
            run_id = client.materialize_asset(
                asset_key=asset_key,
                partition_key=partition,
            )
            progress.remove_task(task)

        print_success("Materialization submitted successfully!")
        print_info(f"Run ID: {run_id}")

        if url := client.run_url(run_id):
            print_info(f"View at: {url}")

        if watch:
            _watch_run(client, run_id)

    except Exception as e:
        print_error(f"Failed to materialize asset: {str(e)}")
        raise typer.Exit(1) from e


@app.command()
def health(  # noqa: C901
    all_assets: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Show all assets (default: failed and never materialized only)",
    ),
    group: str | None = typer.Option(
        None,
        "--group",
        "-g",
        help="Filter by asset group",
    ),
    profile: str | None = typer.Option(
        None,
        "--profile",
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
    """Check asset health status."""
    try:
        client = DagsterClient(profile, deployment)

        with create_spinner("Checking asset health...") as (progress, task):
            assets = client.get_asset_health(group=group)
            progress.remove_task(task)

        if not assets:
            print_warning("No assets found")
            return

        healthy_assets = []
        failed_assets = []
        never_materialized = []

        for asset in assets:
            asset_key_str = format_asset_key(asset.get("key", {}).get("path", []))

            if materializations := asset.get("assetMaterializations", []):
                latest = materializations[0]
                run_info = latest.get("runOrError", {})

                status = "UNKNOWN"
                step_key = latest.get("stepKey")
                if step_key and run_info.get("__typename") == "Run":
                    for step_stat in run_info.get("stepStats", []):
                        if step_stat.get("stepKey") == step_key:
                            status = step_stat.get("status", "UNKNOWN")
                            break
                    else:
                        status = run_info.get("status", "UNKNOWN")
                else:
                    status = run_info.get("status", "UNKNOWN")

                if timestamp := latest.get("timestamp"):
                    last_update_str = datetime.fromtimestamp(
                        float(timestamp) / 1000, tz=timezone.utc
                    ).strftime("%Y-%m-%d %H:%M:%S")
                else:
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
                else:
                    asset_info["status"] = "Healthy"
                    healthy_assets.append(asset_info)

            else:
                never_materialized.append(
                    {
                        "key": asset_key_str,
                        "group": asset.get("groupName", "—"),
                        "status": "Never Materialized",
                        "last_update": "—",
                    }
                )

        all_assets_list = failed_assets + never_materialized + healthy_assets
        unhealthy_count = len(failed_assets) + len(never_materialized)

        if json_output:
            output = {
                "summary": {
                    "total": len(assets),
                    "healthy": len(healthy_assets),
                    "failed": len(failed_assets),
                    "never_materialized": len(never_materialized),
                },
                "assets": all_assets_list
                if all_assets
                else (failed_assets + never_materialized),
            }
            console.print_json(data=output)
        else:
            console.print("\n[bold]Asset Health Summary[/bold]")
            console.print(f"Total Assets: {len(assets)}")
            console.print(f"[green]Healthy: {len(healthy_assets)}[/green]")
            console.print(f"[red]Failed: {len(failed_assets)}[/red]")
            console.print(f"[red]Never Materialized: {len(never_materialized)}[/red]")

            assets_to_show = (
                all_assets_list if all_assets else (failed_assets + never_materialized)
            )

            if assets_to_show:
                console.print("\n[bold]Asset Details[/bold]")
                if not all_assets:
                    console.print(
                        f"[dim]Showing {unhealthy_count} unhealthy assets"
                        " (use --all to see all)[/dim]"
                    )
                print_asset_health_table(assets_to_show)
            elif all_assets:
                print_success("All assets are healthy!")
            else:
                print_success("No unhealthy assets found!")

    except Exception as e:
        print_error(f"Failed to check asset health: {str(e)}")
        raise typer.Exit(1) from e


def _watch_run(client: DagsterClient, run_id: str) -> None:
    """Poll run status until it reaches a terminal state."""
    import time

    terminal_statuses = {"SUCCESS", "FAILURE", "CANCELED"}
    print_info(f"Watching run {run_id[:8]}...")
    last_status = None

    while True:
        run = client.get_run_status(run_id)
        if not run:
            print_error("Run not found while watching")
            raise typer.Exit(1)

        status = run.get("status", "UNKNOWN")
        if status != last_status:
            from dagster_cli.utils.format import colorize_status as cs

            print_info(f"Status: {cs(status)}")
            last_status = status

        if status in terminal_statuses:
            if status == "FAILURE":
                print_error("Run failed")
                raise typer.Exit(1)
            if status == "CANCELED":
                print_warning("Run was canceled")
                raise typer.Exit(1)
            print_success("Run completed successfully")
            return

        time.sleep(5)
