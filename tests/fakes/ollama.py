"""A stub Ollama on localhost: /api/tags lists the models it "has", /api/chat answers like a small local model
summarising mails (JSON), and every request is recorded."""

from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeOllama:
    def __init__(self, models=("qwen3:4b-instruct-2507-q4_K_M",)):
        self.models = list(models)
        self.chats: list[dict] = []
        self.broken = False  # answers that aren't JSON
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, code, obj):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/api/tags":
                    return self._json(200, {"models": [{"name": m} for m in fake.models]})
                return self._json(404, {})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                if self.path != "/api/chat":
                    return self._json(404, {})
                fake.chats.append(body)
                return self._json(200, {"message": {"role": "assistant", "content": fake.answer(body)}})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def answer(self, body: dict) -> str:
        if self.broken:
            return "Sorry, I can't do JSON today."
        prompt = body["messages"][-1]["content"]
        mails = []
        for n, part in enumerate(re.split(r"(?m)^Mail \d+\n", prompt)[1:], 1):
            due = re.search(r"due (\d{4}-\d\d-\d\d \d\d:\d\d)", part)
            subject = re.search(r"Subject: (.*)", part).group(1)
            mails.append(
                {
                    "n": n,
                    "summary": f"Local summary {n}: about {subject}.",
                    "deadlines": [{"title": f"Reply on {subject}", "due": due.group(1)}] if due else [],
                }
            )
        return json.dumps({"mails": mails})

    def close(self):
        self.server.shutdown()
        self.server.server_close()
