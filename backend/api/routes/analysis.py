from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.api.security import assert_trusted_browser_request
from backend.services.ai_analysis import stream_report_analysis
from backend.services.fenbi_client import FenbiError, fetch_report

router = APIRouter(prefix="/api", tags=["analysis"])


@router.get("/analysis/stream")
async def analysis_stream(request: Request) -> StreamingResponse:
    assert_trusted_browser_request(request)
    try:
        report_data = fetch_report()
    except FenbiError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": str(exc), "details": exc.details}) from exc
    return StreamingResponse(stream_report_analysis(report_data), media_type="text/event-stream")
