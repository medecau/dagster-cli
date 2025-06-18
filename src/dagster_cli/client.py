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

    def __init__(self, profile_name: Optional[str] = None):
        self.config = Config()
        self.profile_name = profile_name
        self.profile = self.config.get_profile(profile_name)

        if not self.profile.get("url") or not self.profile.get("token"):
            raise AuthenticationError(
                "No authentication found. Please run 'dgc auth login' first."
            )

        self._dagster_client: Optional[DagsterGraphQLClient] = None
        self._gql_client: Optional[Client] = None

    @property
    def dagster_client(self) -> DagsterGraphQLClient:
        """Get or create Dagster GraphQL client."""
        if self._dagster_client is None:
            try:
                self._dagster_client = DagsterGraphQLClient(
                    self.profile["url"],
                    headers={"Dagster-Cloud-Api-Token": self.profile["token"]},
                )
            except Exception as e:
                raise APIError(f"Failed to create Dagster client: {e}")
        return self._dagster_client

    @property
    def gql_client(self) -> Client:
        """Get or create GQL client for custom queries."""
        if self._gql_client is None:
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

            try:
                self._gql_client = Client(
                    transport=transport, fetch_schema_from_transport=True
                )
            except Exception as e:
                raise APIError(f"Failed to create GraphQL client: {e}")
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

            result = self.gql_client.execute(query)
            return result
        except Exception as e:
            raise APIError(f"Failed to get deployment info: {e}")

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

                    for pipeline in repo.get("pipelines", []):
                        if pipeline.get("isJob", True):
                            jobs.append(
                                {
                                    "name": pipeline["name"],
                                    "description": pipeline.get("description", ""),
                                    "location": location_name,
                                    "repository": repo["name"],
                                }
                            )

            return jobs
        except Exception as e:
            raise APIError(f"Failed to list jobs: {e}")

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

            if "status" in run_data:
                return run_data
            return None
        except Exception as e:
            raise APIError(f"Failed to get run status: {e}")

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

            run_id = self.dagster_client.submit_job_execution(
                job_name,
                repository_location_name=repository_location_name,
                repository_name=repository_name,
                run_config=run_config or {},
            )
            return run_id
        except DagsterGraphQLClientError as e:
            raise APIError(f"Failed to submit job: {e}")

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
            raise APIError(f"Failed to get recent runs: {e}")

    def reload_repository_location(self, location_name: str) -> bool:
        """Reload a repository location."""
        try:
            self.dagster_client.reload_repository_location(location_name)
            return True
        except DagsterGraphQLClientError as e:
            raise APIError(f"Failed to reload repository location: {e}")

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
            raise APIError(f"Failed to list assets: {e}")

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

            if asset_data.get("__typename") == "AssetNode":
                return asset_data

            return None
        except Exception as e:
            raise APIError(f"Failed to get asset details: {e}")

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

            # Submit the job
            run_id = self.dagster_client.submit_job_execution(
                job_name,
                repository_location_name=self.profile.get("location"),
                repository_name=self.profile.get("repository"),
                run_config=run_config,
            )

            return run_id
        except DagsterGraphQLClientError as e:
            raise APIError(f"Failed to materialize asset: {e}")

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
                                        runOrError {
                                            __typename
                                            ... on Run {
                                                id
                                                status
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

                    for asset_node in repo.get("assetNodes", []):
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
                                "assetMaterializations": asset_node.get(
                                    "assetMaterializations", []
                                ),
                            }
                        )

            return assets
        except Exception as e:
            raise APIError(f"Failed to get asset health: {e}")

    @staticmethod
    def format_timestamp(timestamp: Optional[float]) -> str:
        """Format Unix timestamp to readable datetime."""
        if not timestamp:
            return "N/A"

        # Check if timestamp is in seconds or milliseconds
        if timestamp < 10000000000:
            # Already in seconds
            return datetime.fromtimestamp(timestamp).strftime(DATETIME_FORMAT)
        else:
            # In milliseconds
            return datetime.fromtimestamp(timestamp / 1000).strftime(DATETIME_FORMAT)
