"""What the setup wizard (and later the dashboard) can ask for and change."""

from __future__ import annotations

import functools
import json
import os
import secrets
import threading
import time
from importlib import resources
from typing import TYPE_CHECKING

from kurooto import __version__, providers
from kurooto.core import autostart, egress, hardware, opener, setupsteps
from kurooto.core.prereqs import Prereqs
from kurooto.core.state import jload
from kurooto.modules.telegram.api import TelegramError
from kurooto.providers.base import Verdict

if TYPE_CHECKING:
    from kurooto.app import App

STARTER = ["telegram", "chat", "reminders", "checkins", "deadlines"]  # GBrain: a 0.5 GB download, so it's opt-in
# The wizard's "What do you do?": what's added to Starter for each answer ("other": Starter alone)
ROLES = {
    "student": ["subjects", "startby", "quiz", "capture", "doubts", "weekly"],
    "working": ["commitments", "startby", "calendar", "weekly"],
    "research": ["research", "commitments", "startby", "weekly"],
}
BRAIN_ORDER = [  # the first one is the ★ recommendation
    (
        "agy",
        "Recommended: Google's agent program (Antigravity), run locally on this computer; "
        "full tool access and higher limits with a Google account.",
    ),
    (
        "gemini",
        "A key from Google AI Studio. Warning: Free-tier keys have strict daily limits (20 requests/day) "
        "and exhaust quickly; best kept for Phone Calls and Voice Notes.",
    ),
    ("claude", "Advanced: if you pay for Claude, Anthropic's Claude Code, signed in with your Claude account."),
    ("ollama", "Small models on this computer: private and offline, but much weaker than the others."),
    ("custom", "Any other OpenAI-compatible service, with its address and key."),
]
MODULE_ORDER = [
    "telegram",
    "chat",
    "reminders",
    "checkins",
    "deadlines",
    "startby",
    "gbrain",
    "local_models",
    "subjects",
    "commitments",
    "classpacks",
    "doubts",
    "capture",
    "quiz",
    "exam_season",
    "weekly",
    "quests",
    "files",
    "projects",
    "skills",
    "hints",
    "library",
    "remember",
    "retro",
    "dreaming",
    "mind",
    "sorter",
    "finder",
    "learning",
    "cases",
    "calls",
    "alarm",
    "lidsafe",
    "voice_notes",
    "voice",
    "face",
    "awake",
    "calendar",
    "notes_sync",
    "backups",
    "profile",
    "google",
    "classroom_notes",
    "mail_digest",
    "reply_drafts",
    "digest_email",
    "agent_plan",
    "google_calendar",
    "drive_upload",
    "handwritten",
    "books",
    "integrate",
    "space",
    "study",
    "research",
    "research_addon",
    "drafts",  # Check my draft: in the Research add-on bundle
    "terminals",
    "terminal",
    "overlay",
]


@functools.cache
def _tips() -> dict:
    """Every setting's one-line explanation (data/settings-help.json, written by tools/gen_settings_guide.py)."""
    try:
        return json.loads(resources.files("kurooto").joinpath("data", "settings-help.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


class Api:
    def __init__(self, app: App):
        self.app = app
        self.prereqs = Prereqs(app.paths.app, app.paths.cache)
        self.progress: list[dict] = []
        self._installing = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------------------------------------ helpers
    def _hardware(self, refresh: bool = False) -> dict:
        f = self.app.paths.state / "hardware.json"
        if refresh:  # read the machine again
            f.unlink(missing_ok=True)
        return hardware.current(self.app)

    def _brains(self) -> list[dict]:
        rows, order = [], list(BRAIN_ORDER)
        if "freellmapi" in (self.app.settings.get("brain.main"), *providers.fallback.chosen(self.app)):
            order.append(("freellmapi", "Set up with an earlier version of Kurooto; it keeps working."))  # not offered
        for i, (bid, why) in enumerate(order):
            b = providers.build(self.app, bid)
            ok, reason = b.available() if b else (False, "")
            rows.append(
                {
                    "id": bid,
                    "label": providers.CHOICES[bid],
                    "why": why,
                    "recommended": i == 0,
                    "ready": ok,
                    "missing": reason,
                }
            )
        return rows

    def _modules(self) -> list[dict]:
        from kurooto.core import overlay  # your add-ons' features come last (core/overlay.py)

        out = []
        for mid in [*MODULE_ORDER, *overlay.all_modules(self.app)]:  # then the add-ons by link's
            m = self.app.modules.get(mid)
            if not m:
                continue
            ready, why = m.ready()
            out.append(
                {
                    "id": m.id,
                    "title": m.title,
                    "description": m.description,
                    "privacy": m.privacy,
                    "requires": list(m.requires),
                    "on": self.app.is_on(m.id),
                    "ready": ready,
                    "why": why,
                    "starter": m.id in STARTER,
                    "roles": [r for r, ids in ROLES.items() if m.id in ids],
                    "setup": hasattr(m, "setup"),
                    "form": m.setup_form() if hasattr(m, "setup_form") else None,
                    "addon": bool(getattr(m, "addon", False)),
                    "linked": str(getattr(m, "linked", "") or ""),  # the add-on by link it came from
                    "extra": bool(getattr(m, "extra", False)),
                    "bundle": str(getattr(m, "bundle", "") or ""),  # in an add-on bundle: on its card
                    "card": self._card(m),
                }
            )
        return out

    def _addons(self) -> dict:
        from kurooto.core import addons, official, overlay

        st = overlay.status(self.app).get("linked") or {}
        rows = []
        for r in addons.listing(self.app.paths):
            row = st.get(r["name"]) or {}
            rows.append(
                {**r, "modules": row.get("modules") or [], "text": addons.card_text(r["card"]) if r["card"] else ""}
            )
        kept = {}
        for k in addons.kept(self.app.paths):
            if k.get("rec"):
                kept[k["name"]] = {"name": k["name"], "why": k["why"], "at": k["at"], "commit": k["rec"].get("commit")}
        return {
            "on": self.app.settings.get("addons.on", True) is not False,
            "linked": rows,
            "kept": list(kept.values()),
            "official": official.rows(self.app.paths),  # Kurooto's official list, with what you have of each
        }

    def _addons_post(self, action: str, b: dict) -> tuple[int, dict]:
        """look (a link's card, or an official one's by {"official": name}), add (yes to a card), check (an update's
        card), update (yes to it), remove, undo, drop (no to a card), reload (after `kurooto addons` changed them).
        Only you, by a button or the terminal."""
        from kurooto.core import addons, official, overlay

        p = self.app.paths
        try:
            if action == "look" and b.get("official"):  # Features → Add-ons → Official add-ons → Add
                return 200, {"ok": True, **official.fetch(p, str(b["official"]))}
            if action == "look":
                out = addons.fetch(p, str(b.get("url") or ""), str(b.get("ref") or "").strip())
                return 200, {"ok": True, **out}
            if action == "check":
                out = addons.check_update(p, str(b.get("name") or ""))
                if out.get("same"):
                    return 200, {"ok": True, "same": True, "message": "Already at the newest commit."}
                return 200, {"ok": True, **out}
            if action in ("add", "update"):
                code = bool(b.get("code"))  # the box: I trust this code
                tok = str(b.get("token") or "")
                needs_code = addons.runs_code(p, tok)
                if needs_code and not code:
                    return 200, {"ok": False, "message": "It runs code: tick the box to say you trust it first."}
                ok, msg = addons.install(p, tok, bool(b.get("yes", True)), via="button")
            elif action == "drop":
                addons.drop(p, str(b.get("token") or ""))
                return 200, {"ok": True, "message": "Dropped; nothing was kept."}
            elif action == "remove":
                ok, msg = addons.remove(p, str(b.get("name") or ""))
            elif action == "undo":
                ok, msg = addons.undo(p, str(b.get("name") or ""))
            elif action == "reload":
                ok, msg = True, ""
            else:
                return 404, {"error": "not found"}
        except addons.AddonError as e:
            said = str(e)
            return 200, {"ok": False, "message": said[:1].upper() + said[1:] + "."}
        st = overlay.reload_linked(self.app)
        if action == "reload":
            n = len(st.get("linked_modules") or [])
            msg = f"Add-ons by link loaded again: {len(st.get('linked') or {})} add-on(s), {n} feature(s)."
        return 200, {"ok": ok, "message": msg, "modules": self._modules()}

    def _card(self, m) -> dict | None:
        """A feature's own card parts while it's on (Module.card(): lines and switches, e.g. Exam season's)."""
        if not hasattr(m, "card") or not self.app.is_on(m.id):
            return None
        try:
            return m.card()
        except Exception as e:
            return {"lines": [f"Couldn't show this: {type(e).__name__}"], "toggles": []}

    # ---------------------------------------------------------------------------------------------- GET
    def get(self, path: str, q: dict | None = None) -> tuple[int, dict]:
        q = q or {}
        from kurooto.web import tools_api  # the AI's tools, `kurooto ask`, `kurooto call`, AI usage

        if path in tools_api.GETS:
            return tools_api.get(self.app, path, q)
        if path == "addons":  # the add-ons by link, their cards and what's kept for Undo (core/addons.py)
            return 200, self._addons()
        if path == "body":  # Brain's body map for the dashboard (mind/stimulation.py, 0.8.8): plain numbers only
            from kurooto.mind import stimulation

            return 200, stimulation.body(self.app)
        if path == "mind/status":  # Brain's status for the being (mind/status.py, 0.8.14): enums, numbers, its item
            from kurooto.mind import status

            return 200, status.view(self.app)
        if path == "brain/console":  # the Brain console: decisions, timeline, search, parts (mind/console.py)
            from kurooto.mind import console

            return console.view(self.app, q)
        if path == "brain/claude-accounts":  # your extra Claude accounts (providers/claude_accounts.py)
            return 200, {"accounts": providers.claude_accounts.rows(self.app), "terms": providers.claude_accounts.TERMS}
        if path == "jobs":  # what the AI is working on and what waits (core/jobs.py; `kurooto jobs`)
            from kurooto.core.jobs import public

            return 200, {"active": [{**public(j), "line": self.app.jobs.line(j)} for j in self.app.jobs.active()]}
        if path == "term":  # the dashboard's terminals (modules/terminals.py)
            t = self.app.modules.get("terminals")
            on = bool(t) and self.app.is_on("terminals")
            return 200, {"on": on, "terms": t.listing() if on else []}
        if path == "voice":  # Voice: its state, engines and switches (modules/voice)
            v = self.app.modules.get("voice")
            return (200, v.status()) if v is not None else (404, {"error": "no Voice here"})
        if path == "voice/id":  # Voice ID: counts, grades, thresholds, the session; never a vector (voice/voiceid.py)
            v = self.app.modules.get("voice")
            return (200, v.voiceid.status()) if v is not None else (404, {"error": "no Voice here"})
        if path == "face":  # Face presence: its stage, model quality and switches (modules/face); never a template
            f = self.app.modules.get("face")
            return (200, f.status()) if f is not None else (404, {"error": "no Face presence here"})
        if path == "health":  # Kurooto keeps itself working: every check, from what's known here (core/health.py)
            from dataclasses import asdict

            from kurooto.core.health import FIXES

            rows = [{**asdict(r), "fix_label": r.fix_label} for r in self.app.health.evaluate(save=False)]
            return 200, {"on": self.app.health.on(), "results": rows, "fixes": FIXES}
        if path == "sync/status":  # `kurooto sync` waits on this (core/syncall.py)
            from kurooto.core import syncall

            return 200, syncall.status(self.app)
        if path == "profile":  # Profile sync's status and the last restore (modules/profile.py)
            from kurooto.modules.profile import web

            return web(self, path, q, post=False)
        if path == "note":
            return self._note(q.get("id", ""))
        if path == "settings":
            return 200, self._settings()
        if path == "look":  # the pages' colours (core/palette.py); static/palette.js asks every 30 seconds
            from kurooto.core import palette

            return 200, palette.describe(self.app)
        if path == "events":  # each with the SYSTEMS cell it belongs to, as the live ones have (web/live.py)
            from kurooto.web.live import cell_of

            return 200, {"events": [{"cell": cell_of(str(e.get("kind", ""))), **e} for e in self.app.events.tail(80)]}
        if path == "cell":  # a SYSTEMS cell's menu: which of its actions there are (static/home.js:Body.openMenu)
            from kurooto.core import syncall

            m = self.app.modules.get(str(q.get("id") or ""))
            if m is None:
                return 404, {"error": "no such feature"}
            on = self.app.is_on(m.id)
            return 200, {
                "id": m.id,
                "title": m.title,
                "on": on,
                "sync": on and m.id in dict(syncall.steps(self.app)),
                "quiet": on and self.app.keep.quiet_change(m) is not None,
            }
        if (
            path == "brain3d"
        ):  # the Brain page: islands of parts, each one's switch and a few live numbers (core/brainview.py)
            from kurooto.core import brainview

            return 200, brainview.view(self.app)
        if path == "board":  # Kurooto's side of the dashboard's board, for `kurooto top` (web/live.py)
            live = getattr(self.app, "live", None)
            return (200, live.vitals.board()) if live is not None else (503, {"error": "the page isn't up"})
        if path == "state":
            from kurooto.core import zones

            s = self.app.settings
            tg = self.app.modules["telegram"]
            hw = self._hardware()
            models_gb = sum(x["size_gb"] for x in hw["recommendation"]["local_models"])
            return 200, {
                "version": __version__,
                "you": s.get("you"),
                "setup_done": bool(s.get("setup.done")),
                "hardware": hw,
                "settings_hardware": {
                    k: s.get(f"hardware.{k}") for k in ("force_profile", "extra_models", "extra_prereqs")
                },
                "brains": self._brains(),
                "brain": {"main": s.get("brain.main"), "fallback": s.get("brain.fallback")},
                "claude_accounts": providers.claude_accounts.rows(self.app),  # extra ones; terms: the note to show
                "claude_terms": providers.claude_accounts.TERMS,
                "modules": self._modules(),
                "prereqs": self.prereqs.status(),
                "room": self.prereqs.room(["ollama"] if models_gb else [], extra_gb=models_gb),  # ★ AI: a key
                "telegram": {"token_set": bool(self.app.secrets.get("telegram.token")), "paired": tg.ready()[0]},
                # where you talk to it: "telegram", or "app" (the phone app's chat instead; 0.5.18), "" not chosen
                "channel": s.get("setup.channel") or "",
                "keys": {"gemini": bool(self.app.secrets.get("gemini.api_key"))},
                "power": self._power(),
                "autostart": autostart.status(),
                "workspace": str(self.app.workspace),
                "zones": zones.names(),  # the time zone picker: today's names (core/zones.py)
                "computer_zone": zones.computer_zone(),
                "setup": setupsteps.view(self.app),  # each step finished, skipped or not yet (core/setupsteps.py)
                "calm": {k: s.get(f"notify.calm.{k}") for k in ("on", "messages", "evening_at")},  # the daily limit
            }
        if path == "setup":  # where setup is (core/setupsteps.py): the dashboard's Finish setting up
            return 200, setupsteps.view(self.app)
        if (
            path == "notes/fit"
        ):  # the setup page's Notes step: what the folder shows and the proposal (core/notesfit.py)
            from kurooto.core import notesfit

            return 200, notesfit.view(self.app, q.get("folder") or None)
        if path == "phone":
            return 200, self._phone()
        if path == "power":
            return 200, self._power()
        if path == "aboutyou/profile":  # the profile, for the editor (setup page and dashboard)
            return 200, self.app.about.view()
        if path == "persona":  # the persona card, for its editor on the About you tab (core/persona.py)
            from kurooto.core import persona

            return 200, persona.view(self.app)
        if path == "aboutyou":
            from kurooto.core.aboutyou import prompt

            src = q.get("source", "")
            return 200, {
                **self.app.about.status(),
                "prompts": {"main": prompt("main", src), "other": prompt("other", src)},
            }
        if path == "research":
            from kurooto.modules.research import catalog

            return 200, {**self.app.modules["research"].view(), "catalog": catalog()}
        if path == "progress":
            with self._lock:
                return 200, {"installing": self._installing, "lines": self.progress[-30:]}
        if path == "ask" or path.startswith("ask/"):
            return self._ask(path, dict(q))
        if path == "today":  # the Today page: the day, with ids to act on (core/actions.py)
            from kurooto.core import actions

            return 200, actions.today(self.app)
        if path == "study":  # the dashboard's Study mode, for one subject (core/actions.py)
            from kurooto.core import actions

            return 200, actions.study_view(self.app, q.get("subject"))
        if path == "proposals" or path.startswith("proposals/"):  # the AI's changes waiting for your OK, with diffs
            from kurooto.core import proposals

            if path == "proposals":
                pj = self.app.modules.get("projects")
                mine = (
                    [{"name": k, "help": pj.helps(k)} for k in sorted(pj.known())]
                    if pj is not None and self.app.is_on("projects")
                    else None
                )
                return 200, {
                    "proposals": [proposals.public(self.app, p) for p in proposals.every(self.app)[:60]],
                    "projects": mine,  # Help with your project: None while it's off
                }
            p = proposals.get(self.app, path.split("/", 1)[1])
            if p is None:
                return 404, {"error": "no such proposal"}
            return 200, {"proposal": proposals.public(self.app, p, diff=True)}
        if path == "morning":  # the morning page (rhythm)
            from kurooto.modules.daily import morning_view

            return 200, morning_view(self.app)
        if path == "mail/confidential":  # confidential mail summarised on this computer (google): read-only, local
            from kurooto.modules.google_confidential import view

            return 200, view(self.app, q.get("day"))
        if path == "books":  # your books per subject and how far reading got (modules/books.py)
            bk = self.app.modules.get("books")
            if not bk or not self.app.is_on("books"):
                return 200, {"on": False, "books": []}
            rows = [
                {"subject": x["subject"], "id": x["id"], "file": str(x["path"]), **bk.meta(x)} for x in bk.library()
            ]
            return 200, {"on": True, "folder": str(bk.roots()[0][0]), "status": bk.status, "books": rows}
        return 404, {"error": "not found"}

    # --------------------------------------------------------------------------------------------- POST
    def post(self, path: str, b: dict) -> tuple[int, dict]:
        s = self.app.settings
        from kurooto.web import tools_api  # the AI's tools, `kurooto ask`, `kurooto call`

        if path in tools_api.POSTS:
            return tools_api.post(self.app, path, b)
        if path.startswith("addons/"):  # Features → Add-ons by link, `kurooto addons` (core/addons.py)
            return self._addons_post(path[len("addons/") :], b)
        if path.startswith("brain/claude-accounts/"):  # the setup page's AI step, Settings → Claude accounts
            return self._claude_accounts_post(path[len("brain/claude-accounts/") :], b)
        if path == "jobs/cancel":  # a Cancel button on the AI jobs page, `kurooto jobs --cancel ID|all` (core/jobs.py)
            ref = str(b.get("id") or "").strip()
            if not ref:
                return 400, {"ok": False, "message": "which request?"}
            gone = ref.lower() == "all" or self.app.jobs.find(ref) is not None
            return 200, {"ok": gone, "message": self.app.jobs.cancel_text(ref)}
        if path.startswith("voice/"):  # Voice: say, mute, shape (modules/voice)
            return self._voice(path[len("voice/") :], b)
        if path.startswith("face/"):  # Face presence: enrol, train, test, manage, forget (modules/face)
            return self._face(path[len("face/") :], b)
        if path == "health/fix":  # a Fix button on the dashboard, or `kurooto doctor --fix ID` (core/health.py)
            ok, message = self.app.health.fix(str(b.get("id") or ""))
            return 200, {"ok": ok, "message": message}
        if path.startswith("term/"):  # terminals: term/<name>/<attach|input|resize|leave|restart>
            t = self.app.modules.get("terminals")
            _, name, action = (path.split("/") + ["", ""])[:3]
            if not t or not self.app.is_on("terminals"):
                return 403, {"error": "Terminals is off"}
            return t.handle(name, action, b)
        if path == "stream/seen":  # the dashboard is in sight or not: nothing is computed for pages out of sight
            live = getattr(self.app, "live", None)
            try:
                cid = int(b.get("cid") or 0)
            except (TypeError, ValueError):
                return 400, {"error": "bad cid"}
            ok = live is not None and live.seen(cid, b.get("visible") is not False)
            return 200, {"ok": ok}
        if path == "power/stop":  # stop the normal way (`kurooto restore`): shutdown hooks run; it starts at sign-in
            self.app.stop_reason = "stopped"  # for the "going offline" message (core/presence.py)
            threading.Timer(0.3, self.app.request_stop).start()  # answer first
            return 200, {"ok": True, "message": "Stopping."}
        if path == "sync/all":  # sync everything that's on, in the background (`kurooto sync`)
            from kurooto.core import syncall

            ok, message = syncall.start(self.app, notify=bool(b.get("notify", True)))
            return 200, {"ok": ok, "message": message}
        if path == "sync/status":  # `kurooto sync` waits on this (core/syncall.py)
            from kurooto.core import syncall

            return 200, syncall.status(self.app)
        if path == "cell/sync":  # a SYSTEMS cell's "sync now": that feature alone, in the background
            from kurooto.core import syncall

            ok, message = syncall.start_one(self.app, str(b.get("id") or ""))
            return 200, {"ok": ok, "message": message}
        if path == "cell/quiet":  # a SYSTEMS cell's "quiet": it keeps working but stops messaging (core/keep.py)
            m = self.app.modules.get(str(b.get("id") or ""))
            c = self.app.keep.quiet_change(m) if m is not None and self.app.is_on(m.id) else None
            if c is None:
                return 200, {"ok": False, "message": "Nothing of it left to quiet."}
            ok, said, uid = self.app.calm.apply(c, why="dashboard")
            return 200, {"ok": ok, "message": said, "undo": uid}
        if path == "calm/undo":  # the Undo beside a change made from the dashboard (core/calm.py)
            return 200, {"ok": True, "message": self.app.calm.undo(str(b.get("id") or ""))}
        if path.startswith("profile/"):  # save now; restore on a new computer (modules/profile.py)
            from kurooto.modules.profile import web

            return web(self, path, b, post=True)
        if path == "settings":
            return self._set(b.get("key", ""), b.get("value"))
        if path == "modules/card":  # a switch on a feature's card (Module.card_action, e.g. Exam season's parts)
            m = self.app.modules.get(str(b.get("id") or ""))
            if m is None or not self.app.is_on(m.id) or not hasattr(m, "card_action"):
                return 400, {"error": "no such card"}
            return 200, {"ok": True, "message": m.card_action(str(b.get("act") or ""), b.get("value"))}
        if path == "open-note":
            return self._open_note(b.get("id", ""))
        if path == "open-url":  # a link to another site, in the default browser (core/opener.py; look.links_in)
            if s.get("look.links_in") == "here":
                return 200, {"ok": False, "here": True}  # the page opens it itself
            if not opener.safe_url(b.get("url")):
                return 400, {"error": "Only http and https addresses open in the browser."}
            ok, why = opener.open_url(b["url"])
            return 200, {"ok": ok, **({"error": why} if why else {})}
        if path == "you":
            from kurooto.core import zones  # a zone is saved under today's name (Europe/Kiev -> Europe/Kyiv)

            for k in ("name", "timezone", "assistant_name"):
                if k in b and isinstance(b[k], str):
                    old = s.set(f"you.{k}", (zones.canonical(b[k]) if k == "timezone" else b[k].strip())[:80])
                    if old != s.get(f"you.{k}"):
                        self.app.events.emit("setting_changed", key=f"you.{k}")
            return 200, {"ok": True, "timezone": s.get("you.timezone") or ""}
        if path == "act":  # one everyday action, the same as the command and the AI's tool (core/actions.py)
            from kurooto.core import actions

            return 200, actions.act(self.app, str(b.get("action") or ""), b.get("args") or {}, via="dashboard")
        if path == "hardware/refresh":
            return 200, self._hardware(refresh=True)
        if path == "hardware/override":  # go past what the detection suggests: another setup, models of your own
            prof = str(b.get("profile") or "")
            if prof and prof != "auto" and prof not in hardware.PROFILES:
                return 400, {"error": f"not a setup: {prof}"}
            if "profile" in b:
                s.set("hardware.force_profile", "" if prof == "auto" else prof)
            for key, field in (("hardware.extra_models", "models"), ("hardware.extra_prereqs", "prereqs")):
                if isinstance(b.get(field), list):
                    s.set(key, [str(x).strip() for x in b[field] if str(x).strip()][:20])
            out = {"hardware": self._hardware(), "installing": False}
            if not b.get("install"):  # models the new setup doesn't use: Remove / Keep (core/uninstall.py)
                from kurooto.core import uninstall

                said = uninstall.after_hardware(self.app).strip()
                if said:
                    out["message"] = said
            if b.get("install"):  # Kurooto installs Ollama, the models and the programs, with progress on the page
                lm = self.app.modules["local_models"]
                out.update(self._background(lambda note: lm.setup(note), then_enable="local_models"), installing=True)
            return 200, out
        if path == "brain":
            which = b.get("main", "")
            if which and which not in providers.choices(self.app):
                return 400, {"error": "unknown brain"}
            if b.get("key"):
                self.app.secrets.set(f"{which}.api_key", b["key"].strip())
            if b.get("base_url"):
                urls = dict(s.get("brain.base_urls") or {})
                urls[which] = b["base_url"].strip()
                s.set("brain.base_urls", urls)
            if b.get("models"):
                models = dict(s.get("brain.models") or {})
                models[which] = {k: v for k, v in b["models"].items() if k in ("low", "medium", "high") and v}
                s.set("brain.models", models)
            if which:
                s.set("brain.main", which)
            if "fallback" in b:
                s.set("brain.fallback", b["fallback"] or "")
            return 200, {"ok": True, "brains": self._brains()}
        if path == "brain/test":
            return 200, self._test(b.get("which") or s.get("brain.main"))
        if path == "brain/models":
            brain = providers.build(self.app, b.get("which", ""))
            try:
                return 200, {"models": brain.list_models() if hasattr(brain, "list_models") else []}
            except Exception as e:
                return 200, {"models": [], "error": str(e)[:200]}
        if path == "prereqs/install":
            return 200, self._install([k for k in b.get("keys", []) if k in self.prereqs.items])
        if path == "prereqs/signin":
            ok, msg = self.prereqs.open_signin(b.get("key", ""))
            return 200, {"ok": ok, "message": msg}
        if path == "telegram/token":
            try:
                return 200, {"ok": True, **self.app.modules["telegram"].pair_start(b.get("token", ""))}
            except TelegramError as e:
                return 200, {
                    "ok": False,
                    "error": "Telegram didn't accept that token." if e.code in (401, 404) else e.description,
                }
            except Exception as e:
                return 200, {"ok": False, "error": f"Couldn't reach Telegram: {e}"[:200]}
        if path == "telegram/poll":
            from kurooto.modules.telegram import PairingProblem

            try:
                got = self.app.modules["telegram"].pair_poll(wait=int(b.get("wait", 20)))
            except PairingProblem as e:
                return 200, {"paired": False, "error": e.message, "problem": e.kind, "retry": e.retry}
            except Exception as e:
                return 200, {"paired": False, "error": str(e)[:200], "problem": "other", "retry": True}
            if got:
                self.app.enable("telegram")
            return 200, {"paired": bool(got), **(got or {})}
        if path == "telegram/relink":  # the pairing link expired: a new one for the same bot
            from kurooto.modules.telegram import PairingProblem

            try:
                return 200, {"ok": True, **self.app.modules["telegram"].pair_relink()}
            except PairingProblem as e:
                return 200, {"ok": False, "error": e.message}
            except TelegramError as e:
                return 200, {"ok": False, "error": "That token was revoked." if e.code == 401 else e.description}
            except Exception as e:
                return 200, {"ok": False, "error": f"Couldn't reach Telegram: {e}"[:200]}
        if path == "telegram/webhook-off":  # the bot was connected to a web address; Kurooto needs it back
            try:
                self.app.modules["telegram"].drop_webhook()
                return 200, {"ok": True}
            except Exception as e:
                return 200, {"ok": False, "error": f"Couldn't disconnect it: {e}"[:200]}
        if path == "modules/enable":
            res = {}
            ids = b.get("ids", [])
            app_chat = "telegram" not in ids and not self.app.is_on("telegram")  # the phone app's chat goes first
            for mid in sorted(
                ids,
                key=lambda m: -1 if app_chat and m == "calls" else MODULE_ORDER.index(m) if m in MODULE_ORDER else 99,
            ):
                res[mid] = self.app.enable(mid)
            return 200, {
                "results": {k: {"ok": v[0], "message": v[1]} for k, v in res.items()},
                "setup": {k: self.app.modules[k].setup_steps() for k in res if k in self.app.modules},
                "modules": self._modules(),
            }
        if path == "modules/steps":  # what's left to set a feature up (Module.setup_steps)
            m = self.app.modules.get(b.get("id", ""))
            return (
                (200, {"id": m.id, "title": m.title, "steps": m.setup_steps()})
                if m
                else (404, {"error": "no such feature"})
            )
        if path == "modules/setup":
            m = self.app.modules.get(b.get("id", ""))
            if not m or not hasattr(m, "setup"):
                return 400, {"error": "nothing to set up"}
            return 200, self._background(lambda note: m.setup(note), then_enable=m.id)
        if path == "modules/configure":
            m = self.app.modules.get(b.get("id", ""))
            if not m or not hasattr(m, "configure"):
                return 400, {"error": "nothing to configure"}
            try:
                out = m.configure(b.get("values") or {})
            except Exception as e:
                out = {"ok": False, "message": f"{type(e).__name__}: {e}"[:300]}
            if out.get("ok") and not self.app.is_on(m.id) and m.ready()[0] and b.get("enable", True):
                ok, msg = self.app.enable(m.id)
                out["message"] = f"{out.get('message', '')} {msg}.".strip()
            return 200, {**out, "modules": self._modules()}
        if path == "modules/disable":
            ok, msg = self.app.disable(b.get("id", ""))
            return 200, {"ok": ok, "message": msg, "modules": self._modules()}
        if path == "research/save":
            try:
                return 200, {"ok": True, **self.app.modules["research"].save(b)}
            except (ValueError, TypeError) as e:
                return 200, {"ok": False, "error": str(e)}
        if path == "research/preview":
            from kurooto.modules.research import describe, validate

            r = self.app.modules["research"]
            try:
                feed = validate(b.get("feed") or {})
                papers = r.fetch(feed)
            except ValueError as e:
                return 200, {"ok": False, "error": str(e)}
            except Exception as e:
                return 200, {"ok": False, "error": f"Couldn't reach it: {type(e).__name__}: {e}"[:300]}
            return 200, {"ok": True, "label": describe(feed), "count": len(papers), "papers": papers[:10]}
        if path == "research/project":  # Add a project from a repository (core/repoproject.py): a button you pressed
            from kurooto.core import repoproject

            target = str(b.get("target") or "").strip()
            if not target:
                return 200, {"ok": False, "error": "Give a GitHub address or a folder first."}
            said = repoproject.start(self.app, target, str(b.get("name") or "").strip(), via="button")
            return 200, {"ok": not said.startswith(("Can't", "Projects from")), "message": said}
        if path == "research/run":
            r = self.app.modules["research"]
            threading.Thread(target=r.papers, name="papers", daemon=True).start()
            return 200, {"ok": True, "message": "Looking now; the digest comes on Telegram in a minute or two."}
        if path == "notify":  # other programs on this computer message you through Kurooto (`kurooto notify`)
            from kurooto.web.tools_api import notify_from_program  # (ws5) buttons, --click, --reply-to

            return notify_from_program(self.app, b)
        if (
            path == "classpack/import"
        ):  # `kurooto classpack import FILE`: its review on Telegram (modules/classpacks.py)
            from pathlib import Path

            cp = self.app.modules.get("classpacks")
            if cp is None or not self.app.is_on("classpacks"):
                return 200, {"ok": False, "message": "Class packs is off: dashboard → Features → Class packs."}
            ok, message = cp.start_import(Path(str(b.get("path") or "")))
            return 200, {"ok": ok, "message": message}
        if path == "send-file":  # `kurooto send FILE`: a file from this computer to your Telegram
            from kurooto.modules.skills import send_file

            to = "drive" if b.get("to") == "drive" else ""  # (ws2) --to drive: Google Drive, with a link
            ok, message = send_file(self.app, str(b.get("path") or ""), str(b.get("caption") or "")[:900], to=to)
            return 200, {"ok": ok, "message": message}
        if path == "aboutyou/add":
            try:
                return 200, {
                    "ok": True,
                    **self.app.about.add(b.get("label", ""), b.get("text", "")),
                    **self.app.about.status(),
                }
            except ValueError as e:
                return 200, {"ok": False, "error": str(e)}
        if path == "persona":  # save the persona card; what the rules left out is said (core/persona.py)
            from kurooto.core import persona

            values = b.get("values")
            if not isinstance(values, dict):
                return 400, {"error": "values is missing"}
            _, dropped = persona.save(self.app, {k: str(v or "") for k, v in values.items()})
            return 200, {"ok": True, **persona.view(self.app), "message": persona.dropped_text(dropped) or "Saved."}
        if path == "aboutyou/remove":
            return 200, {"ok": self.app.about.remove(str(b.get("id", ""))), **self.app.about.status()}
        if path in ("aboutyou/profile", "aboutyou/preview"):  # save your edit / what its In brief would be
            from kurooto.core.aboutyou import brief_of, brief_warning

            text = b.get("text")
            if not isinstance(text, str):
                return 400, {"error": "text is missing"}
            if path == "aboutyou/preview":
                return 200, {"brief": brief_of(text), "warning": brief_warning(text)}
            try:
                return 200, self.app.about.save_text(text)
            except ValueError as e:
                return 200, {"ok": False, "error": str(e)}
        if path == "aboutyou/merge":
            from kurooto.core.aboutyou import Edited

            try:
                self.app.about.merge(replace=bool(b.get("replace")))
            except Edited as e:  # changed since it was built: the page asks, then sends replace
                return 200, {"ok": False, "edited": True, "error": str(e)}
            except ValueError as e:
                return 200, {"ok": False, "error": str(e)}
            return 200, {
                "ok": True,
                "message": "Building your profile with your AI: a minute or a few. It appears in "
                "your notes as about-me/profile.md.",
                **self.app.about.status(),
            }
        if path == "power/pause":
            when = str(b.get("when") or "").strip()
            if not when:
                return 200, {"ok": True, "message": self.app.power.pause(None), "power": self._power()}
            try:
                from kurooto.core.clock import now, parse_when

                minutes = max(1.0, (parse_when(when.removeprefix("until ")) - now()).total_seconds() / 60)
            except ValueError:
                return 200, {"ok": False, "message": f"I couldn't read {when!r} (try 2h or 18:00)."}
            return 200, {"ok": True, "message": self.app.power.pause(minutes), "power": self._power()}
        if path == "power/resume":
            return 200, {"ok": True, "message": self.app.power.resume(), "power": self._power()}
        if path == "power/off":
            keep = bool(b.get("keep_calls"))
            threading.Timer(0.8, self.app.power.off, kwargs={"keep_calls": keep}).start()  # answer first
            return 200, {
                "ok": True,
                "message": "Turning off. Turn it back on with Kurooto in your app menu, or `kurooto on`.",
            }
        if path == "keys/gemini":
            return 200, self._gemini_key(str(b.get("key", "")).strip())
        if path == "phone/pair":
            try:
                return 200, {"ok": True, **self.app.modules["calls"].pair_start()}
            except Exception as e:
                return 200, {"ok": False, "error": f"{e}"[:300] or "your call line isn't connected"}
        if path == "phone/revoke":
            try:
                return 200, {"ok": self.app.modules["calls"].revoke(str(b.get("id", "")))}
            except Exception as e:
                return 200, {"ok": False, "error": f"{e}"[:300]}
        if path == "phone/shortcut/revoke":  # a Tell Kurooto link (the iPhone Shortcut), 0.6.0
            try:
                return 200, {"ok": self.app.modules["calls"].shortcut_revoke(str(b.get("id", "")))}
            except Exception as e:
                return 200, {"ok": False, "error": f"{e}"[:300]}
        if path == "phone/ntfy":  # an ntfy account token (or "" to clear it): checked, kept, sent to the call line
            calls = self.app.modules.get("calls")
            if calls is None:
                return 200, {"ok": False, "message": "Phone calls aren't here."}
            ok, msg = calls.set_ntfy_token(str(b.get("token") or ""))
            return 200, {"ok": ok, "message": msg}
        if path == "phone/test":
            if not self.app.is_on("calls"):
                return 200, {"ok": False, "error": "Phone calls are off"}
            self.app.modules["calls"].ring(
                "This is a test call from your computer. Answer to check it works.", why="asked"
            )
            return 200, {"ok": True}
        if path == "autostart":
            if os.environ.get("KUROOTO_NO_AUTOSTART") == "1":  # tests and rehearsals leave this computer alone
                return 200, {"ok": True, "message": "Start at sign-in is left alone here (KUROOTO_NO_AUTOSTART)."}
            if b.get("when") in ("boot", "login"):  # at boot (Linux: lingering) or at login
                ok, msg = autostart.set_when(b["when"], s, self.app.secrets, self.app.paths.state)
                return 200, {"ok": ok, "message": msg, "when": autostart.when(s)}
            msg = autostart.enable() if b.get("on", True) else autostart.disable()
            return 200, {"ok": True, "message": msg}
        if path == "tryit":  # the setup page's try-it box: the same handler as a Telegram message (web/tryit.py)
            from kurooto.web import tryit

            return tryit.say(self.app, str(b.get("text") or ""))
        if path == "setup/channel":  # the setup page: Telegram, or the Kurooto phone app instead (0.5.18)
            ch = str(b.get("channel") or "")
            if ch not in ("telegram", "app"):
                return 400, {"error": "telegram or app"}
            s.set("setup.channel", ch)
            return 200, {"ok": True, "channel": ch}
        if path == "setup/step":  # leaving a step: next, skip or leave, and the seconds spent (core/setupsteps.py)
            try:
                return 200, setupsteps.record(
                    self.app, str(b.get("step") or ""), str(b.get("how") or ""), b.get("seconds") or 0, b.get("chosen")
                )
            except ValueError as e:
                return 400, {"error": str(e)}
        if path.startswith("notes/fit/"):  # preview (a dry run), apply (with the plan's digest), undo
            from kurooto.core import notesfit

            try:
                if path == "notes/fit/preview":
                    return 200, notesfit.check(self.app, b)
                if path == "notes/fit/apply":
                    return 200, notesfit.apply(self.app, b)
                if path == "notes/fit/undo":
                    return 200, notesfit.undo_app(self.app, str(b.get("id") or ""))
            except (ValueError, OSError, notesfit.Refused) as e:  # said on the page, so not an HTTP error
                return 200, {"ok": False, "error": str(e)}
            return 404, {"error": "not found"}
        if path == "setup/done":
            s.set("setup.done", True)
            setupsteps.finish(self.app)
            on = [m.title for m in self.app.enabled()]
            where = " in the phone app's chat" if self.app.app_main() else ""
            self.app.notify(f"{self.app.name} is set up. On: {', '.join(on)}. Send /help{where} any time.", why="asked")
            return 200, {"ok": True}
        if path == "ask" or path.startswith("ask/"):
            return self._ask(path, b, post=True)
        if path == "projects/help":  # {name, what}: Help with your project, from the Proposals page
            pj = self.app.modules.get("projects")
            if pj is None or not self.app.is_on("projects"):
                return 200, {"ok": False, "error": "Help with your project is off (Features)."}
            return 200, {"ok": True, "message": pj.start_help(str(b.get("name") or ""), str(b.get("what") or ""))}
        if path == "proposals/act":  # {id, act: apply|discard|undo|change, text}: your tap on the Proposals page
            from kurooto.core import proposals

            pid, act = str(b.get("id") or ""), str(b.get("act") or "")
            if proposals.get(self.app, pid) is None:
                return 404, {"ok": False, "error": "no such proposal"}
            if act == "apply":
                return 200, {"ok": True, "message": proposals.apply(self.app, pid, via="dashboard")}
            if act == "discard":
                return 200, {"ok": True, "message": proposals.discard(self.app, pid)}
            if act == "undo":
                return 200, {"ok": True, "message": proposals.undo(self.app, pid)}
            if act == "change":
                return 200, {"ok": True, "message": proposals.change_with(self.app, pid, str(b.get("text") or ""))}
            return 400, {"ok": False, "error": "act: apply, discard, undo or change"}
        if path == "mail/confidential/settle":  # a date found in confidential mail: add it to Deadlines, or not
            from kurooto.modules.google_confidential import settle

            return 200, {"message": settle(self.app, str(b.get("id", "")), bool(b.get("add")))}
        if path in (
            "subjects/add",
            "subjects/remove",
        ):  # Study mode's subject list: {"name", "aliases", "folder"} / {"slug"}
            sj = self.app.modules.get("subjects")
            if not sj or not self.app.is_on("subjects"):
                return 400, {"ok": False, "message": "Subjects isn't on: turn it on in Features."}
            if path == "subjects/remove":
                return 200, {"ok": True, "message": sj.remove_subject(str(b.get("slug", "")))}
            al = b.get("aliases") or []
            al = [x for x in (al.split(",") if isinstance(al, str) else al) if isinstance(x, str)]
            ok, msg = sj.add_subject(str(b.get("name", "")), al, str(b.get("folder", "")))
            return 200, {"ok": ok, "message": msg}
        if path == "books/add":  # a PDF on this computer into a subject's books: {"path", "subject"} (a copy)
            bk = self.app.modules.get("books")
            if not bk:
                return 400, {"error": "Books isn't available"}
            ok, msg = bk.add(str(b.get("path", "")), str(b.get("subject", "")), move=False)
            return 200, {"ok": ok, "message": msg}
        return 404, {"error": "not found"}

    # ---------------------------------------------------------------------- questions and approvals
    def _ask(self, path: str, b: dict, post: bool = False) -> tuple[int, dict]:
        """Questions for you (core/ask.py), for `kurooto ask-me` / `ask-approval`, other programs and the dashboard.

        GET ask: the open ones. GET ask/<id> (or POST ask/get {id}): one. POST ask {text, choices, kind, expires,
        title}: ask now. POST ask/answer {id, text, via}: answer one. POST ask/expire {id}: stop waiting for one.
        Programs can't name hooks here: whoever asked reads the answer back.
        """
        ask = self.app.ask
        sub = path.partition("/")[2]
        if not post or sub in ("get", "pending"):
            if not sub or sub == "pending":  # POST ask/pending: `kurooto ask-me --pending`
                return 200, {"questions": [ask.public(q) for q in ask.pending()]}
            q = ask.get(str(b.get("id") or "") if sub == "get" else sub)
            return (200, {"question": ask.public(q)}) if q else (404, {"error": "no such question"})
        if not sub:
            text = str(b.get("text") or "").strip()
            if not text:
                return 400, {"error": "a question needs some text"}
            choices = b.get("choices") or []
            if isinstance(choices, str):
                choices = choices.split("|")
            try:
                qid = ask.ask(
                    text[:2000],
                    choices=[str(c) for c in choices if str(c).strip()][:8] if isinstance(choices, list) else None,
                    kind="approval" if b.get("kind") == "approval" else "question",
                    expires=str(b.get("expires") or "") or None,
                    source=str(b.get("source") or "cli")[:40],
                    title=str(b.get("title") or "")[:60] or None,
                    why="asked",
                )
            except ValueError as e:
                return 400, {"error": str(e)}
            return 200, {"ok": True, "id": qid}
        if sub == "answer":
            r = ask.answer(str(b.get("id") or ""), str(b.get("text") or ""), str(b.get("via") or "dashboard")[:20])
            return 200, r
        if sub == "expire":
            return 200, {"ok": ask.expire(str(b.get("id") or ""))}
        return 404, {"error": "not found"}

    def _voice(self, action: str, b: dict) -> tuple[int, dict]:
        """POST voice/say {text}, voice/mute {on: true|false, or none to flip}, voice/stop, voice/shape {text}."""
        v = self.app.modules.get("voice")
        if v is None:
            return 404, {"error": "no Voice here"}
        if action == "shape":  # works with Voice off too: the estimate (modules/voice/shape.py)
            return 200, v.shape(str(b.get("text") or ""))
        if action.startswith("id/"):  # (voice id) the Your voice page (/voice-id)
            return self._voice_id(v.voiceid, action[3:], b)
        if action == "say":
            ok, message = v.say(str(b.get("text") or ""), wait=False)
            return 200, {"ok": ok, "message": message}
        if action == "mute":
            on = b.get("on")
            return 200, {"ok": True, "message": v.mute(None if on is None else bool(on)), "muted": v.muted()}
        if action == "stop":
            v.speaker.stop()
            return 200, {"ok": True, "message": "Stopped speaking."}
        return 404, {"error": "not found"}

    def _voice_id(self, vid, action: str, b: dict) -> tuple[int, dict]:
        """POST voice/id/session {action: start|again|continue|pause|stop|keep, own_words?, conds?}, skip {cond},
        train {use_anyway?}, undo (the last build), test {as: me|other|synthetic}, adapt {undo: today|all},
        forget {confirm: true}, parts/add {path}. Answers carry counts, grades and scores, never a vector."""
        if action == "session":
            act = str(b.get("action") or "")
            if act == "start" and isinstance(b.get("conds"), list):
                return 200, vid.start_session(bool(b.get("own_words")), [str(c) for c in b["conds"]][:8])
            return 200, vid.session_cmd(act, bool(b.get("own_words")))
        if action == "skip":
            return 200, vid.skip(str(b.get("cond") or ""))
        if action == "train":
            return 200, vid.train(use_anyway=bool(b.get("use_anyway")))
        if action == "undo":
            return 200, vid.undo_build()
        if action == "test":
            return 200, vid.test(str(b.get("as") or "me"))
        if action == "adapt":
            return 200, vid.undo_adapt(str(b.get("undo") or ""))
        if action == "forget":
            if b.get("confirm") is not True:
                return 200, {"ok": False, "message": "Confirm first."}
            return 200, {"ok": True, "message": vid.forget()}
        if action == "parts/add":
            return 200, vid.add_file(str(b.get("path") or ""))
        return 404, {"error": "not found"}

    def _face(self, action: str, b: dict) -> tuple[int, dict]:
        """POST face/<action>. enrol/start and test/start open the camera (the guarded action camera.open: the Face
        page's Start and Test buttons only); forget deletes the face model (data.delete: a button after a confirm)."""
        f = self.app.modules.get("face")
        if f is None:
            return 404, {"error": "no Face presence here"}
        sid = str(b.get("session") or "")

        def out(res: tuple[bool, dict | str]) -> tuple[int, dict]:
            ok, data = res
            body = data if isinstance(data, dict) else {"message": data}
            return 200, {"ok": ok, **body}

        if action == "enrol/start":
            return out(f.enrol_start(b.get("cid"), str(b.get("mode") or "new")))
        if action == "enrol/step":
            return out(f.enrol_step(sid, str(b.get("action") or "")))
        if action == "enrol/pause":
            return out(f.session_pause(sid, b.get("on", True) is not False))
        if action == "enrol/discard":
            return out(f.discard(sid))
        if action == "train":
            return out(f.train(sid))
        if action == "test/start":
            return out(f.test_start(b.get("cid")))
        if action == "test/mark":
            return out(f.test_mark(sid, str(b.get("who") or "")))
        if action == "test/stop":
            return out(f.test_stop(sid))
        if action == "retrain":
            return out(f.retrain())
        if action == "undo":  # the last training (Add samples, Start over), this run only
            return out(f.undo_train())
        if action == "strictness":
            return out(f.set_strictness(str(b.get("level") or "")))
        if action == "learn/undo":
            return 200, {"ok": True, "message": f.learn_undo()}
        if action == "learn/forget":
            return 200, {"ok": True, "message": f.learn_forget()}
        if action == "forget":
            return 200, {"ok": True, "message": f.forget()}
        if action == "pause":
            return 200, {"ok": True, "message": f.pause(str(b.get("arg") or ""))}
        if action == "install-from":
            folder = str(b.get("folder") or "").strip()
            if not folder:
                return 400, {"ok": False, "message": "Which folder?"}
            return 200, self._background(lambda note: f.install_from(folder, note))
        return 404, {"error": "not found"}

    def face_frame(self, q: dict) -> bytes | None:
        """GET /api/face/frame?s=<session>: the live preview's latest frame, a JPEG made in memory (web/server.py sends
        it with Cache-Control: no-store). None without a live session."""
        f = self.app.modules.get("face")
        return f.frame(str(q.get("s") or "")) if f is not None else None

    def _power(self) -> dict:
        from kurooto.core.power import on_ac

        p = self.app.power
        hw = jload(self.app.paths.state / "hardware.json", {}) or {}
        return {
            "mode": p.current,
            "why": p.why(),
            "on_ac": on_ac(),
            "on_battery": self.app.settings.get("power.on_battery"),
            "laptop": bool((hw.get("machine") or {}).get("battery")),
        }

    def _phone(self) -> dict:
        calls = self.app.modules.get("calls")
        if not calls or not self.app.is_on("calls"):
            return {"on": False}
        out = {
            "on": True,
            **calls.status(),
            "devices": None,
            "shortcuts": None,
            "ntfy_token": bool(self.app.secrets.get("calls.ntfy_token")),
            "ntfy_limited": calls.ntfy_limited(),
            "views": calls.setting("views") is True,  # Systems and the Notes map on the Android app (calls/views.py)
        }
        if calls.connector.connected:
            try:
                out["devices"] = calls.devices()
                out["shortcuts"] = calls.shortcuts()
            except Exception as e:
                out["error"] = f"{e}"[:200]
        return out

    def _gemini_key(self, key: str) -> dict:
        """Check a Gemini API key against Google (it lists the models it can use), then keep it."""
        import json
        import urllib.error
        import urllib.request

        if not key:
            return {"ok": False, "error": "Paste the key first."}
        from kurooto.modules.voice_notes import gemini_api

        req = urllib.request.Request(  # noqa: S310 (Google's API, https)
            gemini_api(self.app) + "/models?pageSize=1", headers={"x-goog-api-key": key}
        )
        try:
            with egress.urlopen(req, "Gemini key check", timeout=20) as r:
                json.loads(r.read())
        except urllib.error.HTTPError as e:
            return {
                "ok": False,
                "error": "Google didn't accept that key." if e.code in (400, 401, 403) else f"HTTP {e.code}",
            }
        except OSError as e:
            return {"ok": False, "error": f"Couldn't reach Google: {e}"[:200]}
        self.app.secrets.set("gemini.api_key", key)
        return {"ok": True}

    def _test(self, which: str) -> dict:
        brain = providers.build(self.app, which or "")
        if not brain:
            return {"ok": False, "message": "Pick an AI first."}
        ok, why = brain.available()
        if not ok:
            return {"ok": False, "message": why}
        nonce = f"KUROOTO-OK-{1000 + secrets.randbelow(9000)}"
        prompt = f"Reply with exactly this and nothing else: {nonce}"
        t0 = time.monotonic()
        r = brain.complete(prompt, effort="low", timeout=180)
        if which == "agy" and r.verdict == Verdict.EMPTY:  # some builds print nothing without a terminal
            from kurooto.providers.agy import Agy

            r2 = Agy(io_mode="pty").complete(prompt, effort="low", timeout=180)
            if nonce in r2.text:
                self.app.settings.set("brain.agy.io_mode", "pty")
                r = r2
        secs = time.monotonic() - t0
        if nonce in r.text:
            msg = f"Working: it answered in {secs:.0f} s."
            if brain.kind == "cli":  # an agent program: it may stand in for the Gemini key later, and gets set up
                brain.mark_worked(self.app)
                msg += brain.after_test(self.app)
            return {"ok": True, "message": msg}
        msgs = {
            Verdict.AUTH: "It isn't signed in (or the key is wrong).",
            Verdict.RATE_LIMITED: "It's at its usage limit right now.",
            Verdict.TIMEOUT: "It didn't answer in time.",
            Verdict.EMPTY: "It answered with nothing.",
        }
        return {
            "ok": False,
            "message": msgs.get(r.verdict, f"It answered, but not as asked: {r.text[:120] or r.detail[:120]}"),
        }

    def _install(self, keys: list[str]) -> dict:
        def work(note):
            ok_all = True
            for k in keys:
                ok, msg = self.prereqs.install(k, note)
                note(("✓ " if ok else "✗ ") + msg)
                ok_all = ok_all and ok
            return ok_all, ""

        return self._background(work)

    def _background(self, fn, then_enable: str | None = None) -> dict:
        """Run a long step (installs, setting a feature up) in the background; the page polls /api/progress."""
        with self._lock:
            if self._installing:
                return {"started": False, "message": "Something is already being set up; wait for it to finish."}
            self._installing = True
            self.progress = []

        def note(line: str) -> None:
            with self._lock:
                self.progress.append({"t": time.time(), "line": line})

        def work():
            try:
                ok, msg = fn(note)
                if msg:
                    note(("✓ " if ok else "✗ ") + msg)
                if ok and then_enable:
                    ok2, msg2 = self.app.enable(then_enable)
                    note(("✓ " if ok2 else "✗ ") + msg2)
            except Exception as e:
                note(f"✗ {type(e).__name__}: {e}"[:300])
            finally:
                with self._lock:
                    self._installing = False

        threading.Thread(target=work, name="setup", daemon=True).start()
        return {"started": True}

    # ---------------------------------------------------------------------------- notes and settings
    def _note_path(self, nid: str):

        root = self.app.workspace.resolve()
        p = (root / f"{nid}.md").resolve()
        return p if root in p.parents and p.is_file() else None

    def _note(self, nid: str) -> tuple[int, dict]:
        p = self._note_path(nid)
        if not p:
            return 404, {"error": "no such note"}
        import re as _re

        text = p.read_text(encoding="utf-8", errors="replace")
        return 200, {
            "id": nid,
            "text": _re.sub(r"^---\n.*?\n---\n", "", text, flags=_re.S)[:4000],
            "mtime": p.stat().st_mtime,
        }

    def _open_note(self, nid: str) -> tuple[int, dict]:
        """Open a note in your program (notes.open_with, e.g. "kitty nvim {path}"), else the default app."""
        p = self._note_path(nid)
        if not p:
            return 404, {"error": "no such note"}
        ok, note = opener.open_note(self.app.settings, p, self.app.workspace)
        return 200, {"ok": ok, **({"message": note} if note else {})}

    EDITABLE = (
        "you",
        "notify",
        "availability",
        "updates",
        "brain",
        "ask",
        "look",
        "power",
        "notes",
        "files",
        "quota",
        "local_helper",
        "health",
        "jobs",
        "sources",
        "agents",
        "hardware",
        "web",
        "date_offers",
        "addons",
        "uninstall",
    )
    # the core sections' titles where the section's name alone says little
    TITLES = {
        "brain": "AI model",  # (0.8.14) the AI that answers; "Brain" is Kurooto's mind (Features → Brain)
        "quota": "AI limits",
        "local_helper": "Offline helper",
        "health": "Health checks",
        "jobs": "AI jobs",
        "sources": "Sources for answers",
        "agents": "Skills in other AI programs",
        "hardware": "This computer",
        "web": "Dashboard",
        "date_offers": "Dates offered (photos, mail, shared calendars)",
        "addons": "Add-ons by link",
        "uninstall": "What Kurooto installed",
    }
    # Settings the page neither shows nor changes: who may talk to the bot and where it connects (set by pairing), brain
    # addresses and models (POST /api/brain sets those, with its checks), the subject list and timetable (their own
    # pages).
    HIDDEN = {
        "telegram": {"api_base", "allowed_users", "chat_id"},
        "brain": {"base_urls", "models", "claude_accounts"},  # the accounts: their own section (_claude_section)
        "subjects": {"list", "timetable"},
    }

    # settings that take one of a few values: Settings shows them as a list ([value, what it means], value first)
    CHOICES = {
        "brain": lambda self: {
            "main": [[k, v] for k, v in providers.choices(self.app).items()],
            "fallback": [["", "none"], *[[k, v] for k, v in providers.choices(self.app).items()]],
            "classify": [["rules", "rules: no AI"], ["main", "main: your AI"], ["ollama", "ollama: a local model"]],
        },
        "updates": lambda self: {
            "mode": [
                ["night", "night: installs between the window's hours"],
                ["ask", "ask: a message with Update / Later"],
                ["off", "off: only a note in the dashboard"],
            ],
            "channel": [["stable", "stable: older and steadier"], ["beta", "beta: every version the day it's signed"]],
        },
        "power": lambda self: {
            "on_battery": [
                ["saver", "saver: heavy work waits for the charger"],
                ["normal", "normal: as on the charger"],
                ["pause", "pause: nothing runs on battery"],
            ],
        },
    }

    def _settings(self) -> dict:
        """Every setting you can change: the core sections (not the list of features that are on, which Features
        changes, nor Starting's, which has its own row) plus each enabled feature's own."""
        from kurooto.core import (  # noqa: F401 (their defaults)
            agent_export,
            dateoffers,
            hardware,
            health,
            helper,
            jobs,
            quota,
            sources,
            uninstall,
        )
        from kurooto.core.palette import settings_choices as look_choices

        allv = self.app.settings.all()
        sections = [s for s in self.EDITABLE] + [
            m.id for m in self.app.enabled() if m.id in allv and m.id not in self.EDITABLE
        ]
        out = []
        for sec in sections:
            vals = {k: v for k, v in (allv.get(sec) or {}).items() if k not in self.HIDDEN.get(sec, set())}
            if vals:
                title = self.app.modules[sec].title if sec in self.app.modules else self.TITLES.get(sec, sec.title())
                extra = look_choices(self.app, sec)
                if sec == "notes":  # notes.links is one of two (core/layout.py)
                    extra = {
                        "choices": {"links": [["wiki", "[[wikilinks]]"], ["markdown", "markdown: [Name](path.md)"]]}
                    }
                from kurooto.core import choices

                if choices.for_section(sec):  # settings with a known list of values (core/choices.py)
                    extra = {**extra, "choices": {**choices.for_section(sec), **(extra.get("choices") or {})}}
                if sec in self.CHOICES:  # one of a few values: a list to pick from, not a box to type a word into
                    extra = {**extra, "choices": {**self.CHOICES[sec](self), **(extra.get("choices") or {})}}
                tips = {k: t for k in vals if (t := _tips().get(f"{sec}.{k}"))}
                out.append({"section": sec, "title": title, "values": vals, "tips": tips, **extra})
        at = next((i + 1 for i, x in enumerate(out) if x["section"] == "power"), len(out))
        out.insert(at, self._autostart_section())  # Settings → Starting, after Power
        out.insert(at + 1, self._quick_ask_section())  # Settings → Quick ask: the command to bind to a key
        ai = next((i + 1 for i, x in enumerate(out) if x["section"] == "brain"), len(out))
        out.insert(ai, self._claude_section())  # Settings → Claude accounts, after the AI's own
        return {"sections": out}

    def _claude_section(self) -> dict:
        """Settings → Claude accounts: your usual sign-in, then each extra account with its name (changed through
        POST /api/brain/claude-accounts/rename) and a Remove button (…/remove, after a yes). Added on the setup
        page's AI step or with `kurooto ai add-claude`."""
        ca = providers.claude_accounts
        values: dict = {"claude": "your usual Claude sign-in"}
        fixed: dict = {"claude": "your usual Claude sign-in (claude)"}
        helps: dict = {
            "claude": "Add another account on the setup page (AI → Claude Code → Add another Claude account) or with "
            "`kurooto ai add-claude NAME`. Each is its own AI: use its id in brain.main or brain.fallback. " + ca.TERMS
        }
        for r in ca.rows(self.app):
            values[r["key"]] = r["name"]
            state = "working" if r["working"] else "not tested here yet"
            if not r["folder_here"]:
                state = "not signed in on this computer"
            if r["limited_until"]:
                state += f"; at its limit until {time.strftime('%a %H:%M', time.localtime(r['limited_until']))}"
            helps[r["key"]] = (
                f"{r['label']}, id {r['id']}: {state}. Type a new name to rename it (the id stays). Remove deletes "
                "only Kurooto's sign-in folder for it."
            )
        return {
            "section": "claude_accounts",
            "title": "Claude accounts",
            "values": values,
            "fixed": fixed,
            "help": helps,
            "post": "brain/claude-accounts/rename",
            "remove": "brain/claude-accounts/remove",
        }

    def _claude_accounts_post(self, action: str, b: dict) -> tuple[int, dict]:
        """add {name} (makes its folder and opens its sign-in window), signin {id}, rename {id, name} or {key: name}
        (Settings' rename box), remove {id, yes: true} (only after your yes: it deletes Kurooto's folder for it)."""
        ca = providers.claude_accounts
        try:
            if action == "add":
                acc = ca.add(self.app, str(b.get("name") or ""))
                ok, msg = self.prereqs.open_signin("claude", env=ca.env(self.app, acc.key))
                return 200, {
                    "ok": True,
                    "id": acc.id,
                    "label": acc.label,
                    "signin": ok,
                    "message": f"Added {acc.label}. "
                    + (msg if ok else msg + " Then sign in with your other Claude account, and test it."),
                    "accounts": ca.rows(self.app),
                }
            if action == "signin":
                acc = ca.get(self.app, str(b.get("id") or ""))
                if acc is None:
                    return 404, {"ok": False, "message": "No such Claude account."}
                ca.ensure_folder(self.app, acc.key)
                ok, msg = self.prereqs.open_signin("claude", env=ca.env(self.app, acc.key))
                return 200, {"ok": ok, "message": msg}
            if action == "rename":
                if "id" in b:
                    ref, name = str(b.get("id") or ""), str(b.get("name") or "")
                else:  # Settings' box: {key: new name}
                    pairs = [(k, v) for k, v in b.items() if isinstance(v, str)]
                    if len(pairs) != 1:
                        return 400, {"ok": False, "message": "Which account?"}
                    ref, name = pairs[0]
                acc = ca.rename(self.app, ref, name)
                return 200, {
                    "ok": True,
                    "message": f"Renamed: {acc.label} (still {acc.id}).",
                    "accounts": ca.rows(self.app),
                }
            if action == "remove":
                if b.get("yes") is not True:
                    return 400, {"ok": False, "message": "Removing needs your yes."}
                acc, changed = ca.remove(self.app, str(b.get("id") or ""))
                extra = f" Taken out of {', '.join(changed)}." if changed else ""
                if "brain.main" in changed:
                    extra += " It was your main AI: pick another in Settings → AI."
                return 200, {
                    "ok": True,
                    "message": f"Removed {acc.label} and Kurooto's sign-in folder for it.{extra}",
                    "accounts": ca.rows(self.app),
                }
        except ValueError as e:
            said = str(e)
            return 400, {"ok": False, "message": said[:1].upper() + said[1:] + "."}
        return 404, {"ok": False, "message": "No such action."}

    @staticmethod
    def _quick_ask_section() -> dict:
        """Settings → Quick ask: the command that opens the Quick ask window (kurooto/popup.py) on this computer, to
        bind to a key in the system's own settings, and how (core/shortcuts.py). Nothing to change here."""
        from kurooto.core import shortcuts

        cmd = shortcuts.shown(shortcuts.popup_command())
        return {
            "section": "quick_ask",
            "title": "Quick ask (hotkey)",
            "values": {"command": cmd},
            "fixed": {"command": cmd},
            "help": {"command": "Bind this command to a key in your system's settings. " + shortcuts.quick_ask_steps()},
        }

    def _autostart_section(self) -> dict:
        """Settings → Starting: when you log in, or (Linux with systemd) when this computer starts. It changes through
        POST /api/autostart ("post"), which also turns lingering on or off and moves the keys. Windows and macOS start
        at sign-in only, so they get a line that says so ("fixed")."""
        import sys

        sec = {"section": "autostart", "title": "Starting", "values": {"when": autostart.when(self.app.settings)}}
        ok, why = autostart.boot_possible()
        if not sys.platform.startswith("linux"):
            return {**sec, "fixed": {"when": "when you sign in"}, "help": {"when": why}}
        text = (
            "At boot, before anyone logs in, Telegram and calls work after a power cut or a remote reboot; Kurooto's "
            "keys then move to its owner-only settings file (the keychain is locked until you log in)."
        )
        if not autostart.status():
            text += " Right now Kurooto doesn't start by itself: `kurooto autostart on` turns that back on."
        elif not ok:
            text += " " + why
        choices = [["login", "at login"], ["boot", "at boot (before login)"]]
        return {**sec, "post": "autostart", "choices": {"when": choices}, "help": {"when": text}}

    def _set(self, key: str, value) -> tuple[int, dict]:
        from kurooto.core.palette import check as look_check
        from kurooto.web.server import DESIGNS

        sec = key.split(".")[0]
        if key in ("look.palette", "look.theme_file") and (wrong := look_check(self.app, key, value)):  # palette.py
            return 400, {"error": wrong}
        if key == "look.design" and value not in DESIGNS:  # the dashboard's design (web/server.py)
            return 400, {"error": f"look.design is one of: {', '.join(DESIGNS)}"}
        if key == "notes.links" and value not in ("wiki", "markdown"):  # how notes link (core/layout.py)
            return 400, {"error": "notes.links is wiki or markdown"}
        part = key.split(".")[1] if "." in key else ""
        # a whole section at once would take the hidden ones too, so only section.key
        if not part or (sec not in self.EDITABLE and not self.app.is_on(sec)) or part in self.HIDDEN.get(sec, set()):
            return 400, {"error": "not a setting you can change here"}
        if key == "you.timezone" and isinstance(value, str):  # saved under today's name (core/zones.py)
            from kurooto.core import zones

            value = zones.canonical(value)
        old = self.app.settings.get(key)
        if (
            old is not None
            and value is not None
            and type(old) is not type(value)
            and not (isinstance(old, (int, float)) and isinstance(value, (int, float)))
        ):
            return 400, {"error": f"{key} takes a {type(old).__name__}"}
        self.app.settings.set(key, value)
        self.app.events.emit("setting_changed", key=key)
        from kurooto.core import uninstall  # a setup or helper change that leaves a model unused: Remove / Keep

        said = uninstall.after_setting(self.app, key, value).strip()
        return 200, {"ok": True, **({"message": said} if said else {})}
