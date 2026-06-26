from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class NotifyGroup:
    name: str
    webhook_url: str
    mention_all: bool = False


@dataclass(frozen=True)
class CheckItem:
    enabled: bool
    scenario_name: str
    api_name: str
    method: str
    url: str
    headers: dict[str, str]
    params: str
    success_rule: str
    interval_seconds: float
    abnormal_interval_seconds: float
    timeout_ms: int
    notify_group: str

    @property
    def key(self) -> str:
        return f"{self.scenario_name}::{self.api_name}::{self.url}"


@dataclass
class CheckResult:
    item: CheckItem
    ok: bool
    http_status: int | str
    elapsed_ms: float
    checked_at: str
    reason: str = ""
    response_text: str = ""
    request_url: str = ""
    request_params: str = ""


@dataclass
class CheckState:
    consecutive_failures: int = 0
    alerted: bool = False
    last_reason: str = ""


@dataclass
class InspectorConfig:
    checks: list[CheckItem] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)
    sensitive_variables: set[str] = field(default_factory=set)
    notify_groups: dict[str, NotifyGroup] = field(default_factory=dict)


@dataclass(frozen=True)
class ApiSummary:
    scenario_name: str
    api_name: str
    total: int
    success: int
    failure: int
    avg_elapsed_ms: float
    max_elapsed_ms: float


@dataclass(frozen=True)
class DailySummary:
    window_start: datetime
    window_end: datetime
    total: int
    success: int
    failure: int
    avg_elapsed_ms: float
    max_elapsed_ms: float
    api_summaries: list[ApiSummary] = field(default_factory=list)
