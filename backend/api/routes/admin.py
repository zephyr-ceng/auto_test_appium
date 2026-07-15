from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.api.errors import api_error
from backend.api.schemas import CookieUpdateRequest
from backend.api.security import assert_trusted_browser_request
from backend.services.fenbi_client import FenbiError, read_cookie, validate_cookie, write_cookie

router = APIRouter(prefix="/api", tags=["admin"])


@router.get("/admin/cookie")
def get_cookie_status(request: Request) -> dict[str, Any]:
    assert_trusted_browser_request(request)
    cookie, source = read_cookie()
    return {
        "ok": True,
        "cookie": {
            "configured": bool(cookie),
            "source": source,
            "runtime_storage": "file",
        },
    }


@router.post("/admin/cookie", response_model=None)
def update_cookie(payload: CookieUpdateRequest, request: Request) -> dict[str, Any] | JSONResponse:
    assert_trusted_browser_request(request)
    try:
        validation = validate_cookie(payload.cookie)
        write_cookie(payload.cookie)
        return {
            "ok": True,
            "message": "Cookie 已验证并写入本地文件。",
            "storage": "file",
            "warning": "Cookie 保存到 data/fenbi_cookie.txt，请勿提交该文件。",
            "validation": validation,
        }
    except FenbiError as exc:
        return api_error(exc)
