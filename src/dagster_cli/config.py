"""Configuration management for Dagster CLI."""

import json
import os
from typing import Any

from dagster_cli.constants import (
    CONFIG_DIR,
    CONFIG_FILE,
    DEFAULT_PROFILE,
    ENV_LOCATION,
    ENV_REPOSITORY,
    ENV_TOKEN,
    ENV_URL,
)
from dagster_cli.utils.errors import ConfigError


class Config:
    """Manages configuration and authentication for Dagster CLI."""

    def __init__(self):
        self._ensure_config_dir()
        self._config = self._load_config()

    def _ensure_config_dir(self) -> None:
        """Create config directory if it doesn't exist."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Set restrictive permissions on config directory
        if os.name != "nt":  # Unix-like systems
            CONFIG_DIR.chmod(0o700)

    def _load_config(self) -> dict[str, Any]:
        """Load configuration from file."""
        if not CONFIG_FILE.exists():
            return {
                "version": "1.0",
                "profiles": {},
                "current_profile": DEFAULT_PROFILE,
            }

        try:
            with CONFIG_FILE.open() as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid configuration file: {e}") from e
        except Exception as e:
            raise ConfigError(f"Error reading configuration: {e}") from e

    def _save_config(self) -> None:
        """Save configuration to file."""
        try:
            with CONFIG_FILE.open("w") as f:
                json.dump(self._config, f, indent=2)

            # Set restrictive permissions on config file
            if os.name != "nt":  # Unix-like systems
                CONFIG_FILE.chmod(0o600)
        except Exception as e:
            raise ConfigError(f"Error saving configuration: {e}") from e

    def get_profile(self, profile_name: str | None = None) -> dict[str, str]:
        """Get profile configuration, with environment variable fallback."""
        if profile_name is None:
            profile_name = self._config.get("current_profile", DEFAULT_PROFILE)

        profile = self._config.get("profiles", {}).get(profile_name, {})

        # Environment variables take precedence
        return {
            "url": os.getenv(ENV_URL, profile.get("url", "")),
            "token": os.getenv(ENV_TOKEN, profile.get("token", "")),
            "location": os.getenv(ENV_LOCATION, profile.get("location", "")),
            "repository": os.getenv(ENV_REPOSITORY, profile.get("repository", "")),
        }

    def set_profile(
        self,
        profile_name: str,
        url: str,
        token: str,
        location: str | None = None,
        repository: str | None = None,
    ) -> None:
        """Set profile configuration."""
        if "profiles" not in self._config:
            self._config["profiles"] = {}

        self._config["profiles"][profile_name] = {"url": url, "token": token}

        if location:
            self._config["profiles"][profile_name]["location"] = location
        if repository:
            self._config["profiles"][profile_name]["repository"] = repository

        self._save_config()

    def delete_profile(self, profile_name: str) -> None:
        """Delete a profile."""
        if profile_name in self._config.get("profiles", {}):
            del self._config["profiles"][profile_name]

            # If we deleted the current profile, reset to default
            if self._config.get("current_profile") == profile_name:
                self._config["current_profile"] = DEFAULT_PROFILE

            self._save_config()

    def set_current_profile(self, profile_name: str) -> None:
        """Set the current active profile."""
        if profile_name not in self._config.get("profiles", {}):
            raise ConfigError(f"Profile '{profile_name}' does not exist")

        self._config["current_profile"] = profile_name
        self._save_config()

    def get_current_profile_name(self) -> str:
        """Get the name of the current profile."""
        return self._config.get("current_profile", DEFAULT_PROFILE)

    def list_profiles(self) -> dict[str, dict[str, str]]:
        """List all profiles."""
        return self._config.get("profiles", {})

    def has_auth(self, profile_name: str | None = None) -> bool:
        """Check if authentication is configured."""
        profile = self.get_profile(profile_name)
        return bool(profile.get("url") and profile.get("token"))
