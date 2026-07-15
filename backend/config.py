import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = Path(os.getenv("FENBI_DATA_DIR", PROJECT_ROOT / "data"))
FRONTEND_DIR = Path(os.getenv("FENBI_FRONTEND_DIR", PROJECT_ROOT / "frontend"))
PAGES_DIR = Path(os.getenv("FENBI_PAGES_DIR", FRONTEND_DIR / "pages"))
STATIC_DIR = Path(os.getenv("FENBI_STATIC_DIR", FRONTEND_DIR / "assets"))

EXERCISE_HISTORY_FILE = DATA_DIR / "live_exercise_history.json"
USER_ANALYSIS_FILE = DATA_DIR / "live_user_analysis.json"
ERROR_KEYPOINT_TREE_FILE = DATA_DIR / "live_error_keypoint_tree.json"
REPORT_CACHE_FILE = DATA_DIR / "report_cache.json"
STATUS_FILE = DATA_DIR / "status.json"
COOKIE_FILE = DATA_DIR / "fenbi_cookie.txt"
RATE_LIMIT_FILE = DATA_DIR / "rate_limit.json"

FENBI_COOKIE = os.getenv("FENBI_COOKIE", "").strip()
REPORT_CACHE_TTL_SECONDS = int(os.getenv("REPORT_CACHE_TTL_SECONDS", "14400"))
FENBI_TIMEOUT_SECONDS = int(os.getenv("FENBI_TIMEOUT_SECONDS", "20"))
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",")
    if origin.strip()
]
SILENT_REFRESH_JITTER_MIN_SECONDS = int(os.getenv("SILENT_REFRESH_JITTER_MIN_SECONDS", "60"))
SILENT_REFRESH_JITTER_MAX_SECONDS = int(os.getenv("SILENT_REFRESH_JITTER_MAX_SECONDS", "600"))
UPSTREAM_REQUEST_DELAY_MIN_SECONDS = float(os.getenv("UPSTREAM_REQUEST_DELAY_MIN_SECONDS", "1.2"))
UPSTREAM_REQUEST_DELAY_MAX_SECONDS = float(os.getenv("UPSTREAM_REQUEST_DELAY_MAX_SECONDS", "3.5"))
MANUAL_REFRESH_LIMIT_PER_HOUR = int(os.getenv("MANUAL_REFRESH_LIMIT_PER_HOUR", "3"))

AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
AI_MODEL = os.getenv("AI_MODEL", "gpt-4.1-mini")
