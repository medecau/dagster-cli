"""MCP (Model Context Protocol) command for exposing Dagster+ functionality."""

import typer
from typing import Optional

from dagster_cli.utils.output import console, print_error, print_info
from dagster_cli.utils.tldr import print_tldr


app = typer.Typer(
    help="""[bold]MCP operations[/bold]

[bold cyan]Available commands:[/bold cyan]
  [green]start[/green]    Start MCP server exposing Dagster+ functionality
           • Default: stdio mode for local integration
           • [dim]--http[/dim] for HTTP mode (port 8000)
           • [dim]--profile[/dim] to use specific profile

[dim]Use 'dgc mcp COMMAND --help' for detailed options[/dim]""",
    rich_markup_mode="rich",
)


@app.callback(invoke_without_command=True)
def mcp_callback(
    ctx: typer.Context,
    tldr: bool = typer.Option(
        False,
        "--tldr",
        help="Show practical examples and exit",
        is_eager=True,
    ),
):
    """MCP operations callback."""
    if tldr:
        print_tldr("mcp")
        raise typer.Exit()

    # If no command was provided, show help
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


@app.command()
def start(
    http: bool = typer.Option(
        False, "--http", help="Use HTTP transport instead of stdio"
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Use specific profile", envvar="DGC_PROFILE"
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help="Host to bind to (HTTP mode only, currently uses default)",
    ),
    port: int = typer.Option(
        8000, "--port", help="Port to bind to (HTTP mode only, currently uses default)"
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
        # Validate authentication early - fail fast
        from dagster_cli.config import Config

        config = Config()
        profile_data = config.get_profile(profile)

        if not profile_data.get("url") or not profile_data.get("token"):
            raise Exception(
                "No authentication found. Please run 'dgc auth login' first."
            )

        # Show startup message
        print_info(f"Starting MCP server in {'HTTP' if http else 'stdio'} mode...")
        print_info(f"Connected to: {profile_data.get('url', 'Unknown')}")

        if http:
            start_http_server(profile, host, port, path)
        else:
            start_stdio_server(profile)

    except Exception as e:
        print_error(f"Failed to start MCP server: {str(e)}")
        raise typer.Exit(1) from e


def start_stdio_server(profile_name: Optional[str]):
    """Start MCP server in stdio mode."""
    from dagster_cli.mcp_server import create_mcp_server

    # Create the MCP server with all tools/resources
    server = create_mcp_server(profile_name)

    # Run the FastMCP server using its built-in stdio transport
    server.run("stdio")


def start_http_server(
    profile_name: Optional[str],
    host: str = "127.0.0.1",
    port: int = 8000,
    path: str = "/mcp/",
):
    """Start MCP server in HTTP mode using streamable-http transport."""
    from dagster_cli.mcp_server import create_mcp_server

    # Create the MCP server with all tools/resources
    server = create_mcp_server(profile_name)

    # Run the FastMCP server using streamable-http transport
    print_info(f"Starting HTTP server on http://{host}:{port}")
    print_info(f"MCP endpoint: http://{host}:{port}{path}")

    # Note: FastMCP doesn't support host/port/path in run() signature in our version
    # We'll use the default for now and document this limitation
    server.run("streamable-http")
