from __future__ import annotations

from pathlib import Path

from inspector.config_loader import load_config
from inspector.runner import run_once_inspection
from inspector.stats import StatsRecorder
from main import _setup_logging

CONFIG_FILE = Path("config/巡检配置.xlsx")
LOG_FILE = Path("logs/inspection.log")
STATS_FILE = Path("logs/inspection_stats.jsonl")


def run_once_from_pycharm():
    _setup_logging(LOG_FILE)
    config = load_config(CONFIG_FILE)
    return run_once_inspection(config, StatsRecorder(STATS_FILE))


if __name__ == "__main__":
    report = run_once_from_pycharm()
    print(
        "单次巡检完成："
        f"总数={report.total}，成功={report.success}，失败={report.failure}，"
        f"平均响应时间={report.avg_elapsed_ms:.1f}ms"
    )
