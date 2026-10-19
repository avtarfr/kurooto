"""The local web page: the setup wizard now, the dashboard and settings next. It only listens on 127.0.0.1.

Protection:
  - a token that only the page gets (written into the HTML it serves); every API call must send it;
  - the Host header must be this machine's own address and port (stops DNS-rebinding sites);
  - a request from another web page (Origin) is refused;
  - Content-Security-Policy: the page loads nothing from the internet.
"""

from __future__ import annotations

import json
import re
import secrets as pysecrets
import socket
import threading
import time
from html import escape as html_escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from kurooto import __version__
from kurooto.core.config import register_defaults
from kurooto.core.state import jsave

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults("web", {"port": 8770})
CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)
TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


def free_port(start: int) -> int:
    for port in range(start, start + 30):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("no free port for the home page")


def static(name: str) -> bytes | None:
    if not re.fullmatch(r"(?:vendor/xterm/)?[a-z0-9_-]+\.(html|js|css|svg|png|ico)", name):  # vendor: terminals
        return None
    f = resources.files("kurooto.web").joinpath("static", *name.split("/"))
    return f.read_bytes() if f.is_file() else None


class Server:
    def __init__(self, app: App, port: int | None = None):
        self.app = app
        self.port = free_port(port or app.settings.get("web.port") or 8770)
        self.token = app.secrets.get("web.token")
        if not self.token:
            self.token = pysecrets.token_urlsafe(24)
            app.secrets.set("web.token", self.token)
        self.hosts = {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}
        app.web_port = self.port  # sign-in pages (Google) come back here
        from kurooto.web.api import Api
        from kurooto.web.live import Live

        self.api = Api(app)
        self.live = Live(app)
        app.live = self.live  # features push to open pages through it (the terminals' output)
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code: int, body: bytes | dict | list, ctype: str = "application/json"):
                if isinstance(body, (dict, list)):
                    body = json.dumps(body, default=str).encode()
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Security-Policy", CSP)
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def _host_ok(self) -> bool:
                return self.headers.get("Host", "") in server.hosts

            def _authed(self) -> bool:
                if not pysecrets.compare_digest(self.headers.get("X-Kurooto", ""), server.token):
                    return False
                origin = self.headers.get("Origin")
                return origin is None or urlparse(origin).netloc in server.hosts

            def do_GET(self):
                if not self._host_ok():
                    return self._send(403, {"error": "wrong host"})
                path = urlparse(self.path).path
                if path == "/health":
                    return self._send(200, {"ok": True, "version": __version__})
                if path in ("/", "/setup"):
                    done = server.app.settings.get("setup.done")
                    page = "setup.html" if path == "/setup" or not done else "home.html"
                    html = (static(page) or static("setup.html")).decode()
                    html = html.replace("{{TOKEN}}", server.token).replace("{{VERSION}}", __version__)
                    return self._send(200, html.encode(), TYPES[".html"])
                if path.startswith("/static/"):
                    name = path[len("/static/") :]
                    body = static(name)
                    if body is None:
                        return self._send(404, {"error": "not found"})
                    return self._send(200, body, TYPES.get("." + name.rsplit(".", 1)[-1], "application/octet-stream"))
                if path == "/oauth/google":  # Google's sign-in comes back here; the one-time state guards it
                    from urllib.parse import parse_qs

                    q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
                    g = server.app.modules.get("google")
                    if q.get("error") or not g:
                        ok, msg = False, f"Google sign-in didn't finish ({q.get('error', 'not available')})."
                    else:
                        ok, msg = g.finish_signin(q.get("code", ""), q.get("state", ""))
                    page = (
                        '<!doctype html><meta charset=utf-8><title>Kurooto</title><body style="font:16px system-ui;'
                        'background:#14111a;color:#ece8f2;padding:40px">'
                        f"<h2>{'✓' if ok else '✗'} {html_escape(msg)}</h2>"
                    )
                    return self._send(200 if ok else 400, page.encode(), TYPES[".html"])
                if path == "/api/stream":  # EventSource can't send headers: the token comes in the query
                    from urllib.parse import parse_qs

                    tok = (parse_qs(urlparse(self.path).query).get("t") or [""])[0]
                    if not pysecrets.compare_digest(tok, server.token):
                        return self._send(401, {"error": "no"})
                    return self._stream()
                if path.startswith("/api/"):
                    if not self._authed():
                        return self._send(401, {"error": "no"})
                    if path.startswith("/api/term"):  # terminals: only this user account (on Linux, checked)
                        from kurooto.modules.terminals import same_user

                        if not same_user(self.client_address, server.port):
                            return self._send(403, {"error": "no"})
                    from urllib.parse import parse_qs

                    q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
                    code, out = server.api.get(path[5:], q)
                    return self._send(code, out)
                return self._send(404, {"error": "not found"})

            def _stream(self):
                cid, q = server.live.add()
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Security-Policy", CSP)
                self.end_headers()
                try:
                    while not server.stopping:
                        try:
                            data = q.get(timeout=15)
                            chunk = [data]
                            while not q.empty() and len(chunk) < 50:
                                chunk.append(q.get_nowait())
                            self.wfile.write("".join(f"data: {d}\n\n" for d in chunk).encode())
                        except Exception:
                            self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    server.live.drop(cid)

            def do_POST(self):
                if not self._host_ok() or not self._authed():
                    return self._send(403, {"error": "no"})
                path = urlparse(self.path).path
                if path.startswith("/api/term"):  # terminals: only this user account (on Linux, checked)
                    from kurooto.modules.terminals import same_user

                    if not server.app.is_on("terminals") or not same_user(self.client_address, server.port):
                        return self._send(403, {"error": "no"})
                n = int(self.headers.get("Content-Length") or 0)
                if n > 4_000_000:  # long reports from AI accounts (About you)
                    return self._send(413, {"error": "too big"})
                try:
                    body = json.loads(self.rfile.read(n) or b"{}")
                except ValueError:
                    return self._send(400, {"error": "bad json"})
                if not path.startswith("/api/"):
                    return self._send(404, {"error": "not found"})
                code, out = server.api.post(path[5:], body if isinstance(body, dict) else {})
                return self._send(code, out)

        self.stopping = False
        self.httpd = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.httpd.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.port}/"
        jsave(app.paths.state / "web.json", {"port": self.port, "url": self.url, "started": time.time()})

    def start(self) -> Server:
        threading.Thread(target=self.httpd.serve_forever, name="web", daemon=True).start()
        return self

    def stop(self) -> None:
        self.stopping = True
        self.live.stop()
        self.httpd.shutdown()
        self.httpd.server_close()


def start(app: App, port: int | None = None) -> Server:
    return Server(app, port).start()
