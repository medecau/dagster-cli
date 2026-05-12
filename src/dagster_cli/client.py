"""GraphQL client wrapper for Dagster+ API."""

import json
import os
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlparse

from dagster_graphql import DagsterGraphQLClient, DagsterGraphQLClientError
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

from dagster_cli.config import Config
from dagster_cli.constants import DEFAULT_TIMEOUT
from dagster_cli.utils.errors import (
    APIError,
    AuthenticationError,
    ConfigError,
    NotFoundError,
)
from dagster_cli.utils.format import format_asset_key

_LAUNCH_RUN_MUTATION = gql("""
    mutation LaunchRun($executionParams: ExecutionParams!) {
        launchPipelineExecution(executionParams: $executionParams) {
            __typename
            ... on LaunchRunSuccess {
                run { runId }
            }
            ... on PipelineConfigValidationInvalid {
                errors { message }
            }
            ... on PipelineNotFoundError { message }
            ... on InvalidStepError { invalidStepKey }
            ... on InvalidOutputError { stepKey invalidOutputName }
            ... on ConflictingExecutionParamsError { message }
            ... on PresetNotFoundError { message }
            ... on PythonError { message }
            ... on UnauthorizedError { message }
        }
    }
""")

# Inline-fragment block shared by get_run_logs — avoids 14 near-identical fragments
_EVENT_INLINE_FIELDS = """
    __typename
    ... on MessageEvent { timestamp message level stepKey }
    ... on LogMessageEvent { timestamp message level stepKey }
    ... on EngineEvent { timestamp message level stepKey }
    ... on ExecutionStepSuccessEvent { timestamp message level stepKey }
    ... on ExecutionStepFailureEvent {
        timestamp message level stepKey
        error { message stack }
    }
    ... on RunSuccessEvent { timestamp message level }
    ... on RunFailureEvent {
        timestamp message level
        error { message stack }
    }
    ... on RunStartEvent { timestamp message level }
    ... on MaterializationEvent {
        timestamp message level stepKey
        assetKey { path }
    }
    ... on AssetMaterializationPlannedEvent {
        timestamp message level stepKey
        assetKey { path }
    }
    ... on HandledOutputEvent { timestamp message level stepKey outputName }
    ... on AlertStartEvent { timestamp message level }
    ... on AlertSuccessEvent { timestamp message level }
    ... on AlertFailureEvent { timestamp message level }
"""


def _iter_repositories(result: dict) -> Iterator[tuple[dict, str]]:
    """Yield (repo_dict, location_name) for every repositoriesOrError node."""
    for repo in result.get("repositoriesOrError", {}).get("nodes", []):
        yield repo, repo.get("location", {}).get("name", "")


def _parse_tick_summary(state: dict) -> dict:
    """Extract last-tick metadata from a scheduleState or sensorState dict."""
    ticks = state.get("ticks", [])
    if not ticks:
        return {
            "last_tick": None,
            "tick_status": None,
            "tick_run_count": 0,
            "last_run_status": None,
            "last_run_timestamp": None,
        }
    tick = ticks[0]
    runs = tick.get("runs", [])
    run_ids = tick.get("runIds", [])
    tick_status = tick.get("status", "SKIPPED")

    if runs:
        last_run_status = runs[0].get("status", "UNKNOWN")
        last_run_timestamp = runs[0].get("startTime")
    elif run_ids:
        last_run_status = "UNKNOWN"
        last_run_timestamp = None
    elif tick_status == "SKIPPED":
        last_run_status = "SKIPPED"
        last_run_timestamp = None
    else:
        last_run_status = None
        last_run_timestamp = None

    return {
        "last_tick": tick.get("timestamp"),
        "tick_status": tick_status,
        "tick_run_count": len(run_ids),
        "last_run_status": last_run_status,
        "last_run_timestamp": last_run_timestamp,
    }


def _build_automation_detail(
    item: dict,
    auto_type: str,
    location_name: str,
    repo_name: str,
) -> dict:
    """Build an automation detail dict from a schedule or sensor GraphQL node."""
    if auto_type == "Schedule":
        state = item.get("scheduleState", {})
        return {
            "name": item["name"],
            "type": "Schedule",
            "target": item.get("pipelineName", ""),
            "description": item.get("description", ""),
            "cron_schedule": item.get("cronSchedule", ""),
            "execution_timezone": item.get("executionTimezone", ""),
            "status": state.get("status", "STOPPED"),
            "recent_ticks": state.get("ticks", []),
            "location": location_name,
            "repository": repo_name,
        }
    targets = item.get("targets", [])
    state = item.get("sensorState", {})
    return {
        "name": item["name"],
        "type": "Sensor",
        "target": targets[0].get("pipelineName", "") if targets else "",
        "description": item.get("description", ""),
        "min_interval_seconds": item.get("minIntervalSeconds"),
        "status": state.get("status", "STOPPED"),
        "recent_ticks": state.get("ticks", []),
        "location": location_name,
        "repository": repo_name,
    }


def _split_url_for_dagster_client(url: str) -> tuple[str, bool]:
    """Split a Dagster URL into the (hostname, use_https) pair expected by
    ``DagsterGraphQLClient``.

    ``DagsterGraphQLClient.__init__`` accepts ``hostname`` (e.g.
    ``YOUR_ORG.dagster.cloud``) plus a ``use_https`` flag, and internally
    appends ``/graphql``. Passing a full URL such as
    ``https://YOUR_ORG.dagster.cloud/prod`` as ``hostname`` produces the broken
    request URL ``http://https://YOUR_ORG.dagster.cloud/prod/graphql``.

    This helper accepts either a full URL or a bare hostname (with optional
    deployment path) and returns the form ``DagsterGraphQLClient`` actually
    needs.
    """
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host_with_path = (parsed.netloc + parsed.path).rstrip("/")
    # treat missing scheme (bare hostname) the same as explicit https
    use_https = parsed.scheme in ("https", "")
    return host_with_path, use_https


class DagsterClient:
    """Wrapper for Dagster GraphQL client with authentication handling."""

    def __init__(
        self,
        profile_name: str | None = None,
        deployment: str | None = None,
    ):
        self.config = Config()
        self.profile_name = profile_name
        self.profile = self.config.get_profile(profile_name)
        self.deployment = deployment or "prod"

        # DGC_URL / DGC_TOKEN override profile config for one-shot/CI use
        if env_url := os.environ.get("DGC_URL"):
            self.profile = dict(self.profile)
            self.profile["url"] = env_url
        if env_token := os.environ.get("DGC_TOKEN"):
            self.profile = dict(self.profile)
            self.profile["token"] = env_token

        if not self.profile.get("url") or not self.profile.get("token"):
            raise AuthenticationError(
                "No authentication found. "
                "Run 'dgc auth login' or set DGC_URL and DGC_TOKEN.",
            )

        self._dagster_client: DagsterGraphQLClient | None = None
        self._gql_client: Client | None = None
        self._resolved_deployment: str | None = None

    @property
    def dagster_client(self) -> DagsterGraphQLClient:
        """Get or create Dagster GraphQL client."""
        if self._dagster_client is None:
            try:
                url = self._get_deployment_url()
                hostname, use_https = _split_url_for_dagster_client(url)
                self._dagster_client = DagsterGraphQLClient(
                    hostname,
                    use_https=use_https,
                    headers={"Dagster-Cloud-Api-Token": self.profile["token"]},
                )
            except Exception as e:
                raise APIError(f"Failed to create Dagster client: {e}") from e
        return self._dagster_client

    def _resolve_deployment_name(self) -> str:
        """Resolve deployment name from branch name if needed."""
        if self._resolved_deployment:
            return self._resolved_deployment

        # Common deployment names that don't need resolution
        if self.deployment in ["prod", "staging"] or (
            len(self.deployment) == 40 and self.deployment.isalnum()
        ):
            self._resolved_deployment = self.deployment
            return self._resolved_deployment

        # Try to resolve branch name to deployment name
        try:
            # Use prod URL to list deployments
            url = self.profile["url"]
            if not url.startswith("http"):
                url = f"https://{url}"
            graphql_url = f"{url}/graphql"

            transport = RequestsHTTPTransport(
                url=graphql_url,
                headers={"Dagster-Cloud-Api-Token": self.profile["token"]},
                use_json=True,
                timeout=DEFAULT_TIMEOUT,
            )

            temp_client = Client(transport=transport, fetch_schema_from_transport=True)

            query = gql("""
                query {
                    deployments {
                        deploymentName
                        branchDeploymentGitMetadata {
                            branchName
                        }
                    }
                }
            """)

            result = temp_client.execute(query)
            deployments = result.get("deployments", [])

            # Look for exact branch name match
            for dep in deployments:
                if dep.get("branchDeploymentGitMetadata"):
                    branch_name = dep["branchDeploymentGitMetadata"].get("branchName")
                    if branch_name == self.deployment:
                        self._resolved_deployment = dep["deploymentName"]
                        return self._resolved_deployment

            # If no match found, return as-is (will likely fail but with clear error)
            self._resolved_deployment = self.deployment
            return self._resolved_deployment

        except Exception:
            # If we can't list deployments, just use the name as-is
            self._resolved_deployment = self.deployment
            return self._resolved_deployment

    def _get_deployment_url(self) -> str:
        """Get the URL with deployment applied."""
        url = self.profile["url"]
        resolved_deployment = self._resolve_deployment_name()
        if resolved_deployment and resolved_deployment != "prod":
            # Replace /prod with the specified deployment
            url = url.replace("/prod", f"/{resolved_deployment}")
        return url

    @property
    def gql_client(self) -> Client:
        """Get or create GQL client for custom queries."""
        if self._gql_client is None:
            url = self._get_deployment_url()
            if not url.startswith("http"):
                url = f"https://{url}"
            graphql_url = f"{url}/graphql"

            transport = RequestsHTTPTransport(
                url=graphql_url,
                headers={"Dagster-Cloud-Api-Token": self.profile["token"]},
                use_json=True,
                timeout=DEFAULT_TIMEOUT,
            )

            try:
                self._gql_client = Client(
                    transport=transport,
                    fetch_schema_from_transport=True,
                )
            except Exception as e:
                raise APIError(f"Failed to create GraphQL client: {e}") from e
        return self._gql_client

    def _execute(self, query: Any, variables: dict | None = None) -> dict:
        """Execute a GQL query. Only transport failures are wrapped as APIError;
        parser errors (KeyError, TypeError, etc.) propagate naturally."""
        try:
            return self.gql_client.execute(query, variable_values=variables)
        except APIError:
            raise
        except Exception as e:
            raise APIError(str(e)) from e

    def get_deployment_info(self) -> dict[str, Any]:
        """Get basic information about the Dagster deployment."""
        query = gql("""
            query DeploymentInfo {
                version
                repositoriesOrError {
                    ... on RepositoryConnection {
                        nodes {
                            name
                            location {
                                name
                            }
                            pipelines {
                                name
                            }
                        }
                    }
                }
            }
        """)
        return self._execute(query)

    def list_jobs(
        self,
        repository_location: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all available jobs in the deployment."""
        query = gql("""
            query ListJobs {
                repositoriesOrError {
                    ... on RepositoryConnection {
                        nodes {
                            name
                            location {
                                name
                            }
                            pipelines {
                                name
                                description
                                isJob
                            }
                        }
                    }
                }
            }
        """)

        result = self._execute(query)
        jobs = []
        for repo, location_name in _iter_repositories(result):
            if repository_location and location_name != repository_location:
                continue
            jobs.extend(
                {
                    "name": pipeline["name"],
                    "description": pipeline.get("description", ""),
                    "location": location_name,
                    "repository": repo["name"],
                }
                for pipeline in repo.get("pipelines", [])
                if pipeline.get("isJob", True)
            )
        return jobs

    def get_run_status(self, run_id: str) -> dict[str, Any] | None:
        """Get the status of a specific run."""
        query = gql("""
            query GetRunStatus($runId: ID!) {
                pipelineRunOrError(runId: $runId) {
                    ... on Run {
                        id
                        status
                        pipeline {
                            name
                        }
                        startTime
                        endTime
                        stats {
                            ... on RunStatsSnapshot {
                                stepsFailed
                                stepsSucceeded
                                expectations
                                materializations
                            }
                        }
                    }
                }
            }
        """)

        result = self._execute(query, {"runId": run_id})
        run_data = result.get("pipelineRunOrError", {})
        return run_data if "status" in run_data else None

    def submit_job_run(
        self,
        job_name: str,
        run_config: dict | None = None,
        repository_location_name: str | None = None,
        repository_name: str | None = None,
    ) -> str:
        """Submit a job for execution."""
        if not repository_location_name:
            repository_location_name = self.profile.get("location")
        if not repository_name:
            repository_name = self.profile.get("repository")

        execution_params = {
            "selector": {
                "repositoryLocationName": repository_location_name,
                "repositoryName": repository_name,
                "pipelineName": job_name,
            },
            "mode": "default",
            "runConfigData": json.dumps(run_config) if run_config else "{}",
            "executionMetadata": {"tags": []},
        }
        result = self._execute(
            _LAUNCH_RUN_MUTATION, {"executionParams": execution_params}
        )
        payload = result.get("launchPipelineExecution", {})
        typename = payload.get("__typename")
        if typename in ("LaunchRunSuccess", "LaunchPipelineRunSuccess"):
            return payload["run"]["runId"]
        errors = payload.get("errors") or payload.get("message", payload)
        raise APIError(f"Failed to submit job '{job_name}' ({typename}): {errors}")

    def get_recent_runs(
        self,
        limit: int = 10,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get recent run history."""
        query = gql("""
            query GetRecentRuns($limit: Int!) {
                pipelineRunsOrError(limit: $limit) {
                    ... on Runs {
                        results {
                            id
                            status
                            pipeline {
                                name
                            }
                            startTime
                            endTime
                            mode
                            stats {
                                ... on RunStatsSnapshot {
                                    stepsFailed
                                    stepsSucceeded
                                }
                            }
                        }
                    }
                }
            }
        """)

        result = self._execute(query, {"limit": limit})
        runs = result.get("pipelineRunsOrError", {}).get("results", [])
        if status:
            runs = [r for r in runs if r.get("status") == status.upper()]
        return runs

    def reload_repository_location(self, location_name: str) -> None:
        """Reload a repository location. Raises APIError on failure."""
        try:
            self.dagster_client.reload_repository_location(location_name)
        except DagsterGraphQLClientError as e:
            raise APIError(f"Failed to reload repository location: {e}") from e

    def run_url(self, run_id: str) -> str | None:
        """Construct the Dagster+ URL for a run, or None if no URL is configured."""
        base_url = self.profile.get("url", "")
        if not base_url:
            return None
        url = base_url
        if self.deployment and self.deployment != "prod":
            url = url.replace("/prod", f"/{self.deployment}")
        if not url.startswith("http"):
            url = f"https://{url}"
        return f"{url}/runs/{run_id}"

    def cancel_run(self, run_id: str) -> None:
        """Cancel (terminate) a running run. Raises APIError on failure."""
        mutation = gql("""
            mutation TerminateRun($runId: String!) {
                terminateRun(runId: $runId) {
                    __typename
                    ... on TerminateRunSuccess {
                        run { runId }
                    }
                    ... on TerminateRunFailure { message }
                    ... on RunNotFoundError { message }
                    ... on PythonError { message }
                    ... on UnauthorizedError { message }
                }
            }
        """)
        result = self._execute(mutation, {"runId": run_id})
        payload = result.get("terminateRun", {})
        typename = payload.get("__typename")
        if typename == "TerminateRunSuccess":
            return
        if typename == "RunNotFoundError":
            raise NotFoundError(
                f"Run '{run_id}' not found: {payload.get('message', '')}"
            )
        raise APIError(
            f"Failed to cancel run ({typename}): {payload.get('message', payload)}"
        )

    def list_assets(
        self,
        prefix: str | None = None,
        group: str | None = None,
        location: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all assets in the deployment."""
        query = gql("""
            query ListAssets {
                repositoriesOrError {
                    ... on RepositoryConnection {
                        nodes {
                            name
                            location {
                                name
                            }
                            assetNodes {
                                id
                                assetKey {
                                    path
                                }
                                groupName
                                description
                                computeKind
                            }
                        }
                    }
                }
            }
        """)

        result = self._execute(query)
        assets = []
        for repo, location_name in _iter_repositories(result):
            if location and location_name != location:
                continue
            for asset_node in repo.get("assetNodes", []):
                asset_key_str = format_asset_key(
                    asset_node.get("assetKey", {}).get("path", [])
                )
                if prefix and not asset_key_str.startswith(prefix):
                    continue
                if group and asset_node.get("groupName") != group:
                    continue
                assets.append(
                    {
                        "id": asset_node.get("id"),
                        "key": asset_node.get("assetKey"),
                        "groupName": asset_node.get("groupName"),
                        "description": asset_node.get("description"),
                        "computeKind": asset_node.get("computeKind"),
                        "location": location_name,
                        "repository": repo["name"],
                    }
                )
        return assets

    def get_asset_details(self, asset_key: str) -> dict[str, Any] | None:
        """Get detailed information about a specific asset."""
        key_parts = asset_key.split("/")

        query = gql("""
            query GetAsset($assetKey: AssetKeyInput!) {
                assetNodeOrError(assetKey: $assetKey) {
                    __typename
                    ... on AssetNode {
                        id
                        assetKey {
                            path
                        }
                        description
                        groupName
                        computeKind
                        dependencies {
                            asset {
                                assetKey {
                                    path
                                }
                                assetMaterializations(limit: 1) {
                                    runOrError {
                                        __typename
                                        ... on Run {
                                            status
                                        }
                                    }
                                }
                            }
                        }
                        dependedBy {
                            asset {
                                assetKey {
                                    path
                                }
                                assetMaterializations(limit: 1) {
                                    runOrError {
                                        __typename
                                        ... on Run {
                                            status
                                        }
                                    }
                                }
                            }
                        }
                        assetMaterializations(limit: 1) {
                            runId
                            timestamp
                            runOrError {
                                __typename
                                ... on Run {
                                    id
                                    status
                                }
                            }
                        }
                    }
                    ... on AssetNotFoundError {
                        message
                    }
                }
            }
        """)

        result = self._execute(query, {"assetKey": {"path": key_parts}})
        asset_data = result.get("assetNodeOrError", {})
        return asset_data if asset_data.get("__typename") == "AssetNode" else None

    def materialize_asset(
        self,
        asset_key: str,
        partition_key: str | None = None,
    ) -> str:
        """Trigger materialization of an asset."""
        if not self.profile.get("location") or not self.profile.get("repository"):
            raise ConfigError(
                "Asset materialization requires 'location' and 'repository' in the "
                "profile. Run 'dgc auth login' to update your profile."
            )

        asset_key_path = asset_key.split("/")
        tags = (
            [{"key": "dagster/partition", "value": partition_key}]
            if partition_key
            else []
        )
        execution_params = {
            "selector": {
                "repositoryLocationName": self.profile.get("location"),
                "repositoryName": self.profile.get("repository"),
                "pipelineName": "__ASSET_JOB",
                "assetSelection": [{"path": asset_key_path}],
            },
            "mode": "default",
            "runConfigData": "{}",
            "executionMetadata": {"tags": tags},
        }
        result = self._execute(
            _LAUNCH_RUN_MUTATION,
            {"executionParams": execution_params},
        )
        payload = result.get("launchPipelineExecution", {})
        typename = payload.get("__typename")
        if typename == "LaunchRunSuccess":
            return payload["run"]["runId"]
        raise APIError(f"Failed to materialize asset ({typename}): {payload}")

    def get_asset_health(self, group: str | None = None) -> list[dict[str, Any]]:
        """Get assets with their latest materialization status for health checks."""
        query = gql("""
            query GetAssetHealth {
                repositoriesOrError {
                    ... on RepositoryConnection {
                        nodes {
                            name
                            location {
                                name
                            }
                            assetNodes {
                                id
                                assetKey {
                                    path
                                }
                                groupName
                                description
                                computeKind
                                assetMaterializations(limit: 1) {
                                    runId
                                    timestamp
                                    stepKey
                                    runOrError {
                                        __typename
                                        ... on Run {
                                            id
                                            status
                                            stepStats {
                                                stepKey
                                                status
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        """)

        result = self._execute(query)
        assets = []
        for repo, location_name in _iter_repositories(result):
            assets.extend(
                {
                    "id": asset_node.get("id"),
                    "key": asset_node.get("assetKey"),
                    "groupName": asset_node.get("groupName"),
                    "description": asset_node.get("description"),
                    "computeKind": asset_node.get("computeKind"),
                    "location": location_name,
                    "repository": repo["name"],
                    "assetMaterializations": asset_node.get(
                        "assetMaterializations", []
                    ),
                }
                for asset_node in repo.get("assetNodes", [])
                if not group or asset_node.get("groupName") == group
            )
        return assets

    def get_run_logs(
        self,
        run_id: str,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Get event logs for a run."""
        query = gql(f"""
            query GetLogsForRun($runId: ID!, $afterCursor: String, $limit: Int) {{
                logsForRun(
                    runId: $runId, afterCursor: $afterCursor, limit: $limit
                ) {{
                    ... on EventConnection {{
                        events {{
                            {_EVENT_INLINE_FIELDS}
                        }}
                        cursor
                        hasMore
                    }}
                    ... on RunNotFoundError {{
                        message
                    }}
                    ... on PythonError {{
                        message
                        stack
                    }}
                }}
            }}
        """)

        variables: dict[str, Any] = {"runId": run_id, "limit": limit}
        if cursor:
            variables["afterCursor"] = cursor

        result = self._execute(query, variables)
        logs_data = result.get("logsForRun", {})

        if "events" in logs_data:
            return {
                "events": logs_data["events"],
                "cursor": logs_data.get("cursor"),
                "hasMore": logs_data.get("hasMore", False),
            }
        if logs_data.get("__typename") == "RunNotFoundError":
            raise APIError(f"Run not found: {logs_data.get('message', run_id)}")
        raise APIError(f"Failed to get logs: {logs_data}")

    def get_compute_log_urls(
        self,
        run_id: str,
        step_key: str | None = None,
    ) -> dict[str, str | None]:
        """Get S3 URLs for stdout/stderr logs."""
        query = gql("""
            query CapturedLogsMetadata($runId: ID!, $stepKey: String) {
                capturedLogsMetadata(runId: $runId, stepKey: $stepKey) {
                    stdoutDownloadUrl
                    stderrDownloadUrl
                }
            }
        """)

        variables: dict[str, Any] = {"runId": run_id}
        if step_key:
            variables["stepKey"] = step_key

        try:
            result = self._execute(query, variables)
        except APIError as e:
            # Transport or auth failure — surface the error so callers can distinguish
            # "feature not available" (None URLs) from "call failed" (error key).
            return {"stdout_url": None, "stderr_url": None, "error": str(e)}

        metadata = result.get("capturedLogsMetadata")
        if metadata is None:
            return {
                "stdout_url": None,
                "stderr_url": None,
                "note": "capturedLogsMetadata not available (requires Dagster+)",
            }
        return {
            "stdout_url": metadata.get("stdoutDownloadUrl"),
            "stderr_url": metadata.get("stderrDownloadUrl"),
        }

    def list_deployments(self) -> list[dict[str, Any]]:
        """List all available deployments in Dagster+."""
        query = gql("""
            query {
                deployments {
                    deploymentId
                    deploymentName
                    deploymentStatus
                    deploymentType
                    isBranchDeployment
                    branchDeploymentGitMetadata {
                        branchName
                        repoName
                        branchUrl
                        pullRequestUrl
                        pullRequestStatus
                        pullRequestNumber
                    }
                }
            }
        """)
        result = self._execute(query)
        return result.get("deployments", [])

    def list_automations(self) -> list[dict[str, Any]]:
        """List all schedules and sensors."""
        query = gql("""
            query ListAutomations {
                repositoriesOrError {
                    ... on RepositoryConnection {
                        nodes {
                            name
                            location {
                                name
                            }
                            schedules {
                                name
                                cronSchedule
                                pipelineName
                                description
                                scheduleState {
                                    status
                                    ticks(limit: 1) {
                                        timestamp
                                        runIds
                                        status
                                        runs {
                                            id
                                            status
                                            startTime
                                        }
                                    }
                                }
                            }
                            sensors {
                                name
                                targets {
                                    pipelineName
                                }
                                description
                                sensorState {
                                    status
                                    ticks(limit: 1) {
                                        timestamp
                                        runIds
                                        status
                                        runs {
                                            id
                                            status
                                            startTime
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        """)

        result = self._execute(query)
        automations = []

        for repo, location_name in _iter_repositories(result):
            repo_name = repo.get("name", "")

            for schedule in repo.get("schedules", []):
                tick_data = _parse_tick_summary(schedule.get("scheduleState", {}))
                automations.append(
                    {
                        "name": schedule["name"],
                        "type": "Schedule",
                        "target": schedule.get("pipelineName", ""),
                        "description": schedule.get("description", ""),
                        "status": schedule.get("scheduleState", {}).get(
                            "status", "STOPPED"
                        ),
                        "cron_schedule": schedule.get("cronSchedule", ""),
                        "location": location_name,
                        "repository": repo_name,
                        **tick_data,
                    }
                )

            for sensor in repo.get("sensors", []):
                tick_data = _parse_tick_summary(sensor.get("sensorState", {}))
                targets = sensor.get("targets", [])
                target = targets[0].get("pipelineName", "") if targets else ""
                automations.append(
                    {
                        "name": sensor["name"],
                        "type": "Sensor",
                        "target": target,
                        "description": sensor.get("description", ""),
                        "status": sensor.get("sensorState", {}).get(
                            "status", "STOPPED"
                        ),
                        "cron_schedule": None,
                        "location": location_name,
                        "repository": repo_name,
                        **tick_data,
                    }
                )

        return sorted(automations, key=lambda x: x["name"])

    def get_automation_details(self, name: str) -> dict[str, Any] | None:
        """Get detailed information about a specific automation (schedule or sensor)."""
        query = gql("""
            query GetAutomationDetails {
                repositoriesOrError {
                    ... on RepositoryConnection {
                        nodes {
                            name
                            location { name }
                            schedules {
                                name
                                cronSchedule
                                pipelineName
                                description
                                executionTimezone
                                scheduleState {
                                    status
                                    ticks(limit: 10) {
                                        timestamp runIds status
                                        error { message }
                                        runs { id status startTime endTime }
                                    }
                                }
                            }
                            sensors {
                                name
                                targets { pipelineName }
                                description
                                minIntervalSeconds
                                sensorState {
                                    status
                                    ticks(limit: 10) {
                                        timestamp runIds status
                                        error { message }
                                        runs { id status startTime endTime }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        """)

        result = self._execute(query)
        for repo, location_name in _iter_repositories(result):
            repo_name = repo.get("name", "")
            for schedule in repo.get("schedules", []):
                if schedule["name"] == name:
                    return _build_automation_detail(
                        schedule, "Schedule", location_name, repo_name
                    )
            for sensor in repo.get("sensors", []):
                if sensor["name"] == name:
                    return _build_automation_detail(
                        sensor, "Sensor", location_name, repo_name
                    )
        return None

    def get_automation_runs(self, name: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get runs triggered by an automation."""
        automation = self.get_automation_details(name)
        if not automation:
            raise APIError(f"Automation '{name}' not found")

        all_runs: list[dict] = []
        for tick in automation.get("recent_ticks", []):
            if tick_runs := tick.get("runs", []):
                all_runs.extend(
                    {
                        "id": run["id"],
                        "status": run["status"],
                        "startTime": run.get("startTime"),
                        "endTime": run.get("endTime"),
                        "pipeline": {"name": automation["target"]},
                    }
                    for run in tick_runs
                )
            elif tick.get("runIds"):
                for run_id in tick.get("runIds", []):
                    if run := self.get_run_status(run_id):
                        all_runs.append(run)  # noqa: PERF401

        return all_runs[:limit]

    def get_automation_ticks(self, name: str, limit: int = 20) -> list[dict[str, Any]]:
        """Get tick history for an automation."""
        automation = self.get_automation_details(name)
        if not automation:
            raise APIError(f"Automation '{name}' not found")
        return [
            {
                "timestamp": tick.get("timestamp"),
                "status": tick.get("status", "SKIPPED"),
                "run_count": len(tick.get("runIds", [])),
                "run_ids": tick.get("runIds", []),
                "error": (
                    tick.get("error", {}).get("message") if tick.get("error") else None
                ),
            }
            for tick in automation.get("recent_ticks", [])[:limit]
        ]
