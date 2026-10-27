"""A fake OpenAI-compatible API: answers from a script, or fails the way real services do."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeOpenAI:
    def __init__(self, key="sk-fake"):  # noqa: S107 (a fake)
        self.key = key
        self.mode = "ok"  # ok | 429 | 401 | empty | 500
        self.mode_by_model: dict = {}  # a model name -> its own mode (each model has its own limit)
        self.answer = "Paris."
        self.limit_body = None  # what a 429 says (Google's JSON error, say); default: a bare RESOURCE_EXHAUSTED
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
                mode = fake.mode_by_model.get(body.get("model"), fake.mode)
                if self.headers.get("Authorization") != f"Bearer {fake.key}" or mode == "401":
                    return self._send(401, {"error": {"message": "invalid api key"}})
                if mode == "429":
                    body = fake.limit_body or {"error": {"message": "RESOURCE_EXHAUSTED"}}
                    return self._send(429, body, {"Retry-After": "30"})
                if mode == "500":
                    return self._send(500, {"error": {"message": "boom"}})
                text = "" if mode == "empty" else fake.answer
                if body.get("stream"):  # server-sent events, a word at a time, then [DONE]
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    words = text.split(" ")
                    for i, w in enumerate(words):
                        piece = w if i == 0 else f" {w}"
                        chunk = {"model": body.get("model"), "choices": [{"delta": {"content": piece}}]}
                        self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                        self.wfile.flush()
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                    self.close_connection = True
                    return None
                self._send(
                    200,
                    {"choices": [{"message": {"role": "assistant", "content": text}}], "usage": {"total_tokens": 9}},
                )

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
