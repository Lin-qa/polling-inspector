from __future__ import annotations

import argparse
import logging
from pathlib import Path

from inspector.config_loader import create_template, load_config

DEFAULT_CONFIG = Path("config/巡检配置.xlsx")


def main() -> None:
    parser = argparse.ArgumentParser(description="接口轮询巡检工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-config", help="生成巡检配置模板")
    init_parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="配置文件路径")

    run_parser = subparsers.add_parser("run", help="启动轮询巡检")
    run_parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="配置文件路径")
    run_parser.add_argument("--once", action="store_true", help="只执行一轮，用于验证配置")
    run_parser.add_argument("--log-file", default="logs/inspection.log", help="日志文件路径")

    args = parser.parse_args()

    if args.command == "init-config":
        create_template(Path(args.config))
        print(f"已生成配置模板：{args.config}")
        return

    _setup_logging(Path(args.log_file))
    config = load_config(Path(args.config))
    from inspector.runner import PollingRunner

    runner = PollingRunner(config=config, once=args.once)
    runner.run()


def _setup_logging(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


if __name__ == "__main__":
    main()
