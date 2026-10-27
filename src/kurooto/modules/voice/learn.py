"""The gate learning from its own mistakes (0.8.13; voice.listen.learn_nightly, on by default).

Each turn the gate let through (addressed) is kept in memory until it's known how it went:

    told off right after it ("stop", "not you", "I wasn't talking to you" ... gate.TOLD_OFF)   -> a misfire (0)
    the same voice carried on talking to Kurooto in the same conversation                      -> it went well (1)
    anything else (the conversation closed on silence or on chatter)                           -> not kept: unknown

A labelled turn is written as one row to <state>/voice/gate-turns.jsonl: only the deciding rule and flags about the
moment (how its name was said, how many voices, Voice ID's decision word and score, seconds since chatter, faces in
view, whether the careful calls applied) and the day. Never words, never sound, never a vector. ROWS_MAX rows are kept.

Every night (daily NIGHT_AT, after Kurooto's own nightly fine-tune) a small logistic regression is fitted to the rows,
plain Python, class-balanced, with an L2 penalty, and saved to <state>/voice/gate-model.json (weights and counts). It
acts only with MIN_ROWS rows or more and MIN_EACH of each kind, and then only as a veto on borderline openings
(gate.borderline(): its name heard as a near miss, rule 7, the conversation going on, the local model's judgement) that
it thinks are to Kurooto with a chance below VETO_P. It can't stop its name said first with its own or a known spelling
("Kurooto, <request>"): that's the cap. Delete the two files (or turn learn_nightly off) to undo it."""

from __future__ import annotations

import datetime as dt
import json
import math
import threading
from pathlib import Path

ROWS_MAX = 2000
MIN_ROWS = 20  # it acts only once it has this many labelled turns
MIN_EACH = 3  # and at least this many misfires and this many good turns
VETO_P = 0.25  # a borderline opening is vetoed when the model gives it less than this chance of being to Kurooto
NIGHT_AT = "daily 04:10"  # while you sleep: after the mind's nightly fine-tune (03:40)

RULES = (
    "its name",
    "it follows the conversation",
    "the conversation goes on",
    "the local model",
    "an answer to what it said",
    "right after it was called",
)
FEATURES = (
    "bias",
    *(f"rule: {r}" for r in RULES),
    "name exact or known",
    "name near miss",
    "name last",
    "name in the middle",
    "two or more voices",
    "speaker owner",
    "speaker unsure",
    "speaker guest",
    "voice score",
    "chatter lately",
    "one face",
    "two or more faces",
    "careful calls",
)
KEYS = ("rule", "name_exact", "name_near", "where", "voices", "speaker", "score", "since_chatter_s", "faces", "careful")


def clean(row: dict) -> dict:
    """Only the known flags and numbers, as plain values: nothing else (and never words) reaches the file."""
    out: dict = {}
    for k in KEYS:
        v = row.get(k)
        if k == "rule":
            v = v if v in RULES else "other"
        elif k == "where":
            v = v if v in ("first", "last", "middle") else ""
        elif k == "speaker":
            v = v if v in ("owner", "unsure", "guest") else ""
        elif k in ("name_exact", "name_near", "careful"):
            v = bool(v)
        elif k in ("voices", "faces"):
            v = None if v is None else int(v)
        elif k in ("score", "since_chatter_s"):
            v = None if v is None else round(float(v), 2)
        out[k] = v
    return out


def vector(row: dict) -> list[float]:
    rule, where, sp = row.get("rule"), row.get("where"), row.get("speaker")
    since, score, faces = row.get("since_chatter_s"), row.get("score"), row.get("faces")
    x = [1.0]
    x += [1.0 if rule == r else 0.0 for r in RULES]
    x += [float(bool(row.get("name_exact"))), float(bool(row.get("name_near")))]
    x += [float(where == "last"), float(where == "middle")]
    x.append(float((row.get("voices") or 0) >= 2))
    x += [float(sp == "owner"), float(sp == "unsure"), float(sp == "guest")]
    x.append(float(score) if score is not None else 0.0)
    x.append(math.exp(-float(since) / 30.0) if since is not None else 0.0)
    x += [float(faces == 1), float((faces or 0) >= 2)]
    x.append(float(bool(row.get("careful"))))
    return x


def sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def fit(xs: list[list[float]], ys: list[int], l2: float = 0.05, iters: int = 600, lr: float = 0.5) -> list[float]:
    """Logistic regression by batch gradient descent; each class weighs the same in all (misfires are rarer)."""
    n, d = len(xs), len(xs[0])
    pos = sum(ys) or 1
    neg = (n - sum(ys)) or 1
    cw = {1: n / (2.0 * pos), 0: n / (2.0 * neg)}
    w = [0.0] * d
    for _ in range(iters):
        g = [0.0] * d
        for x, y in zip(xs, ys, strict=True):
            err = (sigmoid(sum(a * b for a, b in zip(w, x, strict=True))) - y) * cw[y]
            for j in range(d):
                g[j] += err * x[j]
        for j in range(d):
            g[j] = g[j] / n + (l2 * w[j] if j else 0.0)  # the bias isn't penalised
            w[j] -= lr * g[j]
    return w


def today() -> str:
    return dt.date.today().isoformat()


class Learner:
    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.rows_file = self.folder / "gate-turns.jsonl"
        self.model_file = self.folder / "gate-model.json"
        self.lock = threading.Lock()
        self._model: dict | None = None
        self._loaded = False
        self.vetoes = 0  # since start (a count)
        self.recorded = {0: 0, 1: 0}  # since start

    # ------------------------------------------------------------------------------------------------ rows
    def record(self, row: dict, label: int) -> None:
        """One labelled turn (1 went well, 0 a misfire): flags and numbers only (clean())."""
        line = json.dumps({**clean(row), "label": 1 if label else 0, "day": today()}, separators=(",", ":"))
        with self.lock:
            self.folder.mkdir(parents=True, exist_ok=True)
            with self.rows_file.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
            self.recorded[1 if label else 0] += 1

    def rows(self) -> list[dict]:
        try:
            lines = self.rows_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out = []
        for ln in lines:
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if isinstance(r, dict) and r.get("label") in (0, 1):
                out.append(r)
        return out

    # ----------------------------------------------------------------------------------------------- model
    def model(self) -> dict | None:
        with self.lock:
            if not self._loaded:
                try:
                    self._model = json.loads(self.model_file.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    self._model = None
                self._loaded = True
            return self._model

    def train(self) -> dict:
        """The nightly fit: trims the rows to ROWS_MAX, fits, saves; returns the summary (numbers only)."""
        rows = self.rows()
        if len(rows) > ROWS_MAX:
            rows = rows[-ROWS_MAX:]
            with self.lock:
                tmp = self.rows_file.with_suffix(".tmp")
                tmp.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows), encoding="utf-8")
                tmp.replace(self.rows_file)
        good = sum(1 for r in rows if r["label"] == 1)
        bad = len(rows) - good
        out: dict = {"rows": len(rows), "good": good, "misfires": bad, "trained": today(), "active": False}
        if len(rows) >= MIN_ROWS and good >= MIN_EACH and bad >= MIN_EACH:
            xs = [vector(r) for r in rows]
            ys = [int(r["label"]) for r in rows]
            w = fit(xs, ys)
            p = [sigmoid(sum(a * b for a, b in zip(w, x, strict=True))) for x in xs]
            out["active"] = True
            out["w"] = [round(x, 4) for x in w]
            out["fit"] = round(sum(1 for pi, y in zip(p, ys, strict=True) if (pi >= 0.5) == bool(y)) / len(ys), 3)
            out["would_veto"] = sum(1 for pi, r in zip(p, rows, strict=True) if pi < VETO_P and r["label"] == 0)
            out["would_veto_good"] = sum(1 for pi, r in zip(p, rows, strict=True) if pi < VETO_P and r["label"] == 1)
        with self.lock:
            self.folder.mkdir(parents=True, exist_ok=True)
            tmp = self.model_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(out), encoding="utf-8")
            tmp.replace(self.model_file)
            self._model, self._loaded = out, True
        return {k: v for k, v in out.items() if k != "w"}

    def chance(self, feats: dict) -> float | None:
        """The model's chance that a turn like this is to Kurooto; None when it isn't acting (too few rows)."""
        m = self.model()
        if not m or not m.get("active") or not m.get("w"):
            return None
        w = m["w"]
        x = vector(clean(feats))
        if len(w) != len(x):  # a model from another version: not used until the next night
            return None
        return sigmoid(sum(a * b for a, b in zip(w, x, strict=True)))

    def veto(self, feats: dict) -> bool:
        p = self.chance(feats)
        if p is None or p >= VETO_P:
            return False
        self.vetoes += 1
        return True

    def forget(self) -> None:
        with self.lock:
            for f in (self.rows_file, self.model_file):
                try:
                    f.unlink()
                except OSError:
                    pass
            self._model, self._loaded = None, True

    def status(self) -> dict:
        """Numbers only, for /voice, the health line and GET /api/voice."""
        m = self.model() or {}
        return {
            "rows": int(m.get("rows") or 0),
            "good": int(m.get("good") or 0),
            "misfires": int(m.get("misfires") or 0),
            "active": bool(m.get("active")),
            "trained": m.get("trained"),
            "fit": m.get("fit"),
            "vetoes": self.vetoes,
            "recorded": {"good": self.recorded[1], "misfires": self.recorded[0]},
        }
