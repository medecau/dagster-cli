"""Tests for MCP command functionality."""

import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from dagster_cli.cli import app


runner = CliRunner()


def test_mcp_command_exists():
    """Test that the mcp command is available."""
    result = runner.invoke(app, ["mcp", "--help"])
    assert result.exit_code == 0
    assert "MCP operations" in result.stdout
    assert "start" in result.stdout


def test_mcp_start_requires_authentication():
    """Test that mcp start fails without authentication."""
    with patch("dagster_cli.commands.mcp.DagsterClient") as mock_client:
        # Simulate auth error
        mock_client.side_effect = Exception("No authentication found")

        result = runner.invoke(app, ["mcp", "start"])
        assert result.exit_code == 1
        assert "authentication" in result.stdout.lower()


def test_mcp_start_stdio_mode():
    """Test MCP server starts in stdio mode (default)."""
    with (
        patch("dagster_cli.commands.mcp.DagsterClient") as mock_client,
        patch("dagster_cli.commands.mcp.start_stdio_server") as mock_stdio,
    ):
        # Mock successful auth
        mock_client.return_value = MagicMock()

        runner.invoke(app, ["mcp", "start"])

        # Should call stdio server, not http
        mock_stdio.assert_called_once()
        assert mock_client.called


def test_mcp_start_http_mode():
    """Test MCP server starts in HTTP mode with --http flag."""
    with (
        patch("dagster_cli.commands.mcp.DagsterClient") as mock_client,
        patch("dagster_cli.commands.mcp.start_http_server") as mock_http,
    ):
        # Mock successful auth
        mock_client.return_value = MagicMock()

        runner.invoke(app, ["mcp", "start", "--http"])

        # Should call http server, not stdio
        mock_http.assert_called_once()
        assert mock_client.called


def test_mcp_start_with_profile():
    """Test MCP server respects profile option."""
    with (
        patch("dagster_cli.commands.mcp.DagsterClient") as mock_client,
        patch("dagster_cli.commands.mcp.start_stdio_server"),
    ):
        mock_client.return_value = MagicMock()

        runner.invoke(app, ["mcp", "start", "--profile", "staging"])

        # Should pass profile to client
        mock_client.assert_called_with("staging", None)


def test_mcp_server_validates_auth_on_startup():
    """Test that server validates authentication immediately on startup."""
    from dagster_cli.utils.errors import AuthenticationError

    with patch("dagster_cli.commands.mcp.DagsterClient") as mock_client:
        # Simulate auth failure
        mock_client.side_effect = AuthenticationError("Invalid token")

        result = runner.invoke(app, ["mcp", "start"])

        assert result.exit_code == 1
        assert (
            "Invalid token" in result.stdout
            or "authentication" in result.stdout.lower()
        )


@pytest.mark.asyncio
async def test_mcp_tools_registered():
    """Test that all expected tools are registered in the MCP server."""
    from dagster_cli.mcp_server import create_mcp_server

    # Create mock client
    mock_client = MagicMock()

    # Create server
    server = create_mcp_server(mock_client)

    # Get registered tools using the public method
    tools = await server.list_tools()
    tool_names = [tool.name for tool in tools]

    # Verify expected tools exist
    expected_tools = [
        "list_jobs",
        "run_job",
        "get_run_status",
        "list_runs",
        "list_assets",
        "reload_repository",
        "get_run_logs",
        "get_compute_logs",
    ]

    for expected in expected_tools:
        assert expected in tool_names, (
            f"Tool {expected} not found in registered tools: {tool_names}"
        )
