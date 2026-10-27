"""Try a working copy's dashboard on your running Kurooto's live data, without installing a release (0.8.9).

    uv run python tools/dash_preview.py [--live 8770] [--port 8771]

Serves this folder's src/kurooto/web/static (the page, its scripts, the being's anatomy) on 127.0.0.1:PORT and passes
/api/* (the live stream too) to the Kurooto running on 127.0.0.1:LIVE. The key comes from that Kurooto's own page and
never prints. Everything the page does is real: a setting changed here changes it on that Kurooto. The same guards as
the dashboard: only 127.0.0.1, only this host name, only this user account (web/peer.py), the key on every API call,
and nothing from other sites (Origin). Ctrl+C stops it.
"""

from __future__ import annotations

import argparse
import http.client
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "src" / "kurooto" / "web" / "static"
sys.path.insert(0, str(ROOT / "src"))

from kurooto.web import peer  # noqa: E402
from kurooto.web.server import CSP, TYPES  # noqa: E402


def live_page(port: int) -> str:
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("GET", "/", headers={"Host": f"127.0.0.1:{port}"})
    r = c.getresponse()
    if r.status != 200:
        raise SystemExit(f"Kurooto on port {port} answered {r.status}: is it running, as you?")
    return r.read().decode()


def page(live_html: str, version: str) -> tuple[str, str]:
    """This folder's home.html filled the way the live Kurooto fills its own: its key, palette, layout and design."""
    tok = re.search(r'<meta name="kurooto-token" content="([^"]+)"', live_html)
    if not tok:
        raise SystemExit("The live page has no key in it (an older Kurooto?).")
    attr = lambda name, default: m.group(1) if (m := re.search(rf'data-{name}="([^"]*)"', live_html)) else default  # noqa: E731
    head = "".join(
        re.findall(
            r'<style id="kurooto-palette">.*?</style>|<script src="/static/palette.js" defer></script>'
            r'|<meta name="kurooto-links"[^>]*><script src="/static/links.js" defer></script>',
            live_html,
            re.S,
        )
    )
    html = (STATIC / "home.html").read_text().replace("</head>", head + "\n</head>", 1)
    for k, v in {
        "LAYOUT": attr("layout", "dense"),
        "DESIGN": attr("design", "new"),
        "STUDY": attr("study", ""),
        "PALETTE": attr("palette", "kuro"),
        "VERSION": version,
        "TOKEN": tok.group(1),
    }.items():
        html = html.replace("{{" + k + "}}", v)
    return html, tok.group(1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--live", type=int, default=8770, help="the running Kurooto's port (web.port)")
    ap.add_argument("--port", type=int, default=8771, help="where the preview listens")
    a = ap.parse_args()
    html, _ = page(live_page(a.live), "preview")
    hosts = {f"127.0.0.1:{a.port}", f"localhost:{a.port}"}

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _ok(self) -> bool:
            if self.headers.get("Host", "") not in hosts:
                self._send(403, b'{"error": "wrong host"}')
                return False
            origin = self.headers.get("Origin")
            if origin is not None and urlparse(origin).netloc not in hosts:
                self._send(403, b'{"error": "not from this page"}')
                return False
            if not peer.same_user(self.client_address, a.port):
                self._send(403, b'{"error": "not your account"}')
                return False
            return True

        def _proxy(self, method: str) -> None:
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n) if n else None
            fwd = {"Host": f"127.0.0.1:{a.live}", "Content-Type": self.headers.get("Content-Type", "application/json")}
            if self.headers.get("X-Kurooto"):
                fwd["X-Kurooto"] = self.headers["X-Kurooto"]
            stream = urlparse(self.path).path == "/api/stream"
            c = http.client.HTTPConnection("127.0.0.1", a.live, timeout=None if stream else 120)
            try:
                c.request(method, self.path, body=body, headers=fwd)
                r = c.getresponse()
            except OSError:
                return self._send(502, b'{"error": "the live Kurooto did not answer"}')
            if not stream:
                return self._send(r.status, r.read(), r.getheader("Content-Type", "application/json"))
            self.send_response(r.status)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            try:
                while chunk := r.fp.read1(65536):
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except OSError:
                pass
            finally:
                c.close()

        def do_GET(self):
            if not self._ok():
                return
            path = urlparse(self.path).path
            if path in ("/", "/home"):
                return self._send(200, html.encode(), TYPES[".html"])
            if path.startswith("/api/"):
                return self._proxy("GET")
            if path.startswith("/static/"):
                f = (STATIC / path[len("/static/") :]).resolve()
                if f.is_file() and STATIC.resolve() in f.parents:
                    return self._send(200, f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream"))
            return self._send(404, b'{"error": "not found"}')

        def do_POST(self):
            if not self._ok():
                return
            if urlparse(self.path).path.startswith("/api/"):
                return self._proxy("POST")
            return self._send(404, b'{"error": "not found"}')

    srv = ThreadingHTTPServer(("127.0.0.1", a.port), H)
    srv.daemon_threads = True
    print(f"preview: http://127.0.0.1:{a.port}/  (live data from port {a.live}; settings you change here are real)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
