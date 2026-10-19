"""Google: sign in with your Google account so Kurooto can read Google Classroom (assignments go into Deadlines, new
posts come to Telegram) and save email drafts in Gmail (it never sends anything: drafts wait in Gmail for you).

It uses your own Google "OAuth client" (a free Google Cloud project only you use), so no one else's app ever holds
your Google access. The wizard walks you through making one (about 10 minutes). Google shows "Google hasn't
verified this app" when you sign in: that's expected for a personal client (Advanced → Go to Kurooto).
For just your calendar, the Calendar feature's private iCal link is much simpler.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage

from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Module

register_defaults(
    "google",
    {
        "classroom": True,  # read Classroom (courses, assignments, announcements)
        "gmail_drafts": False,  # save drafts in Gmail (asked for separately: Google calls it a restricted permission)
        "classroom_every": "every 3h",
        "endpoints": {
            "auth": "https://accounts.google.com/o/oauth2/v2/auth",
            "token": "https://oauth2.googleapis.com/token",  # noqa: S105 (an address)
            "classroom": "https://classroom.googleapis.com/v1",
            "gmail": "https://gmail.googleapis.com/gmail/v1",
        },
    },
)
CLIENT = "google.client"  # the OAuth client JSON you downloaded
TOKENS = "google.tokens"  # noqa: S105 (the secret's name)
SCOPES = {
    "classroom": [
        "https://www.googleapis.com/auth/classroom.courses.readonly",
        "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
        "https://www.googleapis.com/auth/classroom.announcements.readonly",
    ],
    "gmail_drafts": ["https://www.googleapis.com/auth/gmail.compose"],
}


class NeedsSignIn(Exception):
    pass


class Google(Module):
    id = "google"
    title = "Google (Classroom, Gmail drafts)"
    description = (
        "Classroom assignments into Deadlines and new posts on Telegram; email drafts saved in Gmail (never sent)."
    )
    privacy = (
        "Kurooto reads Classroom and writes Gmail drafts with your own Google client and sign-in; nothing is sent from "
        "your Gmail. Tokens stay in this computer's keychain."
    )

    def ep(self, name: str) -> str:
        return (self.setting("endpoints") or {})[name].rstrip("/")

    def scopes(self) -> list[str]:
        return [s for key, ss in SCOPES.items() if self.setting(key) for s in ss]

    # ----------------------------------------------------------------------------------- client
    def client(self) -> dict | None:
        try:
            c = json.loads(self.app.secrets.get(CLIENT) or "null")
        except ValueError:
            return None
        return (c or {}).get("installed") or c

    def set_client(self, text: str) -> tuple[bool, str]:
        try:
            c = json.loads(text)
        except ValueError:
            return False, "That isn't the JSON file Google gave you (Download JSON on the OAuth client)."
        inner = c.get("installed") or {}
        if c.get("web"):
            return False, 'That client is a "Web application"; make one of type "Desktop app" instead.'
        if not inner.get("client_id") or not inner.get("client_secret"):
            return False, "That file has no client_id/client_secret."
        self.app.secrets.set(CLIENT, json.dumps({"installed": {k: inner[k] for k in ("client_id", "client_secret")}}))
        return True, "Saved your Google client. Now sign in."

    def tokens(self) -> dict:
        try:
            return json.loads(self.app.secrets.get(TOKENS) or "{}")
        except ValueError:
            return {}

    def ready(self):
        if not self.client():
            return False, "needs your Google OAuth client (the wizard shows how)"
        t = self.tokens()
        if not t.get("refresh_token"):
            return False, "sign in with Google"
        missing = set(self.scopes()) - set((t.get("scope") or "").split())
        if missing:
            return False, "sign in again: a newly chosen part needs Google's OK"
        return True, ""

    # ---------------------------------------------------------------------------------- sign-in
    def redirect_uri(self) -> str:
        return f"http://127.0.0.1:{getattr(self.app, 'web_port', None) or 8770}/oauth/google"

    def start_signin(self) -> str:
        """The Google sign-in page's address (PKCE; comes back to this computer's own page)."""
        c = self.client()
        if not c:
            raise NeedsSignIn("add your Google client first")
        verifier = secrets.token_urlsafe(64)
        state = secrets.token_urlsafe(24)
        jsave(self.app.paths.state / "google-signin.json", {"state": state, "verifier": verifier, "at": time.time()})
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        q = {
            "client_id": c["client_id"],
            "redirect_uri": self.redirect_uri(),
            "response_type": "code",
            "scope": " ".join(self.scopes()),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.ep('auth')}?{urllib.parse.urlencode(q)}"

    def finish_signin(self, code: str, state: str) -> tuple[bool, str]:
        f = self.app.paths.state / "google-signin.json"
        pending = jload(f, {}) or {}
        f.unlink(missing_ok=True)  # single use, whatever happens
        if not pending or not secrets.compare_digest(str(state), pending.get("state", "")):
            return False, "That sign-in link is stale. Start the sign-in again from Kurooto."
        if time.time() - pending.get("at", 0) > 900:
            return False, "That sign-in took too long. Start it again."
        c = self.client()
        try:
            t = self._token_call(
                {
                    "code": code,
                    "client_id": c["client_id"],
                    "client_secret": c["client_secret"],
                    "redirect_uri": self.redirect_uri(),
                    "grant_type": "authorization_code",
                    "code_verifier": pending["verifier"],
                }
            )
        except Exception as e:
            return False, f"Google didn't finish the sign-in: {e}"[:300]
        if not t.get("refresh_token"):
            return (
                False,
                "Google didn't give a lasting sign-in. Remove Kurooto's access in your Google account and try again.",
            )
        self._save_tokens(t)
        self.app.events.emit("google_signed_in")
        return True, "Signed in with Google. You can close this tab."

    def _token_call(self, form: dict) -> dict:
        req = urllib.request.Request(self.ep("token"), data=urllib.parse.urlencode(form).encode())  # noqa: S310 (https)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read())
            except ValueError:
                err = {}
            if err.get("error") == "invalid_grant":
                raise NeedsSignIn("Google's sign-in expired or was removed") from None
            raise RuntimeError(err.get("error_description") or err.get("error") or f"HTTP {e.code}") from None

    def _save_tokens(self, t: dict) -> None:
        old = self.tokens()
        new = {
            "refresh_token": t.get("refresh_token") or old.get("refresh_token"),
            "access_token": t.get("access_token"),
            "expires": time.time() + int(t.get("expires_in", 3600)) - 60,
            "scope": t.get("scope") or old.get("scope", ""),
        }
        self.app.secrets.set(TOKENS, json.dumps(new))

    def access_token(self) -> str:
        with Lock(self.app.paths.state, "google-token"):
            t = self.tokens()
            if t.get("access_token") and t.get("expires", 0) > time.time():
                return t["access_token"]
            if not t.get("refresh_token"):
                raise NeedsSignIn("not signed in")
            c = self.client() or {}
            try:
                fresh = self._token_call(
                    {
                        "client_id": c.get("client_id"),
                        "client_secret": c.get("client_secret"),
                        "refresh_token": t["refresh_token"],
                        "grant_type": "refresh_token",
                    }
                )
            except NeedsSignIn:
                self._lost_signin()
                raise
            self._save_tokens(fresh)
            return fresh["access_token"]

    def _lost_signin(self) -> None:
        t = self.tokens()
        t.pop("refresh_token", None)
        self.app.secrets.set(TOKENS, json.dumps(t))
        self.app.notify(
            "Google sign-in expired (or access was removed), so Classroom and Gmail drafts are paused. Open Kurooto's "
            "dashboard → Features → Google → Set up to sign in again.",
            kind="info",
            urgent=True,
        )
        self.app.events.emit("google_signin_lost")

    def api(self, service: str, path: str, body: dict | None = None, method: str | None = None) -> dict:
        req = urllib.request.Request(  # noqa: S310 (Google's APIs, https)
            f"{self.ep(service)}{path}",
            data=None if body is None else json.dumps(body).encode(),
            method=method or ("POST" if body is not None else "GET"),
            headers={"Authorization": f"Bearer {self.access_token()}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code == 401:
                self._lost_signin()
                raise NeedsSignIn("Google refused the sign-in") from None
            try:
                msg = json.loads(e.read()).get("error", {}).get("message", "")
            except ValueError:
                msg = ""
            raise RuntimeError(f"Google said {e.code}: {msg}"[:300]) from None

    # -------------------------------------------------------------------------------- Classroom
    def start(self):
        if self.setting("classroom"):
            self.every("classroom", self.setting("classroom_every") or "every 3h", lambda p: self.classroom_sync())

    def classroom_sync(self) -> dict:
        if not self.ready()[0] or not self.setting("classroom"):
            return {"skipped": True}
        seen_file = self.app.paths.state / "google-classroom.json"
        seen = jload(seen_file, {}) or {}
        first = not seen
        out = {"deadlines": 0, "done": 0, "posts": 0}
        dl = self.app.modules.get("deadlines") if self.app.is_on("deadlines") else None
        try:
            courses = self.api("classroom", "/courses?studentId=me&courseStates=ACTIVE&pageSize=50").get("courses", [])
            for c in courses:
                cid, cname = c["id"], c.get("name", "a course")
                work = self.api("classroom", f"/courses/{cid}/courseWork?pageSize=30&orderBy=dueDate%20desc").get(
                    "courseWork", []
                )
                for w in work:
                    due = due_of(w)
                    if not due or due < dt.datetime.now() - dt.timedelta(days=2):
                        continue
                    title = f"{cname}: {w.get('title', 'assignment')}"
                    if dl:
                        dl.add(title, due, source="classroom")
                        out["deadlines"] += 1
                        subs = self.api(
                            "classroom", f"/courses/{cid}/courseWork/{w['id']}/studentSubmissions?userId=me"
                        )
                        state = ((subs.get("studentSubmissions") or [{}])[0]).get("state")
                        if state in ("TURNED_IN", "RETURNED") and dl.mark_done(title, due):
                            out["done"] += 1
                posts = self.api("classroom", f"/courses/{cid}/announcements?pageSize=10").get("announcements", [])
                for a in posts:
                    key = f"a:{a['id']}"
                    if key in seen:
                        continue
                    seen[key] = a.get("updateTime", "")
                    if not first:  # the first sync only learns what's already there
                        text = re.sub(r"\s+", " ", a.get("text", ""))[:400]
                        self.app.notify(
                            f"New in {cname}: {text}",
                            kind="info",
                            buttons=[[("Open", {"url": a.get("alternateLink", "https://classroom.google.com")})]]
                            if a.get("alternateLink")
                            else None,
                        )
                        out["posts"] += 1
        except NeedsSignIn:
            return {"error": "needs sign-in"}
        except Exception as e:
            self.app.events.emit("google_failed", error=str(e)[:200])
            return {"error": str(e)[:200]}
        jsave(seen_file, dict(list(seen.items())[-2000:]))
        self.app.events.emit("classroom_synced", **out)
        return out

    # ------------------------------------------------------------------------------ Gmail drafts
    def make_draft(self, to: str, subject: str, body: str) -> str:
        if not self.setting("gmail_drafts"):
            return "Gmail drafts are off (Settings → google.gmail_drafts, then sign in again)."
        msg = EmailMessage()
        msg["To"], msg["Subject"] = to, subject
        msg.set_content(body)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        try:
            self.api("gmail", "/users/me/drafts", {"message": {"raw": raw}})
        except NeedsSignIn:
            return "Google sign-in expired; sign in again from the dashboard."
        self.app.events.emit("gmail_draft")
        return f'Draft saved in Gmail: "{subject}" to {to}. Open Gmail to check it and send it yourself.'

    def commands(self):
        out = [Command("classroom", "check Google Classroom now", lambda m, a: self._classroom_now())]
        if self.setting("gmail_drafts"):
            out.append(
                Command(
                    "draft",
                    "an email draft in Gmail: /draft someone@example.com what it should say",
                    self._draft,
                    usage="/draft <to> <what to say>",
                )
            )
        return out

    def _classroom_now(self) -> str:
        r = self.classroom_sync()
        if r.get("error"):
            return f"Couldn't check Classroom: {r['error']}"
        n = {k: r.get(k, 0) for k in ("deadlines", "done", "posts")}
        return f"Classroom: {n['deadlines']} upcoming assignments, {n['done']} handed in, {n['posts']} new posts."

    def _draft(self, msg: Incoming, arg: str) -> str:
        m = re.match(r"(\S+@\S+)\s+(.+)", arg, re.S)
        if not m:
            return "Usage: /draft someone@example.com what the email should say"
        to, what = m.group(1), m.group(2).strip()
        if "|" in what:  # /draft to | subject | body: no AI needed
            subject, _, body = what.strip().lstrip("|").partition("|")
            if not subject.strip() or not body.strip():
                return "Usage: /draft someone@example.com | subject | the email"
            return self.make_draft(to, subject.strip(), body.strip())
        if not self.app.is_on("chat"):
            return "Turn on Chat for AI-written drafts, or write it yourself: /draft to | subject | body"
        self.app.jobs.then_actions["google.draft"] = self._draft_done
        self.app.jobs.submit(
            f"Write an email to {to}. What it should say: {what}\n\nReply with exactly:\nSubject: <subject>\n\n<body>\n"
            "Plain text, the sender's voice, no placeholders. Don't send anything; it becomes a draft.",
            title=f"Email draft to {to}",
            quiet=True,
            then="google.draft",
            then_payload={"to": to},
            text_only=True,
        )
        return "Writing the draft…"

    def _draft_done(self, job, result, payload) -> None:
        if not result.ok:
            self.app.notify(f"Couldn't write the draft: {result.detail or 'the AI failed'}", kind="result")
            return
        text = result.text.strip()
        m = re.match(r"(?is)\s*subject:\s*(.+?)\n(.*)", text)
        subject, body = (m.group(1).strip(), m.group(2).strip()) if m else ("(no subject)", text)
        self.app.notify(self.make_draft(payload["to"], subject, body), kind="result")

    # ------------------------------------------------------------------------------------- setup
    def setup_form(self) -> dict:
        return {
            "intro": (
                "About 10 minutes, once. 1. Make a Google Cloud project (any name). 2. Turn on the Google "
                "Classroom API (and the Gmail API if you want drafts). 3. OAuth consent screen: External, your email "
                'as the contact, then Publish app ("In production": otherwise Google signs you out every 7 days). '
                "4. Credentials → Create credentials → OAuth client ID → Desktop app → Download JSON. 5. Paste the "
                "file's contents here, then sign in. Google will say the app isn't verified: Advanced → Go to (your "
                "project)."
            ),
            "links": [
                ["1. New project", "https://console.cloud.google.com/projectcreate"],
                ["2. Classroom API", "https://console.cloud.google.com/apis/library/classroom.googleapis.com"],
                ["2. Gmail API", "https://console.cloud.google.com/apis/library/gmail.googleapis.com"],
                ["3. Consent screen", "https://console.cloud.google.com/auth/overview"],
                ["4. Credentials", "https://console.cloud.google.com/auth/clients"],
            ],
            "fields": [
                {
                    "name": "client",
                    "label": "OAuth client JSON",
                    "type": "textarea",
                    "placeholder": '{"installed": {"client_id": …}}',
                }
            ],
        }

    def configure(self, values: dict) -> dict:
        if values.get("client"):
            ok, msg = self.set_client(str(values["client"]))
            if not ok:
                return {"ok": False, "message": msg}
        if not self.client():
            return {"ok": False, "message": "Paste your OAuth client JSON first."}
        return {
            "ok": True,
            "message": "Sign in with Google in the tab that opened, then come back.",
            "open": self.start_signin(),
        }


def due_of(w: dict) -> dt.datetime | None:
    """Classroom's dueDate/dueTime (UTC) as local time, or None."""
    d = w.get("dueDate")
    if not d:
        return None
    t = w.get("dueTime")
    try:
        if not t:  # a date only: the end of that day, your time
            return dt.datetime(d["year"], d["month"], d["day"], 23, 59)
        utc = dt.datetime(d["year"], d["month"], d["day"], t.get("hours", 0), t.get("minutes", 0), tzinfo=dt.UTC)
    except (KeyError, ValueError):
        return None
    return utc.astimezone().replace(tzinfo=None)
