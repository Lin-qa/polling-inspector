import unittest
from unittest.mock import patch

from inspector.models import CheckItem, CheckResult, CheckState, InspectorConfig
from inspector.runner import PollingRunner


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
        self.failure_count = 0
        self.recovery_count = 0

    def notify_failure(self, result, failure_count):
        self.failure_count += 1

    def notify_recovery(self, result):
        self.recovery_count += 1


class RunnerScheduleTests(unittest.TestCase):
    def test_failure_schedules_recovery_without_replacing_normal_schedule(self):
        item = make_item()
        runner = PollingRunner(InspectorConfig(checks=[item]), once=True)
        notifier = FakeNotifier()
        runner.notifier = notifier
        result = CheckResult(item=item, ok=False, http_status="ERR", elapsed_ms=1, checked_at="now", reason="fail")

        with patch("inspector.runner.run_check", return_value=result), patch("inspector.runner.time.time", return_value=1000), patch("inspector.runner.time.sleep"):
            runner.run()

        self.assertEqual(runner.normal_next_run_at[item.key], 4600)
        self.assertEqual(runner.recovery_next_run_at[item.key], 1600)
        self.assertTrue(runner.states[item.key].alerted)
        self.assertEqual(notifier.failure_count, 1)

    def test_recovery_check_does_not_move_normal_schedule(self):
        item = make_item()
        runner = PollingRunner(InspectorConfig(checks=[item]), once=True)
        notifier = FakeNotifier()
        runner.notifier = notifier
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


if __name__ == "__main__":
    unittest.main()

