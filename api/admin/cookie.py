from http import HTTPStatus
from http.server import BaseHTTPRequestHandler

from lib.fenbi_client import (
    FenbiError,
    json_response,
    read_cookie,
    read_request_json,
    validate_cookie,
    write_runtime_cookie,
)


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        json_response(self, {"ok": True})

    def do_GET(self):
        cookie, source = read_cookie()
        json_response(
            self,
            {
                "ok": True,
                "cookie": {
                    "configured": bool(cookie),
                    "source": source,
                    "runtime_storage": "ephemeral",
                },
            },
        )

    def do_POST(self):
        try:
            payload = read_request_json(self)
            cookie = str(payload.get("cookie") or "").strip()
            validation = validate_cookie(cookie)
            write_runtime_cookie(cookie)
            json_response(
                self,
                {
                    "ok": True,
                    "message": "Cookie 已验证并写入运行时临时存储",
                    "storage": "ephemeral",
                    "warning": "Vercel Serverless 文件系统不是持久存储；实例重建后会回退到 FENBI_COOKIE 环境变量。",
                    "validation": validation,
                },
            )
        except FenbiError as exc:
            json_response(
                self,
                {
                    "ok": False,
                    "error": {
                        "message": str(exc),
                        "details": exc.details,
                    },
                },
                exc.status_code,
            )
        except Exception as exc:
            json_response(
                self,
                {
                    "ok": False,
                    "error": {
                        "message": "Cookie 更新失败",
                        "details": {"error": str(exc)},
                    },
                },
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
