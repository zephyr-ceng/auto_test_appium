import json
import os
import time
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests


CACHE_TTL_SECONDS = int(os.environ.get("REPORT_CACHE_TTL_SECONDS", "600"))
COOKIE_ENV_NAME = "FENBI_COOKIE"
COOKIE_FILE = Path(os.environ.get("FENBI_COOKIE_FILE", "/tmp/fenbi_cookie.txt"))
CACHE_FILE = Path(os.environ.get("FENBI_CACHE_FILE", "/tmp/fenbi_report_cache.json"))
STATUS_FILE = Path(os.environ.get("FENBI_STATUS_FILE", "/tmp/fenbi_status.json"))
TIMEOUT_SECONDS = int(os.environ.get("FENBI_TIMEOUT_SECONDS", "20"))

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
    def __init__(self, message: str, status_code: int = HTTPStatus.BAD_GATEWAY, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


@dataclass
class UpstreamResponse:
    name: str
    status_code: int
    content_type: str
    data: Any


def json_response(handler: Any, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_request_json(handler: Any) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or "0")
    if length <= 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FenbiError("请求体不是合法 JSON", HTTPStatus.BAD_REQUEST, {"error": str(exc)}) from exc
    if not isinstance(value, dict):
        raise FenbiError("请求体必须是 JSON 对象", HTTPStatus.BAD_REQUEST)
    return value


def read_cookie() -> tuple[str | None, str]:
    file_cookie = None
    try:
        if COOKIE_FILE.exists():
            file_cookie = COOKIE_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        file_cookie = None

    if file_cookie:
        return file_cookie, "runtime"

    env_cookie = os.environ.get(COOKIE_ENV_NAME, "").strip()
    if env_cookie:
        return env_cookie, "env"

    return None, "missing"


def write_runtime_cookie(cookie: str) -> None:
    COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
    COOKIE_FILE.write_text(cookie.strip(), encoding="utf-8")
    clear_cache()


def clear_cache() -> None:
    for path in (CACHE_FILE, STATUS_FILE):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def read_status() -> dict[str, Any]:
    try:
        if STATUS_FILE.exists():
            return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    return {
        "ok": False,
        "last_fetch_at": None,
        "last_success_at": None,
        "last_error": None,
    }


def write_status(status: dict[str, Any]) -> None:
    try:
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def read_cached_report(max_age_seconds: int = CACHE_TTL_SECONDS) -> dict[str, Any] | None:
    try:
        if not CACHE_FILE.exists():
            return None
        cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        fetched_at = cached.get("meta", {}).get("fetched_at_epoch", 0)
        if time.time() - fetched_at > max_age_seconds:
            return None
        return cached
    except (OSError, json.JSONDecodeError):
        return None


def read_any_cached_report() -> dict[str, Any] | None:
    try:
        if CACHE_FILE.exists():
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    return None


def write_cached_report(report: dict[str, Any]) -> None:
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def browser_headers(cookie: str, referer: str) -> dict[str, str]:
    return {
        "Cookie": cookie,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Referer": referer,
        "Origin": "https://www.fenbi.com",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
    }


def url(base: str, params: dict[str, Any]) -> str:
    return f"{base}?{urlencode(params)}"


def upstream_specs() -> list[dict[str, Any]]:
    no_cache = int(time.time())
    return [
        {
            "name": "history",
            "url": url(
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
            "url": url(
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
            "url": url(
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


def request_upstream(spec: dict[str, Any], cookie: str) -> UpstreamResponse:
    try:
        response = requests.get(
            spec["url"],
            headers=browser_headers(cookie, spec["referer"]),
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise FenbiError(
            f"{spec['name']} 请求失败",
            HTTPStatus.BAD_GATEWAY,
            {"upstream": spec["name"], "error": str(exc)},
        ) from exc

    content_type = response.headers.get("Content-Type", "")
    try:
        data = response.json()
    except ValueError as exc:
        raise FenbiError(
            f"{spec['name']} 返回非 JSON",
            HTTPStatus.BAD_GATEWAY,
            {
                "upstream": spec["name"],
                "status_code": response.status_code,
                "content_type": content_type,
                "preview": response.text[:200],
            },
        ) from exc

    if response.status_code != 200:
        raise FenbiError(
            f"{spec['name']} 上游返回 {response.status_code}",
            HTTPStatus.BAD_GATEWAY,
            {
                "upstream": spec["name"],
                "status_code": response.status_code,
                "content_type": content_type,
                "body": data,
            },
        )

    return UpstreamResponse(spec["name"], response.status_code, content_type, data)


def validate_cookie(cookie: str) -> dict[str, Any]:
    if not cookie or len(cookie.strip()) < 20:
        raise FenbiError("Cookie 不能为空或过短", HTTPStatus.BAD_REQUEST)
    responses = fetch_upstreams(cookie)
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


def fetch_upstreams(cookie: str) -> list[UpstreamResponse]:
    return [request_upstream(spec, cookie) for spec in upstream_specs()]


def fetch_report(force: bool = False) -> dict[str, Any]:
    cookie, source = read_cookie()
    if not cookie:
        raise FenbiError("未配置 Cookie，请设置 FENBI_COOKIE 或通过管理员页面更新", HTTPStatus.UNAUTHORIZED)

    if not force:
        cached = read_cached_report()
        if cached:
            cached["meta"]["cache_hit"] = True
            cached["meta"]["cookie_source"] = source
            return cached

    status = read_status()
    status.update({"last_fetch_at": now_iso(), "ok": False})
    write_status(status)

    try:
        responses = fetch_upstreams(cookie)
        raw = {response.name: response.data for response in responses}
        report = normalize_report(raw, source)
    except FenbiError as exc:
        stale = read_any_cached_report()
        status.update({"ok": False, "last_error": {"message": str(exc), "details": exc.details}})
        write_status(status)
        if stale:
            stale["meta"]["stale"] = True
            stale["meta"]["cache_hit"] = True
            stale["meta"]["cookie_source"] = source
            stale["meta"]["last_error"] = {"message": str(exc), "details": exc.details}
            return stale
        raise

    write_cached_report(report)
    status.update({"ok": True, "last_success_at": report["meta"]["fetched_at"], "last_error": None})
    write_status(status)
    return report


def normalize_report(raw: dict[str, Any], cookie_source: str) -> dict[str, Any]:
    history_data = raw["history"]
    analysis_data = raw["analysis"]
    error_tree = raw["errors"]

    if history_data.get("code") != 1:
        raise FenbiError("练习历史业务状态异常", HTTPStatus.BAD_GATEWAY, {"body": history_data})
    if analysis_data.get("code") != 1:
        raise FenbiError("用户报告业务状态异常", HTTPStatus.BAD_GATEWAY, {"body": analysis_data})
    if not isinstance(error_tree, list):
        raise FenbiError("错题树返回结构异常", HTTPStatus.BAD_GATEWAY, {"body": error_tree})

    tiku_report = analysis_data["data"]["tikuReport"]
    answer_count = number(tiku_report.get("answerCount"))
    correct_count = number(tiku_report.get("correctCount"))
    score_rank_index = number(tiku_report.get("scoreRankIndex"))
    answer_rank_index = number(tiku_report.get("answerCountRankIndex"))
    total_user_count = number(tiku_report.get("totalUserCount"))
    accuracy = correct_count / answer_count * 100 if answer_count else 0
    score_rank_percent = (1 - score_rank_index / total_user_count) * 100 if total_user_count else 0
    answer_rank_percent = (1 - answer_rank_index / total_user_count) * 100 if total_user_count else 0
    history_items = history_data["data"].get("historyItems", [])

    fetched_epoch = time.time()
    return {
        "summary": {
            "userId": tiku_report.get("userId"),
            "quiz": tiku_report.get("userQuiz") or {},
            "answerCount": answer_count,
            "exerciseCount": number(tiku_report.get("exerciseCount")),
            "correctCount": correct_count,
            "accuracy": accuracy,
            "forecastScore": number(tiku_report.get("forecastScore")),
            "avgForecastScore": number(tiku_report.get("avgForecastScore")),
            "maxForecastScore": number(tiku_report.get("maxForecastScore")),
            "exerciseDay": number(tiku_report.get("exerciseDay")),
            "totalUserCount": total_user_count,
            "scoreRankIndex": score_rank_index,
            "scoreRankPercent": score_rank_percent,
            "answerCountRankIndex": answer_rank_index,
            "answerRankPercent": answer_rank_percent,
            "fullMark": number(tiku_report.get("fullMark")),
        },
        "trends": tiku_report.get("trends", []),
        "keypoints": tiku_report.get("keypoints", []),
        "history": {
            "cursor": history_data["data"].get("cursor"),
            "items": history_items,
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


def number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def now_iso(epoch: float | None = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch or time.time()))

