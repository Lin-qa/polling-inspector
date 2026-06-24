from __future__ import annotations

import json
import operator
import re
from typing import Any

OPS = {
    "=": operator.eq,
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}


def assert_success(body: bytes, http_status: int, elapsed_ms: float, rule: str) -> tuple[bool, str]:
    if not 200 <= http_status < 300:
        return False, f"HTTP状态码异常：{http_status}"

    rule = (rule or "").strip()
    if not rule:
        return True, ""

    checks = [item.strip() for item in re.split(r"[;\n]+", rule) if item.strip()]
    for check in checks:
        ok, reason = _assert_one(body, http_status, elapsed_ms, check)
        if not ok:
            return False, reason
    return True, ""


def _assert_one(body: bytes, http_status: int, elapsed_ms: float, rule: str) -> tuple[bool, str]:
    match = re.match(r"^(.+?)(>=|<=|==|!=|=|>|<)(.*)$", rule)
    if not match:
        return False, f"成功判断格式不支持：{rule}"

    left, op_text, expected_text = (part.strip() for part in match.groups())
    actual = _lookup_value(body, http_status, elapsed_ms, left)
    expected = _parse_expected(expected_text)

    left_value = _coerce_number(actual)
    right_value = _coerce_number(expected)
    if left_value is None or right_value is None:
        left_value = "" if actual is None else str(actual)
        right_value = "" if expected is None else str(expected)

    if OPS[op_text](left_value, right_value):
        return True, ""
    return False, f"成功判断不通过：{left} 实际值={actual}，期望 {op_text} {expected}"


def _lookup_value(body: bytes, http_status: int, elapsed_ms: float, path: str) -> Any:
    normalized = path.strip()
    if normalized in {"status", "http_status", "status_code"}:
        return http_status
    if normalized in {"elapsed_ms", "response_ms", "响应时间"}:
        return elapsed_ms

    data = _json_body(body)
    if normalized.startswith("$."):
        normalized = normalized[2:]
    elif normalized.startswith("json."):
        normalized = normalized[5:]

    value: Any = data
    for key in normalized.split("."):
        if key == "":
            continue
        if isinstance(value, dict):
            value = value.get(key)
        elif isinstance(value, list) and key.isdigit():
            value = value[int(key)]
        else:
            return None
    return value


def _json_body(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        return {}


def _parse_expected(value: str) -> Any:
    text = value.strip()
    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False
    if text.lower() == "null":
        return None
    number = _coerce_number(text)
    return number if number is not None else text.strip('"').strip("'")


def _coerce_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

