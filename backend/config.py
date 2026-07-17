import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


def load_local_env() -> None:
    env_file = PROJECT_ROOT / ".env.local"
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and name not in os.environ:
            os.environ[name] = value


load_local_env()

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
AI_DEFAULT_PROVIDER = os.getenv("AI_DEFAULT_PROVIDER", "relay").strip() or "relay"
AI_RELAY_DISABLE_RESPONSE_STORAGE = os.getenv("AI_RELAY_DISABLE_RESPONSE_STORAGE", "true").lower() in {"1", "true", "yes", "on"}

AI_PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "base_url": os.getenv("OPENAI_BASE_URL", AI_BASE_URL).rstrip("/"),
        "model": os.getenv("OPENAI_MODEL", AI_MODEL),
        "api_key_env": "OPENAI_API_KEY",
        "fallback_api_key": AI_API_KEY,
        "wire_api": "chat_completions",
    },
    "relay": {
        "name": os.getenv("AI_RELAY_NAME", "AI 中转站"),
        "base_url": os.getenv("AI_RELAY_BASE_URL", "https://relay.nf.video/v1").rstrip("/"),
        "model": os.getenv("AI_RELAY_MODEL", "gpt-5.5"),
        "api_key_env": "AI_RELAY_API_KEY",
        "fallback_api_key": "",
        "wire_api": os.getenv("AI_RELAY_WIRE_API", "responses"),
        "reasoning_effort": os.getenv("AI_RELAY_REASONING_EFFORT", "high"),
        "store": not AI_RELAY_DISABLE_RESPONSE_STORAGE,
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        "api_key_env": "DEEPSEEK_API_KEY",
        "fallback_api_key": "",
        "wire_api": "chat_completions",
    },
    "qwen": {
        "name": "通义千问",
        "base_url": os.getenv("QWEN_BASE_URL", "https://ws-l9txxb2g2w5lddbn.cn-beijing.maas.aliyuncs.com/compatible-mode/v1").rstrip("/"),
        "model": os.getenv("QWEN_MODEL", "qwen-plus"),
        "api_key_env": "DASHSCOPE_API_KEY",
        "fallback_api_key": "",
        "wire_api": "chat_completions",
    },
}
