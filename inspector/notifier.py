from __future__ import annotations

import logging
import json
from urllib import error, request

from inspector.models import CheckResult, NotifyGroup
from inspector.sanitizer import sanitize_text


class WeComNotifier:
    def __init__(self, groups: dict[str, NotifyGroup]) -> None:
        self.groups = groups

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

    def _send(self, group_name: str, content: str) -> None:
        group = self.groups.get(group_name)
        if not group or not group.webhook_url:
            logging.warning("通知组未配置 webhook，跳过通知：%s", group_name)
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
        except (error.URLError, TimeoutError, OSError) as exc:
            logging.error("企业微信通知发送失败：%s", exc)
