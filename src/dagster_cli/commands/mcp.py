"""MCP (Model Context Protocol) command for exposing Dagster+ functionality."""

import typer
from typing import Optional

from dagster_cli.utils.output import print_error, print_info


app = typer.Typer(help="MCP operations", no_args_is_help=True)


@app.command()
def start(
    http: bool = typer.Option(
        False, "--http", help="Use HTTP transport instead of stdio"
    ),
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Use specific profile", envvar="DGC_PROFILE"
    ),
):
    """Start MCP server exposing Dagster+ functionality.

    By default, starts in stdio mode for local integration with Claude, Cursor, etc.
    Use --http flag to start HTTP server for remote access.
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
            start_http_server(profile)
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


def start_http_server(profile_name: Optional[str]):
    """Start MCP server in HTTP mode."""
    import uvicorn
    from dagster_cli.mcp_server import create_mcp_app

    # Create FastAPI app with MCP server
    app = create_mcp_app(profile_name)

    # Run with uvicorn
    print_info("Starting HTTP server on http://localhost:8000")
    print_info("MCP endpoint: http://localhost:8000/mcp")
    uvicorn.run(app, host="0.0.0.0", port=8000)
