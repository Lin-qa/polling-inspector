import unittest

from inspector.sanitizer import sanitize_text, sanitize_url


class SanitizerTests(unittest.TestCase):
    def test_mask_query_secret(self):
        self.assertEqual(
            sanitize_url("https://api.example.test/a?ticketid=abc123&page=1"),
            "https://api.example.test/a?ticketid=%2A%2A%2A&page=1",
        )

    def test_mask_json_secret(self):
        token_value = "demo" + "token" + "value"
        text = sanitize_text('{"token":"' + token_value + '","name":"demo"}')
        self.assertIn('"token": "***"', text)
        self.assertIn('"name": "demo"', text)

    def test_mask_phone(self):
        phone = "138" + "1234" + "5678"
        self.assertIn("138****5678", sanitize_text("phone=" + phone))


if __name__ == "__main__":
    unittest.main()
