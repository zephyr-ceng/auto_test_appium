from fastapi import APIRouter
from fastapi.responses import FileResponse

from backend.config import PAGES_DIR

router = APIRouter(tags=["pages"])


@router.get("/")
def index() -> FileResponse:
    return FileResponse(PAGES_DIR / "report.html")


@router.head("/")
def index_head() -> FileResponse:
    return FileResponse(PAGES_DIR / "report.html")


@router.get("/report.html")
def report_page() -> FileResponse:
    return FileResponse(PAGES_DIR / "report.html")


@router.head("/report.html")
def report_page_head() -> FileResponse:
    return FileResponse(PAGES_DIR / "report.html")


@router.get("/admin.html")
def admin_page() -> FileResponse:
    return FileResponse(PAGES_DIR / "admin.html")


@router.head("/admin.html")
def admin_page_head() -> FileResponse:
    return FileResponse(PAGES_DIR / "admin.html")
