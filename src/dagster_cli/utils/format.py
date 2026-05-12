"""Shared formatting utilities — pure functions, no I/O."""

from datetime import datetime, timezone

from dagster_cli.constants import DATETIME_FORMAT

_STATUS_STYLES: dict[str, tuple[str, str]] = {
    # Run statuses
    "SUCCESS": ("green", "✓"),
    "FAILURE": ("red", "✗"),
    "FAILED": ("red", "✗"),
    "STARTED": ("yellow", "⏳"),
    "QUEUED": ("yellow", "⏳"),
    "CANCELING": ("yellow", ""),
    "CANCELED": ("dim", ""),
    # Automation statuses
    "RUNNING": ("green", "✓"),
    "STOPPED": ("yellow", "⏸"),
    # Tick statuses (overlap with run statuses above)
    "SKIPPED": ("dim", ""),
    # Deployment statuses
    "ACTIVE": ("green", ""),
    # Asset / dependency pseudo-statuses
    "NEVER": ("dim", ""),
}


def colorize_status(status: str, *, with_icon: bool = False) -> str:
    """Wrap *status* in Rich color markup.

    ``with_icon=True`` appends the status-specific symbol used in detail panels.
    """
    style, icon = _STATUS_STYLES.get(status, ("white", ""))
    text = f"{status} {icon}".strip() if with_icon and icon else status
    return f"[{style}]{text}[/{style}]"


def normalize_epoch_seconds(ts: float | int) -> float:
    """Normalize an epoch timestamp to seconds (handles both ms and s)."""
    return ts / 1000.0 if ts > 10_000_000_000 else float(ts)


def format_timestamp(ts: float | int | str | None) -> str:
    """Format a Unix timestamp (seconds or milliseconds) to a readable string."""
    if not ts:
        return "N/A"
    if isinstance(ts, str):
        try:
            ts = float(ts)
        except ValueError:
            return "N/A"
    dt = datetime.fromtimestamp(normalize_epoch_seconds(ts), tz=timezone.utc)
    return dt.strftime(DATETIME_FORMAT)


def format_duration(start: float | int | None, end: float | int | None) -> str:
    """Format the wall-clock duration between two epoch timestamps."""
    if not start or not end:
        return "—"
    duration = int(normalize_epoch_seconds(end) - normalize_epoch_seconds(start))
    hours, remainder = divmod(duration, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def format_asset_key(key: str | list[str]) -> str:
    """Normalize an asset key to a slash-separated string."""
    if isinstance(key, list):
        return "/".join(key)
    return str(key)


def format_job_name(name: str) -> str:
    """Return a display-friendly job name, expanding Dagster's internal aliases."""
    if name == "__ASSET_JOB":
        return "__ASSET_JOB (asset job)"
    return name
