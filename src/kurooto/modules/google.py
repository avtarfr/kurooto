"""Google: sign in with your Google account so Kurooto can read Google Classroom (assignments go into Deadlines, new
posts come to Telegram) and save email drafts in Gmail (it never sends anything: drafts wait in Gmail for you).
More Google features build on this sign-in, each off until you set it up, and each asks Google for its own
permission when you do: Classroom → notes, the mail digest (and its copy by email), reply drafts, the Agent plan
calendar, Google Calendar and Drive upload.

Several Google accounts (a personal one and a school one, say): the first you sign in with is "main"; each feature
uses main unless you give it another account on its card (a new name there signs that account in) or with
/google use <feature> <account>. Each account has its own sign-in and only the permissions of the features that use
it. /google lists them.

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
from kurooto.update.updater import PAGES

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
        "calendar_read": False,  # your calendars, read-only (Google Calendar)
        "digest_email": False,  # the mail digest emailed to yourself (send only)
        "drive_upload": False,  # files you send yourself, into a Kurooto folder in Drive (its own files only)
        "accounts": ["main"],  # your Google accounts by name; "main" is the first one you signed in with
        # which account each feature uses: {"mail_digest": "school", "calendar_read": ["main", "school"]}; unset: main
        "use": {},
        "endpoints": {
            "auth": "https://accounts.google.com/o/oauth2/v2/auth",
            "token": "https://oauth2.googleapis.com/token",  # noqa: S105 (an address)
            "classroom": "https://classroom.googleapis.com/v1",
            "gmail": "https://gmail.googleapis.com/gmail/v1",
            "drive": "https://www.googleapis.com/drive/v3",
            "calendar": "https://www.googleapis.com/calendar/v3",
            "drive_upload": "https://www.googleapis.com/upload/drive/v3",
        },
    },
)
CLIENT = "google.client"  # the OAuth client JSON you downloaded
TOKENS = "google.tokens"  # noqa: S105 (the secret's name; another account's is google.tokens.<name>)
MAIN = "main"
ACCOUNT = re.compile(r"^[a-z0-9][a-z0-9-]{0,23}$")
IDENTITY = ["openid", "https://www.googleapis.com/auth/userinfo.email"]  # which Google account it is (its address)
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
    "calendar_read": ["https://www.googleapis.com/auth/calendar.readonly"],
    "digest_email": ["https://www.googleapis.com/auth/gmail.send", *IDENTITY],
    "drive_upload": ["https://www.googleapis.com/auth/drive.file"],
}
BASE = ("classroom", "gmail_drafts")  # what the Google feature itself needs; the rest belongs to its add-on features
PARTS = {  # an add-on's setting -> the feature (module id) that uses it
    "classroom_notes": "classroom_notes",
    "mail_digest": "mail_digest",
    "reply_drafts": "reply_drafts",
    "agent_calendar": "agent_plan",
    "calendar_read": "google_calendar",
    "digest_email": "digest_email",
    "drive_upload": "drive_upload",
}
FOLLOWS = {"reply_drafts": "mail_digest"}  # always the same account: drafts answer mail in the digest's mailbox
MULTI = ("calendar_read",)  # features that may use several accounts at once
WORDS = {  # what you may call a feature in /google use
    "classroom": "classroom",
    "drafts": "gmail_drafts",
    "gmail_drafts": "gmail_drafts",
    "calendar": "calendar_read",
    "mail": "mail_digest",
    "email": "digest_email",
    "drive": "drive_upload",
    "plan": "agent_calendar",
    "blocks": "agent_calendar",
    **{mid: part for part, mid in PARTS.items()},
    **{part: part for part in PARTS},
}
# The beginner's setup, also in docs/MANUAL.md ("Google: setting up your own sign-in (step by step)")
GUIDE = "https://github.com/avtarfr/kurooto/blob/main/docs/MANUAL.md#google-setting-up-your-own-sign-in-step-by-step"
SITE = PAGES.rstrip("/") + "/"
SETUP_VALUES = [  # what the Branding page asks for: the card has a copy button for each
    ["App name", "Kurooto"],
    ["Application home page", SITE],
    ["Application privacy policy link", SITE + "privacy.html"],
    ["Authorized domain", urllib.parse.urlsplit(SITE).hostname],
]
SETUP_STEPS = [
    "Create a Google Cloud project (link 1).",
    "Turn on the APIs for the Google features you want: Classroom, Gmail, Drive, Calendar (links 2).",
    "Google Auth Platform → Get started: app name Kurooto, your email, External, your email again. Then Branding: the "
    "home page, privacy link and authorized domain below (copy buttons), and Save.",
    "Audience → Publish app, so it's In production (in Testing, Google signs you out every 7 days).",
    "Clients → Create client → Desktop app → Create → Download JSON right away (Google shows the secret only once).",
    "Paste the file below (or choose it) and press Save. Google says it hasn't verified this app: it's your own "
    "project, which Google hasn't reviewed. Advanced → Go to Kurooto → Continue.",
]
SETUP_LINKS = [
    ["1. New project", "https://console.cloud.google.com/projectcreate"],
    ["2. Classroom API", "https://console.cloud.google.com/apis/library/classroom.googleapis.com"],
    ["2. Gmail API", "https://console.cloud.google.com/apis/library/gmail.googleapis.com"],
    ["2. Drive API", "https://console.cloud.google.com/apis/library/drive.googleapis.com"],
    ["2. Calendar API", "https://console.cloud.google.com/apis/library/calendar-json.googleapis.com"],
    ["3. Branding", "https://console.cloud.google.com/auth/branding"],
    ["4. Audience", "https://console.cloud.google.com/auth/audience"],
    ["5. Clients", "https://console.cloud.google.com/auth/clients"],
]
UNVERIFIED = (
    'Google shows "Google hasn\'t verified this app" because the app is your own Google Cloud project, which Google '
    "hasn't reviewed: Advanced → Go to Kurooto. Turn on the API it needs in that project first (link below)."
)


class NeedsSignIn(Exception):
    pass


class TokenError(RuntimeError):
    """Google's token endpoint said no; .code is its error ("invalid_client", ...)."""

    def __init__(self, code: str, text: str):
        super().__init__(text)
        self.code = code


# What went wrong, in plain words: errors Google sends back to the sign-in page, and from its token endpoint
SIGNIN_ERRORS = {
    "access_denied": "You pressed Cancel (or didn't allow access) on Google's page. Start the sign-in again from "
    "Kurooto and press Continue, leaving every box ticked.",
    "admin_policy_enforced": "Your organisation's Google admin doesn't allow this app for your account. Sign in with "
    "another Google account (a personal one), or ask your admin.",
    "org_internal": "This Google Cloud project only lets accounts of its own organisation sign in. Use one of those, "
    "or set the project's Audience to External.",
    "invalid_client": "Google doesn't recognise this OAuth client: it was deleted, or its secret was replaced. "
    "Download a fresh client JSON from Google Cloud (Clients), paste it in Kurooto, and sign in again.",
    "unauthorized_client": "This OAuth client isn't allowed to sign in this way: make a client of type Desktop app, "
    "paste its JSON in Kurooto, and sign in again.",
    "redirect_uri_mismatch": "This OAuth client isn't a Desktop app, so Google can't bring you back to Kurooto. Make a "
    "Desktop app client, paste its JSON in Kurooto, and sign in again.",
    "invalid_grant": "That sign-in code was already used or has expired. Start the sign-in again from Kurooto.",
}
SCOPE_WORDS = {  # what each permission is for, when its box was left unticked on Google's page
    "classroom.courses.readonly": "your Classroom courses",
    "classroom.coursework.me.readonly": "your Classroom coursework",
    "classroom.announcements.readonly": "Classroom announcements",
    "classroom.courseworkmaterials.readonly": "Classroom materials (Classroom → notes)",
    "drive.readonly": "Drive files (Classroom → notes)",
    "gmail.readonly": "reading your mail (Mail digest)",
    "gmail.compose": "Gmail drafts",
    "calendar.app.created": "the Agent plan calendar",
    "calendar.readonly": "your calendars (Google Calendar)",
    "gmail.send": "sending the digest to yourself",
    "userinfo.email": "your email address",
    "openid": "your email address",
    "drive.file": "Kurooto's own files in Drive (Drive upload)",
}


def signin_error(code: str) -> str:
    """The sign-in page came back with ?error=<code>: what it means and what to do."""
    return SIGNIN_ERRORS.get(code, f"Google's sign-in didn't finish ({code}). Start it again from Kurooto.")


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

    def scopes(self, account: str = MAIN) -> list[str]:
        """Every permission to ask this account for: those of the features you've set up that use it (and, for any
        account but main, its address, so Kurooto can show which account is which)."""
        out = [s for part in self.parts_of(account) for s in SCOPES[part]]
        if account != MAIN or not out:
            out += IDENTITY
        return list(dict.fromkeys(out))

    def granted(self, part: str, account: str | None = None) -> bool:
        """Has Google OK'd everything this part needs (on each account it uses)?"""
        names = [account] if account else self.accounts_for(part)
        return all(set(SCOPES[part]) <= set((self.tokens(a).get("scope") or "").split()) for a in names)

    # --------------------------------------------------------------------------------- accounts
    def account_names(self) -> list[str]:
        return list(dict.fromkeys([MAIN, *(a for a in self.setting("accounts") or [] if ACCOUNT.match(str(a)))]))

    def accounts_for(self, part: str) -> list[str]:
        """The accounts a feature uses (most use one; Google Calendar may read several). Main unless you chose."""
        v = (self.setting("use") or {}).get(FOLLOWS.get(part, part)) or MAIN
        names = [n for n in ([v] if isinstance(v, str) else list(v)) if ACCOUNT.match(str(n))]
        return list(dict.fromkeys(names)) or [MAIN]

    def account_for(self, part: str) -> str:
        return self.accounts_for(part)[0]

    def parts_of(self, account: str) -> list[str]:
        """The features you've set up that use this account."""
        return [p for p in SCOPES if self.setting(p) and account in self.accounts_for(p)]

    def as_account(self, account: str) -> Account:
        return Account(self, account)

    def email(self, account: str = MAIN) -> str:
        return self.tokens(account).get("email") or ""

    def choose(self, part: str, names: str | list[str]) -> tuple[bool, str]:
        """Which account(s) a feature uses: "school", or "main, school" for Google Calendar. A new name is added."""
        raw = names.split(",") if isinstance(names, str) else list(names)
        picked = list(dict.fromkeys(re.sub(r"\s+", "-", str(n).strip().lower()) for n in raw if str(n).strip()))
        if not picked:
            return True, ""
        bad = [n for n in picked if not ACCOUNT.match(n)]
        if bad:
            return False, f"An account name is a short word (letters, digits, -), like school: not {bad[0]!r}."
        if len(picked) > 1 and part not in MULTI:
            return False, "This feature uses one Google account."
        part = FOLLOWS.get(part, part)
        self.app.settings.set("google.accounts", list(dict.fromkeys([*self.account_names(), *picked])))
        self.app.settings.set(f"google.use.{part}", picked if part in MULTI else picked[0])
        self.app.events.emit("google_account_chosen", part=part, accounts=len(picked), new=picked[0] != MAIN)
        return True, ", ".join(picked)

    def forget(self, account: str) -> str:
        """Forget another account's sign-in on this computer; its features go back to main."""
        if account == MAIN or account not in self.account_names():
            return "Not one of your other accounts (/google lists them; main stays)."
        self.app.secrets.delete(f"{TOKENS}.{account}")
        self.app.settings.set("google.accounts", [a for a in self.account_names() if a != account])
        use = dict(self.setting("use") or {})
        for part, v in list(use.items()):
            left = [n for n in ([v] if isinstance(v, str) else v) if n != account]
            use[part] = (left if part in MULTI else left[0]) if left else MAIN
        self.app.settings.set("google.use", use)
        self.app.events.emit("google_account_forgotten")
        return (
            f"Forgot your {account} Google account on this computer; its features use main now. To take Kurooto's "
            "access away at Google too: myaccount.google.com/connections."
        )

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

    @staticmethod
    def _secret(account: str) -> str:
        return TOKENS if account == MAIN else f"{TOKENS}.{account}"

    def tokens(self, account: str = MAIN) -> dict:
        try:
            return json.loads(self.app.secrets.get(self._secret(account)) or "{}")
        except ValueError:
            return {}

    def signed_in(self, account: str = MAIN) -> bool:
        return bool(self.tokens(account).get("refresh_token"))

    def _base_accounts(self) -> list[str]:
        return list(dict.fromkeys(a for p in BASE if self.setting(p) for a in self.accounts_for(p))) or [MAIN]

    def ready(self):
        if not self.client():
            return False, "needs your Google OAuth client (the wizard shows how)"
        for a in self._base_accounts():
            if not self.signed_in(a):
                return False, "sign in with Google" if a == MAIN else f"sign in to your {a} Google account"
        if not all(self.granted(p) for p in BASE if self.setting(p)):
            return False, "sign in again: a newly chosen part needs Google's OK"
        return True, ""

    def _next_account(self, parts) -> str:
        """The first account these features use that isn't signed in or lacks Google's OK; main if none."""
        for p in parts:
            for a in self.accounts_for(p):
                if not self.signed_in(a) or not self.granted(p, a):
                    return a
        return MAIN

    # ---------------------------------------------------------------------------------- sign-in
    def redirect_uri(self) -> str:
        return f"http://127.0.0.1:{getattr(self.app, 'web_port', None) or 8770}/oauth/google"

    def start_signin(self, account: str = MAIN) -> str:
        """The Google sign-in page's address for one of your accounts (PKCE; comes back to this computer's own
        page). It asks for what the features using that account need."""
        c = self.client()
        if not c:
            raise NeedsSignIn("add your Google client first")
        verifier = secrets.token_urlsafe(64)
        state = secrets.token_urlsafe(24)
        jsave(
            self.app.paths.state / "google-signin.json",
            {"state": state, "verifier": verifier, "at": time.time(), "account": account},
        )
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        q = {
            "client_id": c["client_id"],
            "redirect_uri": self.redirect_uri(),
            "response_type": "code",
            "scope": " ".join(self.scopes(account)),
            "access_type": "offline",
            "prompt": "consent" if account == MAIN else "select_account consent",  # another account: pick it
            "include_granted_scopes": "true",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        if self.email(account):
            q["login_hint"] = self.email(account)
        return f"{self.ep('auth')}?{urllib.parse.urlencode(q)}"

    def finish_signin(self, code: str, state: str) -> tuple[bool, str]:
        f = self.app.paths.state / "google-signin.json"
        pending = jload(f, {}) or {}
        f.unlink(missing_ok=True)  # single use, whatever happens
        if not pending or not secrets.compare_digest(str(state), pending.get("state", "")):
            return False, (
                "This sign-in page is out of date: it was already used, or a newer sign-in was started since. Start "
                "the sign-in again from Kurooto (Save on the Google card)."
            )
        if time.time() - pending.get("at", 0) > 900:
            return (
                False,
                "That sign-in took more than 15 minutes. Start it again from Kurooto (Save on the Google card).",
            )
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
        except NeedsSignIn:
            return False, SIGNIN_ERRORS["invalid_grant"]
        except TokenError as e:
            return False, SIGNIN_ERRORS.get(e.code) or f"Google didn't finish the sign-in: {e}"[:300]
        except Exception as e:
            return False, f"Google didn't finish the sign-in: {e}"[:300]
        if not t.get("refresh_token"):
            return (
                False,
                "Google didn't give Kurooto a lasting sign-in (it does that when the app already had access). Remove "
                "Kurooto's access at myaccount.google.com/connections, then start the sign-in again from Kurooto.",
            )
        account = pending.get("account") or MAIN
        granted = set((t.get("scope") or "").split())
        missing = [x for x in self.scopes(account) if x not in granted] if t.get("scope") else []
        self._save_tokens(t, account)
        self.app.events.emit("google_signed_in", missing=len(missing), main=account == MAIN)
        turned_on = []
        for part, mid in PARTS.items():  # a feature you just set up turns on once Google has OK'd it
            m = self.app.modules.get(mid)
            if m and self.setting(part) and not self.app.is_on(mid) and self.app.is_on(self.id) and m.ready()[0]:
                if self.app.enable(mid)[0]:
                    turned_on.append(m.title)
                    for extra in getattr(m, "with_modules", ()):  # e.g. Google Calendar turns Calendar on
                        x = self.app.modules.get(extra)
                        if x and not self.app.is_on(extra) and x.ready()[0] and self.app.enable(extra)[0]:
                            turned_on.append(x.title)
        on = f" Turned on: {', '.join(turned_on)}." if turned_on else ""
        email = self.email(account)
        who = f" ({account}: {email})" if account != MAIN and email else f" ({account})" if account != MAIN else ""
        same = [a for a in self.account_names() if a != account and email and self.email(a) == email]
        if same:  # the browser picked the account that's already signed in as another name
            on += f" Note: that's the same Google account as your {same[0]} one; sign in again and pick the other."
        later = [  # a feature that also needs another account (Google Calendar from two accounts)
            f"{self.app.modules[PARTS[p]].title} also needs your {a} account: press Save on its card again."
            for p in self.parts_of(account)
            if p in PARTS and PARTS[p] in self.app.modules
            for a in self.accounts_for(p)
            if a != account and not self.granted(p, a)
        ][:1]
        on += f" {later[0]}" if later else ""
        if missing:  # boxes left unticked on Google's page: say which, and that ticking them all fixes it
            what = ", ".join(
                dict.fromkeys(SCOPE_WORDS.get(x.rsplit("/", 1)[-1], x.rsplit("/", 1)[-1]) for x in missing)
            )
            base_ok = all(self.granted(p) for p in BASE if self.setting(p))
            return base_ok, (
                f"Signed in with Google{who}.{on} Some boxes on Google's page weren't ticked, so Kurooto can't use: "
                f"{what}. Start the sign-in again from Kurooto and tick every box."
            )
        return True, f"Signed in with Google{who}.{on} You can close this tab and go back to Kurooto."

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
            raise TokenError(
                str(err.get("error") or ""), err.get("error_description") or err.get("error") or f"HTTP {e.code}"
            ) from None

    def _save_tokens(self, t: dict, account: str = MAIN) -> None:
        old = self.tokens(account)
        new = {
            "refresh_token": t.get("refresh_token") or old.get("refresh_token"),
            "access_token": t.get("access_token"),
            "expires": time.time() + int(t.get("expires_in", 3600)) - 60,
            "scope": t.get("scope") or old.get("scope", ""),
        }
        email = id_email(t.get("id_token")) or old.get("email")
        if email:
            new["email"] = email
        self.app.secrets.set(self._secret(account), json.dumps(new))

    def access_token(self, account: str = MAIN) -> str:
        with Lock(self.app.paths.state, "google-token"):
            t = self.tokens(account)
            if t.get("access_token") and t.get("expires", 0) > time.time():
                return t["access_token"]
            if not t.get("refresh_token"):
                raise NeedsSignIn("not signed in" if account == MAIN else f"your {account} account isn't signed in")
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
                self._lost_signin(account)
                raise
            self._save_tokens(fresh, account)
            return fresh["access_token"]

    def _lost_signin(self, account: str = MAIN) -> None:
        t = self.tokens(account)
        t.pop("refresh_token", None)
        self.app.secrets.set(self._secret(account), json.dumps(t))
        if account == MAIN:
            text = (
                "Google sign-in expired (or access was removed), so the Google features are paused. Open Kurooto's "
                "dashboard → Features → Google → Set up to sign in again."
            )
        else:
            uses = [
                self.app.modules[PARTS[p]].title for p in self.parts_of(account) if PARTS.get(p) in self.app.modules
            ]
            text = (
                f"The sign-in of your {account} Google account expired (or access was removed), so "
                f"{', '.join(uses) or 'what uses it'} is paused. Open Kurooto's dashboard → Features → that feature → "
                "Save, and sign in again."
            )
        self.app.notify(text, kind="info", urgent=True)
        self.app.events.emit("google_signin_lost", main=account == MAIN)

    def api(
        self,
        service: str,
        path: str,
        body: dict | None = None,
        method: str | None = None,
        raw: int = 0,
        account: str = MAIN,
    ) -> dict | bytes:
        """Call a Google API as one of your accounts. raw=N: the response's bytes (a file), at most N of them (more
        raises GoogleError 413)."""
        req = urllib.request.Request(  # noqa: S310 (Google's APIs, https)
            f"{self.ep(service)}{path}",
            data=None if body is None else json.dumps(body).encode(),
            method=method or ("POST" if body is not None else "GET"),
            headers={"Authorization": f"Bearer {self.access_token(account)}", "Content-Type": "application/json"},
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
                self._lost_signin(account)
                raise NeedsSignIn("Google refused the sign-in") from None
            try:
                msg = json.loads(e.read()).get("error", {}).get("message", "")
            except (ValueError, AttributeError):
                msg = ""
            raise GoogleError(e.code, f"Google said {e.code}: {msg}"[:300]) from None

    def pages(self, service: str, path: str, key: str, params: dict, limit: int = 5, account: str = MAIN):
        """The items of a list call, page after page (at most `limit` pages)."""
        token = None
        for _ in range(limit):
            q = {**params, **({"pageToken": token} if token else {})}
            r = self.api(service, f"{path}?{urllib.parse.urlencode(q, doseq=True)}", account=account)
            yield from r.get(key, [])
            token = r.get("nextPageToken")
            if not token:
                return

    def want(self, part: str) -> str:
        """Mark an add-on as wanted and return the sign-in address that asks Google for its permission (for the
        first of its accounts that doesn't have it yet)."""
        self.app.settings.set(f"google.{part}", True)
        return self.start_signin(self._next_account([part]))

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
        acct = self.as_account(self.account_for("classroom"))
        try:
            courses = acct.api("classroom", "/courses?studentId=me&courseStates=ACTIVE&pageSize=50").get("courses", [])
            for c in courses:
                cid, cname = c["id"], c.get("name", "a course")
                work = acct.api("classroom", f"/courses/{cid}/courseWork?pageSize=30&orderBy=dueDate%20desc").get(
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
                        subs = acct.api(
                            "classroom", f"/courses/{cid}/courseWork/{w['id']}/studentSubmissions?userId=me"
                        )
                        state = ((subs.get("studentSubmissions") or [{}])[0]).get("state")
                        if state in ("TURNED_IN", "RETURNED") and dl.mark_done(title, due):
                            out["done"] += 1
                posts = acct.api("classroom", f"/courses/{cid}/announcements?pageSize=10").get("announcements", [])
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
            self.api("gmail", "/users/me/drafts", {"message": {"raw": raw}}, account=self.account_for("gmail_drafts"))
        except NeedsSignIn:
            return "Google sign-in expired; sign in again from the dashboard."
        self.app.events.emit("gmail_draft")
        return f'Draft saved in Gmail: "{subject}" to {to}. Open Gmail to check it and send it yourself.'

    def commands(self):
        out = [
            Command("classroom", "check Google Classroom now", lambda m, a: self._classroom_now()),
            Command(
                "google",
                "your Google accounts and which feature uses which; /google use <feature> <account>",
                self._google_cmd,
                usage="/google [use <feature> <account> | forget <account>]",
            ),
        ]
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

    def accounts_text(self) -> str:
        """Each account, its address and the features that use it."""
        lines = []
        for a in self.account_names():
            uses = [
                self.app.modules[PARTS[p]].title if p in PARTS else BASE_WORDS[p]
                for p in self.parts_of(a)
                if p in BASE_WORDS or PARTS.get(p) in self.app.modules
            ]
            state = self.email(a) or ("signed in" if self.signed_in(a) else "not signed in")
            lines.append(f"- {a} ({state}): {', '.join(uses) or 'nothing uses it yet'}")
        return "Your Google accounts:\n" + "\n".join(lines)

    def _google_cmd(self, msg: Incoming, arg_text: str) -> str:
        word, _, rest = arg_text.strip().partition(" ")
        word = word.lower()
        if word == "forget":
            return self.forget(rest.strip().lower())
        if word == "use":
            what, _, names = rest.strip().partition(" ")
            part = WORDS.get(what.lower().strip())
            if not part or not names.strip():
                return (
                    "Usage: /google use <feature> <account>, e.g. /google use mail school. Features: classroom, "
                    "drafts, mail, email, calendar, plan, drive (and classroom_notes)."
                )
            ok, said = self.choose(part, names)
            if not ok:
                return said
            title = self.app.modules[PARTS[part]].title if part in PARTS and PARTS[part] in self.app.modules else ""
            title = title or BASE_WORDS.get(part, part)
            if not self.setting(part) or self.granted(part):
                return f"{title} uses {said}."
            return (
                f"{title} uses {said} now. It needs that account's OK once: on this computer, Kurooto's dashboard → "
                f"Features → {title if part in PARTS else 'Google'} → Save, and sign in."
            )
        return self.accounts_text() + (
            "\nChange one: /google use <feature> <account> (a new name adds an account). /google forget <account>."
        )

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
                "Kurooto signs in to Google with your own app registration: a free Google Cloud project only you own. "
                "10 to 15 minutes, once:"
            ),
            "steps": SETUP_STEPS,
            "guide": ["Full step-by-step guide", GUIDE],
            "copy": SETUP_VALUES,
            "links": SETUP_LINKS,
            "fields": [
                {
                    "name": "client",
                    "label": "OAuth client JSON (paste it, or choose the file you downloaded)",
                    "type": "textarea",
                    "accept": ".json,application/json",
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
        account = self._next_account([p for p in BASE if self.setting(p)])
        which = "" if account == MAIN else f" (your {account} account)"
        return {
            "ok": True,
            "message": f"Sign in with Google{which} in the tab that opened, then come back.",
            "open": self.start_signin(account),
        }


BASE_WORDS = {"classroom": "Classroom (deadlines and posts)", "gmail_drafts": "Gmail drafts"}


class Account:
    """One of your Google accounts, as a feature uses it: the Google feature's calls, made as that account."""

    def __init__(self, google: Google, name: str):
        self.g, self.name = google, name

    def api(self, service: str, path: str, body: dict | None = None, method: str | None = None, raw: int = 0):
        return self.g.api(service, path, body, method, raw, account=self.name)

    def pages(self, service: str, path: str, key: str, params: dict, limit: int = 5):
        return self.g.pages(service, path, key, params, limit, account=self.name)

    def tokens(self) -> dict:
        return self.g.tokens(self.name)

    def access_token(self) -> str:
        return self.g.access_token(self.name)

    def email(self) -> str:
        return self.g.email(self.name)

    def __getattr__(self, name: str):
        return getattr(self.g, name)


def id_email(id_token: str | None) -> str:
    """The address in the ID token Google's token endpoint gave us (asked for with "openid email")."""
    try:
        payload = str(id_token or "").split(".")[1]
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError, TypeError):
        return ""
    email = str(data.get("email") or "").lower()
    return email if re.fullmatch(r"[^@\s]+@[^@\s]+", email) else ""


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
    with_modules: tuple[str, ...] = ()  # features to turn on with it (when they're ready)

    @property
    def account(self) -> str:
        """Which of your Google accounts it uses (main unless you chose another)."""
        g = self.app.modules.get("google")
        return g.account_for(self.part) if g is not None else MAIN

    @property
    def google(self) -> Account:
        return self.app.modules["google"].as_account(self.account)

    def ready(self):
        g = self.app.modules.get("google")
        if g is None:
            return False, "needs the Google feature"
        if not g.client():
            return False, f"Google first: {g.ready()[1]}"
        for a in g.accounts_for(self.part):
            if not g.signed_in(a):
                if a == MAIN:
                    return False, f"Google first: {g.ready()[1]}"
                return False, f"needs your {a} Google account: Set up, then sign in"
        if not g.granted(self.part):
            return False, "needs Google's OK for this: Set up, then sign in"
        return True, ""

    def allowed(self) -> bool:
        """Ready to run? If Google's OK is missing, say so (at most once a day) and how to fix it."""
        ok, why = self.ready()
        if ok:
            return True
        g = self.app.modules.get("google")
        if g is None or not g.client() or not all(g.signed_in(a) for a in g.accounts_for(self.part)):
            return False  # the sign-in itself is the problem, and Google says so itself when it's lost
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
        g = self.app.modules.get("google")
        now = ", ".join(g.accounts_for(self.part)) if g is not None else MAIN
        several = " (or several: main, school)" if self.part in MULTI else ""
        return {
            "intro": f"{self.permission} Press Save and sign in with Google again to allow it. {UNVERIFIED}",
            "guide": ["Full step-by-step guide", GUIDE],
            "links": [list(self.api_link)] if self.api_link else [],
            "fields": []
            if self.part in FOLLOWS  # reply drafts: always the mail digest's account
            else [
                {
                    "name": "account",
                    "label": f"Which Google account{several}: empty keeps {now}; a new name, like school, signs in "
                    "another account",
                    "type": "text",
                    "placeholder": now,
                }
            ],
        }

    def configure(self, values: dict) -> dict:
        g = self.app.modules.get("google")
        if g is None or not g.client() or not g.signed_in(MAIN):
            return {"ok": False, "message": "Set up the Google feature first (its own card), then this one."}
        if str(values.get("account") or "").strip() and self.part not in FOLLOWS:
            ok, said = g.choose(self.part, str(values["account"]))
            if not ok:
                return {"ok": False, "message": said}
        url = g.want(self.part)
        account = g._next_account([self.part])
        which = "" if account == MAIN else f" (your {account} account)"
        return {
            "ok": True,
            "message": f"Sign in with Google{which} in the tab that opened; {self.title} turns on when you're back.",
            "open": url,
        }
