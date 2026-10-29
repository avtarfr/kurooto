"""Your face model: what "training" means here, honestly. No neural network is trained; YuNet and SFace are used as
they are. Training is three things done on this computer, in well under a second:

1. The template. Each accepted sample is SFace's 128 numbers. The template is their centroid, one per condition
   group: base (steps front to far), glasses, light. A group with fewer than 5 samples merges into base. Several
   centroids handle glasses on and off far better than one mean; score(x) = the best cosine against any of them.
2. The threshold. Your samples are scored held out (5-fold, stratified by step: each against a template built from
   the other four folds), and the bundled impostor faces are scored against the full template. The cut-off is picked
   for a false-accept rate (face.recognise.strictness) on the impostors, and never below OpenCV's published 0.363
   (chosen on LFW, real people). How often you'd be recognised at it (TAR) is measured on your held-out samples.
3. The grade. good, fair or weak, with advice ("add more samples in low light").

Learning over time (face.learn.on) adds confident samples to a small pool (weight 0.5, never replacing enrolled ones);
the threshold is still measured only against held-out enrolled samples, so learning can't grade its own homework.

Looks (0.9.0, face.looks.on, "Add this look"): a short capture of how you look today (hair up, a new beard) adds 7 to 10
enrolled samples with the step "look:<id>", their own condition group and so their own centroid. Before they're added,
look_check() refuses a look that isn't safe: its average must already count as the same person as your enrolment by
OpenCV's published 0.363 (or your "unsure" cut-off, if that's higher), and with the impostor set, the re-measured
cut-off must not leave your usual samples recognised less often. Learning alone can't do this: it only learns from
frames already well above the cut-off, so a look that scores "unsure" is never learned.

Why not a classifier or a fine-tune on top (yet): there's one identity and about 50 samples of it; a classifier on
128 numbers (you against the impostors) would mostly learn how made-up impostor faces differ from real ones; a
fine-tune of SFace would need torch and real impostor images we can't licence. If an evaluation on real held-out data
ever shows a classifier beating the centroid at the same false-accept rate, it can come behind its own switch.
"""

from __future__ import annotations

import secrets
import statistics
import time
from dataclasses import dataclass, field

from kurooto.core.biometric import calibrate, dot, mean_unit, pack, unpack

FLOOR = 0.363  # OpenCV's published SFace cosine threshold (its face_detect sample, chosen on LFW)
STRICTNESS = {"loose": (1e-2, 2.33), "normal": (1e-3, 3.09), "strict": (1e-4, 3.72)}  # false accepts per frame, z
MIN_GROUP = 5  # a condition group smaller than this merges into base
LEARN_WEIGHT = 0.5
FOLDS = 5
MODEL = "SFace 2021dec"
VERSION = 1
NOVEL = 0.97  # a learned frame must be less like every stored sample than this
EXTRA = ("near", "far", "glasses", "light")  # the steps that raise the grade
LOOK = "look:"  # (0.9.0) a look's samples have the step "look:<id>": their own group, so their own centroid
LOOKS_MAX = 6  # at most this many looks
LOOK_MIN = 7  # a look needs this many samples: each held-out fold still leaves MIN_GROUP of it to make its centroid
LOOK_TAR_DROP = 0.05  # (impostor set) a look whose re-measured cut-off drops your usual samples' TAR more is refused
WORDS = {
    "front": "looking straight at the camera",
    "left": "turned to your left",
    "right": "turned to your right",
    "up": "chin up",
    "down": "chin down",
    "near": "close to the camera",
    "far": "sitting back",
    "glasses": "glasses on or off",
    "light": "other light",
}


def group_of(step: str) -> str:
    return step if step in ("glasses", "light") or is_look(step) else "base"


def is_look(step: str) -> bool:
    return step.startswith(LOOK)


def _words(step: str) -> str:
    return "in an added look" if is_look(step) else WORDS.get(step, step)


@dataclass
class Sample:
    e: list[float]
    step: str
    at: float
    q: dict = field(default_factory=dict)  # blur and light, rounded: how good the sample was

    def to_json(self) -> dict:
        return {"e": pack(self.e), "step": self.step, "at": round(self.at), "q": self.q}

    @classmethod
    def from_json(cls, d: dict) -> Sample:
        return cls(unpack(d["e"]), str(d.get("step") or "front"), float(d.get("at") or 0), dict(d.get("q") or {}))


def centroids(samples: list[Sample], learned: list[Sample] | None = None) -> list[tuple[str, list[float]]]:
    groups: dict[str, list[Sample]] = {}
    for s in samples:
        groups.setdefault(group_of(s.step), []).append(s)
    for g in [g for g in groups if g != "base" and len(groups[g]) < MIN_GROUP]:
        groups.setdefault("base", []).extend(groups.pop(g))
    if not groups:
        return []
    enrolled = {g: mean_unit([s.e for s in ss]) for g, ss in groups.items()}
    vecs: dict[str, list[tuple[list[float], float]]] = {g: [(s.e, 1.0) for s in ss] for g, ss in groups.items()}
    for s in learned or []:  # each learned sample joins the group it's nearest
        g = max(enrolled, key=lambda k: dot(s.e, enrolled[k]))
        vecs[g].append((s.e, LEARN_WEIGHT))
    return [(g, mean_unit([v for v, _ in vw], [w for _, w in vw])) for g, vw in vecs.items()]


def score(x, cents: list[tuple[str, list[float]]]) -> float:
    return max((dot(x, c) for _, c in cents), default=-1.0)


def folds(samples: list[Sample], k: int = FOLDS) -> list[int]:
    """Stratified by step: each step's samples go round the folds in turn."""
    seen: dict[str, int] = {}
    out = []
    for s in samples:
        n = seen.get(s.step, 0)
        seen[s.step] = n + 1
        out.append(n % k)
    return out


def held_out(samples: list[Sample], k: int = FOLDS) -> list[tuple[str, float]]:
    """(step, score) for every sample against a template built without its fold."""
    fs = folds(samples, k)
    out = []
    for f in range(k):
        train = [s for s, g in zip(samples, fs, strict=True) if g != f]
        test = [s for s, g in zip(samples, fs, strict=True) if g == f]
        if not train or not test:
            continue
        cents = centroids(train)
        out += [(s.step, score(s.e, cents)) for s in test]
    return out


def train(
    samples: list[Sample],
    learned: list[Sample] | None,
    impostors: list[list[float]] | None,
    strictness: str = "normal",
    override: float = 0.0,
    targets: dict[str, int] | None = None,
) -> dict:
    """Centroids, the two cut-offs, how often you'd be recognised, the grade and advice (numbers and words only)."""
    far, z = STRICTNESS.get(strictness, STRICTNESS["normal"])
    cents = centroids(samples, learned)
    g = held_out(samples)
    genuine = [v for _, v in g]
    j = [score(i, cents) for i in impostors] if impostors else []
    th = calibrate(genuine, j, far, z, FLOOR, override)
    tar = sum(v >= th.hi for v in genuine) / len(genuine) if genuine else 0.0
    by_step: dict[str, list[float]] = {}
    for st, v in g:
        by_step.setdefault(st, []).append(v)
    tar_step = {st: (sum(v >= th.hi for v in vs), len(vs)) for st, vs in by_step.items()}
    counts: dict[str, int] = {}
    for s in samples:
        if not is_look(s.step):  # a look's samples are counted with the looks, not the steps
            counts[s.step] = counts.get(s.step, 0) + 1
    med_g = statistics.median(genuine) if genuine else 0.0
    med_j = statistics.median(j) if j else None
    targets = targets or {}
    extra_done = all(counts.get(st, 0) >= targets.get(st, 1) for st in EXTRA)
    if tar >= 0.95 and med_g - th.hi >= 0.15 and extra_done:
        grade = "good"
    elif tar >= 0.80:
        grade = "fair"
    else:
        grade = "weak"
    advice = []
    for st, (k, n) in tar_step.items():
        if n and k / n < 0.7 and is_look(st):
            advice.append(
                f"An added look: recognised in {k} of {n} held-out samples. Remove it and add it again facing the "
                "camera in steady light."
            )
        elif n and k / n < 0.7:
            advice.append(
                f"{_words(st).capitalize()}: recognised in {k} of {n} held-out samples. Add more samples {_words(st)}."
            )
    if med_j is not None and med_j > 0.25:
        advice.append("Your samples look alike to many other faces. Retake them in better light.")
    if not extra_done:
        missing = [WORDS[st] for st in EXTRA if counts.get(st, 0) < targets.get(st, 1)]
        advice.append("Add samples " + ", ".join(missing) + " to raise the grade (Add samples).")
    if th.method == "floor":
        advice.append("Calibrated without the impostor set: run the 'someone else' test.")
    report = {
        "samples": len(samples),
        "learned": len(learned or []),
        "per_step": counts,
        "tar": round(tar, 3),
        "tar_by_step": {st: [k, n] for st, (k, n) in tar_step.items()},
        "median_you": round(med_g, 3),
        "median_others": None if med_j is None else round(med_j, 3),
        "thresholds": th.as_dict(),
        "grade": grade,
        "advice": advice,
    }
    return {"centroids": cents, "thresholds": th, "grade": grade, "report": report}


def look_check(
    samples: list[Sample],
    learned: list[Sample] | None,
    new: list[Sample],
    impostors: list[list[float]] | None,
    strictness: str = "normal",
    override: float = 0.0,
) -> str:
    """Whether a look's new samples are safe to add to a template of `samples`: "" when they are, else the reason in
    plain words. A new centroid widens what's accepted as you; the threshold can only push back when there are
    impostors to measure, and the impostor set isn't always there (the floor), so the look must first be close to
    you as you enrolled: its average at least max(FLOOR, the current unsure cut-off) against the enrolment's own
    centroids (never another look's, so looks can't walk away from you one after another). Then, with impostors,
    the cut-off re-measured with the look must not leave your usual samples (held out, as enrolment measures them)
    recognised more than LOOK_TAR_DROP less often."""
    if len(new) < LOOK_MIN:
        return f"only {len(new)} clear samples (a look needs {LOOK_MIN})"
    before = train(samples, learned, impostors, strictness, override)
    th = before["thresholds"]
    enrolled = centroids([s for s in samples if not is_look(s.step)])  # never against another look: no drifting
    if score(mean_unit([s.e for s in new]), enrolled) < max(FLOOR, th.lo):
        return (
            "this look is too far from your face model to be sure it's you, and adding it would let other faces "
            "pass as you. Enrol again (Start over) if your look has changed for good"
        )
    after = train(samples + new, learned, impostors, strictness, override)
    th2 = after["thresholds"]
    if th2.hi < th.hi - 1e-9:  # can't happen with the maths as it is; kept so a change there can't loosen it
        return "adding it would lower the cut-off for recognising you"
    if impostors:
        old = [v for _, v in held_out(samples)]
        mine = [v for st, v in held_out(samples + new) if not is_look(st)]
        tar0 = sum(v >= th.hi for v in old) / len(old) if old else 0.0
        tar1 = sum(v >= th2.hi for v in mine) / len(mine) if mine else 0.0
        if tar1 < tar0 - LOOK_TAR_DROP:
            return (
                "this look is too close to other faces: to keep them out, the cut-off would rise so far that your "
                f"usual look would be recognised in {round(tar1 * 100)}% of samples instead of {round(tar0 * 100)}%"
            )
    return ""


class Template:
    """The decoded template: samples, learned samples, centroids and thresholds. Kept only sealed (TemplateStore)."""

    def __init__(self, model_sha: str):
        self.model_sha = model_sha
        self.samples: list[Sample] = []
        self.learned: list[Sample] = []
        self.cents: list[tuple[str, list[float]]] = []
        self.hi = FLOOR + 0.05
        self.lo = max(0.20, self.hi - 0.10)
        self.thresholds: dict = {}
        self.grade = ""
        self.report: dict = {}
        self.last_test: dict = {}
        self.baseline: dict = {}  # the front step's pitch, face height and light (for Add samples)
        self.gaze: dict = {}  # (0.8.17) Calibrate my eyes: h, v, yaw, pitch, n, at (gaze.py); never a picture
        self.looks: list[dict] = []  # (0.9.0) Add this look: {id, label, at, n}; the samples are in self.samples
        self.cameras: list[str] = []  # (0.9.2) the cameras its samples came from: names only (Face._camera_watch)
        self.use_looks = True  # (face.looks.on) off: the looks' centroids don't count (never stored)
        self.created = time.time()
        self.updated = self.created
        self.impostors_sha = ""
        self.from_store = False  # unsealed from the store (Face.template): saved again only while it's the current one

    # -------------------------------------------------------------------------------------------- stored
    def to_payload(self) -> dict:
        return {
            "version": VERSION,
            "model_sha256": self.model_sha,
            "created": round(self.created),
            "updated": round(self.updated),
            "samples": [s.to_json() for s in self.samples],
            "learned": [s.to_json() for s in self.learned],
            "centroids": [{"group": g, "e": pack(c)} for g, c in self.cents],
            "thresholds": {**self.thresholds, "hi": self.hi, "lo": self.lo, "impostors_sha": self.impostors_sha},
            "grade": self.grade,
            "report": self.report,
            "last_test": self.last_test,
            "baseline": self.baseline,
            "gaze": self.gaze,
            "looks": self.looks,
            "cameras": self.cameras,
        }

    @classmethod
    def from_payload(cls, d: dict) -> Template:
        t = cls(str(d.get("model_sha256") or ""))
        t.samples = [Sample.from_json(x) for x in d.get("samples") or []]
        t.learned = [Sample.from_json(x) for x in d.get("learned") or []]
        t.cents = [(str(c.get("group") or "base"), unpack(c["e"])) for c in d.get("centroids") or []]
        th = dict(d.get("thresholds") or {})
        t.hi = float(th.get("hi") or FLOOR + 0.05)
        t.lo = float(th.get("lo") or max(0.20, t.hi - 0.10))
        t.impostors_sha = str(th.get("impostors_sha") or "")
        t.thresholds = th
        t.grade = str(d.get("grade") or "")
        t.report = dict(d.get("report") or {})
        t.last_test = dict(d.get("last_test") or {})
        t.baseline = dict(d.get("baseline") or {})
        t.gaze = dict(d.get("gaze") or {})
        t.looks = [dict(x) for x in d.get("looks") or [] if isinstance(x, dict) and x.get("id")]
        t.cameras = [str(x) for x in d.get("cameras") or [] if x][-6:]
        t.created = float(d.get("created") or time.time())
        t.updated = float(d.get("updated") or t.created)
        return t

    def status(self) -> dict:
        """face.json: counts and dates only (the card and /face work with the keychain locked)."""
        per = {}
        for s in self.samples:
            if not is_look(s.step):
                per[s.step] = per.get(s.step, 0) + 1
        return {
            "enrolled": True,
            "samples": len(self.samples),
            "per_step": per,
            "learned": len(self.learned),
            "learned_at": [round(s.at) for s in self.learned][-30:],
            "grade": self.grade,
            "tar": self.report.get("tar"),
            "created": round(self.created),
            "trained": round(self.updated),
            "last_test_at": self.last_test.get("at"),
            "gaze_at": self.gaze.get("at"),  # (0.8.17) when your eyes were calibrated: a date, never the numbers
            "looks": len(self.looks),  # (0.9.0) how many looks were added: a count, never their labels
            "model": MODEL,
            "impostors": self.thresholds.get("method") == "impostors",
        }

    # ------------------------------------------------------------------------------------------ deciding
    def score(self, x) -> float:
        if not self.use_looks:  # stricter, never looser: a centroid fewer, the same cut-off
            return score(x, [(g, c) for g, c in self.cents if not is_look(g)])
        return score(x, self.cents)

    def classify(self, x) -> tuple[str, float]:
        s = self.score(x)
        return ("owner" if s >= self.hi else "unsure" if s >= self.lo else "stranger"), s

    # ---------------------------------------------------------------------------------------- training
    def retrain(
        self,
        impostors: list[list[float]] | None,
        impostors_sha: str = "",
        strictness: str = "normal",
        override: float = 0.0,
        targets: dict[str, int] | None = None,
    ) -> dict:
        out = train(self.samples, self.learned, impostors, strictness, override, targets)
        th = out["thresholds"]
        self.cents, self.hi, self.lo = out["centroids"], th.hi, th.lo
        self.thresholds = th.as_dict()
        self.impostors_sha = impostors_sha if impostors else ""
        self.grade, self.report = out["grade"], out["report"]
        self.updated = time.time()
        return self.report

    def learnable(self, x, margin: float) -> bool:
        """Confident (beats T_hi by `margin`) and new (less like every stored sample than NOVEL)."""
        if self.score(x) < self.hi + margin:
            return False
        return all(dot(x, s.e) < NOVEL for s in [*self.samples, *self.learned])

    def learn(self, x, at: float, cap: int) -> int:
        self.learned.append(Sample(list(x), "learned", at))
        while len(self.learned) > max(0, cap):
            self.learned.pop(0)  # the oldest learned one goes; enrolled samples are never replaced
        return len(self.learned)

    def undo_learn(self) -> bool:
        if not self.learned:
            return False
        self.learned.pop()
        return True

    def forget_learned(self) -> int:
        n = len(self.learned)
        self.learned = []
        return n

    # ------------------------------------------------------------------------------------------- looks
    def add_look(self, label: str, new: list[Sample], at: float) -> dict:
        """Adds a look's samples as enrolled samples of their own step (look_check first; retrain after)."""
        lid = secrets.token_hex(4)
        while any(x["id"] == lid for x in self.looks):
            lid = secrets.token_hex(4)
        for s in new:
            self.samples.append(Sample(list(s.e), LOOK + lid, s.at, dict(s.q)))
        look = {"id": lid, "label": label, "at": round(at), "n": len(new)}
        self.looks.append(look)
        return look

    def remove_look(self, lid: str) -> dict | None:
        """Takes a look and its samples out (retrain after); None when there's no such look."""
        look = next((x for x in self.looks if x.get("id") == lid), None)
        if look is None:
            return None
        self.looks = [x for x in self.looks if x is not look]
        self.samples = [s for s in self.samples if s.step != LOOK + lid]
        return look
