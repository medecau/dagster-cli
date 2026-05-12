"""Utilities for run-related operations."""

from typing import Any

from dagster_cli.client import DagsterClient


def resolve_run_id(
    client: DagsterClient,
    run_id: str,
    recent_runs_limit: int = 50,
) -> tuple[str, str | None, list[dict[str, Any]] | None]:
    """
    Resolve a potentially partial run ID to a full run ID.

    Args:
        client: DagsterClient instance
        run_id: Full or partial run ID
        recent_runs_limit: Number of recent runs to search (default: 50)

    Returns:
        tuple: (full_run_id, error_message, matching_runs)
        - If successful: (full_run_id, None, None)
        - If no matches: (run_id, "No runs found matching...", None)
        - If ambiguous: (run_id, "Multiple runs found matching...", matching_runs)
    """
    # If it looks like a full ID (20+ chars), return as-is
    if len(run_id) >= 20:
        return run_id, None, None

    # Search recent runs for matches
    recent_runs = client.get_recent_runs(limit=recent_runs_limit)
    if matching_runs := [r for r in recent_runs if r["id"].startswith(run_id)]:
        return (
            (matching_runs[0]["id"], None, None)
            if len(matching_runs) == 1
            else (
                run_id,
                f"Multiple runs found matching '{run_id}'",
                matching_runs[:5],
            )
        )
    return run_id, f"No runs found matching '{run_id}'", None
