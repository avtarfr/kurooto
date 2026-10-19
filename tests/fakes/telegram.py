"""A fake Telegram Bot API on localhost: records what the bot sends, serves queued updates and files."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeTelegram:
    def __init__(self, token="123:fake", username="kurooto_test_bot"):  # noqa: S107 (a fake)
        self.token, self.username = token, username
        self.updates: list[dict] = []
        self.sent: list[tuple[str, dict]] = []
        self.files: dict[str, bytes] = {}
        self._next_update = 1
        self._next_msg = 100
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                prefix = f"/file/bot{fake.token}/"
                if self.path.startswith(prefix) and self.path[len(prefix) :] in fake.files:
                    body = fake.files[self.path[len(prefix) :]]
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n)
                token, _, method = self.path.removeprefix("/bot").partition("/")
                ctype = self.headers.get("Content-Type", "")
                params = json.loads(raw or b"{}") if ctype.startswith("application/json") else {"multipart": True}
                if token != fake.token:
                    return self._send(401, {"ok": False, "error_code": 401, "description": "Unauthorized"})
                fake.sent.append((method, params))
                res = fake.answer(method, params)
                self._send(200, {"ok": True, "result": res})

            def _send(self, code, obj):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def answer(self, method, p):
        if method == "getMe":
            return {"id": 42, "is_bot": True, "username": self.username}
        if method == "getUpdates":
            off = p.get("offset", 0)
            return [u for u in self.updates if u["update_id"] >= off]
        if method in ("sendMessage", "sendDocument"):
            self._next_msg += 1
            return {"message_id": self._next_msg}
        if method == "getFile":
            return {"file_id": p["file_id"], "file_path": f"docs/{p['file_id']}.pdf", "file_size": 10}
        return True

    def message(self, text="", user=7, chat=7, chat_type="private", **extra):
        m = {
            "message_id": self._next_update + 1000,
            "from": {"id": user, "first_name": "Friend"},
            "chat": {"id": chat, "type": chat_type},
            "text": text,
            **extra,
        }
        self.updates.append({"update_id": self._next_update, "message": m})
        self._next_update += 1
        return m

    def press(self, data, user=7):
        self.updates.append(
            {"update_id": self._next_update, "callback_query": {"id": "cb1", "from": {"id": user}, "data": data}}
        )
        self._next_update += 1

    def texts(self):
        return [p.get("text") for m, p in self.sent if m == "sendMessage"]

    def close(self):
        self.server.shutdown()
