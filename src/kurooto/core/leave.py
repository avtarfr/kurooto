"""Leaving cleanly, and new keys after a lost phone or a backup that got out.

`kurooto uninstall --revoke` takes back what Kurooto set up on your accounts before it removes itself, while the keys
it needs are still on this computer:
    your call line  deleted from your Cloudflare account with its secrets and stored data (`wrangler delete`, through
                    Kurooto's own Cloudflare login), then that login is signed out. If the login has expired or is
                    for another account, you get the steps for Cloudflare's dashboard instead.
    Google          each signed-in account's access revoked at Google's revoke endpoint (Kurooto drops off your
                    account's "Third-party apps" page).
    Telegram        the bot's webhook and the messages waiting for Kurooto dropped, and the command menu Kurooto set
                    removed. The bot stays yours.
    by hand         what only you can do, with links: the GitHub token(s) for your notes, the Gemini key, the bot
                    itself, the Google client, Profile sync's branch.
Then Kurooto's keys are removed from this computer's keychain too (a plain uninstall leaves them there).

`kurooto rotate` (a lost phone, or a backup zip with your keys that got out) gives your call line new keys: this
computer's key to it, the key that signs call links, the phone notification key and channel (ntfy) and the Web Push
keys. It redeploys the line with them (the same address); the line then forgets every paired phone, the call links it
made and open pairing codes (worker.js, Line.fresh), and the running Kurooto makes a link to pair the phones you
still have again. If the redeploy fails, the old keys are put back and nothing changed. The keys only you can replace
(your bot's token, Google, the GitHub token, ...) come from the health registry's credential list (core/health.py).
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from kurooto.core import egress
from kurooto.modules.calls import deploy

Say = Callable[[str], None]
Ask = Callable[[str, dict], "dict | None"]  # the running Kurooto's local page (cli.ask_running); None: not running

GOOGLE_REVOKE = "https://oauth2.googleapis.com/revoke"
GOOGLE_CONNECTIONS = "https://myaccount.google.com/connections"
GITHUB_TOKENS = "https://github.com/settings/personal-access-tokens"  # noqa: S105 (an address)
GEMINI_KEYS = "https://aistudio.google.com/apikey"
CLOUDFLARE = "https://dash.cloudflare.com"
WRANGLER = ("node_modules", "wrangler", "bin", "wrangler.js")
GONE = re.compile(r"\b10007\b|does not exist", re.I)  # Cloudflare: no such Worker (it was deleted already)
LINE_KEYS = (  # made by deploy.ensure_secrets: missing ones are made fresh on the next deploy
    "calls.call_secret",  # signs the call links this computer makes; the line's pairings hang on it too
    "calls.connector_secret",  # this computer's key to the line
    "calls.ntfy_topic",  # the Android app's notification channel...
    "calls.ntfy_key",  # ...and the key its messages are sealed with
    "calls.vapid_jwk",  # Web Push (the iPhone app)
    "calls.vapid_public",
)
GITHUB_SECRETS = ("notes_sync.token", "calls.github_token", "profile.token")
REPLACE = {  # a credential check's id (core/health_checks.py) -> how you replace that key yourself
    "telegram": "Telegram bot: send /revoke to @BotFather for a new token, and paste it on the setup page (Telegram).",
    "google": f"Google: remove Kurooto at {GOOGLE_CONNECTIONS}, then sign in again (Features → Google → Save).",
    "notes_sync": f"GitHub token for notes: delete it at {GITHUB_TOKENS}, make a new one (the same repository, "
    "Contents: Read and write) and paste it (Features → Notes sync → Set up).",
}
INTRO = """\
New keys for your call line, for a lost phone or a backup with your keys that got out:
  - this computer's key to the line, and the key that signs call links (links sent before stop working)
  - the phone notification key and channel, and the Web Push keys
Your call line is deployed again with them (a minute or two; the same address). It then forgets every paired phone,
so you pair the phones you still have again. Reminders, scheduled calls and your notes stay as they are.
If your Gemini key got out too, paste a new one first (Settings → AI model): this takes it to your call line."""


@dataclass
class Step:
    what: str  # "Call line", "Google (school)", "Telegram"
    ok: bool | None  # True: done; False: couldn't (by_hand says what to do); None: nothing to do
    detail: str
    by_hand: str = ""

    def line(self) -> str:
        mark = {True: "ok  ", False: "FAIL", None: "--  "}[self.ok]
        return f"  {mark}  {self.what}: {self.detail}" + (f"\n        {self.by_hand}" if self.by_hand else "")


# ---------------------------------------------------------------------------------------------- the call line
def find_node(d: deploy.Deployer) -> str | None:
    """Node.js, where the call line's setup put or found it (tests put a stand-in here)."""
    return d.prereqs.items["node"].find()


def delete_line(app, say: Say = print, sign_out: bool = True) -> Step:
    """Delete your call line (and with it its secrets and stored data) through Kurooto's own Cloudflare login, then
    sign that login out. The dashboard steps when that can't be done."""
    w = app.settings.get("calls.worker") or {}
    name = str(w.get("name") or "")
    if not name:
        return Step("Call line", None, "none was set up")
    steps = (
        f"Delete it yourself: {CLOUDFLARE} → Workers & Pages → {name} → Settings → Delete (its keys and stored data "
        "go with it)."
    )
    d = deploy.Deployer(app, say, unattended=True)
    d.node = find_node(d)
    if not d.node or not d.dir.joinpath(*WRANGLER).is_file():
        return Step("Call line", False, "the Cloudflare tools Kurooto used aren't on this computer any more", steps)
    say("Checking Kurooto's Cloudflare sign-in…")
    r = d._wrangler("whoami", timeout=90)
    accounts = deploy.accounts_from_whoami(r.out)
    if r.code != 0 or not accounts or "not authenticated" in r.out.lower():
        return Step("Call line", False, "Kurooto's Cloudflare sign-in has expired", steps)
    account = str(w.get("account") or (accounts[0] if len(accounts) == 1 else ""))
    if account not in accounts:  # never delete a same-named Worker on someone else's account
        return Step("Call line", False, "the Cloudflare sign-in here isn't for the account your line is on", steps)
    d.account = account
    say(f"Deleting {name} from your Cloudflare account…")
    r = d._wrangler("delete", "--name", name, "--force", timeout=180)
    text = f"{r.out}\n{r.err}".strip()
    gone = r.code == 0 or bool(GONE.search(text))
    if sign_out:
        d._wrangler("logout", timeout=60)  # Cloudflare forgets Kurooto's sign-in too
    if not gone:
        last = (text.splitlines() or ["no answer"])[-1].strip()
        return Step("Call line", False, f"Cloudflare said: {last}"[:200], steps)
    app.settings.reset("calls.worker")  # (kept settings: a reinstall knows there's no line)
    app.events.emit("calls_line_deleted")
    signed = "; Kurooto's Cloudflare sign-in is signed out" if sign_out else ""
    return Step("Call line", True, f"{name} is deleted from your Cloudflare account, with its keys and data{signed}")


def line_set_up(app) -> bool:
    return bool((app.settings.get("calls.worker") or {}).get("url"))


def rotate_line(app, say: Say = print) -> tuple[bool, str]:
    """New keys for the call line, deployed. On any failure (or Ctrl-C) the old keys are put back."""
    if not line_set_up(app):
        return False, "Phone calls isn't set up, so there's no call line to give new keys"
    old = {k: app.secrets.get(k) for k in LINE_KEYS}
    ok, msg = False, "stopped"
    try:
        for k in LINE_KEYS:
            app.secrets.delete(k)
        deploy.ensure_secrets(app)  # all fresh at once, made as on the first setup; the deploy sends them
        ok, msg = deploy.deploy(app, say)
    finally:
        if not ok:
            for k, v in old.items():
                if v:
                    app.secrets.set(k, v)
                else:
                    app.secrets.delete(k)
    if ok:
        app.events.emit("line_rotated", keys=len(LINE_KEYS))
    return ok, msg


def pair_again(
    app,
    ask: Ask,
    say: Say = print,
    wait_s: float = 150,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict | None:
    """A pairing link from the running Kurooto, once it's linked to the line with the new key (its link drops while
    the line restarts, and it dials again by itself). None: Kurooto isn't running, or Phone calls is off."""
    if not app.is_on("calls"):
        return None
    end = clock() + wait_s
    told = False
    while True:
        r = ask("phone/pair", {})
        if r is None or r.get("ok") or clock() >= end:
            return r
        if not told:
            say("Waiting for Kurooto to link up with your call line's new key (up to a few minutes)…")
            told = True
        sleep(5)


def credentials_by_hand(app) -> list[str]:
    """The keys only you can replace, from the health registry's credential list (the features that are on), and
    your Gemini key."""
    out = []
    for c in app.health.credentials():
        out.append(REPLACE.get(c.id) or f"{c.title}: {c.help or 'replace it where you set it up.'}")
    if app.secrets.get("gemini.api_key"):
        out.append(
            f"Gemini key: delete it at {GEMINI_KEYS} and paste a new one (Settings → AI model); after this, Settings "
            "→ Features → Phone calls → Set up takes it to your call line."
        )
    return out


def rotate_command(
    yes: bool,
    ask: Ask,
    say: Say = print,
    read: Callable[[str], str] = input,
    interactive: bool = True,
    wait_s: float = 150,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """`kurooto rotate`: 0 done, 1 not done, 2 needs --yes (nobody at the keyboard)."""
    from kurooto.app import App

    app = App()
    try:
        if not line_set_up(app):
            say("Phone calls isn't set up, so there's no call line to give new keys.")
            _others(app, say, "If a backup with your keys got out, replace these yourself:")
            return 1
        say(INTRO)
        if not yes:
            if not interactive:
                say("Add --yes to go ahead (every paired phone has to pair again).")
                return 2
            try:
                answer = read("Go on? [y/N] ")
            except (EOFError, KeyboardInterrupt):
                answer = ""
            if answer.strip().lower() not in ("y", "yes"):
                say("Nothing changed.")
                return 1
        ok, msg = rotate_line(app, say)
        if not ok:
            say(f"Nothing changed: {msg}")
            return 1
        say("Your call line has new keys. Phones paired before, older call links and pairing codes no longer work.")
        _pair_steps(app, pair_again(app, ask, say, wait_s=wait_s, sleep=sleep), say)
        say(
            "Lost the phone? If it was signed in to Telegram, end that session from another device: Telegram → "
            "Settings → Devices."
        )
        if app.is_on("profile"):
            say("Profile sync is on: run `kurooto profile save` now, so a restore brings the new keys, not the old.")
        _others(app, say, "If a backup with your keys got out, also replace these (only you can):")
        return 0
    finally:
        app.close()


def _pair_steps(app, r: dict | None, say: Say) -> None:
    say("Pair the phones you still have again:")
    say("  Android: in the Kurooto app, tap Unpair this phone, then open the pairing link on the phone (or scan it).")
    say("  iPhone: delete Kurooto from the Home Screen, then open the pairing link in Safari and add it again.")
    if r and r.get("ok"):
        say(f"  Pairing link (one phone, 15 minutes): {r['link']}")
        _qr(r["link"], say)
        say("  For another phone: /phone on Telegram, or the dashboard's Phone tab → Pair a phone.")
    elif r is None and not app.is_on("calls"):
        say("  Phone calls is off: turn it on (dashboard → Features), then Phone tab → Pair a phone.")
    elif r is None:
        say("  Kurooto isn't running: `kurooto start`, then the dashboard's Phone tab → Pair a phone (or /phone).")
    else:
        why = r.get("error") or "it isn't linked to your call line yet"
        say(f"  Kurooto couldn't make a link ({why}); in a few minutes: /phone on Telegram, or the Phone tab.")


def _qr(link: str, say: Say) -> None:
    """The link as a QR code in this terminal (a phone's camera opens it)."""
    import io
    import sys

    if not sys.stdout.isatty():
        return
    try:
        import segno

        buf = io.StringIO()
        segno.make(link, error="m").terminal(out=buf, compact=True)
        say(buf.getvalue().rstrip("\n"))
    except Exception:
        pass


def _others(app, say: Say, head: str) -> None:
    lines = credentials_by_hand(app)
    if lines:
        say(head)
        for ln in lines:
            say(f"  - {ln}")


# --------------------------------------------------------------------------------------------------- Google
def _google_revoke(endpoint: str, token: str, what: str, steps: str) -> Step:
    req = urllib.request.Request(  # noqa: S310 (Google's revoke endpoint, https; a fake in tests)
        endpoint,
        data=urllib.parse.urlencode({"token": token}).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with egress.urlopen(req, "uninstall --revoke", timeout=20):
            return Step(what, True, "Kurooto's access is taken back")
    except urllib.error.HTTPError as e:
        try:
            err = str((json.loads(e.read() or b"{}") or {}).get("error") or "")
        except ValueError:
            err = ""
        if e.code == 400 and err == "invalid_token":
            return Step(what, True, "that sign-in had already ended")
        return Step(what, False, f"Google answered {e.code}", steps)
    except OSError as e:
        return Step(what, False, f"couldn't reach Google ({e})"[:160], steps)


def revoke_google(app) -> list[Step]:
    """Revoke every signed-in Google account's grant (a refresh token's revoke ends the whole grant)."""
    from kurooto.modules.google import MAIN

    g = app.modules.get("google")
    if g is None:
        return []
    endpoint = (app.settings.get("google.endpoints") or {}).get("revoke") or GOOGLE_REVOKE
    out = []
    for a in g.account_names():
        t = g.tokens(a)
        tok = t.get("refresh_token") or t.get("access_token")
        if not tok:
            continue
        who = f" (signed in as {t['email']})" if t.get("email") else ""
        out.append(
            _google_revoke(
                endpoint,
                tok,
                "Google" if a == MAIN else f"Google ({a})",
                f"Remove Kurooto yourself{who}: {GOOGLE_CONNECTIONS}",
            )
        )
    return out or [Step("Google", None, "not signed in")]


# ------------------------------------------------------------------------------------------------- Telegram
def clear_telegram(app) -> Step:
    """Drop the bot's webhook and the messages waiting for Kurooto, and the command menu Kurooto set."""
    from kurooto.modules.telegram.api import API, TelegramAPI, TelegramError

    tok = app.secrets.get("telegram.token")
    if not tok:
        return Step("Telegram", None, "no bot was set up")
    api = TelegramAPI(tok, app.settings.get("telegram.api_base") or API)
    try:
        api.call("deleteWebhook", {"drop_pending_updates": True}, timeout=20)
        api.call("deleteMyCommands", {}, timeout=20)
    except TelegramError as e:
        if e.code in (401, 404):
            return Step("Telegram", True, "your bot's token no longer works, so there's nothing to clear")
        return Step("Telegram", False, f"Telegram said: {e.description}"[:160])
    except OSError as e:
        return Step("Telegram", False, f"couldn't reach Telegram ({e})"[:160])
    return Step("Telegram", True, "your bot's webhook, waiting messages and command menu are cleared")


# ---------------------------------------------------------------------------------------- what's left to you
def by_hand(app) -> list[str]:
    """What only you can do, with links. Read before the keys are removed."""
    s, sec = app.settings, app.secrets
    out = []
    tokens = {v for k in GITHUB_SECRETS if (v := sec.get(k))}
    if tokens:
        repos = ", ".join(dict.fromkeys(r for r in (s.get("notes_sync.repo"), s.get("profile.repo")) if r))
        many = "s" if len(tokens) > 1 else ""
        out.append(
            f"GitHub: delete the token{many} you made for Kurooto{f' ({repos})' if repos else ''}: {GITHUB_TOKENS}"
        )
    if sec.get("gemini.api_key"):
        out.append(f"Gemini: if you made the key only for Kurooto, delete it: {GEMINI_KEYS}")
    if sec.get("telegram.token"):
        out.append("Telegram: the bot is still yours; send /deletebot to @BotFather to delete it.")
    if sec.get("google.client"):
        out.append(
            "Google: your OAuth client is a project on your Google Cloud account; delete the project there if you "
            "made it only for Kurooto."
        )
    if sec.get("profile.key"):
        branch = s.get("profile.branch") or "kurooto-profile"
        out.append(f"Profile sync: your repository keeps an encrypted {branch} branch; delete it if you won't be back.")
    return out


def forget_keys(app) -> int:
    """Remove every key Kurooto kept from this computer's keychain (or its file). How many there were."""
    from kurooto.modules.backups import known_secret_names

    names = set(known_secret_names(app.secrets))
    names |= {f"google.tokens.{a}" for a in app.settings.get("google.accounts") or [] if isinstance(a, str)}
    n = 0
    for name in sorted(names):
        if app.secrets.get(name) is not None:
            n += 1
        app.secrets.delete(name)
    return n


def revoke_all(app, say: Say = print) -> list[Step]:
    """Each in turn; one that breaks doesn't stop the others."""
    steps: list[Step] = []
    for what, fn in (
        ("Call line", lambda: [delete_line(app, say)]),
        ("Google", lambda: revoke_google(app)),
        ("Telegram", lambda: [clear_telegram(app)]),
    ):
        try:
            steps += fn()
        except Exception as e:
            steps.append(Step(what, False, f"{type(e).__name__}: {e}"[:200]))
    app.events.emit("revoked", done=sum(st.ok is True for st in steps), failed=sum(st.ok is False for st in steps))
    return steps


def uninstall_revoke(say: Say = print) -> bool:
    """`kurooto uninstall --revoke`, run once Kurooto is stopped and before its folders go. False: its settings
    couldn't be read, so nothing was taken back (the uninstall then stops)."""
    from kurooto.app import App

    try:
        app = App()
    except Exception as e:
        say(f"Couldn't read Kurooto's settings to take back its access: {type(e).__name__}: {e}"[:300])
        return False
    try:
        say("Taking back what Kurooto set up on your accounts…")
        left = by_hand(app)
        for st in revoke_all(app, say):
            say(st.line())
        if left:
            say("Left for you (Kurooto can't do these):")
            for ln in left:
                say(f"  - {ln}")
        n = forget_keys(app)
        if n:
            say(f"Removed Kurooto's {n} key{'s' if n != 1 else ''} from this computer's keychain.")
        return True
    finally:
        app.close()
