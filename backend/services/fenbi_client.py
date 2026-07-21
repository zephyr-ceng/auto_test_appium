import json
import random
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from backend.config import (
    COOKIE_FILE,
    ERROR_KEYPOINT_TREE_FILE,
    EXERCISE_HISTORY_FILE,
    FENBI_COOKIE,
    FENBI_TIMEOUT_SECONDS,
    FIXTURE_ERROR_KEYPOINT_TREE_FILE,
    FIXTURE_EXERCISE_HISTORY_FILE,
    FIXTURE_USER_ANALYSIS_FILE,
    REPORT_CACHE_FILE,
    REPORT_CACHE_TTL_SECONDS,
    SILENT_REFRESH_JITTER_MAX_SECONDS,
    SILENT_REFRESH_JITTER_MIN_SECONDS,
    STATUS_FILE,
    UPSTREAM_REQUEST_DELAY_MAX_SECONDS,
    UPSTREAM_REQUEST_DELAY_MIN_SECONDS,
    USER_ANALYSIS_FILE,
)


COMMON_QUERY = {
    "app": "web",
    "kav": "128",
    "av": "128",
    "hav": "128",
    "version": "3.0.0.0",
    "deviceId": "",
    "gav": "2",
    "apcId": "0",
}


class FenbiError(Exception):
    def __init__(self, message: str, status_code: int = 502, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


@dataclass
class UpstreamResponse:
    name: str
    status_code: int
    content_type: str
    data: Any


_cache_lock = threading.RLock()
_thread_lock = threading.RLock()
_refresh_lock = threading.Lock()
_refresh_thread: threading.Thread | None = None
_next_silent_refresh_at = 0.0
_silent_loop_started = False
_silent_loop_check_interval_seconds = 30.0


def now_iso(epoch: float | None = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch or time.time()))


def read_json(path: Path) -> Any:
    with _cache_lock:
        return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    with _cache_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(f"{path.suffix}.tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)


def read_first_json(*paths: Path) -> Any:
    last_missing: FileNotFoundError | None = None
    for path in paths:
        try:
            return read_json(path)
        except FileNotFoundError as exc:
            last_missing = exc
    if last_missing:
        raise last_missing
    raise FileNotFoundError("No JSON paths provided.")


def read_cookie() -> tuple[str | None, str]:
    if COOKIE_FILE.exists():
        cookie = COOKIE_FILE.read_text(encoding="utf-8").strip()
        if cookie:
            return cookie, "file"
    if FENBI_COOKIE:
        return FENBI_COOKIE, "env"
    return None, "missing"


def write_cookie(cookie: str) -> None:
    normalized = cookie.strip()
    if len(normalized) < 20:
        raise FenbiError("Cookie 不能为空或过短。", 400)
    with _cache_lock:
        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        COOKIE_FILE.write_text(normalized, encoding="utf-8")
    clear_cache()


def clear_cache() -> None:
    with _cache_lock:
        for path in (REPORT_CACHE_FILE, STATUS_FILE):
            path.unlink(missing_ok=True)


def read_status() -> dict[str, Any]:
    if STATUS_FILE.exists():
        try:
            return read_json(STATUS_FILE)
        except json.JSONDecodeError:
            pass
    return {
        "ok": False,
        "last_fetch_at": None,
        "last_success_at": None,
        "last_error": None,
    }


def write_status(payload: dict[str, Any]) -> None:
    write_json(STATUS_FILE, payload)


def read_cached_report(max_age_seconds: int = REPORT_CACHE_TTL_SECONDS) -> dict[str, Any] | None:
    if not REPORT_CACHE_FILE.exists():
        return None
    try:
        cached = read_json(REPORT_CACHE_FILE)
    except json.JSONDecodeError:
        return None
    fetched_at = cached.get("meta", {}).get("fetched_at_epoch", 0)
    if time.time() - fetched_at > max_age_seconds:
        return None
    return cached


def read_any_cached_report() -> dict[str, Any] | None:
    if not REPORT_CACHE_FILE.exists():
        return None
    try:
        return read_json(REPORT_CACHE_FILE)
    except json.JSONDecodeError:
        return None


def write_cached_report(report: dict[str, Any]) -> None:
    write_json(REPORT_CACHE_FILE, report)


def write_live_data(raw: dict[str, Any]) -> None:
    write_json(EXERCISE_HISTORY_FILE, raw["history"])
    write_json(USER_ANALYSIS_FILE, raw["analysis"])
    write_json(ERROR_KEYPOINT_TREE_FILE, raw["errors"])


def browser_headers(cookie: str, referer: str) -> dict[str, str]:
    return {
        "Cookie": cookie,
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-US;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Referer": referer,
        "Origin": "https://www.fenbi.com",
        "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "X-Requested-With": "XMLHttpRequest",
    }


def build_url(base: str, params: dict[str, Any]) -> str:
    return f"{base}?{urlencode(params)}"


def upstream_specs() -> list[dict[str, str]]:
    no_cache = int(time.time())
    return [
        {
            "name": "history",
            "url": build_url(
                "https://tiku.fenbi.com/combine/exercise/getExerciseBriefHistory",
                {
                    "noCacheTag": no_cache,
                    "categoryId": 3,
                    "limit": 15,
                    "cursor": "",
                    "routecs": "xingce",
                    **COMMON_QUERY,
                },
            ),
            "referer": "https://www.fenbi.com/spa/tiku/report/profile/xingce/xingce/history",
        },
        {
            "name": "analysis",
            "url": build_url(
                "https://ke.fenbi.com/api/v3/user/analysis",
                {
                    "tiku_prefix": "xingce",
                    "web_cache": 0,
                    **COMMON_QUERY,
                },
            ),
            "referer": "https://www.fenbi.com/spa/tiku/report/profile/xingce/xingce/summary",
        },
        {
            "name": "errors",
            "url": build_url(
                "https://tiku.fenbi.com/api/xingce/errors/keypoint-tree",
                {
                    "timeRange": 0,
                    "order": "desc",
                    **COMMON_QUERY,
                },
            ),
            "referer": "https://www.fenbi.com/spa/tiku/report/profile/xingce/xingce/tree/2",
        },
    ]


def request_upstream(spec: dict[str, str], cookie: str) -> UpstreamResponse:
    try:
        response = requests.get(
            spec["url"],
            headers=browser_headers(cookie, spec["referer"]),
            timeout=FENBI_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise FenbiError(f"{spec['name']} 请求失败。", 502, {"upstream": spec["name"], "error": str(exc)}) from exc

    content_type = response.headers.get("Content-Type", "")
    try:
        data = response.json()
    except ValueError as exc:
        raise FenbiError(
            f"{spec['name']} 返回的不是 JSON。",
            502,
            {
                "upstream": spec["name"],
                "status_code": response.status_code,
                "content_type": content_type,
                "preview": response.text[:200],
            },
        ) from exc

    if response.status_code != 200:
        raise FenbiError(
            f"{spec['name']} 上游返回 {response.status_code}。",
            502,
            {
                "upstream": spec["name"],
                "status_code": response.status_code,
                "content_type": content_type,
                "body": data,
            },
        )

    return UpstreamResponse(spec["name"], response.status_code, content_type, data)


def fetch_upstreams(cookie: str) -> list[UpstreamResponse]:
    responses = []
    specs = upstream_specs()
    for index, spec in enumerate(specs):
        if index:
            time.sleep(random.uniform(UPSTREAM_REQUEST_DELAY_MIN_SECONDS, UPSTREAM_REQUEST_DELAY_MAX_SECONDS))
        responses.append(request_upstream(spec, cookie))
    return responses


def validate_cookie(cookie: str) -> dict[str, Any]:
    normalized = cookie.strip()
    if len(normalized) < 20:
        raise FenbiError("Cookie 不能为空或过短。", 400)
    responses = fetch_upstreams(normalized)
    return {
        "ok": True,
        "upstreams": {
            response.name: {
                "status_code": response.status_code,
                "content_type": response.content_type,
            }
            for response in responses
        },
    }


def cache_age_seconds(report: dict[str, Any] | None) -> float | None:
    if not report:
        return None
    fetched_at = report.get("meta", {}).get("fetched_at_epoch", 0)
    if not fetched_at:
        return None
    return max(0.0, time.time() - float(fetched_at))


def refresh_jitter_seconds() -> float:
    if SILENT_REFRESH_JITTER_MAX_SECONDS <= SILENT_REFRESH_JITTER_MIN_SECONDS:
        return float(max(0, SILENT_REFRESH_JITTER_MIN_SECONDS))
    return random.uniform(SILENT_REFRESH_JITTER_MIN_SECONDS, SILENT_REFRESH_JITTER_MAX_SECONDS)


def schedule_next_silent_refresh(base_epoch: float | None = None, only_if_due_since: float | None = None) -> float:
    global _next_silent_refresh_at
    with _thread_lock:
        if only_if_due_since is not None and _next_silent_refresh_at > only_if_due_since:
            return _next_silent_refresh_at
        _next_silent_refresh_at = (base_epoch or time.time()) + REPORT_CACHE_TTL_SECONDS + refresh_jitter_seconds()
        return _next_silent_refresh_at


def next_silent_refresh_at() -> float:
    with _thread_lock:
        return _next_silent_refresh_at


def next_silent_refresh_meta() -> dict[str, Any]:
    next_at = next_silent_refresh_at()
    if next_at <= 0:
        return {"next_silent_refresh_at": None, "next_silent_refresh_at_epoch": None}
    return {
        "next_silent_refresh_at": now_iso(next_at),
        "next_silent_refresh_at_epoch": next_at,
    }


def start_silent_refresh_loop() -> bool:
    global _silent_loop_started
    with _thread_lock:
        if _silent_loop_started:
            return False
        _silent_loop_started = True
        if _next_silent_refresh_at <= 0:
            schedule_next_silent_refresh()
    thread = threading.Thread(target=_silent_refresh_loop, daemon=True)
    thread.start()
    return True


def _silent_refresh_loop() -> None:
    while True:
        next_at = next_silent_refresh_at()
        if next_at <= 0:
            next_at = schedule_next_silent_refresh()
        wait_seconds = next_at - time.time()
        if wait_seconds > 0:
            time.sleep(min(wait_seconds, _silent_loop_check_interval_seconds))
            continue

        started_at = time.time()
        try:
            refresh_report(reason="silent-loop")
        except FenbiError:
            pass
        finally:
            schedule_next_silent_refresh(started_at, only_if_due_since=started_at)


def schedule_refresh(reason: str = "silent") -> bool:
    global _refresh_thread
    with _thread_lock:
        if _refresh_thread and _refresh_thread.is_alive():
            return False
        _refresh_thread = threading.Thread(target=_refresh_worker, args=(reason,), daemon=True)
        _refresh_thread.start()
        return True


def _refresh_worker(reason: str) -> None:
    try:
        refresh_report(reason=reason)
    finally:
        global _refresh_thread
        with _thread_lock:
            _refresh_thread = None


def fetch_report() -> dict[str, Any]:
    cookie, source = read_cookie()
    if not cookie:
        return load_local_report("missing-cookie")

    cached = read_any_cached_report()
    if cached:
        cached["meta"]["cache_hit"] = True
        cached["meta"]["cookie_source"] = source
        cached["meta"].update(next_silent_refresh_meta())
        return cached

    schedule_refresh("cold-start")
    local = load_local_report("warming-cache")
    local["meta"]["refresh_scheduled"] = True
    local["meta"]["cookie_source"] = source
    local["meta"].update(next_silent_refresh_meta())
    return local


def refresh_report(reason: str = "manual") -> dict[str, Any]:
    started_at = time.time()
    if reason == "manual":
        schedule_next_silent_refresh(started_at)

    if not _refresh_lock.acquire(blocking=False):
        stale = read_any_cached_report()
        if stale:
            stale["meta"]["cache_hit"] = True
            stale["meta"]["refresh_in_progress"] = True
            stale["meta"].update(next_silent_refresh_meta())
            return stale
        raise FenbiError("刷新正在进行，请稍后再试。", 409)

    try:
        return _refresh_report_locked(reason, started_at)
    finally:
        _refresh_lock.release()


def _refresh_report_locked(reason: str, started_at: float) -> dict[str, Any]:
    cookie, source = read_cookie()
    if not cookie:
        raise FenbiError("尚未配置 Cookie。", 400)

    status = read_status()
    status.update(
        {
            "last_fetch_at": now_iso(started_at),
            "ok": False,
            "refresh_reason": reason,
            **next_silent_refresh_meta(),
        }
    )
    write_status(status)

    try:
        responses = fetch_upstreams(cookie)
        raw = {response.name: response.data for response in responses}
        report = normalize_report(raw, source)
        write_live_data(raw)
    except FenbiError as exc:
        status.update({"ok": False, "last_error": {"message": str(exc), "details": exc.details}})
        write_status(status)

        stale = read_any_cached_report()
        if stale:
            stale["meta"]["stale"] = True
            stale["meta"]["cache_hit"] = True
            stale["meta"]["cookie_source"] = source
            stale["meta"].update(next_silent_refresh_meta())
            stale["meta"]["last_error"] = {"message": str(exc), "details": exc.details}
            return stale

        local = load_local_report("upstream-error")
        local["meta"].update(next_silent_refresh_meta())
        local["meta"]["last_error"] = {"message": str(exc), "details": exc.details}
        return local

    report["meta"].update(next_silent_refresh_meta())
    write_cached_report(report)
    status.update(
        {
            "ok": True,
            "last_success_at": report["meta"]["fetched_at"],
            "last_error": None,
            **next_silent_refresh_meta(),
        }
    )
    write_status(status)
    return report


def load_local_report(reason: str = "local-cache") -> dict[str, Any]:
    raw = {
        "history": read_first_json(EXERCISE_HISTORY_FILE, FIXTURE_EXERCISE_HISTORY_FILE),
        "analysis": read_first_json(USER_ANALYSIS_FILE, FIXTURE_USER_ANALYSIS_FILE),
        "errors": read_first_json(ERROR_KEYPOINT_TREE_FILE, FIXTURE_ERROR_KEYPOINT_TREE_FILE),
    }
    report = normalize_report(raw, "local")
    report["meta"]["stale"] = True
    report["meta"]["cache_hit"] = True
    report["meta"]["fallback_reason"] = reason
    return report


def normalize_report(raw: dict[str, Any], cookie_source: str) -> dict[str, Any]:
    history_data = raw["history"]
    analysis_data = raw["analysis"]
    error_tree = raw["errors"]

    if history_data.get("code") != 1:
        raise FenbiError("练习历史业务状态异常。", 502, {"body": history_data})
    if analysis_data.get("code") != 1:
        raise FenbiError("用户报告业务状态异常。", 502, {"body": analysis_data})
    if not isinstance(error_tree, list):
        raise FenbiError("错题树返回结构异常。", 502, {"body": error_tree})

    tiku_report = analysis_data["data"]["tikuReport"]
    answer_count = as_number(tiku_report.get("answerCount"))
    correct_count = as_number(tiku_report.get("correctCount"))
    score_rank_index = as_number(tiku_report.get("scoreRankIndex"))
    answer_rank_index = as_number(tiku_report.get("answerCountRankIndex"))
    total_user_count = as_number(tiku_report.get("totalUserCount"))
    accuracy = correct_count / answer_count * 100 if answer_count else 0
    score_rank_percent = (1 - score_rank_index / total_user_count) * 100 if total_user_count else 0
    answer_rank_percent = (1 - answer_rank_index / total_user_count) * 100 if total_user_count else 0
    fetched_epoch = time.time()

    return {
        "summary": {
            "userId": tiku_report.get("userId"),
            "quiz": tiku_report.get("userQuiz") or {},
            "answerCount": answer_count,
            "exerciseCount": as_number(tiku_report.get("exerciseCount")),
            "correctCount": correct_count,
            "accuracy": accuracy,
            "forecastScore": as_number(tiku_report.get("forecastScore")),
            "avgForecastScore": as_number(tiku_report.get("avgForecastScore")),
            "maxForecastScore": as_number(tiku_report.get("maxForecastScore")),
            "exerciseDay": as_number(tiku_report.get("exerciseDay")),
            "totalUserCount": total_user_count,
            "scoreRankIndex": score_rank_index,
            "scoreRankPercent": score_rank_percent,
            "answerCountRankIndex": answer_rank_index,
            "answerRankPercent": answer_rank_percent,
            "maxAnswerCount": as_number(tiku_report.get("maxAnswerCount")),
            "fullMark": as_number(tiku_report.get("fullMark")),
        },
        "trends": tiku_report.get("trends", []),
        "keypoints": tiku_report.get("keypoints", []),
        "history": {
            "cursor": history_data["data"].get("cursor"),
            "items": history_data["data"].get("historyItems", []),
        },
        "errors": error_tree,
        "meta": {
            "fetched_at": now_iso(fetched_epoch),
            "fetched_at_epoch": fetched_epoch,
            "cookie_source": cookie_source,
            "cache_hit": False,
            "stale": False,
            "upstream_status": {
                "history": 200,
                "analysis": 200,
                "errors": 200,
            },
        },
    }


def as_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
