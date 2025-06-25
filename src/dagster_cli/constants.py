"""Constants used throughout the Dagster CLI application."""

from pathlib import Path

APP_NAME = "dagster-cli"
CONFIG_DIR = Path.home() / ".config" / "dagster-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_PROFILE = "default"

ENV_TOKEN = "DAGSTER_CLOUD_TOKEN"
ENV_URL = "DAGSTER_CLOUD_URL"
ENV_LOCATION = "DAGSTER_CLOUD_LOCATION"
ENV_REPOSITORY = "DAGSTER_CLOUD_REPOSITORY"

DEFAULT_TIMEOUT = 120
DEFAULT_RUN_LIMIT = 10
DEFAULT_JOB_LIMIT = 20

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Deployment option configuration
DEPLOYMENT_OPTION_NAME = "--deployment"
DEPLOYMENT_OPTION_SHORT = "-d"
DEPLOYMENT_OPTION_HELP = "Dagster+ deployment name (default: prod)"
DEPLOYMENT_OPTION_DEFAULT = None  # None means use "prod"
