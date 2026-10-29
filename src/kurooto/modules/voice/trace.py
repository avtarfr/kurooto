"""The turn record and the route (0.9.2, voice.listen.trace): one numbers-only row per stretch Voice judged, and the
pure decision of where an addressed turn goes.

- **route(facts)** says which way an addressed turn goes, from plain facts (Voice ID's word, the switches, whether a
  face was seen, whether its sound was kept): LIVE (Gemini Live, his session), LIVE_GUEST (Live's guest session), BRAIN
  (his AI the usual way) or GUEST (the text guest path). It was pulled out of Voice.ask_brain without changing what it
  does (tests/unit/test_voice_route.py drives the real flow over the whole table). Live may still fail or refuse (no
  key, the guest rules, the hourly cap, no first sound): then fallback(path, who) is where the turn goes instead.
- **Trace** keeps the last KEEP rows in memory: the gate's class and rule, the face check's state, Voice ID's word and
  score, the path, the stage times in ms from the last word (Voice ID, the transcriber's wait and work, how many times
  it ran, the gate, the face check, sent, first sound) and the machine's load. Never words, sound or a voice's numbers;
  never written to disk or sent in an event (the score stays in memory, for /voice turns and add-ons on this computer).
  Voice.turn_log is its rows, newest last. /voice turns shows them as a table; GET /api/voice has them under "turns".
"""

from __future__ import annotations

import itertools
import os
import time
from collections import deque

KEEP = 20

LIVE, LIVE_GUEST, BRAIN, GUEST = "live", "live_guest", "brain", "guest"

# the face check's state for a turn (Voice._timed_face_check): what the Body add-on and /voice turns show
FACE_SEEN, FACE_NONE, FACE_BLIND, FACE_OFF, FACE_FREE, FACE_UNCHECKED = "seen", "none", "blind", "off", "free", ""


def route(f: dict) -> str:
    """Where an addressed turn goes. f: who ("owner", "unsure", "guest", or "" with Voice ID off), live
    (voice.listen.live), everyone (live_everyone), faced (a face was seen close and facing it for this turn), kept (its
    sound was kept for Live), speak (voice.speak.on), cut (Voice off or muted meanwhile), at_all (Voice ID's mode is
    owner_only_at_all)."""
    who = f.get("who") or ""
    live_ok = bool(f.get("live") and f.get("kept") and f.get("speak") and not f.get("cut"))
    if who == "owner":
        return LIVE if live_ok and (f.get("faced") or f.get("everyone")) else BRAIN
    if live_ok and f.get("everyone") and not f.get("at_all"):
        return LIVE_GUEST
    return GUEST if who else BRAIN


def fallback(path: str, who: str) -> str:
    """Where a turn goes when Live couldn't take it (or wasn't asked)."""
    if path == LIVE:
        return BRAIN
    if path == LIVE_GUEST:
        return GUEST if who else BRAIN
    return path


def load() -> float | None:
    """The machine's load over the last minute (None where it can't be read)."""
    try:
        return round(os.getloadavg()[0], 2)
    except (OSError, AttributeError):
        return None


def percentile(xs: list, q: float):
    """The q-th (0..1) value of xs by rank (nearest), None when empty."""
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    return xs[min(len(xs) - 1, max(0, round(q * (len(xs) - 1))))]


class Trace:
    """The last KEEP turn rows, in memory. new() starts a row; done() files it (its "ms" from the turn's stamps)."""

    def __init__(self):
        self.rows: deque = deque(maxlen=KEEP)
        self._seq = itertools.count(1)

    def new(self, end: float) -> dict:
        return {"seq": next(self._seq), "at": time.strftime("%H:%M:%S"), "end": end, "gate": "", "rule": "",
                "face": FACE_UNCHECKED, "id_verdict": "", "id_score": None, "path": "", "speech_s": 0.0,
                "stt_runs": 0, "voiceid_ms": 0, "stt_wait_ms": 0, "stt_ms": 0}  # fmt: skip

    def done(self, rec: dict, turn: dict | None = None) -> dict:
        """Files the row: the turn's stamps as ms from the last word (fast.numbers), the load; returns the row."""
        from kurooto.modules.voice import fast

        end = rec.pop("end", None)
        if turn is not None and end is not None:
            rec.update({k: v for k, v in fast.numbers(turn).items() if k not in rec})
        rec["load"] = load()
        for k in ("voiceid_ms", "stt_wait_ms", "stt_ms"):
            rec[k] = round(rec.get(k) or 0)
        rec["speech_s"] = round(float(rec.get("speech_s") or 0.0), 2)
        if rec.get("id_score") is not None:
            rec["id_score"] = round(float(rec["id_score"]), 2)
        self.rows.append(rec)
        return rec

    def table(self) -> str:
        """The rows as a small text table for /voice turns, newest last."""
        if not self.rows:
            return "No turns heard since Kurooto started (or voice.listen.trace is off)."
        head = "#    time      gate       face  voice      path        words  wait  id   sent  sound"
        out = [head]
        for r in self.rows:
            vid = r.get("id_verdict") or "-"
            if r.get("id_score") is not None:
                vid = f"{vid} {r['id_score']:.2f}"
            sound = r.get("play_ms", r.get("audio_ms"))
            out.append(
                f"{r['seq']:<4} {r.get('at', ''):<9} {(r.get('gate') or '-')[:10]:<10} {(r.get('face') or '-')[:5]:<5} "
                f"{vid[:10]:<10} {(r.get('path') or '-')[:11]:<11} {_s(r.get('text_ms')):>5} "
                f"{_s(r.get('stt_wait_ms') or None):>5} {_s(r.get('voiceid_ms') or None):>4} {_s(r.get('sent_ms')):>5} "
                f"{_s(sound):>6}"
            )
        out.append("Seconds from your last word: words written out, the transcriber's wait, Voice ID's check, sent, "
                   "first sound. Numbers only, never words.")  # fmt: skip
        return "\n".join(out)


def _s(ms) -> str:
    return "-" if ms is None else f"{ms / 1000:.1f}"
