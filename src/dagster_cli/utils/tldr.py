"""TLDR content for dgc commands."""

# TLDR content for each command
REPO_URL = "https://github.com/medecau/dagster-cli"
TLDR_CONTENT: dict[str, str] = {
    "main": (
        """\
  [magenta]dgc — The CLI for Dagster+ operators, by operators[/magenta]

  [green]Authenticate with your Dagster+ deployment:[/green]

    [cyan]dgc auth login[/cyan]

  [green]Check health status of all assets (find problems):[/green]

    [cyan]dgc asset health[/cyan]

  [green]View details about a specific asset:[/green]

    [cyan]dgc asset view analytics/daily_revenue[/cyan]

  [green]View logs for a failed run (see stack traces):[/green]

    [cyan]dgc run logs abc123 --stderr[/cyan]

  [green]List recent runs to find failures:[/green]

    [cyan]dgc run list --limit 10[/cyan]

  """
        f"[dim italic]source code: [red italic]{REPO_URL}[/red italic]\n"
        "  MIT-licensed — bugs, ideas, and patches welcome[/dim italic]"
    ),
    "auth": """\
  [magenta]Authentication management for Dagster+ deployments.[/magenta]

  [green]Login to a Dagster+ deployment:[/green]

    [cyan]dgc auth login[/cyan]

  [green]Check current authentication status:[/green]

    [cyan]dgc auth status[/cyan]

  [green]Switch to a different profile:[/green]

    [cyan]dgc auth switch production[/cyan]""",
    "job": """\
  [magenta]Manage Dagster jobs - list, view details, and run jobs.[/magenta]

  [green]List all available jobs:[/green]

    [cyan]dgc job list[/cyan]

  [green]Run a job:[/green]

    [cyan]dgc job run daily_etl[/cyan]

  [green]Run a job with configuration file:[/green]

    [cyan]dgc job run etl_pipeline --config-file config.json[/cyan]""",
    "run": """\
  [magenta]Monitor and manage Dagster run executions.[/magenta]

  [green]List recent runs:[/green]

    [cyan]dgc run list[/cyan]

  [green]View details of a specific run (partial ID works):[/green]

    [cyan]dgc run view abc123[/cyan]

  [green]View Python stack trace for a failed run:[/green]

    [cyan]dgc run logs abc123 --stderr[/cyan]""",
    "asset": """\
  [magenta]Manage Dagster assets - list, materialize, and check health.[/magenta]

  [green]Check health status of all assets:[/green]

    [cyan]dgc asset health[/cyan]

  [green]List all assets:[/green]

    [cyan]dgc asset list[/cyan]

  [green]View details about a specific asset:[/green]

    [cyan]dgc asset view analytics/daily_revenue[/cyan]

  [green]Materialize an asset:[/green]

    [cyan]dgc asset materialize analytics/daily_revenue[/cyan]""",
    "repo": """\
  [magenta]Repository management - list locations and reload code.[/magenta]

  [green]List all repository locations:[/green]

    [cyan]dgc repo list[/cyan]

  [green]Reload a repository location:[/green]

    [cyan]dgc repo reload data_etl[/cyan]""",
    "deployment": """\
  [magenta]Manage Dagster+ deployments including branch deployments.[/magenta]

  [green]List all available deployments:[/green]

    [cyan]dgc deployment list[/cyan]""",
    "mcp": """\
  [magenta]MCP server for AI agents.[/magenta]

  [green]Start MCP server (stdio mode by default):[/green]

    [cyan]dgc mcp start[/cyan]

  [green]Start MCP server in HTTP mode:[/green]

    [cyan]dgc mcp start --http[/cyan]""",
    "automation": """\
  [magenta]Manage Dagster schedules and sensors.[/magenta]

  [green]List all schedules and sensors:[/green]

    [cyan]dgc automation list[/cyan]

  [green]View details of a schedule or sensor:[/green]

    [cyan]dgc automation view daily_schedule[/cyan]

  [green]View recent ticks and runs:[/green]

    [cyan]dgc automation history daily_schedule[/cyan]""",
}
