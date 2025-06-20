"""Test utilities."""

from unittest.mock import MagicMock

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
