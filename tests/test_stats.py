import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from inspector.stats import StatsRecorder


class StatsRecorderTests(unittest.TestCase):
    def test_summarizes_records_in_window(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "inspection_stats.jsonl"
            path.write_text(
                "\n".join(
                    [
                        '{"recorded_at":"2026-06-25T05:59:59","scenario_name":"场景","api_name":"接口","ok":true,"elapsed_ms":100}',
                        '{"recorded_at":"2026-06-25T18:00:00","scenario_name":"场景","api_name":"接口","ok":true,"elapsed_ms":100}',
                        '{"recorded_at":"2026-06-25T19:00:00","scenario_name":"场景","api_name":"接口","ok":false,"elapsed_ms":300}',
                        '{"recorded_at":"2026-06-26T18:00:00","scenario_name":"场景","api_name":"接口","ok":true,"elapsed_ms":500}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            recorder = StatsRecorder(path)

            summary = recorder.summarize(
                datetime(2026, 6, 25, 18, 0, 0),
                datetime(2026, 6, 26, 18, 0, 0),
            )

        self.assertEqual(summary.total, 2)
        self.assertEqual(summary.success, 1)
        self.assertEqual(summary.failure, 1)
        self.assertEqual(summary.avg_elapsed_ms, 200)
        self.assertEqual(summary.max_elapsed_ms, 300)
        self.assertEqual(len(summary.api_summaries), 1)
        self.assertEqual(summary.api_summaries[0].failure, 1)


if __name__ == "__main__":
    unittest.main()
