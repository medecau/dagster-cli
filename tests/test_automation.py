"""Tests for automation commands."""

import pytest
from unittest.mock import patch
from typer.testing import CliRunner

from dagster_cli.cli import app
from dagster_cli.utils.errors import APIError


runner = CliRunner()


@pytest.fixture
def mock_client():
    """Create a mock DagsterClient."""
    with patch("dagster_cli.commands.automation.DagsterClient") as mock:
        yield mock


class TestAutomationList:
    """Test automation list command."""

    def test_list_automations_success(self, mock_client):
        """Test successful automation listing."""
        # Mock response
        mock_instance = mock_client.return_value
        mock_instance.list_automations.return_value = [
            {
                "name": "daily_update",
                "type": "Schedule",
                "target": "update_job",
                "status": "RUNNING",
                "cron_schedule": "0 0 * * *",
                "last_tick": 1700000000.0,
                "last_run_status": "SUCCESS",
                "last_run_timestamp": 1700000000.0,
                "tick_status": "SUCCESS",
                "tick_run_count": 1,
                "location": "prod",
                "repository": "main_repo",
            },
            {
                "name": "file_sensor",
                "type": "Sensor",
                "target": "process_job",
                "status": "STOPPED",
                "cron_schedule": None,
                "last_tick": 1700001000.0,
                "last_run_status": "FAILURE",
                "last_run_timestamp": 1700001000.0,
                "tick_status": "SUCCESS",
                "tick_run_count": 1,
                "location": "prod",
                "repository": "main_repo",
            },
        ]

        result = runner.invoke(app, ["automation", "list"])

        assert result.exit_code == 0
        assert "Found 2 automations" in result.output
        assert "daily_update" in result.output
        assert "file_sensor" in result.output
        assert "0 0 * * *" in result.output  # Cron schedule
        assert "Sensor" in result.output
        assert "1 run" in result.output  # Run count

    def test_list_automations_empty(self, mock_client):
        """Test listing when no automations exist."""
        mock_instance = mock_client.return_value
        mock_instance.list_automations.return_value = []

        result = runner.invoke(app, ["automation", "list"])

        assert result.exit_code == 0
        assert "No automations found" in result.output

    def test_list_automations_json(self, mock_client):
        """Test JSON output for automation list."""
        mock_instance = mock_client.return_value
        mock_instance.list_automations.return_value = [
            {
                "name": "test_schedule",
                "type": "Schedule",
                "target": "test_job",
                "status": "RUNNING",
            }
        ]

        result = runner.invoke(app, ["automation", "list", "--json"])

        assert result.exit_code == 0
        assert '"name": "test_schedule"' in result.output
        assert '"type": "Schedule"' in result.output

    def test_list_automations_error(self, mock_client):
        """Test error handling in list command."""
        mock_instance = mock_client.return_value
        mock_instance.list_automations.side_effect = APIError("Failed to connect")

        result = runner.invoke(app, ["automation", "list"])

        assert result.exit_code == 1
        assert "Failed to list automations" in result.output


class TestAutomationView:
    """Test automation view command."""

    def test_view_automation_success(self, mock_client):
        """Test successful automation viewing."""
        mock_instance = mock_client.return_value
        mock_instance.get_automation_details.return_value = {
            "name": "daily_update",
            "type": "Schedule",
            "target": "update_job",
            "description": "Daily data update",
            "status": "RUNNING",
            "cron_schedule": "0 0 * * *",
            "execution_timezone": "UTC",
            "location": "prod",
            "repository": "main_repo",
            "recent_ticks": [
                {"status": "SUCCESS", "timestamp": 1700000000.0},
                {"status": "SUCCESS", "timestamp": 1699913600.0},
                {"status": "FAILURE", "timestamp": 1699827200.0},
            ],
        }

        result = runner.invoke(app, ["automation", "view", "daily_update"])

        assert result.exit_code == 0
        assert "Schedule Details" in result.output
        assert "daily_update" in result.output
        assert "Daily data update" in result.output
        assert "0 0 * * *" in result.output

    def test_view_automation_not_found(self, mock_client):
        """Test viewing non-existent automation."""
        mock_instance = mock_client.return_value
        mock_instance.get_automation_details.return_value = None

        result = runner.invoke(app, ["automation", "view", "nonexistent"])

        assert result.exit_code == 1
        assert "Automation 'nonexistent' not found" in result.output

    def test_view_automation_json(self, mock_client):
        """Test JSON output for automation view."""
        mock_instance = mock_client.return_value
        mock_instance.get_automation_details.return_value = {
            "name": "test_sensor",
            "type": "Sensor",
            "target": "test_job",
            "status": "STOPPED",
        }

        result = runner.invoke(app, ["automation", "view", "test_sensor", "--json"])

        assert result.exit_code == 0
        assert '"name": "test_sensor"' in result.output
        assert '"type": "Sensor"' in result.output


class TestAutomationHistory:
    """Test automation history command."""

    def test_history_runs_success(self, mock_client):
        """Test successful run history viewing."""
        mock_instance = mock_client.return_value
        mock_instance.get_automation_runs.return_value = [
            {
                "id": "abc123",
                "pipeline": {"name": "update_job"},
                "status": "SUCCESS",
                "startTime": 1700000000.0,
                "endTime": 1700001000.0,
            },
            {
                "id": "def456",
                "pipeline": {"name": "update_job"},
                "status": "FAILURE",
                "startTime": 1699913600.0,
                "endTime": 1699914000.0,
            },
        ]

        result = runner.invoke(app, ["automation", "history", "daily_update"])

        assert result.exit_code == 0
        assert "Showing 2 runs" in result.output
        assert "abc123" in result.output
        assert "SUCCESS" in result.output
        assert "FAILURE" in result.output

    def test_history_ticks_success(self, mock_client):
        """Test successful tick history viewing."""
        mock_instance = mock_client.return_value
        mock_instance.get_automation_ticks.return_value = [
            {
                "timestamp": 1700000000.0,
                "status": "SUCCESS",
                "run_count": 1,
                "run_ids": ["abc123"],
                "error": None,
            },
            {
                "timestamp": 1699913600.0,
                "status": "SKIPPED",
                "run_count": 0,
                "run_ids": [],
                "error": None,
            },
        ]

        result = runner.invoke(
            app, ["automation", "history", "daily_update", "--ticks"]
        )

        assert result.exit_code == 0
        assert "Showing 2 ticks" in result.output
        assert "SUCCESS" in result.output
        assert "SKIPPED" in result.output
        assert "1 run" in result.output

    def test_history_no_runs(self, mock_client):
        """Test history when no runs exist."""
        mock_instance = mock_client.return_value
        mock_instance.get_automation_runs.return_value = []

        result = runner.invoke(app, ["automation", "history", "new_automation"])

        assert result.exit_code == 0
        assert "No runs found for automation 'new_automation'" in result.output

    def test_history_limit(self, mock_client):
        """Test history with limit parameter."""
        mock_instance = mock_client.return_value
        mock_instance.get_automation_ticks.return_value = []

        result = runner.invoke(
            app, ["automation", "history", "test_automation", "--ticks", "--limit", "5"]
        )

        assert result.exit_code == 0
        mock_instance.get_automation_ticks.assert_called_with(
            "test_automation", limit=5
        )

    def test_history_error(self, mock_client):
        """Test error handling in history command."""
        mock_instance = mock_client.return_value
        mock_instance.get_automation_runs.side_effect = APIError("Failed to fetch runs")

        result = runner.invoke(app, ["automation", "history", "test_automation"])

        assert result.exit_code == 1
        assert "Failed to get automation history" in result.output
