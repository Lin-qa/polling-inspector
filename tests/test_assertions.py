import unittest

from inspector.assertions import assert_success


class AssertionTests(unittest.TestCase):
    def test_status_only(self):
        ok, reason = assert_success(b"{}", 200, 10, "status=200")
        self.assertTrue(ok, reason)

    def test_json_field(self):
        ok, reason = assert_success(b'{"code":0,"data":{"count":3}}', 200, 10, "code=0; data.count>=1")
        self.assertTrue(ok, reason)

    def test_elapsed_ms(self):
        ok, reason = assert_success(b"{}", 200, 1200, "elapsed_ms<1000")
        self.assertFalse(ok)
        self.assertIn("成功判断不通过", reason)


if __name__ == "__main__":
    unittest.main()

