"""Voice ID per microphone (0.9.2; voice.speaker_id.per_device, voice.speaker_id.claim): the plain rules, no I/O.

A voice print is enrolled on one microphone. Through another (a phone's, through an add-on; a headset) the same voice
scores lower, most turns come out "not sure", and "improve over time" pulled the print toward that microphone until
its drift guard stopped it for good. So:

    enrolled_on(tpl, dev)   the microphone the print was enrolled on (its "mic", or "mics" when recorded)
    a device's entry        tpl["devices"][dev]: its samples (vectors only, with the day and how each was proven),
                            its state, its own print once built, and whether the owner said yes
    add()                   a proven turn's vector: his face recognised alone at that moment, one voice, at least
                            BOOT_SPEECH_S of speech (how "face"), or a "that was me" tap with his face in view (how
                            "claim"); either only when its score against the print in use isn't in the "clearly not
                            you" band (voiceid.check: at or above the band's unsure cut-off); capped per day,
                            KEEP_MAX kept (the oldest goes)
    due() / build()         with MIN_SAMPLES (12) of them the print is built like an enrolment's (speakerid.calibrate:
                            outliers out, the template, held-out scores) against the impostor set heard through a
                            simulated phone channel when it ships (impostors-<model>-phone.bin), else the plain one;
                            never synthetic (TTS) voices. A weak one keeps learning and is built again every
                            REBUILD_EVERY samples
    usable()                the print is used only after the owner's one-time yes (state "on"); "No" drops the samples
                            and it stops learning there until he forgets that microphone's entry

Until a microphone has a print in use, "improve over time" leaves the enrolled print alone there (Voice ID scores with
it, but never learns from it): the fix for the drift guard's block. Nothing here is audio: vectors and counts only, in
the sealed template (core/biometric.py)."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from kurooto.modules.voice import speakerid as sid

BOOT_SPEECH_S = 2.0  # a turn proven by his face needs at least this much speech to be a sample
CLAIM_SPEECH_S = 1.0  # a claimed turn needs this much to be kept as a sample (shorter: only re-run)
KEEP_MAX = 40  # samples kept per microphone (the oldest goes)
REBUILD_EVERY = 6  # a weak print is built again after this many more samples
STATES = ("learning", "weak", "ready", "on", "declined")
HOW = ("face", "claim")


def key(name: str) -> str:
    """A microphone's name as Voice ID keys it ("" -> "default")."""
    return str(name or "").strip()[:120] or "default"


def ref(dev: str) -> str:
    """A short, stable reference for buttons (never the name itself)."""
    return hashlib.sha1(dev.encode(), usedforsecurity=False).hexdigest()[:8]


def enrolled_on(tpl: dict | None, dev: str) -> bool:
    """Whether `dev` is a microphone the print was enrolled on. A print that doesn't say counts as this one's (as
    before 0.9.2)."""
    t = tpl or {}
    mics = [str(m) for m in (t.get("mics") or [t.get("mic")]) if m]
    if not mics:
        return True
    return any(m == dev or m.startswith(f"{dev} via ") for m in mics)


def new() -> dict:
    return {"samples": [], "state": "learning", "print": None, "built_n": 0, "asked": False, "claims": {}}


def entry(tpl: dict | None, dev: str) -> dict | None:
    return ((tpl or {}).get("devices") or {}).get(dev)


def usable(d: dict | None) -> bool:
    return bool(d and d.get("state") == "on" and (d.get("print") or {}).get("centroid"))


def learning(d: dict | None) -> bool:
    """Still taking samples (no entry yet counts)."""
    return d is None or d.get("state") in ("learning", "weak", "ready")


def add(d: dict, e: Sequence[float], how: str, day: str, per_day: int) -> tuple[bool, str]:
    """A proven turn's vector into the entry (changed in place). (taken, why not)."""
    if not learning(d):
        return False, "not learning here"
    got = list(d.get("samples") or [])
    if sum(1 for x in got if x.get("day") == day and x.get("how") == how) >= max(0, int(per_day)):
        return False, "enough for today"
    got.append({"e": sid.to_b64(sid.normalize(e)), "day": day, "how": how if how in HOW else "face"})
    d["samples"] = got[-KEEP_MAX:]
    return True, "taken"


def due(d: dict) -> bool:
    """Time to build (or build again): enough samples, still learning or weak, enough new ones since the last."""
    n = len(d.get("samples") or [])
    if n < sid.MIN_SAMPLES or d.get("state") not in ("learning", "weak"):
        return False
    built = int(d.get("built_n") or 0)
    return built == 0 or n - built >= REBUILD_EVERY


def build(
    d: dict, bank: sid.Bank, channel: str, strictness: str = "normal", margin: float = 0.05, threshold: float = 0.0
) -> str:
    """The microphone's print from its samples (changed in place): state "ready" (good or fair: ask once) or "weak"
    (keeps learning). Returns the grade, or "" when it can't be built."""
    raw = [{"e": sid.from_b64(x["e"]), "s": None, "cond": x.get("how") or "face"} for x in d.get("samples") or []]
    try:
        res = sid.calibrate(raw, bank, (), strictness, margin, threshold)  # never synthetic voices
    except ValueError:
        return ""
    r = res["report"]
    d["print"] = {
        "centroid": sid.to_b64(res["centroid"]),
        "centroid_enrolled": sid.to_b64(res["centroid"]),
        "thresholds": res["thresholds"].to_dict(),
        "calibrated": res["calibrated"].to_dict(),
        "report": {k: v for k, v in r.items() if k != "histogram"},
        "adapted": [],
        "drift_stopped": False,
        "bank": channel,
    }
    d["built_n"] = len(raw)
    d["state"] = "weak" if r["grade"] == "weak" else "ready"
    return str(r["grade"])


def decide(d: dict, yes: bool) -> None:
    """The owner's one-time answer: yes puts the print in use; no drops the samples and the print, and it stops
    learning on this microphone."""
    if yes:
        if (d.get("print") or {}).get("centroid"):
            d["state"] = "on"
        return
    d.update(samples=[], print=None, built_n=0, state="declined")


def claims_today(d: dict, day: str) -> int:
    c = d.get("claims") or {}
    return int(c.get("n") or 0) if c.get("day") == day else 0


def view(dev: str, d: dict, now: str = "") -> dict:
    """What the page and /voice id show of one microphone: counts, the state and the grade; never a vector."""
    p = d.get("print") or {}
    r = p.get("report") or {}
    s = d.get("samples") or []
    return {
        "name": dev,
        "ref": ref(dev),
        "state": d.get("state") or "learning",
        "samples": len(s),
        "need": sid.MIN_SAMPLES,
        "by_how": {h: sum(1 for x in s if x.get("how") == h) for h in HOW},
        "grade": r.get("grade"),
        "frr_long": r.get("frr_long"),
        "bank": p.get("bank"),
        "learned": len(p.get("adapted") or []),
        "now": dev == now,
    }
