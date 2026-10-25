"""A true journal (Brain, 0.8.0 stage 07): Kurooto writes about its own days, and every line is checked against the mind
log.
True by construction (invariant I-10): code decides what must be in it, code checks every sentence, and a model on this
computer only puts a fact into words; a sentence that fails a check is deleted, never rewritten.

    manifest(app, day)       from the log: every broken promise, undo, failure and crash, wrong read, big swing of the
    drive
                             (|r| > 0.3), change of feeling, autonomous act at R2 or above and proposal, each with its
                             log
                             seq ids and its numbers
    words_for(fact)          the fixed first-person sentence for a fact kind
    check(fact, sentence)    the rules: numbers, names, feeling words, causes, and a closed vocabulary (no invented
    events)
    write_day(app, day)      the day's file: a line per fact, a model's wording where it passes the checks (and the
    entailment
                             question), else the fixed sentence; coverage: every fact has a line
    selfcheck(app, lines)    corrupt copies of the night's lines: the checker must reject at least 99% and keep 95% of
    the true ones
    strike(app, day, n)      you strike a line: a tombstone; a line about you also forgets that day's read (stage 04)

Never a cloud AI: the facts include readings of you (I-11). Tier C computers (no local model) use the fixed sentences
only.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.mind import feelings

if TYPE_CHECKING:
    from kurooto.app import App

PART = "journal"  # its switch: mind.journal.on

register_defaults(
    "mind",
    {
        "journal": {
            "on": True,  # a daily journal of its own states, reasons and mistakes, every line checked against its log
            "in_notes": False,  # also keep it as a block in your notes ("Kurooto journal.md", in Kurooto's own markers)
        }
    },
)

DIR = "mind-journal"  # in the state folder (the scorekeeper's folder holds only what it writes)
SWING = 0.3
REJECT_MIN = 0.99
KEEP_MIN = 0.95
FEELING_WORDS = frozenset(
    {"uneasy", "frustrated", "relieved", "satisfied", "sad", "happy", "worried", "anxious", "upset", "glad", "afraid",
     "lonely", "angry", "excited", "proud", "ashamed", "guilty", "hurt", "scared", "joyful"}
)  # fmt: skip
CAUSAL = re.compile(r"\b(because|since|due to)\b", re.I)
NUMBER = re.compile(r"(?<![A-Za-z])\d+(?:[.:]\d+)?(?![A-Za-z])")  # not the 2 of "R2"
WORD = re.compile(r"[A-Za-z][A-Za-z']*")
CAUSES = {"stop": {"computer", "off", "asleep", "stopped", "paused", "sleeping", "was"}}
FUNCTION = frozenset(
    "i a an the and or but it its my me of at by in on to for with that this was were is are be been you your one not "
    "no "
    "did do does had has have so then also about after before again once twice".split()
)

# the fixed sentence per fact kind; its words (and the fact's own) are the only words a line may use
TEMPLATES = {
    "promise_broken": "I broke a promise: I said I'd do something at {due} and it didn't happen{cause}.",
    "undo": "You undid one of my acts ({what}).",
    "failure": "Something of mine failed: {what}.",
    "wrong_read": "My read of how you were doing was wrong that day.",
    "swing": "My drive {dir} by {r} at {time}.",
    "feeling": "I became {label} about {object}.",
    "act": "I did a {klass} act on my own: {what}.",
    "proposal": "A proposal was {what}.",
}


@dataclass
class Fact:
    kind: str
    seqs: list[int]
    t: float
    nums: dict = field(default_factory=dict)  # name -> number (what a sentence's numbers must come from)
    words: dict = field(default_factory=dict)  # name -> id-like word (what a sentence's names must come from)
    cause: str = ""
    label: str = ""  # a feeling label
    about_him: bool = False

    def tokens(self) -> set[str]:
        out: set[str] = set()
        for v in [*self.words.values(), self.label, self.cause]:
            out |= {w.lower() for w in re.split(r"[^A-Za-z]+", str(v)) if w}
        return out

    def numbers(self) -> set[str]:
        """Every way a sentence may write one of this fact's numbers (a time as HH:MM and its parts)."""
        out: set[str] = set()
        for name, v in self.nums.items():
            if name in ("due", "time"):
                h, m = divmod(int(v) % 1440, 60)
                out |= {f"{h:02d}:{m:02d}", f"{h:02d}", f"{m:02d}", str(h), str(m)}
            else:
                out |= {str(int(v)), f"{abs(v):.2f}", f"{abs(v):.1f}", f"{abs(v):g}", f"{v:g}"}
        return out


def _hm(ts: float) -> int:
    d = dt.datetime.fromtimestamp(ts)
    return d.hour * 60 + d.minute


def _word(v) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]", "", str(v or ""))[:40]


def manifest(app: App, day: dt.date) -> list[Fact]:
    """The facts of the day (local midnight to midnight) that must have a line, from the mind log."""
    lo = dt.datetime.combine(day, dt.time(0)).timestamp()
    hi = lo + 86400
    c = mind.connect(app)
    recs = [r for r in c.log(0, None, 5000) if lo <= r.ts < hi]
    spans = _spans(c)
    out: list[Fact] = []
    for r in recs:
        b = r.body if isinstance(r.body, dict) else {}
        k = r.kind
        if k == "promise_broken":
            stopped = _frozen(spans, float(b.get("due_s") or 0))
            out.append(
                Fact(
                    "promise_broken",
                    [r.seq],
                    r.ts,
                    {"due": _hm(float(b.get("due_s") or r.ts))},
                    cause="stop" if stopped else "",
                )
            )
        elif k.endswith(("_undo", "_undone")):
            out.append(
                Fact("undo", [r.seq], r.ts, words={"what": _word(k.replace("_undone", "").replace("_undo", ""))})
            )
        elif k in ("job_failed", "job_crashed", "kurooto_crashed", "module_failed") or (
            k == "mind_keeper_exited" and not b.get("asked")
        ):
            out.append(Fact("failure", [r.seq], r.ts, words={"what": _word(k)}))
        elif k == "read_answer" and b.get("right") is False:
            out.append(Fact("wrong_read", [r.seq], r.ts, about_him=True))
        elif k == "reward_tick" and abs(float(b.get("r") or 0)) > SWING:
            rr = float(b["r"])
            out.append(
                Fact(
                    "swing",
                    [r.seq],
                    r.ts,
                    {"r": abs(rr), "time": _hm(r.ts)},
                    words={"dir": "fell" if rr < 0 else "rose"},
                )
            )
        elif k == "mind_feeling" and b.get("label") not in (None, "none"):
            out.append(
                Fact(
                    "feeling",
                    [r.seq],
                    r.ts,
                    {
                        "valence": float(b.get("valence") or 0),
                        "r": float(b.get("r") or 0),
                        "neg": float(b.get("neg") or 0),
                    },
                    words={"object": _word(b.get("object"))},
                    label=_word(b.get("label")),
                )
            )
        elif k == "mind_act" and b.get("klass") in ("R2", "R3"):
            out.append(Fact("act", [r.seq], r.ts, words={"klass": _word(b["klass"]), "what": _word(b.get("action"))}))
        elif k.startswith("proposal_"):
            out.append(Fact("proposal", [r.seq], r.ts, words={"what": _word(k[9:])}))
    return sorted(out, key=lambda f: f.t)


def _spans(c) -> list:
    from kurooto.mind import stops

    try:
        return stops.spans(
            c.log(0, stops.STOP_KINDS if hasattr(stops, "STOP_KINDS") else None, 5000), now=now().timestamp()
        )
    except Exception:
        return []


def _frozen(spans, t: float) -> bool:
    from kurooto.mind import stops

    try:
        return stops.frozen(spans, t)
    except Exception:
        return False


# ------------------------------------------------------------------------------------------------------ the words
def words_for(f: Fact) -> str:
    """The fixed sentence for a fact."""
    t = TEMPLATES[f.kind]
    w = {k: v.replace("_", " ").replace(".", " ") for k, v in f.words.items()}
    nums = f.nums
    hm = lambda m: f"{int(m) // 60 % 24:02d}:{int(m) % 60:02d}"  # noqa: E731
    return t.format(
        due=hm(nums.get("due", 0)),
        time=hm(nums.get("time", 0)),
        r=f"{nums.get('r', 0):.2f}",
        dir=w.get("dir", ""),
        cause=" because the computer was off" if f.cause == "stop" else "",
        label=f.label,
        what=w.get("what", ""),
        object=w.get("object", ""),
        klass=w.get("klass", ""),
    )


def _template_vocab() -> set[str]:
    v = set(FUNCTION)
    for t in TEMPLATES.values():
        v |= {w.lower() for w in WORD.findall(re.sub(r"\{[^}]*\}", " ", t))}
    v |= {"computer", "off", "promises", "slack", "fell", "rose", "drive", "moved", "my", "read", "you", "day"}
    v |= {"because", "since", "due"}  # the causal words (their claims are checked against the fact's cause)
    return v


BASE_VOCAB = _template_vocab()


# ----------------------------------------------------------------------------------------------------- the checks
def check(f: Fact, sentence: str, seqs_exist: set[int] | None = None) -> str:
    """ "" when the sentence passes every rule for this fact, else the name of the first rule it breaks."""
    s = sentence.strip()
    if not s:
        return "empty"
    nums = f.numbers()
    for n in NUMBER.findall(s):
        if n not in nums:
            return "number"  # every number equals a number in its fact
    m = CAUSAL.search(s)
    if m:
        if not f.cause:
            return "cause"  # it claims a cause the fact doesn't have
        after = {w.lower() for w in WORD.findall(s[m.end() :])}
        if not (after & CAUSES.get(f.cause, set()) - {"was"}):
            return "cause"
    toks = [w.lower() for w in WORD.findall(s)]
    allowed = BASE_VOCAB | f.tokens()
    for w in toks:
        if w in FEELING_WORDS:
            if not _feeling_ok(f, w):
                return "feeling"  # a feeling word only for a state above its threshold, at that time
        elif w not in allowed:
            return "invented"  # a word the sentence has no business with: an invented event or name
    if seqs_exist is not None and not set(f.seqs) <= seqs_exist:
        return "seq"  # the cited records must exist in the log
    return ""


def _feeling_ok(f: Fact, word: str) -> bool:
    if f.kind != "feeling" or f.label != word:
        return False
    n, th = f.nums, feelings.THRESHOLDS
    return {
        "uneasy": n.get("valence", 0) < th["uneasy"],
        "satisfied": n.get("valence", 0) > th["satisfied"],
        "relieved": n.get("r", 0) >= th["relieved_r"],
        "frustrated": n.get("neg", 0) >= th["frustrated_n"],
    }.get(word, False)


def fact_dict(f: Fact) -> dict:
    return {"kind": f.kind, "seqs": f.seqs, "t": f.t, "nums": f.nums, "words": f.words, "cause": f.cause,
            "label": f.label, "about_him": f.about_him}  # fmt: skip


def fact_of(d: dict) -> Fact:
    return Fact(d["kind"], list(d["seqs"]), float(d["t"]), dict(d.get("nums") or {}), dict(d.get("words") or {}),
                d.get("cause", ""), d.get("label", ""), bool(d.get("about_him")))  # fmt: skip


def _fact_json(f: Fact) -> str:
    return json.dumps(
        {"kind": f.kind, "nums": f.nums, "words": f.words, "cause": f.cause, "label": f.label}, sort_keys=True
    )


def entails(app: App, f: Fact, sentence: str) -> bool | None:
    """The second net: does the sentence follow from the fact? A yes or no from the model on this computer; None without
    one."""
    from kurooto.mind import tone

    mdl = tone.model(app)
    if not mdl:
        return None
    fact = json.dumps(
        {"kind": f.kind, "nums": f.nums, "words": f.words, "cause": f.cause, "label": f.label}, sort_keys=True
    )
    body = {
        "model": mdl,
        "prompt": (
            f"Fact: {fact}\nSentence: {sentence}\n"
            "Does the sentence follow from the fact, adding nothing? Answer yes or no.\nAnswer:"
        ),
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "num_predict": 2},
    }
    try:
        with app.modules["local_models"].api("/api/generate", body, timeout=60) as r:
            return str(json.loads(r.read()).get("response", "")).strip().lower().startswith("yes")
    except Exception:
        return None


def wording(app: App, f: Fact, use_model: bool = True) -> tuple[str, bool]:
    """(the sentence, whether a model line was swapped): the model's sentence when it passes every check and the
    entailment question, else the fixed one."""
    fixed = words_for(f)
    if not use_model:
        return fixed, False
    from kurooto.mind import tone

    mdl = tone.model(app)
    if not mdl:
        return fixed, False
    body = {
        "model": mdl,
        "prompt": "Write this fact in first person, in plain words, without adding anything. One sentence.\n"
        f"Fact: {_fact_json(f)}\nSentence:",
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "num_predict": 40},
    }
    try:
        with app.modules["local_models"].api("/api/generate", body, timeout=60) as r:
            said = " ".join(str(json.loads(r.read()).get("response", "")).split())
    except Exception:
        return fixed, False
    if not said or check(f, said) or entails(app, f, said) is False:
        return fixed, True  # a failing line is deleted, not rewritten: the fixed sentence takes its place (coverage)
    return said, False


# ---------------------------------------------------------------------------------------------------- the day file
def folder(app: App):
    d = app.paths.state / DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_day(app: App, day: dt.date | None = None, use_model: bool = True) -> dict | None:
    """Write the day's journal: a line per required fact (and the feeling arc), each citing its log records. Returns
    {path, lines, rejected} or None when it's off."""
    if not mind.part_on(app, "journal"):
        return None
    day = day or now().date()
    facts = manifest(app, day)
    c = mind.connect(app)
    verified = c.verify().ok
    exist = {r.seq for r in c.log(0, None, 5000)}
    lines, rejected = [], 0
    for f in facts:
        text, swapped = wording(app, f, use_model)
        rejected += 1 if swapped else 0
        bad = check(f, text, exist) or ("log" if not verified else "")
        if bad:
            rejected += 1
            text = words_for(f)
            bad = check(f, text, exist) or ("log" if not verified else "")
        if bad:  # even the fixed sentence fails (the log doesn't verify): the line isn't written
            continue
        lines.append(
            {
                "text": text, "seqs": f.seqs, "kind": f.kind, "about_him": f.about_him, "struck": False,
                "day": day.isoformat(), "fact": fact_dict(f),
            }
        )  # fmt: skip
    out = {"day": day.isoformat(), "lines": lines, "rejected": rejected, "facts": len(facts)}
    jsave(folder(app) / f"{day.isoformat()}.json", out)
    (folder(app) / f"{day.isoformat()}.md").write_text(render(out), encoding="utf-8")
    _index(app, out)
    if app.settings.get("mind.journal.in_notes"):
        _into_notes(app, day, out)
    return {"path": str(folder(app) / f"{day.isoformat()}.md"), "lines": len(lines), "rejected": rejected}


def render(entry: dict) -> str:
    rows = [f"# Kurooto's journal, {entry['day']}", ""]
    if not entry["lines"]:
        rows.append("Nothing happened that I had to write down.")
    for i, ln in enumerate(entry["lines"], 1):
        cite = ", ".join(f"#{s}" for s in ln["seqs"])
        rows.append(f"{i}. ~~{ln['text']}~~ (struck)" if ln.get("struck") else f"{i}. {ln['text']} [{cite}]")
    return "\n".join(rows) + "\n"


def _index(app: App, entry: dict) -> None:
    f = folder(app) / "index.json"
    idx = jload(f, {}) or {}
    idx[entry["day"]] = {"lines": len(entry["lines"]), "rejected": entry["rejected"], "facts": entry["facts"]}
    jsave(f, idx)


def _into_notes(app: App, day: dt.date, entry: dict) -> None:
    from pathlib import Path

    from kurooto.core import graphwrite

    path = Path(app.workspace) / "Kurooto journal.md"
    text = path.read_text(encoding="utf-8") if path.exists() else "# Kurooto's journal\n\n"
    path.write_text(graphwrite.put_block(text, "journal", render(entry)), encoding="utf-8")


def read_day(app: App, day: dt.date) -> dict | None:
    return jload(folder(app) / f"{day.isoformat()}.json", None)


def strike(app: App, day: dt.date, n: int) -> str:
    """Strike line n: it stays as a tombstone. A line about you also forgets that day's read (stage 04's cascade)."""
    e = read_day(app, day)
    if not e or not 1 <= n <= len(e["lines"]):
        return "No such line."
    ln = e["lines"][n - 1]
    ln["struck"] = True
    jsave(folder(app) / f"{day.isoformat()}.json", e)
    (folder(app) / f"{day.isoformat()}.md").write_text(render(e), encoding="utf-8")
    if ln.get("about_him"):
        from kurooto.mind import mood

        mood.forget_day(app, day.isoformat())
    return f"Struck line {n}."


# ------------------------------------------------------------------------------------------- the mutation suite


def mutations(f: Fact, sentence: str) -> list[tuple[str, str]]:
    """Corrupted copies of a true sentence: a changed number, a swapped cause, a feeling on a state below its threshold,
    an
    invented event, reordered times."""
    out: list[tuple[str, str]] = []
    if NUMBER.search(sentence):
        out.append(("number", NUMBER.sub(lambda m: str(int(re.sub(r"\D", "", m[0]) or 0) + 7), sentence)))
        t = re.search(r"\b(\d{2}):(\d{2})\b", sentence)
        if t:
            out.append(
                ("times", sentence.replace(t[0], f"{t[2]}:{t[1]}") if t[1] != t[2] else sentence.replace(t[0], "99:99"))
            )
    out.append(("cause", sentence.rstrip(".") + " because you were asleep."))
    out.append(
        (
            "feeling",
            "I was frustrated and " + sentence[0].lower() + sentence[1:]
            if f.kind != "feeling"
            else sentence.replace(f.label, "excited"),
        )
    )
    out.append(("invented", sentence.rstrip(".") + ". I also called you twice at night."))
    return out


def rates(facts: list[Fact], exist: set[int] | None = None) -> dict:
    """The checker's rates over the fixed sentences of these facts and their corrupted copies."""
    kept = total_true = rejected = total_bad = 0
    for f in facts:
        s = words_for(f)
        total_true += 1
        kept += 0 if check(f, s, exist) else 1
        for _k, m in mutations(f, s):
            if m == s:
                continue
            total_bad += 1
            rejected += 1 if check(f, m, exist) else 0
    return {
        "kept": round(kept / total_true, 4) if total_true else 1.0,
        "rejected": round(rejected / total_bad, 4) if total_bad else 1.0,
        "n_true": total_true, "n_bad": total_bad,
    }  # fmt: skip


def selfcheck(app: App, day: dt.date | None = None) -> dict | None:
    """Nightly: the checker against corrupted copies of that night's facts. Below the bars, learning freezes and a
    morning
    line says so."""
    if not mind.part_on(app, "journal"):
        return None
    day = day or now().date()
    facts = manifest(app, day)
    exist = {r.seq for r in mind.connect(app).log(0, None, 5000)}
    r = rates(facts, exist)
    app.events.emit("journal_selfcheck", kept=r["kept"], rejected=r["rejected"], n=r["n_true"])
    if r["n_true"] and (r["rejected"] < REJECT_MIN or r["kept"] < KEEP_MIN):
        mind.connect(app).report("learning_freeze", {"why": "journal"})
        app.notify(
            "My journal's own checks slipped tonight, so I've stopped learning until they hold again.",
            kind="info",
            why="mind.journal_check",
        )
    return r
