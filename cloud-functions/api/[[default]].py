from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


FUNCTION_FILE = Path(__file__).resolve()
PROJECT_ROOT = FUNCTION_FILE.parents[2]
RUNTIME_DATA_DIR = Path(os.getenv("FENBI_DATA_DIR", "/tmp/auto_test_appium_data"))
SOURCE_DATA_DIR = PROJECT_ROOT / "data"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("FENBI_DATA_DIR", str(RUNTIME_DATA_DIR))
os.environ.setdefault("FENBI_FRONTEND_DIR", str(PROJECT_ROOT / "frontend"))
os.environ.setdefault("TRUST_CURRENT_HOST", "1")


def seed_runtime_data() -> None:
    RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for source in SOURCE_DATA_DIR.glob("live_*.json"):
        target = RUNTIME_DATA_DIR / source.name
        if not target.exists():
            shutil.copy2(source, target)


seed_runtime_data()

from backend.main import app  # noqa: E402


@app.middleware("http")
async def restore_api_prefix_for_edgeone(request, call_next):
    path = request.scope.get("path", "")
    if not path.startswith("/api"):
        request.scope["path"] = f"/api{path if path.startswith('/') else f'/{path}'}"
    return await call_next(request)
