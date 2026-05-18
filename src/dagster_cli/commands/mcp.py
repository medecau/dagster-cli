"""MCP (Model Context Protocol) command for exposing Dagster+ functionality."""

import typer

from dagster_cli.utils.output import console, print_error, print_info
from dagster_cli.utils.tldr import TLDR_CONTENT
from dagster_cli.utils.typer_utils import Typer

app = Typer(
    help="""[bold]MCP operations[/bold]

[bold cyan]Available commands:[/bold cyan]
  [green]start[/green]    Start MCP server exposing Dagster+ functionality
           • Default: stdio mode for local integration
           • [dim]--http[/dim] for HTTP mode (port 8000)
           • [dim]--profile[/dim] to use specific profile

[dim]Use 'dgc mcp COMMAND --help' for detailed options[/dim]""",
    epilog=TLDR_CONTENT["mcp"],
    rich_markup_mode="rich",
)


@app.callback(invoke_without_command=True)
def mcp_callback(ctx: typer.Context):
    """MCP operations callback."""
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


@app.command()
def start(
    http: bool = typer.Option(
        False,
        "--http",
        help="Use HTTP transport instead of stdio",
    ),
    profile: str | None = typer.Option(
        None,
        "--profile",
        "-p",
        help="Use specific profile",
        envvar="DGC_PROFILE",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help="Host to bind to (HTTP mode only, currently uses default)",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        help="Port to bind to (HTTP mode only, currently uses default)",
    ),
    path: str = typer.Option(
        "/mcp/",
        "--path",
        help="URL path for MCP endpoint (HTTP mode only, currently uses default)",
    ),
):
    """Start MCP server exposing Dagster+ functionality.

    By default, starts in stdio mode for local integration with Claude, Cursor, etc.
    Use --http flag to start HTTP server for remote access.

    Note: Host, port, and path options are provided for future compatibility but
    are not currently functional due to MCP SDK limitations. The server will use
    default values (127.0.0.1:8000/mcp/).
    """
    try:
        from dagster_cli.client import DagsterClient

        client = DagsterClient(profile)
        print_info(f"Starting MCP server in {'HTTP' if http else 'stdio'} mode...")
        print_info(f"Connected to: {client.profile.get('url', 'Unknown')}")

        if http:
            start_http_server(profile, host, port, path)
        else:
            start_stdio_server(profile)

    except Exception as e:
        print_error(f"Failed to start MCP server: {str(e)}")
        raise typer.Exit(1) from e


def start_stdio_server(profile_name: str | None):
    """Start MCP server in stdio mode."""
    from dagster_cli.mcp_server import create_mcp_server

    server = create_mcp_server(profile_name)
    server.run("stdio")


def start_http_server(
    profile_name: str | None,
    host: str = "127.0.0.1",
    port: int = 8000,
    path: str = "/mcp/",
):
    """Start MCP server in HTTP mode using streamable-http transport."""
    from dagster_cli.mcp_server import create_mcp_server

    server = create_mcp_server(profile_name)
    print_info(f"Starting HTTP server on http://{host}:{port}")
    print_info(f"MCP endpoint: http://{host}:{port}{path}")
    server.run("streamable-http")
