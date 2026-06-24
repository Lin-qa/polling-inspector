from __future__ import annotations

import logging
import time

from inspector.http_client import run_check
from inspector.models import CheckItem, CheckState, InspectorConfig
from inspector.notifier import WeComNotifier


class PollingRunner:
    def __init__(self, config: InspectorConfig, once: bool = False) -> None:
        self.config = config
        self.once = once
        self.notifier = WeComNotifier(config.notify_groups)
        self.states: dict[str, CheckState] = {}
        self.next_run_at: dict[str, float] = {}

    def run(self) -> None:
        logging.info("轮询巡检启动，接口数量：%s", len(self.config.checks))
        for item in self.config.checks:
            self.next_run_at[item.key] = 0

        while True:
            now = time.time()
            ran_any = False
            for item in self.config.checks:
                if now < self.next_run_at.get(item.key, 0):
                    continue
                self._run_item(item)
                self.next_run_at[item.key] = time.time() + item.interval_seconds
                ran_any = True

            if self.once:
                return

            if not ran_any:
                sleep_seconds = self._next_sleep_seconds()
                time.sleep(min(max(sleep_seconds, 0.5), 5))

    def _run_item(self, item: CheckItem) -> None:
        result = run_check(item, self.config.variables)
        state = self.states.setdefault(item.key, CheckState())

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
            return

        state.consecutive_failures += 1
        state.last_reason = result.reason
        logging.warning(
            "巡检失败 | %s | %s | 连续失败%s次 | %s",
            item.scenario_name,
            item.api_name,
            state.consecutive_failures,
            result.reason,
        )
        if state.consecutive_failures >= item.failure_threshold and not state.alerted:
            self.notifier.notify_failure(result, state.consecutive_failures)
            state.alerted = True

    def _next_sleep_seconds(self) -> float:
        if not self.next_run_at:
            return 1
        return min(self.next_run_at.values()) - time.time()

