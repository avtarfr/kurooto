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

Another device an add-on reports for (0.8.12, `feed`, `mind.stimulation.addons`): a phone standing as its face, the
eye page on its screen. Each raw reading is translated to a physical analogue (ADDON, `translate`), kept in memory
only, and felt at the next tick like the rest; older than 10 minutes, it's left out.

    channel      reading (the add-on's key, unit) -> x                    region   kind
    brightness   light_lux -> log10(1 + lux): 0 dark, 2 a room, 5 sun     face     tonic    light on its face, the pupil
    closeness    proximity_cm -> 1 - cm/10 in [0, 1], or near (0/1)       face     phasic   something at its face
    sway         accel_x/y/z m/s^2 -> | |a| - g |                         face     phasic   the otoliths: being moved
    tilt         accel_x/y/z -> degrees from upright (y up), 0..180       face     tonic    the otoliths: gravity
    turning      gyro_x/y/z rad/s -> |w|                                  face     phasic   the canals: rotation
    heading      heading_deg -> degrees, unwrapped from the last one      face     tonic    orientation (no valence)
    eyes         screen_on 0/1                                            face     tonic    its eyes open or shut
    loudness     loudness_db (SPL), or loudness_dbfs + 100                face     tonic    hearing: the room's sound
    handled      picked_up (0/1, or pick-ups since the last report)       skin     phasic   touch: being picked up
    temperature  battery_temp_c                                           skin     tonic    heat (over 45 C hurts)
    satiety      battery_pct, +10 while charging                          gut      tonic    hunger (under 5 % hurts)
(face = that device.) (0.9.0, face.light_sense) With no device's light fed in, Face presence's camera stands in for
brightness: its smoothed frame brightness (0..1) x WEBCAM_SCALE, a rough dark-to-lit signal.
Unknown keys, non-numbers and readings out of range are ignored. None of these move the mood:
an add-on can make it feel, never make it glad or sad (as the channels about him, I-14). A phasic channel is felt at
its strongest since the last tick; a tonic one at its latest.

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

The orienting jolt (0.8.14, `mind.stimulation.jolt`): something sudden (the phone picked up, something close to an
add-on's device, a loud room) is felt at once rather than at the next minute's tick. `jolt(app, kind)` (add-ons and
senses call it; feed() does for closeness, handled and loudness past JOLT_AT) raises arousal to the jolt's strength,
fading with PHASIC_TAU_S, and runs the workspace's cycle now. `arousal(app)` is the body's arousal with any jolt in it
(the status stream reads it). Kinds and numbers only, in memory; a kind jolts at most once a JOLT_GAP_S.
"""

from __future__ import annotations

import math
import re
import threading
import time
import weakref
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
            "addons": True,  # an add-on may feed another device's sensors in (light, motion, battery...): feed()
            "jolt": True,  # a pickup, something close or a loud room: an orienting jolt (arousal, a workspace look)
        }
    },
)

FILE = "mind-stimulation.json"
WEBCAM_SCALE = 2.5  # (0.9.0, face.light_sense) the camera's 0..1 level onto brightness's log-lux scale (rough)
TAU_S = 6 * 3600.0  # the baseline's window
PHASIC_TAU_S = 120.0  # a touch or a movement fades with this
PAIN = {"hot_c": 90.0, "disk_pct": 5.0, "battery_pct": 5.0, "crash_s": 3600.0}
PAIN_FLOOR = 0.8
FLOOR_W = 0.05
REGIONS = ("head", "hands", "gut", "skin", "face")


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
    # another device an add-on reports for (feed): never its own body, so never the mood
    "brightness": Channel("face", False, 0.4, 1.5, 0.2, 2.3, 2.3, 2.5, 0.5, False),
    "closeness": Channel("face", True, 0.6, 1.5, 0.2, 0.3, 1.0, 1.0, 0.3, False),
    "sway": Channel("face", True, 0.5, 1.5, 0.3, 0.5, 1.0, 4.0, 0.4, False),
    "tilt": Channel("face", False, 0.3, 1.5, 3.0, 0.0, 30.0, 90.0, 0.4, False),
    "turning": Channel("face", True, 0.4, 1.5, 0.1, 0.2, 1.0, 3.0, 0.4, False),
    "heading": Channel("face", False, 0.2, 1.2, 5.0, 0.0, 180.0, 180.0, 0.0, False),
    "eyes": Channel("face", False, 0.2, 1.5, 0.1, 1.0, 1.5, 1.0, 0.3, False),
    "loudness": Channel("face", False, 0.4, 1.5, 2.0, 45.0, 45.0, 35.0, 0.4, False),
    "handled": Channel("skin", True, 0.6, 1.5, 0.5, 1.0, 2.0, 4.0, 0.5, False),
    "temperature": Channel("skin", False, 0.5, 1.5, 1.0, 30.0, 25.0, 15.0, 0.6, False),
    "satiety": Channel("gut", False, 0.5, 1.5, 2.0, 85.0, 80.0, 60.0, 0.6, False),
    "interest": Channel("head", True, 0.5, 1.5, 0.1, 0.0, 1.0, 1.0, 0.5, False),  # something caught its attention
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
    _devices(app, t, x, broken)
    _webcam(app, x)
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


# ------------------------------------------------------------------------------------------------- another device
# An add-on's raw readings: key -> (lowest, highest) it may say; anything else, or out of range, is ignored.
ADDON = {
    "light_lux": (0.0, 200_000.0),
    "proximity_cm": (0.0, 1000.0),
    "near": (0.0, 1.0),
    "accel_x": (-200.0, 200.0),
    "accel_y": (-200.0, 200.0),
    "accel_z": (-200.0, 200.0),
    "gyro_x": (-100.0, 100.0),
    "gyro_y": (-100.0, 100.0),
    "gyro_z": (-100.0, 100.0),
    "heading_deg": (-360.0, 720.0),
    "screen_on": (0.0, 1.0),
    "loudness_db": (0.0, 160.0),
    "loudness_dbfs": (-160.0, 0.0),
    "picked_up": (0.0, 1000.0),
    "battery_temp_c": (-40.0, 100.0),
    "battery_pct": (0.0, 100.0),
    "charging": (0.0, 1.0),
    "interest": (0.0, 1.0),  # an add-on's judgement that something caught its attention (a jolt, felt in the head)
}
ADDON_PAIN = {"temperature": lambda x: x > 45.0, "loudness": lambda x: x >= 100.0, "satiety": lambda x: x < 5.0}
FED_S = 600.0  # a device's reading older than this isn't felt any more (as intero's sample)
LIVE_S = 0.2  # to open dashboards at most 5 a second per device
G = 9.80665
SOURCE = re.compile(r"^[\w .'-]{1,30}$")
_fed: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()  # app -> {channel: {x, peak, t, src}}: memory only
_live_at: dict[tuple[int, str], float] = {}
_fed_lock = threading.Lock()
JOLT_AT = {"closeness": 0.7, "handled": 1.0, "loudness": 75.0}  # an add-on's channel past this jolts (feed())
JOLT_KINDS = {"closeness": "close", "handled": "pickup", "loudness": "loud"}
JOLT_GAP_S = 60.0
KIND = re.compile(r"^[a-z_]{1,20}$")
_jolts: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()  # app -> {kind: {t, x}}: memory only


def _ok(readings: dict) -> dict[str, float]:
    """The readings it knows, as floats in range (a yes/no as 0/1); the rest dropped."""
    out = {}
    for k, v in readings.items():
        lim = ADDON.get(k) if isinstance(k, str) else None
        if lim is None or not isinstance(v, (int, float)) or not math.isfinite(v):
            continue
        if lim[0] <= float(v) <= lim[1]:
            out[k] = float(v)
    return out


def translate(readings: dict, heading_was: float | None = None) -> dict[str, float]:
    """An add-on device's raw readings -> {channel: x} (the table at the top); unknown ones are ignored."""
    r = _ok(readings) if isinstance(readings, dict) else {}
    x: dict[str, float] = {}
    if "light_lux" in r:
        x["brightness"] = math.log10(1.0 + r["light_lux"])
    if "proximity_cm" in r:
        x["closeness"] = max(0.0, 1.0 - r["proximity_cm"] / 10.0)
    elif "near" in r:
        x["closeness"] = 1.0 if r["near"] else 0.0
    if all(k in r for k in ("accel_x", "accel_y", "accel_z")):
        a = math.sqrt(r["accel_x"] ** 2 + r["accel_y"] ** 2 + r["accel_z"] ** 2)
        x["sway"] = abs(a - G)
        if a > 1.0:  # not falling: gravity says which way is down
            x["tilt"] = math.degrees(math.acos(max(-1.0, min(1.0, r["accel_y"] / a))))
    if all(k in r for k in ("gyro_x", "gyro_y", "gyro_z")):
        x["turning"] = math.sqrt(r["gyro_x"] ** 2 + r["gyro_y"] ** 2 + r["gyro_z"] ** 2)
    if "heading_deg" in r:  # a circle: 359 -> 1 is a turn of 2 degrees, not 358
        h = r["heading_deg"] % 360.0
        x["heading"] = h if heading_was is None else heading_was + ((h - heading_was % 360.0 + 540.0) % 360.0 - 180.0)
    if "screen_on" in r:
        x["eyes"] = 1.0 if r["screen_on"] else 0.0
    if "loudness_db" in r:
        x["loudness"] = r["loudness_db"]
    elif "loudness_dbfs" in r:  # full scale, uncalibrated: 0 dBFS read as a loud 100 dB
        x["loudness"] = max(0.0, r["loudness_dbfs"] + 100.0)
    if "picked_up" in r:
        x["handled"] = r["picked_up"]
    if "battery_temp_c" in r:
        x["temperature"] = r["battery_temp_c"]
    if "battery_pct" in r:
        x["satiety"] = min(110.0, r["battery_pct"] + (10.0 if r.get("charging") else 0.0))
    if "interest" in r:
        x["interest"] = r["interest"]
    return x


def addons_on(app: App) -> bool:
    return on(app) and bool(app.settings.get("mind.stimulation.addons"))


def feed(app: App, source: str, readings: dict) -> bool:
    """For add-ons: another device's sensor readings (`source` names it, e.g. "body phone"; `readings` the raw numbers
    of ADDON: light_lux, proximity_cm, accel_x/y/z, battery_pct...). Each becomes its physical analogue on the body
    map, felt at the next minute's tick (kept in memory only), and the numbers go to open dashboards at once as
    {"t": "senses", "source", "readings", "channels", "at"} for the being's senses. Call it as often as the device
    reads (the page gets at most 5 a second). False, with nothing done, when Brain, its body
    (mind.stimulation.on) or mind.stimulation.addons is off, or none of the readings is one it knows."""
    if not addons_on(app) or not isinstance(readings, dict):
        return False
    src = str(source or "").strip()[:30]
    src = src if SOURCE.match(src) else "another device"
    t = time.time()
    with _fed_lock:
        fed = _fed.setdefault(app, {})
        x = translate(readings, (fed.get("heading") or {}).get("x"))
        if not x:
            return False
        for name, val in x.items():
            was = fed.get(name)
            peak = max(val, float(was["peak"])) if was and t - was["t"] < FED_S else val  # phasic: the strongest
            fed[name] = {"x": val, "peak": peak, "t": t, "src": src}
    for name, at in JOLT_AT.items():  # something sudden is felt at once (0.8.14)
        if x.get(name, 0.0) >= at:
            jolt(app, JOLT_KINDS[name])
    key = (id(app), src)
    live = getattr(app, "live", None)
    if live is not None and time.monotonic() - _live_at.get(key, 0.0) >= LIVE_S:
        _live_at[key] = time.monotonic()
        try:
            live.push({"t": "senses", "source": src, "readings": {k: round(v, 3) for k, v in _ok(readings).items()},
                       "channels": {k: round(v, 3) for k, v in x.items()}, "at": round(t, 1)})  # fmt: skip
        except Exception:
            pass
    return True


def _devices(app: App, t: float, x: dict, broken: dict) -> None:
    """The fed channels into this tick: a phasic one at its strongest since the last tick, a tonic one its latest."""
    if not addons_on(app):
        return
    with _fed_lock:
        for name, r in (_fed.get(app) or {}).items():
            if t - r["t"] >= FED_S or name not in CHANNELS:
                continue
            x[name] = float(r["peak"] if CHANNELS[name].phasic else r["x"])
            r["peak"] = r["x"]
            if name in ADDON_PAIN:
                broken[name] = ADDON_PAIN[name](x[name])


def _webcam(app: App, x: dict) -> None:
    """(0.9.0, face.light_sense) With no device's light fed in (an add-on's lux, which wins), the camera's smoothed
    level (Face.light_level, 0..1) stands in for brightness as WEBCAM_SCALE x level: a rough 0 dark .. 2 "a room",
    since a webcam adjusts its exposure. A number only, from memory."""
    if "brightness" in x:
        return
    face = app.modules.get("face") if hasattr(app, "modules") else None
    try:
        level = face.light_level() if face is not None else None
    except Exception:
        level = None
    if level is not None:
        x["brightness"] = WEBCAM_SCALE * float(level)


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


def jolt(app: App, kind: str, strength: float = 1.0) -> bool:
    """An orienting jolt (a pickup, something close, a loud room): arousal at once, and the workspace looks now. For
    add-ons and senses. False, with nothing done, when it's off, the kind isn't a short word, or it jolted lately."""
    if not on(app) or not app.settings.get("mind.stimulation.jolt") or not KIND.match(str(kind or "")):
        return False
    t = time.time()
    x = max(0.0, min(1.0, float(strength)))
    with _fed_lock:
        js = _jolts.setdefault(app, {})
        was = js.get(kind)
        if was and t - was["t"] < JOLT_GAP_S:
            return False
        js[kind] = {"t": t, "x": x}
    try:
        from kurooto.mind import workspace

        workspace.cycle(app, force=True)
    except Exception:  # noqa: S110 (the jolt is felt all the same)
        pass
    app.events.emit("mind_jolt", kind=kind)
    return True


def arousal(app: App) -> float:
    """The body's arousal now, 0..1: the minute's reading, or a recent jolt fading with PHASIC_TAU_S if higher."""
    if not on(app):
        return 0.0
    base = float(state(app).get("arousal") or 0.0)
    t = time.time()
    with _fed_lock:
        js = list((_jolts.get(app) or {}).values())
    j = max((v["x"] * math.exp(-max(0.0, t - v["t"]) / PHASIC_TAU_S) for v in js), default=0.0)
    return round(max(0.0, min(1.0, max(base, j))), 4)


def forget(app: App) -> None:
    (app.paths.state / FILE).unlink(missing_ok=True)
    with _fed_lock:
        _fed.pop(app, None)
        _jolts.pop(app, None)
