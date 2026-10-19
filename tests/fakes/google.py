"""A fake Google for tests: the OAuth token endpoint (checks PKCE), Classroom, Drive, Gmail (read and drafts) and
Calendar. Records requests, so tests can check what was read, written and sent."""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RECENT = (dt.datetime.now(dt.UTC) - dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


class FakeGoogle:
    def __init__(self):
        self.challenges: dict[str, str] = {}  # code -> PKCE challenge it was issued for
        self.refresh_ok = True
        self.drafts: list[dict] = []  # bodies of drafts.create calls (kept for the older tests)
        self.draft_store: dict[str, dict] = {}  # id -> message
        self.sent: list[str] = []  # draft ids sent
        self.token_calls: list[dict] = []
        self.requests: list[tuple[str, str]] = []  # (method, path) of every API call
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
        self.materials: dict[str, list | None] = {"c1": []}  # None: the course doesn't share materials (403)
        self.drive: dict[str, dict] = {}  # id -> {"name", "mimeType", "data": bytes, "children": [ids]}
        self.me = "me@school.example"
        self.labels = [{"id": "INBOX", "name": "INBOX"}, {"id": "Label_7", "name": "Courses"}]
        self.mail: dict[str, dict] = {}  # id -> {"from", "subject", "labels", "text", "html", "thread", "ms", ...}
        self.full_fetched: list[str] = []  # message ids read in full (the body)
        self.mail_queries: list[str] = []
        self.calendars: dict[str, dict] = {}  # id -> {"summary", "events": {id: body}}
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

            def _bytes(self, data: bytes):
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _empty(self):
                self.send_response(204)
                self.end_headers()

            def _authed(self):
                return self.headers.get("Authorization", "").startswith("Bearer access-")

            def _body(self) -> bytes:
                return self.rfile.read(int(self.headers.get("Content-Length") or 0))

            def do_POST(self):
                raw = self._body()
                path = urllib.parse.urlsplit(self.path).path
                if path == "/token":
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
                if not self._authed():
                    return self._json(401, {"error": {"message": "no"}})
                fake.requests.append(("POST", path))
                body = json.loads(raw or b"{}")
                parts = path.strip("/").split("/")
                if path == "/gmail/users/me/drafts":
                    fake.drafts.append(body)
                    did = f"r-{len(fake.drafts)}"
                    fake.draft_store[did] = body["message"]
                    return self._json(200, {"id": did, "message": {"id": f"m-{did}"}})
                if path == "/gmail/users/me/drafts/send":
                    if body.get("id") not in fake.draft_store:
                        return self._json(404, {"error": {"message": "Requested entity was not found."}})
                    fake.sent.append(body["id"])
                    fake.draft_store.pop(body["id"])
                    return self._json(200, {"id": "sent-1"})
                if path == "/calendar/calendars":
                    cid = f"kur{len(fake.calendars) + 1}@group.calendar.google.com"
                    fake.calendars[cid] = {"summary": body.get("summary"), "body": body, "events": {}}
                    return self._json(200, {"id": cid, **body})
                if parts[:2] == ["calendar", "calendars"] and len(parts) == 4 and parts[3] == "events":
                    cal = fake.calendars.get(urllib.parse.unquote(parts[2]))
                    if cal is None:
                        return self._json(404, {"error": {"message": "Not Found"}})
                    eid = f"e{sum(len(c['events']) for c in fake.calendars.values()) + 1}"
                    cal["events"][eid] = {"id": eid, **body}
                    return self._json(200, cal["events"][eid])
                return self._json(404, {})

            def do_PUT(self):
                raw = self._body()
                if not self._authed():
                    return self._json(401, {"error": {"message": "no"}})
                path = urllib.parse.urlsplit(self.path).path
                fake.requests.append(("PUT", path))
                parts = path.strip("/").split("/")
                if parts[:4] == ["gmail", "users", "me", "drafts"] and len(parts) == 5:
                    if parts[4] not in fake.draft_store:
                        return self._json(404, {"error": {"message": "Requested entity was not found."}})
                    fake.draft_store[parts[4]] = json.loads(raw)["message"]
                    return self._json(200, {"id": parts[4]})
                return self._json(404, {})

            def do_DELETE(self):
                if not self._authed():
                    return self._json(401, {"error": {"message": "no"}})
                path = urllib.parse.urlsplit(self.path).path
                fake.requests.append(("DELETE", path))
                parts = path.strip("/").split("/")
                if parts[:4] == ["gmail", "users", "me", "drafts"] and len(parts) == 5:
                    if fake.draft_store.pop(parts[4], None) is None:
                        return self._json(404, {"error": {"message": "not found"}})
                    return self._empty()
                if parts[:2] == ["calendar", "calendars"] and len(parts) == 5 and parts[3] == "events":
                    cal = fake.calendars.get(urllib.parse.unquote(parts[2]))
                    if not cal or cal["events"].pop(parts[4], None) is None:
                        return self._json(404, {"error": {"message": "not found"}})
                    return self._empty()
                return self._json(404, {})

            def do_GET(self):
                if not self._authed():
                    return self._json(401, {"error": {"message": "no"}})
                u = urllib.parse.urlsplit(self.path)
                path, q = u.path, {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
                fake.requests.append(("GET", path))
                parts = path.strip("/").split("/")
                handler = {"classroom": self._classroom, "drive": self._drive, "gmail": self._gmail}
                handler["calendar"] = self._calendar
                if parts[0] in handler:
                    return handler[parts[0]](parts, q)
                return self._json(404, {})

            def _classroom(self, parts, q):
                if parts == ["classroom", "courses"]:
                    return self._json(200, {"courses": fake.courses})
                if len(parts) == 4 and parts[3] == "courseWork":
                    return self._json(200, {"courseWork": fake.work.get(parts[2], [])})
                if len(parts) == 4 and parts[3] == "courseWorkMaterials":
                    if fake.materials.get(parts[2]) is None:
                        return self._json(403, {"error": {"message": "The caller does not have permission"}})
                    return self._json(200, {"courseWorkMaterial": fake.materials[parts[2]]})
                if len(parts) == 6 and parts[5] == "studentSubmissions":
                    st = "TURNED_IN" if parts[4] in fake.turned_in else "CREATED"
                    return self._json(200, {"studentSubmissions": [{"state": st}]})
                if len(parts) == 4 and parts[3] == "announcements":
                    return self._json(200, {"announcements": fake.posts.get(parts[2], [])})
                return self._json(404, {})

            def _drive(self, parts, q):
                if parts[-1] == "files" and "q" in q:  # a folder's children
                    parent = q["q"].split("'")[1]
                    kids = fake.drive.get(parent, {}).get("children", [])
                    return self._json(200, {"files": [{"id": k, **_meta(fake.drive[k])} for k in kids]})
                if len(parts) >= 3 and parts[1] == "files":
                    f = fake.drive.get(parts[2])
                    if f is None or f.get("forbidden"):
                        return self._json(404 if f is None else 403, {"error": {"message": "File not found"}})
                    if (len(parts) == 4 and parts[3] == "export") or q.get("alt") == "media":
                        return self._bytes(f["data"])
                    return self._json(200, {"id": parts[2], **_meta(f)})
                return self._json(404, {})

            def _gmail(self, parts, q):
                tail = parts[3:]  # after gmail/users/me
                if tail == ["profile"]:
                    return self._json(200, {"emailAddress": fake.me})
                if tail == ["labels"]:
                    return self._json(200, {"labels": fake.labels})
                if tail == ["messages"]:
                    fake.mail_queries.append(q.get("q", ""))
                    ids = sorted(fake.mail, key=lambda k: -fake.mail[k]["ms"])
                    return self._json(200, {"messages": [{"id": i, "threadId": fake.mail[i]["thread"]} for i in ids]})
                if len(tail) == 2 and tail[0] == "messages":
                    m = fake.mail.get(tail[1])
                    if not m:
                        return self._json(404, {"error": {"message": "not found"}})
                    heads = [{"name": "From", "value": m["from"]}, {"name": "Subject", "value": m["subject"]}]
                    heads.append({"name": "Message-ID", "value": f"<{tail[1]}@mail.example>"})
                    if m.get("reply_to"):
                        heads.append({"name": "Reply-To", "value": m["reply_to"]})
                    out = {
                        "id": tail[1],
                        "threadId": m["thread"],
                        "labelIds": m["labels"],
                        "internalDate": str(m["ms"]),
                        "payload": {"headers": heads},
                    }
                    if q.get("format") == "full":
                        fake.full_fetched.append(tail[1])
                        mime = "text/html" if m.get("html") else "text/plain"
                        kids = [{"mimeType": mime, "body": {"data": _b64(m["text"])}}]
                        kids += [
                            {"filename": a, "mimeType": "application/pdf", "body": {"attachmentId": "x", "size": 9}}
                            for a in m.get("attachments", [])
                        ]
                        out["payload"] = {**out["payload"], "mimeType": "multipart/mixed", "parts": kids}
                    return self._json(200, out)
                return self._json(404, {})

            def _calendar(self, parts, q):
                if parts[:2] == ["calendar", "calendars"] and len(parts) == 4 and parts[3] == "events":
                    cal = fake.calendars.get(urllib.parse.unquote(parts[2]))
                    if cal is None:
                        return self._json(404, {"error": {"message": "Not Found"}})
                    lo, hi = dt.datetime.fromisoformat(q["timeMin"]), dt.datetime.fromisoformat(q["timeMax"])
                    items = [e for e in cal["events"].values() if lo <= _start(e) < hi]
                    return self._json(200, {"items": sorted(items, key=_start)})
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
            "drive": f"{self.base}/drive",
            "calendar": f"{self.base}/calendar",
        }

    def issue_code(self, auth_url: str, drop: str = "") -> tuple[str, str]:
        """What Google does when you approve: a code bound to the PKCE challenge. Returns (code, state).
        drop: words of a scope the user unticked on the consent screen (it isn't granted)."""
        q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(auth_url).query).items()}
        self.scope = " ".join(s for s in q["scope"].split() if not drop or drop not in s)
        code = f"code-{len(self.challenges) + 1}"
        self.challenges[code] = q["code_challenge"]
        return code, q["state"]

    def add_mail(self, mid: str, frm: str, subject: str, text: str, labels=None, **kw) -> None:
        ms = int((dt.datetime.now() - dt.timedelta(hours=len(self.mail) + 1)).timestamp() * 1000)
        self.mail[mid] = {
            "from": frm,
            "subject": subject,
            "text": text,
            "labels": labels or ["INBOX", "CATEGORY_PERSONAL"],
            "thread": f"t-{mid}",
            "ms": ms,
            **kw,
        }

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def _meta(f: dict) -> dict:
    return {"name": f["name"], "mimeType": f["mimeType"], "size": str(len(f.get("data", b"")))}


def _start(e: dict) -> dt.datetime:
    return dt.datetime.fromisoformat(e["start"]["dateTime"])
