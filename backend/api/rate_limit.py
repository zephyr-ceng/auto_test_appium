import time

from fastapi import Request

from backend.config import MANUAL_REFRESH_LIMIT_PER_HOUR, RATE_LIMIT_FILE
from backend.services.fenbi_client import FenbiError, read_json, write_json


def check_manual_refresh_limit(request: Request) -> None:
    now = time.time()
    window_start = now - 3600
    key = request.client.host if request.client else "local"
    try:
        payload = read_json(RATE_LIMIT_FILE)
    except (FileNotFoundError, ValueError):
        payload = {}

    records = []
    for item in payload.get(key, []):
        try:
            timestamp = float(item)
        except (TypeError, ValueError):
            continue
        if timestamp >= window_start:
            records.append(timestamp)
    if len(records) >= MANUAL_REFRESH_LIMIT_PER_HOUR:
        retry_after = max(1, int(3600 - (now - records[0])))
        raise FenbiError("手动刷新过于频繁，请稍后再试。", 429, {"retry_after_seconds": retry_after})

    records.append(now)
    payload[key] = records
    write_json(RATE_LIMIT_FILE, payload)
