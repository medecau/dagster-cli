"""GraphQL client wrapper for Dagster+ API."""

from typing import Optional, Dict, List, Any
from datetime import datetime

from dagster_graphql import DagsterGraphQLClient, DagsterGraphQLClientError
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

from dagster_cli.config import Config
from dagster_cli.constants import DEFAULT_TIMEOUT, DATETIME_FORMAT
from dagster_cli.utils.errors import APIError, AuthenticationError


class DagsterClient:
    """Wrapper for Dagster GraphQL client with authentication handling."""

    def __init__(
        self, profile_name: Optional[str] = None, deployment: Optional[str] = None
    ):
        self.config = Config()
        self.profile_name = profile_name
        self.profile = self.config.get_profile(profile_name)
        self.deployment = deployment or "prod"

        if not self.profile.get("url") or not self.profile.get("token"):
            raise AuthenticationError(
                "No authentication found. Please run 'dgc auth login' first."
            )

        self._dagster_client: Optional[DagsterGraphQLClient] = None
        self._gql_client: Optional[Client] = None
        self._resolved_deployment: Optional[str] = None

    @property
    def dagster_client(self) -> DagsterGraphQLClient:
        """Get or create Dagster GraphQL client."""
        if self._dagster_client is None:
            try:
                url = self._get_deployment_url()
                self._dagster_client = DagsterGraphQLClient(
                    url,
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
            # Create a temporary client to list deployments
            from gql import Client, gql
            from gql.transport.requests import RequestsHTTPTransport

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
                    transport=transport, fetch_schema_from_transport=True
                )
            except Exception as e:
                raise APIError(f"Failed to create GraphQL client: {e}") from e
        return self._gql_client

    def get_deployment_info(self) -> Dict[str, Any]:
        """Get basic information about the Dagster deployment."""
        try:
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

            return self.gql_client.execute(query)
        except Exception as e:
            raise APIError(f"Failed to get deployment info: {e}") from e

    def list_jobs(
        self, repository_location: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all available jobs in the deployment."""
        try:
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

            result = self.gql_client.execute(query)
            jobs = []

            if "repositoriesOrError" in result:
                repositories = result["repositoriesOrError"].get("nodes", [])
                for repo in repositories:
                    location_name = repo.get("location", {}).get("name", "")

                    # Filter by location if specified
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
        except Exception as e:
            raise APIError(f"Failed to list jobs: {e}") from e

    def get_run_status(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a specific run."""
        try:
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

            result = self.gql_client.execute(query, variable_values={"runId": run_id})
            run_data = result.get("pipelineRunOrError", {})

            return run_data if "status" in run_data else None
        except Exception as e:
            raise APIError(f"Failed to get run status: {e}") from e

    def submit_job_run(
        self,
        job_name: str,
        run_config: Optional[Dict] = None,
        repository_location_name: Optional[str] = None,
        repository_name: Optional[str] = None,
    ) -> str:
        """Submit a job for execution."""
        try:
            # Use profile defaults if not provided
            if not repository_location_name:
                repository_location_name = self.profile.get("location")
            if not repository_name:
                repository_name = self.profile.get("repository")

            return self.dagster_client.submit_job_execution(
                job_name,
                repository_location_name=repository_location_name,
                repository_name=repository_name,
                run_config=run_config or {},
            )
        except DagsterGraphQLClientError as e:
            raise APIError(f"Failed to submit job: {e}") from e

    def get_recent_runs(
        self, limit: int = 10, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get recent run history."""
        try:
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

            result = self.gql_client.execute(query, variable_values={"limit": limit})
            runs_data = result.get("pipelineRunsOrError", {})

            if "results" in runs_data:
                runs = runs_data["results"]

                # Filter by status if specified
                if status:
                    runs = [r for r in runs if r.get("status") == status.upper()]

                return runs
            return []
        except Exception as e:
            raise APIError(f"Failed to get recent runs: {e}") from e

    def reload_repository_location(self, location_name: str) -> bool:
        """Reload a repository location."""
        try:
            self.dagster_client.reload_repository_location(location_name)
            return True
        except DagsterGraphQLClientError as e:
            raise APIError(f"Failed to reload repository location: {e}") from e

    def list_assets(
        self,
        prefix: Optional[str] = None,
        group: Optional[str] = None,
        location: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all assets in the deployment."""
        try:
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

            result = self.gql_client.execute(query)
            assets = []

            if "repositoriesOrError" in result:
                repositories = result["repositoriesOrError"].get("nodes", [])
                for repo in repositories:
                    location_name = repo.get("location", {}).get("name", "")

                    # Filter by location if specified
                    if location and location_name != location:
                        continue

                    for asset_node in repo.get("assetNodes", []):
                        asset_key = asset_node.get("assetKey", {}).get("path", [])
                        asset_key_str = (
                            "/".join(asset_key)
                            if isinstance(asset_key, list)
                            else str(asset_key)
                        )

                        # Filter by prefix if specified
                        if prefix and not asset_key_str.startswith(prefix):
                            continue

                        # Filter by group if specified
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
        except Exception as e:
            raise APIError(f"Failed to list assets: {e}") from e

    def get_asset_details(self, asset_key: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific asset."""
        try:
            # Convert string key to path array
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

            variables = {"assetKey": {"path": key_parts}}

            result = self.gql_client.execute(query, variable_values=variables)
            asset_data = result.get("assetNodeOrError", {})

            return asset_data if asset_data.get("__typename") == "AssetNode" else None
        except Exception as e:
            raise APIError(f"Failed to get asset details: {e}") from e

    def materialize_asset(
        self, asset_key: str, partition_key: Optional[str] = None
    ) -> str:
        """Trigger materialization of an asset."""
        try:
            # First, find which job can materialize this asset
            # For now, we'll use the __ASSET_JOB which is the default asset job
            job_name = "__ASSET_JOB"

            # Build run config for asset selection
            run_config = {"selection": [asset_key]}

            if partition_key:
                run_config["partitionKey"] = partition_key

            return self.dagster_client.submit_job_execution(
                job_name,
                repository_location_name=self.profile.get("location"),
                repository_name=self.profile.get("repository"),
                run_config=run_config,
            )
        except DagsterGraphQLClientError as e:
            raise APIError(f"Failed to materialize asset: {e}") from e

    def get_asset_health(self, group: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get assets with their latest materialization status for health checks."""
        try:
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

            result = self.gql_client.execute(query)
            assets = []

            if "repositoriesOrError" in result:
                repositories = result["repositoriesOrError"].get("nodes", [])
                for repo in repositories:
                    location_name = repo.get("location", {}).get("name", "")

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
        except Exception as e:
            raise APIError(f"Failed to get asset health: {e}") from e

    def get_run_logs(
        self, run_id: str, limit: int = 100, cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get event logs for a run."""
        try:
            query = gql("""
                query GetLogsForRun($runId: ID!, $afterCursor: String, $limit: Int) {
                    logsForRun(runId: $runId, afterCursor: $afterCursor, limit: $limit) {
                        ... on EventConnection {
                            events {
                                __typename
                                ... on MessageEvent {
                                    timestamp
                                    message
                                    level
                                    stepKey
                                }
                                ... on LogMessageEvent {
                                    timestamp
                                    message
                                    level
                                    stepKey
                                }
                                ... on EngineEvent {
                                    timestamp
                                    message
                                    level
                                    stepKey
                                }
                                ... on ExecutionStepSuccessEvent {
                                    timestamp
                                    message
                                    level
                                    stepKey
                                }
                                ... on ExecutionStepFailureEvent {
                                    timestamp
                                    message
                                    level
                                    stepKey
                                    error {
                                        message
                                        stack
                                    }
                                }
                                ... on RunSuccessEvent {
                                    timestamp
                                    message
                                    level
                                }
                                ... on RunFailureEvent {
                                    timestamp
                                    message
                                    level
                                    error {
                                        message
                                        stack
                                    }
                                }
                                ... on RunStartEvent {
                                    timestamp
                                    message
                                    level
                                }
                                ... on MaterializationEvent {
                                    timestamp
                                    message
                                    level
                                    stepKey
                                    assetKey {
                                        path
                                    }
                                }
                                ... on AssetMaterializationPlannedEvent {
                                    timestamp
                                    message
                                    level
                                    stepKey
                                    assetKey {
                                        path
                                    }
                                }
                                ... on HandledOutputEvent {
                                    timestamp
                                    message
                                    level
                                    stepKey
                                    outputName
                                }
                                ... on AlertStartEvent {
                                    timestamp
                                    message
                                    level
                                }
                                ... on AlertSuccessEvent {
                                    timestamp
                                    message
                                    level
                                }
                                ... on AlertFailureEvent {
                                    timestamp
                                    message
                                    level
                                }
                            }
                            cursor
                            hasMore
                        }
                        ... on RunNotFoundError {
                            message
                        }
                        ... on PythonError {
                            message
                            stack
                        }
                    }
                }
            """)

            variables = {
                "runId": run_id,
                "limit": limit,
            }
            if cursor:
                variables["afterCursor"] = cursor

            result = self.gql_client.execute(query, variable_values=variables)
            logs_data = result.get("logsForRun", {})

            if "events" in logs_data:
                return {
                    "events": logs_data["events"],
                    "cursor": logs_data.get("cursor"),
                    "hasMore": logs_data.get("hasMore", False),
                }
            elif logs_data.get("__typename") == "RunNotFoundError":
                raise APIError(f"Run not found: {logs_data.get('message', run_id)}")
            else:
                raise APIError(f"Failed to get logs: {logs_data}")

        except Exception as e:
            raise APIError(f"Failed to get run logs: {e}") from e

    def get_compute_log_urls(
        self, run_id: str, step_key: Optional[str] = None
    ) -> Dict[str, Optional[str]]:
        """Get S3 URLs for stdout/stderr logs."""
        try:
            # Query for compute log metadata
            query = gql("""
                query CapturedLogsMetadata($runId: ID!, $stepKey: String) {
                    capturedLogsMetadata(runId: $runId, stepKey: $stepKey) {
                        stdoutDownloadUrl
                        stderrDownloadUrl
                    }
                }
            """)

            variables = {"runId": run_id}
            if step_key:
                variables["stepKey"] = step_key

            result = self.gql_client.execute(query, variable_values=variables)
            metadata = result.get("capturedLogsMetadata", {})

            return {
                "stdout_url": metadata.get("stdoutDownloadUrl"),
                "stderr_url": metadata.get("stderrDownloadUrl"),
            }
        except Exception:
            # If the query is not available (e.g., not on Dagster+), return empty URLs
            return {"stdout_url": None, "stderr_url": None}

    def list_deployments(self) -> List[Dict[str, Any]]:
        """List all available deployments in Dagster+."""
        try:
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

            result = self.gql_client.execute(query)
            return result.get("deployments", [])
        except Exception as e:
            raise APIError(f"Failed to list deployments: {e}") from e

    @staticmethod
    def format_timestamp(timestamp: Optional[float]) -> str:
        """Format Unix timestamp to readable datetime."""
        if not timestamp:
            return "N/A"

        # Convert string to float if needed
        if isinstance(timestamp, str):
            try:
                timestamp = float(timestamp)
            except ValueError:
                return "N/A"

        # Check if timestamp is in seconds or milliseconds
        if timestamp < 10000000000:
            # Already in seconds
            return datetime.fromtimestamp(timestamp).strftime(DATETIME_FORMAT)
        else:
            # In milliseconds
            return datetime.fromtimestamp(timestamp / 1000).strftime(DATETIME_FORMAT)
