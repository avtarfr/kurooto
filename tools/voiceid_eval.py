#!/usr/bin/env python3
"""Measure Voice ID offline: false accepts and false rejects on held-out LibriSpeech speakers (a dev tool; Kurooto
never imports it, nothing it makes ships).

    uv run --with onnxruntime --with kaldi-native-fbank --with soundfile --with numpy \\
        python tools/voiceid_eval.py --librispeech /path/to/librispeech --model <the .onnx> --out /tmp/eval.json

What it runs is Kurooto's own code, not a copy of it:
- the impostor set is built the way tools/voiceid_bank.py builds the shipped one (same picks, crops and kinds), but
  never from the speakers being tested: the shipped set has every LibriSpeech dev/test speaker, so testing against it
  would put each stranger's own voice inside the threshold's calibration. Two ways: "halves" (the set from dev-*,
  speakers tested from test-*, then the other way round; every other speaker of the half is a stranger) and "groups"
  (--groups K: the speakers in K groups; each group is tested against a set made from all the others, about
  (K-1)/K of the shipped set's size, the strangers being the rest of its group). The false-accept rate falls as the
  set grows (roughly halving each time it doubles), so "groups" is the closer estimate of the shipped set.
- each tested speaker is enrolled through modules/voice/enrol.Session (the real plan, quality checks, crops and
  windows), from his first chapter, with the conditions made from clean audiobook speech: quiet is 14 dB softer, far
  is 10 dB softer with a synthetic room echo, noise is pink noise at 10 dB below the speech, short requests are 1.2 to
  2.5 s cuts, free speech is 11 s of joined utterances. The template and thresholds come from speakerid.calibrate,
  every strictness, as Train does; each turn is decided by speakerid.Verifier.check, as Voice does.
- turns: his other utterances (another chapter where he has one) and every other tested speaker's, each whole (up to
  8 s), and cut to 2 s, 1.5 s and 0.8 s from the middle; speech seconds come from an energy VAD on 512-sample frames.
  The 0.8 s turns are decided twice: alone ("too short", never accepted) and as a short reply right after an
  accepted turn of the owner (carry), which is the one place a short turn can pass.

Honest limits: LibriSpeech is read audiobook speech, mostly clean, one microphone per chapter; real rooms, colds,
other microphones and spontaneous speech score lower for the owner (more "not sure") and the simulated conditions
are only an approximation. Impostors here are strangers, not relatives. Vectors are cached in --cache (numbers only,
in the scratch folder you name; never audio)."""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from kurooto.modules.voice import enrol  # noqa: E402
from kurooto.modules.voice import speakerid as sid  # noqa: E402

FOLDS = (("dev-clean", "dev-other"), ("test-clean", "test-other"))
STRICTNESS = ("relaxed", "normal", "strict")
LENGTHS = (("long", None), ("2s", 2.0), ("1.5s", 1.5), ("0.8s", 0.8))
TEST_UTTS = 8  # held-out utterances per speaker
RATE = 16000
_EMB = None


# ------------------------------------------------------------------------------------------------ sound
def _np():
    import numpy as np

    return np


def level(x, rms_db: float = -26.0, peak: float = 0.9):
    """Speech to rms_db dBFS, its peak kept under `peak`."""
    np = _np()
    r = float(np.sqrt(np.mean(x * x))) or 1e-9
    y = x * (10 ** (rms_db / 20) / r)
    m = float(np.max(np.abs(y))) or 1e-9
    return y * min(1.0, peak / m)


def pink(n: int, rng):
    np = _np()
    w = rng.standard_normal(n)
    f = np.fft.rfft(w)
    f /= np.sqrt(np.maximum(np.arange(len(f)), 1))
    y = np.fft.irfft(f, n)
    return y / (float(np.sqrt(np.mean(y * y))) or 1e-9)


def room(x, rng, rt60: float = 0.45):
    np = _np()
    n = int(rt60 * RATE)
    t = np.arange(n) / RATE
    ir = rng.standard_normal(n) * np.exp(-6.9 * t / rt60)
    ir[0] = 1.0
    ir *= 0.35 / (float(np.sqrt(np.sum(ir[1:] ** 2))) or 1e-9)
    ir[0] = 1.0
    return np.convolve(x, ir)[: len(x)]


def pad(x, rng, seconds: float = 0.35, floor_db: float = -62.0):
    """A pre-roll and a tail of room hiss, as the listener's cut has; the hiss runs under the speech too."""
    np = _np()
    n = int(seconds * RATE)
    y = np.concatenate([np.zeros(n), x, np.zeros(n)])
    return y + pink(len(y), rng) * 10 ** (floor_db / 20)


def pcm16(x) -> bytes:
    np = _np()
    return (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()


def flags(pcm: bytes) -> bytes:
    """An energy VAD per 512-sample frame: 12 dB over the quietest tenth of the frames (and over -50 dBFS)."""
    np = _np()
    a = np.frombuffer(pcm, dtype="<i2").astype("float32") / 32768
    n = len(a) // enrol.FRAME
    if n == 0:
        return b""
    fr = a[: n * enrol.FRAME].reshape(n, enrol.FRAME)
    db = 20 * np.log10(np.sqrt(np.mean(fr * fr, axis=1)) + 1e-9)
    floor = float(np.sort(db)[: max(1, n // 10)].mean())
    cut = max(floor + 12, -50.0)
    return bytes(int(d > cut) for d in db)


def middle(x, seconds: float):
    n = int(seconds * RATE)
    if len(x) <= n:
        return x
    a = (len(x) - n) // 2
    return x[a : a + n]


# ---------------------------------------------------------------------------------------------- speakers
def speakers(root: Path) -> dict[str, dict]:
    """speaker key -> {split, gender, chapters: {chapter: [files]}}, every split there is."""
    import voiceid_bank as vb

    gender = {}
    txt = next((p for p in (root / "LibriSpeech" / "SPEAKERS.TXT", root / "SPEAKERS.TXT") if p.is_file()), None)
    if txt is not None:
        for line in txt.read_text(errors="replace").splitlines():
            if line.startswith(";") or "|" not in line:
                continue
            parts = [p.strip() for p in line.split("|")]
            gender[parts[0]] = parts[1]
    out = {}
    for split in vb.SPLITS:
        base = next((p for p in (root / "LibriSpeech" / split, root / split) if p.is_dir()), None)
        if base is None:
            continue
        for spk in sorted(p for p in base.iterdir() if p.is_dir()):
            ch = {c.name: sorted(c.glob("*.flac")) for c in sorted(spk.iterdir()) if c.is_dir()}
            out[f"{split}/{spk.name}"] = {"split": split, "gender": gender.get(spk.name, "?"), "chapters": ch}
    return out


def _embedder(model: str, threads: int):
    global _EMB
    if _EMB is None:
        _EMB = sid.Embedder(Path(model), threads=threads)
    return _EMB


def bank_rows(files: list[Path], emb) -> tuple[list, list]:
    """tools/voiceid_bank.py's recipe for one speaker: 4 utterances of 4 s or more (its round-robin picks), each
    whole, and its middle 3 s and 1.5 s."""
    import voiceid_bank as vb

    rows, kinds, took = [], [], 0
    for f in files:
        if took >= vb.PER_SPEAKER:
            break
        x = vb.load16k(f)
        if len(x) < vb.MIN_S * RATE:
            continue
        for kind, piece in ((sid.KIND_FULL, x), (sid.KIND_3S, vb.middle(x, 3.0)), (sid.KIND_15, vb.middle(x, 1.5))):
            rows.append(emb.embed(piece.tobytes()))
            kinds.append(kind)
        took += 1
    return rows, kinds


def bank_picks(chapters: dict[str, list[Path]]) -> list[Path]:
    import voiceid_bank as vb

    by = {c: list(fs) for c, fs in chapters.items()}
    picked = []
    while len(picked) < vb.PER_SPEAKER * 3 and any(by.values()):
        for c in sorted(by):
            if by[c]:
                picked.append(by[c].pop(0))
    return picked


def load(f: Path):
    import voiceid_bank as vb

    return vb.load16k(f).astype("float32") / 32768


def enrol_speaker(files: list[Path], emb, seed: int) -> tuple[list[dict], dict]:
    """The real enrolment Session, fed clips made from these files. Its accepted samples and a few counts."""
    np = _np()
    rng = np.random.default_rng(seed)
    utts = [x for x in (load(f) for f in files) if len(x) >= 2.0 * RATE]
    if len(utts) < 6:
        raise ValueError("too few utterances to enrol")
    it = iter(range(10**6))

    def utt():
        return utts[next(it) % len(utts)]

    def clip(cond: str) -> tuple[bytes, bytes]:
        """The sound and its VAD flags; with noise, the flags come from the speech before the noise (Silero, which
        the listener uses, finds speech in noise far better than an energy VAD would)."""
        if cond == "free":
            parts, total = [], 0
            while total < 11 * RATE:
                u = middle(utt(), 4.0)
                parts += [u, np.zeros(int(0.25 * RATE))]
                total += len(u)
            x = level(np.concatenate(parts))
        elif cond == "calls":
            x = level(middle(utt(), float(rng.uniform(1.2, 2.5))))
        else:
            x = level(middle(utt(), float(rng.uniform(3.0, 4.5))))
        if cond == "quiet":
            x = x * 10 ** (-14 / 20)
        elif cond == "far":
            x = room(x, rng) * 10 ** (-10 / 20)
        y = pad(x, rng)
        fl = flags(pcm16(y))
        if cond == "noise":
            sp = float(np.sqrt(np.mean(x * x)))
            y = y + pink(len(y), rng) * sp * 10 ** (-10 / 20)
        return pcm16(y), fl

    holder: dict = {}
    tries = {"n": 0}

    def capture(_timeout: float, _cancel) -> enrol.Cut | None:
        s = holder["s"]
        tries["n"] += 1
        if tries["n"] > 120:  # something keeps failing: stop rather than loop
            s.command("stop")
            return None
        pcm, fl = clip(s.cond.key if s.cond else "normal")
        return enrol.Cut(bytearray(pcm), fl)

    rng_s = random.Random(seed)  # noqa: S311 (which sentence; nothing secret)
    s = enrol.Session(capture=capture, embed=emb.embed, stt=None, rng=rng_s, timeout_s=1, idle_s=1)
    holder["s"] = s
    end = s.run()
    rejected = {}
    for a in s.attempts:
        if not a["ok"]:
            k = a["reason"].split(":")[0].split("(")[0].strip()
            rejected[k] = rejected.get(k, 0) + 1
    return s.samples, {"end": end, "attempts": len(s.attempts), "rejected": rejected}


def test_turns(files: list[Path], emb, seed: int) -> list[dict]:
    """Each held-out utterance as four turns: whole (up to 8 s), and its middle 2, 1.5 and 0.8 s."""
    np = _np()
    rng = np.random.default_rng(seed)
    out = []
    for f in files[:TEST_UTTS]:
        x = level(load(f))
        for name, sec in LENGTHS:
            piece = middle(x, 8.0 if sec is None else sec)
            pcm = pcm16(pad(piece, rng))
            fl = flags(pcm)
            speech_s = sum(fl) * enrol.FRAME / RATE
            lo, hi = enrol.speech_span(enrol.Cut(bytearray(pcm), fl))
            try:
                e = emb.embed(pcm[lo:hi]) if hi - lo >= 2 * int(0.3 * RATE) else None
            except ValueError:
                e = None
            if e is not None:
                out.append({"len": name, "speech_s": round(speech_s, 3), "e": [round(v, 5) for v in e]})
    return out


def one_speaker(job: tuple) -> dict:
    key, info, model, threads, seed = job
    emb = _embedder(model, threads)
    chs = info["chapters"]
    order = sorted(chs, key=lambda c: -len(chs[c]))
    first = chs[order[0]]
    others = [f for c in order[1:] for f in chs[c]]
    n_enrol = min(len(first), 24)
    enrol_files = first[:n_enrol]
    test_files = others if len(others) >= TEST_UTTS else others + first[n_enrol:]
    out = {"key": key, "split": info["split"], "gender": info["gender"], "cross_chapter": len(others) >= TEST_UTTS}
    rows, kinds = bank_rows(bank_picks(chs), emb)
    out["bank"] = {"rows": [[round(v, 5) for v in r] for r in rows], "kinds": kinds}
    try:
        samples, meta = enrol_speaker(enrol_files, emb, seed)
        out["enrol"] = {"samples": [{**s, "e": [round(v, 5) for v in s["e"]],
                                     "s": [round(v, 5) for v in s["s"]]} for s in samples], **meta}  # fmt: skip
    except ValueError as e:
        out["enrol"] = {"samples": [], "end": f"skipped: {e}"}
    out["tests"] = test_turns(test_files, emb, seed + 1)
    return out


# ------------------------------------------------------------------------------------------------ scoring
def rates(dec: list[str]) -> dict:
    n = len(dec) or 1
    return {k: round(sum(1 for d in dec if d == k) / n, 5) for k in (sid.OWNER, sid.UNSURE, sid.GUEST)} | {
        "n": len(dec)
    }


def fold(bank_side: list[dict], test_side: list[dict], strictness: str, margin: float) -> dict:
    rows, kinds = [], []
    for sp in bank_side:
        rows += sp["bank"]["rows"]
        kinds += sp["bank"]["kinds"]
    bank = sid.Bank({"model_sha256": "eval"}, bytes(kinds), rows)
    genuine: dict[str, list[str]] = {n: [] for n, _ in LENGTHS}
    impostor: dict[str, list[str]] = {n: [] for n, _ in LENGTHS}
    same_g: dict[str, list[str]] = {n: [] for n, _ in LENGTHS}
    carry_g, carry_i = [], []
    grades: dict[str, int] = {}
    per_spk_far = []
    enrolled = [sp for sp in test_side if len(sp["enrol"]["samples"]) >= sid.MIN_SAMPLES]
    for sp in enrolled:
        try:
            cal = sid.calibrate(sp["enrol"]["samples"], bank, (), strictness, margin, 0.0)
        except ValueError:
            continue
        grades[cal["report"]["grade"]] = grades.get(cal["report"]["grade"], 0) + 1
        vectors: dict[bytes, list] = {}

        def embed(key: bytes, vectors=vectors):
            return vectors[key]

        ver = sid.Verifier(embed, cal["centroid"], cal["thresholds"])
        rules = {"min_speech_s": 1.0, "carry": strictness != "strict", "carry_s": 15, "strict": strictness == "strict"}
        alone = sid.Ctx()
        after = sid.Ctx(portal_session=1, last_owner_at=0.0, last_owner_session=1, now=3.0)

        def decide(t: dict, ctx, vectors=vectors, ver=ver, rules=rules) -> sid.Verdict:
            k = f"{id(t)}".encode()
            vectors[k] = t["e"]
            return ver.check(k, t["speech_s"], ctx, **rules)

        for t in sp["tests"]:
            v = decide(t, alone)
            genuine[t["len"]].append(v.decision)
            if t["len"] == "0.8s":
                carry_g.append(decide(t, after).decision)
        acc = 0
        n = 0
        for other in enrolled:
            if other is sp:
                continue
            for t in other["tests"]:
                v = decide(t, alone)
                impostor[t["len"]].append(v.decision)
                if other["gender"] == sp["gender"]:
                    same_g[t["len"]].append(v.decision)
                if t["len"] == "long":
                    n += 1
                    acc += v.decision == sid.OWNER
                if t["len"] == "0.8s":
                    carry_i.append(decide(t, after).decision)
        per_spk_far.append(acc / n if n else 0.0)
    return {
        "bank_rows": len(rows),
        "bank_speakers": len(bank_side),
        "speakers": len(enrolled),
        "grades": grades,
        "genuine": {k: rates(v) for k, v in genuine.items()},
        "impostor": {k: rates(v) for k, v in impostor.items()},
        "impostor_same_gender": {k: rates(v) for k, v in same_g.items()},
        "carry_genuine": rates(carry_g),
        "carry_impostor": rates(carry_i),
        "speakers_with_any_false_accept_long": sum(1 for x in per_spk_far if x > 0),
        "worst_speaker_far_long": round(max(per_spk_far, default=0.0), 5),
    }


def groups(data: list[dict], k: int, seed: int) -> list[list[dict]]:
    order = sorted(data, key=lambda d: d["key"])
    random.Random(seed).shuffle(order)  # noqa: S311 (a grouping; nothing secret)
    return [order[i::k] for i in range(k)]


def merge_all(parts: list[dict]) -> dict:
    out = parts[0]
    for p in parts[1:]:
        out = merge(out, p) | {"bank_rows": min(out.get("bank_rows", 0), p.get("bank_rows", 0))}
    return out


def merge(a: dict, b: dict) -> dict:
    """Two folds' rates, weighted by their counts."""

    def mix(x: dict, y: dict) -> dict:
        n = x["n"] + y["n"]
        out = {
            k: round((x[k] * x["n"] + y[k] * y["n"]) / n, 5) if n else 0.0 for k in (sid.OWNER, sid.UNSURE, sid.GUEST)
        }
        return out | {"n": n}

    out = {"speakers": a["speakers"] + b["speakers"], "grades": {}}
    for g in set(a["grades"]) | set(b["grades"]):
        out["grades"][g] = a["grades"].get(g, 0) + b["grades"].get(g, 0)
    for k in ("genuine", "impostor", "impostor_same_gender"):
        out[k] = {n: mix(a[k][n], b[k][n]) for n in a[k]}
    for k in ("carry_genuine", "carry_impostor"):
        out[k] = mix(a[k], b[k])
    out["speakers_with_any_false_accept_long"] = (
        a["speakers_with_any_false_accept_long"] + b["speakers_with_any_false_accept_long"]
    )
    out["worst_speaker_far_long"] = max(a["worst_speaker_far_long"], b["worst_speaker_far_long"])
    out["bank_rows"] = min(a.get("bank_rows", 0), b.get("bank_rows", 0))
    return out


def pct(x: float) -> str:
    return f"{100 * x:.2f}%"


def table(res: dict) -> str:
    lines = [
        f"impostor set: at least {res[STRICTNESS[0]].get('bank_rows', '?')} rows (the shipped one: about 1,750)",
        "strictness  turn   owner accepted  owner unsure  stranger accepted  same-gender accepted  (trials)",
    ]
    for st in STRICTNESS:
        r = res[st]
        for n, _ in LENGTHS:
            g, i, s = r["genuine"][n], r["impostor"][n], r["impostor_same_gender"][n]
            lines.append(
                f"{st:10}  {n:5}  {pct(g['owner']):>14}  {pct(g['unsure']):>12}  {pct(i['owner']):>17}  "
                f"{pct(s['owner']):>20}  ({g['n']}/{i['n']})"
            )
        cg, ci = r["carry_genuine"], r["carry_impostor"]
        lines.append(
            f"{st:10}  carry  {pct(cg['owner']):>14}  {'':>12}  {pct(ci['owner']):>17}  (0.8 s right after you)"
        )
        lines.append(
            f"{'':10}  grades {r['grades']}; speakers with a stranger accepted on a long turn: "
            f"{r['speakers_with_any_false_accept_long']} of {r['speakers']}; worst {pct(r['worst_speaker_far_long'])}"
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--librispeech", type=Path, required=True)
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--cache", type=Path, required=True, help="a scratch folder for the vectors (never in the repo)")
    ap.add_argument("--out", type=Path, default=None, help="the results as JSON")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--margin", type=float, default=0.05)
    ap.add_argument("--limit", type=int, default=0, help="at most this many speakers per split (a quick run)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--groups", type=int, default=0, help="also the K-group estimate (e.g. 12)")
    ap.add_argument("--repeats", type=int, default=4, help="the K-group estimate over this many ways of grouping")
    a = ap.parse_args()

    a.cache.mkdir(parents=True, exist_ok=True)
    cache = a.cache / f"vectors-{a.model.stem}-s{a.seed}.json"
    spk = speakers(a.librispeech)
    if a.limit:
        by: dict[str, int] = {}
        keep = {}
        for k, v in spk.items():
            if by.get(v["split"], 0) < a.limit:
                by[v["split"]] = by.get(v["split"], 0) + 1
                keep[k] = v
        spk = keep
    done: dict[str, dict] = {}
    if cache.is_file():
        done = {d["key"]: d for d in json.loads(cache.read_text())}
    todo = [
        (k, v, str(a.model), a.threads, a.seed + i) for i, (k, v) in enumerate(sorted(spk.items())) if k not in done
    ]
    t0 = time.monotonic()
    if todo:
        with ProcessPoolExecutor(max_workers=max(1, a.workers)) as ex:
            for n, r in enumerate(ex.map(one_speaker, todo), 1):
                done[r["key"]] = r
                el = time.monotonic() - t0
                eta = el / n * (len(todo) - n)
                bar = "#" * int(30 * n / len(todo))
                print(f"\r[{bar:<30}] {n}/{len(todo)} speakers, {el:.0f}s, eta {eta:.0f}s", end="", flush=True)
                if n % 10 == 0 or n == len(todo):
                    cache.write_text(json.dumps(list(done.values())))
        print()
    data = [done[k] for k in sorted(spk) if k in done]
    half = [[d for d in data if d["split"] in f] for f in FOLDS]
    res: dict = {"model": a.model.name, "margin": a.margin, "speakers": len(data)}
    ends: dict[str, int] = {}
    for d in data:
        ends[d["enrol"].get("end", "?")] = ends.get(d["enrol"].get("end", "?"), 0) + 1
    res["enrolment_ends"] = ends
    rej: dict[str, int] = {}
    for d in data:
        for k, v in (d["enrol"].get("rejected") or {}).items():
            rej[k] = rej.get(k, 0) + v
    res["enrolment_rejections"] = rej
    res["samples_per_speaker"] = statistics.median([len(d["enrol"]["samples"]) for d in data]) if data else 0
    for st in STRICTNESS:
        f1 = fold(half[0], half[1], st, a.margin)  # strangers' set from dev, speakers tested from test
        f2 = fold(half[1], half[0], st, a.margin)
        res[st] = merge(f1, f2) | {"folds": [f1, f2]}
    if a.groups > 1:
        # which speakers share a group decides which pairs are compared, and a few look-alike pairs carry most of
        # the false accepts: several groupings, pooled
        res["groups"] = {"k": a.groups, "repeats": a.repeats}
        for st in STRICTNESS:
            parts, each = [], []
            for r in range(max(1, a.repeats)):
                gs = groups(data, a.groups, a.seed + r)
                one = [fold([d for j, g in enumerate(gs) if j != i for d in g], gs[i], st, a.margin)
                       for i in range(len(gs))]  # fmt: skip
                parts += one
                each.append(merge_all(one)["impostor"]["long"]["owner"])
            res["groups"][st] = merge_all(parts) | {"far_long_each": each}
    print(f"{res['speakers']} speakers ({len(half[0])} dev, {len(half[1])} test); enrolment: {ends}; "
          f"rejected samples: {rej}; median samples kept {res['samples_per_speaker']}")  # fmt: skip
    print("halves:")
    print(table(res))
    if a.groups > 1:
        print(f"groups ({a.groups}, {a.repeats} groupings pooled):")
        print(table(res["groups"]))
        for st in STRICTNESS:
            each = ", ".join(pct(x) for x in res["groups"][st]["far_long_each"])
            print(f"  {st}: a stranger accepted on a long turn, each grouping: {each}")
    if a.out:
        a.out.write_text(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
