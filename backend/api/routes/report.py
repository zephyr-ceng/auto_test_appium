from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.api.errors import api_error
from backend.api.rate_limit import check_manual_refresh_limit
from backend.api.security import assert_trusted_browser_request
from backend.services.fenbi_client import FenbiError, fetch_report, refresh_report

router = APIRouter(prefix="/api", tags=["report"])


@router.get("/report", response_model=None)
def report(request: Request) -> dict[str, Any] | JSONResponse:
    assert_trusted_browser_request(request)
    try:
        return {"ok": True, "data": fetch_report()}
    except FenbiError as exc:
        return api_error(exc)


@router.post("/report/refresh", response_model=None)
def refresh(request: Request) -> dict[str, Any] | JSONResponse:
    assert_trusted_browser_request(request)
    try:
        check_manual_refresh_limit(request)
        return {"ok": True, "data": refresh_report(reason="manual")}
    except FenbiError as exc:
        return api_error(exc)
