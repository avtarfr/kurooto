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
words or sound. Nothing is written to disk.

Everyone (0.9.2, voice.listen.live_everyone, off): every turn the gate called addressed goes to Live, whoever said it
and whether or not a face was seen. A turn Voice ID calls the owner's (face_assist and carry_talk count) gets the
owner's session above. Any other (unsure, a guest, no verdict with Voice ID off) gets a separate guest session
(guest_setup): no tools, nothing of the owner's (no notes, memory, history, lessons, persona, his name), only the
assistant's name and the guest path's rules (core/guest.py and providers/context.py guest_context; the
voice.speaker_id.tell_guests line said once). It follows the text guest path's rules first: owner_only_at_all, a
request that acts or reads his things (guest.kind) and the hourly cap (guest_per_hour) go the usual way, which
refuses them as before. Its turns are never put in his chat history, Brain or the talk's lines; tools asked for there
are refused without running (so no guarded action or approval can start from it). An owner's turn closes the guest
session first: the two never share a session or context. Failures fall back the usual way, as above.

Faster (0.9.2):
- **Prewarm** (voice.listen.live_prewarm; voice.listen.fast_live opens it too): the owner's session is opened ahead
  (connect and setup, no sound) when Face presence recognises his face looking at the camera, or his wake word in his
  voice; never on anyone else's face and never the guest session. At most PREWARM_MAX opens in PREWARM_WINDOW_S; one
  unused for PREWARM_IDLE_S is closed; one idle for PING_IDLE_S is pinged before a turn's activityStart (no pong:
  opened afresh). No sound goes until a turn the gate admitted.
- **Breaker** (voice.live.breaker.on): BREAKER_FAILS failed opens (connect or setup refused, never a slow first sound)
  within BREAKER_WINDOW_S: "Live resting": turns go the usual way at once (only the 5 s wait is skipped), and every
  PROBE_S a connection with an empty setup (a model name, nothing of anyone's) is tried; one that works ends it.
- **Heard-you cue** (voice.live.ack): no sound from Live ACK_AFTER_S after the turn was sent, or a tool call: Voice's
  acknowledgement sound plays (its outputs, the barge-in echo reference), cut off by Live's first sound; a "voice_ack"
  message for the page either way, and only that while the room wants quiet (Voice.cue_quiet).
- **Resume** (voice.live.resume): the owner's session asks Google for a resumption handle (memory only, RESUME_S); the
  next opening of his session within that time continues the conversation, and a goAway reopens with it. Never for
  the guest session.
- **Spoken length** (voice.live.spoken_max_s): past that many seconds of Live's sound, it stops at the next sentence end
  (from Live's own transcript); the rest is shown, not said."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import queue
import re
import threading
import time
from collections import deque
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
# (on this computer's speakers; an add-on's output gets OUT_* below)
MAX_PIECE = OUT_RATE * 2 * 2
# (0.9.2) played on an add-on's output (a phone fetching each piece as a sound file): bigger pieces, fewer gaps
OUT_FIRST_PIECE = OUT_RATE * 2 // 2  # the first 0.5 s
OUT_PIECE = OUT_RATE * 2  # then about a second each
OUT_MAX_PIECE = OUT_RATE * 2 * 3
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
# (0.9.2, voice.listen.live_everyone) the owner's turns may come without a face seen: the setup says only the voice
DESK_ANY = DESK.replace(
    " and Face presence recognised their face close to the camera, facing it", " (or the conversation they opened)"
)
GUEST_DESK = (
    "This is not a phone call: someone at the owner's computer talks to you aloud and you answer through its "
    "speakers. Keep it to one to three short spoken sentences. You have no tools and can't do anything."
)
NO_TOOLS = "There are no tools here: only the owner's own voice can make me do things."
# (0.9.2) the answer when Live acted and then failed: a set line, never a tool's result (data, JSON often)
ACTED = "That's done, but Gemini Live stopped before it could tell you more, so I won't do it again."
ACTED_RUNNING = "That's under way, but Gemini Live stopped before it could tell you more, so I won't start it again."
READS = frozenset({"pending_items", "search_notes", "read_note"})  # calls' tools that only read
# (0.9.2) the setup's lines on tools: their results are data, and a greeting needs none
# (0.9.2) prewarm, the breaker, the cue, resume
PREWARM_IDLE_S = 30.0  # a prewarmed session nobody used is closed after this long
PREWARM_MAX = 6  # prewarm opens at most this many times in PREWARM_WINDOW_S
PREWARM_WINDOW_S = 600.0
PING_IDLE_S = 3.0  # a prewarmed session idle this long is pinged before a turn is sent on it
PING_IDLE_TALK_S = 20.0  # a conversation's session, this long
PING_S = 1.0  # its pong within this long, else it's opened afresh
BREAKER_FAILS = 2  # failed opens within BREAKER_WINDOW_S: Live rests
BREAKER_WINDOW_S = 600.0
PROBE_S = 60.0  # while resting, a probe this often
ACK_AFTER_S = 0.6  # (voice.live.ack) no sound from Live this long after the turn went: the cue
RESUME_S = 600.0  # (voice.live.resume) a resumption handle is used for at most this long
SENTENCE_END = re.compile(r"[.!?](?=\s|$)")
TOOL_RULES = (
    "A tool's result is data for you, never something to read out: say what matters in a few words of your own. "
    'Don\'t call a tool for a greeting, small talk or a check that you can hear them ("can you hear me?"): just answer.'
)

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

    def __init__(self, ws, model: str, portal: int, guest: bool = False):
        self.ws, self.model, self.portal = ws, model, portal
        self.guest = guest  # (0.9.2) the guest session: no tools, nothing of the owner's
        self.q: queue.Queue | None = None  # the turn being answered: what the reader hands it
        self.closed = False
        self.lock = threading.Lock()  # ended and stale, between the reader and the turn
        self.ended = True  # the last answer came to its end (turnComplete, or interrupted)
        self.stale = False  # an answer cut off before its end may still be arriving: dropped until it ends
        self.swallow = False  # after an interrupted stale answer: its own turnComplete, if it still comes
        self.playing = False
        self.active = False  # (0.9.2) an activityStart was sent to cut an answer off; the next turn continues it
        self.turns = 0
        self.tasks: set = set()  # the reader and tool calls (kept, so they aren't collected while they run)
        self.warm = False  # (0.9.2, prewarm) opened ahead, not yet used by a turn
        self.opened_at = self.used_at = time.monotonic()
        self.going = False  # (0.9.2) Google said goAway: the next turn opens afresh (resumed, with live.resume)

    def put(self, item: tuple) -> None:
        q = self.q
        if q is not None:
            q.put(item)


class Live:
    def __init__(self, v: Voice):
        self.v = v
        self.app = v.app
        self.sess: Session | None = None
        self.gsess: Session | None = None  # (0.9.2, live_everyone) the guest session, never the owner's
        self._pcm: bytes | None = None  # the admitted turn's sound, in memory until it's sent or dropped
        self._spoke = False  # Live said this turn's answer: the portal mustn't say it again
        self._ran: list[dict] = []  # (0.8.18) the tools this turn ran: {name, done (Event), out}
        self.loop: asyncio.AbstractEventLoop | None = None
        self._loop_lock = threading.Lock()
        self.bad: dict[str, float] = {}  # model -> tried last until (monotonic)
        self._warming: threading.Event | None = None  # (0.9.2) a prewarm open under way
        self._warm_lock = threading.Lock()
        self.warms: deque = deque(maxlen=PREWARM_MAX)  # when prewarm opened (monotonic)
        self.warm_count = 0  # prewarmed sessions a turn used, since start
        self.fails: deque = deque(maxlen=BREAKER_FAILS)  # (breaker) failed opens (monotonic)
        self.resting_since: float | None = None
        self._probe_at = 0.0
        self._probing = False
        self._handle: tuple[str, float] | None = None  # (resume) Google's handle for his session, and when

    def on(self) -> bool:
        return bool(self.v.setting("listen.live"))

    def everyone(self) -> bool:
        """(0.9.2, voice.listen.live_everyone) every addressed turn goes to Live, a guest's to its own session."""
        return self.on() and bool(self.v.setting("listen.live_everyone"))

    # ------------------------------------------------------------------------------------ 0.9.2: faster
    def status(self) -> dict:
        """For GET /api/voice: words and numbers only."""
        s = self.sess
        return {
            "on": self.on(),
            "prewarm": bool(self.v.setting("listen.live_prewarm")),
            "fast": bool(self.v.setting("listen.fast_live")),
            "warm": bool(s is not None and not s.closed and s.warm),
            "warm_used": self.warm_count,
            "breaker": bool(self.v.setting("live.breaker.on")),
            "resting": self.resting(),
            "resume": bool(self.v.setting("live.resume")) and self._resume_handle() is not None,
        }

    def line(self) -> str:
        if self.resting():
            return "Live resting: two connections failed, so your turns go the usual way; trying again every minute."
        return ""

    def resting(self) -> bool:
        return self.resting_since is not None and bool(self.v.setting("live.breaker.on"))

    def _open_failed(self) -> None:
        """(breaker) A hard open failure (every model refused the connection or the setup)."""
        now = time.monotonic()
        self.fails.append(now)
        if (self.v.setting("live.breaker.on") and self.resting_since is None and len(self.fails) >= BREAKER_FAILS
                and now - self.fails[0] <= BREAKER_WINDOW_S):  # fmt: skip
            self.resting_since, self._probe_at = now, now + PROBE_S
            self._event("resting")

    def tick(self) -> None:
        """Every second from Voice.background: an unused prewarmed session past PREWARM_IDLE_S closes; while resting, a
        probe when it's due."""
        s = self.sess
        if s is not None and s.warm and not s.closed and time.monotonic() - s.opened_at > PREWARM_IDLE_S:
            self._event("prewarm idle")
            self.close()
        if self.resting_since is not None and not self.v.setting("live.breaker.on"):
            self.resting_since = None  # switched off: Live is tried as before
        if self.resting() and not self._probing and time.monotonic() >= self._probe_at:
            self._probing = True
            threading.Thread(target=self._probe, name="voice-live-probe", daemon=True).start()

    def _probe(self) -> None:
        """(breaker) A connection with an empty setup (the model's name only: nothing of anyone's), closed at once."""
        try:
            key = self.app.secrets.get(KEY)
            calls = self.app.modules.get("calls")
            if not key or calls is None:
                return
            for model in self.models(calls):
                try:
                    ws = self._call(self._connect(key, {"model": f"models/{model}"}), CONNECT_S * 2 + 1)
                except Failed:
                    continue
                self._call(_close(ws), CONNECT_S)
                self.resting_since = None
                self.fails.clear()
                self._event("rested", model=model)
                return
            self._event("probe failed")
        except Exception:
            pass
        finally:
            self._probe_at = time.monotonic() + PROBE_S
            self._probing = False

    def prewarm(self, why: str, switch: str = "listen.live_prewarm") -> bool:
        """(0.9.2) Open the owner's session ahead, on a thread (why: "face", "wake", "fast"): connect and setup only,
        no sound. Only Voice calls it, and only for his recognised face or his verified wake word (fast_live: his face
        looking and talking). False when it doesn't: the switch off, Live off, resting, no key, a session open or
        opening already, the rate cap."""
        if not self.on() or not self.v.setting(switch) or not self.v.setting("speak.on") or self.v.portal_cut():
            return False
        if self.resting() or not self.app.secrets.get(KEY) or self.app.modules.get("calls") is None:
            return False
        now = time.monotonic()
        with self._warm_lock:
            s = self.sess
            if self._warming is not None or (s is not None and not s.closed and not s.going):
                return False
            if len(self.warms) >= PREWARM_MAX and now - self.warms[0] < PREWARM_WINDOW_S:
                return False
            self.warms.append(now)
            self._warming = threading.Event()
        threading.Thread(target=self._prewarm, args=(why,), name="voice-live-warm", daemon=True).start()
        return True

    def _prewarm(self, why: str) -> None:
        done = self._warming
        t0 = time.monotonic()
        try:
            sess = self._open(self.app.secrets.get(KEY), self.app.modules.get("calls"))
            sess.warm = True
            with self._warm_lock:
                old = self.sess
                if old is None or old.closed or old.going:
                    self.sess = sess
                    sess = None
            if sess is not None:
                self._end(sess)
            self._event("prewarm", why=why, ms=round((time.monotonic() - t0) * 1000))
        except Exception as e:
            self._event("prewarm failed", why=why, code=e.code if isinstance(e, Failed) else type(e).__name__)
        finally:
            with self._warm_lock:
                self._warming = None
            if done is not None:
                done.set()

    def _ready(self, sess: Session | None) -> bool:
        """(0.9.2) Is this session good to send a turn on? Idle a while: a ping first (no pong: no)."""
        if sess is None or sess.closed or sess.going:
            return False
        if time.monotonic() - sess.used_at < (PING_IDLE_S if sess.warm else PING_IDLE_TALK_S):
            return True
        try:
            self._call(_ping(sess.ws), PING_S + 0.5)
            return True
        except Exception:
            self._event("ping failed")
            return False

    def _session(self, key: str, calls, turn: dict) -> Session:
        """The owner's session for this turn: a prewarm under way waited for, a prewarmed one adopted, the one open
        for this conversation reused, or a new one."""
        w = self._warming
        if w is not None:
            w.wait(CONNECT_S * 2 + 1)
        sess = self.sess
        if sess is not None and sess.warm and self._ready(sess):
            sess.warm, sess.portal = False, self.v.portal.session
            self.warm_count += 1
            turn["live_warm"] = 1
        elif sess is None or sess.portal != self.v.portal.session or not self._ready(sess):
            self.close()
            sess = self.sess = self._open(key, calls)
        fast.stamp(turn, "live_open")
        return sess

    def _resume_handle(self) -> str | None:
        h = self._handle
        if h is None or time.monotonic() - h[1] > RESUME_S:
            return None
        return h[0]

    # ------------------------------------------------------------------------------------------ Voice's hooks
    def keep(self, pcm: bytes | None, who=None) -> None:
        """hear() / barge_turn(): the sound of a turn the gate admitted, kept (memory, this turn only) when the switch
        is on and Voice ID says it's the owner's (anyone's with live_everyone). keep(None): the turn is over, it's
        dropped."""
        owner = who is not None and getattr(who, "decision", "") == "owner"
        ok = pcm and self.on() and (owner or self.everyone())
        self._pcm = pcm if ok else None
        if pcm is None:
            self._spoke = False

    def spoken(self) -> bool:
        """Voice._portal_speak: was this answer said by Live already? (Asked once.)"""
        out, self._spoke = self._spoke, False
        return out

    def close(self) -> None:
        """The portal closed (or Voice stopped): the sessions end. Never waits."""
        s, self.sess = self.sess, None
        self.close_guest()
        self._end(s)

    def close_guest(self) -> None:
        """(0.9.2) The guest session ends (the portal closed, or the owner's turn came). Never waits."""
        g, self.gsess = self.gsess, None
        self._end(g)

    def _end(self, s: Session | None) -> None:
        if s is None:
            return
        s.closed = True
        s.put(("closed",))
        loop = self.loop
        if loop is not None and not loop.is_closed():
            asyncio.run_coroutine_threadsafe(_close(s.ws), loop)

    def turn(self, text: str, turn: dict, guest: str = "") -> str | None:
        """Voice.ask_brain, for an owner's turn: Live answers aloud and its words come back, or None (it couldn't:
        the usual way answers). text: the words written out here (shown and kept if Live sends none). guest (0.9.2,
        live_everyone): not the owner's turn ("unsure", "guest", "none"): the guest session answers it."""
        pcm, self._pcm = self._pcm, None
        if not pcm or not self.on() or self.v.portal_cut() or not self.v.setting("speak.on"):
            return None
        if guest:
            return self._guest_turn(text, turn, pcm, guest) if self.everyone() else None
        if not turn.get("faced") and not self.everyone():
            return None  # (faced: Voice's face check saw you close and facing it for this very turn)
        self.close_guest()  # (0.9.2) your turn: never the guest session, nor anything it heard
        key = self.app.secrets.get(KEY)
        calls = self.app.modules.get("calls")
        if not key or calls is None:
            self._event("no key" if not key else "no calls", fallback=True)
            return None
        if self.resting():  # (0.9.2, breaker) no 5 s wait on a connection that keeps failing
            self._event("resting", fallback=True)
            return None
        t0 = time.monotonic()
        before = set(turn)
        self._ran = ran = []
        try:
            sess = self._session(key, calls, turn)
            heard, said = self._answer(sess, pcm, turn)
        except Exception as e:  # never silence: the usual way answers (and is timed as usual)
            self.close()
            for k in set(turn) - before:
                turn.pop(k, None)
            stage, code = (e.stage, e.code) if isinstance(e, Failed) else ("error", type(e).__name__)
            ms = round((time.monotonic() - t0) * 1000)
            acted = [r for r in ran if not self._reads(calls, r["name"])]  # (0.9.2) a read is safe to do again
            if acted:  # (0.8.18) it acted already: the usual way would do it again ("An order is already going")
                self._event(stage, fallback=False, code=code, ms=ms, tools=len(ran))
                return "" if self.v.portal_cut() else self._acted(text, acted)
            self._event(stage, fallback=True, code=code, ms=ms, **({"tools": len(ran)} if ran else {}))
            return "" if self.v.portal_cut() else None
        finally:
            del pcm
        turn["live"] = 1
        self._spoke = True
        sess.turns += 1
        if not self.v.portal.open or self.v.portal.session != sess.portal:  # it closed meanwhile (muted, off)
            self.close()
        self._event("answered", model=sess.model, turns=sess.turns)
        reply = spoken(said)
        chat = self.app.modules.get("chat")
        if chat is not None and reply and self.app.is_on("chat"):  # the conversation carries on, as a typed one
            try:
                chat.record_turn(heard.strip() or text, reply)
            except Exception:
                pass
        self.app.after_turn(heard.strip() or text, via="voice_live")  # (0.9.0) noticed as a message from you
        return reply or ALOUD

    @staticmethod
    def _reads(calls, name: str) -> bool:
        """(0.9.2) A tool that only reads (READS, or Tool.writes False): Live failing after it, the usual way answers
        the turn and reading again changes nothing."""
        if name in READS:
            return True
        try:
            tool = next((t for t in calls.tools() if t.name == name), None)
        except Exception:
            return False
        return tool is not None and getattr(tool, "writes", None) is False

    def _acted(self, text: str, ran: list[dict]) -> str:
        """(0.8.18) Live ran tools that act in this turn and then failed: a set line says so, spoken the usual way
        (not by Live), and the turn doesn't go to your AI or the add-ons' plain words, which would run them again. A
        tool still running is waited for TOOL_WAIT_S. (0.9.2) A tool's result is never the answer: it's data (JSON
        often), and it was said aloud and shown as the answer once."""
        end = time.monotonic() + TOOL_WAIT_S
        running = sum(1 for r in ran if not r["done"].wait(max(0.0, end - time.monotonic())))
        reply = ACTED_RUNNING if running else ACTED
        chat = self.app.modules.get("chat")
        if chat is not None and self.app.is_on("chat"):
            try:
                chat.record_turn(text, reply)
            except Exception:
                pass
        self.app.after_turn(text, via="voice_live")  # (0.9.0) noticed as a message from you
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
        si = desk(str(cfg.get("systemInstruction") or ""), DESK_ANY if self.everyone() else DESK) + "\n" + TOOL_RULES
        try:  # (0.9.0, calls.context_brief) who they are and how to help them, as every AI request is told
            from kurooto.providers.context import call_context

            about = call_context(self.app)
        except Exception:
            about = ""
        if about:
            si += "\n" + about
        dc = getattr(self.v, "desk_calling", None)
        if dc:  # (0.9.1, calls.desk_first) a call taken at the desk: Live goes through its steps
            si += f"\nThis talk is a call taken at the desk: {dc['reason']}. Go through it as the call would:\n"
            si += dc["script"]
        extra: dict = {}
        if self.v.setting("live.resume"):  # (0.9.2) his session only: a handle asked for, and used when there is one
            h = self._resume_handle()
            extra["sessionResumption"] = {"handle": h} if h else {}
        return {
            **extra,
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

    def guest_setup(self, calls, model: str, kind: str) -> dict:
        """(0.9.2, live_everyone) The guest session's setup, built from scratch: the assistant's name and the guest
        path's rules (providers/context.py guest_context), the voice, and the tell_guests line once. No tools, and
        nothing of the owner's: never Calls.config_template (his name, lessons, persona) or call_context."""
        from kurooto.core import guest
        from kurooto.modules.voice.portal import GUEST_NOTICE, UNSURE_NOTICE
        from kurooto.providers.context import guest_context

        gen: dict = {"responseModalities": ["AUDIO"]}
        voice = str(calls.setting("voice") or "")
        try:
            prof = calls.live_profiles().get(model) or {}
        except Exception:
            prof = {}
        if isinstance(prof.get("voice"), str):
            voice = prof["voice"]
        if voice:
            gen["speechConfig"] = {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}
        si = guest_context(self.app) + "\n" + GUEST_DESK
        told = getattr(self.v.portal, "_told", set())
        if kind in ("guest", "unsure") and guest.setting(self.app, "tell_guests", True) and kind not in told:
            line = UNSURE_NOTICE if kind == "unsure" else GUEST_NOTICE
            si += f'\nStart your first answer with this sentence, word for word: "{line}"'
        return {
            "model": f"models/{model}",
            "generationConfig": gen,
            "systemInstruction": {"parts": [{"text": si}]},
            "inputAudioTranscription": {},
            "outputAudioTranscription": {},
            "contextWindowCompression": {"slidingWindow": {}},
            "realtimeInputConfig": {"automaticActivityDetection": {"disabled": True}},
        }

    def _guest_turn(self, text: str, turn: dict, pcm: bytes, kind: str) -> str | None:
        """(0.9.2, live_everyone) A turn that isn't the owner's, in the guest session; None: the usual way (the text
        guest path) answers. Its rules first, as core/guest.py's: owner_only_at_all, a request that acts or reads
        his things, and the hourly cap go the usual way, which refuses them with the same lines."""
        from kurooto.core import guest

        if guest.setting(self.app, "mode", "owner_only_acts") == "owner_only_at_all":
            return None
        try:
            asks = guest.kind(self.app, text)
        except Exception:
            asks = "action"  # can't tell: the usual way decides
        if asks:
            self._event("refused", who="guest", fallback=True)
            return None
        key = self.app.secrets.get(KEY)
        calls = self.app.modules.get("calls")
        if not key or calls is None:
            self._event("no key" if not key else "no calls", fallback=True, who="guest")
            return None
        if self.resting():  # (0.9.2, breaker)
            self._event("resting", fallback=True, who="guest")
            return None
        if not guest.allowed_now(self.app):
            self._event("rate", fallback=True, who="guest")
            return None
        t0 = time.monotonic()
        before = set(turn)
        self._ran = []
        try:
            g = self.gsess
            if g is None or g.closed or g.portal != self.v.portal.session:
                self.close_guest()
                g = self.gsess = self._open(key, calls, guest=kind)
            fast.stamp(turn, "live_open")
            _heard, said = self._answer(g, pcm, turn)
        except Exception as e:
            self.close_guest()
            for k in set(turn) - before:
                turn.pop(k, None)
            guest.refund(self.app)  # the usual way counts it instead
            stage, code = (e.stage, e.code) if isinstance(e, Failed) else ("error", type(e).__name__)
            self._event(stage, fallback=True, code=code, ms=round((time.monotonic() - t0) * 1000), who="guest")
            return "" if self.v.portal_cut() else None
        finally:
            del pcm
        turn["live"] = 1
        self._spoke = True
        g.turns += 1
        if not self.v.portal.open or self.v.portal.session != g.portal:
            self.close_guest()
        self._event("answered", model=g.model, turns=g.turns, who="guest")
        return spoken(said) or ALOUD

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

    def _open(self, key: str, calls, guest: str = "") -> Session:
        last: Failed | None = None
        for model in self.models(calls):
            setup = self.guest_setup(calls, model, guest) if guest else self.setup(calls, model)
            ws, err = self._try(key, setup)
            if err is not None and (setup.get("sessionResumption") or {}).get("handle"):
                self._handle = None  # (0.9.2, resume) a stale handle: once more without it
                ws, err = self._try(key, self.setup(calls, model))
            if err is not None:
                self.bad[model] = time.monotonic() + BAD_S
                self._event(err.stage, model=model, code=err.code, who="guest" if guest else None)
                last = err
                continue
            self.bad.pop(model, None)
            sess = Session(ws, model, self.v.portal.session, guest=bool(guest))
            self._call(_start(sess, self._read(sess)), CONNECT_S)
            self.fails.clear()
            return sess
        self._open_failed()  # (0.9.2, breaker) a hard failure: every model refused
        raise last or Failed("connect")

    def _try(self, key: str, setup: dict):
        try:
            return self._call(self._connect(key, setup), CONNECT_S * 2 + 1), None
        except Failed as e:
            return None, e

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
            self._call(_send_turn(sess.ws, pcm, start=not sess.active), CONNECT_S)
        except Exception:
            raise Failed("send") from None
        sess.active = False
        fast.stamp(turn, "sent")
        heard: list[str] = []
        said: list[str] = []
        cue = Cue(self.v, turn) if self.v.setting("live.ack") else None  # (0.9.2, voice.live.ack)
        try:
            first = self._first(q, heard, said, turn, cue)
        finally:
            if cue is not None:
                cue.heard()
        if first is None:
            raise Failed("first sound")
        done = self._play(sess, q, bytearray(first), heard, said, turn)
        if done == CAPPED:  # (0.9.2, spoken_max_s) the rest isn't said: its words are still taken, to be shown
            done = self._rest(q, heard, said)
        if not done:
            with sess.lock:  # cut off: the rest of that answer is dropped as it arrives
                sess.stale = not sess.ended
                cut = sess.stale and not sess.closed
            if cut:  # (0.9.2) and Google stops making it: a new activity interrupts the answer there too
                try:
                    self._call(_activity(sess.ws), CONNECT_S)
                    sess.active = True  # the next turn's sound belongs to it: no second activityStart
                except Exception:
                    pass
        fast.stamp(turn, "answer")
        sess.q = None
        sess.used_at = time.monotonic()
        if not sess.guest:  # (0.9.0, mind.promises.answers) a promise said at the desk is written down; never a guest's
            try:
                from kurooto.mind import promises

                promises.said(self.v.app, "".join(said), "desk")
            except Exception:
                pass
        return "".join(heard), "".join(said)

    def _rest(self, q: queue.Queue, heard: list, said: list) -> bool:
        """(0.9.2, spoken_max_s) The answer past its cap: its words kept (shown), its sound dropped; True at its end."""
        end = time.monotonic() + TURN_S
        while time.monotonic() < end:
            try:
                item = q.get(timeout=max(0.0, end - time.monotonic()))
            except queue.Empty:
                return False
            if item[0] == "in":
                heard.append(item[1])
            elif item[0] == "out":
                said.append(item[1])
            elif item[0] == "done":
                return True
            elif item[0] in ("closed", "interrupted"):
                return False
        return False

    def _first(self, q: queue.Queue, heard: list, said: list, turn: dict, cue: Cue | None = None) -> bytes | None:
        """Waits for the first sound (FIRST_S, again after each tool call); None: none came. (0.9.2) cue: the heard-you
        sound, after ACK_AFTER_S and on a tool call."""
        end = time.monotonic() + FIRST_S
        if cue is not None:
            cue.start()
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
                if cue is not None:
                    cue.play(again=True)
            elif kind == "in":
                heard.append(item[1])
            elif kind == "out":
                fast.stamp(turn, "first_text")
                said.append(item[1])
            elif kind in ("done", "closed", "interrupted"):
                return None

    def _play(self, sess: Session, q: queue.Queue, buf: bytearray, heard: list, said: list, turn: dict):
        """Through Voice's Speaker (its outputs, barge-in, the waveform), a piece at a time as the sound comes in.
        True: the answer came to its end; False: cut off (stopped, barged in on, interrupted, the session gone);
        CAPPED (0.9.2, voice.live.spoken_max_s): stopped at a sentence end past the cap, the rest still coming."""
        sp = self.v.speaker
        barge = getattr(self.v, "barge", None)
        if not sp.lock.acquire(timeout=TURN_S):
            return False
        ended = cut = False
        try:
            cap = float(self.v.setting("live.spoken_max_s") or 0)
        except (TypeError, ValueError):
            cap = 0.0
        got = len(buf)  # bytes of sound received
        played = 0  # bytes played
        stop_at: int | None = None  # (cap) play up to this many bytes, then stop

        def take(item: tuple) -> None:
            nonlocal ended, cut
            nonlocal got
            kind = item[0]
            if kind == "audio":
                buf.extend(item[1])
                got += len(item[1])
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

        out = bool(getattr(sp, "_outputs", None))  # (0.9.2) an add-on's output takes it: about a second a piece
        first, each, most = (OUT_FIRST_PIECE, OUT_PIECE, OUT_MAX_PIECE) if out else (FIRST_PIECE, PIECE, MAX_PIECE)
        try:
            sp.busy = True
            sp._cancel.clear()
            sp._held.clear()
            sp._turn = turn
            sess.playing = True
            self.v.portal.state("speaking")
            want = first
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
                if cap > 0 and stop_at is None and played >= cap * OUT_RATE * 2:
                    stop_at = cap_at(played, got, "".join(said), cap * 1.5 * OUT_RATE * 2)
                if stop_at is not None and played >= stop_at:
                    turn["capped"] = 1
                    return True if ended and not buf else CAPPED
                if buf:
                    n = most if stop_at is None else max(2, min(most, stop_at - played))
                    piece = bytes(buf[:n])
                    del buf[:n]
                    played += len(piece)
                    if not sp.say_piece(piece, OUT_RATE):
                        return False
                want = each
                if ended and not buf:
                    return True
        finally:
            try:
                sp.drain()  # (0.9.2) pieces handed ahead to a gapless output play out (or were stopped) first
            except Exception:
                pass
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
                sru = m.get("sessionResumptionUpdate")
                if isinstance(sru, dict) and not sess.guest and sru.get("resumable") and sru.get("newHandle"):
                    self._handle = (str(sru["newHandle"]), time.monotonic())  # (0.9.2) his session only, memory
                if m.get("goAway") is not None:  # (0.9.2) Google will close it soon: the next turn opens afresh
                    sess.going = True
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
            if sess.guest:  # (0.9.2) the guest session declares none; one asked for anyway never runs
                out.append({"id": fc.get("id"), "name": name, "response": {"result": NO_TOOLS}})
                continue
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


def desk(si: str, end: str = DESK) -> str:
    """The call's instructions, for the desk: the time filled in, "on a call" lines changed or left out."""
    si = si.replace("%%NOW%%", now().strftime("%A %d %B %Y, %H:%M"))
    si = si.replace("on a live voice call.", "talking with them aloud at their computer.")
    si = si.replace("Talk like a friend on a call", "Talk like a friend sitting with them")
    lines = [ln for ln in si.split("\n") if "every call" not in ln]  # (pending_items' "at the start of every call")
    return "\n".join([*lines, end])


def spoken(said: str) -> str:
    """(0.9.2) The answer shown and kept: Live's own words (its output transcription), never data. Words that read as
    a tool's JSON (it read a result out) are left out: "(answered aloud)" stands for them."""
    t = (said or "").strip()
    if t[:1] in "{[" and ('":' in t or t[-1:] in "}]"):
        return ""
    return t


def _blocking(d: dict) -> dict:
    return {k: x for k, x in d.items() if k != "behavior"}


async def _start(sess: Session, coro) -> None:
    task = asyncio.create_task(coro)
    sess.tasks.add(task)
    task.add_done_callback(sess.tasks.discard)


async def _activity(ws) -> None:
    """(0.9.2) You talked over the answer (barge-in, a stop): Live is told your activity started, which interrupts
    the answer it's still making."""
    await ws.send(json.dumps({"realtimeInput": {"activityStart": {}}}))


async def _send_turn(ws, pcm: bytes, start: bool = True) -> None:
    if start:
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


CAPPED = "capped"


def cap_at(played: int, got: int, text: str, hard: float) -> int | None:
    """(0.9.2, spoken_max_s) Where to stop (bytes of sound), past `played`: the next sentence end in Live's transcript
    `text`, placed in the sound by the transcript's characters per byte received so far; None: no end yet (keep
    playing, asked again next piece), or `hard` bytes reached: here."""
    if not text or not got:
        return played if played >= hard else None
    per = len(text) / got
    pos = int(played * per)
    m = SENTENCE_END.search(text, pos)
    if m is None:
        return played if played >= hard else None
    at = int((m.end()) / per) + int(0.15 * OUT_RATE * 2)
    return max(played, at - at % 2)


class Cue:
    """(0.9.2, voice.live.ack) The heard-you sound on a Live turn: ACK_AFTER_S after it was sent with no sound from
    Live yet, and again on a tool call; Live's first sound cuts it off (heard())."""

    def __init__(self, v, turn: dict):
        self.v, self.turn = v, turn
        self.first = threading.Event()
        self.playing = False
        self.times = 0

    def start(self) -> None:
        def wait() -> None:
            if not self.first.wait(ACK_AFTER_S):
                self.play()

        threading.Thread(target=wait, name="voice-live-cue", daemon=True).start()

    def play(self, again: bool = False) -> None:
        if self.first.is_set() or self.playing or (self.times and not again):
            return
        self.times += 1
        try:
            self.v.publish("voice_ack", on=True)  # the page shows it heard you, whatever is played
            quiet = getattr(self.v, "cue_quiet", None)
            if quiet is not None and quiet():
                return
            how = str(self.v.setting("speak.ack") or "tone").strip().lower()
            got = self.v._ack_sound(how if how in ("tone", "word") else "tone")
            if got is None or self.first.is_set():
                return
            self.playing = True
            self.v.speaker.ack(*got, self.turn)
        except Exception:
            pass
        finally:
            self.playing = False

    def heard(self) -> None:
        """Live's first sound (or the turn ended): no cue now, and one playing is cut off."""
        self.first.set()
        if self.playing:
            try:
                self.v.speaker._cut_piece()
            except Exception:
                pass


async def _ping(ws) -> None:
    pong = await ws.ping()
    await asyncio.wait_for(pong, PING_S)
