from __future__ import annotations

import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "token",
    "ticket",
    "ticketid",
    "session",
    "openid",
    "unionid",
    "userid",
    "user_id",
    "memid",
    "password",
    "secret",
    "sign",
}


def sanitize_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = _mask_json_like(text)
    text = re.sub(r"1[3-9]\d{9}", lambda m: m.group(0)[:3] + "****" + m.group(0)[-4:], text)
    text = re.sub(r"\b\d{17}[\dXx]\b", lambda m: m.group(0)[:6] + "********" + m.group(0)[-4:], text)
    text = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._\-+/=]{12,}", r"\1***", text)
    text = re.sub(r"(?i)(saas-token-ex=)[^;,\s]+", r"\1***", text)
    text = re.sub(r"(?i)\b(token|ticketid|ticket|password|secret|sign)=([^&\s]+)", lambda m: f"{m.group(1)}=***", text)
    text = re.sub(r"\b[A-Za-z0-9+/=_-]{48,}\b", "***", text)
    return text


def sanitize_url(url: str) -> str:
    parts = urlsplit(url)
    if not parts.query:
        return url
    masked = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        masked.append((key, "***" if _is_sensitive_key(key) else value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(masked), parts.fragment))


def _mask_json_like(text: str) -> str:
    try:
        data = json.loads(text)
    except Exception:
        return text
    return json.dumps(_mask_value(data), ensure_ascii=False)


def _mask_value(value):
    if isinstance(value, dict):
        return {key: ("***" if _is_sensitive_key(key) else _mask_value(val)) for key, val in value.items()}
    if isinstance(value, list):
        return [_mask_value(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
    return any(name.replace("_", "") in normalized for name in SENSITIVE_KEYS)

