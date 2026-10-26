"""Physical stimulation (Brain, 0.8.8, `mind.stimulation.on`): the senses felt as a body, as touch, heat, pain and
motion. Every minute, from what the senses already read (mind/senses: intero's sample of its own machine, the activity
stream if it's on, the phone's bins if they're on), each reading becomes a channel of a body map.

    channel      reading                                                 region   kind
    heat         the hottest of CPU and GPU, in C                        skin     tonic
    warmth       the phone's ambient light (dark 0, dim 0.5, bright 1)   skin     tonic
    touch        phone unlocks in the last 5 minutes, and window         skin     phasic
                 switches on this computer (the activity stream): held
    load         max(CPU %, memory %) + 5 per AI request waiting         head     tonic
    pain         how many pain thresholds are broken (below)             head     tonic
    nourishment  battery %, +10 while charging (100 on mains)            gut      tonic
    motion       still 0, walking 1, vehicle 2, + new steps / 200        hands    phasic
    hearing      headphones on (1) or off (0)                            hands    tonic
    quiet        Do Not Disturb on (1) or off (0)                        hands    tonic
    place        home 1 (a saved place or Wi-Fi labelled home), else 0   hands    tonic
(head = the laptop, hands = the phone, gut = nourishment, skin = heat and touch.)

Per channel, every minute:
    baseline     mu and spread s are slow EWMAs, alpha = 1 - exp(-dt / 6 h): it adapts like skin does
    intensity    I = 2 sigmoid(g ln(1 + |x - mu| / (s + eps))) - 1 = tanh(g/2 ln(1 + |x - mu| / (s + eps)))
                 (Weber-Fechner: the change matters, relative to what's normal; the spec's sigmoid, shifted so that a
                 reading at its baseline is felt as 0, not 0.5)
    phasic       touch and motion: a change sets a peak that decays with tau = 2 minutes; tonic channels hold
    valence      an inverted U around a comfort setpoint, v = amp (1 - 2 z^2), z = (x - c) / w (w the left or right
                 width), in [-1, 1]: warm is fine, hot hurts; some load is good, overload hurts. Past a pain threshold
                 the channel's valence is -1 whatever the curve says.
    pain         over 90 C, under 5 % disk or battery (not charging), a crash in the last hour, an AI provider at its
                 limit. Pain doesn't fade into the baseline: while a threshold is broken its intensity is at least 0.8.
Out: per region (intensity = its strongest channel, valence = the intensity-weighted mean of its channels' valences),
arousal = the weighted mean intensity, hedonic tone = the intensity-weighted valence (both with a 0.05 floor weight per
channel, so a calm, comfortable body reads mildly positive rather than undefined).

What it feeds: feelings (the body's arousal raises the feelings' arousal: mind/feelings.py) and the mood, as an input,
never as a reward: only the tone of its own body (heat, load, pain, nourishment) goes with the body budget's tick
(mind/measure.py) and moves the mood a little (mind/engine.py TONE_GAIN). Channels about him (touch, motion, hearing,
quiet, place, warmth) are shown, and raise arousal, but never move its mood, so nothing in it prefers him to behave one
way (I-14). The dashboard reads it at GET /api/body (numbers only). It stays on this computer:
`<state>/mind-stimulation.json`, the latest state only.
"""

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

PART = "stimulation"  # its switch: mind.stimulation.on

register_defaults(
    "mind",
    {
        "stimulation": {
            "on": True,  # its senses felt as a body (heat, load, touch, pain...), for its feelings and the dashboard
        }
    },
)

FILE = "mind-stimulation.json"
TAU_S = 6 * 3600.0  # the baseline's window
PHASIC_TAU_S = 120.0  # a touch or a movement fades with this
PAIN = {"hot_c": 90.0, "disk_pct": 5.0, "battery_pct": 5.0, "crash_s": 3600.0}
PAIN_FLOOR = 0.8
FLOOR_W = 0.05
REGIONS = ("head", "hands", "gut", "skin")


class Channel:
    __slots__ = ("region", "phasic", "weight", "gain", "eps", "c", "left", "right", "amp", "own")

    def __init__(self, region, phasic, weight, gain, eps, c, left, right, amp, own):
        self.region, self.phasic, self.weight, self.gain, self.eps = region, phasic, weight, gain, eps
        self.c, self.left, self.right, self.amp, self.own = c, left, right, amp, own


CHANNELS: dict[str, Channel] = {
    #                     region  phasic weight gain  eps   comfort left  right  amp  its own body
    "heat": Channel("skin", False, 1.0, 1.5, 1.0, 55.0, 40.0, 30.0, 1.0, True),
    "warmth": Channel("skin", False, 0.5, 1.5, 0.1, 0.5, 0.75, 0.75, 0.5, False),
    "touch": Channel("skin", True, 0.8, 1.5, 0.5, 2.0, 4.0, 8.0, 0.6, False),
    "load": Channel("head", False, 1.0, 1.5, 2.0, 35.0, 70.0, 55.0, 1.0, True),
    "pain": Channel("head", False, 1.5, 2.0, 0.2, 0.0, 1.0, 1.0, 0.0, True),
    "nourishment": Channel("gut", False, 1.0, 1.5, 2.0, 85.0, 80.0, 60.0, 1.0, True),
    "motion": Channel("hands", True, 0.6, 1.5, 0.2, 1.0, 2.0, 2.0, 0.5, False),
    "hearing": Channel("hands", False, 0.3, 1.5, 0.1, 0.5, 1.0, 1.0, 0.2, False),
    "quiet": Channel("hands", False, 0.3, 1.5, 0.1, 0.5, 1.0, 1.0, 0.3, False),
    "place": Channel("hands", False, 0.4, 1.5, 0.1, 1.0, 1.5, 1.5, 0.6, False),
}


def on(app: App) -> bool:
    return mind.part_on(app, PART)


# ------------------------------------------------------------------------------------------------- the maths
def intensity(x: float, mu: float, s: float, gain: float, eps: float) -> float:
    """Weber-Fechner: how far from normal, relative to the normal spread, on a log scale, squashed to [0, 1)."""
    z = abs(float(x) - float(mu)) / (max(0.0, float(s)) + eps)
    return math.tanh(0.5 * gain * math.log1p(z))


def comfort(ch: Channel, x: float) -> float:
    """The inverted U around the comfort setpoint, in [-1, 1]."""
    w = ch.left if x < ch.c else ch.right
    z = (float(x) - ch.c) / max(w, 1e-9)
    return max(-1.0, min(1.0, ch.amp * (1.0 - 2.0 * z * z)))


def ewma(mu: float, s2: float, x: float, dt: float, tau: float = TAU_S) -> tuple[float, float]:
    """One step of the slow baseline: the mean and the variance, alpha = 1 - exp(-dt / tau)."""
    a = 1.0 - math.exp(-max(0.0, dt) / tau)
    d = x - mu
    mu2 = mu + a * d
    return mu2, (1.0 - a) * (s2 + a * d * d)


def feel(name: str, prev: dict | None, x: float, t: float, broken: bool = False) -> dict:
    """One channel's new state: {x, mu, s2, I, v, peak, changed, at} from the last one and the reading x at t."""
    ch = CHANNELS[name]
    if not prev or "mu" not in prev:
        prev = {"mu": x, "s2": 0.0, "x": x, "peak": 0.0, "changed": t, "at": t}
    dt = max(0.0, t - float(prev.get("at", t)))
    raw = intensity(x, prev["mu"], math.sqrt(max(0.0, prev["s2"])), ch.gain, ch.eps)
    peak, changed = float(prev.get("peak", 0.0)), float(prev.get("changed", t))
    if ch.phasic:
        now_i = peak * math.exp(-(t - changed) / PHASIC_TAU_S)
        if x != prev.get("x"):
            peak, changed = max(raw, now_i), t
            now_i = peak
        i = now_i
    else:
        i = raw
    if broken:
        i = max(i, PAIN_FLOOR)
    v = -1.0 if broken else (0.0 if name == "pain" else comfort(ch, x))
    mu, s2 = ewma(prev["mu"], prev["s2"], x, dt)
    return {"x": x, "mu": round(mu, 6), "s2": round(s2, 6), "I": round(i, 4), "v": round(v, 4),
            "peak": round(peak, 4), "changed": round(changed, 1), "at": round(t, 1)}  # fmt: skip


def summarise(channels: dict[str, dict]) -> dict:
    """Regions, arousal, hedonic tone and its own body's tone, from the channels' (I, v)."""
    regions = {r: {"intensity": 0.0, "valence": 0.0, "channels": {}} for r in REGIONS}
    num = den = aw = ai = own_n = own_d = 0.0
    per: dict[str, list] = {r: [] for r in REGIONS}
    for name, c in channels.items():
        ch = CHANNELS[name]
        i, v = float(c["I"]), float(c["v"])
        per[ch.region].append((i, v))
        regions[ch.region]["channels"][name] = {"intensity": round(i, 4), "valence": round(v, 4)}
        w = i + FLOOR_W
        num, den = num + w * v, den + w
        aw, ai = aw + ch.weight, ai + ch.weight * i
        if ch.own:
            own_n, own_d = own_n + w * v, own_d + w
    for r, xs in per.items():
        if xs:
            regions[r]["intensity"] = round(max(i for i, _ in xs), 4)
            regions[r]["valence"] = round(sum((i + FLOOR_W) * v for i, v in xs) / sum(i + FLOOR_W for i, _ in xs), 4)
    return {
        "regions": regions,
        "arousal": round(ai / aw, 4) if aw else 0.0,
        "tone": round(num / den, 4) if den else 0.0,
        "own_tone": round(own_n / own_d, 4) if own_d else 0.0,
    }


# ------------------------------------------------------------------------------------------------- the readings
def readings(app: App, t: float, prev: dict | None = None) -> tuple[dict[str, float], dict[str, bool]]:
    """({channel: x}, {channel: a pain threshold broken}) from what the senses read; a channel with no input is left
    out."""
    from kurooto.mind.senses import intero

    prev = prev or {}
    x: dict[str, float] = {}
    broken: dict[str, bool] = {}
    hist = (jload(app.paths.state / intero.FILE, {}) or {}).get("history") or []
    s = hist[-1] if hist and t - float(hist[-1].get("at") or 0) < 600 else {}
    pains = 0
    if s:
        temps = [float(s[k]) for k in ("cpu_temp_c", "gpu_temp_c") if isinstance(s.get(k), (int, float))]
        if temps:
            x["heat"] = max(temps)
            broken["heat"] = max(temps) > PAIN["hot_c"]
            pains += broken["heat"]
        load = max(float(s.get("cpu_pct") or 0.0), float(s.get("ram_pct") or 0.0))
        x["load"] = min(100.0, load + 5.0 * min(int(s.get("queue_depth") or 0), 10))
        disk_pain = isinstance(s.get("disk_free_pct"), (int, float)) and float(s["disk_free_pct"]) < PAIN["disk_pct"]
        pains += bool(disk_pain) + bool(s.get("limit_hit"))
        if "battery_pct" in s:
            charging = bool(s.get("charging"))
            x["nourishment"] = min(110.0, float(s["battery_pct"]) + (10.0 if charging else 0.0))
            broken["nourishment"] = float(s["battery_pct"]) < PAIN["battery_pct"] and not charging
            pains += broken["nourishment"]
        else:
            x["nourishment"] = 100.0  # on mains: fed
        try:
            cut = time.time() - PAIN["crash_s"]
            crashed = [e for e in app.events.tail(20, {"kurooto_crashed"}) if _ts(e.get("ts")) >= cut]
            pains += bool(crashed)
        except Exception:
            pass
        x["pain"] = float(pains)
        broken["pain"] = pains > 0
    _phone(app, t, x, prev)
    return x, broken


def _ts(iso) -> float:
    import datetime as dt

    try:
        return dt.datetime.fromisoformat(str(iso)).timestamp()
    except ValueError:
        return 0.0


def _phone(app: App, t: float, x: dict, prev: dict) -> None:
    """The phone's channels, from the bins the phone sends (each sensor opt-in) and the activity stream."""
    try:
        from kurooto.mind.senses import activity, phone, store
    except Exception:
        return

    def last(sensor: str, since: float) -> dict | None:
        if not phone.enabled(app, sensor):
            return None
        rows = store.events(app, f"phone:{sensor}", since)
        return rows[-1] if rows else None

    day = t - 86400
    touch = 0.0
    seen_touch = False
    if phone.enabled(app, "screen"):
        seen_touch = True
        touch += sum(r["n"] for r in store.events(app, "phone:screen", t - 300, "unlocks"))
    if activity.on(app):
        seen_touch = True
        touch += len(store.events(app, "activity", t - 300, "window"))
    if seen_touch:
        x["touch"] = touch
    m = last("motion", day)
    if m is not None or phone.enabled(app, "steps"):
        val = {"still": 0.0, "walking": 1.0, "vehicle": 2.0}.get((m or {}).get("target") or "", 0.0)
        st = last("steps", day)
        steps = float((st or {}).get("n") or 0.0)
        before = float(((prev.get("channels") or {}).get("motion") or {}).get("steps") or steps)
        x["motion"] = val + min(1.0, max(0.0, steps - before) / 200.0)
        x["_steps"] = steps
    li = last("light", day)
    if li is not None:
        x["warmth"] = {"dark": 0.0, "dim": 0.5, "bright": 1.0}.get(li.get("target") or "", 0.5)
    h = last("headphones", day)
    if h is not None:
        x["hearing"] = 1.0 if h["n"] else 0.0
    q = last("dnd", day)
    if q is not None:
        x["quiet"] = 1.0 if q["n"] else 0.0
    p = last("places", day)
    w = last("wifi", day)
    if p is not None or w is not None:
        if w is not None:  # the Wi-Fi it's on says it best, once you've labelled it
            home = "home" in phone.wifi_label(app, str(w.get("target") or "")).lower()
        else:  # else the last saved place it reported
            home = "home" in str((p or {}).get("target") or "").lower()
        x["place"] = 1.0 if home else 0.0


# ------------------------------------------------------------------------------------------------- the tick
def tick(app: App, payload: dict | None = None, t: float | None = None) -> dict | None:
    """Every minute: read, feel, keep the latest state. None when it's off."""
    if not on(app):
        return None
    t = float(t if t is not None else time.time())
    prev = state(app)
    x, broken = readings(app, t, prev)
    steps = x.pop("_steps", None)
    chans: dict[str, dict] = {}
    for name, val in x.items():
        if name in CHANNELS:
            chans[name] = feel(name, (prev.get("channels") or {}).get(name), float(val), t, bool(broken.get(name)))
    if steps is not None and "motion" in chans:
        chans["motion"]["steps"] = steps
    out = {"channels": chans, **summarise(chans), "at": round(t, 1)}
    jsave(app.paths.state / FILE, out)
    return out


def state(app: App) -> dict:
    return jload(app.paths.state / FILE, {}) or {}


def own_tone(app: App) -> float | None:
    """The hedonic tone of its own body (heat, load, pain, nourishment), for the mood: None when off or not felt yet,
    or older than ten minutes."""
    if not on(app):
        return None
    st = state(app)
    if not st or time.time() - float(st.get("at") or 0) > 600:
        return None
    return float(st.get("own_tone") or 0.0)


def body(app: App) -> dict:
    """For the dashboard (GET /api/body): plain numbers only, nothing of what he wrote or where he is."""
    st = state(app) if on(app) else {}
    regions = st.get("regions") or {r: {"intensity": 0.0, "valence": 0.0, "channels": {}} for r in REGIONS}
    clean = {
        r: {
            "intensity": float((regions.get(r) or {}).get("intensity") or 0.0),
            "valence": float((regions.get(r) or {}).get("valence") or 0.0),
            "channels": {
                str(c): {"intensity": float(v.get("intensity") or 0.0), "valence": float(v.get("valence") or 0.0)}
                for c, v in ((regions.get(r) or {}).get("channels") or {}).items()
                if c in CHANNELS and isinstance(v, dict)
            },
        }
        for r in REGIONS
    }
    mood = None
    try:
        from kurooto.mind import feelings

        mood = feelings.self_mood(app) if mind.on(app) else None
    except Exception:
        pass
    return {
        "on": on(app),
        "regions": clean,
        "arousal": float(st.get("arousal") or 0.0),
        "tone": float(st.get("tone") or 0.0),
        "mood": round(mood, 4) if isinstance(mood, (int, float)) else 0.0,
        "at": float(st.get("at") or 0.0),
    }


def report(app: App) -> str:
    """/senses body: how its body feels, in words and numbers."""
    if not on(app):
        return "Its sense of a body is off (mind.stimulation.on)."
    st = state(app)
    if not st:
        return "Nothing felt yet: it reads its senses every minute."
    lines = [f"Its body: arousal {st.get('arousal', 0):.2f}, hedonic tone {st.get('tone', 0):+.2f}."]
    for r, d in (st.get("regions") or {}).items():
        if d.get("channels"):
            parts = ", ".join(f"{c} {v['intensity']:.2f}/{v['valence']:+.2f}" for c, v in sorted(d["channels"].items()))
            lines.append(f"- {r}: {d['intensity']:.2f} felt, {d['valence']:+.2f} ({parts})")
    return "\n".join(lines)


def forget(app: App) -> None:
    (app.paths.state / FILE).unlink(missing_ok=True)
