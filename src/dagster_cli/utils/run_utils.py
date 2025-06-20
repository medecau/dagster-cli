"""Utilities for run-related operations."""

from typing import Optional, Tuple, List, Dict, Any

from dagster_cli.client import DagsterClient


def resolve_run_id(
    client: DagsterClient, run_id: str, recent_runs_limit: int = 50
) -> Tuple[str, Optional[str], Optional[List[Dict[str, Any]]]]:
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
    matching_runs = [r for r in recent_runs if r["id"].startswith(run_id)]

    if not matching_runs:
        return run_id, f"No runs found matching '{run_id}'", None
    elif len(matching_runs) == 1:
        return matching_runs[0]["id"], None, None
    else:
        # Return first 5 matches for display
        return (run_id, f"Multiple runs found matching '{run_id}'", matching_runs[:5])
