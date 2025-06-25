"""Integration tests for MCP functionality."""

import json
import pytest
from unittest.mock import MagicMock, patch

from dagster_cli.mcp_server import create_mcp_server
from dagster_cli.utils.errors import APIError


async def call_tool_json(server, tool_name, arguments):
    """Helper to call tool and extract JSON response."""
    result = await server.call_tool(tool_name, arguments)
    # MCP returns a list of content objects
    content = result[0].text
    return json.loads(content)


@pytest.mark.asyncio
async def test_list_jobs_tool():
    """Test list_jobs tool returns correct data."""
    with patch("dagster_cli.mcp_server.DagsterClient") as mock_client_class:
        # Mock the client instance
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock list_jobs response
        mock_client.list_jobs.return_value = [
            {
                "name": "daily_etl",
                "description": "Daily ETL pipeline",
                "location": "data_etl",
                "repository": "__repository__",
            },
            {
                "name": "hourly_sync",
                "description": "Hourly data sync",
                "location": "data_etl",
                "repository": "__repository__",
            },
        ]

        server = create_mcp_server("test_profile")

        # Call the tool
        data = await call_tool_json(server, "list_jobs", {})

        # Verify response
        assert data["status"] == "success"
        assert data["count"] == 2
        assert len(data["jobs"]) == 2
        assert data["jobs"][0]["name"] == "daily_etl"

        # Verify client was called with deployment
        mock_client_class.assert_called_with("test_profile", None)
        mock_client.list_jobs.assert_called_once_with(None)


@pytest.mark.asyncio
async def test_list_jobs_tool_with_deployment():
    """Test list_jobs tool with deployment parameter."""
    with patch("dagster_cli.mcp_server.DagsterClient") as mock_client_class:
        # Mock the client instance
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock list_jobs response
        mock_client.list_jobs.return_value = []

        server = create_mcp_server("test_profile")

        # Call the tool with deployment
        await call_tool_json(server, "list_jobs", {"deployment": "staging"})

        # Verify client was called with deployment
        mock_client_class.assert_called_with("test_profile", "staging")


@pytest.mark.asyncio
async def test_run_job_tool():
    """Test run_job tool submits job correctly."""
    with patch("dagster_cli.mcp_server.DagsterClient") as mock_client_class:
        # Mock the client instance
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.profile = {"url": "myorg.dagster.cloud/prod", "token": "test_token"}
        mock_client.deployment = "prod"

        # Mock submit_job_run response
        mock_client.submit_job_run.return_value = "run_abc123"

        server = create_mcp_server("test_profile")

        # Call the tool
        data = await call_tool_json(
            server,
            "run_job",
            {
                "job_name": "daily_etl",
                "config": {"ops": {"my_op": {"config": {"key": "value"}}}},
            },
        )

        # Verify response
        assert data["status"] == "success"
        assert data["run_id"] == "run_abc123"
        assert "myorg.dagster.cloud/prod/runs/run_abc123" in data["url"]
        assert "daily_etl" in data["message"]

        # Verify client was called correctly
        mock_client.submit_job_run.assert_called_once()
        call_args = mock_client.submit_job_run.call_args
        assert call_args.kwargs["job_name"] == "daily_etl"
        assert call_args.kwargs["run_config"] == {
            "ops": {"my_op": {"config": {"key": "value"}}}
        }


@pytest.mark.asyncio
async def test_run_job_tool_with_deployment():
    """Test run_job tool with deployment parameter."""
    with patch("dagster_cli.mcp_server.DagsterClient") as mock_client_class:
        # Mock the client instance
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.profile = {"url": "myorg.dagster.cloud/prod", "token": "test_token"}
        mock_client.deployment = "fix/azure-auth"

        # Mock submit_job_run response
        mock_client.submit_job_run.return_value = "run_xyz789"

        server = create_mcp_server("test_profile")

        # Call the tool with deployment
        data = await call_tool_json(
            server,
            "run_job",
            {
                "job_name": "test_job",
                "deployment": "fix/azure-auth",
            },
        )

        # Verify response
        assert data["status"] == "success"
        assert data["run_id"] == "run_xyz789"
        assert "myorg.dagster.cloud/fix/azure-auth/runs/run_xyz789" in data["url"]

        # Verify client was called with deployment
        mock_client_class.assert_called_with("test_profile", "fix/azure-auth")


@pytest.mark.asyncio
async def test_get_run_status_tool():
    """Test get_run_status tool returns run details."""
    with patch("dagster_cli.mcp_server.DagsterClient") as mock_client_class:
        # Mock the client instance
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock get_run_status response
        mock_client.get_run_status.return_value = {
            "id": "run_abc123",
            "pipeline": {"name": "daily_etl"},
            "status": "SUCCESS",
            "startTime": 1700000000000,
            "endTime": 1700003600000,
            "stats": {"stepsSucceeded": 10, "stepsFailed": 0},
        }

        # Mock get_recent_runs for partial ID resolution
        mock_client.get_recent_runs.return_value = [
            {
                "id": "run_abc123",
                "pipeline": {"name": "daily_etl"},
                "status": "SUCCESS",
                "startTime": 1700000000000,
            }
        ]

        server = create_mcp_server("test_profile")

        # Call with full run ID
        data = await call_tool_json(server, "get_run_status", {"run_id": "run_abc123"})

        # Verify response
        assert data["status"] == "success"
        assert data["run"]["id"] == "run_abc123"
        assert data["run"]["status"] == "SUCCESS"
        assert data["run"]["pipeline"]["name"] == "daily_etl"


@pytest.mark.asyncio
async def test_get_run_status_partial_id():
    """Test get_run_status with partial run ID."""
    with patch("dagster_cli.mcp_server.DagsterClient") as mock_client_class:
        # Mock the client instance
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock get_run_status response
        mock_client.get_run_status.return_value = {
            "id": "run_abc123",
            "pipeline": {"name": "daily_etl"},
            "status": "SUCCESS",
        }

        # Mock get_recent_runs for partial ID resolution
        mock_client.get_recent_runs.return_value = [
            {
                "id": "run_abc123",
                "pipeline": {"name": "daily_etl"},
                "status": "SUCCESS",
                "startTime": 1700000000000,
            },
            {
                "id": "run_def456",
                "pipeline": {"name": "hourly_sync"},
                "status": "FAILURE",
                "startTime": 1699996400000,
            },
        ]

        server = create_mcp_server("test_profile")

        # Call with partial run ID
        data = await call_tool_json(server, "get_run_status", {"run_id": "run_abc"})

        # Verify it found the right run
        assert data["status"] == "success"
        assert data["run"]["id"] == "run_abc123"

        # Verify it searched recent runs
        mock_client.get_recent_runs.assert_called_once_with(limit=50)


@pytest.mark.asyncio
async def test_list_assets_tool():
    """Test list_assets tool returns asset data."""
    with patch("dagster_cli.mcp_server.DagsterClient") as mock_client_class:
        # Mock the client instance
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock list_assets response
        mock_client.list_assets.return_value = [
            {
                "id": "asset1",
                "key": {"path": ["raw", "users"]},
                "groupName": "raw_data",
                "description": "Raw user data",
                "computeKind": "dbt",
            },
            {
                "id": "asset2",
                "key": {"path": ["analytics", "daily_active_users"]},
                "groupName": "analytics",
                "description": "Daily active users metric",
                "computeKind": "python",
            },
        ]

        server = create_mcp_server("test_profile")

        # Call the tool with filters
        data = await call_tool_json(
            server, "list_assets", {"group": "analytics", "prefix": "analytics/"}
        )

        # Verify response
        assert data["status"] == "success"
        assert data["count"] == 2
        assert len(data["assets"]) == 2

        # Verify client was called with filters
        mock_client.list_assets.assert_called_once_with(
            prefix="analytics/", group="analytics", location=None
        )


@pytest.mark.asyncio
async def test_error_handling():
    """Test tools handle errors gracefully."""
    with patch("dagster_cli.mcp_server.DagsterClient") as mock_client_class:
        # Mock the client instance
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Simulate API error
        mock_client.list_jobs.side_effect = APIError("Connection failed")

        server = create_mcp_server("test_profile")

        # Call the tool
        data = await call_tool_json(server, "list_jobs", {})

        # Verify error response
        assert data["status"] == "error"
        assert data["error_type"] == "APIError"
        assert "Connection failed" in data["error"]


@pytest.mark.asyncio
async def test_all_tools_have_descriptions():
    """Test that all tools have proper descriptions."""
    server = create_mcp_server("test_profile")

    tools = await server.list_tools()

    for tool in tools:
        assert tool.description is not None
        assert len(tool.description) > 10  # Meaningful description
        assert tool.inputSchema is not None  # Has parameter schema
