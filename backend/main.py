from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.routes import admin, analysis, health, pages, report
from backend.config import ALLOWED_ORIGINS, STATIC_DIR
from backend.services.fenbi_client import start_silent_refresh_loop


def create_app() -> FastAPI:
    app = FastAPI(title="Fenbi Report Server")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["GET", "POST", "HEAD", "OPTIONS"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(pages.router)
    app.include_router(health.router)
    app.include_router(report.router)
    app.include_router(admin.router)
    app.include_router(analysis.router)

    @app.on_event("startup")
    def startup() -> None:
        start_silent_refresh_loop()

    return app


app = create_app()
