import unittest
from unittest.mock import patch

from inspector.http_client import run_pre_request
from inspector.models import PreRequest


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return (
            b'{"result":"{\\"ticketid\\":\\"new-ticket\\",'
            b'\\"useruuid\\":\\"user-uuid\\",\\"userid\\":\\"7327031\\"}"}'
        )


class HttpClientTests(unittest.TestCase):
    def test_pre_request_extracts_nested_json_string(self):
        pre_request = PreRequest(
            name="登录",
            method="POST",
            url="https://api.example.test/login",
            headers={"Content-Type": "application/json"},
            params='{"openid":"${openid}"}',
            success_rule="status=200",
            extractors={
                "ticketid": "result.ticketid",
                "app_user_id": "result.useruuid",
                "userid": "result.userid",
            },
            timeout_ms=5000,
        )

        with patch("inspector.http_client.request.urlopen", return_value=FakeResponse()):
            ok, reason, variables = run_pre_request(pre_request, {"openid": "open-id"})

        self.assertTrue(ok, reason)
        self.assertEqual(variables["ticketid"], "new-ticket")
        self.assertEqual(variables["app_user_id"], "user-uuid")
        self.assertEqual(variables["userid"], "7327031")


if __name__ == "__main__":
    unittest.main()
