"""MCP server implementation for Dagster CLI."""

from typing import Optional
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


def should_include_event(event, min_level):
    """Check if an event should be included based on the minimum log level."""
    if not min_level:
        return True

    # Get the event's level
    event_level = event.get("level")

    # If no level field, check event type mapping
    if not event_level:
        event_type = event.get("__typename")
        event_level = EVENT_TYPE_LEVELS.get(event_type)

    # If still no level, include it
    if not event_level or min_level not in LEVEL_HIERARCHY:
        return True

    # Compare levels
    return LEVEL_HIERARCHY.get(event_level, -1) >= LEVEL_HIERARCHY.get(min_level, 0)


def create_mcp_server(profile_name: Optional[str]) -> FastMCP:
    """Create MCP server with Dagster+ tools and resources."""
    mcp = FastMCP("dagster-cli")

    # Tool: List jobs
    @mcp.tool()
    async def list_jobs(
        location: Optional[str] = None, deployment: Optional[str] = None
    ) -> dict:
        """List available Dagster jobs.

        Args:
            location: Optional filter by repository location
            deployment: Optional deployment name (defaults to prod)

        Returns:
            List of jobs with their details
        """
        try:
            client = DagsterClient(profile_name, deployment)
            jobs = client.list_jobs(location)
            return {"status": "success", "count": len(jobs), "jobs": jobs}
        except DagsterCLIError as e:
            return {"status": "error", "error_type": type(e).__name__, "error": str(e)}
        except Exception as e:
            return {"status": "error", "error_type": "UnknownError", "error": str(e)}

    # Tool: Run a job
    @mcp.tool()
    async def run_job(
        job_name: str,
        config: Optional[dict] = None,
        location: Optional[str] = None,
        repository: Optional[str] = None,
        deployment: Optional[str] = None,
    ) -> dict:
        """Submit a job for execution.

        Args:
            job_name: Name of the job to run
            config: Optional run configuration
            location: Optional repository location (overrides profile default)
            repository: Optional repository name (overrides profile default)
            deployment: Optional deployment name (defaults to prod)

        Returns:
            Run ID and URL for the submitted job
        """
        try:
            client = DagsterClient(profile_name, deployment)
            run_id = client.submit_job_run(
                job_name=job_name,
                run_config=config,
                repository_location_name=location,
                repository_name=repository,
            )

            # Construct URL if possible
            base_url = client.profile.get("url", "")
            if base_url:
                # Apply deployment to URL
                url = base_url
                if client.deployment and client.deployment != "prod":
                    url = url.replace("/prod", f"/{client.deployment}")
                if not url.startswith("http"):
                    url = f"https://{url}"
                run_url = f"{url}/runs/{run_id}"
            else:
                run_url = None

            return {
                "status": "success",
                "run_id": run_id,
                "url": run_url,
                "message": f"Job '{job_name}' submitted successfully",
            }
        except DagsterCLIError as e:
            return {"status": "error", "error_type": type(e).__name__, "error": str(e)}
        except Exception as e:
            return {"status": "error", "error_type": "UnknownError", "error": str(e)}

    # Tool: Get run status
    @mcp.tool()
    async def get_run_status(run_id: str, deployment: Optional[str] = None) -> dict:
        """Get the status of a specific run.

        Args:
            run_id: Run ID to check (can be partial)
            deployment: Optional deployment name (defaults to prod)

        Returns:
            Run details including status, timing, and stats
        """
        try:
            client = DagsterClient(profile_name, deployment)
            # Resolve partial run ID if needed
            full_run_id, error_msg, matching_runs = resolve_run_id(client, run_id)

            if error_msg:
                if matching_runs:
                    return {
                        "status": "error",
                        "error_type": "Ambiguous",
                        "error": error_msg,
                        "matches": [
                            {"id": r["id"], "job": r["pipeline"]["name"]}
                            for r in matching_runs
                        ],
                    }
                else:
                    return {
                        "status": "error",
                        "error_type": "NotFound",
                        "error": error_msg,
                    }

            run = client.get_run_status(full_run_id)

            if not run:
                return {
                    "status": "error",
                    "error_type": "NotFound",
                    "error": f"Run '{run_id}' not found",
                }

            return {"status": "success", "run": run}
        except DagsterCLIError as e:
            return {"status": "error", "error_type": type(e).__name__, "error": str(e)}
        except Exception as e:
            return {"status": "error", "error_type": "UnknownError", "error": str(e)}

    # Tool: List recent runs
    @mcp.tool()
    async def list_runs(
        limit: int = 10, status: Optional[str] = None, deployment: Optional[str] = None
    ) -> dict:
        """Get recent run history.

        Args:
            limit: Number of runs to return (default: 10)
            status: Optional filter by status (SUCCESS, FAILURE, STARTED, etc.)
            deployment: Optional deployment name (defaults to prod)

        Returns:
            List of recent runs with their details
        """
        try:
            client = DagsterClient(profile_name, deployment)
            runs = client.get_recent_runs(limit=limit, status=status)
            return {"status": "success", "count": len(runs), "runs": runs}
        except DagsterCLIError as e:
            return {"status": "error", "error_type": type(e).__name__, "error": str(e)}
        except Exception as e:
            return {"status": "error", "error_type": "UnknownError", "error": str(e)}

    # Tool: List assets
    @mcp.tool()
    async def list_assets(
        prefix: Optional[str] = None,
        group: Optional[str] = None,
        location: Optional[str] = None,
        deployment: Optional[str] = None,
    ) -> dict:
        """List all assets in the deployment.

        Args:
            prefix: Filter assets by prefix
            group: Filter by asset group
            location: Filter by repository location
            deployment: Optional deployment name (defaults to prod)

        Returns:
            List of assets with their details
        """
        try:
            client = DagsterClient(profile_name, deployment)
            assets = client.list_assets(prefix=prefix, group=group, location=location)
            return {"status": "success", "count": len(assets), "assets": assets}
        except DagsterCLIError as e:
            return {"status": "error", "error_type": type(e).__name__, "error": str(e)}
        except Exception as e:
            return {"status": "error", "error_type": "UnknownError", "error": str(e)}

    # Tool: Materialize asset
    @mcp.tool()
    async def materialize_asset(
        asset_key: str,
        partition_key: Optional[str] = None,
        deployment: Optional[str] = None,
    ) -> dict:
        """Trigger materialization of an asset.

        Args:
            asset_key: Asset key to materialize (e.g., 'my_asset' or 'prefix/my_asset')
            partition_key: Optional partition to materialize
            deployment: Optional deployment name (defaults to prod)

        Returns:
            Run ID and URL for the materialization
        """
        try:
            client = DagsterClient(profile_name, deployment)
            run_id = client.materialize_asset(
                asset_key=asset_key,
                partition_key=partition_key,
            )

            # Construct URL if possible
            base_url = client.profile.get("url", "")
            if base_url:
                # Apply deployment to URL
                url = base_url
                if client.deployment and client.deployment != "prod":
                    url = url.replace("/prod", f"/{client.deployment}")
                if not url.startswith("http"):
                    url = f"https://{url}"
                run_url = f"{url}/runs/{run_id}"
            else:
                run_url = None

            return {
                "status": "success",
                "run_id": run_id,
                "url": run_url,
                "message": f"Asset '{asset_key}' materialization submitted successfully",
            }
        except DagsterCLIError as e:
            return {"status": "error", "error_type": type(e).__name__, "error": str(e)}
        except Exception as e:
            return {"status": "error", "error_type": "UnknownError", "error": str(e)}

    # Tool: Reload repository
    @mcp.tool()
    async def reload_repository(
        location_name: str, deployment: Optional[str] = None
    ) -> dict:
        """Reload a repository location.

        Args:
            location_name: Name of the repository location to reload
            deployment: Optional deployment name (defaults to prod)

        Returns:
            Success status
        """
        try:
            client = DagsterClient(profile_name, deployment)
            success = client.reload_repository_location(location_name)
            return {
                "status": "success" if success else "error",
                "message": f"Repository location '{location_name}' reloaded successfully"
                if success
                else "Failed to reload",
            }
        except DagsterCLIError as e:
            return {"status": "error", "error_type": type(e).__name__, "error": str(e)}
        except Exception as e:
            return {"status": "error", "error_type": "UnknownError", "error": str(e)}

    # Tool: Get run logs
    @mcp.tool()
    async def get_run_logs(
        run_id: str,
        limit: int = 100,
        level: Optional[str] = None,
        include_stderr_on_error: bool = True,
        deployment: Optional[str] = None,
    ) -> dict:
        """Get event logs for a run, with optional level filtering.

        Args:
            run_id: Run ID to check (can be partial)
            limit: Max events to return after filtering (default: 100)
            level: Minimum log level to include (DEBUG/INFO/WARNING/ERROR/CRITICAL)
            include_stderr_on_error: Auto-fetch stderr if errors found (default: True)
            deployment: Optional deployment name (defaults to prod)

        Returns:
            Filtered events with complete level statistics
        """
        import requests

        try:
            client = DagsterClient(profile_name, deployment)
            # Resolve partial run ID if needed
            full_run_id, error_msg, matching_runs = resolve_run_id(client, run_id)

            if error_msg:
                if matching_runs:
                    return {
                        "status": "error",
                        "error_type": "Ambiguous",
                        "error": error_msg,
                        "matches": [
                            {"id": r["id"], "job": r["pipeline"]["name"]}
                            for r in matching_runs
                        ],
                    }
                else:
                    return {
                        "status": "error",
                        "error_type": "NotFound",
                        "error": error_msg,
                    }

            # Validate level if provided
            filter_level = None
            if level:
                filter_level = level.upper()
                if filter_level not in LEVEL_HIERARCHY:
                    return {
                        "status": "error",
                        "error_type": "InvalidArgument",
                        "error": f"Invalid log level: {level}. Valid levels are: DEBUG, INFO, WARNING, ERROR, CRITICAL",
                    }

            # Initialize counters
            level_counts = {lvl: 0 for lvl in LEVEL_HIERARCHY}
            all_events = []
            filtered_events = []
            cursor = None
            has_more = True
            total_fetched = 0

            # Paginate through all events
            while has_more:
                # Fetch next page
                logs_data = client.get_run_logs(full_run_id, limit=100, cursor=cursor)
                events = logs_data.get("events", [])

                # Update total fetched
                total_fetched += len(events)

                # Count all events by level
                for event in events:
                    event_level = event.get("level")
                    if not event_level:
                        event_type = event.get("__typename")
                        event_level = EVENT_TYPE_LEVELS.get(event_type)

                    if event_level and event_level in level_counts:
                        level_counts[event_level] += 1

                # Filter events if level specified
                if filter_level:
                    for event in events:
                        if should_include_event(event, filter_level):
                            filtered_events.append(event)
                            # Stop if we have enough filtered events
                            if len(filtered_events) >= limit:
                                has_more = False
                                break
                else:
                    all_events.extend(events)
                    # Stop if we have enough events (no filtering)
                    if len(all_events) >= limit:
                        has_more = False
                        break

                # Check for more pages
                if has_more:
                    has_more = logs_data.get("hasMore", False)
                    cursor = logs_data.get("cursor")

            # Use filtered events if filtering was applied, limit results
            events_to_return = (
                filtered_events[:limit] if filter_level else all_events[:limit]
            )

            # Check for errors in returned events
            has_errors = any(
                event.get("level") in ["ERROR", "CRITICAL"]
                or event.get("__typename")
                in ["ExecutionStepFailureEvent", "RunFailureEvent"]
                for event in events_to_return
            )

            result = {
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
                "has_more_filtered": len(filtered_events) > limit
                if filter_level
                else len(all_events) > limit,
                "has_errors": has_errors,
            }

            # Auto-fetch stderr if there are errors
            if has_errors and include_stderr_on_error:
                log_urls = client.get_compute_log_urls(full_run_id)
                stderr_url = log_urls.get("stderr_url")

                if stderr_url:
                    try:
                        response = requests.get(stderr_url)
                        response.raise_for_status()
                        stderr_content = response.text.strip()
                        result["stderr"] = stderr_content
                        result["stderr_available"] = True
                    except Exception as e:
                        result["stderr_error"] = str(e)
                        result["stderr_available"] = False
                else:
                    result["stderr_available"] = False
                    result["stderr_note"] = (
                        "stderr logs not available (may require Dagster+)"
                    )

            return result
        except DagsterCLIError as e:
            return {"status": "error", "error_type": type(e).__name__, "error": str(e)}
        except Exception as e:
            return {"status": "error", "error_type": "UnknownError", "error": str(e)}

    # Tool: Get compute logs
    @mcp.tool()
    async def get_compute_logs(
        run_id: str, log_type: str = "stderr", deployment: Optional[str] = None
    ) -> dict:
        """Get stdout/stderr logs for a run (Dagster+ only).

        Args:
            run_id: Run ID to check (can be partial)
            log_type: Type of log to fetch - 'stdout' or 'stderr' (default: 'stderr')
            deployment: Optional deployment name (defaults to prod)

        Returns:
            Log content or error if not available
        """
        import requests

        try:
            # Validate log_type
            if log_type not in ["stdout", "stderr"]:
                return {
                    "status": "error",
                    "error_type": "InvalidArgument",
                    "error": "log_type must be 'stdout' or 'stderr'",
                }

            client = DagsterClient(profile_name, deployment)
            # Resolve partial run ID if needed
            full_run_id, error_msg, matching_runs = resolve_run_id(client, run_id)

            if error_msg:
                if matching_runs:
                    return {
                        "status": "error",
                        "error_type": "Ambiguous",
                        "error": error_msg,
                        "matches": [
                            {"id": r["id"], "job": r["pipeline"]["name"]}
                            for r in matching_runs
                        ],
                    }
                else:
                    return {
                        "status": "error",
                        "error_type": "NotFound",
                        "error": error_msg,
                    }

            # Get compute log URLs
            log_urls = client.get_compute_log_urls(full_run_id)
            url = log_urls.get(f"{log_type}_url")

            if not url:
                return {
                    "status": "error",
                    "error_type": "NotAvailable",
                    "error": f"No {log_type} logs available for this run",
                    "note": "Compute logs may only be available for Dagster+ deployments",
                }

            # Download log content
            response = requests.get(url)
            response.raise_for_status()
            log_content = response.text

            return {
                "status": "success",
                "run_id": full_run_id,
                "log_type": log_type,
                "content": log_content,
                "size": len(log_content),
            }
        except requests.RequestException as e:
            return {
                "status": "error",
                "error_type": "DownloadError",
                "error": f"Failed to download {log_type}: {str(e)}",
            }
        except DagsterCLIError as e:
            return {"status": "error", "error_type": type(e).__name__, "error": str(e)}
        except Exception as e:
            return {"status": "error", "error_type": "UnknownError", "error": str(e)}

    return mcp
