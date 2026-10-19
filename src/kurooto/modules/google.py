"""Google: sign in with your Google account so Kurooto can read Google Classroom (assignments go into Deadlines, new
posts come to Telegram) and save email drafts in Gmail (it never sends anything: drafts wait in Gmail for you).
More Google features build on this sign-in, each off until you set it up, and each asks Google for its own
permission when you do: Classroom → notes, the mail digest, reply drafts and the Agent plan calendar.

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
        # the features below ask for their own permission; each is set when you set that feature up
        "classroom_notes": False,  # Classroom materials and attached Drive files (read-only)
        "mail_digest": False,  # read Gmail (read-only)
        "reply_drafts": False,  # reply drafts in Gmail, sent only when you tap Send
        "agent_calendar": False,  # Kurooto's own "Agent plan" calendar
        "endpoints": {
            "auth": "https://accounts.google.com/o/oauth2/v2/auth",
            "token": "https://oauth2.googleapis.com/token",  # noqa: S105 (an address)
            "classroom": "https://classroom.googleapis.com/v1",
            "gmail": "https://gmail.googleapis.com/gmail/v1",
            "drive": "https://www.googleapis.com/drive/v3",
            "calendar": "https://www.googleapis.com/calendar/v3",
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
    "classroom_notes": [
        "https://www.googleapis.com/auth/classroom.courses.readonly",
        "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
        "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly",
        "https://www.googleapis.com/auth/classroom.announcements.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ],
    "mail_digest": ["https://www.googleapis.com/auth/gmail.readonly"],
    "reply_drafts": ["https://www.googleapis.com/auth/gmail.compose"],
    "agent_calendar": ["https://www.googleapis.com/auth/calendar.app.created"],
}
BASE = ("classroom", "gmail_drafts")  # what the Google feature itself needs; the rest belongs to its add-on features
PARTS = {  # an add-on's setting -> the feature (module id) that uses it
    "classroom_notes": "classroom_notes",
    "mail_digest": "mail_digest",
    "reply_drafts": "reply_drafts",
    "agent_calendar": "agent_plan",
}
UNVERIFIED = (
    'Google shows "Google hasn\'t verified this app" because the app is your own Google Cloud project: Advanced → '
    "Go to (your project). Turn on the API it needs in that project first (link below)."
)


class NeedsSignIn(Exception):
    pass


class GoogleError(RuntimeError):
    """Google answered with an error; .code is the HTTP status (404: it's gone, 403: no permission)."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


class Google(Module):
    id = "google"
    title = "Google (Classroom, Gmail drafts)"
    description = (
        "Classroom assignments into Deadlines and new posts on Telegram; email drafts saved in Gmail (never sent)."
    )
    privacy = (
        "Kurooto reads Classroom and writes Gmail drafts with your own Google client and sign-in; nothing is sent from "
        "your Gmail (Email reply drafts sends one only when you tap Send). Tokens stay in this computer's keychain."
    )

    def ep(self, name: str) -> str:
        return (self.setting("endpoints") or {})[name].rstrip("/")

    def scopes(self) -> list[str]:
        """Every permission to ask Google for: this feature's, and those of the add-ons you've set up."""
        return list(dict.fromkeys(s for key, ss in SCOPES.items() if self.setting(key) for s in ss))

    def granted(self, part: str) -> bool:
        """Has Google OK'd everything this part needs?"""
        return set(SCOPES[part]) <= set((self.tokens().get("scope") or "").split())

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
        if not all(self.granted(p) for p in BASE if self.setting(p)):
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
        turned_on = []
        for part, mid in PARTS.items():  # a feature you just set up turns on once Google has OK'd it
            m = self.app.modules.get(mid)
            if m and self.setting(part) and not self.app.is_on(mid) and self.app.is_on(self.id) and self.granted(part):
                if self.app.enable(mid)[0]:
                    turned_on.append(m.title)
        on = f" Turned on: {', '.join(turned_on)}." if turned_on else ""
        return True, f"Signed in with Google.{on} You can close this tab."

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
            "Google sign-in expired (or access was removed), so the Google features are paused. Open Kurooto's "
            "dashboard → Features → Google → Set up to sign in again.",
            kind="info",
            urgent=True,
        )
        self.app.events.emit("google_signin_lost")

    def api(
        self, service: str, path: str, body: dict | None = None, method: str | None = None, raw: int = 0
    ) -> dict | bytes:
        """Call a Google API. raw=N: the response's bytes (a file), at most N of them (more raises GoogleError 413)."""
        req = urllib.request.Request(  # noqa: S310 (Google's APIs, https)
            f"{self.ep(service)}{path}",
            data=None if body is None else json.dumps(body).encode(),
            method=method or ("POST" if body is not None else "GET"),
            headers={"Authorization": f"Bearer {self.access_token()}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120 if raw else 60) as r:  # noqa: S310
                if raw:
                    data = r.read(raw + 1)
                    if len(data) > raw:
                        raise GoogleError(413, f"larger than {raw // 2**20} MB")
                    return data
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code == 401:
                self._lost_signin()
                raise NeedsSignIn("Google refused the sign-in") from None
            try:
                msg = json.loads(e.read()).get("error", {}).get("message", "")
            except (ValueError, AttributeError):
                msg = ""
            raise GoogleError(e.code, f"Google said {e.code}: {msg}"[:300]) from None

    def pages(self, service: str, path: str, key: str, params: dict, limit: int = 5):
        """The items of a list call, page after page (at most `limit` pages)."""
        token = None
        for _ in range(limit):
            q = {**params, **({"pageToken": token} if token else {})}
            r = self.api(service, f"{path}?{urllib.parse.urlencode(q, doseq=True)}")
            yield from r.get(key, [])
            token = r.get("nextPageToken")
            if not token:
                return

    def want(self, part: str) -> str:
        """Mark an add-on as wanted and return the sign-in address that asks Google for its permission."""
        self.app.settings.set(f"google.{part}", True)
        return self.start_signin()

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

    def sync_now(self) -> tuple[bool | None, str]:
        """Everything Google, now (/sync all): Classroom deadlines and posts, then the add-ons you have on.
        (ok, one short line); None: skipped."""
        if not self.ready()[0]:
            return None, f"not ready: {self.ready()[1]}"
        ok, said = True, []
        r = self.classroom_sync()
        if r.get("error"):
            ok = False
            said.append(f"Classroom: {r['error']}")
        elif not r.get("skipped"):
            said.append(f"Classroom: {r['deadlines']} due, {r['posts']} new posts")
        for mid, run, what in (("classroom_notes", "sync", "items"), ("mail_digest", "digest", "read")):
            m = self.app.modules.get(mid)
            if m is None or not self.app.is_on(mid):
                continue
            r = getattr(m, run)()
            if r.get("error"):
                ok = False
            said.append(f"{m.title}: {r.get('error') or r.get('skipped') or f'{r.get(what, 0)} new for the AI'}")
        return ok, "; ".join(said) or "nothing to do"

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


# ------------------------------------------------------------------------------------------- shared helpers
def not_interested(app, text: str) -> str | None:
    """The topic on your not-interested list that this text is about, or None."""
    try:
        from kurooto.core.notinterested import is_ignored
    except ImportError:
        return None
    try:
        return is_ignored(app, text or "")
    except Exception:
        return None


def not_interested_list(app) -> list[str]:
    try:
        from kurooto.core.notinterested import ignored_topics
    except ImportError:
        return []
    try:
        return list(ignored_topics(app))
    except Exception:
        return []


def shipped_skill(name: str, args: str) -> tuple[str, str]:
    """A skill that ships with Kurooto: (its text with the arguments in, its effort)."""
    from importlib import resources

    text = (resources.files("kurooto.data") / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
    effort = "auto"
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if m:
        e = re.search(r"^effort:\s*['\"]?(\w+)", m.group(1), re.M)
        effort = e.group(1) if e else "auto"
        text = text[m.end() :]
    if "$ARGUMENTS" in text:
        text = text.replace("$ARGUMENTS", args)
    elif args:
        text += f"\n\nWhat they gave you:\n{args}"
    rules = (
        "\n\nRules: use Kurooto's tools to read and write notes; never delete or reword what's already written; "
        "send nothing to anyone but the user."
    )
    return text + rules, effort


def run_skill(app, name: str, args: str, title: str, then: str, payload: dict, quiet: bool = True) -> str:
    """Run one of Kurooto's skills as unattended background work (it waits for the charger on battery)."""
    sk = app.modules.get("skills")
    if sk is not None and app.is_on("skills") and hasattr(sk, "run"):
        return sk.run(name, args=args, then=then, then_payload=payload, quiet=quiet, background=True, title=title)
    prompt, effort = None, "auto"
    try:
        from kurooto.modules.skills import load_skill, skill_prompt

        prompt = skill_prompt(app, name, args)
        found = load_skill(app, name)
        effort = getattr(found, "effort", "auto") or "auto"
    except ImportError:
        pass
    if prompt is None:
        prompt, effort = shipped_skill(name, args)
    return app.jobs.submit(
        prompt, title=title, effort=effort, quiet=quiet, then=then, then_payload=payload, background=True
    )


class GooglePart(Module):
    """A Google feature that needs one more permission from Google: setting it up asks for it (one sign-in), and it
    turns on by itself once Google has OK'd it."""

    part = ""  # its google.<part> setting and SCOPES key
    requires = ("google",)
    permission = ""  # plain words: what Google will ask you to allow, and what Kurooto reads or writes
    api_link: tuple[str, str] | None = None  # the API to turn on in your Google Cloud project

    @property
    def google(self) -> Google:
        return self.app.modules["google"]

    def ready(self):
        g = self.app.modules.get("google")
        if g is None:
            return False, "needs the Google feature"
        ok, why = g.ready()
        if not ok:
            return False, f"Google first: {why}"
        if not g.granted(self.part):
            return False, "needs Google's OK for this: Set up, then sign in"
        return True, ""

    def allowed(self) -> bool:
        """Ready to run? If Google's OK is missing, say so (at most once a day) and how to fix it."""
        ok, why = self.ready()
        if ok:
            return True
        g = self.app.modules.get("google")
        if g is None or not g.ready()[0]:
            return False  # Google's own sign-in is the problem, and it says so itself
        flag = self.app.paths.state / f"google-needs-{self.part}"
        if not flag.exists() or time.time() - flag.stat().st_mtime > 86400:
            flag.touch()
            self.app.notify(
                f"{self.title} is paused: {why}. On this computer: Kurooto's dashboard → Features → {self.title} → "
                "Save, then sign in with Google.",
                kind="info",
            )
            self.app.events.emit("google_needs_ok", part=self.part)
        return False

    def setup_form(self) -> dict:
        return {
            "intro": f"{self.permission} Press Save and sign in with Google again to allow it. {UNVERIFIED}",
            "links": [list(self.api_link)] if self.api_link else [],
            "fields": [],
        }

    def configure(self, values: dict) -> dict:
        g = self.app.modules.get("google")
        if g is None or not g.client() or not g.tokens().get("refresh_token"):
            return {"ok": False, "message": "Set up the Google feature first (its own card), then this one."}
        return {
            "ok": True,
            "message": f"Sign in with Google in the tab that opened; {self.title} turns on when you're back.",
            "open": g.want(self.part),
        }
