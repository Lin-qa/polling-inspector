import logging
import tempfile
import unittest
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from main import LOG_BACKUP_DAYS, _setup_logging


class LoggingTests(unittest.TestCase):
    def tearDown(self):
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            handler.close()
        root_logger.handlers.clear()

    def test_setup_logging_writes_stream_and_keeps_seven_daily_backups(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file = Path(tmp_dir) / "inspection.log"

            _setup_logging(log_file)

            handlers = logging.getLogger().handlers
            rotating_handlers = [
                handler for handler in handlers if isinstance(handler, TimedRotatingFileHandler)
            ]
            self.assertEqual(len(rotating_handlers), 1)
            self.assertEqual(rotating_handlers[0].backupCount, LOG_BACKUP_DAYS)
            self.assertEqual(rotating_handlers[0].when, "MIDNIGHT")
            self.assertEqual(len(handlers), 2)

            logging.info("log check")

            self.assertIn("log check", log_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
