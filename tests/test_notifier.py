import json
import unittest
from unittest.mock import patch

from inspector.models import NotifyGroup
from inspector.notifier import _build_feishu_payload, _build_wecom_payload, _is_feishu_group


class NotifierTests(unittest.TestCase):
    def test_detects_feishu_by_url_or_type(self):
        by_url = NotifyGroup(
            name="飞书组",
            webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/demo",
        )
        by_type = NotifyGroup(
            name="飞书组",
            webhook_url="https://example.test/webhook",
            webhook_type="飞书",
        )

        self.assertTrue(_is_feishu_group(by_url))
        self.assertTrue(_is_feishu_group(by_type))

    def test_builds_feishu_text_payload_without_secret(self):
        group = NotifyGroup(
            name="飞书组",
            webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/demo",
        )

        payload = _build_feishu_payload(group, "巡检报告")

        self.assertEqual(payload["msg_type"], "text")
        self.assertEqual(payload["content"]["text"], "巡检报告")
        self.assertNotIn("sign", payload)

    def test_builds_feishu_text_payload_with_secret(self):
        group = NotifyGroup(
            name="飞书组",
            webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/demo",
            secret="demo-secret",
        )

        with patch("inspector.notifier.time.time", return_value=1000):
            payload = _build_feishu_payload(group, "巡检报告")

        self.assertEqual(payload["timestamp"], "1000")
        self.assertTrue(payload["sign"])

    def test_builds_wecom_text_payload(self):
        group = NotifyGroup(
            name="企业微信群",
            webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=demo",
            mention_all=True,
        )

        payload = _build_wecom_payload(group, "巡检报告")

        self.assertEqual(payload["msgtype"], "text")
        self.assertEqual(payload["text"]["content"], "巡检报告")
        self.assertEqual(payload["text"]["mentioned_list"], ["@all"])
        json.dumps(payload, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
