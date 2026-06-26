from __future__ import annotations

import argparse
import logging
from logging.handlers import TimedRotatingFileHandler
import sys
from pathlib import Path

from inspector.config_loader import create_template, load_config

DEFAULT_CONFIG = Path("config/巡检配置.xlsx")
LOG_BACKUP_DAYS = 7


def main() -> None:
    parser = argparse.ArgumentParser(description="接口轮询巡检工具")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init-config", help="生成巡检配置模板")
    init_parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="配置文件路径")

    run_parser = subparsers.add_parser("run", help="启动轮询巡检")
    run_parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="配置文件路径")
    run_parser.add_argument("--once", action="store_true", help="只执行一轮，并发送单次执行报告")
    run_parser.add_argument("--log-file", default="logs/inspection.log", help="日志文件路径")
    run_parser.add_argument("--stats-file", default="", help="统计文件路径，默认和日志文件放在同一目录")

    args = parser.parse_args(sys.argv[1:] or ["run"])

    if args.command == "init-config":
        create_template(Path(args.config))
        print(f"已生成配置模板：{args.config}")
        return

    log_file = Path(args.log_file)
    stats_file = Path(args.stats_file) if args.stats_file else log_file.with_name("inspection_stats.jsonl")
    _setup_logging(log_file)
    config = load_config(Path(args.config))
    from inspector.runner import PollingRunner

    runner = PollingRunner(config=config, once=args.once, stats_file=stats_file)
    runner.run()


def _setup_logging(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    stream_handler = logging.StreamHandler()
    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=LOG_BACKUP_DAYS,
        encoding="utf-8",
        delay=True,
    )
    for handler in [stream_handler, file_handler]:
        handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)


if __name__ == "__main__":
    main()
