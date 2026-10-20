"""What the setup wizard (and later the dashboard) can ask for and change."""

from __future__ import annotations

import os
import secrets
import threading
import time
from dataclasses import asdict
from typing import TYPE_CHECKING

from kurooto import __version__, providers
from kurooto.core import autostart, hardware
from kurooto.core.prereqs import Prereqs
from kurooto.core.state import jload, jsave
from kurooto.modules.telegram.api import TelegramError
from kurooto.providers.base import Verdict

if TYPE_CHECKING:
    from kurooto.app import App

STARTER = ["telegram", "chat", "reminders", "checkins", "deadlines"]  # GBrain: a 0.5 GB download, so it's opt-in
BRAIN_ORDER = [  # the first one is the ★ recommendation
    (
        "gemini",
        "A key from Google AI Studio: the simplest, and the way Google recommends for tools like this. Free "
        "tier, or paid. Phone calls and voice notes use it too.",
    ),
    (
        "agy",
        "Free with a Google account: Google's agent program, run on this computer as you; it can read your notes. "
        "Some risk to the account (see its note).",
    ),
    ("codex", "If you pay for ChatGPT: OpenAI's Codex, signed in with your ChatGPT account."),
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
    "gbrain",
    "local_models",
    "subjects",
    "capture",
    "quiz",
    "weekly",
    "files",
    "skills",
    "library",
    "remember",
    "retro",
    "calls",
    "alarm",
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
    "agent_plan",
    "handwritten",
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
        cached = jload(f, None)
        if cached and not refresh:
            return cached
        m = hardware.detect(self.app.paths.app)
        out = {"machine": m.to_dict(), "recommendation": asdict(hardware.recommend(m)), "at": time.time()}
        jsave(f, out)
        return out

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
                    "setup": hasattr(m, "setup"),
                    "form": m.setup_form() if hasattr(m, "setup_form") else None,
                    "addon": bool(getattr(m, "addon", False)),
                }
            )
        return out

    # ---------------------------------------------------------------------------------------------- GET
    def get(self, path: str, q: dict | None = None) -> tuple[int, dict]:
        q = q or {}
        from kurooto.web import tools_api  # the AI's tools, `kurooto ask`, `kurooto call`, AI usage

        if path in tools_api.GETS:
            return tools_api.get(self.app, path, q)
        if path == "term":  # the dashboard's terminals (modules/terminals.py)
            t = self.app.modules.get("terminals")
            on = bool(t) and self.app.is_on("terminals")
            return 200, {"on": on, "terms": t.listing() if on else []}
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
            s = self.app.settings
            tg = self.app.modules["telegram"]
            hw = self._hardware()
            models_gb = sum(x["size_gb"] for x in hw["recommendation"]["local_models"])
            return 200, {
                "version": __version__,
                "you": s.get("you"),
                "setup_done": bool(s.get("setup.done")),
                "hardware": hw,
                "brains": self._brains(),
                "brain": {"main": s.get("brain.main"), "fallback": s.get("brain.fallback")},
                "modules": self._modules(),
                "prereqs": self.prereqs.status(),
                "room": self.prereqs.room(["ollama"] if models_gb else [], extra_gb=models_gb),  # ★ AI: a key
                "telegram": {"token_set": bool(self.app.secrets.get("telegram.token")), "paired": tg.ready()[0]},
                "keys": {"gemini": bool(self.app.secrets.get("gemini.api_key"))},
                "power": self._power(),
                "autostart": autostart.status(),
                "workspace": str(self.app.workspace),
            }
        if path == "phone":
            return 200, self._phone()
        if path == "power":
            return 200, self._power()
        if path == "aboutyou/profile":  # the profile, for the editor (setup page and dashboard)
            return 200, self.app.about.view()
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
        if path == "morning":  # the morning page (rhythm)
            from kurooto.modules.daily import morning_view

            return 200, morning_view(self.app)
        if path == "mail/confidential":  # confidential mail summarised on this computer (google): read-only, local
            from kurooto.modules.google_confidential import view

            return 200, view(self.app, q.get("day"))
        return 404, {"error": "not found"}

    # --------------------------------------------------------------------------------------------- POST
    def post(self, path: str, b: dict) -> tuple[int, dict]:
        s = self.app.settings
        from kurooto.web import tools_api  # the AI's tools, `kurooto ask`, `kurooto call`

        if path in tools_api.POSTS:
            return tools_api.post(self.app, path, b)
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
        if path.startswith("profile/"):  # save now; restore on a new computer (modules/profile.py)
            from kurooto.modules.profile import web

            return web(self, path, b, post=True)
        if path == "settings":
            return self._set(b.get("key", ""), b.get("value"))
        if path == "open-note":
            return self._open_note(b.get("id", ""))
        if path == "you":
            for k in ("name", "timezone", "assistant_name"):
                if k in b and isinstance(b[k], str):
                    s.set(f"you.{k}", b[k].strip()[:80])
            return 200, {"ok": True}
        if path == "hardware/refresh":
            return 200, self._hardware(refresh=True)
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
            for mid in sorted(b.get("ids", []), key=lambda m: MODULE_ORDER.index(m) if m in MODULE_ORDER else 99):
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
        if path == "send-file":  # `kurooto send FILE`: a file from this computer to your Telegram
            from kurooto.modules.skills import send_file

            ok, message = send_file(self.app, str(b.get("path") or ""), str(b.get("caption") or "")[:900])
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
        if path == "phone/test":
            if not self.app.is_on("calls"):
                return 200, {"ok": False, "error": "Phone calls are off"}
            self.app.modules["calls"].ring("This is a test call from your computer. Answer to check it works.")
            return 200, {"ok": True}
        if path == "autostart":
            if os.environ.get("KUROOTO_NO_AUTOSTART") == "1":  # tests and rehearsals leave this computer alone
                return 200, {"ok": True, "message": "Start at sign-in is left alone here (KUROOTO_NO_AUTOSTART)."}
            if b.get("when") in ("boot", "login"):  # at boot (Linux: lingering) or at login
                ok, msg = autostart.set_when(b["when"], s, self.app.secrets, self.app.paths.state)
                return 200, {"ok": ok, "message": msg, "when": autostart.when(s)}
            msg = autostart.enable() if b.get("on", True) else autostart.disable()
            return 200, {"ok": True, "message": msg}
        if path == "setup/done":
            s.set("setup.done", True)
            on = [m.title for m in self.app.enabled()]
            self.app.notify(f"{self.app.name} is set up. On: {', '.join(on)}. Send /help any time.")
            return 200, {"ok": True}
        if path == "ask" or path.startswith("ask/"):
            return self._ask(path, b, post=True)
        if path == "mail/confidential/settle":  # a date found in confidential mail: add it to Deadlines, or not
            from kurooto.modules.google_confidential import settle

            return 200, {"message": settle(self.app, str(b.get("id", "")), bool(b.get("add")))}
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
        out = {"on": True, **calls.status(), "devices": None}
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
            with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310
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
            if which == "agy":  # setting agy up: give it Kurooto's tools (`kurooto mcp`) now; and it may stand in
                from kurooto.providers.agy import connect_tools, mark_worked  # for the Gemini key later

                mark_worked(self.app.paths.state)
                ok_t, why = connect_tools(self.app, brain.exe)
                msg += (
                    " It can now use Kurooto's tools, read your notes, Documents and Downloads, and write in your "
                    "notes folder."
                    if ok_t
                    else f" (It can't use Kurooto's tools yet: {why}.)"
                )
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
        import subprocess
        import sys as _sys

        p = self._note_path(nid)
        if not p:
            return 404, {"error": "no such note"}
        if _sys.platform == "win32":
            import os as _os

            _os.startfile(str(p))  # noqa: S606 (opens the user's own note in their default app)
        else:
            subprocess.Popen(["open" if _sys.platform == "darwin" else "xdg-open", str(p)], start_new_session=True)
        return 200, {"ok": True}

    EDITABLE = ("you", "notify", "availability", "updates", "brain", "ask", "look", "power", "notes", "files")

    def _settings(self) -> dict:
        """Every setting you can change: the core sections plus each enabled feature's own."""
        from kurooto.core.palette import settings_choices as look_choices

        allv = self.app.settings.all()
        sections = [s for s in self.EDITABLE] + [
            m.id for m in self.app.enabled() if m.id in allv and m.id not in self.EDITABLE
        ]
        hidden = {
            "telegram": {"api_base", "allowed_users", "chat_id"},
            "brain": {"base_urls", "models"},
            "subjects": {"list", "timetable"},
        }
        out = []
        for sec in sections:
            vals = {k: v for k, v in (allv.get(sec) or {}).items() if k not in hidden.get(sec, set())}
            if vals:
                title = self.app.modules[sec].title if sec in self.app.modules else sec.title()
                out.append({"section": sec, "title": title, "values": vals, **look_choices(self.app, sec)})
        return {"sections": out}

    def _set(self, key: str, value) -> tuple[int, dict]:
        from kurooto.core.palette import check as look_check

        sec = key.split(".")[0]
        if key in ("look.palette", "look.theme_file") and (wrong := look_check(self.app, key, value)):  # palette.py
            return 400, {"error": wrong}
        if sec not in self.EDITABLE and not self.app.is_on(sec):
            return 400, {"error": "not a setting you can change here"}
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
