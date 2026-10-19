"""A fake Google for tests: the OAuth token endpoint (checks PKCE), Classroom and Gmail drafts. Records requests."""

from __future__ import annotations

import base64
import hashlib
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeGoogle:
    def __init__(self):
        self.challenges: dict[str, str] = {}  # code -> PKCE challenge it was issued for
        self.refresh_ok = True
        self.drafts: list[dict] = []
        self.token_calls: list[dict] = []
        self.courses = [{"id": "c1", "name": "Linear Algebra"}]
        self.work = {
            "c1": [
                {
                    "id": "w1",
                    "title": "Problem set 3",
                    "dueDate": {"year": 2099, "month": 1, "day": 10},
                    "dueTime": {"hours": 18, "minutes": 30},
                },
                {"id": "w2", "title": "Problem set 2", "dueDate": {"year": 2099, "month": 1, "day": 3}},
                {"id": "w0", "title": "Old one", "dueDate": {"year": 2001, "month": 1, "day": 1}},
            ]
        }
        self.turned_in = {"w2"}
        self.posts = {"c1": [{"id": "a1", "text": "Welcome!", "alternateLink": "https://classroom.example.com/a1"}]}
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

            def _authed(self):
                return self.headers.get("Authorization", "").startswith("Bearer access-")

            def do_POST(self):
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                if self.path == "/token":
                    f = {k: v[0] for k, v in urllib.parse.parse_qs(raw.decode()).items()}
                    fake.token_calls.append(f)
                    if f.get("grant_type") == "authorization_code":
                        ch = fake.challenges.get(f.get("code"))
                        digest = base64.urlsafe_b64encode(hashlib.sha256(f.get("code_verifier", "").encode()).digest())
                        if not ch or digest.rstrip(b"=").decode() != ch:
                            return self._json(400, {"error": "invalid_grant"})
                        return self._json(
                            200,
                            {
                                "access_token": "access-1",
                                "refresh_token": "refresh-1",
                                "expires_in": 3600,
                                "scope": f.get("scope_granted", fake.scope),
                            },
                        )
                    if f.get("grant_type") == "refresh_token":
                        if not fake.refresh_ok:
                            return self._json(400, {"error": "invalid_grant"})
                        return self._json(200, {"access_token": "access-2", "expires_in": 3600})
                    return self._json(400, {"error": "unsupported_grant_type"})
                if self.path == "/gmail/users/me/drafts":
                    if not self._authed():
                        return self._json(401, {"error": {"message": "no"}})
                    fake.drafts.append(json.loads(raw))
                    return self._json(200, {"id": "d1"})
                return self._json(404, {})

            def do_GET(self):
                if not self._authed():
                    return self._json(401, {"error": {"message": "no"}})
                path = urllib.parse.urlsplit(self.path).path
                parts = path.strip("/").split("/")
                if path == "/classroom/courses":
                    return self._json(200, {"courses": fake.courses})
                if len(parts) == 4 and parts[3] == "courseWork":
                    return self._json(200, {"courseWork": fake.work.get(parts[2], [])})
                if len(parts) == 6 and parts[5] == "studentSubmissions":
                    st = "TURNED_IN" if parts[4] in fake.turned_in else "CREATED"
                    return self._json(200, {"studentSubmissions": [{"state": st}]})
                if len(parts) == 4 and parts[3] == "announcements":
                    return self._json(200, {"announcements": fake.posts.get(parts[2], [])})
                return self._json(404, {})

        self.scope = ""
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def endpoints(self) -> dict:
        return {
            "auth": f"{self.base}/auth",
            "token": f"{self.base}/token",
            "classroom": f"{self.base}/classroom",
            "gmail": f"{self.base}/gmail",
        }

    def issue_code(self, auth_url: str) -> tuple[str, str]:
        """What Google does when you approve: a code bound to the PKCE challenge. Returns (code, state)."""
        q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(auth_url).query).items()}
        self.scope = q["scope"]
        code = f"code-{len(self.challenges) + 1}"
        self.challenges[code] = q["code_challenge"]
        return code, q["state"]

    def close(self):
        self.server.shutdown()
        self.server.server_close()
