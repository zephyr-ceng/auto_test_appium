from http import HTTPStatus
from http.server import BaseHTTPRequestHandler

from lib.fenbi_client import FenbiError, fetch_report, json_response


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        json_response(self, {"ok": True})

    def do_GET(self):
        try:
            force = "force=1" in (self.path.split("?", 1)[1] if "?" in self.path else "")
            report = fetch_report(force=force)
            json_response(self, {"ok": True, "data": report})
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
                        "message": "服务端未知错误",
                        "details": {"error": str(exc)},
                    },
                },
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
