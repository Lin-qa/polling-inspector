from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from inspector.models import ApiSummary, CheckResult, DailySummary


class StatsRecorder:
    def __init__(self, path: Path) -> None:
        self.path = path

    def record(self, result: CheckResult) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "recorded_at": datetime.now().isoformat(timespec="seconds"),
                "scenario_name": result.item.scenario_name,
                "api_name": result.item.api_name,
                "ok": result.ok,
                "elapsed_ms": result.elapsed_ms,
            }
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as exc:
            logging.warning("巡检统计写入失败：%s", exc)

    def summarize(self, window_start: datetime, window_end: datetime) -> DailySummary:
        records = [
            record
            for record in self._read_records()
            if window_start <= record["recorded_at"] < window_end
        ]
        return _build_summary(window_start, window_end, records)

    def prune_before(self, cutoff: datetime) -> None:
        records = [record for record in self._read_records() if record["recorded_at"] >= cutoff]
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w", encoding="utf-8") as file:
                for record in records:
                    file.write(json.dumps(_dump_record(record), ensure_ascii=False) + "\n")
        except Exception as exc:
            logging.warning("巡检统计清理失败：%s", exc)

    def _read_records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        try:
            with self.path.open("r", encoding="utf-8") as file:
                for line in file:
                    record = _parse_record(line)
                    if record is not None:
                        records.append(record)
        except Exception as exc:
            logging.warning("巡检统计读取失败：%s", exc)
        return records


def _parse_record(line: str) -> dict[str, Any] | None:
    try:
        data = json.loads(line)
        return {
            "recorded_at": datetime.fromisoformat(str(data["recorded_at"])),
            "scenario_name": str(data.get("scenario_name") or ""),
            "api_name": str(data.get("api_name") or ""),
            "ok": bool(data.get("ok")),
            "elapsed_ms": float(data.get("elapsed_ms") or 0),
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _dump_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "recorded_at": record["recorded_at"].isoformat(timespec="seconds"),
        "scenario_name": record["scenario_name"],
        "api_name": record["api_name"],
        "ok": record["ok"],
        "elapsed_ms": record["elapsed_ms"],
    }


def _build_summary(
    window_start: datetime,
    window_end: datetime,
    records: list[dict[str, Any]],
) -> DailySummary:
    total = len(records)
    success = sum(1 for record in records if record["ok"])
    failure = total - success
    elapsed_values = [record["elapsed_ms"] for record in records]
    avg_elapsed_ms = sum(elapsed_values) / total if total else 0
    max_elapsed_ms = max(elapsed_values) if elapsed_values else 0

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(record["scenario_name"], record["api_name"])].append(record)

    api_summaries = []
    for (scenario_name, api_name), api_records in grouped.items():
        api_total = len(api_records)
        api_success = sum(1 for record in api_records if record["ok"])
        api_failure = api_total - api_success
        api_elapsed = [record["elapsed_ms"] for record in api_records]
        api_summaries.append(
            ApiSummary(
                scenario_name=scenario_name,
                api_name=api_name,
                total=api_total,
                success=api_success,
                failure=api_failure,
                avg_elapsed_ms=sum(api_elapsed) / api_total if api_total else 0,
                max_elapsed_ms=max(api_elapsed) if api_elapsed else 0,
            )
        )

    api_summaries.sort(key=lambda item: (item.failure, item.total), reverse=True)
    return DailySummary(
        window_start=window_start,
        window_end=window_end,
        total=total,
        success=success,
        failure=failure,
        avg_elapsed_ms=avg_elapsed_ms,
        max_elapsed_ms=max_elapsed_ms,
        api_summaries=api_summaries,
    )
