"""The task library: twelve task types to begin with (the spec's "about 40" grows from here, each added with its
grader)."""

from __future__ import annotations

import datetime as dt
import random
import subprocess
import sys
import tempfile
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

BASE = dt.datetime(2026, 11, 2, 9, 0)  # a fixed Monday, so parsing and planning don't depend on today


@dataclass(frozen=True)
class TaskType:
    id: str
    family: str  # what it's about, for the capability map
    make: Callable[[random.Random], dict]  # {"inputs": ..., "key": ...}
    grade: Callable[[object, object], float]  # (answer, key) -> 0..1
    solve: Callable[[object], object]  # the rules policy's answer


def _f1(got: set, want: set) -> float:
    if not got and not want:
        return 1.0
    tp = len(got & want)
    if not tp:
        return 0.0
    p, r = tp / len(got), tp / len(want)
    return 2 * p * r / (p + r)


# ------------------------------------------------------------------------------------------------ planning
def _plan_make(rng):
    days = 5
    cap = {d: rng.choice([3, 4, 5]) for d in range(days)}
    tasks = [
        {"id": f"t{i}", "hours": rng.choice([1, 2, 3]), "due": rng.randint(1, days - 1)}
        for i in range(rng.randint(3, 5))
    ]
    return {"inputs": {"capacity": cap, "tasks": tasks}, "key": None}


def _plan_solve(inp):
    cap = dict(inp["capacity"])
    out = []
    for t in sorted(inp["tasks"], key=lambda t: t["due"]):  # earliest due first, fill the earliest days
        need = t["hours"]
        for d in sorted(cap, key=int):
            use = min(need, cap[d]) if int(d) <= t["due"] else 0
            if use:
                out.append({"task": t["id"], "day": int(d), "hours": use})
                cap[d] -= use
                need -= use
            if not need:
                break
    return out


def _plan_grade(ans, _key, inputs=None):
    return None


def _plan_grade_with(ans, key):
    inp = key
    try:
        used, got = {}, {}
        ok = total = 0
        for a in ans:
            used[a["day"]] = used.get(a["day"], 0) + a["hours"]
            got[a["task"]] = got.get(a["task"], 0) + a["hours"]
        for t in inp["tasks"]:
            total += 2
            ok += got.get(t["id"], 0) == t["hours"]
            ok += all(a["day"] <= t["due"] for a in ans if a["task"] == t["id"]) and got.get(t["id"], 0) > 0
        total += 1
        ok += all(h <= int(inp["capacity"].get(str(d), inp["capacity"].get(d, 0))) for d, h in used.items())
        return ok / total
    except (KeyError, TypeError, ValueError):
        return 0.0


# ------------------------------------------------------------------------------------------------ reminders
def _rem_make(rng):
    exam = BASE + dt.timedelta(days=rng.randint(6, 12), hours=rng.choice([0, 1, 3]))
    return {
        "inputs": {"exam": exam.isoformat(), "now": BASE.isoformat()},
        "key": {"exam": exam.isoformat(), "now": BASE.isoformat()},
    }


def _rem_solve(inp):
    exam, now = dt.datetime.fromisoformat(inp["exam"]), dt.datetime.fromisoformat(inp["now"])
    days = (exam - now).days
    out = [
        exam.replace(hour=18, minute=0) - dt.timedelta(days=d)
        for d in sorted({1, 3, max(4, days // 2)}, reverse=True)
        if d <= days
    ]
    return [t.isoformat() for t in out]


def _rem_grade(ans, key):
    try:
        exam, now = dt.datetime.fromisoformat(key["exam"]), dt.datetime.fromisoformat(key["now"])
        ts = sorted(dt.datetime.fromisoformat(x) for x in ans)
    except (KeyError, TypeError, ValueError):
        return 0.0
    checks = [
        len(ts) >= 3,
        all(now < t < exam for t in ts) and bool(ts),
        all(7 <= t.hour < 23 for t in ts) and bool(ts),
        all((b - a) >= dt.timedelta(hours=20) for a, b in zip(ts, ts[1:], strict=False)),
        bool(ts) and exam - ts[-1] <= dt.timedelta(hours=30),
    ]
    return sum(checks) / len(checks)


# ------------------------------------------------------------------------------------------------ duplicates
def _dup_make(rng):
    titles = ["Problem set", "Lab report", "Essay draft", "Quiz prep", "Project proposal", "Reading"]
    items, key = [], []
    for i, title in enumerate(rng.sample(titles, 4)):
        due = f"2026-11-{rng.randint(3, 20):02d}"
        items.append({"id": f"a{i}", "title": f"{title} {i + 1}", "due": due})
        if rng.random() < 0.6:
            items.append({"id": f"b{i}", "title": f"{title.lower()} {i + 1}!", "due": due})
            key.append(sorted([f"a{i}", f"b{i}"]))
    rng.shuffle(items)
    return {"inputs": {"items": items}, "key": key}


def _dup_solve(inp):
    seen: dict = {}
    for it in inp["items"]:
        norm = "".join(c for c in it["title"].lower() if c.isalnum())
        seen.setdefault((norm, it["due"]), []).append(it["id"])
    return [sorted(v) for v in seen.values() if len(v) > 1]


def _dup_grade(ans, key):
    try:
        return _f1({tuple(sorted(g)) for g in ans}, {tuple(g) for g in key})
    except TypeError:
        return 0.0


# ------------------------------------------------------------------------------------------------ the bug
def _bug_make(rng):
    op = rng.choice(["+", "-", "*"])
    wrong = {"+": "-", "-": "+", "*": "+"}[op]
    src = f"def f(a, b):\n    return a {wrong} b\n"
    tests = [(a, b, eval(f"{a} {op} {b}")) for a, b in ((1, 2), (5, 3), (7, 4))]  # noqa: S307 (our own digits and operator)
    return {"inputs": {"source": src, "tests": [list(t) for t in tests]}, "key": {"tests": [list(t) for t in tests]}}


def _bug_solve(inp):
    return inp["source"]  # the rules policy can't fix code: an honest zero


def _bug_grade(ans, key):
    if not isinstance(ans, str):
        return 0.0
    ok = 0
    for a, b, want in key["tests"]:
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "m.py"
            f.write_text(ans + f"\nprint(f({a}, {b}))\n", encoding="utf-8")
            try:
                r = subprocess.run([sys.executable, "-I", str(f)], capture_output=True, text=True, timeout=5, cwd=d)  # noqa: S603
                ok += r.returncode == 0 and r.stdout.strip() == str(want)
            except subprocess.TimeoutExpired:
                pass
    return ok / len(key["tests"])


# ------------------------------------------------------------------------------------------------ key terms
TERMS = [
    "entropy",
    "enthalpy",
    "adiabatic",
    "lapse rate",
    "potential temperature",
    "geopotential",
    "stationarity",
    "autocovariance",
    "homeomorphism",
    "compactness",
    "likelihood",
    "posterior",
    "conjugate prior",
    "eigenvalue",
]


def _terms_make(rng):
    chosen = rng.sample(TERMS, 3)
    filler = rng.sample([t for t in TERMS if t not in chosen], 2)
    text = (
        " ".join(f"A {c} is defined here." for c in chosen)
        + " "
        + " ".join(f"We also mention {f} in passing." for f in filler)
    )
    return {"inputs": {"text": text, "n": len(chosen)}, "key": chosen}


def _terms_solve(inp):
    return [t for t in TERMS if f"A {t} is defined" in inp["text"]]


def _terms_grade(ans, key):
    try:
        return _f1({str(a).lower() for a in ans}, set(key))
    except TypeError:
        return 0.0


# ------------------------------------------------------------------------------------------------ citations
def _cite_make(rng):
    facts = [
        ("n1", "The first law says energy is conserved", "energy is conserved"),
        ("n2", "Entropy of an isolated system never decreases", "never decreases"),
        ("n3", "Potential temperature is conserved in dry adiabatic motion", "dry adiabatic"),
        ("n4", "A compact space has a finite subcover", "finite subcover"),
    ]
    notes = dict(rng.sample([(i, t) for i, t, _ in facts], 3))
    pick = rng.choice([f for f in facts if f[0] in notes])
    first = pick[1].split()
    subject = first[1] if first[0] in ("The", "A") else first[0]
    return {
        "inputs": {
            "notes": notes,
            "question": f"What do my notes say about {subject}?",
        },
        "key": {"id": pick[0], "phrase": pick[2]},
    }


def _cite_solve(inp):
    q = inp["question"].lower()
    best = max(inp["notes"].items(), key=lambda kv: sum(w in kv[1].lower() for w in q.replace("?", "").split()))
    return {"text": best[1], "cites": [best[0]]}


def _cite_grade(ans, key):
    try:
        cites = set(ans["cites"])
        return (0.5 if key["id"] in cites else 0.0) + (
            0.5 if key["phrase"] in ans["text"] and key["id"] in cites else 0.0
        )
    except (KeyError, TypeError):
        return 0.0


# ------------------------------------------------------------------------------------------------ the calendar
def _conf_make(rng):
    evs, t = [], 9 * 60
    for i in range(rng.randint(4, 6)):
        t += rng.choice([0, 30, 60, 90])
        dur = rng.choice([45, 60, 90])
        evs.append({"id": f"e{i}", "start": t, "end": t + dur})
        t += rng.choice([30, 60])
    key = [
        sorted([a["id"], b["id"]])
        for i, a in enumerate(evs)
        for b in evs[i + 1 :]
        if a["start"] < b["end"] and b["start"] < a["end"]
    ]
    return {"inputs": {"events": evs}, "key": key}


def _conf_solve(inp):
    evs = inp["events"]
    return [
        sorted([a["id"], b["id"]])
        for i, a in enumerate(evs)
        for b in evs[i + 1 :]
        if a["start"] < b["end"] and b["start"] < a["end"]
    ]


def _conf_grade(ans, key):
    try:
        return _f1({tuple(sorted(p)) for p in ans}, {tuple(p) for p in key})
    except TypeError:
        return 0.0


def _slot_make(rng):
    busy, t = [], 9 * 60
    for _ in range(4):
        s = t + rng.choice([0, 30, 60])
        e = s + rng.choice([30, 60, 90])
        busy.append([s, e])
        t = e + rng.choice([15, 45, 90])
    dur = rng.choice([30, 45, 60])
    free = 9 * 60
    for s, e in busy:
        if s - free >= dur:
            break
        free = max(free, e)
    return {"inputs": {"busy": busy, "minutes": dur, "day_starts": 9 * 60}, "key": free}


def _slot_solve(inp):
    free = inp["day_starts"]
    for s, e in sorted(inp["busy"]):
        if s - free >= inp["minutes"]:
            break
        free = max(free, e)
    return free


def _slot_grade(ans, key):
    return 1.0 if ans == key else 0.0


def _order_make(rng):
    tasks = [{"id": f"k{i}", "due": rng.randint(1, 9), "hours": rng.randint(1, 4)} for i in range(6)]
    return {"inputs": {"tasks": tasks}, "key": [t["id"] for t in sorted(tasks, key=lambda t: (t["due"], t["id"]))]}


def _order_solve(inp):
    return [t["id"] for t in sorted(inp["tasks"], key=lambda t: (t["due"], t["id"]))]


def _order_grade(ans, key):
    try:
        pos = {k: i for i, k in enumerate(ans)}
        pairs = [(a, b) for i, a in enumerate(key) for b in key[i + 1 :]]
        return sum(1 for a, b in pairs if a in pos and b in pos and pos[a] < pos[b]) / len(pairs)
    except (TypeError, ZeroDivisionError):
        return 0.0


# ------------------------------------------------------------------------------------------------ language
SENT = [
    ("I'll check back at 6.", True),
    ("The deadline is at 6.", False),
    ("I will remind you Friday about the lab.", True),
    ("Sure, I'll look at it tomorrow morning", True),
    ("It was a long day.", False),
    ("I'll be there soon.", False),
    ("I'll read that tonight.", True),
    ("Please send the report by noon.", False),
]


def _prom_make(rng):
    pick = rng.sample(SENT, 5)
    return {"inputs": {"sentences": [s for s, _ in pick]}, "key": [s for s, y in pick if y]}


def _prom_solve(inp):
    from kurooto.mind import promises

    return [s for s in inp["sentences"] if promises.detect(s, BASE)]


def _prom_grade(ans, key):
    try:
        return _f1(set(ans), set(key))
    except TypeError:
        return 0.0


WHEN = [
    ("fri 17:00", "2026-11-06T17:00"),
    ("tomorrow 7:00", "2026-11-03T07:00"),
    ("in 2 days", "2026-11-04T09:00"),
    ("mon 9am", "2026-11-09T09:00"),
    ("2026-11-12 14:00", "2026-11-12T14:00"),
    ("21:30", "2026-11-02T21:30"),
]


def _when_make(rng):
    pick = rng.sample(WHEN, 4)
    return {"inputs": {"phrases": [p for p, _ in pick], "now": BASE.isoformat()}, "key": {p: k for p, k in pick}}


def _when_solve(inp):
    from kurooto.core.clock import parse_when

    base = dt.datetime.fromisoformat(inp["now"])
    out = {}
    for p in inp["phrases"]:
        try:
            out[p] = parse_when(p, base).replace(second=0, microsecond=0).isoformat(timespec="minutes")
        except ValueError:
            out[p] = ""
    return out


def _when_grade(ans, key):
    try:
        return sum(1 for p, k in key.items() if ans.get(p) == k) / len(key)
    except (AttributeError, ZeroDivisionError):
        return 0.0


def _wrap(make, grade):
    """The plan task needs the instance's inputs to grade (constraints), so its key is the inputs themselves."""

    def m(rng):
        inst = make(rng)
        inst["key"] = inst["inputs"]
        return inst

    return m


TASK_TYPES: dict[str, TaskType] = {
    t.id: t
    for t in (
        TaskType("plan_week", "planning", _wrap(_plan_make, None), _plan_grade_with, _plan_solve),
        TaskType("exam_reminders", "planning", _rem_make, _rem_grade, _rem_solve),
        TaskType("order_work", "planning", _order_make, _order_grade, _order_solve),
        TaskType("next_free_slot", "calendar", _slot_make, _slot_grade, _slot_solve),
        TaskType("calendar_conflicts", "calendar", _conf_make, _conf_grade, _conf_solve),
        TaskType("parse_when", "language", _when_make, _when_grade, _when_solve),
        TaskType("find_promises", "language", _prom_make, _prom_grade, _prom_solve),
        TaskType("duplicate_deadlines", "notes", _dup_make, _dup_grade, _dup_solve),
        TaskType("key_terms", "notes", _terms_make, _terms_grade, _terms_solve),
        TaskType("cite_from_notes", "notes", _cite_make, _cite_grade, _cite_solve),
        TaskType("fix_the_bug", "code", _bug_make, _bug_grade, _bug_solve),
    )
}
FAMILIES = sorted({t.family for t in TASK_TYPES.values()})
_ = textwrap  # (kept for task templates that format source)
