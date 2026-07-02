import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from inspector.models import CheckItem, CheckResult, CheckState, DailySummary, InspectorConfig, PreRequest
from inspector.runner import PollingRunner, _next_summary_timestamp, run_once_inspection


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
        self.once_report_count = 0
        self.once_report = None

    def notify_startup(self, checks):
        self.startup_count += 1

    def notify_failure(self, result, failure_count):
        self.failure_count += 1

    def notify_recovery(self, result):
        self.recovery_count += 1

    def notify_daily_summary(self, summary):
        self.summary_count += 1
        self.summary = summary

    def notify_once_report(self, report):
        self.once_report_count += 1
        self.once_report = report


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
    def test_run_item_failure_records_and_notifies_when_enabled(self):
        item = make_item()
        runner = PollingRunner(InspectorConfig(checks=[item]), once=False)
        notifier = FakeNotifier()
        runner.notifier = notifier
        runner.stats_recorder = FakeStatsRecorder()
        result = CheckResult(item=item, ok=False, http_status="ERR", elapsed_ms=1, checked_at="now", reason="fail")

        with patch("inspector.runner.run_check", return_value=result), patch("inspector.runner.time.sleep"):
            returned = runner._run_item(item)

        self.assertIs(returned, result)
        self.assertTrue(runner.states[item.key].alerted)
        self.assertEqual(notifier.failure_count, 1)
        self.assertEqual(notifier.startup_count, 0)
        self.assertEqual(len(runner.stats_recorder.results), 1)

    def test_run_item_recovery_notifies_and_clears_state(self):
        item = make_item()
        runner = PollingRunner(InspectorConfig(checks=[item]), once=False)
        notifier = FakeNotifier()
        runner.notifier = notifier
        runner.stats_recorder = FakeStatsRecorder()
        runner.states[item.key] = CheckState(consecutive_failures=3, alerted=True)
        result = CheckResult(item=item, ok=True, http_status=200, elapsed_ms=1, checked_at="now")

        with patch("inspector.runner.run_check", return_value=result), patch("inspector.runner.time.sleep"):
            returned = runner._run_item(item)

        self.assertIs(returned, result)
        self.assertFalse(runner.states[item.key].alerted)
        self.assertEqual(notifier.recovery_count, 1)

    def test_run_item_refreshes_variables_with_pre_request(self):
        item = CheckItem(
            enabled=True,
            scenario_name="场景",
            api_name="接口",
            method="GET",
            url="https://api.example.test/health?ticketid=${ticketid}",
            headers={},
            params="无",
            success_rule="status=200",
            interval_seconds=3600,
            abnormal_interval_seconds=600,
            timeout_ms=5000,
            notify_group="默认组",
            pre_request_name="登录",
        )
        pre_request = PreRequest(
            name="登录",
            method="POST",
            url="https://api.example.test/login",
            headers={},
            params="无",
            success_rule="status=200",
            extractors={"ticketid": "result.ticketid"},
            timeout_ms=5000,
        )
        config = InspectorConfig(
            checks=[item],
            variables={"ticketid": "old-ticket"},
            pre_requests={"登录": pre_request},
        )
        runner = PollingRunner(config, once=False)
        runner.stats_recorder = FakeStatsRecorder()
        result = CheckResult(item=item, ok=True, http_status=200, elapsed_ms=1, checked_at="now")

        with patch("inspector.runner.run_pre_request", return_value=(True, "", {"ticketid": "new-ticket"})) as pre, patch("inspector.runner.run_check", return_value=result) as check:
            returned = runner._run_item(item)

        self.assertIs(returned, result)
        pre.assert_called_once()
        check.assert_called_once_with(item, {"ticketid": "new-ticket"})
        self.assertEqual(config.variables["ticketid"], "new-ticket")

    def test_reuses_successful_pre_request_variables(self):
        first_item = CheckItem(
            enabled=True,
            scenario_name="场景",
            api_name="接口1",
            method="GET",
            url="https://api.example.test/one?ticketid=${ticketid}",
            headers={},
            params="无",
            success_rule="status=200",
            interval_seconds=3600,
            abnormal_interval_seconds=600,
            timeout_ms=5000,
            notify_group="默认组",
            pre_request_name="登录",
        )
        second_item = CheckItem(
            enabled=True,
            scenario_name="场景",
            api_name="接口2",
            method="GET",
            url="https://api.example.test/two?ticketid=${ticketid}",
            headers={},
            params="无",
            success_rule="status=200",
            interval_seconds=3600,
            abnormal_interval_seconds=600,
            timeout_ms=5000,
            notify_group="默认组",
            pre_request_name="登录",
        )
        pre_request = PreRequest("登录", "POST", "https://api.example.test/login", {}, "无", "status=200", {"ticketid": "result.ticketid"}, 5000)
        config = InspectorConfig(checks=[first_item, second_item], variables={}, pre_requests={"登录": pre_request})
        runner = PollingRunner(config, once=False)
        runner.stats_recorder = FakeStatsRecorder()
        result = CheckResult(item=first_item, ok=True, http_status=200, elapsed_ms=1, checked_at="now")

        with patch("inspector.runner.run_pre_request", return_value=(True, "", {"ticketid": "new-ticket"})) as pre, patch("inspector.runner.run_check", return_value=result):
            runner._run_item(first_item)
            runner._run_item(second_item)

        pre.assert_called_once()
        self.assertEqual(config.variables["ticketid"], "new-ticket")

    def test_run_item_supports_multiple_pre_requests_in_order(self):
        item = CheckItem(
            enabled=True,
            scenario_name="场景",
            api_name="接口",
            method="GET",
            url="https://api.example.test/health?memberId=${member_id}",
            headers={},
            params="无",
            success_rule="status=200",
            interval_seconds=3600,
            abnormal_interval_seconds=600,
            timeout_ms=5000,
            notify_group="默认组",
            pre_request_name="登录, 会员详情",
        )
        config = InspectorConfig(
            checks=[item],
            variables={},
            pre_requests={
                "登录": PreRequest("登录", "POST", "https://api.example.test/login", {}, "无", "status=200", {"app_user_id": "result.useruuid"}, 5000),
                "会员详情": PreRequest("会员详情", "POST", "https://api.example.test/member", {}, '{"appId":"${app_user_id}"}', "status=200", {"member_id": "data.memId"}, 5000),
            },
        )
        runner = PollingRunner(config, once=False)
        runner.stats_recorder = FakeStatsRecorder()
        result = CheckResult(item=item, ok=True, http_status=200, elapsed_ms=1, checked_at="now")

        with patch(
            "inspector.runner.run_pre_request",
            side_effect=[
                (True, "", {"app_user_id": "user-uuid"}),
                (True, "", {"member_id": "member-id"}),
            ],
        ) as pre, patch("inspector.runner.run_check", return_value=result) as check:
            returned = runner._run_item(item)

        self.assertIs(returned, result)
        self.assertEqual(pre.call_count, 2)
        check.assert_called_once_with(item, {"app_user_id": "user-uuid", "member_id": "member-id"})

    def test_daily_summary_uses_previous_five_to_current_five_window(self):
        item = make_item()
        runner = PollingRunner(InspectorConfig(checks=[item]), once=False)
        notifier = FakeNotifier()
        stats_recorder = FakeStatsRecorder()
        runner.notifier = notifier
        runner.stats_recorder = stats_recorder
        due = datetime(2026, 6, 26, 17, 0, 0)
        runner.next_summary_at = due.timestamp()

        runner._send_due_summaries(due.timestamp())

        self.assertEqual(notifier.summary_count, 1)
        self.assertEqual(stats_recorder.summary_start, datetime(2026, 6, 25, 17, 0, 0))
        self.assertEqual(stats_recorder.summary_end, due)
        self.assertEqual(stats_recorder.prune_cutoff, due - timedelta(days=8))

    def test_next_summary_timestamp(self):
        before_summary = datetime(2026, 6, 26, 16, 59, 0)
        after_summary = datetime(2026, 6, 26, 17, 1, 0)

        self.assertEqual(
            datetime.fromtimestamp(_next_summary_timestamp(before_summary.timestamp())),
            datetime(2026, 6, 26, 17, 0, 0),
        )
        self.assertEqual(
            datetime.fromtimestamp(_next_summary_timestamp(after_summary.timestamp())),
            datetime(2026, 6, 27, 17, 0, 0),
        )

    def test_once_inspection_sends_one_report_without_failure_alert(self):
        item = make_item()
        config = InspectorConfig(checks=[item])
        notifier = FakeNotifier()
        stats_recorder = FakeStatsRecorder()
        result = CheckResult(item=item, ok=False, http_status="ERR", elapsed_ms=123, checked_at="now", reason="fail")

        with patch("inspector.runner.run_check", return_value=result), patch("inspector.runner.time.sleep"):
            report = run_once_inspection(config, stats_recorder, notifier)

        self.assertEqual(report.total, 1)
        self.assertEqual(report.success, 0)
        self.assertEqual(report.failure, 1)
        self.assertEqual(report.avg_elapsed_ms, 123)
        self.assertEqual(notifier.once_report_count, 1)
        self.assertEqual(notifier.failure_count, 0)
        self.assertEqual(len(stats_recorder.results), 1)

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
