from urllib.parse import urlparse

from fastapi import HTTPException, Request

from backend.config import ALLOWED_ORIGINS


def assert_trusted_browser_request(request: Request) -> None:
    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site == "cross-site":
        raise HTTPException(status_code=403, detail="不允许的跨站请求。")

    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    if origin and origin not in ALLOWED_ORIGINS:
        raise HTTPException(status_code=403, detail="不允许的请求来源。")
    if not origin and referer and not is_allowed_referer(referer):
        raise HTTPException(status_code=403, detail="不允许的请求来源。")


def is_allowed_referer(referer: str) -> bool:
    parsed = urlparse(referer)
    if not parsed.scheme or not parsed.netloc:
        return False
    return f"{parsed.scheme}://{parsed.netloc}" in ALLOWED_ORIGINS
