"""TLDR content for dgc commands."""

from typing import Dict

# TLDR content for each command
TLDR_CONTENT: Dict[str, str] = {
    "main": """[bold magenta]dgc[/bold magenta]

  [magenta]Dagster CLI - Command-line interface for Dagster+ operations.
  Similar to GitHub's 'gh' CLI, but for managing Dagster+ deployments.
  More information: [red italic]https://github.com/pedramamani/dagster-cli[/red italic][/magenta]

  [green]Authenticate with your Dagster+ deployment:[/green]

    [cyan]dgc auth login[/cyan]

  [green]Check health status of all assets (find problems):[/green]

    [cyan]dgc asset health[/cyan]

  [green]View details about a specific asset:[/green]

    [cyan]dgc asset view analytics/daily_revenue[/cyan]

  [green]View logs for a failed run (see stack traces):[/green]

    [cyan]dgc run logs abc123 --stderr[/cyan]

  [green]List recent runs to find failures:[/green]

    [cyan]dgc run list --limit 10[/cyan]""",
    "auth": """[bold magenta]dgc auth[/bold magenta]

  [magenta]Authentication management for Dagster+ deployments.
  More information: [red italic]https://github.com/pedramamani/dagster-cli#authentication[/red italic][/magenta]

  [green]Login to a Dagster+ deployment:[/green]

    [cyan]dgc auth login[/cyan]

  [green]Check current authentication status:[/green]

    [cyan]dgc auth status[/cyan]

  [green]Switch to a different profile:[/green]

    [cyan]dgc auth switch production[/cyan]""",
    "job": """[bold magenta]dgc job[/bold magenta]

  [magenta]Manage Dagster jobs - list, view details, and run jobs.
  More information: [red italic]https://github.com/pedramamani/dagster-cli#job-operations[/red italic][/magenta]

  [green]List all available jobs:[/green]

    [cyan]dgc job list[/cyan]

  [green]Run a job:[/green]

    [cyan]dgc job run daily_etl[/cyan]

  [green]Run a job with configuration file:[/green]

    [cyan]dgc job run etl_pipeline --config-file config.json[/cyan]""",
    "run": """[bold magenta]dgc run[/bold magenta]

  [magenta]Monitor and manage Dagster run executions.
  More information: [red italic]https://github.com/pedramamani/dagster-cli#run-management[/red italic][/magenta]

  [green]List recent runs:[/green]

    [cyan]dgc run list[/cyan]

  [green]View details of a specific run (partial ID works):[/green]

    [cyan]dgc run view abc123[/cyan]

  [green]View Python stack trace for a failed run:[/green]

    [cyan]dgc run logs abc123 --stderr[/cyan]""",
    "asset": """[bold magenta]dgc asset[/bold magenta]

  [magenta]Manage Dagster assets - list, materialize, and check health.
  More information: [red italic]https://github.com/pedramamani/dagster-cli#asset-operations[/red italic][/magenta]

  [green]Check health status of all assets:[/green]

    [cyan]dgc asset health[/cyan]

  [green]List all assets:[/green]

    [cyan]dgc asset list[/cyan]

  [green]View details about a specific asset:[/green]

    [cyan]dgc asset view analytics/daily_revenue[/cyan]

  [green]Materialize an asset:[/green]

    [cyan]dgc asset materialize analytics/daily_revenue[/cyan]""",
    "repo": """[bold magenta]dgc repo[/bold magenta]

  [magenta]Repository management - list locations and reload code.
  More information: [red italic]https://github.com/pedramamani/dagster-cli#repository-management[/red italic][/magenta]

  [green]List all repository locations:[/green]

    [cyan]dgc repo list[/cyan]

  [green]Reload a repository location:[/green]

    [cyan]dgc repo reload data_etl[/cyan]""",
    "deployment": """[bold magenta]dgc deployment[/bold magenta]

  [magenta]Manage Dagster+ deployments including branch deployments.
  More information: [red italic]https://github.com/pedramamani/dagster-cli#deployment-management[/red italic][/magenta]

  [green]List all available deployments:[/green]

    [cyan]dgc deployment list[/cyan]""",
    "mcp": """[bold magenta]dgc mcp[/bold magenta]

  [magenta]Model Context Protocol server for AI assistant integration.
  More information: [red italic]https://github.com/pedramamani/dagster-cli#mcp-operations[/red italic][/magenta]

  [green]Start MCP server (stdio mode by default):[/green]

    [cyan]dgc mcp start[/cyan]

  [green]Start MCP server in HTTP mode:[/green]

    [cyan]dgc mcp start --http[/cyan]""",
}


def print_tldr(command: str = "main") -> None:
    """Print TLDR content for a command and exit."""
    from dagster_cli.utils.output import console

    if command in TLDR_CONTENT:
        console.print(TLDR_CONTENT[command])
    else:
        console.print(f"[red]No TLDR content available for '{command}'[/red]")
