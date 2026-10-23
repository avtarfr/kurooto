"""What the setup wizard (and later the dashboard) can ask for and change."""

from __future__ import annotations

import os
import secrets
import threading
import time
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
    "skills",
    "hints",
    "library",
    "remember",
    "retro",
    "dreaming",
    "learning",
    "cases",
    "calls",
    "alarm",
    "lidsafe",
    "voice_notes",
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
    "terminals",
    "terminal",
    "overlay",
]


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
        if "freellmapi" in (self.app.settings.get("brain.main"), self.app.settings.get("brain.fallback")):
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
        for mid in [*MODULE_ORDER, *overlay.status(self.app)["modules"]]:
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
                    "extra": bool(getattr(m, "extra", False)),
                    "card": self._card(m),
                }
            )
        return out

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
        if path == "jobs":  # what the AI is working on and what waits (core/jobs.py; `kurooto jobs`)
            from kurooto.core.jobs import public

            return 200, {"active": [{**public(j), "line": self.app.jobs.line(j)} for j in self.app.jobs.active()]}
        if path == "term":  # the dashboard's terminals (modules/terminals.py)
            t = self.app.modules.get("terminals")
            on = bool(t) and self.app.is_on("terminals")
            return 200, {"on": on, "terms": t.listing() if on else []}
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
        if path == "events":
            return 200, {"events": self.app.events.tail(80)}
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
        if path == "jobs/cancel":  # a Cancel button on the AI jobs page, `kurooto jobs --cancel ID|all` (core/jobs.py)
            ref = str(b.get("id") or "").strip()
            if not ref:
                return 400, {"ok": False, "message": "which request?"}
            gone = ref.lower() == "all" or self.app.jobs.find(ref) is not None
            return 200, {"ok": gone, "message": self.app.jobs.cancel_text(ref)}
        if path == "health/fix":  # a Fix button on the dashboard, or `kurooto doctor --fix ID` (core/health.py)
            ok, message = self.app.health.fix(str(b.get("id") or ""))
            return 200, {"ok": ok, "message": message}
        if path.startswith("term/"):  # terminals: term/<name>/<attach|input|resize|leave|restart>
            t = self.app.modules.get("terminals")
            _, name, action = (path.split("/") + ["", ""])[:3]
            if not t or not self.app.is_on("terminals"):
                return 403, {"error": "Terminals is off"}
            return t.handle(name, action, b)
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
            if b.get("install"):  # Kurooto installs Ollama, the models and the programs, with progress on the page
                lm = self.app.modules["local_models"]
                out.update(self._background(lambda note: lm.setup(note), then_enable="local_models"), installing=True)
            return 200, out
        if path == "brain":
            which = b.get("main", "")
            if which and which not in providers.CHOICES:
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
                "modules": self._modules(),
            }
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
        if path == "mail/confidential/settle":  # a date found in confidential mail: add it to Deadlines, or not
            from kurooto.modules.google_confidential import settle

            return 200, {"message": settle(self.app, str(b.get("id", "")), bool(b.get("add")))}
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
            "ntfy_token": bool(self.app.secrets.get("calls.ntfy_token")),
            "ntfy_limited": calls.ntfy_limited(),
        }
        if calls.connector.connected:
            try:
                out["devices"] = calls.devices()
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
    )
    # the core sections' titles where the section's name alone says little
    TITLES = {
        "quota": "AI limits",
        "local_helper": "Offline helper",
        "health": "Health checks",
        "jobs": "AI jobs",
        "sources": "Sources for answers",
        "agents": "Skills in other AI programs",
        "hardware": "This computer",
        "web": "Dashboard",
    }
    # Settings the page neither shows nor changes: who may talk to the bot and where it connects (set by pairing), brain
    # addresses and models (POST /api/brain sets those, with its checks), the subject list and timetable (their own
    # pages).
    HIDDEN = {
        "telegram": {"api_base", "allowed_users", "chat_id"},
        "brain": {"base_urls", "models"},
        "subjects": {"list", "timetable"},
    }

    def _settings(self) -> dict:
        """Every setting you can change: the core sections (not the list of features that are on, which Features
        changes, nor Starting's, which has its own row) plus each enabled feature's own."""
        from kurooto.core import agent_export, hardware, health, helper, jobs, quota, sources  # noqa: F401 (defaults)
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
                out.append({"section": sec, "title": title, "values": vals, **look_choices(self.app, sec)})
        at = next((i + 1 for i, x in enumerate(out) if x["section"] == "power"), len(out))
        out.insert(at, self._autostart_section())  # Settings → Starting, after Power
        return {"sections": out}

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
        return 200, {"ok": True}
