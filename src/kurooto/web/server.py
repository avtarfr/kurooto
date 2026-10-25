"""The local web page: the setup wizard now, the dashboard and settings next. It only listens on 127.0.0.1.

Protection:
  - a token that only the page gets (written into the HTML it serves); every API call must send it;
  - the Host header must be this machine's own address and port (stops DNS-rebinding sites);
  - a request from another web page (Origin) is refused;
  - on Linux, the page and every API request must come from this user account (web/peer.py), so another account on a
    shared computer can't use it; refused when that can't be told;
  - Content-Security-Policy: the page loads nothing from the internet.
"""

from __future__ import annotations

import hashlib
import json
import os
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
from kurooto.web import peer

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults("web", {"port": 8770})
register_defaults("look", {"palette": "kuro", "theme_file": ""})  # the pages' colours (core/palette.py, themes.py)
PALETTES = ("kuro", "rose", "system")
# the dashboard's layout: dense (one full-screen board, on screens 1280 px wide or more; narrower ones get roomy) or
# roomy; projects: folders of git repositories its PROJECTS box shows (empty: Research's repositories); panes: the dense
# board's hidden panes ("status", "systems", "notes", "terminal"); hidden_features: features off the Features page;
# links_in: where links to other sites open, "default" (this computer's default browser) or "here" (static/links.js);
# study_mode: the board shows only the notes map and the STUDY pane (core/actions.py: study_mode)
register_defaults(
    "look",
    {"layout": "dense", "projects": [], "panes": [], "hidden_features": [], "links_in": "default", "study_mode": False},
)
register_defaults("look", {"design": "new"})  # the dashboard's design: new, or classic (the monospace look of 0.5.18)
LAYOUTS = ("dense", "roomy")
DESIGNS = ("new", "classic")
CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)
TOOLS_ONLY = ("/api/tools", "/api/tools/call")  # what the tools-only key may reach
TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


def free_port(start: int) -> int:
    for port in range(start, start + 30):
        with socket.socket() as s:
            try:
                if os.name != "nt":  # like the server itself: the last run's closing connections don't make it busy
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("no free port for the home page")


def static(name: str) -> bytes | None:
    if (
        not re.fullmatch(r"(?:vendor/xterm/|views/)?[a-z0-9_-]+\.(html|js|css|svg|png|ico)", name)
        and not re.fullmatch(r"fonts/[a-z0-9_-]+\.woff2", name)
        and not re.fullmatch(r"vendor/katex/(?:katex\.min\.(?:js|css)|fonts/KaTeX_[A-Za-z0-9_-]+\.woff2)", name)
    ):  # vendor: terminals, katex (recall maths); views: SYSTEMS and NOTES (the phone app's too); fonts: the typeface
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

            def _send(
                self, code: int, body: bytes | dict | list, ctype: str = "application/json", etag: str | None = None
            ):
                if isinstance(body, (dict, list)):
                    body = json.dumps(body, default=str).encode()
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Security-Policy", CSP)
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                if etag:  # a static file: kept by the browser, asked about each time (304 while it's the same)
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("ETag", etag)
                else:  # pages (they hold the key) and the API: never kept
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

            def _tools_authed(self, path: str) -> bool:
                """`kurooto mcp` has its own key, good for listing and running the AI's tools only."""
                return (
                    path in TOOLS_ONLY
                    and self.headers.get("Origin") is None
                    and pysecrets.compare_digest(self.headers.get("X-Kurooto-Tools", ""), server.tools_token)
                )

            def _same_user(self) -> bool:
                """On Linux, only this user account may use the page and its API (web/peer.py); refused when the
                connection's owner can't be told. Elsewhere: True (127.0.0.1 and the key protect it)."""
                return peer.same_user(self.client_address, server.port)

            def do_GET(self):
                if not self._host_ok():
                    return self._send(403, {"error": "wrong host"})
                path = urlparse(self.path).path
                if path == "/health":
                    return self._send(200, {"ok": True, "version": __version__})
                if not path.startswith("/static/") and not self._same_user():  # the page (it holds the key), the API
                    return self._send(403, {"error": "not your account"})
                if path == "/morning":  # the morning page (rhythm): today's plan, opened by the alarm
                    html = server.fill((static("morning.html") or b"").decode())
                    return self._send(200, html.encode(), TYPES[".html"])
                if path == "/proposals":  # the AI's changes waiting for your OK, with diffs (core/proposals.py)
                    html = server.fill((static("proposals.html") or b"").decode())
                    return self._send(200, html.encode(), TYPES[".html"])
                if path == "/confidential":  # confidential mail summarised on this computer (google): read-only
                    html = server.fill((static("confidential.html") or b"").decode())
                    return self._send(200, html.encode(), TYPES[".html"])
                if path in ("/", "/setup"):
                    done = server.app.settings.get("setup.done")
                    page = "setup.html" if path == "/setup" or not done else "home.html"
                    html = server.fill((static(page) or static("setup.html")).decode())
                    return self._send(200, html.encode(), TYPES[".html"])
                if path.startswith("/static/"):
                    name = path[len("/static/") :]
                    body = static(name)
                    if body is None:
                        return self._send(404, {"error": "not found"})
                    ctype = TYPES.get("." + name.rsplit(".", 1)[-1], "application/octet-stream")
                    # the browser keeps the dashboard's script (230 KB), styles and fonts, and what it compiled of
                    # them, instead of fetching and compiling everything again on each load (0.6.1)
                    tag = '"' + hashlib.sha1(body, usedforsecurity=False).hexdigest()[:20] + '"'
                    if tag in [t.strip() for t in self.headers.get("If-None-Match", "").split(",")]:
                        return self._send(304, b"", ctype, etag=tag)
                    return self._send(200, body, ctype, etag=tag)
                if path == "/oauth/google":  # Google's sign-in comes back here; the one-time state guards it
                    from urllib.parse import parse_qs

                    q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
                    g = server.app.modules.get("google")
                    if not g:
                        ok, msg = False, "Google sign-in isn't available in this version of Kurooto."
                    elif q.get("error"):
                        from kurooto.modules.google import signin_error

                        ok, msg = False, signin_error(q["error"])
                    else:
                        ok, msg = g.finish_signin(q.get("code", ""), q.get("state", ""))
                    page = (
                        '<!doctype html><meta charset=utf-8><title>Kurooto</title><body style="font:16px system-ui;'
                        'background:#0b0f0a;color:#dad3c8;padding:40px">'
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
                    if not self._authed() and not self._tools_authed(path):
                        return self._send(401, {"error": "no"})
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
                path = urlparse(self.path).path
                if not self._host_ok() or not self._same_user() or not (self._authed() or self._tools_authed(path)):
                    return self._send(403, {"error": "no"})
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    n = -1
                if n < 0:  # read(-1) would wait for the connection to close
                    return self._send(400, {"error": "bad length"})
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
        # the tools-only key for `kurooto mcp` (agent programs), new at every start; the file is owner-only
        from kurooto.core.mcp import access_file

        self.tools_token = pysecrets.token_urlsafe(24)
        jsave(access_file(app.paths), {"url": self.url, "token": self.tools_token, "started": time.time()})

    def fill(self, html: str) -> str:
        """A page with its key, the version, the palette (look.palette), the layout (look.layout), the design
        (look.design) and Study mode (look.study_mode) written in. The system palette's colours come as a <style>
        (made only of checked #rrggbb values), and static/palette.js keeps them current. static/links.js sends links
        to other sites to the default browser (look.links_in)."""
        from kurooto.core import palette as pal

        name = pal.resolve(self.app)[0]  # "system" with nothing found is kuro
        layout = self.app.settings.get("look.layout")
        layout = layout if layout in LAYOUTS else "dense"
        design = self.app.settings.get("look.design")
        design = design if design in DESIGNS else "new"
        head = (
            f'<style id="kurooto-palette">{pal.css(self.app)}</style><script src="/static/palette.js" defer></script>'
        )
        links = "here" if self.app.settings.get("look.links_in") == "here" else "default"  # never anything else
        head += f'<meta name="kurooto-links" content="{links}"><script src="/static/links.js" defer></script>'
        html = html.replace("</head>", head + "\n</head>", 1).replace("{{LAYOUT}}", layout)
        html = html.replace("{{DESIGN}}", design)
        html = html.replace("{{STUDY}}", "on" if self.app.settings.get("look.study_mode") else "")
        return html.replace("{{TOKEN}}", self.token).replace("{{VERSION}}", __version__).replace("{{PALETTE}}", name)

    def start(self) -> Server:
        threading.Thread(target=self.httpd.serve_forever, name="web", daemon=True).start()
        return self

    def stop(self) -> None:
        self.stopping = True
        self.live.stop()
        self.httpd.shutdown()
        self.httpd.server_close()
        from kurooto.core.mcp import access_file
        from kurooto.core.state import jload

        f = access_file(self.app.paths)
        if (jload(f, {}) or {}).get("token") == self.tools_token:  # not one a newer start wrote
            f.unlink(missing_ok=True)


def start(app: App, port: int | None = None) -> Server:
    return Server(app, port).start()
