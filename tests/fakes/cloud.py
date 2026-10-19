"""Fake cloud services for the call line's local test: Gemini's token endpoint, ntfy, and a Web Push endpoint.
They record what they're sent."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeCloud:
    def __init__(self):
        self.tokens: list[dict] = []  # Gemini auth_tokens requests
        self.ntfy: list[dict] = []
        self.pushes: list[dict] = []
        self.generate: list[dict] = []  # Gemini generateContent (voice notes)
        self.transcript = "remind me at nine to call home"
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path.startswith("/models"):  # checking a Gemini key
                    if self.headers.get("x-goog-api-key") == "good-key":
                        return self._json({"models": [{"name": "models/x"}]})
                    self.send_response(400)
                    self.end_headers()
                    return None
                self.send_response(404)
                self.end_headers()
                return None

            def do_POST(self):
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                hdrs = {k.lower(): v for k, v in self.headers.items()}
                if self.path.endswith("/auth_tokens"):
                    fake.tokens.append({"headers": hdrs, "body": json.loads(raw or b"{}")})
                    return self._json({"name": f"auth_tokens/fake-{len(fake.tokens)}"})
                if ":generateContent" in self.path:
                    fake.generate.append({"path": self.path, "headers": hdrs, "body": json.loads(raw or b"{}")})
                    return self._json({"candidates": [{"content": {"parts": [{"text": fake.transcript}]}}]})
                if self.path.startswith("/push/"):
                    fake.pushes.append({"path": self.path, "headers": hdrs, "len": len(raw)})
                    self.send_response(201)
                    self.end_headers()
                    return None
                if self.path == "/":
                    fake.ntfy.append(json.loads(raw or b"{}"))
                    return self._json({"id": str(len(fake.ntfy))})
                self.send_response(404)
                self.end_headers()
                return None

            def _json(self, obj):
                body = json.dumps(obj).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
