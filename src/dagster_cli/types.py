"""Shared TypedDicts for data contracts between client methods and output functions."""

from typing import Any

from typing_extensions import TypedDict


class RunSummary(TypedDict, total=False):
    id: str
    status: str
    startTime: float | None
    endTime: float | None
    pipeline: dict[str, Any]
    stats: dict[str, Any]
    mode: str


class TickSummary(TypedDict, total=False):
    timestamp: float | None
    status: str
    run_count: int
    run_ids: list[str]
    error: str | None


class AutomationSummary(TypedDict, total=False):
    name: str
    type: str
    target: str
    description: str
    status: str
    cron_schedule: str | None
    last_tick: float | None
    last_run_status: str | None
    last_run_timestamp: float | None
    tick_status: str | None
    tick_run_count: int
    location: str
    repository: str


class AssetSummary(TypedDict, total=False):
    id: str
    key: dict[str, Any]
    groupName: str | None
    description: str | None
    computeKind: str | None
    location: str
    repository: str
    assetMaterializations: list[dict[str, Any]]
