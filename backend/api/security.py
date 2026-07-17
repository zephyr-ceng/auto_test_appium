from urllib.parse import urlparse

from fastapi import HTTPException, Request

from backend.config import ALLOWED_ORIGINS


def assert_trusted_browser_request(request: Request) -> None:
    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site == "cross-site":
        raise HTTPException(status_code=403, detail="不允许的跨站请求。")

    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    if origin and not is_allowed_origin(origin, request):
        raise HTTPException(status_code=403, detail="不允许的请求来源。")
    if not origin and referer and not is_allowed_referer(referer, request):
        raise HTTPException(status_code=403, detail="不允许的请求来源。")


def is_allowed_origin(origin: str, request: Request | None = None) -> bool:
    if origin in ALLOWED_ORIGINS:
        return True
    return is_current_host(origin, request)


def is_allowed_referer(referer: str, request: Request | None = None) -> bool:
    parsed = urlparse(referer)
    if not parsed.scheme or not parsed.netloc:
        return False
    return is_allowed_origin(f"{parsed.scheme}://{parsed.netloc}", request)


def is_current_host(origin: str, request: Request | None) -> bool:
    if not request or not getattr(request.app.state, "trust_current_host", False):
        return False
    parsed = urlparse(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    return parsed.netloc == request.url.netloc
