"""How Brain reads how you're doing (0.8.0 stage 04, shadow mode): statistics on your own behaviour, adjusted for
what the calendar asks of you, and nothing else. It drives nothing yet: it's computed, logged and shown in /mood.

Each day has a few numbers (signals): when you woke, when you slept, snoozes, study minutes, how fast you answered
(banded), deadlines moved, classes attended, the tone of what you wrote. For each, the last 28 days are fitted to what
the calendar asked (deadlines due within 72 hours, exam weight, class hours, exam season, weekday); the difference
between what happened and what the calendar explains is the residual, and a robust z (against the median absolute
deviation) says how unusual it is. A signal with |z| > 2 is a vote; sleep, wake and snoozes together are one vote (the
sleep cluster), and a CUSUM alarm on sleep adds that vote. A read counts only with 3 or more votes on 2 days running (or
your own answer). The label: steady, stretched, low or buoyant. Confidence is learned from your answers (isotonic) and
stays unknown until there are 50 of them. Accuracy under 60% over the last 20 answers switches the read off.

Pure functions over plain data; the daemon part is mind/signals.py and the view mind/mood.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from kurooto.mind import stats

PART = "read"  # its switch: mind.read.on

WINDOW = 28  # days fitted
RIDGE = 1.0
Z_VOTE = 2.0
MIN_VOTES = 3
MIN_ANSWERS = 50  # confirmed answers before confidence is a number
GATE_WINDOW = 20
GATE_MIN_ACC = 0.60
MIN_HISTORY = 10  # days before a signal is read at all

SIGNALS = (
    "wake_min",
    "sleep_min",
    "snoozes",
    "study_min",
    "reply_band",
    "deadline_moves",
    "classes_attended",
    "class_skip_h",
    "tone_mean",
)
LOAD_SIGNALS = ("load_deadlines_w", "load_deadlines_n", "load_class_h", "load_exam")  # what the day asked (signals.py)
SLEEP_CLUSTER = ("sleep_min", "wake_min", "snoozes")
# +1: a higher number reads as more stretched or low (later, more snoozes, more moves, slower); -1: a lower one does
DIRECTION = {
    "wake_min": 1, "sleep_min": 1, "snoozes": 1, "study_min": -1, "reply_band": 1, "deadline_moves": 1,
    "classes_attended": -1, "class_skip_h": 1, "tone_mean": -1,
}  # fmt: skip
LABELS = ("steady", "stretched", "low", "buoyant")


@dataclass
class Day:
    """One day: its date, the calendar's load, and the signals that were measured (missing ones are left out)."""

    day: str
    load: dict = field(
        default_factory=dict
    )  # deadlines_w (72 h, exam 3, assignment 1), deadlines_n, class_h, exam_season, weekday
    sig: dict = field(default_factory=dict)


def features(load: dict) -> list[float]:
    """The calendar's load as numbers: weighted and plain deadline counts, class hours, exam season, weekday."""
    wd = int(load.get("weekday", 0)) % 7
    return [
        float(load.get("deadlines_w", 0)), float(load.get("deadlines_n", 0)), float(load.get("class_h", 0)),
        1.0 if load.get("exam_season") else 0.0, *[1.0 if wd == i else 0.0 for i in range(1, 7)],
    ]  # fmt: skip


def explain(history: list[Day], today: Day, name: str) -> dict | None:
    """The residual and z of one signal today against the calendar-adjusted fit on the last WINDOW days before it;
    None when there isn't enough history or today's number is missing."""
    if name not in today.sig:
        return None
    rows = [d for d in history[-WINDOW:] if name in d.sig]
    if len(rows) < MIN_HISTORY:
        return None
    X = [features(d.load) for d in rows]
    y = [float(d.sig[name]) for d in rows]
    beta = stats.ridge(X, y, RIDGE)
    if beta is None:
        return None
    res = [yy - stats.predict(beta, x) for x, yy in zip(X, y, strict=True)]
    scale = stats.mad_scale(res)
    if scale < 1e-9:  # a flat signal: any change is unusual, so use the spread of the raw numbers instead
        scale = max(stats.mad_scale(y), 1e-3)
    resid = float(today.sig[name]) - stats.predict(beta, features(today.load))
    zs = [stats.robust_z(r, scale) for r in res]
    return {"residual": resid, "z": stats.robust_z(resid, scale), "series": zs}


@dataclass
class Read:
    day: str
    label: str
    votes: list  # [(signal or "sleep cluster", z)]
    n_votes: int
    strength: float  # the sum of |z| over the votes: what confidence is learned against
    evidence: dict  # signal -> z (every signal read, voting or not)


def read_day(history: list[Day], today: Day) -> Read:
    ev: dict = {}
    series: dict = {}
    for name in SIGNALS:
        e = explain(history, today, name)
        if e is not None:
            ev[name] = e["z"]
            series[name] = e["series"]
    votes: list = []
    sleep = [(n, ev[n]) for n in SLEEP_CLUSTER if n in ev and abs(ev[n]) > Z_VOTE]
    alarm = False
    if "sleep_min" in series:
        zs = series["sleep_min"] + [ev["sleep_min"]]
        alarm = (len(zs) - 1) in stats.cusum(zs, 0.5, 4.0)
    if sleep or alarm:
        z = max((v for _, v in sleep), key=abs) if sleep else ev.get("sleep_min", 0.0)
        votes.append(("sleep cluster", z))
    for name in ("study_min", "reply_band", "deadline_moves", "classes_attended", "tone_mean"):
        if name in ev and abs(ev[name]) > Z_VOTE:
            votes.append((name, ev[name]))
    net = sum(DIRECTION.get(n if n != "sleep cluster" else "sleep_min", 1) * (1 if z > 0 else -1) for n, z in votes)
    label = "steady"
    if votes and net > 0:
        study_down = any(n == "study_min" and z < 0 for n, z in votes)
        label = "low" if study_down else "stretched"
    elif votes and net < 0:
        label = "buoyant"
    return Read(
        today.day,
        label,
        votes,
        len(votes),
        round(sum(abs(z) for _, z in votes), 4),
        {k: round(v, 3) for k, v in ev.items()},
    )


def counts(yesterday: Read | None, today: Read, answer: str | None = None) -> bool:
    """Does the read count? 3 or more votes on 2 days running, or your own answer says so."""
    if answer in LABELS:
        return True
    return yesterday is not None and yesterday.n_votes >= MIN_VOTES and today.n_votes >= MIN_VOTES


def confidence(answers: list[tuple[float, bool]], strength: float) -> float | None:
    """From your confirmed answers (vote strength, was the read right): isotonic, None until MIN_ANSWERS of them."""
    if len(answers) < MIN_ANSWERS:
        return None
    f = stats.isotonic([a for a, _ in answers], [1.0 if ok else 0.0 for _, ok in answers])
    return None if f is None else round(f(strength), 3)


def accuracy_ok(answers: list[tuple[float, bool]]) -> bool:
    """False when the last GATE_WINDOW confirmed answers were right less than GATE_MIN_ACC of the time."""
    last = answers[-GATE_WINDOW:]
    if len(last) < GATE_WINDOW:
        return True
    return sum(1 for _, ok in last if ok) / len(last) >= GATE_MIN_ACC
