"""When Google's live voice (Gemini Live) won't take a call, the call still happens. Three ways, tried in order (the
call page drives them; see data/worker/web/fallback.js):

1. Live again: a start that Google refuses for now (503 UNAVAILABLE, 429) is tried again after about 1 s and 3 s,
   each time with the next model in calls.live_models; a drop in the middle of a call is tried again once.
2. Turn by turn: the phone's own speech recognition and voice. Each turn comes here through your call line (/turn)
   and is answered by a quick text AI (your Gemini key, or the model on this computer; never an agent program, which
   takes seconds to start) with the call's own instructions, script and tools. While this computer is off, or when it
   doesn't answer in time, a Gemini text model with your key answers on the call line instead.
   This is also a mode you can choose (calls.voice_mode = "phone", or per kind of call in calls.voice_by_kind):
   then calls don't use Live at all, and on Android 13+ the speech is recognised on the phone.
3. Text on Telegram: the phone has no speech recognition or microphone, so the call goes on as messages, about the
   same thing (a check-in stays a check-in). Reply to its messages, or just type; End (or 20 quiet minutes) ends it.

Whichever way it went, the transcript is kept and goes to the feature that placed the call, as with any call (a
check-in's becomes your journal and study logs). Live's failures and what calls did instead are counted for
`kurooto doctor` ("Phone calls: voice service") and the dashboard.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import threading
import time
import uuid
from typing import TYPE_CHECKING

from kurooto.core.clock import now
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.modules.base import Incoming
    from kurooto.modules.calls import Calls

TURN_S = 25  # a turn not answered here by then is answered on the call line (it waits 55 s for this computer)
TEXT_IDLE_S = 20 * 60  # a call on Telegram with no message for this long is over
LATE_S = 2 * 3600  # a call handed to Telegram while this computer was off still starts this long after
KEEP = 300  # health records kept per kind
WHY = {
    "live": "the voice service is down",
    "no_speech": "this phone can't turn speech into text",
    "no_mic": "the microphone isn't available",
}
LAYER = {"live": "live voice", "turns": "turn by turn", "telegram": "text on Telegram", "text": "text on Telegram"}


def spoken(text: str, n: int = 1500) -> str:
    """An answer as it's said (or texted) on a call: no markdown, links as their words."""
    s = re.sub(r"```.*?```", " ", str(text or ""), flags=re.S)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"(?m)^\s{0,3}(#{1,6}|[-*+]|\d+[.)])\s+", "", s)
    s = re.sub(r"[*_`~|>#]+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _when(ts: float) -> str:
    t = dt.datetime.fromtimestamp(ts)
    return f"{t:%H:%M}" if t.date() == now().date() else f"{t:%a %H:%M}"


def _ts(v) -> float:
    """An event's time (ISO from the call line's queue), else now."""
    try:
        return dt.datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return time.time()


# ----------------------------------------------------------------------------------------------- health
class LiveHealth:
    """How often Gemini Live failed, a retry got through, and a call went on another way (state: live-health.json)."""

    def __init__(self, calls: Calls):
        self.app = calls.app
        self.file = calls.dir / "live-health.json"

    def record(self, name: str, m: dict) -> None:
        kind = {"live_failed": "failed", "live_recovered": "recovered", "call_fallback": "fallback"}.get(name)
        if not kind:
            return
        rec = {"at": _ts(m.get("at"))}
        for k in ("model", "code", "status", "stage", "layer", "why", "attempt"):
            if m.get(k) not in (None, ""):
                rec[k] = m[k] if isinstance(m[k], int) else str(m[k])[:80]
        with Lock(self.app.paths.state, "calls-live-health"):
            d = jload(self.file, {}) or {}
            d[kind] = (d.get(kind) or [])[-(KEEP - 1) :] + [rec]
            jsave(self.file, d)
        self.app.events.emit(
            f"call_{name}" if not name.startswith("call_") else name,
            **{k: v for k, v in rec.items() if k != "at"},
        )

    def summary(self, days: int = 7) -> dict:
        cut = time.time() - days * 86400
        d = jload(self.file, {}) or {}
        recent = {k: [r for r in d.get(k) or [] if r.get("at", 0) >= cut] for k in ("failed", "recovered", "fallback")}
        last = recent["failed"][-1] if recent["failed"] else None
        layers: dict[str, int] = {}
        for r in recent["fallback"]:
            layers[r.get("layer", "?")] = layers.get(r.get("layer", "?"), 0) + 1
        return {
            "days": days,
            "failed": len(recent["failed"]),
            "recovered": len(recent["recovered"]),
            "fallbacks": layers,
            "last": last,
        }

    def line(self) -> tuple[bool | None, str]:
        """For `kurooto doctor`: a note (not a problem: Google's outages aren't yours to fix) with the counts."""
        s = self.summary()
        if not s["failed"] and not s["fallbacks"]:
            return True, f"Gemini Live: no failures in the last {s['days']} days"
        out = f"Gemini Live failed {s['failed']} time{'s' if s['failed'] != 1 else ''} in {s['days']} days"
        last = s["last"]
        if last:
            what = " ".join(str(x) for x in (last.get("code") or "", last.get("status") or "") if x) or "an error"
            out += f" (last {_when(last['at'])}: {what}{', ' + last['model'] if last.get('model') else ''})"
        parts = []
        if s["recovered"]:
            parts.append(f"{s['recovered']} got through on a retry")
        for layer, n in sorted(s["fallbacks"].items()):
            parts.append(f"{n} went on {LAYER.get(layer, layer)}")
        if parts:
            out += "; calls: " + ", ".join(parts)
        return None, out


# --------------------------------------------------------------------------------------- the prompt
def turn_prompt(calls: Calls, lines: list[dict], purpose: str, mode: str, note: str = "") -> str:
    """One turn of a call that isn't on Live, for the text AI: the call's own instructions (the same as Live's), why it
    was placed, how to talk in this mode, what needs attention (pending_items) before the first answer, the call so
    far, and a note such as "[The call just connected. Speak first.]"."""
    app = calls.app
    cfg = calls.config_template()
    texts = calls.texts()
    si = str(cfg.get("systemInstruction") or "").replace("%%NOW%%", f"{now():%A %d %B %Y, %H:%M}")
    if purpose:
        si += "\n" + texts["purpose"].replace("%%REASON%%", purpose[:300])
    si += "\n" + texts["turns" if mode == "turns" else "text_call"]
    out = [si]
    if not any(x.get("who") == app.name for x in lines):
        try:
            brief = json.dumps(calls.pending(), ensure_ascii=False, default=str)[:4000]
        except Exception as e:
            brief = f"(couldn't get it: {e})"
        out.append(f"pending_items, already called for you: {brief}")
    if lines:
        out.append("The call so far:\n" + "\n".join(f"{x.get('who') or '?'}: {x.get('text', '')}" for x in lines[-60:]))
    if note:
        out.append(note)
    say = "the words you'd say" if mode == "turns" else "the message you'd send"
    out.append(f"Now write only your next turn on the call: {say}, nothing else.")
    return "\n\n".join(out)


def _history_lines(calls: Calls, history: list) -> tuple[list[dict], str]:
    """The call page's turns ([{role, text}], newest last) as "who: text" lines, and the newest one apart when it's a
    note from the page in brackets ("[Task finished] ...", "[The call just connected. Speak first.]")."""
    you = calls.app.settings.get("you.name") or "You"
    items = [h for h in history if isinstance(h, dict) and str(h.get("text") or "").strip()][-60:]
    lines, note = [], ""
    for i, h in enumerate(items):
        text = str(h["text"]).strip()[:2000]
        if h.get("role") == "model":
            lines.append({"who": calls.app.name, "text": text})
        elif text.startswith("[") and i == len(items) - 1:
            note = text
        else:
            lines.append({"who": "(note)" if text.startswith("[") else you, "text": text})
    return lines, note


# ------------------------------------------------------------------------------------ turn by turn
class VoiceTurns:
    """One turn of a turn-by-turn call, answered here while the call line waits. It has to be quick, so it's never an
    agent program (agy, Codex, Claude Code: seconds just to start): your Gemini key's text model (calls.text_model),
    or the model on this computer when calls.turn_brain is "local" and Local AI models set one up. Same tools as any
    request (core/tools.py). Nothing quick, or no answer in TURN_S: the call line answers with Gemini instead."""

    def __init__(self, calls: Calls):
        self.calls = calls
        self.app = calls.app

    def brain(self):
        from kurooto import providers

        if self.calls.setting("turn_brain") == "local":
            b = providers.local(self.app)
            if b is not None:
                return b
        if not self.app.secrets.get("gemini.api_key"):
            return None
        b = providers.build(self.app, "gemini")
        if b is not None:
            b.models = {**b.models, "low": self.calls.setting("text_model") or "gemini-flash-latest"}
        return b if b is not None and b.available()[0] else None

    def answer(self, b: dict) -> tuple[int, dict]:
        from kurooto.core.tools import agent_tools, run_tool
        from kurooto.providers.base import Task
        from kurooto.providers.context import headless_context

        history = b.get("history") if isinstance(b.get("history"), list) else []
        lines, note = _history_lines(self.calls, history)
        if not lines and not note:
            return 400, {"error": "nothing to answer"}
        brain = self.brain()
        if brain is None:
            return 503, {"error": "no quick AI here for calls"}
        purpose = str(b.get("purpose") or "")[:300]
        tools = agent_tools(self.app)
        task = Task(
            prompt=turn_prompt(self.calls, lines, purpose, "turns", note),
            effort="low",
            title=f"Call turn: {purpose or 'your call'}"[:80],
            cwd=self.app.workspace,
            timeout_s=TURN_S,
            context=headless_context(self.app),
            tools=tools,
            run_tool=lambda name, args: run_tool(self.app, name, args, tools, via="call"),
        )
        box: dict = {}

        def run():
            try:
                box["result"] = brain.run(task)
            except Exception as e:
                box["error"] = f"{type(e).__name__}: {e}"[:200]

        t = threading.Thread(target=run, name="call-turn", daemon=True)
        t.start()
        t.join(TURN_S + 5)
        res = box.get("result")
        if res is None or not res.ok or not res.text.strip():
            why = "slow" if t.is_alive() else (box.get("error") or (res.verdict.value if res is not None else "error"))
            self.app.events.emit("call_turn", ok=False, brain=brain.id, why=str(why)[:80])
            return 504 if t.is_alive() else 502, {"error": "the quick AI here couldn't answer"}
        self.app.events.emit("call_turn", ok=True, brain=brain.id, seconds=round(res.seconds, 1))
        return 200, {"reply": spoken(res.text), "brain": brain.id}


# --------------------------------------------------------------------------------------- on Telegram
class TextCall:
    """Layer 3: the call as messages (Telegram, or the phone app when Telegram isn't on). One conversation per call,
    in textcalls.json: {id: {purpose, since, why, lines, state, started, last, busy, more}}."""

    def __init__(self, calls: Calls):
        self.calls = calls
        self.app = calls.app
        self.file = calls.dir / "textcalls.json"

    def _lock(self):
        return Lock(self.app.paths.state, "calls-textcall")

    def _load(self) -> dict:
        return jload(self.file, {}) or {}

    def _save(self, d: dict) -> None:
        jsave(self.file, dict(list(d.items())[-20:]))

    def get(self, cid: str) -> dict | None:
        return self._load().get(cid)

    def _you(self) -> str:
        return self.app.settings.get("you.name") or "You"

    # ---------------------------------------------------------------------------------------- start
    def start(self, b: dict) -> dict:
        """The call page couldn't go on by voice: the conversation starts here, with what was said so far."""
        purpose = str(b.get("purpose") or "")[:300]
        why = WHY.get(str(b.get("why") or ""), WHY["live"])
        ai, you = self.app.name, self._you()
        lines = [
            {"who": ai if str(x.get("who")) == ai else you, "text": str(x.get("text") or "").strip()[:4000]}
            for x in (b.get("lines") or [])[-200:]
            if isinstance(x, dict) and str(x.get("text") or "").strip()
        ]
        cid = uuid.uuid4().hex[:8]
        conv = {
            "purpose": purpose,
            "since": str(b.get("since") or ""),
            "why": str(b.get("why") or "live"),
            "lines": lines,
            "state": "open",
            "started": time.time(),
            "last": time.time(),
            "busy": False,
            "more": False,
        }
        with self._lock():
            d = self._load()
            d[cid] = conv
            self._save(d)
        head = f"Your call couldn't go on by voice ({why}), so let's carry on here" + (
            f": {purpose}." if purpose else "."
        )
        self._send(cid, head + " Reply to my messages, or just type.")
        if lines:
            note = "[The call moved to text messages because the voice failed. Pick up where you left off.]"
        elif purpose:
            note = "[The call just connected. Speak first: greet them and get straight to the reason.]"
        else:
            note = "[They called you, and the voice failed, so it's text now. Greet them briefly and ask what's up.]"
        self._ask(cid, note)
        self._idle_later(cid)
        self.app.events.emit("call_text_started", why=conv["why"], purpose=bool(purpose))
        return {"ok": True, "id": cid, "where": "telegram" if self._telegram() else "app"}

    def start_late(self, m: dict) -> None:
        """Handed over while this computer was off: start now, unless it's been too long."""
        if time.time() - _ts(m.get("at")) > LATE_S:
            self.app.notify(
                "A call couldn't connect by voice while this computer was off"
                + (f": {m['purpose']}" if m.get("purpose") else "")
                + ". Tell me here if it still matters.",
                kind="info",
            )
            return
        self.start(m)

    # -------------------------------------------------------------------------------------- turns
    def _telegram(self) -> bool:
        return "telegram" in self.app.notifier.channels  # Telegram is on and delivering

    def _send(self, cid: str, text: str, end_button: bool = True) -> None:
        self.app.notify(
            text,
            kind="info" if self._telegram() else "question",  # without Telegram: the phone app, with a Reply box
            map_kind="callchat",
            map_ref=cid,
            buttons=[[("End the call", f"callchat:{cid}:end")]] if end_button else None,
            urgent=True,  # a call isn't held for focus time
        )

    def _ask(self, cid: str, note: str = "") -> None:
        """Your AI's next message (through the queue, with its tools); said() sends it."""
        with self._lock():
            d = self._load()
            conv = d.get(cid)
            if not conv or conv["state"] != "open":
                return
            conv["busy"], conv["more"] = True, False
            self._save(d)
        prompt = turn_prompt(self.calls, conv["lines"], conv["purpose"], "text", note)
        self.app.jobs.submit(
            prompt,
            title=f"Call by text: {conv['purpose'] or 'your call'}"[:80],
            effort="low",
            quiet=True,
            then="calls.textcall_said",
            then_payload={"cid": cid},
        )

    def said(self, job, result, payload: dict) -> None:
        """The AI's answer: sent as the call's next message (and asked again if you wrote more meanwhile)."""
        cid = str(payload.get("cid") or "")
        text = spoken(result.text, 3500) if result.ok else ""
        with self._lock():
            d = self._load()
            conv = d.get(cid)
            if not conv or conv["state"] != "open":
                return
            if text:
                conv["lines"].append({"who": self.app.name, "text": text})
            more = conv.get("more")
            conv["busy"], conv["more"], conv["last"] = False, False, time.time()
            self._save(d)
        self._send(cid, text or "I couldn't answer just now (the AI didn't respond). Say it again, or end the call.")
        if more:
            self._ask(cid)
        self._idle_later(cid)

    def turn(self, cid: str, text: str) -> bool:
        """Something you wrote in the call. False if that call is over."""
        with self._lock():
            d = self._load()
            conv = d.get(cid)
            if not conv or conv["state"] != "open":
                return False
            conv["lines"].append({"who": self._you(), "text": text.strip()[:4000]})
            conv["last"] = time.time()
            busy = conv["busy"]
            if busy:
                conv["more"] = True  # the answer being written gets this one next
            self._save(d)
        if not busy:
            self._ask(cid)
        self._idle_later(cid)
        return True

    def open_one(self) -> str | None:
        """The call going on by text now, if there is one."""
        t = time.time()
        live = [
            (c["last"], cid) for cid, c in self._load().items() if c["state"] == "open" and t - c["last"] < TEXT_IDLE_S
        ]
        return max(live)[1] if live else None

    def takes(self, msg: Incoming) -> bool:
        """While a call goes on by text, what you write on Telegram (not a command or a file) is part of it."""
        if msg.via != "telegram" or msg.files or not msg.text.strip() or msg.text.strip().startswith("/"):
            return False
        cid = self.open_one()
        return bool(cid) and self.turn(cid, msg.text)

    def reply(self, msg: Incoming, ref: str) -> str | None:
        """A reply to one of the call's messages (Telegram, or the phone app's Reply box)."""
        if self.turn(ref, msg.text):
            return None if msg.via == "telegram" else "Sent."
        return "That call is over. Write again without replying to it, and I'll answer as usual."

    def button(self, cid: str, act: str) -> str:
        if act == "end":
            return "Call ended." if self.end(cid, "you ended it") else "That call is over already."
        return "OK."

    # ---------------------------------------------------------------------------------------- the end
    def _idle_later(self, cid: str) -> None:
        self.app.scheduler.at(
            time.time() + TEXT_IDLE_S, "calls.textcall_idle", {"cid": cid}, key=f"calls:textcall:{cid}", module="calls"
        )

    def idle(self, p: dict) -> None:
        cid = str(p.get("cid") or "")
        conv = self.get(cid)
        if conv and conv["state"] == "open" and time.time() - conv["last"] >= TEXT_IDLE_S - 5:
            self.end(cid, "no messages for 20 minutes")

    def end(self, cid: str, why: str) -> bool:
        """Over: its transcript is kept and goes to the feature that placed the call (a check-in's journal)."""
        with self._lock():
            d = self._load()
            conv = d.get(cid)
            if not conv or conv["state"] != "open":
                return False
            conv["state"], conv["ended"] = "ended", time.time()
            self._save(d)
        self.app.scheduler.cancel(f"calls:textcall:{cid}")
        self.calls.save_transcript(
            {"lines": conv["lines"], "purpose": conv["purpose"], "since": conv["since"], "layer": "telegram"}
        )
        if why != "you ended it":
            self.app.notify(f"Ended the call ({why}).", kind="info")
        self.app.events.emit("call_text_ended", lines=len(conv["lines"]), why=why)
        return True
