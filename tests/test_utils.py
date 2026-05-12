"""Test utilities."""

import pytest
from unittest.mock import MagicMock, patch

from dagster_cli.client import _split_url_for_dagster_client, DagsterClient
from dagster_cli.utils.errors import APIError
from dagster_cli.utils.run_utils import resolve_run_id


class TestResolveRunId:
    """Test the resolve_run_id utility function."""

    def test_full_run_id_returned_as_is(self):
        """Test that full run IDs (20+ chars) are returned unchanged."""
        client = MagicMock()
        run_id = "abcdef123456789012345678901234567890"

        result_id, error, matches = resolve_run_id(client, run_id)

        assert result_id == run_id
        assert error is None
        assert matches is None
        # Should not call get_recent_runs for full IDs
        client.get_recent_runs.assert_not_called()

    def test_partial_id_single_match(self):
        """Test partial ID that matches exactly one run."""
        client = MagicMock()
        client.get_recent_runs.return_value = [
            {"id": "run_abc123_full_id_here", "pipeline": {"name": "job1"}},
            {"id": "run_def456_full_id_here", "pipeline": {"name": "job2"}},
        ]

        result_id, error, matches = resolve_run_id(client, "run_abc")

        assert result_id == "run_abc123_full_id_here"
        assert error is None
        assert matches is None
        client.get_recent_runs.assert_called_once_with(limit=50)

    def test_partial_id_no_matches(self):
        """Test partial ID that matches no runs."""
        client = MagicMock()
        client.get_recent_runs.return_value = [
            {"id": "run_abc123_full_id_here", "pipeline": {"name": "job1"}},
            {"id": "run_def456_full_id_here", "pipeline": {"name": "job2"}},
        ]

        result_id, error, matches = resolve_run_id(client, "run_xyz")

        assert result_id == "run_xyz"
        assert error == "No runs found matching 'run_xyz'"
        assert matches is None

    def test_partial_id_multiple_matches(self):
        """Test partial ID that matches multiple runs."""
        client = MagicMock()
        client.get_recent_runs.return_value = [
            {"id": "run_abc123_full_id_here", "pipeline": {"name": "job1"}},
            {"id": "run_abc456_full_id_here", "pipeline": {"name": "job2"}},
            {"id": "run_abc789_full_id_here", "pipeline": {"name": "job3"}},
            {"id": "run_abcdef_full_id_here", "pipeline": {"name": "job4"}},
            {"id": "run_abcxyz_full_id_here", "pipeline": {"name": "job5"}},
            {"id": "run_abc000_full_id_here", "pipeline": {"name": "job6"}},
        ]

        result_id, error, matches = resolve_run_id(client, "run_abc")

        assert result_id == "run_abc"
        assert error == "Multiple runs found matching 'run_abc'"
        assert matches is not None
        assert len(matches) == 5  # Should return first 5 matches
        assert matches[0]["id"] == "run_abc123_full_id_here"

    def test_custom_limit(self):
        """Test using a custom limit for recent runs."""
        client = MagicMock()
        client.get_recent_runs.return_value = []

        resolve_run_id(client, "run_abc", recent_runs_limit=100)

        client.get_recent_runs.assert_called_once_with(limit=100)

    def test_exact_20_char_id(self):
        """Test that exactly 20 character IDs are treated as full IDs."""
        client = MagicMock()
        run_id = "12345678901234567890"  # Exactly 20 chars

        result_id, error, matches = resolve_run_id(client, run_id)

        assert result_id == run_id
        assert error is None
        assert matches is None
        client.get_recent_runs.assert_not_called()


class TestSplitUrlForDagsterClient:
    def test_https_url_with_deployment_path(self):
        assert _split_url_for_dagster_client("https://myorg.dagster.cloud/prod") == (
            "myorg.dagster.cloud/prod",
            True,
        )

    def test_http_localhost_with_port(self):
        assert _split_url_for_dagster_client("http://localhost:3000") == (
            "localhost:3000",
            False,
        )

    def test_bare_hostname_assumes_https(self):
        assert _split_url_for_dagster_client("myorg.dagster.cloud") == (
            "myorg.dagster.cloud",
            True,
        )

    def test_bare_hostname_with_path(self):
        assert _split_url_for_dagster_client("myorg.dagster.cloud/prod") == (
            "myorg.dagster.cloud/prod",
            True,
        )

    def test_trailing_slash_stripped(self):
        assert _split_url_for_dagster_client("https://myorg.dagster.cloud/prod/") == (
            "myorg.dagster.cloud/prod",
            True,
        )


_FAKE_PROFILE = {
    "url": "https://myorg.dagster.cloud/prod",
    "token": "test-token",
    "location": "my_location",
    "repository": "__repository__",
}


@pytest.fixture
def client_with_mock_gql():
    """DagsterClient with Config and gql_client mocked out."""
    with patch("dagster_cli.client.Config") as mock_config:
        mock_config.return_value.get_profile.return_value = _FAKE_PROFILE
        client = DagsterClient()
        mock_execute = MagicMock()
        client._gql_client = MagicMock()
        client._gql_client.execute = mock_execute
        yield client, mock_execute


class TestMaterializeAsset:
    def test_simple_key_produces_single_path_component(self, client_with_mock_gql):
        client, mock_execute = client_with_mock_gql
        mock_execute.return_value = {
            "launchPipelineExecution": {
                "__typename": "LaunchRunSuccess",
                "run": {"runId": "run-123"},
            }
        }

        run_id = client.materialize_asset("my_asset")

        assert run_id == "run-123"
        _, kwargs = mock_execute.call_args
        selector = kwargs["variable_values"]["executionParams"]["selector"]
        assert selector["assetSelection"] == [{"path": ["my_asset"]}]

    def test_slashed_key_produces_multi_component_path(self, client_with_mock_gql):
        client, mock_execute = client_with_mock_gql
        mock_execute.return_value = {
            "launchPipelineExecution": {
                "__typename": "LaunchRunSuccess",
                "run": {"runId": "run-456"},
            }
        }

        run_id = client.materialize_asset("prefix/my_asset")

        assert run_id == "run-456"
        _, kwargs = mock_execute.call_args
        selector = kwargs["variable_values"]["executionParams"]["selector"]
        assert selector["assetSelection"] == [{"path": ["prefix", "my_asset"]}]

    def test_partition_key_becomes_dagster_partition_tag(self, client_with_mock_gql):
        client, mock_execute = client_with_mock_gql
        mock_execute.return_value = {
            "launchPipelineExecution": {
                "__typename": "LaunchRunSuccess",
                "run": {"runId": "run-789"},
            }
        }

        client.materialize_asset("my_asset", partition_key="2024-01-01")

        _, kwargs = mock_execute.call_args
        tags = kwargs["variable_values"]["executionParams"]["executionMetadata"]["tags"]
        assert {"key": "dagster/partition", "value": "2024-01-01"} in tags

    def test_no_partition_key_sends_empty_tags(self, client_with_mock_gql):
        client, mock_execute = client_with_mock_gql
        mock_execute.return_value = {
            "launchPipelineExecution": {
                "__typename": "LaunchRunSuccess",
                "run": {"runId": "run-000"},
            }
        }

        client.materialize_asset("my_asset")

        _, kwargs = mock_execute.call_args
        tags = kwargs["variable_values"]["executionParams"]["executionMetadata"]["tags"]
        assert tags == []

    def test_non_success_typename_raises_api_error(self, client_with_mock_gql):
        client, mock_execute = client_with_mock_gql
        mock_execute.return_value = {
            "launchPipelineExecution": {
                "__typename": "PipelineNotFoundError",
                "message": "pipeline not found",
            }
        }

        with pytest.raises(APIError, match="PipelineNotFoundError"):
            client.materialize_asset("my_asset")
