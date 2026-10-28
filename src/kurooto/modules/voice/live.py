"""Live at the desk (voice.listen.live, 0.8.17, off): a turn said to Kurooto is answered by Gemini Live, speech to
speech, the way phone calls already are, instead of text to your AI and back through the voice made here.

Only a turn Voice has already taken to the AI goes: the gate called it addressed (not chatter, not noise), Voice ID
said it's the owner's voice (it must be on: a guest's turn, or one it's unsure of, goes the usual way), and the face
check passed by actually seeing a face close to the camera and facing it for this turn (turn["faced"], set by
Voice._timed_face_check); that is everything in Voice.hear() up to the moment it would send the words, and more: a turn
let through without a face (the wake word and the request right after it, need_face off, Face presence off or paused,
need_face_fallback "voice" while the camera can't see) goes the usual way, never to Live. Its sound (the stretch, in
memory, 16 kHz) then goes to Gemini Live with your key; nothing else the microphone hears ever does. The first such
turn opens a Live session; further turns admitted while the conversation (the portal) stays open go to the same one;
the portal closing closes it.

What it reuses: the call setup (Calls.config_template: the instructions, with a few lines changed for the desk, and the
tools' declarations), the Live models in their fallback order (Calls.live_models, live_profiles), calls' run_tool for
the tools, core/tap.py for guarded ones (outside a live phone call they ask Approve / Deny first and never run by
themselves), Voice's Speaker for the sound (its outputs, barge-in's hold and release, the dashboard's waveform), the
turn's timing (fast.stamp; "live" in voice_timing) and the chat history (chat.record_turn with what Live heard and
said, so the conversation carries on if a later turn goes the usual way).

Any failure (no key, a connection or setup refused, no first sound within FIRST_S) answers that turn the usual way:
never silence. A model that failed is tried last for BAD_S. The key goes in a header (never a URL), and the websocket
library's own logging is shut off here so nothing can print it; events hold the model, stage and numbers only, never
words or sound. Nothing is written to disk."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import queue
import threading
import time
from typing import TYPE_CHECKING

from kurooto.core import egress, tap
from kurooto.core.clock import now
from kurooto.modules.voice import fast

if TYPE_CHECKING:
    from kurooto.modules.voice import Voice

LIVE_URL = (
    "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService."
    "BidiGenerateContent"
)
KEY = "gemini.api_key"
FEATURE = "Voice"
IN_RATE, OUT_RATE = 16000, 24000  # the stretch Voice heard; what Live sends back (16-bit mono both)
CHUNK = IN_RATE * 2 // 4  # the stretch goes in 250 ms messages
CONNECT_S = 5.0  # connecting and Google's answer to the setup
FIRST_S = 5.0  # the turn's first sound (a tool call starts the wait again); else it goes the usual way
TURN_S = 60.0  # a turn's answer waits at most this long for its next piece of sound
BAD_S = 600  # a model that failed is tried last for this long
FIRST_PIECE = OUT_RATE * 2 // 5  # the first 0.2 s of sound is played as soon as it's in
PIECE = OUT_RATE * 2 * 3 // 5  # then pieces of at least 0.6 s, at most MAX_PIECE (a cut piece is said again whole)
MAX_PIECE = OUT_RATE * 2 * 2
ALOUD = "(answered aloud)"  # shown when Live said something but sent no words for it
DESK = (
    "This is not a phone call: they're at their computer and talk to you aloud; you hear each turn they say to you "
    "and answer through its speakers. Keep it to one to three short spoken sentences; what needs a screen is on the "
    "computer in front of them. Every turn you hear reached you because Voice ID recognised their voice and Face "
    "presence recognised their face close to the camera, facing it; you never see the camera's pictures."
)
# (0.8.17) never at the desk: an approval is answered by their tap, not by the AI that asked for it
DESK_NEVER = frozenset({"answer_approval"})
TOOL_WAIT_S = 15.0  # (0.8.18) Live failed after starting a tool: its result is waited for this long, then said

_log = logging.getLogger("kurooto.voice.live.ws")  # the websocket library's own log: off, so headers never print
_log.propagate = False
_log.addHandler(logging.NullHandler())
_log.setLevel(logging.CRITICAL + 1)


class Failed(Exception):
    """Live didn't answer this turn (stage: connect, setup, first sound); the turn goes the usual way."""

    def __init__(self, stage: str, code: int | str = ""):
        super().__init__(stage)
        self.stage, self.code = stage, code


class Session:
    """One Live websocket, for one opening of the portal."""

    def __init__(self, ws, model: str, portal: int):
        self.ws, self.model, self.portal = ws, model, portal
        self.q: queue.Queue | None = None  # the turn being answered: what the reader hands it
        self.closed = False
        self.lock = threading.Lock()  # ended and stale, between the reader and the turn
        self.ended = True  # the last answer came to its end (turnComplete, or interrupted)
        self.stale = False  # an answer cut off before its end may still be arriving: dropped until it ends
        self.swallow = False  # after an interrupted stale answer: its own turnComplete, if it still comes
        self.playing = False
        self.turns = 0
        self.tasks: set = set()  # the reader and tool calls (kept, so they aren't collected while they run)

    def put(self, item: tuple) -> None:
        q = self.q
        if q is not None:
            q.put(item)


class Live:
    def __init__(self, v: Voice):
        self.v = v
        self.app = v.app
        self.sess: Session | None = None
        self._pcm: bytes | None = None  # the admitted turn's sound, in memory until it's sent or dropped
        self._spoke = False  # Live said this turn's answer: the portal mustn't say it again
        self._ran: list[dict] = []  # (0.8.18) the tools this turn ran: {name, done (Event), out}
        self.loop: asyncio.AbstractEventLoop | None = None
        self._loop_lock = threading.Lock()
        self.bad: dict[str, float] = {}  # model -> tried last until (monotonic)

    def on(self) -> bool:
        return bool(self.v.setting("listen.live"))

    # ------------------------------------------------------------------------------------------ Voice's hooks
    def keep(self, pcm: bytes | None, who=None) -> None:
        """hear() / barge_turn(): the sound of a turn the gate admitted, kept (memory, this turn only) when the switch
        is on and Voice ID says it's the owner's. keep(None): the turn is over, it's dropped."""
        ok = pcm and self.on() and who is not None and getattr(who, "decision", "") == "owner"
        self._pcm = pcm if ok else None
        if pcm is None:
            self._spoke = False

    def spoken(self) -> bool:
        """Voice._portal_speak: was this answer said by Live already? (Asked once.)"""
        out, self._spoke = self._spoke, False
        return out

    def close(self) -> None:
        """The portal closed (or Voice stopped): the session ends. Never waits."""
        s, self.sess = self.sess, None
        if s is None:
            return
        s.closed = True
        s.put(("closed",))
        loop = self.loop
        if loop is not None and not loop.is_closed():
            asyncio.run_coroutine_threadsafe(_close(s.ws), loop)

    def turn(self, text: str, turn: dict) -> str | None:
        """Voice.ask_brain, for an owner's turn: Live answers aloud and its words come back, or None (it couldn't:
        the usual way answers). text: the words written out here (shown and kept if Live sends none)."""
        pcm, self._pcm = self._pcm, None
        if not pcm or not turn.get("faced") or not self.on() or self.v.portal_cut() or not self.v.setting("speak.on"):
            return None  # (faced: Voice's face check saw you close and facing it for this very turn)
        key = self.app.secrets.get(KEY)
        calls = self.app.modules.get("calls")
        if not key or calls is None:
            self._event("no key" if not key else "no calls", fallback=True)
            return None
        t0 = time.monotonic()
        before = set(turn)
        self._ran = ran = []
        try:
            sess = self.sess
            if sess is None or sess.closed or sess.portal != self.v.portal.session:
                self.close()
                sess = self.sess = self._open(key, calls)
            heard, said = self._answer(sess, pcm, turn)
        except Exception as e:  # never silence: the usual way answers (and is timed as usual)
            self.close()
            for k in set(turn) - before:
                turn.pop(k, None)
            stage, code = (e.stage, e.code) if isinstance(e, Failed) else ("error", type(e).__name__)
            ms = round((time.monotonic() - t0) * 1000)
            if ran:  # (0.8.18) it acted already: the usual way would do it again ("An order is already going")
                self._event(stage, fallback=False, code=code, ms=ms, tools=len(ran))
                return "" if self.v.portal_cut() else self._acted(text, ran)
            self._event(stage, fallback=True, code=code, ms=ms)
            return "" if self.v.portal_cut() else None
        finally:
            del pcm
        turn["live"] = 1
        self._spoke = True
        sess.turns += 1
        if not self.v.portal.open or self.v.portal.session != sess.portal:  # it closed meanwhile (muted, off)
            self.close()
        self._event("answered", model=sess.model, turns=sess.turns)
        reply = said.strip()
        chat = self.app.modules.get("chat")
        if chat is not None and reply and self.app.is_on("chat"):  # the conversation carries on, as a typed one
            try:
                chat.record_turn(heard.strip() or text, reply)
            except Exception:
                pass
        return reply or ALOUD

    def _acted(self, text: str, ran: list[dict]) -> str:
        """(0.8.18) Live ran tools in this turn and then failed: what they said becomes the answer, spoken the usual
        way (not by Live), and the turn doesn't go to your AI or the add-ons' plain words, which would run them again.
        A tool still running is waited for TOOL_WAIT_S."""
        end = time.monotonic() + TOOL_WAIT_S
        parts = []
        for r in ran:
            if not r["done"].wait(max(0.0, end - time.monotonic())):
                parts.append(f"{r['name']} is still running.")
                continue
            out = r["out"]
            out = out if isinstance(out, str) else json.dumps(out, default=str)
            parts.append(out.strip()[:400] or f"{r['name']}: done.")
        reply = " ".join(parts)
        chat = self.app.modules.get("chat")
        if chat is not None and self.app.is_on("chat"):
            try:
                chat.record_turn(text, reply)
            except Exception:
                pass
        return reply

    # ---------------------------------------------------------------------------------------------- the setup
    def setup(self, calls, model: str) -> dict:
        """The call setup (Calls.config_template), as Live's setup message, for the desk."""
        cfg = calls.config_template()
        prof = {}
        try:
            prof = calls.live_profiles().get(model) or {}
        except Exception:
            pass
        gen: dict = {"responseModalities": ["AUDIO"]}
        speech = cfg.get("speechConfig")
        if isinstance(prof.get("voice"), str):  # another model: a voice it knows, or Google's default
            v = prof["voice"]
            speech = {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": v}}} if v else None
        if speech:
            gen["speechConfig"] = speech
        tools = [  # a turn waits for its tools' answers (behavior NON_BLOCKING is for calls)
            {
                "functionDeclarations": [
                    _blocking(d) for d in t.get("functionDeclarations") or [] if d.get("name") not in DESK_NEVER
                ]
            }
            for t in cfg.get("tools") or []
        ]
        si = desk(str(cfg.get("systemInstruction") or ""))
        try:  # (0.9.0, calls.context_brief) who they are and how to help them, as every AI request is told
            from kurooto.providers.context import call_context

            about = call_context(self.app)
        except Exception:
            about = ""
        if about:
            si += "\n" + about
        return {
            "model": f"models/{model}",
            "generationConfig": gen,
            "systemInstruction": {"parts": [{"text": si}]},
            "tools": tools,
            "inputAudioTranscription": {},
            "outputAudioTranscription": {},
            "contextWindowCompression": cfg.get("contextWindowCompression") or {"slidingWindow": {}},
            # Voice already cut the turn out (its own listener and gate): it says where the turn starts and ends
            "realtimeInputConfig": {"automaticActivityDetection": {"disabled": True}},
        }

    def models(self, calls) -> list[str]:
        """calls.live_models in order, those Google said don't exist left out, those that failed lately last."""
        names = list(calls.live_models())
        try:
            gone = set(calls.live.gone())
        except Exception:
            gone = set()
        names = [m for m in names if m not in gone] or names
        t = time.monotonic()
        return sorted(names, key=lambda m: self.bad.get(m, 0) > t)

    def _open(self, key: str, calls) -> Session:
        last: Failed | None = None
        for model in self.models(calls):
            try:
                ws = self._call(self._connect(key, self.setup(calls, model)), CONNECT_S * 2 + 1)
            except Failed as e:
                self.bad[model] = time.monotonic() + BAD_S
                self._event(e.stage, model=model, code=e.code)
                last = e
                continue
            self.bad.pop(model, None)
            sess = Session(ws, model, self.v.portal.session)
            self._call(_start(sess, self._read(sess)), CONNECT_S)
            return sess
        raise last or Failed("connect")

    async def _connect(self, key: str, setup: dict):
        from websockets.asyncio.client import connect
        from websockets.exceptions import ConnectionClosed

        try:
            egress.allow(LIVE_URL, FEATURE)
            ws = await connect(
                LIVE_URL,
                additional_headers={"x-goog-api-key": key},  # a header: the address never carries it
                open_timeout=CONNECT_S,
                max_size=16 * 1024 * 1024,
                user_agent_header="kurooto",
                logger=_log,
            )
        except Exception as e:
            raise Failed("connect", _code(e)) from None
        try:
            await ws.send(json.dumps({"setup": setup}))
            async with asyncio.timeout(CONNECT_S):
                while "setupComplete" not in _parse(await ws.recv()):
                    pass
        except (ConnectionClosed, TimeoutError, OSError) as e:
            await _close(ws)
            raise Failed("setup", _code(e)) from None
        return ws

    # ----------------------------------------------------------------------------------------------- a turn
    def _answer(self, sess: Session, pcm: bytes, turn: dict) -> tuple[str, str]:
        """Sends the turn, plays the answer as it comes; (what Live heard, what it said)."""
        q: queue.Queue = queue.Queue()
        sess.q = q
        with sess.lock:
            sess.ended = False
        try:
            self._call(_send_turn(sess.ws, pcm), CONNECT_S)
        except Exception:
            raise Failed("send") from None
        fast.stamp(turn, "sent")
        heard: list[str] = []
        said: list[str] = []
        first = self._first(q, heard, said, turn)
        if first is None:
            raise Failed("first sound")
        done = self._play(sess, q, bytearray(first), heard, said, turn)
        if not done:
            with sess.lock:  # cut off: the rest of that answer is dropped as it arrives
                sess.stale = not sess.ended
        fast.stamp(turn, "answer")
        sess.q = None
        return "".join(heard), "".join(said)

    def _first(self, q: queue.Queue, heard: list, said: list, turn: dict) -> bytes | None:
        """Waits for the first sound (FIRST_S, again after each tool call); None: none came."""
        end = time.monotonic() + FIRST_S
        while True:
            try:
                item = q.get(timeout=max(0.0, end - time.monotonic()))
            except queue.Empty:
                return None
            kind = item[0]
            if kind == "audio":
                fast.stamp(turn, "audio")
                return item[1]
            if kind == "tool":
                end = time.monotonic() + FIRST_S
            elif kind == "in":
                heard.append(item[1])
            elif kind == "out":
                fast.stamp(turn, "first_text")
                said.append(item[1])
            elif kind in ("done", "closed", "interrupted"):
                return None

    def _play(self, sess: Session, q: queue.Queue, buf: bytearray, heard: list, said: list, turn: dict) -> bool:
        """Through Voice's Speaker (its outputs, barge-in, the waveform), a piece at a time as the sound comes in.
        True: the answer came to its end; False: cut off (stopped, barged in on, interrupted, the session gone)."""
        sp = self.v.speaker
        barge = getattr(self.v, "barge", None)
        if not sp.lock.acquire(timeout=TURN_S):
            return False
        ended = cut = False

        def take(item: tuple) -> None:
            nonlocal ended, cut
            kind = item[0]
            if kind == "audio":
                buf.extend(item[1])
            elif kind == "in":
                heard.append(item[1])
            elif kind == "out":
                fast.stamp(turn, "first_text")
                said.append(item[1])
                if barge is not None:  # barge-in: the words being said (the echo's), as for speech made here
                    try:
                        barge.speaking([item[1]])
                    except Exception:
                        pass
            elif kind == "done":
                ended = True
            elif kind in ("closed", "interrupted"):
                ended = cut = True

        try:
            sp.busy = True
            sp._cancel.clear()
            sp._held.clear()
            sp._turn = turn
            sess.playing = True
            self.v.portal.state("speaking")
            want = FIRST_PIECE
            while True:
                while not ended and len(buf) < want:  # enough for a piece, or the end
                    try:
                        take(q.get(timeout=TURN_S))
                    except queue.Empty:
                        ended = cut = True
                while not ended:  # and whatever else is in already
                    try:
                        take(q.get_nowait())
                    except queue.Empty:
                        break
                if cut:
                    return False
                if buf:
                    piece = bytes(buf[:MAX_PIECE])
                    del buf[:MAX_PIECE]
                    if not sp.say_piece(piece, OUT_RATE):
                        return False
                want = PIECE
                if ended and not buf:
                    return True
        finally:
            sess.playing = False
            sp._turn = None
            sp.busy = False
            sp.until = time.monotonic() + 0.4
            sp.lock.release()

    # ------------------------------------------------------------------------------------------ the session
    async def _read(self, sess: Session) -> None:
        """Everything Live sends, handed to the turn being answered; tool calls run here (never on the turn's
        thread, which may be playing)."""
        try:
            async for raw in sess.ws:
                m = _parse(raw)
                if m.get("toolCall") and not sess.stale:
                    sess.swallow = False
                    sess.put(("tool",))
                    await _start(sess, self._tools(sess, m["toolCall"]))
                sc = m.get("serverContent")
                if not isinstance(sc, dict):
                    continue
                end = bool(sc.get("turnComplete") or sc.get("interrupted"))
                with sess.lock:
                    if end:
                        sess.ended = True
                    if sess.stale:  # the rest of an answer that was cut off: dropped
                        if end:
                            sess.stale = False
                            sess.swallow = not sc.get("turnComplete")  # interrupted: its turnComplete may follow
                        continue
                    if sess.swallow and sc.get("turnComplete") and not sc.get("modelTurn"):
                        sess.swallow = False
                        continue
                    if sc.get("modelTurn") or sc.get("outputTranscription"):
                        sess.swallow = False
                for p in (sc.get("modelTurn") or {}).get("parts") or []:
                    data = (p.get("inlineData") or {}).get("data") if isinstance(p, dict) else None
                    if data:
                        sess.put(("audio", base64.b64decode(data)))
                for k, tag in (("inputTranscription", "in"), ("outputTranscription", "out")):
                    t = (sc.get(k) or {}).get("text")
                    if t:
                        sess.put((tag, str(t)))
                if sc.get("interrupted"):  # Live stopped its answer: so does the sound
                    if sess.playing:
                        self.v.speaker.stop()
                    sess.put(("interrupted",))
                if sc.get("turnComplete"):
                    sess.put(("done",))
        except Exception:
            pass
        finally:
            sess.closed = True
            sess.put(("closed",))

    async def _tools(self, sess: Session, call: dict) -> None:
        out = []
        loop = asyncio.get_running_loop()
        for fc in call.get("functionCalls") or []:
            name, args = str(fc.get("name") or ""), fc.get("args")
            res = await loop.run_in_executor(None, self.run_tool, name, args if isinstance(args, dict) else {})
            out.append({"id": fc.get("id"), "name": name, "response": {"result": res}})
        if out and not sess.closed:
            try:
                await sess.ws.send(json.dumps({"toolResponse": {"functionResponses": out}}))
            except Exception:
                pass

    def run_tool(self, name: str, args: dict):
        """A tool Live asked for: through calls' run_tool, except a guarded one (core/tap.py): at the desk you're not
        on a live phone call, so it asks Approve / Deny first and runs only on Approve."""
        calls = self.app.modules.get("calls")
        if calls is None:
            return f"There's no {name} tool."
        if name in DESK_NEVER:  # (0.8.17) it could approve its own guarded action: the tap decides, not the AI
            return "Approvals are answered by their tap (the phone or the dashboard), never here. Tell them it waits."
        rec = {"name": name, "done": threading.Event(), "out": None}
        self._ran.append(rec)  # (0.8.18) this turn acted: a fallback mustn't do it again
        try:
            tool = next((t for t in calls.tools() if t.name == name), None)
            action = tap.action_of(tool, args) if tool is not None else ""
            out = tap.ask_first(self.app, tool, action, args, via="voice") if action else calls.run_tool(name, args)
        except Exception as e:
            out = f"That failed: {type(e).__name__}"
        if isinstance(out, dict) and name == "pending_items":  # (0.9.0) the desk's setup already says who they are
            out = {k: v for k, v in out.items() if k != "about_them"}
        try:
            json.dumps(out)
        except (TypeError, ValueError):
            out = str(out)
        rec["out"] = out
        rec["done"].set()
        return out

    # ------------------------------------------------------------------------------------------- plumbing
    def _call(self, coro, timeout: float):
        """Runs a coroutine on Live's own loop (a thread of its own) and waits for it."""
        loop = self._loop()
        fut = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            return fut.result(timeout)
        except Failed:
            raise
        except Exception as e:
            fut.cancel()
            raise Failed("connect", _code(e)) from None

    def _loop(self) -> asyncio.AbstractEventLoop:
        with self._loop_lock:
            if self.loop is None or self.loop.is_closed():
                loop = asyncio.new_event_loop()
                threading.Thread(target=loop.run_forever, name="voice-live", daemon=True).start()
                self.loop = loop
            return self.loop

    def _event(self, stage: str, **fields) -> None:
        """voice_live: the stage, the model, numbers; never words, sound or the key."""
        self.app.events.emit("voice_live", stage=stage, **{k: v for k, v in fields.items() if v not in (None, "")})


def desk(si: str) -> str:
    """The call's instructions, for the desk: the time filled in, "on a call" lines changed or left out."""
    si = si.replace("%%NOW%%", now().strftime("%A %d %B %Y, %H:%M"))
    si = si.replace("on a live voice call.", "talking with them aloud at their computer.")
    si = si.replace("Talk like a friend on a call", "Talk like a friend sitting with them")
    lines = [ln for ln in si.split("\n") if "every call" not in ln]  # (pending_items' "at the start of every call")
    return "\n".join([*lines, DESK])


def _blocking(d: dict) -> dict:
    return {k: x for k, x in d.items() if k != "behavior"}


async def _start(sess: Session, coro) -> None:
    task = asyncio.create_task(coro)
    sess.tasks.add(task)
    task.add_done_callback(sess.tasks.discard)


async def _send_turn(ws, pcm: bytes) -> None:
    await ws.send(json.dumps({"realtimeInput": {"activityStart": {}}}))
    for i in range(0, len(pcm), CHUNK):
        data = base64.b64encode(pcm[i : i + CHUNK]).decode("ascii")
        await ws.send(json.dumps({"realtimeInput": {"audio": {"data": data, "mimeType": f"audio/pcm;rate={IN_RATE}"}}}))
    await ws.send(json.dumps({"realtimeInput": {"activityEnd": {}}}))


async def _close(ws) -> None:
    try:
        await ws.close()
    except Exception:
        pass


def _parse(raw) -> dict:
    try:
        m = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
    except (ValueError, UnicodeDecodeError):
        return {}
    return m if isinstance(m, dict) else {}


def _code(e: BaseException) -> int | str:
    """A failure as a number or a short word (never its message: it may quote what was sent)."""
    rcvd = getattr(e, "rcvd", None)
    if rcvd is not None and getattr(rcvd, "code", None):
        return int(rcvd.code)
    resp = getattr(e, "response", None)
    if resp is not None and getattr(resp, "status_code", None):
        return int(resp.status_code)
    return type(e).__name__
