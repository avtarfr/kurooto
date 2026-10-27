"""Voice ID's numbers (0.8.10): the speaker model, the owner's template, its calibrated thresholds and the decision.

What "training" is here, honestly: no neural network is trained or fine-tuned. A pretrained speaker-embedding model
(CAM++, 3D-Speaker, Apache-2.0; ONNX by k2-fsa/sherpa-onnx, Apache-2.0) turns a stretch of speech into a vector (512
numbers for campplus-en, 192 for campplus-multi). Training builds the owner's template, the normalised mean of his
sample vectors, and calibrates his thresholds: each sample is scored against the mean of the others (leave-one-out)
and compared with about 1,750 impostor vectors that ship with Kurooto (computed from LibriSpeech's dev and test
speakers, CC BY 4.0; no audio ships). A classifier on top (logistic regression, SVM, PLDA) was considered and not
used: with 12 to 60 samples it overfits to the enrolment's conditions and is harder to calibrate than a cosine
against a centroid.

    Embedder     fbank (kaldi-native-fbank, 80 bins) + the ONNX model on the processor, read from its metadata
    calibrate()  outliers out, the template, held-out genuine scores, impostor scores, thresholds for long and short
                 turns, a grade, the manual override
    decide()     owner / unsure / guest from a score (and a short reply right after the owner's turn: carry)
    Verifier     holds the template in memory; check(pcm) -> Verdict
    Adapter      improving over time (voice.speaker_id.adapt, off by default): only very confident long turns, a
                 quarter of the weight at most, a drift guard, undo

The vector maths is plain Python (Kurooto itself doesn't depend on numpy; a few thousand dot products take tens of
milliseconds). Only the Embedder needs numpy and onnxruntime, from Voice's own packages (parts.py). Audio is never
written anywhere, and a score is never logged or put on the live stream: the decision word only."""

from __future__ import annotations

import json
import math
import struct
import threading
from array import array
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from operator import mul
from pathlib import Path

OWNER, UNSURE, GUEST = "owner", "unsure", "guest"
NOT_OWNER = (GUEST, UNSURE)
WORDS = {OWNER: "you", UNSURE: "unsure", GUEST: "someone else"}
SHORT_S = 2.5  # a turn with less speech than this uses the short thresholds
FAR = {"relaxed": 0.01, "normal": 0.002, "strict": 0.0}  # the target false-accept rate per strictness
CLAMP = (0.30, 0.85)
OVERRIDE = (0.30, 0.95)  # voice.speaker_id.threshold is held to this: a setting can't make a stranger "you"
MARGIN_MAX = 0.20  # the "not sure" band is at most this wide (a short reply right after you carries from its bottom)
STRICT_PAD = 0.03
MIN_SAMPLES = 12
MIN_CONDS = 3
NEED_CONDS = ("normal", "calls")
KIND_FULL, KIND_3S, KIND_15 = 0, 1, 2
ADAPT_ABOVE = 0.08  # adapt takes a turn only this far above accept_long
ADAPT_WEIGHT = 0.25
DRIFT_MIN = 0.95
BANK_MAGIC = b"KUROOTO-VOICEID-BANK 1\n"

Vec = Sequence[float]


# ------------------------------------------------------------------------------------------- vector maths
def dot(a: Vec, b: Vec) -> float:
    return sum(map(mul, a, b))


def normalize(v: Vec) -> list[float]:
    n = math.sqrt(dot(v, v))
    return [x / n for x in v] if n > 0 else [float(x) for x in v]


def mean(vs: Sequence[Vec]) -> list[float]:
    k = len(vs)
    return [s / k for s in map(math.fsum, zip(*vs, strict=True))]


def cos(a: Vec, b: Vec) -> float:
    na, nb = math.sqrt(dot(a, a)), math.sqrt(dot(b, b))
    return dot(a, b) / (na * nb) if na > 0 and nb > 0 else 0.0


def quantile(xs: Sequence[float], q: float) -> float:
    """Linear interpolation between the closest ranks (numpy's default)."""
    s = sorted(xs)
    if not s:
        return 0.0
    pos = (len(s) - 1) * min(1.0, max(0.0, q))
    lo = math.floor(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def median(xs: Sequence[float]) -> float:
    return quantile(xs, 0.5)


def to_b64(v: Vec) -> str:
    import base64

    return base64.b64encode(struct.pack(f"<{len(v)}e", *v)).decode()


def from_b64(s: str) -> list[float]:
    import base64

    raw = base64.b64decode(s)
    return list(struct.unpack(f"<{len(raw) // 2}e", raw))


# ------------------------------------------------------------------------------------------ thresholds
@dataclass
class Band:
    accept: float
    unsure: float


@dataclass
class Thresholds:
    long: Band
    short: Band

    def pick(self, speech_s: float) -> Band:
        return self.short if speech_s < SHORT_S else self.long

    def to_dict(self) -> dict:
        r = lambda x: round(float(x), 4)  # noqa: E731
        return {
            "long": {"accept": r(self.long.accept), "unsure": r(self.long.unsure)},
            "short": {"accept": r(self.short.accept), "unsure": r(self.short.unsure)},
        }

    @classmethod
    def from_dict(cls, d: dict) -> Thresholds:
        lo, sh = d.get("long") or {}, d.get("short") or {}
        return cls(
            Band(float(lo.get("accept", 0.5)), float(lo.get("unsure", 0.45))),
            Band(float(sh.get("accept", 0.5)), float(sh.get("unsure", 0.45))),
        )


def margin_of(margin: float) -> float:
    """voice.speaker_id.margin, held to 0..MARGIN_MAX (a wide band would let almost anyone carry a short reply)."""
    try:
        m = float(margin)
    except (TypeError, ValueError):
        return 0.05
    return min(MARGIN_MAX, max(0.0, m)) if math.isfinite(m) else 0.05


def band(impostors: Sequence[float], strictness: str, margin: float) -> Band:
    """accept: the impostor quantile at the target false-accept rate (strict: above every impostor), clamped;
    unsure: the lower of the impostors' 99th percentile and accept - margin."""
    imp = list(impostors) or [0.0]
    if strictness == "strict":
        accept = max(imp) + STRICT_PAD
    else:
        accept = quantile(imp, 1 - FAR.get(strictness, FAR["normal"]))
    accept = min(CLAMP[1], max(CLAMP[0], accept))
    unsure = min(quantile(imp, 0.99), accept - margin_of(margin))
    return Band(accept, min(unsure, accept - 1e-6))


def derive(i_long: Sequence[float], i_short: Sequence[float], strictness: str, margin: float) -> Thresholds:
    return Thresholds(band(i_long, strictness, margin), band(i_short, strictness, margin))


def override(t: Thresholds, threshold: float, margin: float) -> Thresholds:
    """voice.speaker_id.threshold > 0 replaces accept, long and short alike, held to OVERRIDE (0.30 to 0.95: below
    that most strangers would pass)."""
    try:
        th = float(threshold or 0)
    except (TypeError, ValueError):
        th = 0.0
    if not math.isfinite(th) or th <= 0:
        return t
    th = min(OVERRIDE[1], max(OVERRIDE[0], th))
    b = Band(th, th - max(1e-6, margin_of(margin)))
    return Thresholds(b, Band(b.accept, b.unsure))


def frr(genuine: Sequence[float], accept: float) -> float:
    g = list(genuine)
    return sum(1 for x in g if x < accept) / len(g) if g else 0.0


# ------------------------------------------------------------------------------------------ the bank
@dataclass
class Bank:
    """Impostor vectors (L2-normalised) with their kind: 0 a whole utterance, 1 a 3 s crop, 2 a 1.5 s crop."""

    meta: dict
    kinds: bytes
    rows: list = field(default_factory=list)  # array("f") each

    def scores(self, c: Vec, kinds: tuple[int, ...]) -> list[float]:
        return [dot(r, c) for r, k in zip(self.rows, self.kinds, strict=True) if k in kinds]


def write_bank(path: Path, rows: Sequence[Vec], kinds: Sequence[int], meta: dict) -> None:
    """The bank's file: a magic line, one line of JSON (dim, rows, kinds, model_sha256, source), the kinds as bytes,
    then the vectors as little-endian float16 (tools/voiceid_bank.py writes it)."""
    dim = len(rows[0])
    head = {**meta, "dim": dim, "rows": len(rows), "kinds": [list(kinds).count(k) for k in (0, 1, 2)]}
    with open(path, "wb") as f:
        f.write(BANK_MAGIC + json.dumps(head, sort_keys=True).encode() + b"\n" + bytes(kinds))
        for r in rows:
            f.write(struct.pack(f"<{dim}e", *r))


def read_bank(path: Path) -> Bank | None:
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return None
    if not raw.startswith(BANK_MAGIC):
        return None
    rest = raw[len(BANK_MAGIC) :]
    line, _, body = rest.partition(b"\n")
    try:
        meta = json.loads(line)
        dim, n = int(meta["dim"]), int(meta["rows"])
    except (ValueError, KeyError, TypeError):
        return None
    kinds, data = body[:n], body[n:]
    if len(kinds) != n or len(data) != n * dim * 2:
        return None
    rows = [array("f", struct.unpack_from(f"<{dim}e", data, i * dim * 2)) for i in range(n)]
    return Bank(meta, kinds, rows)


def bank_path(model: str) -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "voiceid" / f"impostors-{model}.bin"


# ----------------------------------------------------------------------------------------- calibrate
CONDITION_WORDS = {
    "normal": "your normal voice",
    "quiet": "a quiet voice",
    "far": "far from the microphone",
    "noise": "with noise around you",
    "calls": "short requests",
    "free": "free speech",
    "other": "added later",
}


def _times(rate: float) -> str:
    k = round(rate * 10)
    return f"{k} time{'s' if k != 1 else ''} in 10"


def calibrate(
    samples: Sequence[dict],
    bank: Bank,
    synthetic: Sequence[Vec] = (),
    strictness: str = "normal",
    margin: float = 0.05,
    threshold: float = 0.0,
) -> dict:
    """samples: [{"e": full-utterance vector, "s": its 1.5 s crop's vector, "cond": its condition}], normalised.
    Raises ValueError with a sentence when there aren't enough. Returns the template's numbers: centroid,
    thresholds (after any override), calibrated (before it), report, kept (indices) and genuine scores."""
    n = len(samples)
    if n < MIN_SAMPLES:
        raise ValueError(f"I need at least {MIN_SAMPLES} samples to build your voice print; I have {n}.")
    E = [list(s["e"]) for s in samples]
    total = [math.fsum(col) for col in zip(*E, strict=True)]

    # 1. outliers: leave-one-out against the rest; at most 10% go
    def loo(i: int, kept_total: list[float], k: int) -> list[float]:
        return normalize([(t - x) / (k - 1) for t, x in zip(kept_total, E[i], strict=True)])

    g = [dot(E[i], loo(i, total, n)) for i in range(n)]
    med = median(g)
    mad = median([abs(x - med) for x in g])
    floor = med - 3 * 1.4826 * mad
    out = sorted((i for i in range(n) if g[i] < floor and g[i] < 0.30), key=lambda i: g[i])[: max(0, n // 10)]
    kept = [i for i in range(n) if i not in out]
    dropped_by: dict[str, int] = {}
    for i in out:
        c = samples[i].get("cond") or "other"
        dropped_by[c] = dropped_by.get(c, 0) + 1

    # 2. the template
    k = len(kept)
    ktotal = [math.fsum(E[i][d] for i in kept) for d in range(len(total))]
    centroid = normalize([x / k for x in ktotal])

    # 3. held-out genuine scores (each sample against the template without it)
    g_long, g_short, by_cond = [], [], {}
    for i in kept:
        c_i = loo(i, ktotal, k)
        gl = dot(E[i], c_i)
        g_long.append(gl)
        if samples[i].get("s"):
            g_short.append(dot(samples[i]["s"], c_i))
        by_cond.setdefault(samples[i].get("cond") or "other", []).append(gl)

    # 4. impostors
    i_long = bank.scores(centroid, (KIND_FULL, KIND_3S))
    i_short = bank.scores(centroid, (KIND_15,))
    syn = [dot(normalize(t), centroid) for t in synthetic]
    i_long, i_short = i_long + syn, i_short + syn

    # 5. thresholds
    calibrated = derive(i_long, i_short or i_long, strictness, margin)
    t = override(calibrated, threshold, margin)

    # 6. grade
    fl, fs = frr(g_long, t.long.accept), frr(g_short, t.short.accept) if g_short else 0.0
    frr_by = {c: round(frr(v, t.long.accept), 3) for c, v in by_cond.items()}
    headroom = median(g_long) - t.long.accept
    if fl <= 0.05 and fs <= 0.15 and headroom >= 0.12:
        grade = "good"
    elif fl <= 0.15:
        grade = "fair"
    else:
        grade = "weak"
    advice = ""
    if grade != "good" and frr_by:
        worst = max(frr_by, key=lambda c: (frr_by[c], -len(by_cond[c])))
        if frr_by[worst] > 0:
            advice = (
                f"{CONDITION_WORDS.get(worst, worst).capitalize()} turns you away {_times(frr_by[worst])}: add "
                f"{max(2, min(5, round(frr_by[worst] * 10)))} more there."
            )
        elif fs > 0.15:
            advice = "Short turns are turned away often: add a few more short requests."
        else:
            advice = "Your samples are close to strangers' voices: add more in a quiet room, at your usual distance."
    if out:
        where = ", ".join(f"{v} from '{CONDITION_WORDS.get(c, c)}'" for c, v in dropped_by.items())
        many = "s" if len(out) != 1 else ""
        dropped_line = f"{len(out)} sample{many} ({where}) didn't sound like the rest and weren't used."
    else:
        dropped_line = ""
    report = {
        "n": n,
        "used": k,
        "dropped": len(out),
        "dropped_by_cond": dropped_by,
        "dropped_line": dropped_line,
        "grade": grade,
        "advice": advice,
        "frr_long": round(fl, 3),
        "frr_short": round(fs, 3),
        "frr_by_cond": frr_by,
        "median_genuine": round(median(g_long), 3),
        "bank_rows": len(bank.rows),
        "bank_pass_long": sum(1 for x in i_long if x >= t.long.accept),
        "bank_pass_short": sum(1 for x in i_short if x >= t.short.accept),
        "synthetic": len(syn),
        "synthetic_pass": sum(1 for x in syn if x >= t.long.accept),
        "synthetic_max": round(max(syn), 3) if syn else None,
        "strictness": strictness,
        "override": float(threshold or 0) > 0,
        "histogram": histogram(g_long, i_long),
    }
    return {
        "centroid": centroid,
        "thresholds": t,
        "calibrated": calibrated,
        "report": report,
        "kept": kept,
        "genuine": {"long": [round(x, 4) for x in g_long], "short": [round(x, 4) for x in g_short]},
    }


def histogram(genuine: Sequence[float], impostors: Sequence[float], bins: int = 24) -> dict:
    """Counts per score bin, for the page's picture (numbers only)."""
    lo, hi = -0.2, 1.0
    w = (hi - lo) / bins

    def count(xs: Sequence[float]) -> list[int]:
        out = [0] * bins
        for x in xs:
            out[min(bins - 1, max(0, int((x - lo) / w)))] += 1
        return out

    return {"lo": lo, "hi": hi, "genuine": count(genuine), "impostor": count(impostors)}


# --------------------------------------------------------------------------------------------- decide
@dataclass
class Verdict:
    decision: str  # owner | unsure | guest
    why: str
    score: float | None = None  # for the page's test only: never logged or on the live stream
    speech_s: float = 0.0
    short: bool = False
    carried: bool = False

    @property
    def word(self) -> str:
        return WORDS.get(self.decision, self.decision)

    def public(self) -> dict:
        """What may travel (the live stream, events): no score."""
        return {"decision": self.decision, "who": self.word, "why": self.why}


@dataclass
class Ctx:
    portal_session: int = 0
    last_owner_at: float | None = None
    last_owner_session: int = -1
    now: float = 0.0
    voices: int | None = None


def decide(
    score: float | None,
    t: Thresholds | None,
    speech_s: float,
    ctx: Ctx | None = None,
    *,
    min_speech_s: float = 1.0,
    carry: bool = True,
    carry_s: float = 15,
    strict: bool = False,
    missing: str = "",
) -> Verdict:
    """missing: why there's nothing to score against ("no voice print", "locked", "model failed"): unsure."""
    ctx = ctx or Ctx()
    if missing or t is None or score is None:
        return Verdict(UNSURE, missing or "no voice print", None, speech_s)
    if ctx.voices is not None and ctx.voices >= 2:
        return Verdict(UNSURE, "two voices", score, speech_s)
    short = speech_s < SHORT_S
    b = t.pick(speech_s)
    if speech_s < min_speech_s:
        if (
            carry
            and not strict
            and ctx.last_owner_at is not None
            and ctx.last_owner_session == ctx.portal_session
            and ctx.now - ctx.last_owner_at <= carry_s
            and score >= b.unsure
        ):
            return Verdict(OWNER, "a short reply right after you", score, speech_s, short, carried=True)
        return Verdict(UNSURE, "too short to tell", score, speech_s, short)
    if score >= b.accept:
        return Verdict(OWNER, "your voice", score, speech_s, short)
    if score >= b.unsure:
        return Verdict(UNSURE, "not sure it was you", score, speech_s, short)
    return Verdict(GUEST, "someone else", score, speech_s, short)


# ------------------------------------------------------------------------------------------ the model
class Embedder:
    """CAM++ (or another 3D-Speaker model) through onnxruntime on the processor, never the GPU. Its front end is read
    from the model's own metadata (sample_rate, normalize_samples, feature_normalize_type, output_dim), not
    hard-coded. Loaded once; numpy, onnxruntime and kaldi_native_fbank come from Voice's packages."""

    def __init__(self, model_path: Path, threads: int = 2):
        import kaldi_native_fbank as knf
        import numpy as np
        import onnxruntime as ort

        self.np, self.knf = np, knf
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = int(threads)
        opts.inter_op_num_threads = 1
        self.s = ort.InferenceSession(str(model_path), sess_options=opts, providers=["CPUExecutionProvider"])
        meta = self.s.get_modelmeta().custom_metadata_map or {}
        self.meta = dict(meta)
        self.rate = int(meta.get("sample_rate", 16000))
        if self.rate != 16000:
            raise ValueError(f"the speaker model works at {self.rate} Hz; Voice ID needs 16000")
        self.normalize_samples = str(meta.get("normalize_samples", "1")) != "0"
        self.global_mean = str(meta.get("feature_normalize_type", "global-mean")) == "global-mean"
        self.dim = int(meta.get("output_dim", 0) or 0)
        self.input = self.s.get_inputs()[0].name
        self._lock = threading.Lock()

    def features(self, pcm: bytes):
        np, knf = self.np, self.knf
        x = np.frombuffer(pcm, dtype="<i2").astype("float32")
        if self.normalize_samples:
            x = x / 32768.0
        opts = knf.FbankOptions()
        opts.frame_opts.dither = 0
        opts.frame_opts.snip_edges = True
        opts.frame_opts.samp_freq = self.rate
        opts.mel_opts.num_bins = 80
        fb = knf.OnlineFbank(opts)
        fb.accept_waveform(self.rate, x.tolist())
        fb.input_finished()
        frames = np.array([fb.get_frame(i) for i in range(fb.num_frames_ready)], dtype="float32")
        if self.global_mean and len(frames):
            frames = frames - frames.mean(axis=0, keepdims=True)
        return frames

    def embed(self, pcm: bytes) -> list[float]:
        """16 kHz mono int16 sound -> its L2-normalised vector. The sound isn't kept or written anywhere."""
        feats = self.features(pcm)
        if not len(feats):
            raise ValueError("too little sound to embed")
        with self._lock:
            out = self.s.run(None, {self.input: feats[None, :, :]})[0]
        v = self.np.asarray(out, dtype="float32").reshape(-1)
        return normalize(v.tolist())


# -------------------------------------------------------------------------------------------- verifier
class Verifier:
    """The owner's template in memory and the decision for one turn. `embed` is the Embedder's (or a test's fake)."""

    def __init__(self, embed: Callable[[bytes], Sequence[float]] | None, centroid: Vec | None, t: Thresholds | None):
        self.embed = embed
        self.centroid = list(centroid) if centroid else None
        self.t = t
        self.last: list[float] | None = None  # the last turn's vector, for the adapter only; dropped after

    def score(self, pcm: bytes) -> float:
        assert self.embed is not None and self.centroid is not None
        e = list(self.embed(pcm))
        self.last = e
        return dot(e, self.centroid)

    def check(self, pcm: bytes, speech_s: float, ctx: Ctx, missing: str = "", **rules) -> Verdict:
        self.last = None
        if missing or self.embed is None or self.centroid is None or self.t is None:
            return decide(None, None, speech_s, ctx, missing=missing or "no voice print", **rules)
        try:
            s = self.score(pcm)
        except Exception:
            return decide(None, None, speech_s, ctx, missing="model failed", **rules)
        return decide(s, self.t, speech_s, ctx, **rules)


# --------------------------------------------------------------------------------------------- adapter
def template_centroid(tpl: dict) -> list[float]:
    """The enrolment's centroid, with the adapted turns at a quarter of the weight at most."""
    enrolled = tpl.get("centroid_enrolled") or tpl.get("centroid")
    base = from_b64(enrolled) if isinstance(enrolled, str) else list(enrolled)
    adapted = [from_b64(a["e"]) for a in tpl.get("adapted") or []]
    if not adapted:
        return normalize(base)
    m = mean(adapted)
    return normalize([(1 - ADAPT_WEIGHT) * b + ADAPT_WEIGHT * a for b, a in zip(base, m, strict=True)])


class Adapter:
    """Improving over time (voice.speaker_id.adapt): turns it was very sure were the owner refine his template
    slowly. Never from a carried or unsure turn, never two voices; capped per day and in all (oldest replaced); a
    drift guard; undo today or all. Changes the template dict in place; the caller saves it."""

    def __init__(self, bank: Bank | None, strictness: str = "normal", margin: float = 0.05, threshold: float = 0.0):
        self.bank, self.strictness, self.margin, self.threshold = bank, strictness, margin, threshold

    def consider(
        self, tpl: dict, e: Vec, v: Verdict, voices: int | None, today: str, per_day: int = 10, cap: int = 40
    ) -> tuple[bool, str]:
        t = Thresholds.from_dict(tpl.get("thresholds") or {})
        if v.decision != OWNER or v.carried or v.why != "your voice":
            return False, "not a sure turn"
        if v.score is None or v.score < t.long.accept + ADAPT_ABOVE:
            return False, "not sure enough"
        if v.speech_s < 2:
            return False, "too short"
        if voices is not None and voices >= 2:
            return False, "two voices"
        adapted = list(tpl.get("adapted") or [])
        if sum(1 for a in adapted if a.get("day") == today) >= per_day:
            return False, "enough for today"
        new = [*adapted, {"e": to_b64(normalize(e)), "day": today}][-max(1, int(cap)) :]
        trial = {**tpl, "adapted": new}
        c_new = template_centroid(trial)
        c_enrolled = normalize(from_b64(tpl["centroid_enrolled"]))
        if dot(c_new, c_enrolled) < DRIFT_MIN:
            tpl["drift_stopped"] = True
            return False, "drift"
        tpl["adapted"] = new
        tpl["drift_stopped"] = False
        self.rederive(tpl, c_new)
        return True, "taken"

    def rederive(self, tpl: dict, c: Vec | None = None) -> None:
        """The template's centroid and thresholds for its current adapted turns (impostors scored again)."""
        c = c if c is not None else template_centroid(tpl)
        tpl["centroid"] = to_b64(c)
        if self.bank is not None and self.bank.rows:
            calibrated = derive(
                self.bank.scores(c, (KIND_FULL, KIND_3S)), self.bank.scores(c, (KIND_15,)), self.strictness, self.margin
            )
            tpl["calibrated"] = calibrated.to_dict()
            tpl["thresholds"] = override(calibrated, self.threshold, self.margin).to_dict()

    def undo(self, tpl: dict, which: str, today: str) -> int:
        """which: "today" drops today's learned turns, "all" every one. How many went."""
        adapted = list(tpl.get("adapted") or [])
        keep = [a for a in adapted if a.get("day") != today] if which == "today" else []
        tpl["adapted"] = keep
        tpl["drift_stopped"] = False
        self.rederive(tpl)
        return len(adapted) - len(keep)
