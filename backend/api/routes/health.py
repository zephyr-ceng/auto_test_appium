from typing import Any

from fastapi import APIRouter, Request

from backend.api.security import assert_trusted_browser_request
from backend.services.fenbi_client import read_cookie, read_status

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    assert_trusted_browser_request(request)
    cookie, source = read_cookie()
    return {
        "ok": True,
        "cookie": {
            "configured": bool(cookie),
            "source": source,
        },
        "status": read_status(),
    }
