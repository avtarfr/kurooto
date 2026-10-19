"""A fake OpenAI-style chat API that answers from a script, for the function-calling loop.

Each step of the script is one reply: a message dict ({"content": ..., "tool_calls": [...]}), or
("http", code, body, headers) to fail the way real services do. When the script runs out, the last step repeats.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def call(name: str, args, cid: str | None = "c1") -> dict:
    """One tool call as the API sends it (arguments as a JSON string, or raw text to test bad JSON)."""
    c = {
        "type": "function",
        "function": {"name": name, "arguments": args if isinstance(args, str) else json.dumps(args)},
    }
    if cid is not None:
        c["id"] = cid
    return c


class ScriptedOpenAI:
    def __init__(self, script: list, key: str = "sk-tools"):
        self.key = key
        self.script = list(script)
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

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                fake.requests.append(body)
                step = fake.script.pop(0) if len(fake.script) > 1 else fake.script[0]
                if isinstance(step, tuple) and step[0] == "http":
                    return self._send(step[1], step[2], step[3] if len(step) > 3 else None)
                msg = {"role": "assistant", "content": step.get("content")}
                if step.get("tool_calls"):
                    msg["tool_calls"] = step["tool_calls"]
                self._send(200, {"choices": [{"message": msg}], "usage": {"total_tokens": 10}})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
