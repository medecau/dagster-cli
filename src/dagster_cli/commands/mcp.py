"""MCP (Model Context Protocol) command for exposing Dagster+ functionality."""

import typer
from typing import Optional

from dagster_cli.client import DagsterClient
from dagster_cli.constants import (
    DEPLOYMENT_OPTION_NAME,
    DEPLOYMENT_OPTION_SHORT,
    DEPLOYMENT_OPTION_HELP,
)
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
    deployment: Optional[str] = typer.Option(
        None,
        DEPLOYMENT_OPTION_NAME,
        DEPLOYMENT_OPTION_SHORT,
        help=DEPLOYMENT_OPTION_HELP,
    ),
):
    """Start MCP server exposing Dagster+ functionality.

    By default, starts in stdio mode for local integration with Claude, Cursor, etc.
    Use --http flag to start HTTP server for remote access.
    """
    try:
        # Validate authentication early - fail fast
        client = DagsterClient(profile, deployment)

        # Show startup message
        print_info(f"Starting MCP server in {'HTTP' if http else 'stdio'} mode...")

        # Show URL with deployment if specified
        url = client.profile.get("url", "Unknown")
        if client.deployment and client.deployment != "prod" and url != "Unknown":
            url = url.replace("/prod", f"/{client.deployment}")
        print_info(f"Connected to: {url}")

        if http:
            start_http_server(client)
        else:
            start_stdio_server(client)

    except Exception as e:
        print_error(f"Failed to start MCP server: {str(e)}")
        raise typer.Exit(1) from e


def start_stdio_server(client: DagsterClient):
    """Start MCP server in stdio mode."""
    from dagster_cli.mcp_server import create_mcp_server

    # Create the MCP server with all tools/resources
    server = create_mcp_server(client)

    # Run the FastMCP server using its built-in stdio transport
    server.run("stdio")


def start_http_server(client: DagsterClient):
    """Start MCP server in HTTP mode."""
    import uvicorn
    from dagster_cli.mcp_server import create_mcp_app

    # Create FastAPI app with MCP server
    app = create_mcp_app(client)

    # Run with uvicorn
    print_info("Starting HTTP server on http://localhost:8000")
    print_info("MCP endpoint: http://localhost:8000/mcp")
    uvicorn.run(app, host="0.0.0.0", port=8000)
