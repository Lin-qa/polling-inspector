from __future__ import annotations

import json
import ssl
import time
from datetime import datetime
from urllib import error, parse, request

import certifi

from inspector.assertions import assert_success
from inspector.models import CheckItem, CheckResult, PreRequest
from inspector.sanitizer import sanitize_text, sanitize_url
from inspector.variables import apply_variables, unresolved_variables

EMPTY_PARAMS = {"", "无", "空", "EMPTY", "__EMPTY__"}


def run_check(item: CheckItem, variables: dict[str, str]) -> CheckResult:
    checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    url = apply_variables(item.url, variables)
    headers = {key: apply_variables(value, variables) for key, value in item.headers.items()}
    params = apply_variables(item.params, variables)

    unresolved = unresolved_variables(url, headers, params)
    if unresolved:
        return CheckResult(
            item=item,
            ok=False,
            http_status="CONFIG",
            elapsed_ms=0,
            checked_at=checked_at,
            reason=f"参数未传入：{', '.join(unresolved)}",
            request_url=sanitize_url(url),
            request_params=sanitize_text(params),
        )

    start = time.perf_counter()
    request_url = url
    try:
        request_url, payload, request_headers = _prepare_request(item.method, url, params, headers)
        req = request.Request(request_url, data=payload, headers=request_headers, method=item.method)
        with request.urlopen(req, timeout=item.timeout_ms / 1000, context=_ssl_context()) as response:
            body = response.read()
            status = response.status
        elapsed_ms = (time.perf_counter() - start) * 1000
        ok, reason = assert_success(body, status, elapsed_ms, item.success_rule)
        if ok and elapsed_ms > item.timeout_ms:
            ok = False
            reason = f"请求时间超过超时时间：{elapsed_ms:.1f}ms > {item.timeout_ms}ms"
        return CheckResult(
            item=item,
            ok=ok,
            http_status=status,
            elapsed_ms=elapsed_ms,
            checked_at=checked_at,
            reason=reason,
            response_text=sanitize_text(body.decode("utf-8", errors="replace")[:500]),
            request_url=sanitize_url(request_url),
            request_params=sanitize_text(params),
        )
    except error.HTTPError as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        body = exc.read()
        ok, reason = assert_success(body, exc.code, elapsed_ms, item.success_rule)
        return CheckResult(
            item=item,
            ok=ok,
            http_status=exc.code,
            elapsed_ms=elapsed_ms,
            checked_at=checked_at,
            reason=reason or f"HTTP状态码异常：{exc.code}",
            response_text=sanitize_text(body.decode("utf-8", errors="replace")[:500]),
            request_url=sanitize_url(request_url),
            request_params=sanitize_text(params),
        )
    except (error.URLError, TimeoutError, OSError) as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return CheckResult(
            item=item,
            ok=False,
            http_status="ERR",
            elapsed_ms=elapsed_ms,
            checked_at=checked_at,
            reason=f"请求异常：{type(exc).__name__}: {exc}",
            request_url=sanitize_url(request_url),
            request_params=sanitize_text(params),
        )


def run_pre_request(item: PreRequest, variables: dict[str, str]) -> tuple[bool, str, dict[str, str]]:
    url = apply_variables(item.url, variables)
    headers = {key: apply_variables(value, variables) for key, value in item.headers.items()}
    params = apply_variables(item.params, variables)

    unresolved = unresolved_variables(url, headers, params)
    if unresolved:
        return False, f"前置请求参数未传入：{', '.join(unresolved)}", {}

    start = time.perf_counter()
    request_url = url
    try:
        request_url, payload, request_headers = _prepare_request(item.method, url, params, headers)
        req = request.Request(request_url, data=payload, headers=request_headers, method=item.method)
        with request.urlopen(req, timeout=item.timeout_ms / 1000, context=_ssl_context()) as response:
            body = response.read()
            status = response.status
        elapsed_ms = (time.perf_counter() - start) * 1000
        ok, reason = assert_success(body, status, elapsed_ms, item.success_rule)
        if not ok:
            return False, f"前置请求成功判断不通过：{reason}", {}
        return True, "", _extract_variables(body, item.extractors)
    except error.HTTPError as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        body = exc.read()
        ok, reason = assert_success(body, exc.code, elapsed_ms, item.success_rule)
        if ok:
            try:
                return True, "", _extract_variables(body, item.extractors)
            except ValueError as extract_error:
                return False, str(extract_error), {}
        return False, reason or f"前置请求HTTP状态码异常：{exc.code}", {}
    except ValueError as exc:
        return False, str(exc), {}
    except (error.URLError, TimeoutError, OSError) as exc:
        return False, f"前置请求异常：{type(exc).__name__}: {exc}；请求={sanitize_url(request_url)}", {}


def _prepare_request(
    method: str,
    url: str,
    params: str,
    headers: dict[str, str],
) -> tuple[str, bytes | None, dict[str, str]]:
    request_headers = dict(headers)
    if params.strip() in EMPTY_PARAMS:
        return url, None, request_headers
    if method == "GET":
        return _append_query(url, params), None, request_headers
    if _looks_like_json(params):
        request_headers.setdefault("Content-Type", "application/json")
        return url, json.dumps(json.loads(params), ensure_ascii=False).encode("utf-8"), request_headers
    request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    return url, params.encode("utf-8"), request_headers


def _looks_like_json(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith("{") or stripped.startswith("[")


def _params_to_dict(params: str) -> dict[str, str]:
    if _looks_like_json(params):
        data = json.loads(params)
        if isinstance(data, dict):
            return {str(key): str(value) for key, value in data.items()}
        return {}
    result: dict[str, str] = {}
    for part in params.split("&"):
        if not part:
            continue
        key, _, value = part.partition("=")
        result[key] = value
    return result


def _append_query(url: str, params: str) -> str:
    query = parse.urlencode(_params_to_dict(params))
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{query}" if query else url


def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def _extract_variables(body: bytes, extractors: dict[str, str]) -> dict[str, str]:
    if not extractors:
        return {}
    data = _json_body(body)
    extracted = {}
    missing = []
    for variable_name, path in extractors.items():
        value = _lookup_path(data, path)
        if value in (None, ""):
            missing.append(f"{variable_name}={path}")
            continue
        extracted[variable_name] = str(value)
    if missing:
        raise ValueError(f"前置请求未提取到变量：{', '.join(missing)}")
    return extracted


def _json_body(body: bytes):
    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        return {}


def _lookup_path(data, path: str):
    value = data
    normalized = path.strip()
    if normalized.startswith("$."):
        normalized = normalized[2:]
    for key in normalized.split("."):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except Exception:
                return None
        if isinstance(value, dict):
            value = value.get(key)
        elif isinstance(value, list) and key.isdigit():
            value = value[int(key)]
        else:
            return None
    return value
