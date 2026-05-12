"""MCP server implementation for Dagster CLI."""

import functools
from typing import Any, cast

import requests
from mcp.server.fastmcp import FastMCP

from dagster_cli.client import DagsterClient
from dagster_cli.utils.errors import DagsterCLIError
from dagster_cli.utils.run_utils import resolve_run_id

# Log level hierarchy for filtering
LEVEL_HIERARCHY = {
    "DEBUG": 0,
    "INFO": 1,
    "WARNING": 2,
    "ERROR": 3,
    "CRITICAL": 4,
}

# Map event types to log levels
EVENT_TYPE_LEVELS = {
    "ExecutionStepFailureEvent": "ERROR",
    "RunFailureEvent": "ERROR",
    "ExecutionStepSuccessEvent": "INFO",
    "RunSuccessEvent": "INFO",
    "MaterializationEvent": "INFO",
    "AssetMaterializationPlannedEvent": "INFO",
    "HandledOutputEvent": "INFO",
    "EngineEvent": "INFO",
    "RunStartEvent": "INFO",
    "AlertStartEvent": "WARNING",
    "AlertSuccessEvent": "INFO",
    "AlertFailureEvent": "ERROR",
}


def should_include_event(event: dict, min_level: str | None) -> bool:
    """Return True if *event* meets the *min_level* threshold."""
    if not min_level:
        return True
    event_level = event.get("level") or EVENT_TYPE_LEVELS.get(
        event.get("__typename", "")
    )
    if not event_level or min_level not in LEVEL_HIERARCHY:
        return True
    return LEVEL_HIERARCHY.get(event_level, -1) >= LEVEL_HIERARCHY.get(min_level, 0)


def mcp_error(error_type: str, error: str, **extra: Any) -> dict:
    """Build a standard error response envelope for MCP tools."""
    return {"status": "error", "error_type": error_type, "error": error, **extra}


def _resolve_run_id_or_error(
    client: DagsterClient, run_id: str
) -> tuple[str | None, dict | None]:
    """Resolve a partial run ID, returning (full_id, None) or (None, error_dict)."""
    full_run_id, error_msg, matching_runs = resolve_run_id(client, run_id)
    if not error_msg:
        return full_run_id, None
    if matching_runs:
        return None, mcp_error(
            "Ambiguous",
            error_msg,
            matches=[
                {"id": r["id"], "job": r["pipeline"]["name"]} for r in matching_runs
            ],
        )
    return None, mcp_error("NotFound", error_msg)


def _fetch_compute_log(client: DagsterClient, run_id: str, log_type: str) -> dict:
    """Fetch stdout or stderr content for a run. Returns a result dict."""
    log_urls = client.get_compute_log_urls(run_id)
    url = log_urls.get(f"{log_type}_url")
    if not url:
        return {
            "available": False,
            "note": f"{log_type} logs not available (may require Dagster+)",
        }
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        content = response.text.strip()
        return {"available": True, "content": content}
    except requests.RequestException as e:
        return {"available": False, "error": str(e)}


def _mcp_tool(fn):
    """Decorator that wraps an async MCP tool with standard error handling."""

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except DagsterCLIError as e:
            return mcp_error(type(e).__name__, str(e))
        except Exception as e:
            return mcp_error("UnknownError", str(e))

    return wrapper


def create_mcp_server(profile_name: str | None) -> FastMCP:  # noqa: C901
    """Create MCP server with Dagster+ tools."""
    mcp = FastMCP("dagster-cli")

    @mcp.tool()
    @_mcp_tool
    async def list_jobs(
        location: str | None = None,
        deployment: str | None = None,
    ) -> dict:
        """List available Dagster jobs.

        Use this tool to discover what jobs exist in the deployment before running
        one. Filter by ``location`` when the deployment has multiple code locations.

        Args:
            location: Optional filter by repository location name.
            deployment: Dagster+ deployment name (default: prod). Use
                ``dgc deployment list`` to see valid names.

        Returns:
            ``{status, count, jobs}`` — jobs include name, description, location,
            and repository fields.
        """
        client = DagsterClient(profile_name, deployment)
        jobs = client.list_jobs(location)
        return {"status": "success", "count": len(jobs), "jobs": jobs}

    @mcp.tool()
    @_mcp_tool
    async def run_job(
        job_name: str,
        run_config: dict | None = None,
        repository_location_name: str | None = None,
        repository_name: str | None = None,
        deployment: str | None = None,
    ) -> dict:
        """Submit a Dagster job for execution.

        This triggers an *asynchronous* run — it returns immediately with a run
        ID. Use ``get_run_status`` to poll for completion.

        Args:
            job_name: Exact name of the job (from ``list_jobs``).
            run_config: Optional run configuration dict (YAML-equivalent).
            repository_location_name: Code location name (overrides profile default).
            repository_name: Repository name (overrides profile default).
            deployment: Dagster+ deployment name (default: prod).

        Returns:
            ``{status, run_id, url, message}``
        """
        client = DagsterClient(profile_name, deployment)
        run_id = client.submit_job_run(
            job_name=job_name,
            run_config=run_config,
            repository_location_name=repository_location_name,
            repository_name=repository_name,
        )
        return {
            "status": "success",
            "run_id": run_id,
            "url": client.run_url(run_id),
            "message": f"Job '{job_name}' submitted successfully",
        }

    @mcp.tool()
    @_mcp_tool
    async def get_run_status(run_id: str, deployment: str | None = None) -> dict:
        """Get the status and timing of a specific run.

        Accepts full or partial run IDs, and the special aliases
        ``latest`` (most recent run) and ``last-failure`` (most recent failed run).

        Args:
            run_id: Full or partial run ID, ``latest``, or ``last-failure``.
            deployment: Dagster+ deployment name (default: prod).

        Returns:
            ``{status, run}`` — run includes id, status, startTime, endTime, stats.
            Status values: SUCCESS, FAILURE, STARTED, QUEUED, CANCELED, CANCELING.
        """
        client = DagsterClient(profile_name, deployment)
        full_run_id, err = _resolve_run_id_or_error(client, run_id)
        if err:
            return err
        full_run_id = cast("str", full_run_id)
        run = client.get_run_status(full_run_id)
        if not run:
            return mcp_error("NotFound", f"Run '{run_id}' not found")
        return {"status": "success", "run": run}

    @mcp.tool()
    @_mcp_tool
    async def list_runs(
        limit: int = 10,
        status: str | None = None,
        deployment: str | None = None,
    ) -> dict:
        """Get recent run history.

        Args:
            limit: Number of runs to return (default: 10, max practical: 50).
            status: Filter by run status. One of: SUCCESS, FAILURE, STARTED,
                QUEUED, CANCELED, CANCELING.
            deployment: Dagster+ deployment name (default: prod).

        Returns:
            ``{status, count, runs}``
        """
        client = DagsterClient(profile_name, deployment)
        runs = client.get_recent_runs(limit=limit, status=status)
        return {"status": "success", "count": len(runs), "runs": runs}

    @mcp.tool()
    @_mcp_tool
    async def list_assets(
        prefix: str | None = None,
        group: str | None = None,
        location: str | None = None,
        deployment: str | None = None,
    ) -> dict:
        """List assets in the deployment.

        Args:
            prefix: Filter assets whose key starts with this string
                (e.g., ``"finance/"``).
            group: Filter by asset group name.
            location: Filter by code location name.
            deployment: Dagster+ deployment name (default: prod).

        Returns:
            ``{status, count, assets}`` — each asset has key (list of path parts),
            groupName, computeKind, location, repository.

        Note:
            Asset keys are represented as path lists (e.g., ``["finance", "revenue"]``).
            Join with ``"/"`` to form the human-readable key used in materialize_asset.
        """
        client = DagsterClient(profile_name, deployment)
        assets = client.list_assets(prefix=prefix, group=group, location=location)
        return {"status": "success", "count": len(assets), "assets": assets}

    @mcp.tool()
    @_mcp_tool
    async def materialize_asset(
        asset_key: str,
        partition_key: str | None = None,
        deployment: str | None = None,
    ) -> dict:
        """Trigger materialization of an asset.

        This submits an *asynchronous* run — it does NOT materialize synchronously.
        Use ``get_run_status`` to poll for the result.

        The asset must exist in the deployment and the profile must have
        ``location`` and ``repository`` configured (or the deployment must have
        exactly one code location).

        Args:
            asset_key: Slash-separated asset key (e.g., ``"finance/revenue"``
                or ``"my_asset"``).
            partition_key: Optional partition to materialize (e.g., ``"2024-01-01"``).
            deployment: Dagster+ deployment name (default: prod).

        Returns:
            ``{status, run_id, url, message}``
        """
        client = DagsterClient(profile_name, deployment)
        run_id = client.materialize_asset(
            asset_key=asset_key,
            partition_key=partition_key,
        )
        return {
            "status": "success",
            "run_id": run_id,
            "url": client.run_url(run_id),
            "message": f"Asset '{asset_key}' materialization submitted",
        }

    @mcp.tool()
    @_mcp_tool
    async def reload_repository(
        location_name: str,
        deployment: str | None = None,
    ) -> dict:
        """Reload a repository location so new code definitions take effect.

        Args:
            location_name: Name of the code location to reload.
            deployment: Dagster+ deployment name (default: prod).

        Returns:
            ``{status, message}``
        """
        client = DagsterClient(profile_name, deployment)
        client.reload_repository_location(location_name)
        return {
            "status": "success",
            "message": f"Repository location '{location_name}' reloaded",
        }

    @mcp.tool()
    @_mcp_tool
    async def get_run_logs(  # noqa: C901
        run_id: str,
        limit: int = 100,
        level: str | None = None,
        include_stderr_on_error: bool = True,
        deployment: str | None = None,
    ) -> dict:
        """Get event logs for a run, with optional level filtering.

        For investigating failures: use ``level="ERROR"`` to focus on errors, or
        set ``include_stderr_on_error=True`` (default) to auto-fetch stderr when
        error events are present.

        Args:
            run_id: Full or partial run ID, ``latest``, or ``last-failure``.
            limit: Max events to return after filtering (default: 100).
            level: Minimum log level. One of: DEBUG, INFO, WARNING, ERROR, CRITICAL.
            include_stderr_on_error: Auto-fetch stderr when errors are found
                (default: True). Requires Dagster+.
            deployment: Dagster+ deployment name (default: prod).

        Returns:
            ``{status, run_id, events, statistics, has_errors}``
            If errors found and ``include_stderr_on_error``: also ``stderr``.
        """
        client = DagsterClient(profile_name, deployment)
        full_run_id, err = _resolve_run_id_or_error(client, run_id)
        if err:
            return err
        full_run_id = cast("str", full_run_id)

        filter_level = None
        if level:
            filter_level = level.upper()
            if filter_level not in LEVEL_HIERARCHY:
                return mcp_error(
                    "InvalidArgument",
                    f"Invalid log level: {level}."
                    " Valid levels: DEBUG, INFO, WARNING, ERROR, CRITICAL",
                )

        level_counts = {lvl: 0 for lvl in LEVEL_HIERARCHY}
        all_events: list = []
        filtered_events: list = []
        cursor = None
        has_more = True
        total_fetched = 0

        while has_more:
            logs_data = client.get_run_logs(full_run_id, limit=100, cursor=cursor)
            events = logs_data.get("events", [])
            total_fetched += len(events)

            for event in events:
                event_level = event.get("level") or EVENT_TYPE_LEVELS.get(
                    event.get("__typename", "")
                )
                if event_level and event_level in level_counts:
                    level_counts[event_level] += 1

            if filter_level:
                for event in events:
                    if should_include_event(event, filter_level):
                        filtered_events.append(event)
                        if len(filtered_events) >= limit:
                            has_more = False
                            break
            else:
                all_events.extend(events)
                if len(all_events) >= limit:
                    has_more = False
                    break

            if has_more:
                has_more = logs_data.get("hasMore", False)
                cursor = logs_data.get("cursor")

        events_to_return = (
            filtered_events[:limit] if filter_level else all_events[:limit]
        )
        error_types = {"ExecutionStepFailureEvent", "RunFailureEvent"}
        has_errors = any(
            event.get("level") in ["ERROR", "CRITICAL"]
            or event.get("__typename") in error_types
            for event in events_to_return
        )

        result: dict = {
            "status": "success",
            "run_id": full_run_id,
            "events": events_to_return,
            "statistics": {
                "total_events": total_fetched,
                "levels": level_counts,
                "filter_applied": filter_level,
                "events_matching_filter": len(filtered_events)
                if filter_level
                else total_fetched,
                "events_returned": len(events_to_return),
            },
            "has_more_filtered": (len(filtered_events) > limit)
            if filter_level
            else (len(all_events) > limit),
            "has_errors": has_errors,
        }

        if has_errors and include_stderr_on_error:
            stderr_result = _fetch_compute_log(client, full_run_id, "stderr")
            if stderr_result.get("available"):
                result["stderr"] = stderr_result["content"]
                result["stderr_available"] = True
            else:
                result["stderr_available"] = False
                result["stderr_note"] = stderr_result.get("note") or stderr_result.get(
                    "error", "stderr unavailable"
                )

        return result

    @mcp.tool()
    @_mcp_tool
    async def get_compute_logs(
        run_id: str,
        log_type: str = "stderr",
        deployment: str | None = None,
    ) -> dict:
        """Get stdout or stderr compute logs for a run (Dagster+ only).

        Prefer ``get_run_logs`` with ``include_stderr_on_error=True`` for
        investigating failures — it combines event logs and stderr in one call.
        Use this tool when you need raw stdout or the full stderr independently.

        Args:
            run_id: Full or partial run ID, ``latest``, or ``last-failure``.
            log_type: ``"stdout"`` or ``"stderr"`` (default: ``"stderr"``).
            deployment: Dagster+ deployment name (default: prod).

        Returns:
            ``{status, run_id, log_type, content, size}``
        """
        if log_type not in ["stdout", "stderr"]:
            return mcp_error("InvalidArgument", "log_type must be 'stdout' or 'stderr'")

        client = DagsterClient(profile_name, deployment)
        full_run_id, err = _resolve_run_id_or_error(client, run_id)
        if err:
            return err
        full_run_id = cast("str", full_run_id)

        log_result = _fetch_compute_log(client, full_run_id, log_type)
        if not log_result.get("available"):
            return mcp_error(
                "NotAvailable",
                log_result.get("error")
                or log_result.get("note", f"No {log_type} logs available"),
            )

        content = log_result["content"]
        return {
            "status": "success",
            "run_id": full_run_id,
            "log_type": log_type,
            "content": content,
            "size": len(content),
        }

    return mcp
