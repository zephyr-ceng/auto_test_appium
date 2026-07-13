from http.server import BaseHTTPRequestHandler

from lib.fenbi_client import json_response, read_cookie, read_status


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        json_response(self, {"ok": True})

    def do_GET(self):
        cookie, source = read_cookie()
        status = read_status()
        json_response(
            self,
            {
                "ok": True,
                "cookie": {
                    "configured": bool(cookie),
                    "source": source,
                },
                "status": status,
            },
        )
