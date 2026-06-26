from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

from inspector.http_client import run_check
from inspector.models import CheckItem, CheckResult, CheckState, InspectorConfig, OnceRunReport
from inspector.notifier import WeComNotifier
from inspector.stats import StatsRecorder

MAX_ATTEMPTS_PER_CHECK = 3
SUMMARY_HOUR = 18
STATS_RETENTION_DAYS = 8


class PollingRunner:
    def __init__(self, config: InspectorConfig, once: bool = False, stats_file: Path | None = None) -> None:
        self.config = config
        self.once = once
        self.notifier = WeComNotifier(config.notify_groups)
        self.stats_recorder = StatsRecorder(stats_file or Path("logs/inspection_stats.jsonl"))
        self.states: dict[str, CheckState] = {}
        self.normal_next_run_at: dict[str, float] = {}
        self.recovery_next_run_at: dict[str, float] = {}
        self.next_summary_at: float | None = None
        self._startup_notified = False

    def run(self) -> None:
        logging.info("轮询巡检启动，接口数量：%s", len(self.config.checks))
        if self.once:
            self.run_once()
            return
        self._notify_startup_once()
        self.next_summary_at = _next_summary_timestamp(time.time())
        for item in self.config.checks:
            self.normal_next_run_at[item.key] = 0

        while True:
            now = time.time()
            if not self.once:
                self._send_due_summaries(now)
            ran_any = False
            for item in self.config.checks:
                state = self.states.setdefault(item.key, CheckState())
                normal_due = now >= self.normal_next_run_at.get(item.key, 0)
                recovery_due = state.alerted and now >= self.recovery_next_run_at.get(item.key, float("inf"))
                if not normal_due and not recovery_due:
                    continue
                self._run_item(item)
                if normal_due:
                    self.normal_next_run_at[item.key] = time.time() + item.interval_seconds
                if self.states[item.key].alerted:
                    self.recovery_next_run_at[item.key] = time.time() + item.abnormal_interval_seconds
                else:
                    self.recovery_next_run_at.pop(item.key, None)
                ran_any = True

            if not ran_any:
                sleep_seconds = self._next_sleep_seconds()
                time.sleep(min(max(sleep_seconds, 0.5), 5))

    def run_once(self) -> OnceRunReport:
        return run_once_inspection(self.config, self.stats_recorder, self.notifier)

    def _run_item(self, item: CheckItem, notify_failure: bool = True) -> CheckResult | None:
        state = self.states.setdefault(item.key, CheckState())
        result = None

        for attempt in range(1, MAX_ATTEMPTS_PER_CHECK + 1):
            result = run_check(item, self.config.variables)
            if result.ok:
                break
            logging.warning(
                "巡检失败 | %s | %s | 第%s/%s次 | %s",
                item.scenario_name,
                item.api_name,
                attempt,
                MAX_ATTEMPTS_PER_CHECK,
                result.reason,
            )
            if attempt < MAX_ATTEMPTS_PER_CHECK:
                time.sleep(1)

        if result is None:
            return None

        self.stats_recorder.record(result)
        if result.ok:
            logging.info(
                "巡检成功 | %s | %s | %.1fms | HTTP %s",
                item.scenario_name,
                item.api_name,
                result.elapsed_ms,
                result.http_status,
            )
            if state.alerted:
                self.notifier.notify_recovery(result)
            state.consecutive_failures = 0
            state.alerted = False
            state.last_reason = ""
            return result

        state.consecutive_failures = MAX_ATTEMPTS_PER_CHECK
        state.last_reason = result.reason
        if notify_failure and not state.alerted:
            self.notifier.notify_failure(result, state.consecutive_failures)
            state.alerted = True
        return result

    def _notify_startup_once(self) -> None:
        if self._startup_notified:
            return
        self.notifier.notify_startup(self.config.checks)
        self._startup_notified = True

    def _send_due_summaries(self, now: float) -> None:
        if self.next_summary_at is None:
            return
        while now >= self.next_summary_at:
            window_end = datetime.fromtimestamp(self.next_summary_at)
            window_start = window_end - timedelta(days=1)
            summary = self.stats_recorder.summarize(window_start, window_end)
            self.notifier.notify_daily_summary(summary)
            self.stats_recorder.prune_before(window_end - timedelta(days=STATS_RETENTION_DAYS))
            self.next_summary_at = _next_summary_timestamp(self.next_summary_at + 1)

    def _next_sleep_seconds(self) -> float:
        next_times = list(self.normal_next_run_at.values()) + list(self.recovery_next_run_at.values())
        if self.next_summary_at is not None:
            next_times.append(self.next_summary_at)
        if not next_times:
            return 1
        return min(next_times) - time.time()


def _next_summary_timestamp(timestamp: float) -> float:
    current = datetime.fromtimestamp(timestamp)
    summary_time = current.replace(hour=SUMMARY_HOUR, minute=0, second=0, microsecond=0)
    if current >= summary_time:
        summary_time += timedelta(days=1)
    return summary_time.timestamp()


def run_once_inspection(
    config: InspectorConfig,
    stats_recorder: StatsRecorder | None = None,
    notifier: WeComNotifier | None = None,
) -> OnceRunReport:
    started_at = datetime.now()
    recorder = stats_recorder or StatsRecorder(Path("logs/inspection_stats.jsonl"))
    report_notifier = notifier or WeComNotifier(config.notify_groups)
    runner = PollingRunner(config=config, once=True)
    runner.stats_recorder = recorder
    runner.notifier = report_notifier

    results = []
    for item in config.checks:
        result = runner._run_item(item, notify_failure=False)
        if result is not None:
            results.append(result)

    finished_at = datetime.now()
    total = len(results)
    success = sum(1 for result in results if result.ok)
    failure = total - success
    elapsed_values = [result.elapsed_ms for result in results]
    report = OnceRunReport(
        started_at=started_at,
        finished_at=finished_at,
        total=total,
        success=success,
        failure=failure,
        avg_elapsed_ms=sum(elapsed_values) / total if total else 0,
        max_elapsed_ms=max(elapsed_values) if elapsed_values else 0,
        results=results,
    )
    report_notifier.notify_once_report(report)
    return report
