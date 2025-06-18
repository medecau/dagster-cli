"""MCP server implementation for Dagster CLI."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from dagster_cli.client import DagsterClient
from dagster_cli.utils.errors import DagsterCLIError


def create_mcp_server(client: DagsterClient) -> FastMCP:
    """Create MCP server with Dagster+ tools and resources."""
    mcp = FastMCP("dagster-cli")

    # Tool: List jobs
    @mcp.tool()
    async def list_jobs(location: Optional[str] = None) -> dict:
        """List available Dagster jobs.

        Args:
            location: Optional filter by repository location

        Returns:
            List of jobs with their details
        """
        try:
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
    ) -> dict:
        """Submit a job for execution.

        Args:
            job_name: Name of the job to run
            config: Optional run configuration
            location: Optional repository location (overrides profile default)
            repository: Optional repository name (overrides profile default)

        Returns:
            Run ID and URL for the submitted job
        """
        try:
            run_id = client.submit_job_run(
                job_name=job_name,
                run_config=config,
                repository_location_name=location,
                repository_name=repository,
            )

            # Construct URL if possible
            url = client.profile.get("url", "")
            if url:
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
    async def get_run_status(run_id: str) -> dict:
        """Get the status of a specific run.

        Args:
            run_id: Run ID to check (can be partial)

        Returns:
            Run details including status, timing, and stats
        """
        try:
            # Handle partial run IDs
            full_run_id = run_id
            if len(run_id) < 20:
                recent_runs = client.get_recent_runs(limit=50)
                matching = [r for r in recent_runs if r["id"].startswith(run_id)]

                if not matching:
                    return {
                        "status": "error",
                        "error_type": "NotFound",
                        "error": f"No runs found matching '{run_id}'",
                    }
                elif len(matching) > 1:
                    return {
                        "status": "error",
                        "error_type": "Ambiguous",
                        "error": f"Multiple runs found matching '{run_id}'",
                        "matches": [
                            {"id": r["id"], "job": r["pipeline"]["name"]}
                            for r in matching[:5]
                        ],
                    }
                else:
                    full_run_id = matching[0]["id"]

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
    async def list_runs(limit: int = 10, status: Optional[str] = None) -> dict:
        """Get recent run history.

        Args:
            limit: Number of runs to return (default: 10)
            status: Optional filter by status (SUCCESS, FAILURE, STARTED, etc.)

        Returns:
            List of recent runs with their details
        """
        try:
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
    ) -> dict:
        """List all assets in the deployment.

        Args:
            prefix: Filter assets by prefix
            group: Filter by asset group
            location: Filter by repository location

        Returns:
            List of assets with their details
        """
        try:
            assets = client.list_assets(prefix=prefix, group=group, location=location)
            return {"status": "success", "count": len(assets), "assets": assets}
        except DagsterCLIError as e:
            return {"status": "error", "error_type": type(e).__name__, "error": str(e)}
        except Exception as e:
            return {"status": "error", "error_type": "UnknownError", "error": str(e)}

    # Tool: Materialize asset
    @mcp.tool()
    async def materialize_asset(
        asset_key: str, partition_key: Optional[str] = None
    ) -> dict:
        """Trigger materialization of an asset.

        Args:
            asset_key: Asset key to materialize (e.g., 'my_asset' or 'prefix/my_asset')
            partition_key: Optional partition to materialize

        Returns:
            Run ID for the materialization
        """
        try:
            run_id = client.materialize_asset(
                asset_key=asset_key, partition_key=partition_key
            )

            # Construct URL if possible
            url = client.profile.get("url", "")
            if url:
                if not url.startswith("http"):
                    url = f"https://{url}"
                run_url = f"{url}/runs/{run_id}"
            else:
                run_url = None

            return {
                "status": "success",
                "run_id": run_id,
                "url": run_url,
                "message": f"Asset '{asset_key}' materialization submitted",
            }
        except DagsterCLIError as e:
            return {"status": "error", "error_type": type(e).__name__, "error": str(e)}
        except Exception as e:
            return {"status": "error", "error_type": "UnknownError", "error": str(e)}

    # Tool: Reload repository
    @mcp.tool()
    async def reload_repository(location_name: str) -> dict:
        """Reload a repository location.

        Args:
            location_name: Name of the repository location to reload

        Returns:
            Success status
        """
        try:
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

    return mcp


def create_mcp_app(client: DagsterClient):
    """Create FastAPI app with MCP server for HTTP transport."""
    from fastapi import FastAPI

    # Create MCP server
    mcp_server = create_mcp_server(client)

    # Create FastAPI app
    app = FastAPI(title="Dagster CLI MCP Server")

    # Mount MCP endpoints
    app.include_router(mcp_server._get_router(), prefix="/mcp")

    @app.get("/")
    async def root():
        return {
            "name": "Dagster CLI MCP Server",
            "version": "0.1.0",
            "mcp_endpoint": "/mcp",
        }

    return app
