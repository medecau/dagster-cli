"""Utilities for run-related operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dagster_cli.client import DagsterClient


def resolve_run_id(
    client: DagsterClient,
    run_id: str,
    recent_runs_limit: int = 50,
) -> tuple[str, str | None, list[dict[str, Any]] | None]:
    """
    Resolve a potentially partial run ID to a full run ID.

    Special aliases:
      ``latest``       — most recent run regardless of status
      ``last-failure`` — most recent FAILURE run

    Returns:
        tuple: (full_run_id, error_message, matching_runs)
        - If successful: (full_run_id, None, None)
        - If no matches: (run_id, "No runs found matching...", None)
        - If ambiguous:  (run_id, "Multiple runs found matching...", matching_runs)
    """
    if run_id == "latest":
        recent = client.get_recent_runs(limit=1)
        if recent:
            return recent[0]["id"], None, None
        return run_id, "No runs found", None

    if run_id == "last-failure":
        failures = client.get_recent_runs(limit=50, status="FAILURE")
        if failures:
            return failures[0]["id"], None, None
        return run_id, "No failed runs found", None

    # Full ID — return as-is (20+ chars is unambiguous)
    if len(run_id) >= 20:
        return run_id, None, None

    # Prefix search against recent runs
    recent_runs = client.get_recent_runs(limit=recent_runs_limit)
    if matching_runs := [r for r in recent_runs if r["id"].startswith(run_id)]:
        if len(matching_runs) == 1:
            return matching_runs[0]["id"], None, None
        return (
            run_id,
            f"Multiple runs found matching '{run_id}'",
            matching_runs[:5],
        )
    return run_id, f"No runs found matching '{run_id}'", None
