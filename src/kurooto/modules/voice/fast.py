"""Voice speed (0.8.16): how long a turn takes, and what makes the wait shorter or feel shorter.

- **Timing** (voice.listen.timing): each turn sent to the AI gets stamps, kept in memory as numbers only: your last
  word (the stretch's end), the words written out, the gate's decision with the face check, the request queued, the
  AI starting on it, its first words, the whole answer, the acknowledgement, the first sound made and the first sound
  playing (when an output, or this computer's player, is handed the sound). One
  voice_timing event per turn (milliseconds from your last word) and the medians in /voice and GET /api/voice.
- **Acknowledgement** (voice.speak.ack): the moment a turn goes to the AI, a short soft sound through the same output,
  unless the answer is already arriving: `tone` (made here, below) or `word` ("Hmm.", made once by the speech engine
  and kept in memory).
- **Streaming** (voice.speak.stream): Stream speaks the answer a sentence at a time as the AI writes it, when the AI
  can stream (providers/base.py: Task.on_text); the rest of the answer is spoken when it's done.
- **A faster brain for plain chat** (voice.listen.fast_brain): chat_only() says whether a turn needs nothing of yours
  and no tools; FastPick picks which AI answers those.

Nothing here keeps or sends words: the Stream holds the answer's text only while it speaks it."""

from __future__ import annotations

import collections
import math
import re
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from kurooto.modules.voice import shape as shape_mod

if TYPE_CHECKING:
    from kurooto.modules.voice import Speaker

# ---------------------------------------------------------------------------------------------------- timing
STAMPS = ("text", "gate", "sent", "start", "first_text", "answer", "ack", "audio", "play")
SHOWN = (("text", "words"), ("gate", "decided"), ("sent", "sent"), ("first_text", "first words from the AI"),
         ("audio", "first sound made"), ("play", "playing"))  # fmt: skip
KEEP = 20  # turns the medians are taken over


def stamp(turn: dict | None, name: str, at: float | None = None) -> None:
    """The first time `name` happened in this turn (later ones don't move it)."""
    if turn is not None and name not in turn:
        turn[name] = time.monotonic() if at is None else at


def numbers(turn: dict) -> dict:
    """The turn as milliseconds from your last word (only what happened), plus the face check's own wait."""
    end = turn.get("end")
    out: dict = {}
    if end is None:
        return out
    for k in STAMPS:
        if k in turn:
            out[f"{k}_ms"] = max(0, round((turn[k] - end) * 1000))
    for k in ("face_ms", "streamed", "fast"):
        if k in turn:
            out[k] = turn[k]
    return out


def medians(rows) -> dict:
    """Each stamp's median over the kept turns (ms), and how many turns."""
    rows = list(rows)
    out: dict = {"turns": len(rows)}
    for k in (*STAMPS, "face"):
        xs = sorted(r[f"{k}_ms"] for r in rows if f"{k}_ms" in r)
        if xs:
            out[f"{k}_ms"] = xs[len(xs) // 2]
    return out


def line(med: dict) -> str:
    """'Speed (median of 5 turns, from your last word): words 0.7 s, decided 1.2 s, ...' or ''."""
    if not med.get("turns"):
        return ""
    parts = [f"{label} {med[f'{k}_ms'] / 1000:.1f} s" for k, label in SHOWN if f"{k}_ms" in med]
    n = med["turns"]
    return f"Speed (median of {n} turn{'s' if n != 1 else ''}, from your last word): " + ", ".join(parts) + "."


# ------------------------------------------------------------------------------------------- acknowledgement
ACK_RATE = 24000
ACK_WORD = "Hmm."
ACK_WAIT_S = 0.25  # an answer that comes this soon (a plain-English request done here) needs no acknowledgement


def tone(sr: int = ACK_RATE) -> bytes:
    """A short soft sound: a G4 gliding up to about C5 over its first 40%, a quiet octave below it, a gentle rise and a
    long fall; 0.24 s, peaking about -20 dB. No click at either end (it starts and ends at zero)."""
    n = int(sr * 0.24)
    out = bytearray()
    phase = 0.0
    for i in range(n):
        t = i / n
        f = 392.0 * (1 + 0.33 * min(1.0, t * 2.5))  # glides up over the first 40%, then holds
        phase += 2 * math.pi * f / sr
        rise = min(1.0, t / 0.12)
        env = math.sin(rise * math.pi / 2) ** 2 * (1 - t) ** 1.6
        x = 0.1 * env * (math.sin(phase) + 0.25 * math.sin(phase / 2))
        out += struct.pack("<h", int(max(-1.0, min(1.0, x)) * 32767))
    return bytes(out)


# ---------------------------------------------------------------------------------------------- streaming
BOUNDARY = re.compile(r"(?<=[.!?])\s+|\n+")
REST = "The rest is on screen."


class Stream:
    """Speaks an answer while the AI writes it. feed(key, text so far) from the request's thread: every finished
    sentence is queued at once; finish(answer) from Voice when the answer is in: what wasn't spoken yet is queued and
    it waits until all of it has played. The speaking runs on a thread of its own holding the Speaker's lock (nothing
    else is said in between), a piece made while the one before plays, the first piece alone or joined up to 120
    characters, later ones up to 200 (voice.speak.join_sentences). While it waits for more words it isn't "speaking"
    (the microphone is held for the request as before, not opened for cutting in)."""

    def __init__(self, speaker: Speaker, turn: dict | None = None, wait_s: float = 600):
        self.sp, self.turn, self.wait_s = speaker, turn, wait_s
        v = speaker.v
        self.numbers = bool(v.setting("speak.numbers_as_words"))
        self.join = bool(v.setting("speak.join_sentences"))
        self.limit = int(v.setting("speak.max_chars") or 800)
        self.cond = threading.Condition()
        self.pieces: list[str] = []
        self.key = None
        self.text = ""
        self.used = 0  # characters of the current message already queued
        self.raw: list[str] = []  # what was queued, as written (to find what's left of the answer)
        self.chars = 0
        self.over = False
        self.closed = False
        self.cut = False  # stopped (/voice stop, mute, cutting in): nothing more is said
        self.thread: threading.Thread | None = None
        self.spoke = 0  # pieces played

    # ------------------------------------------------------------------------------------- the words in
    def feed(self, key, text: str) -> None:
        with self.cond:
            if self.cut or self.closed or self.over:
                return
            if key != self.key:  # a new message (the words before a tool call were one; the answer is the last)
                self.key, self.text, self.used = key, "", 0
            if not text.startswith(self.text[: self.used]):  # rewritten: wait for the answer
                return
            self.text = text
            done, rest = text[: self.used], text[self.used :]
            for end in reversed([m.end() for m in BOUNDARY.finditer(rest)]):
                if (done + rest[:end]).count("```") % 2 == 0:  # never inside a code block: up to before it
                    self.used += end
                    self._queue(rest[:end])
                    return

    def _queue(self, raw: str) -> None:
        """Under the lock: a finished stretch of text, as the pieces it's spoken in."""
        if not raw.strip():
            return
        stamp(self.turn, "first_text")
        self.raw.append(raw)
        for p in shape_mod.sentences(raw, numbers=self.numbers):
            if self.chars + len(p) > self.limit and self.chars:
                self.pieces.append(REST)
                self.over = True
                break
            self.pieces.append(p)
            self.chars += len(p)
        self.cond.notify_all()
        if self.pieces and self.thread is None:
            self.thread = threading.Thread(target=self._run, name="voice-stream", daemon=True)
            self.thread.start()

    def left(self, answer: str) -> str:
        """What of the whole answer hasn't been queued: the rest after the streamed part when the answer is the message
        streamed last; else its sentences that weren't said (another AI answered, or the text changed)."""
        final = (answer or "").strip()
        said = (self.text[: self.used] if self.key is not None else "").strip()
        if not said:
            return final if not self.raw or not final else self._unsaid(final)
        if final.startswith(said):
            return final[len(said) :]
        return self._unsaid(final)

    def _unsaid(self, final: str) -> str:
        done = {s.strip() for r in self.raw for s in BOUNDARY.split(r) if s.strip()}
        return " ".join(s for s in BOUNDARY.split(final) if s.strip() and s.strip() not in done)

    def finish(self, answer: str) -> None:
        """The whole answer: what's left of it is queued, then this waits until it's all been played (or stopped)."""
        with self.cond:
            if not self.cut and not self.over:
                rest = self.left(answer)
                if rest.strip():
                    self._queue(rest)
            self.closed = True
            self.cond.notify_all()
            t = self.thread
        if t is not None:
            t.join(self.wait_s)

    def cancel(self) -> None:
        with self.cond:
            self.cut = self.closed = True
            self.pieces.clear()
            self.cond.notify_all()

    # -------------------------------------------------------------------------------------- the sound out
    def _next(self, first: bool, block: bool) -> str | None:
        with self.cond:
            end = time.monotonic() + self.wait_s
            while block and not self.pieces and not self.closed and not self.sp._cancel.is_set():
                if time.monotonic() > end:
                    break
                if self.spoke:  # waiting for more words: not speaking now (the microphone stays held for the request)
                    self.sp.busy = False
                    self.sp.until = time.monotonic() + 0.4
                self.cond.wait(0.1)
            if not self.pieces or self.sp._cancel.is_set():
                return None
            self.sp.busy = True
            piece = self.pieces.pop(0)
            most = 120 if first else 200
            while self.join and self.pieces and len(piece) + 1 + len(self.pieces[0]) <= most:
                prev = piece if piece[-1] in ".!?;:," else piece + "."
                piece = f"{prev} {self.pieces.pop(0)}"
            return piece

    def _run(self) -> None:
        from kurooto.modules.voice import pause_after

        sp = self.sp
        tts, _why = sp.v.tts()
        if tts is None:
            with self.cond:
                self.cut = True
            return
        with sp.lock:
            sp.busy = True
            sp._cancel.clear()
            sp._turn = self.turn
            pool = ThreadPoolExecutor(1, thread_name_prefix="voice-tts")
            try:
                piece = self._next(first=True, block=True)
                fut = pool.submit(tts.synth, piece) if piece else None
                while fut is not None:
                    pcm, sr = fut.result()
                    stamp(self.turn, "audio")
                    nxt = self._next(first=False, block=False)
                    fut = pool.submit(tts.synth, nxt) if nxt else None
                    if nxt or not self.closed:  # more may come: the breath after it, as between pieces
                        pcm += pause_after(tts, piece, sr)
                    if sp._cancel.is_set():
                        break
                    try:
                        sp.v.barge.speaking([piece])
                    except Exception:
                        pass
                    sp.v.publish("voice_speak", samples=shape_mod.from_pcm(pcm, sr), rate=shape_mod.RATE)
                    sp._play(pcm, sr)
                    self.spoke += 1
                    if sp._cancel.is_set():
                        break
                    if fut is None:
                        piece = self._next(first=False, block=True)
                        fut = pool.submit(tts.synth, piece) if piece else None
                    else:
                        piece = nxt
            except Exception as e:
                sp.v.app.events.emit("voice_failed", part="speaking", error=f"{type(e).__name__}: {e}"[:300])
            finally:
                if sp._cancel.is_set():
                    with self.cond:
                        self.cut = True
                        self.pieces.clear()
                pool.shutdown(wait=False, cancel_futures=True)
                sp._turn = None
                sp.busy = False
                sp.until = time.monotonic() + 0.4


# ------------------------------------------------------------------------------------- a faster brain for chat
# words that mean the turn needs something of yours (notes, files, the calendar, what's due), the time now, the web,
# or an action: those go to your main AI with its tools, whatever voice.listen.fast_brain says
NEEDS = re.compile(
    r"\b(my|mine|our|i|i'm|im|i've|i'll|i'd|we|we're|us|remind\w*|remember\w*|forget|schedul\w*|notes?|files?|"
    r"folders?|documents?|pdfs?|deadlines?|due|calendar|class(es)?|lectures?|labs?|exams?|quiz\w*|assignments?|"
    r"homework|tasks?|to-?dos?|projects?|papers?|e-?mails?|mail|messages?|texts?|call\w*|alarms?|timers?|today|"
    r"tonight|tomorrow|yesterday|week\w*|month|now|latest|current\w*|news|weather|prices?|search\w*|look\s+up|find|"
    r"open|read|write|save|add|create|delete|update|change|set|send|move|plan|book|status|kurooto)\b",
    re.I,
)
CHAT_MAX = 240  # longer than this isn't small talk


def chat_only(app, text: str) -> bool:
    """Plain chat that needs nothing of yours and no tools: not a command, not something Kurooto's own requests would
    take (core/guest.py's check), and none of NEEDS' words. Careful by design: when unsure, the main AI answers."""
    t = (text or "").strip()
    if not t or len(t) > CHAT_MAX or t.startswith("/") or NEEDS.search(t):
        return False
    try:
        from kurooto.core import guest

        return guest.kind(app, t) == ""
    except Exception:
        return False


class FastPick:
    """voice.listen.fast_brain "fastest": which configured AI answers plain chat first, by how long its first words
    took in recent voice turns (memory only). One not tried yet is tried in the order below before the times decide:
    the main AI when it's an API, a Gemini key, the model on this computer, then the main AI held to text (an agent
    program with no tools and no MCP servers starts faster)."""

    def __init__(self):
        self.times: dict[str, collections.deque] = {}

    def note(self, key: str, seconds: float) -> None:
        self.times.setdefault(key, collections.deque(maxlen=5)).append(float(seconds))

    def median(self, key: str) -> float | None:
        xs = sorted(self.times.get(key) or [])
        return xs[len(xs) // 2] if xs else None

    @staticmethod
    def candidates(app) -> list[tuple[str, dict]]:
        """(key, turn options) for each AI that could answer plain chat here."""
        from kurooto import providers

        out: list[tuple[str, dict]] = []
        main_id = str(app.settings.get("brain.main") or "")
        try:
            main = providers.build(app, main_id) if main_id else None
        except Exception:
            main = None
        if main is not None and getattr(main, "kind", "") == "api" and main.available()[0]:
            out.append((main_id, {"brain": main_id, "text_only": True, "effort": "low"}))
        if main_id != "gemini":
            try:
                g = providers.fallback.ready(app, "gemini")
            except Exception:
                g = None
            if g is not None:
                out.append(("gemini", {"brain": "gemini", "text_only": True, "effort": "low"}))
        try:
            local = providers.local(app)
        except Exception:
            local = None
        if local is not None and local.id not in {k for k, _ in out}:
            out.append((local.id, {"brain": local.id, "text_only": True, "effort": "low"}))
        if main is not None and getattr(main, "kind", "") == "cli":
            out.append(("main", {"text_only": True, "effort": "low"}))
        return out

    def pick(self, app) -> tuple[str, dict] | None:
        cands = self.candidates(app)
        if not cands:
            return None
        for key, opts in cands:
            if self.median(key) is None:
                return key, opts
        return min(cands, key=lambda c: self.median(c[0]) or 0.0)
