from __future__ import annotations

import logging
import json
from urllib import error, request

from inspector.models import CheckItem, CheckResult, DailySummary, NotifyGroup
from inspector.sanitizer import sanitize_text


class WeComNotifier:
    def __init__(self, groups: dict[str, NotifyGroup]) -> None:
        self.groups = groups

    def notify_startup(self, checks: list[CheckItem]) -> None:
        content = "\n".join(
            [
                "【接口巡检启动】",
                f"启动接口数：{len(checks)}",
                "日报时间：每天 18:00",
                "日报周期：前一天 18:00:00 至当天 18:00:00",
            ]
        )
        self._send_all(content)

    def notify_daily_summary(self, summary: DailySummary) -> None:
        success_rate = (summary.success / summary.total * 100) if summary.total else 0
        lines = [
            "【接口巡检日报】",
            f"统计周期：{summary.window_start:%Y-%m-%d %H:%M:%S} 至 {summary.window_end:%Y-%m-%d %H:%M:%S}",
            f"巡检次数：{summary.total}",
            f"成功次数：{summary.success}",
            f"失败次数：{summary.failure}",
            f"成功率：{success_rate:.2f}%",
            f"平均响应时间：{summary.avg_elapsed_ms:.1f}ms",
            f"最大响应时间：{summary.max_elapsed_ms:.1f}ms",
        ]
        failed_apis = [item for item in summary.api_summaries if item.failure > 0]
        if failed_apis:
            lines.append("失败接口：")
            for item in failed_apis[:5]:
                lines.append(
                    f"- {item.scenario_name}/{item.api_name}：失败{item.failure}次，"
                    f"成功{item.success}次，平均{item.avg_elapsed_ms:.1f}ms"
                )
        else:
            lines.append("失败接口：无")
        self._send_all("\n".join(lines))

    def notify_failure(self, result: CheckResult, failure_count: int) -> None:
        item = result.item
        content = "\n".join(
            [
                "【接口巡检异常】",
                f"场景：{item.scenario_name}",
                f"接口：{item.api_name}",
                f"时间：{result.checked_at}",
                f"连续失败：{failure_count}次",
                f"HTTP状态：{result.http_status}",
                f"响应时间：{result.elapsed_ms:.1f}ms",
                f"异常原因：{sanitize_text(result.reason)}",
                f"请求方式：{item.method}",
                f"请求地址：{result.request_url}",
                f"请求参数：{result.request_params or '无'}",
                f"响应摘要：{result.response_text or '无'}",
            ]
        )
        self._send(item.notify_group, content)

    def notify_recovery(self, result: CheckResult) -> None:
        item = result.item
        content = "\n".join(
            [
                "【接口巡检恢复】",
                f"场景：{item.scenario_name}",
                f"接口：{item.api_name}",
                f"恢复时间：{result.checked_at}",
                f"HTTP状态：{result.http_status}",
                f"响应时间：{result.elapsed_ms:.1f}ms",
                f"请求地址：{result.request_url}",
            ]
        )
        self._send(item.notify_group, content)

    def _send_all(self, content: str) -> None:
        if not self.groups:
            logging.warning("未配置通知组，跳过通知")
            logging.info("通知内容：\n%s", content)
            return
        for group_name in self.groups:
            self._send(group_name, content)

    def _send(self, group_name: str, content: str) -> None:
        group = self.groups.get(group_name)
        if not group or not group.webhook_url:
            logging.warning("通知组未配置 webhook，跳过通知：%s", group_name)
            logging.info("通知内容：\n%s", content)
            return
        if "REPLACE_WITH_YOUR_KEY" in group.webhook_url or "替换" in group.webhook_url:
            logging.warning("通知组 webhook 仍是占位符，跳过通知：%s", group_name)
            logging.info("通知内容：\n%s", content)
            return

        payload = {
            "msgtype": "text",
            "text": {
                "content": content,
            },
        }
        if group.mention_all:
            payload["text"]["mentioned_list"] = ["@all"]

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            group.webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=5) as response:
                response.read()
            logging.info("企业微信通知已发送：%s", group_name)
        except Exception as exc:
            logging.error("企业微信通知发送失败：%s", exc)
