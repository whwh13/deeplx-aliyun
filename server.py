import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import aliyun
from aliyun import AliyunMtError


class State:
    """托盘与 HTTP 服务共享的可重载配置。"""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def start(self):
        self.stop()
        self.httpd = ThreadingHTTPServer(
            (self.cfg["host"], int(self.cfg["port"])), make_handler(self.cfg)
        )
        self.thread = threading.Thread(
            target=self.httpd.serve_forever, daemon=True
        )
        self.thread.start()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
            self.thread = None


def make_handler(cfg: dict):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, payload: dict):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._send(
                200,
                {
                    "code": 200,
                    "message": "DeepLX-Aliyun",
                    "config": {
                        "host": cfg["host"],
                        "port": cfg["port"],
                        "access_key_id": cfg["access_key_id"][:4] + "***"
                        if cfg["access_key_id"]
                        else "(未配置)",
                    },
                },
            )

        def do_POST(self):
            if self.path.rstrip("/") not in ("/translate", "/v2/translate"):
                self._send(404, {"code": 404, "message": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, json.JSONDecodeError):
                self._send(400, {"code": 400, "message": "invalid JSON body"})
                return

            text = data.get("text", "")
            source_lang = data.get("source_lang", "auto") or "auto"
            target_lang = data.get("target_lang", "ZH") or "ZH"
            if not text:
                self._send(400, {"code": 400, "message": "text is empty"})
                return
            if not cfg.get("access_key_id") or not cfg.get("access_key_secret"):
                self._send(
                    500, {"code": 500, "message": "未配置阿里云 AccessKey（config.json）"}
                )
                return

            try:
                result, detected = aliyun.translate(
                    text, source_lang, target_lang, cfg
                )
            except AliyunMtError as e:
                self._send(e.code, {"code": e.code, "message": e.message})
                return

            src_out = (detected or source_lang).upper()
            self._send(
                200,
                {
                    "code": 200,
                    "id": data.get("id", 0),
                    "data": result,
                    "alternatives": [],
                    "source_lang": src_out,
                    "target_lang": target_lang.upper(),
                    "method": "Aliyun",
                },
            )

        def log_message(self, fmt, *args):
            pass

    return Handler
