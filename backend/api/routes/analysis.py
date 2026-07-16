from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.api.security import assert_trusted_browser_request
from backend.services.ai_analysis import available_ai_providers, stream_report_analysis
from backend.services.fenbi_client import FenbiError, fetch_report

router = APIRouter(prefix="/api", tags=["analysis"])


@router.get("/analysis/stream")
async def analysis_stream(request: Request, provider: str = "openai") -> StreamingResponse:
    assert_trusted_browser_request(request)
    try:
        report_data = fetch_report()
    except FenbiError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": str(exc), "details": exc.details}) from exc
    return StreamingResponse(stream_report_analysis(report_data, provider), media_type="text/event-stream")


@router.get("/analysis/providers")
def analysis_providers(request: Request) -> dict[str, object]:
    assert_trusted_browser_request(request)
    return {"ok": True, "providers": available_ai_providers()}
