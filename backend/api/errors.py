from fastapi.responses import JSONResponse

from backend.services.fenbi_client import FenbiError


def api_error(exc: FenbiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "error": {
                "message": str(exc),
                "details": exc.details,
            },
        },
    )
