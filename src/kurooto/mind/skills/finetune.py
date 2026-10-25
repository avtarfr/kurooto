"""The weekly local fine-tune (Brain, 0.8.0 stage 12, off by default: `mind.finetune.on`).

A QLoRA adapter on the local model, trained from the base weights every week (adapters are never stacked, so forgetting
holds), on examples whose outcome was verified by code or by the world, never by your approval:
  - an applied proposal that held for 48 hours, with its checks passing (the request and the diff),
  - a practice task of the hidden harness that its own rules solve and the grader marks right.
Everything about health or money, anything out of other people's chats, and anything `/forget` removed is left out.

Verified forgetting (I-11): for every example that was trained on once and has since gone from its source, a tombstone
keeps a keyed hash and the first few words of its prompt (`mind.finetune.probe_words`, at least 3) with a keyed
fingerprint of its answer; the new adapter is asked each of those prompts, and if any answer comes back the adapter is
rejected. The adapter then becomes a challenger (mind/improve.py) and is promoted only after a hidden-harness win and
your say-so.

    available(app)    why the fine-tune can't run here ("" when it can): an 8 GB-class GPU, the training packages
    collect(app)      the examples
    run(app, ...)     one weekly run; the trainer, the generator and the scorer are passed in (tests use fakes)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import shutil
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core import proposals
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.mind import improve
from kurooto.mind.skills.distill import SENSITIVE, SETTLE_S

if TYPE_CHECKING:
    from kurooto.app import App

FILE = "mind-finetune.json"
MIN_VRAM_GB = 6.0
PACKAGES = ("torch", "transformers", "peft", "bitsandbytes")
FP_WORDS = 12
TOMBSTONES_MAX = 1000
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
OTHERS = re.compile(r"\b(whatsapp|telegram chat|group chat|messages from|dm from)\b", re.I)

register_defaults(
    "mind",
    {
        "finetune": {
            "on": False,  # a weekly local fine-tune on checked examples; needs an 8 GB GPU and the training packages
            "day": "sun",  # the night it trains (mon to sun)
            "base": "",  # the local model's name in Ollama to build the adapter into (empty: the helper model)
            "base_hf": "",  # the same model's Hugging Face name, which the trainer loads
            "probe_words": 5,  # words of a forgotten prompt kept to check that the new adapter forgot it (3 or more)
            "min_examples": 30,  # fewer verified examples than this and it skips the week
            "practice": True,  # include the harness' practice tasks, which its own rules solve and a grader checks
        }
    },
)


# ---------------------------------------------------------------------------------------------------- state
def _state(app: App) -> dict:
    d = jload(app.paths.state / FILE, {}) or {}
    for k, v in (("manifest", []), ("tombstones", []), ("runs", [])):
        d.setdefault(k, v)
    return d


def _save(app: App, d: dict) -> None:
    d["tombstones"] = d["tombstones"][-TOMBSTONES_MAX:]
    d["runs"] = d["runs"][-30:]
    jsave(app.paths.state / FILE, d)


def home(app: App) -> Path:
    return app.paths.state / "mind-skills" / "finetune"


def _secret(app: App) -> bytes:
    f = home(app) / "secret"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(hashlib.sha256(f"{time.time()}{id(app)}".encode() + __import__("os").urandom(32)).digest())
        f.chmod(0o600)
    return f.read_bytes()


def keyed(app: App, *parts: str) -> str:
    return hmac.new(_secret(app), "\x1f".join(parts).encode(), hashlib.sha256).hexdigest()[:32]


def words(text: str, n: int) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())[:n]


def fingerprint(app: App, completion: str) -> str:
    return keyed(app, "fp", " ".join(words(completion, FP_WORDS)))


def probe_words(app: App) -> int:
    n = app.settings.get("mind.finetune.probe_words")
    return max(3, int(n)) if isinstance(n, (int, float)) else 5


# ----------------------------------------------------------------------------------------------- the examples
def excluded(*texts: str) -> bool:
    t = " ".join(texts)
    return bool(SENSITIVE.search(t) or OTHERS.search(t))


def from_proposals(app: App, now: float) -> list[dict]:
    """Outcome-verified: applied, not undone, old enough, checks (if any ran) passing. Approval is not read at all."""
    out = []
    for p in proposals.every(app):
        a = p.get("applied") or {}
        if p.get("status") != "applied" or now - float(a.get("at") or now) < SETTLE_S:
            continue
        checks = p.get("checks") or {}
        if checks.get("ran") and not checks.get("ok"):
            continue
        try:
            diff = (proposals.home(app) / f"{p['id']}.diff").read_text(encoding="utf-8")
        except OSError:
            continue
        req = str(p.get("request") or p.get("title") or "")
        if not req or excluded(req, diff[:4000], str(p.get("title") or "")):
            continue
        out.append({"source": f"proposal:{p['id']}", "prompt": req[:1500], "completion": diff[:6000]})
    return out


def from_practice(app: App) -> list[dict]:
    """The harness' practice tasks its own rules solve and the grader marks right (code-verified, nobody's data)."""
    from kurooto.mind.harness import suite
    from kurooto.mind.harness.tasks import TASK_TYPES

    out = []
    try:
        insts = suite.load(app, "practice")
    except Exception:
        return []
    for inst in insts:
        t = TASK_TYPES.get(inst["type"])
        if t is None:
            continue
        ans = t.solve(inst["inputs"])
        if t.grade(ans, inst["key"]) >= 1.0:
            out.append(
                {
                    "source": f"practice:{inst['type']}:{inst.get('id', len(out))}",
                    "prompt": f"Task type: {inst['type']}. Answer with JSON only.\nInputs: "
                    + json.dumps(inst["inputs"], sort_keys=True),
                    "completion": ans if isinstance(ans, str) else json.dumps(ans, sort_keys=True),
                }
            )
    return out


def collect(app: App, now: float | None = None) -> list[dict]:
    now = now or time.time()
    st = _state(app)
    gone = {t["key"] for t in st["tombstones"]}
    out = []
    pool = from_proposals(app, now) + (from_practice(app) if app.settings.get("mind.finetune.practice") else [])
    for ex in pool:
        ex["key"] = keyed(app, "src", ex["source"])
        if ex["key"] not in gone:
            out.append(ex)
    return out[: int(app.settings.get("mind.finetune.max_examples") or 400)]


def forget_span(app: App, lo: float, hi: float) -> int:
    """/forget: the examples from proposals made in [lo, hi) become tombstones (a keyed hash, a few words and an
    answer fingerprint), so no later adapter trains on them and every one is probed against them."""
    st = _state(app)
    have = {t["key"] for t in st["tombstones"]}
    n, now = 0, time.time()
    for ex in from_proposals(app, now + 10 * 86400):  # whatever its age: settled or not
        p = proposals.get(app, ex["source"].split(":", 1)[1])
        if not p or not (lo <= float(p.get("created") or 0) < hi):
            continue
        key = keyed(app, "src", ex["source"])
        if key not in have:
            st["tombstones"].append(
                {
                    "key": key,
                    "prefix": " ".join(words(ex["prompt"], probe_words(app))),
                    "fp": fingerprint(app, ex["completion"]),
                    "at": now,
                }
            )
            n += 1
    st["manifest"] = [e for e in st["manifest"] if e["key"] not in {t["key"] for t in st["tombstones"]}]
    _save(app, st)
    return n


def sync_forgotten(app: App, current: set[str]) -> int:
    """Examples that were trained on and are no longer in their source (the owner forgot them, or they were undone)
    become
    tombstones: a keyed hash, a few words of the prompt and an answer fingerprint; the text itself is already gone."""
    st = _state(app)
    keep, moved = [], 0
    have = {t["key"] for t in st["tombstones"]}
    for e in st["manifest"]:
        if e["key"] in current:
            keep.append(e)
        else:
            if e["key"] not in have:
                st["tombstones"].append({**e, "at": time.time()})
            moved += 1
    st["manifest"] = keep
    _save(app, st)
    return moved


# ------------------------------------------------------------------------------------------- availability
def available(app: App) -> str:
    """Why the fine-tune can't run on this computer, or "" when it can."""
    import importlib.util

    from kurooto.core import hardware

    try:
        vram = hardware.detect().nvidia_vram
    except Exception:
        vram = 0.0
    if vram < MIN_VRAM_GB:
        return f"it needs an NVIDIA graphics card with about 8 GB (this one has {vram:g} GB)"
    missing = [p for p in PACKAGES if importlib.util.find_spec(p) is None]
    if missing:
        return "the training packages aren't installed (" + ", ".join(missing) + ")"
    if not str(app.settings.get("mind.finetune.base_hf") or ""):
        return "mind.finetune.base_hf names no base model to train"
    return ""


def due(app: App, now: float | None = None) -> bool:
    """Is it the night? The configured weekday, and not already trained this week."""
    now = now or time.time()
    day = str(app.settings.get("mind.finetune.day") or "sun").lower()[:3]
    if day not in DAYS or time.strftime("%a", time.localtime(now)).lower()[:3] != day:
        return False
    last = max((r["at"] for r in _state(app)["runs"] if r.get("ok") is not None), default=0)
    return now - last > 5 * 86400


# --------------------------------------------------------------------------------------------- the weekly run
def champion(app: App) -> dict:
    rows = sorted(mind.connect(app).mood_rows("harness:"), key=lambda r: r["key"])
    if not rows:
        return {"mean_hidden": 0.0, "invariants_ok": True}
    m = rows[-1].get("meta") or {}
    return {"mean_hidden": float(m.get("mean_hidden") or 0.0), "invariants_ok": bool(m.get("invariants_ok", True))}


def run(app: App, trainer=None, generate=None, scorer=None, now: float | None = None, force: bool = False) -> dict:
    """One weekly run -> {"ok", "why", ...}. `trainer(base, dataset_path, out_dir)` trains from the base weights and
    returns the adapter folder or None (it is given no earlier adapter); `generate(adapter, prompt) -> str`;
    `scorer(adapter) -> {"mean_hidden", "invariants_ok"}`."""
    now = now or time.time()
    if not mind.part_on(app, "finetune"):
        return {"ok": False, "why": "the fine-tune is off (mind.finetune.on)"}
    if not force and not due(app, now):
        return {"ok": False, "why": "not its night"}
    if trainer is None:
        why = available(app)
        if why:
            return {"ok": False, "why": why}
        from kurooto.core import power

        if not power.on_ac():
            return {"ok": False, "why": "it isn't on the charger"}
        trainer, generate, scorer = (
            default_trainer(app),
            generate or default_generate(app),
            scorer or default_scorer(app),
        )
    examples = collect(app, now)
    need = int(app.settings.get("mind.finetune.min_examples") or 30)
    if len(examples) < need:
        return {"ok": False, "why": f"only {len(examples)} verified examples; it waits for {need}"}
    sync_forgotten(app, {e["key"] for e in examples})
    st = _state(app)
    run_id = time.strftime("%Y%m%d", time.localtime(now)) + "-" + keyed(app, "run", str(now))[:6]
    d = home(app) / run_id
    d.mkdir(parents=True, exist_ok=True)
    data = d / "train.jsonl"
    data.write_text("\n".join(json.dumps({"prompt": e["prompt"], "completion": e["completion"]}) for e in examples))
    base = str(app.settings.get("mind.finetune.base") or app.settings.get("mind.finetune.base_hf") or "")
    try:
        adapter = trainer(base, data, d / "adapter")
    finally:
        data.unlink(missing_ok=True)  # the training text doesn't outlive the run
    if adapter is None:
        shutil.rmtree(d, ignore_errors=True)
        return {"ok": False, "why": "the trainer made no adapter"}
    n = probe_words(app)
    manifest = [
        {"key": e["key"], "prefix": " ".join(words(e["prompt"], n)), "fp": fingerprint(app, e["completion"])}
        for e in examples
    ]
    leaks = probe(app, generate, adapter, st["tombstones"]) if generate and st["tombstones"] else []
    if leaks:
        shutil.rmtree(d, ignore_errors=True)
        st["runs"].append({"at": now, "ok": False, "why": "forgotten", "n": len(examples), "leaks": len(leaks)})
        _save(app, st)
        mind.connect(app).report(
            "finetune_event", {"status": "rejected_forgetting", "n": len(examples), "leaks": len(leaks)}
        )
        return {
            "ok": False,
            "why": f"{len(leaks)} forgotten item(s) came back; the adapter was thrown away",
            "leaks": len(leaks),
        }
    st["manifest"] = manifest
    st["runs"].append({"at": now, "ok": True, "n": len(examples), "adapter": str(adapter)})
    _save(app, st)
    champ = champion(app)
    sub = improve.submit(app, f"Local model adapter {run_id}", [f"adapters/{run_id}"], f"+adapter {run_id}\n", champ)
    if sub["ok"]:
        improve.attach(app, sub["id"], adapter=str(adapter))
        if scorer:
            improve.score(app, sub["id"], scorer(adapter))
    mind.connect(app).report("finetune_event", {"status": "trained", "n": len(examples), "leaks": 0})
    return {"ok": True, "why": "", "n": len(examples), "challenger": sub.get("id"), "adapter": str(adapter)}


def probe(app: App, generate, adapter, tombstones: list[dict]) -> list[str]:
    """Ask the new adapter each forgotten prompt; the keys whose answer's fingerprint matches what was forgotten."""
    leaks = []
    for t in tombstones:
        try:
            out = generate(adapter, t["prefix"]) or ""
        except Exception as e:  # a generation that fails can't show a leak; the run says so
            app.events.emit("finetune_probe_failed", error=type(e).__name__)
            continue
        if fingerprint(app, out) == t["fp"]:
            leaks.append(t["key"])
    return leaks


# -------------------------------------------------------------------------------- the default (unverified here)
def default_trainer(app: App):
    """Train with the QLoRA script in a subprocess in the lab's sandbox is not possible (it needs the GPU and the model
    files); it runs as a plain subprocess of this Python, on the charger, at night."""
    import subprocess

    def train(base: str, dataset: Path, out: Path) -> Path | None:
        out.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-m",
                "kurooto.mind.skills.qlora",
                "train",
                "--base",
                str(app.settings.get("mind.finetune.base_hf")),
                "--data",
                str(dataset),
                "--out",
                str(out),
            ],
            capture_output=True,
            text=True,
            timeout=6 * 3600,
            check=False,
        )
        return out if r.returncode == 0 and (out / "adapter_config.json").exists() else None

    return train


def default_generate(app: App):
    import subprocess

    def gen(adapter: Path, prompt: str) -> str:
        r = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-m",
                "kurooto.mind.skills.qlora",
                "generate",
                "--base",
                str(app.settings.get("mind.finetune.base_hf")),
                "--adapter",
                str(adapter),
                "--prompt",
                prompt,
            ],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        return r.stdout if r.returncode == 0 else ""

    return gen


def default_scorer(app: App):
    """The adapter's hidden-harness score: the harness run with the adapter answering. Not wired yet: None means the
    challenger stays in shadow (I-12) until a score is recorded."""

    def score(adapter: Path):
        return None

    return score


def install(app: App, adapter: str) -> str:
    """After you promote an adapter: build it into Ollama as a model of its own (the base stays as it was)."""
    import subprocess

    base = str(app.settings.get("mind.finetune.base") or "")
    if not base:
        return " (mind.finetune.base names no Ollama model to build it into, so nothing was installed)"
    name = f"{base.split(':')[0]}-kurooto"
    mf = Path(adapter) / "Modelfile"
    mf.write_text(f"FROM {base}\nADAPTER {Path(adapter).resolve()}\n")
    r = subprocess.run(
        ["ollama", "create", name, "-f", str(mf)], capture_output=True, text=True, timeout=1800, check=False
    )  # noqa: S603, S607
    return (
        f" Built into Ollama as {name}." if r.returncode == 0 else " (Ollama couldn't build it; the adapter is kept.)"
    )
