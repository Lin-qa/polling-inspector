import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from inspector.models import CheckItem, CheckResult, CheckState, DailySummary, InspectorConfig
from inspector.runner import PollingRunner, _next_summary_timestamp


def make_item() -> CheckItem:
    return CheckItem(
        enabled=True,
        scenario_name="场景",
        api_name="接口",
        method="GET",
        url="https://api.example.test/health",
        headers={},
        params="无",
        success_rule="status=200",
        interval_seconds=3600,
        abnormal_interval_seconds=600,
        timeout_ms=5000,
        notify_group="默认组",
    )


class FakeNotifier:
    def __init__(self) -> None:
        self.startup_count = 0
        self.failure_count = 0
        self.recovery_count = 0
        self.summary_count = 0
        self.summary = None

    def notify_startup(self, checks):
        self.startup_count += 1

    def notify_failure(self, result, failure_count):
        self.failure_count += 1

    def notify_recovery(self, result):
        self.recovery_count += 1

    def notify_daily_summary(self, summary):
        self.summary_count += 1
        self.summary = summary


class FakeStatsRecorder:
    def __init__(self) -> None:
        self.results = []
        self.summary_start = None
        self.summary_end = None
        self.prune_cutoff = None

    def record(self, result):
        self.results.append(result)

    def summarize(self, window_start, window_end):
        self.summary_start = window_start
        self.summary_end = window_end
        return DailySummary(
            window_start=window_start,
            window_end=window_end,
            total=1,
            success=1,
            failure=0,
            avg_elapsed_ms=12,
            max_elapsed_ms=12,
        )

    def prune_before(self, cutoff):
        self.prune_cutoff = cutoff


class RunnerScheduleTests(unittest.TestCase):
    def test_failure_schedules_recovery_without_replacing_normal_schedule(self):
        item = make_item()
        runner = PollingRunner(InspectorConfig(checks=[item]), once=True)
        notifier = FakeNotifier()
        runner.notifier = notifier
        runner.stats_recorder = FakeStatsRecorder()
        result = CheckResult(item=item, ok=False, http_status="ERR", elapsed_ms=1, checked_at="now", reason="fail")

        with patch("inspector.runner.run_check", return_value=result), patch("inspector.runner.time.time", return_value=1000), patch("inspector.runner.time.sleep"):
            runner.run()

        self.assertEqual(runner.normal_next_run_at[item.key], 4600)
        self.assertEqual(runner.recovery_next_run_at[item.key], 1600)
        self.assertTrue(runner.states[item.key].alerted)
        self.assertEqual(notifier.failure_count, 1)
        self.assertEqual(notifier.startup_count, 0)
        self.assertEqual(len(runner.stats_recorder.results), 1)

    def test_recovery_check_does_not_move_normal_schedule(self):
        item = make_item()
        runner = PollingRunner(InspectorConfig(checks=[item]), once=True)
        notifier = FakeNotifier()
        runner.notifier = notifier
        runner.stats_recorder = FakeStatsRecorder()
        runner.normal_next_run_at[item.key] = 4600
        runner.recovery_next_run_at[item.key] = 1000
        runner.states[item.key] = CheckState(consecutive_failures=3, alerted=True)
        result = CheckResult(item=item, ok=True, http_status=200, elapsed_ms=1, checked_at="now")

        with patch("inspector.runner.run_check", return_value=result), patch("inspector.runner.time.time", return_value=1000), patch("inspector.runner.time.sleep"):
            runner.run()

        self.assertEqual(runner.normal_next_run_at[item.key], 4600)
        self.assertNotIn(item.key, runner.recovery_next_run_at)
        self.assertFalse(runner.states[item.key].alerted)
        self.assertEqual(notifier.recovery_count, 1)

    def test_daily_summary_uses_previous_six_to_current_six_window(self):
        item = make_item()
        runner = PollingRunner(InspectorConfig(checks=[item]), once=False)
        notifier = FakeNotifier()
        stats_recorder = FakeStatsRecorder()
        runner.notifier = notifier
        runner.stats_recorder = stats_recorder
        due = datetime(2026, 6, 26, 18, 0, 0)
        runner.next_summary_at = due.timestamp()

        runner._send_due_summaries(due.timestamp())

        self.assertEqual(notifier.summary_count, 1)
        self.assertEqual(stats_recorder.summary_start, datetime(2026, 6, 25, 18, 0, 0))
        self.assertEqual(stats_recorder.summary_end, due)
        self.assertEqual(stats_recorder.prune_cutoff, due - timedelta(days=8))

    def test_next_summary_timestamp(self):
        before_summary = datetime(2026, 6, 26, 17, 59, 0)
        after_summary = datetime(2026, 6, 26, 18, 1, 0)

        self.assertEqual(
            datetime.fromtimestamp(_next_summary_timestamp(before_summary.timestamp())),
            datetime(2026, 6, 26, 18, 0, 0),
        )
        self.assertEqual(
            datetime.fromtimestamp(_next_summary_timestamp(after_summary.timestamp())),
            datetime(2026, 6, 27, 18, 0, 0),
        )

    def test_startup_notification_only_for_loop_mode(self):
        item = make_item()
        runner = PollingRunner(InspectorConfig(checks=[item]), once=False)
        notifier = FakeNotifier()
        runner.notifier = notifier

        runner._notify_startup_once()
        runner._notify_startup_once()

        self.assertEqual(notifier.startup_count, 1)


if __name__ == "__main__":
    unittest.main()
