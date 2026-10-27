"""The offline helper: a small model on this computer (about 1 GB, through Ollama) for quick decisions on computers
without a graphics card, and the stand-in while the internet is down.

Quick decisions only, never answers to your requests while you're online:
    effort    how hard a request is (low, medium, high) when the rules would otherwise decide alone, or when your AI's
              free limit is kept for you (providers/effort.py, core/jobs.py:_classifier)
    intent    which instant request a short message means when no pattern takes it but some are near (core/repair.py's
              readings, only requests that don't send, delete or call): it picks one by number, or none
    yes/no    a short reply to "Still true?" that isn't a plain yes or no (modules/remember.py)
Each decision waits at most local_helper.timeout_s (4 s); a slow, unsure or failed answer leaves it to the rules.

It's used only after a speed test passes here: a warm-up (loading the model), then three one-word answers, the middle
one within local_helper.max_s (1.5 s). A model too slow here is removed again (only when Kurooto downloaded it just
now) and the helper stays off. The model comes from data/ollama_models.toml ("cpu-helper"), or local_helper.model.

Offered once, with Install / Not now (Calm, local_helper.offer), two weeks after Kurooto started here, on a computer
whose hardware profile has no helper model of its own (no graphics card) and enough memory and disk, when the free AI
limit ran short on TIGHT_DAYS of the last two weeks (core/quota.py's reserve or a used-up limit) or the internet
dropped OUTAGES times in that time. Not now asks once more, a month later. /helper on sets it up any time.

Offline (local_helper.offline, on): when the internet is down, as Kurooto's own traffic finds it (core/egress.py:
net_down, requests to two or more hosts failing with no answer since; core/presence.py:net_down, Telegram and the call
line not answering, unless another host answered since; nothing extra is pinged), a quick question to Chat is
answered here with a line saying so, and AI requests that need the internet wait in the queue (core/jobs.py:_hold)
and run once it's back: you're told once that it waits, the answer says it waited, and when the connection comes back
one line says what's running now. One that waited local_helper.hold_h (24 h) ends with a message. Never dropped
silently. Without the helper, quick things are left to the rules and everything else waits the same way.

State: state/local-helper.json (the speed test, outages seen, the offer). Nothing leaves the computer except the one
download, which Ollama makes from its registry (counted as handed to Ollama, core/egress.py).
"""

from __future__ import annotations

import datetime as dt
import json
import re
import statistics
import threading
import time
import uuid
from typing import TYPE_CHECKING

from kurooto.core import egress
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "local_helper",
    {
        "on": False,  # the offline helper: a small model on this computer for quick decisions (/helper on sets it up)
        "model": "",  # its Ollama model; empty: the one in ollama_models.toml (cpu-helper, about 1 GB)
        "max_s": 1.5,  # its speed test: a one-word answer must come within this many seconds, or it stays off
        "timeout_s": 4,  # a quick decision waits this long for it, then the rules decide
        "offline": True,  # with the internet down: quick things answered here, AI requests wait until it's back
        "hold_h": 24,  # a request waits this many hours for the connection, then says it couldn't run
        "offer": True,  # after two weeks, offer it once when the free AI limit runs short or the internet often drops
    },
)

FILE = "local-helper.json"
TABLE_KEY = "cpu-helper"  # its row in data/ollama_models.toml
WARM_S = 180  # the speed test's warm-up (loading the model into memory) may take this long
TESTS = 3  # timed one-word answers after the warm-up; the middle one counts
SPEED_Q = "Is ice cold? Answer with one word: yes or no."
HAVE_S = 600  # "the model is there" is believed this long
RETRY_S = 120  # a request waiting for the connection looks again this often
QUICK_CHARS = 240  # offline, a question this short (and judged low effort) is answered here
NEAR = 0.6  # a reading this close (core/repair.py) is put to the helper
MIN_RAM_GB = 4.0
OFFER_AFTER_D = 14
WINDOW_D = 14
TIGHT_DAYS = 3
OUTAGES = 3
OUTAGE_MIN_S = 300  # shorter drops aren't counted as outages
AGAIN_D = 30
OFFERS = 2  # at most this many offers, ever
KEEP_D = 30
ANSWER = (
    "You are a small offline helper on the user's computer; the internet is down. Answer the question below in at most "
    "two short sentences, from general knowledge only. If it needs the user's notes, files, calendar, messages, "
    "today's date or the internet, answer exactly CANNOT.\n\nQuestion: {text}"
)


def _words(raw: str | None) -> list[str]:
    return re.findall(r"[a-z0-9]+", (raw or "").lower())


class Helper:
    def __init__(self, app: App):
        self.app = app
        self.file = app.paths.state / FILE
        self.clock = time.time  # tests use a fake clock
        self.timer = time.monotonic  # ...and a fake stopwatch for the speed test
        self._lock = threading.RLock()
        self._have: tuple[float, str, bool] = (0.0, "", False)
        self._busy = threading.Lock()  # one setup or speed test at a time

    # ------------------------------------------------------------------------------------------ settings
    def s(self, key: str):
        return self.app.settings.get(f"local_helper.{key}")

    def number(self, key: str, default: float) -> float:
        try:
            v = float(self.s(key))
            return v if v > 0 else default
        except (TypeError, ValueError):
            return default

    def state(self) -> dict:
        return jload(self.file, {}) or {}

    def _update(self, **kw) -> dict:
        with self._lock:
            st = self.state()
            st.update(kw)
            jsave(self.file, st)
            return st

    def lm(self):
        return self.app.modules.get("local_models")

    def model(self) -> dict:
        """{"tag", "size_gb"}: local_helper.model, or the table's cpu-helper."""
        from kurooto.core.hardware import _models

        row = dict((_models().get("models") or {}).get(TABLE_KEY) or {})
        tag = str(self.s("model") or "").strip()
        if tag and tag != row.get("tag"):
            sizes = jload(self.app.paths.state / "model-sizes.json", {}) or {}
            return {"tag": tag, "size_gb": float(sizes.get(tag) or 1.0)}
        return {"tag": row.get("tag") or "", "size_gb": float(row.get("size_gb") or 1.0)}

    # ------------------------------------------------------------------------------------------ the model
    def tested(self) -> bool:
        test = self.state().get("test") or {}
        return bool(test.get("ok")) and test.get("model") == self.model()["tag"]

    def ready(self) -> bool:
        """On, its speed test passed for this model, and Ollama has the model."""
        return bool(self.s("on")) and self.tested() and self._present()

    def _present(self) -> bool:
        tag, t = self.model()["tag"], self.clock()
        at, was, ok = self._have
        if was == tag and t - at < HAVE_S:
            return ok
        lm = self.lm()
        ok = bool(lm is not None and tag in lm.have())
        self._have = (t, tag, ok)
        return ok

    def _generate(self, prompt: str, tokens: int, timeout: float) -> str | None:
        """One answer from the model (Ollama's /api/generate on this computer), or None."""
        lm = self.lm()
        if lm is None:
            return None
        body = {
            "model": self.model()["tag"],
            "prompt": prompt,
            "stream": False,
            "keep_alive": "30m",
            "options": {"temperature": 0, "num_predict": tokens},
        }
        try:
            with lm.api("/api/generate", body, timeout=timeout) as r:
                return str(json.loads(r.read()).get("response") or "").strip()
        except (OSError, ValueError):
            return None

    def word(self, prompt: str, choices: tuple[str, ...]) -> str | None:
        """A one-word decision among choices, or None (not ready, slow, or not one of them)."""
        if not self.ready():
            return None
        raw = self._generate(prompt, 4, self.number("timeout_s", 4))
        got = next((w for w in _words(raw) if w in choices), None)
        self.app.events.emit("helper_decided", answered=got is not None)
        return got

    def classifier(self):
        """For providers/effort.py: the helper's "how hard is this", or None when it isn't ready."""
        if not self.ready():
            return None
        return lambda q: self.word(q, ("low", "medium", "high"))

    def pick(self, text: str, rows: list[dict]) -> dict | None:
        """Which of the near readings (core/repair.py) the message means, or None (none, or not sure)."""
        rows = [r for r in rows if r.get("score", 0) >= NEAR][:3]
        if not rows or not self.ready():
            return None
        listed = "\n".join(f"{i}: {r['means']}" for i, r in enumerate(rows, 1))
        q = (
            f'Someone wrote to their assistant: "{text[:300]}"\nWhich of these requests is it? Answer with the number '
            f"only, or 0 if it is none of them.\n{listed}"
        )
        got = self.word(q, tuple(str(i) for i in range(len(rows) + 1)))
        return rows[int(got) - 1] if got and got != "0" else None

    def yes_no(self, question: str, reply: str) -> bool | None:
        """A short reply to a yes/no question: True, False, or None (it says something else, or not sure)."""
        if len(reply.split()) > 6:
            return None
        q = (
            f'The assistant asked: "{question[:200]}"\nThe user replied: "{reply[:100]}"\nAnswer with one word: yes if '
            "the reply means yes and adds nothing, no if it means no and adds nothing, other if it says anything else."
        )
        got = self.word(q, ("yes", "no", "other"))
        return True if got == "yes" else False if got == "no" else None

    # ------------------------------------------------------------------------------------------ offline
    def offline(self) -> bool:
        """Is the internet down, as Kurooto's own traffic finds it (nothing is pinged for this)? Requests to two or
        more hosts failing, or Telegram and the call line not answering while nothing else has answered since (when
        something has, it's those services, not the internet)."""
        if egress.net_down():
            return True
        pres = getattr(self.app, "presence", None)
        if pres is None or not pres.net_down():
            return False
        return not egress.answered_since(float(pres.net_fail_since or 0))

    def sure(self) -> bool:
        """Down for certain: Kurooto's requests to two or more hosts are failing. Otherwise a request that waited
        once tries again when its time comes, its own request being the check."""
        return egress.net_down()

    def holds(self) -> bool:
        """AI requests that need the internet wait now."""
        return bool(self.s("offline")) and self.offline()

    def lost(self, since: float) -> bool:
        """A request that failed after `since`: was it for want of a connection (so it waits instead)?"""
        return bool(self.s("offline")) and (self.offline() or egress.failed_since(since))

    def hold_s(self) -> float:
        return self.number("hold_h", 24) * 3600

    @staticmethod
    def here(brain) -> bool:
        """A brain that runs on this computer (Ollama, a local server): it needs no internet."""
        local = getattr(brain, "local", None)
        return bool(callable(local) and local())

    def waiting_line(self, title: str = "") -> str:
        what = f'"{title[:60]}"' if title else "it"
        return f"No internet connection right now: {what} waits and runs as soon as it's back."

    def offline_reply(self, text: str, files: bool = False) -> str | None:
        """Chat, with the internet down: a quick question answered here, with a line saying so; None otherwise."""
        text = text.strip()
        if files or not text or len(text) > QUICK_CHARS or not self.holds() or not self.ready():
            return None
        from kurooto.providers import effort

        if effort.pick(text, self.classifier()) != "low":
            return None
        said = self._generate(ANSWER.format(text=text), 160, max(30.0, self.number("timeout_s", 4) * 8))
        if not said or "CANNOT" in said.upper():
            return None
        self.app.events.emit("helper_offline_answer", chars=len(said))
        return (
            f"{said}\n\n(The offline helper answered: a small model on this computer, as the internet is down. Ask "
            "again once it's back for your AI's answer.)"
        )

    # ------------------------------------------------------------------------------------------ running
    def start(self) -> None:
        with self._lock:
            st = self.state()
            if not st.get("since"):  # two weeks from here (or from Keep's own start, whichever came first)
                self._update(since=self.clock())
        sch = self.app.scheduler
        sch.action("local_helper.tick", lambda p: self.tick())
        sch.every("local_helper:tick", "every 1m", "local_helper.tick", module="local_helper")
        sch.action("local_helper.offer", lambda p: self.maybe_offer())
        sch.every("local_helper:offer", "daily 12:30", "local_helper.offer", module="local_helper", respect="quiet")

    def tick(self) -> str:
        """Every minute: the internet going down or coming back (outages kept; waiting requests run when it's back),
        and Ollama kept running while the helper is on."""
        t = self.clock()
        down = self.offline()
        st = self.state()
        since = st.get("down_since")
        said = ""
        if down and not since:
            self._update(down_since=t)
            self.app.events.emit("helper_offline", by="presence" if self._presence_down() else "egress")
            said = "down"
        elif not down and since:
            outages = [o for o in st.get("outages") or [] if isinstance(o, list) and o[1] > t - KEEP_D * 86400]
            if t - float(since) >= OUTAGE_MIN_S:
                outages.append([round(float(since)), round(t)])
            self._update(down_since=None, outages=outages)
            self.app.events.emit("helper_online", minutes=round((t - float(since)) / 60))
            self.back()
            said = "back"
        if self.s("on") and not down and int(t // 60) % 10 == 0 and self.app.power.current == "normal":
            lm = self.lm()
            if lm is not None and not lm.running():
                lm.serve()
        return said

    def _presence_down(self) -> bool:
        pres = getattr(self.app, "presence", None)
        return bool(pres is not None and pres.net_down())

    def back(self) -> int:
        """The connection is back: requests that waited run now, and you're told which (your own ones)."""
        jobs = getattr(self.app, "jobs", None)
        if jobs is None:
            return 0
        mine = jobs.unhold()
        if mine:
            from kurooto.core.calm import ASKED

            names = "; ".join(f'"{t[:50]}"' for t in mine[:3]) + (f" and {len(mine) - 3} more" if len(mine) > 3 else "")
            self.app.notify(f"The internet is back: running what waited for it ({names}).", kind="info", why=ASKED)
        return len(mine)

    # ------------------------------------------------------------------------------------------ setting up
    def eligible(self) -> tuple[bool, str]:
        """Is this a computer the helper is for: no helper model of its own (no graphics card), enough memory?"""
        lm = self.lm()
        try:
            wanted = lm.wanted() if lm is not None else []
        except Exception:
            wanted = []
        if any(str(m.get("key") or "").startswith("helper") for m in wanted):
            return False, "this computer runs a bigger helper model already (Local AI models)"
        machine = (jload(self.app.paths.state / "hardware.json", {}) or {}).get("machine") or {}
        ram = machine.get("ram_gb")
        if isinstance(ram, (int, float)) and ram < MIN_RAM_GB:
            return False, f"this computer has {ram:g} GB of memory; the helper wants {MIN_RAM_GB:g} GB or more"
        return True, ""

    def room(self) -> dict:
        """The storage check (core/prereqs.py:room): Ollama, if it isn't installed, and the model."""
        lm = self.lm()
        need = [] if lm.prereqs.items["ollama"].find() else ["ollama"]
        return lm.prereqs.room(need, extra_gb=self.model()["size_gb"])

    def setup(self, progress=print) -> tuple[bool, str]:
        """Install Ollama if needed, download the model (after the storage check), run the speed test, and turn the
        helper on only if it passes."""
        if not self._busy.acquire(blocking=False):
            return False, "The offline helper is being set up already."
        try:
            return self._setup(progress)
        finally:
            self._busy.release()

    def _setup(self, progress) -> tuple[bool, str]:
        lm, m = self.lm(), self.model()
        if lm is None or not m["tag"]:
            return False, "Local AI models aren't part of this Kurooto."
        room = self.room()
        if not room["ok"]:
            return False, (
                f"Not enough space for the offline helper ({room['need_gb']:g} GB; {room['free_gb']:g} GB free and "
                f"{room['margin_gb']:g} GB kept spare)."
            )
        if not lm.prereqs.items["ollama"].find():
            ok, msg = lm.prereqs.install("ollama", progress)
            if not ok:
                return False, msg
        if not lm.serve():
            return False, "Ollama is installed but its server didn't start; restart the computer and try again."
        pulled = False
        if m["tag"] not in lm.have():
            ok, msg = lm.pull(m["tag"], m["size_gb"], progress, feature="Offline helper", by="local_helper")
            if not ok:
                return False, msg
            pulled = True
        self._have = (0.0, "", False)
        progress("Timing a one-word answer…")
        ok, secs = self.speed_test()
        limit = self.number("max_s", 1.5)
        if not ok:
            self.app.settings.set("local_helper.on", False)
            gone = pulled and lm.remove(m["tag"])
            said = "too slow" if secs < 1e6 else "no answer"
            took = f"{secs:.1f} s" if secs < 1e6 else "no answer"
            self.app.events.emit("helper_setup", ok=False, seconds=None if secs >= 1e6 else round(secs, 2))
            return False, (
                f"The offline helper is {said} here ({took} for a one-word answer; it needs {limit:g} s or less), so "
                f"it stays off{'; its model was removed again' if gone else ''}. Quick decisions stay with the rules "
                "and your AI, and with the internet down your requests still wait until it's back."
            )
        self.app.settings.set("local_helper.on", True)
        self.app.events.emit("helper_setup", ok=True, seconds=round(secs, 2))
        return True, (
            f"The offline helper is on ({m['tag']}, {secs:.1f} s for a one-word answer). It takes the quick decisions "
            "now, and answers quick questions when the internet is down. /helper off turns it off."
        )

    def speed_test(self) -> tuple[bool, float]:
        """A warm-up, then TESTS timed one-word answers: (passed, the middle time). Kept in the state file."""
        tag, limit = self.model()["tag"], self.number("max_s", 1.5)
        if self._generate(SPEED_Q, 2, WARM_S) is None:
            secs = float("inf")
        else:
            times = []
            for _ in range(TESTS):
                t0 = self.timer()
                got = self._generate(SPEED_Q, 2, 30)
                times.append(self.timer() - t0 if got is not None else float("inf"))
            secs = statistics.median(times)
        ok = secs <= limit
        test = {"ok": ok, "model": tag, "at": self.clock(), "seconds": None if secs == float("inf") else round(secs, 2)}
        self._update(test=test)
        return ok, secs if secs != float("inf") else 1e9

    def turn_off(self) -> str:
        self.app.settings.set("local_helper.on", False)
        from kurooto.core import uninstall  # a model Kurooto downloaded for it: Remove / Keep (uninstall.offer)

        said = uninstall.after_off(self.app, "local_helper")
        stays = "" if said else " Its model stays in Ollama (about 1 GB; /helper on uses it again)."
        return f"The offline helper is off.{stays} With the internet down, requests still wait until it's back.{said}"

    def _in_background(self, fn, label: str) -> None:
        from kurooto.core.calm import ASKED

        def go():
            try:
                said = fn()[1]
            except Exception as e:  # never a silent failure
                said = f"Setting up the offline helper failed: {type(e).__name__}: {e}"[:300]
            self.app.notify(said, kind="info", title=label, why=ASKED)

        threading.Thread(target=go, name="local-helper", daemon=True).start()

    # ------------------------------------------------------------------------------------------ the offer
    def tight_days(self) -> int:
        """Days in the last two weeks the free AI limit ran short (the reserve held background work, or it was used
        up), from the event log."""
        cut = dt.datetime.fromtimestamp(self.clock() - WINDOW_D * 86400).isoformat()
        days = {
            str(e.get("ts", ""))[:10]
            for e in self.app.events.tail(300, {"quota_reserve", "quota_limit"})
            if str(e.get("ts", "")) >= cut
        }
        return len(days)

    def outages(self) -> int:
        t = self.clock()
        return len([o for o in self.state().get("outages") or [] if o[1] > t - WINDOW_D * 86400])

    def why_offer(self) -> str | None:
        """ "limit", "offline", or None: whether it's time to offer the helper, and why."""
        if not self.s("offer") or self.s("on") or not self.app.settings.get("setup.done"):
            return None
        st, t = self.state(), self.clock()
        offer = st.get("offer") or {}
        if int(offer.get("count") or 0) >= OFFERS or t - float(offer.get("at") or 0) < AGAIN_D * 86400:
            return None
        keep = getattr(self.app, "keep", None)
        starts = [float(x) for x in (st.get("since"), keep.state().get("since") if keep else None) if x]
        if not starts or t - min(starts) < OFFER_AFTER_D * 86400:
            return None
        why = "limit" if self.tight_days() >= TIGHT_DAYS else "offline" if self.outages() >= OUTAGES else None
        if why is None or not self.eligible()[0]:
            return None
        try:
            if not self.room()["ok"]:
                return None
        except (OSError, KeyError):
            return None
        return why

    def maybe_offer(self) -> bool:
        why = self.why_offer()
        if why is None:
            return False
        m = self.model()
        head = (
            f"Your free AI limit ran short on {self.tight_days()} of the last {WINDOW_D} days."
            if why == "limit"
            else f"The internet dropped {self.outages()} times in the last {WINDOW_D} days."
        )
        text = (
            f"{head} A small model on this computer ({m['tag']}, about {m['size_gb']:g} GB to download) could take "
            "the quick decisions (how hard a request is, which request you meant), so more of the limit is left for "
            "answers; with the internet down it answers quick questions and keeps the rest until it's back. It runs on "
            "the processor, so it's only used if a short speed test after the download passes here."
        )
        ref = uuid.uuid4().hex[:8]
        st = self.state()
        offer = st.get("offer") or {}
        self._update(offer={"count": int(offer.get("count") or 0) + 1, "at": self.clock(), "why": why, "ref": ref})
        self.app.notify(
            text,
            kind="question",
            title="Offline helper",
            why="local_helper.offer",
            buttons=[[("Install", f"lh:{ref}:install"), ("Not now", f"lh:{ref}:later")]],
        )
        self.app.events.emit("helper_offered", why=why)
        return True

    def button(self, ref: str, act: str) -> str:
        """Install / Not now under the offer ("lh:<ref>:install")."""
        if act == "later":
            self.app.events.emit("helper_offer_answered", install=False)
            return "OK. /helper on sets it up any time."
        if act != "install":
            return "unknown button"
        if self.s("on") and self.tested():
            return "The offline helper is on already."
        self.app.events.emit("helper_offer_answered", install=True)
        self._in_background(lambda: self.setup(progress=lambda s: None), "Offline helper")
        return "Setting up the offline helper; I'll say when it's ready."

    # ------------------------------------------------------------------------------------------ /helper
    def status(self) -> str:
        m, st = self.model(), self.state()
        test = st.get("test") or {}
        if self.ready():
            head = f"The offline helper is on: {m['tag']}"
        elif self.s("on") and not self.tested():
            head = f"The offline helper is set to on, but {m['tag']} hasn't passed its speed test (/helper test)"
        elif self.s("on"):
            head = f"The offline helper is on, but Ollama doesn't have {m['tag']} or isn't running (/helper on)"
        else:
            head = f"The offline helper is off ({m['tag']}, about {m['size_gb']:g} GB; /helper on sets it up)"
        lines = [head + "."]
        if test.get("model") == m["tag"] and test.get("at"):
            when = dt.datetime.fromtimestamp(float(test["at"])).strftime("%d %b")
            secs = f"{test['seconds']:.1f} s" if test.get("seconds") is not None else "no answer"
            lines.append(
                f"Speed test ({when}): {secs} for a one-word answer; it needs {self.number('max_s', 1.5):g} s or less."
            )
        if self.offline():
            lines.append("The internet is down now: AI requests wait until it's back.")
        jobs = getattr(self.app, "jobs", None)
        n = jobs.held() if jobs is not None else 0
        if n:
            lines.append(f"{n} request{'s wait' if n != 1 else ' waits'} for the connection.")
        if not self.s("offline"):
            lines.append("With the internet down, requests fail as before (local_helper.offline is off).")
        return "\n".join(lines)

    def command(self, arg: str = "") -> str:
        """/helper: how it's doing; /helper on, off, test."""
        a = arg.strip().lower()
        if a in ("on", "install", "setup"):
            if self.ready():
                return "The offline helper is on already."
            ok, why = self.eligible()
            note = f" (Note: {why}.)" if not ok else ""
            self._in_background(lambda: self.setup(progress=lambda s: None), "Offline helper")
            return f"Setting up the offline helper ({self.model()['tag']}); I'll say when it's ready.{note}"
        if a == "off":
            return self.turn_off()
        if a == "test":
            lm = self.lm()
            if lm is None or self.model()["tag"] not in lm.have():
                return "The offline helper's model isn't here: /helper on sets it up."

            def retest():
                ok, secs = self.speed_test()
                limit = self.number("max_s", 1.5)
                took = f"{secs:.1f} s" if secs < 1e6 else "no answer"
                if not ok:
                    self.app.settings.set("local_helper.on", False)
                    return False, f"Speed test: {took}; it needs {limit:g} s or less, so the offline helper is off."
                return True, f"Speed test: {took} (it needs {limit:g} s or less). /helper on uses it."

            self._in_background(retest, "Offline helper")
            return "Timing it; I'll say how it went."
        return self.status()
