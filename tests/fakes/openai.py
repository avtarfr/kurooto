"""A fake OpenAI-compatible API: answers from a script, or fails the way real services do."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeOpenAI:
    def __init__(self, key="sk-fake"):  # noqa: S107 (a fake)
        self.key = key
        self.mode = "ok"  # ok | 429 | 401 | empty | 500
        self.answer = "Paris."
        self.requests: list[dict] = []
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, obj, headers=None):
                body = json.dumps(obj).encode()
                self.send_response(code)
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path.endswith("/models"):
                    return self._send(200, {"data": [{"id": "models/fast"}, {"id": "smart"}]})
                self._send(404, {})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                fake.requests.append(body)
                if self.headers.get("Authorization") != f"Bearer {fake.key}" or fake.mode == "401":
                    return self._send(401, {"error": {"message": "invalid api key"}})
                if fake.mode == "429":
                    return self._send(429, {"error": {"message": "RESOURCE_EXHAUSTED"}}, {"Retry-After": "30"})
                if fake.mode == "500":
                    return self._send(500, {"error": {"message": "boom"}})
                text = "" if fake.mode == "empty" else fake.answer
                self._send(
                    200,
                    {"choices": [{"message": {"role": "assistant", "content": text}}], "usage": {"total_tokens": 9}},
                )

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
