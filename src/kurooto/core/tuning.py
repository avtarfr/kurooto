"""Dream RSI, part three: part two's nightly replay (core/policy.py, when its messages reach you) applied to Kurooto's
other recorded decisions, and changes to skills proposed from repeated failures.

Three more areas, each with its own switch, each tuning one setting from what was recorded (the last 45 days):
    effort     (dreaming.tune_effort, on) the effort your own requests get, per what picked it (providers/effort.py:
               the notes rule, or the quick check's low / medium / high): brain.effort_map. Scored on your requests
               by retries (the same request again within RETRY_MIN), the Wrong button, "that's not what I asked"
               (heard(): the words are kept on the request, forgotten with it) and run time. A typed "high:" is
               never tuned, and work nobody is waiting for keeps the quick check's pick.
    fallbacks  (dreaming.tune_fallbacks, on) the order of the AIs at an effort level: brain.fallback_first lists the
               levels at which the fallback is tried before the main AI. Scored by every try recorded per AI
               (attempts in jobs.db): answers, failures, limits, timeouts and their time.
    sizing     (dreaming.tune_sizing, on) Start-by's guess of how long each kind of deadline takes (startby.sizes):
               planned hours against actual ones, from study time on the deadline's subject between its start-by
               date and when it was done (or, with parts, extrapolated from "4/7" progress) and from sizes you
               tapped for a deadline. A size you set yourself is never changed.
Each area replays today's rules and a few one-setting variants against what actually happened. A choice that wasn't
made is estimated from what was recorded nearby, said plainly: an effort level a request didn't run at, from what that
level did on other requests (more effort fixes half of the misses, MORE_FIXES; less breaks at least LESS_BREAKS of the
answers that went well, or that level's own miss rate); an AI that wasn't tried, as limited when it hit a limit in the
LIMIT_H hours before, else from its own record at that level. Today's rules are always a candidate, so a change is
never worse on the replay.

One change a night across all of them (night(), from Dreaming's morning message): part two's round (policy.consider)
and each area's best variant; of those that beat today's by their margin, the one that wins by the most (as a multiple
of its margin) is applied through Calm.apply (Undo: calm:<uid>:undo) and said in one line. The others wait.

Improving how it improves: every applied change's later outcome is kept (review()): still in place after KEPT_DAYS is
"kept", undone or put back by hand is "undone". The margin for a kind of change (effort.up, fallbacks.first,
sizing.down, messages.habituate, prompts...) is dreaming.tune_margin times trust(), 1 + undone - kept/2, between 1 and
MAX_TRUST: a kind you undid needs a clearer win next time; one you kept earns some of that back. A target whose change
was undone is left alone for BLOCK_DAYS.

Proposals (dreaming.propose_prompts, off): when a skill's answers were corrected, marked Wrong or asked again
REPEAT times or more in the last FAIL_DAYS days, the night asks the second-look AI (Learning's) for the skill with the
failing step rewritten, and for each past failure whether the rewrite fixes it. Offered only when it fixes at least
half of them (more for a kind you said No to or undid: trust()), in the morning message with Apply and No; never
applied without your tap. Apply changes the skill through Learning (before-copy, Undo) and replays your test cases
(modules/cases.py); if one that passed goes wrong, the change is put back at once. /dream proposal shows it.

State: <state>/dream-tuning.json (the day, the decisions, the outcomes per kind, the proposal) and
<state>/tuning/proposal-<id>.md (the proposed skill). /dream policy shows the rules and the decisions.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import statistics
import uuid
from typing import TYPE_CHECKING

from kurooto.core import policy
from kurooto.core.calm import Change
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "dreaming",
    {
        "tune_effort": True,  # each night, replay your requests and tune the effort they get (one change, Undo)
        "tune_fallbacks": True,  # each night, replay every try per AI and tune which AI goes first at each effort
        "tune_sizing": True,  # each night, compare Start-by's sizes with the time deadlines took and tune them
        "propose_prompts": False,  # propose a fix to a skill that keeps going wrong (Apply or No; never by itself)
    },
)

BY = "dreaming.tuning"  # what Calm records as the change's cause (its Undo)
RECORD_DAYS = 45
KEEP_DECISIONS = 60
KEPT_DAYS = 14  # a change still in place this long is "kept"
BLOCK_DAYS = 30
MAX_TRUST = 4.0
LEVELS = ("low", "medium", "high")
ORIGINS = {"low": "low", "medium": "medium", "high": "high", "notes": "high"}  # what picked it -> its own level
CHANGE = {"effort": 0.5, "fallbacks": 0.5, "sizing": 0.5}

# effort
MIN_ASKS = 8  # judged requests from one origin before anything is proposed for it
RETRY_MIN = 15  # the same request again this soon: the first one missed
SIMILAR = 0.6  # word overlap that makes two requests the same
GOOD, MINUTE, OTHER_MISS = 1.0, 0.1, 2.5
MISS = {"wrong": 3.0, "corrected": 3.0, "retried": 2.0, "empty": 2.0, "timeout": 2.0, "stuck": 2.0}
MORE_FIXES, LESS_BREAKS = 0.5, 0.15
TIME = {"low": 1.0, "medium": 2.0, "high": 4.0}  # relative run time when too little was recorded
JUDGED_VERDICTS = ("ok", "empty", "timeout", "stuck")  # limits, sign-outs and errors aren't the effort's doing

# fallbacks
MIN_JOBS, MIN_FAILS, MIN_TRIES = 6, 3, 3
LIMIT_H = 2.0
ANSWER, FAIL, TRY = 1.0, 2.0, 0.5  # a wasted try: a request used up, often a limit told
RETRY_VERDICTS = ("rate_limited", "auth", "error", "denied", "empty")  # core/jobs.py:RETRY: the next AI tries

# sizing
MIN_SAMPLES = 4
SPAN_DAYS = 14  # a deadline without a start-by date: its work counted from this long before it was due
UNDER = 1.5  # a size too small costs more than one too big (you'd start too late)
SIZE_DAYS = 90

# proposals
REPEAT, FAIL_DAYS, PROPOSE_EVERY_DAYS, PROPOSAL_DAYS = 2, 14, 7, 7
FIX_SHARE = 0.5

CORRECTS = re.compile(
    r"^\s*(?:that'?s not what i (?:asked|meant|wanted)|not what i (?:asked|meant|wanted)|you misunderstood|"
    r"(?:that|this|it) (?:is|was|'s) (?:wrong|not right|incorrect|not what i (?:asked|meant|wanted))|"
    r"that'?s (?:wrong|not right|incorrect)|wrong answer|i (?:asked|meant) (?:for|about)\b|"
    r"no,\s+(?:\S+\s+){2,}\S+)",
    re.I,
)

PROPOSE = """An AI assistant (Kurooto) runs a skill when its user types /{name}: the instructions below. Lately its
answers went wrong {n} times: the user corrected them, marked them Wrong or asked again. Rewrite the skill so these
would go right, changing only what has to change.

The skill file now:
{text}

What went wrong (numbered):
{cases}

Reply in exactly this shape and nothing else:

CHANGE: <one short sentence: what you changed and why>
FIXES 1: yes|no
FIXES 2: yes|no
(one line per case above: would following the rewritten skill have avoided it?)
```skill
<the whole skill file, the header between the --- lines included>
```

Keep its name, its header and everything that works. If nothing in the skill caused these, answer only NONE: <why>.
No health, money or other people's private details."""


def state_file(app: App):
    return app.paths.state / "dream-tuning.json"


def _load(app: App) -> dict:
    return jload(state_file(app), {}) or {}


def _save(app: App, st: dict) -> None:
    jsave(state_file(app), st)


def _since() -> float:
    return (now() - dt.timedelta(days=RECORD_DAYS)).timestamp()


def _days(first_ts: float | None) -> int:
    return max(1, round((now().timestamp() - first_ts) / 86400)) if first_ts else 0


def _rows(app: App, sql: str, args: tuple = ()) -> list:
    return app.jobs._read(sql, args, one=False)


# ------------------------------------------------------------------------------------------- trust
def trust(st: dict, kind: str) -> float:
    """How much clearer a win a kind of change needs than dreaming.tune_margin: 1 + undone - kept/2, 1 to MAX_TRUST."""
    o = (st.get("outcomes") or {}).get(kind) or {}
    return min(MAX_TRUST, max(1.0, 1.0 + int(o.get("undone") or 0) - int(o.get("kept") or 0) / 2))


def _outcome(st: dict, kind: str, what: str) -> None:
    o = st.setdefault("outcomes", {}).setdefault(kind, {"kept": 0, "undone": 0})
    o[what] = int(o.get(what) or 0) + 1


def live(app: App, d: dict) -> bool:
    """Is an applied decision's change still in place?"""
    area, target = d.get("area"), d.get("target")
    if area == "messages":
        return policy.live(app, d)
    if area == "effort":
        return (app.settings.get("brain.effort_map") or {}).get(target) == d.get("set")
    if area == "fallbacks":
        return (target in (app.settings.get("brain.fallback_first") or [])) == bool(d.get("set"))
    if area == "sizing":
        try:
            return float(app.settings.get(f"startby.sizes.{target}")) == float(d.get("set"))
        except (TypeError, ValueError):
            return False
    if area == "prompts":
        lrn = app.modules.get("learning")
        c = next((x for x in (lrn.changes() if lrn is not None else []) if x["id"] == d.get("cid")), None)
        return bool(c) and not c.get("undone")
    return True


def review(app: App, st: dict) -> list[dict]:
    """Each applied change's later outcome, once: "undone" when it's no longer in place, "kept" after KEPT_DAYS.
    Returns the decisions that got an outcome now."""
    out = []
    for d in st.get("decisions") or []:
        if not d.get("applied") or d.get("outcome"):
            continue
        age = now() - dt.datetime.fromisoformat(d["at"])
        if not live(app, d):
            d["outcome"] = "undone"
        elif age >= dt.timedelta(days=KEPT_DAYS):
            d["outcome"] = "kept"
        else:
            continue
        d["outcome_at"] = now().isoformat(timespec="seconds")
        _outcome(st, d["trust"], d["outcome"])
        out.append(d)
        app.events.emit("dreaming_outcome", kind=d["trust"], outcome=d["outcome"])
    return out


def blocked(app: App, st: dict, area: str) -> set[str]:
    """Targets of an area whose change was undone (or put back by hand) in the last BLOCK_DAYS days."""
    cutoff = now() - dt.timedelta(days=BLOCK_DAYS)
    return {
        d["target"]
        for d in st.get("decisions") or []
        if d.get("area") == area
        and (d.get("applied") or d.get("declined"))
        and dt.datetime.fromisoformat(d["at"]) >= cutoff
        and (d.get("declined") or not live(app, d))
    }


def _decision(area: str, **kw) -> dict:
    return {"at": now().isoformat(timespec="seconds"), "area": area, "applied": False, **kw}


# ------------------------------------------------------------------------------------------ effort
def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", str(text or "").lower()) if len(w) > 2}


def _same(a: str, b: str) -> bool:
    wa, wb = _words(a), _words(b)
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) >= SIMILAR


def _skill_of(then: str, payload: str) -> str:
    if then not in ("skills.done", "skills.latex"):
        return ""
    try:
        return str((json.loads(payload or "{}") or {}).get("name") or "")
    except ValueError:
        return ""


def _wrong_jobs(app: App) -> dict[str, str]:
    """Requests whose answer you marked Wrong (modules/cases.py): job -> your note."""
    cases = app.modules.get("cases")
    if cases is None:
        return {}
    try:
        cs = cases.store.load()["cases"].values()
    except Exception:
        return {}
    return {c["job"]: str(c.get("note") or "") for c in cs if c.get("wrong") and c.get("job")}


def asks(app: App) -> list[dict]:
    """Your own requests that ended (oldest first), each with how it went: misses (wrong, corrected, retried, or its
    verdict), its minutes, and what picked its effort."""
    got = _rows(
        app,
        "select id, created, coalesce(finished, created), coalesce(effort_from,''), coalesce(effort,''), "
        "coalesce(verdict,''), coalesce(seconds,0), coalesce(corrected,''), prompt, coalesce(then_action,''), "
        "coalesce(then_payload,''), title from jobs where coalesce(lane,'you')='you' "
        "and status in ('ok','failed') and created >= ? order by created",
        (_since(),),
    )
    wrong = _wrong_jobs(app)
    rows = []
    for jid, created, finished, origin, level, verdict, secs, corr, prompt, then, payload, title in got:
        rows.append(
            {
                "id": jid,
                "ts": float(created),
                "end": float(finished),
                "origin": origin,
                "level": level,
                "verdict": verdict,
                "min": float(secs or 0) / 60,
                "corrected": corr,
                "prompt": prompt or "",
                "skill": _skill_of(then, payload),
                "title": title or "",
                "wrong": jid in wrong,
                "note": wrong.get(jid, ""),
                "retried": False,
            }
        )
    for i, r in enumerate(rows):  # the same request (or the same skill) asked again soon after it ended
        for later in rows[i + 1 :]:
            if later["ts"] - r["end"] > RETRY_MIN * 60:
                break
            if later["ts"] < r["end"]:
                continue
            if (r["skill"] and later["skill"] == r["skill"]) or (
                r["prompt"] and later["prompt"] and _same(r["prompt"], later["prompt"])
            ):
                r["retried"] = True
                break
    for r in rows:
        r["misses"] = [k for k in ("wrong", "corrected", "retried") if r[k]]
        if r["verdict"] in MISS:
            r["misses"].append(r["verdict"])
        r["judged"] = r["origin"] in ORIGINS and r["level"] in LEVELS and r["verdict"] in JUDGED_VERDICTS
    return rows


def _miss_weight(r: dict) -> float:
    return max((MISS.get(k, OTHER_MISS) for k in r["misses"]), default=0.0)


def _effort_score(r: dict, level: str, ratio: dict, drop: dict) -> float:
    """One request's score had it run at `level` (as recorded when that's how it ran)."""
    a, w = r["level"], _miss_weight(r)
    if level == a:
        return (-w if r["misses"] else GOOD) - r["min"] * MINUTE
    minutes = r["min"] * ratio[level] / max(ratio[a], 1e-6)
    timeout = r["verdict"] in ("timeout", "stuck")
    if LEVELS.index(level) > LEVELS.index(a):  # more thought: half the misses go right; a timeout stays one
        p = 1.0 if timeout else (1 - MORE_FIXES if r["misses"] else 0.0)
    else:  # less: what went well may go wrong; a timeout may finish
        p = (0.5 if timeout else 1.0) if r["misses"] else drop[level]
    return (1 - p) * GOOD - p * (w or OTHER_MISS) - minutes * MINUTE


def _effort_rates(rows: list[dict]) -> tuple[dict, dict]:
    """(relative run time per level, the miss rate per level), from what was recorded."""
    by = {lv: [r for r in rows if r["judged"] and r["level"] == lv] for lv in LEVELS}
    ratio = dict(TIME)
    med = {lv: statistics.median([r["min"] for r in rs]) for lv, rs in by.items() if len(rs) >= 3}
    if med.get("medium"):
        for lv, m in med.items():
            ratio[lv] = max(0.1, m / med["medium"] * TIME["medium"])
    drop = {lv: max(LESS_BREAKS, sum(bool(r["misses"]) for r in rs) / len(rs)) if rs else LESS_BREAKS
            for lv, rs in by.items()}  # fmt: skip
    return ratio, drop


def effort_replay(rows: list[dict], mapping: dict, ratio: dict, drop: dict) -> float:
    """The record's score had each origin got the level in `mapping`."""
    total = 0.0
    for r in rows:
        if not r["judged"]:
            continue
        total += _effort_score(r, mapping.get(r["origin"]) or ORIGINS[r["origin"]], ratio, drop)
    return total


def _levels(app: App) -> dict:
    """What each origin gets today."""
    m = dict(app.settings.get("brain.effort_map") or {})
    return {o: m.get(o) if m.get(o) in LEVELS else lv for o, lv in ORIGINS.items()}


ORIGIN_SAID = {
    "low": "requests the quick check calls quick",
    "medium": "requests the quick check calls medium",
    "high": "requests the quick check calls hard",
    "notes": "requests to study from your notes",
}


def effort_plan(app: App, st: dict) -> tuple[dict, Change | None] | None:
    if not app.settings.get("dreaming.tune_effort"):
        return None
    rows = asks(app)
    judged = [r for r in rows if r["judged"]]
    cur = _levels(app)
    ratio, drop = _effort_rates(rows)
    base = effort_replay(rows, cur, ratio, drop)
    skip = blocked(app, st, "effort")
    best, best_s, cands = None, base, 0
    for origin in ORIGINS:
        mine = [r for r in judged if r["origin"] == origin]
        if len(mine) < MIN_ASKS or origin in skip:
            continue
        i = LEVELS.index(cur[origin])
        for j in (i + 1, i - 1):
            if not 0 <= j < len(LEVELS):
                continue
            cand = {**cur, origin: LEVELS[j]}
            cands += 1
            s = effort_replay(rows, cand, ratio, drop) - CHANGE["effort"]
            if s > best_s:
                best, best_s = (origin, LEVELS[j], mine), s
    d = _decision("effort", score=round(base, 2), best=round(best_s, 2), candidates=cands + 1, judged=len(judged))
    d["days"] = _days(judged[0]["ts"] if judged else None)
    if best is None:
        return d, None
    origin, level, mine = best
    was = cur[origin]
    up = LEVELS.index(level) > LEVELS.index(was)
    missed = sum(bool(r["misses"]) for r in mine)
    said = f"{ORIGIN_SAID[origin]} now get {level} effort, not {was}"
    if up:
        why = f"{missed} of the last {len(mine)} were asked again, marked Wrong, corrected or ran out of time"
    else:
        saved = sum(r["min"] for r in mine) * (1 - ratio[level] / max(ratio[was], 1e-6))
        why = f"{len(mine) - missed} of the last {len(mine)} went fine, and it saves about {max(1, round(saved))} min"
    new = dict(app.settings.get("brain.effort_map") or {})
    if level == ORIGINS[origin]:
        new.pop(origin, None)
    else:
        new[origin] = level
    d.update(target=origin, set=level if level != ORIGINS[origin] else None, said=said, why=why)
    d["trust"] = "effort.up" if up else "effort.down"
    return d, Change(said, key="brain.effort_map", value=new)


# --------------------------------------------------------------------------------------- fallbacks
def _brains(app: App) -> tuple[str, str] | None:
    m, f = app.settings.get("brain.main") or "", app.settings.get("brain.fallback") or ""
    return (m, f) if m and f and m != f else None


def tries(app: App) -> list[dict]:
    """Every request (not pinned to an AI) with its tries in order: [(brain, verdict, seconds, at)]."""
    jobs = {
        jid: {"id": jid, "level": lv, "ts": float(c), "tries": []}
        for jid, lv, c in _rows(
            app,
            "select id, coalesce(effort,''), created from jobs where created >= ? and coalesce(brain_req,'')='' "
            "and status in ('ok','failed') and coalesce(verdict,'') != 'cancelled'",
            (_since(),),
        )
        if lv in LEVELS
    }
    for job, brain, verdict, at, secs in _rows(
        app, "select job, brain, verdict, at, coalesce(seconds,0) from attempts where at >= ? order by at", (_since(),)
    ):
        if job in jobs:
            jobs[job]["tries"].append((brain, verdict, float(secs or 0), float(at)))
    return sorted((j for j in jobs.values() if j["tries"]), key=lambda j: j["ts"])


class _Odds:
    """Each AI's record per effort level, for the tries that weren't made."""

    def __init__(self, jobs: list[dict]):
        self.all = [t + (j["level"],) for j in jobs for t in j["tries"]]

    def at(self, brain: str, level: str) -> list[tuple]:
        mine = [t for t in self.all if t[0] == brain and t[4] == level]
        return mine if len(mine) >= MIN_TRIES else [t for t in self.all if t[0] == brain]

    def limited(self, brain: str, ts: float) -> bool:
        """It hit a limit (or was signed out) in the LIMIT_H hours before, with no answer since."""
        last = None
        for b, v, _s, at, _lv in self.all:
            if b == brain and ts - LIMIT_H * 3600 <= at <= ts:
                last = v
        return last in ("rate_limited", "auth")

    def guess(self, brain: str, level: str, ts: float) -> tuple[float, float, float, float, float]:
        """(p answer, p fail and hand on, p fail and stop, minutes if answered, minutes if failed)."""
        if self.limited(brain, ts):
            return 0.0, 1.0, 0.0, 0.0, 0.05
        rec = self.at(brain, level)
        n = len(rec)
        ok = sum(t[1] == "ok" for t in rec)
        on = sum(t[1] in RETRY_VERDICTS for t in rec)
        p_ok, p_on = (ok + 1) / (n + 2), (on + 0.5) / (n + 2)
        oks = [t[2] / 60 for t in rec if t[1] == "ok"]
        bad = [t[2] / 60 for t in rec if t[1] != "ok"]
        return (
            p_ok,
            p_on,
            max(0.0, 1 - p_ok - p_on),
            statistics.median(oks) if oks else 1.0,
            (statistics.median(bad) if bad else 0.5),
        )


def _chain_score(job: dict, order: list[str], odds: _Odds) -> float:
    """Expected score of a request had its AIs been tried in this order (as recorded where they were)."""
    known = {}
    for b, v, s, _at, *_ in job["tries"]:
        known.setdefault(b, (v, s / 60))

    def step(k: int, tried: int) -> float:
        if k >= len(order):
            return -FAIL
        b = order[k]
        if b in known:
            v, m = known[b]
            if v == "ok":
                return ANSWER - m * MINUTE - tried * TRY
            cost = -m * MINUTE
            return cost + (step(k + 1, tried + 1) if v in RETRY_VERDICTS else -FAIL)
        p_ok, p_on, p_stop, m_ok, m_bad = odds.guess(b, job["level"], job["ts"])
        return (
            p_ok * (ANSWER - m_ok * MINUTE - tried * TRY)
            + p_on * (-m_bad * MINUTE + step(k + 1, tried + 1))
            + p_stop * (-m_bad * MINUTE - FAIL)
        )

    return step(0, 0)


def fallback_replay(jobs: list[dict], first: set[str], pair: tuple[str, str], odds: _Odds) -> float:
    m, f = pair
    total = 0.0
    for j in jobs:
        if not {t[0] for t in j["tries"]} & {m, f}:
            continue
        total += _chain_score(j, [f, m] if j["level"] in first else [m, f], odds)
    return total


def fallbacks_plan(app: App, st: dict) -> tuple[dict, Change | None] | None:
    if not app.settings.get("dreaming.tune_fallbacks"):
        return None
    pair = _brains(app)
    if pair is None:
        return None
    m, f = pair
    jobs = tries(app)
    odds = _Odds(jobs)
    cur = {lv for lv in (app.settings.get("brain.fallback_first") or []) if lv in LEVELS}
    base = fallback_replay(jobs, cur, pair, odds)
    skip = blocked(app, st, "fallbacks")
    best, best_s, cands = None, base, 0
    mine = [j for j in jobs if {t[0] for t in j["tries"]} & {m, f}]
    for lv in LEVELS:
        at = [j for j in mine if j["level"] == lv]
        fails = [t for j in at for t in j["tries"] if t[0] == m and t[1] != "ok"]
        if lv in skip or len(at) < MIN_JOBS:
            continue
        if lv not in cur and (len(fails) < MIN_FAILS or len(odds.at(f, lv)) < MIN_TRIES):
            continue
        cand = cur ^ {lv}
        cands += 1
        s = fallback_replay(jobs, cand, pair, odds) - CHANGE["fallbacks"]
        if s > best_s:
            best, best_s = (lv, at, fails), s
    d = _decision("fallbacks", score=round(base, 2), best=round(best_s, 2), candidates=cands + 1, judged=len(mine))
    d["days"] = _days(mine[0]["ts"] if mine else None)
    if best is None:
        return d, None
    from kurooto.core.jobs import NAMES

    lv, at, fails = best
    name = lambda b: NAMES.get(b, b)  # noqa: E731
    on = lv not in cur
    if on:
        said = f"{lv}-effort requests now try {name(f)} first, then {name(m)}"
        kinds = {"rate_limited": "limits", "timeout": "timeouts", "auth": "sign-outs"}
        bits = sorted({kinds.get(t[1], "errors") for t in fails})
        why = f"{name(m)} failed {len(fails)} times on the last {len(at)} of them ({', '.join(bits)})"
    else:
        said = f"{lv}-effort requests go to {name(m)} first again"
        why = f"{name(f)} did worse on the last {len(at)} of them"
    new = sorted(cur ^ {lv}, key=LEVELS.index)
    d.update(target=lv, set=on, said=said, why=why, trust="fallbacks.first" if on else "fallbacks.back")
    return d, Change(said, key="brain.fallback_first", value=new)


# ------------------------------------------------------------------------------------------ sizing
def samples(app: App) -> list[dict]:
    """Deadlines whose real size is known: one you tapped a size for, or one done with study time on its subject
    (shared with the subject's other deadlines those days, by their planned size), or with half its parts done."""
    dl, sb = app.modules.get("deadlines"), app.modules.get("startby")
    if dl is None or sb is None or not app.is_on("deadlines") or not app.is_on("startby"):
        return []
    from kurooto.modules.startby import kind_of

    items = dl.items()
    st = sb._state()
    tapped, told = st.get("sizes") or {}, st.get("told") or {}
    cutoff = now() - dt.timedelta(days=SIZE_DAYS)
    out, spans = [], []
    for i, it in items.items():
        try:
            due = dt.datetime.fromisoformat(it["due"])
        except (KeyError, ValueError):
            continue
        if due < cutoff:
            continue
        kind = kind_of(it.get("title", ""), it.get("kind", "task"))
        if i in tapped:
            out.append({"id": i, "kind": kind, "hours": float(tapped[i]), "how": "tapped"})
            continue
        done = it.get("done_at") if it.get("status") == "done" else None
        parts, pdone = it.get("parts") or 0, it.get("parts_done") or 0
        frac = 1.0
        if not done and parts and pdone / parts >= 0.5 and it.get("progress_at"):
            done, frac = it["progress_at"], pdone / parts
        if not done or not it.get("subject"):
            continue
        end = dt.datetime.fromisoformat(done).replace(tzinfo=None)
        start = dt.date.fromisoformat(told[i]) if told.get(i) else (due - dt.timedelta(days=SPAN_DAYS)).date()
        planned = sb._whole_size(i, it, st)[0]
        spans.append({"id": i, "kind": kind, "subject": it["subject"], "from": start, "to": end.date(),
                      "planned": planned, "frac": frac})  # fmt: skip
    study = app.modules.get("study") if app.is_on("study") else None
    if study is None or not spans:
        return out
    day = min(s["from"] for s in spans)
    got: dict[str, float] = {}
    while day <= max(s["to"] for s in spans):
        d = study.day(day)
        for subj in {s["subject"] for s in spans}:
            secs = sum(float(v or 0) for k, v in d.items() if k.split("|")[0] == subj)
            here = [s for s in spans if s["subject"] == subj and s["from"] <= day <= s["to"]]
            weight = sum(s["planned"] for s in here)
            for s in here:
                got[s["id"]] = got.get(s["id"], 0.0) + secs / 3600 * s["planned"] / max(weight, 1e-6)
        day += dt.timedelta(days=1)
    for s in spans:
        h = got.get(s["id"], 0.0) / s["frac"]
        if h >= 0.25:
            out.append({"id": s["id"], "kind": s["kind"], "hours": round(h, 2), "how": "study"})
    return out


def size_replay(rows: list[dict], kind: str, h: float) -> float:
    return -sum((UNDER if h < r["hours"] else 1.0) * abs(math.log(h / r["hours"])) for r in rows if r["kind"] == kind)


def sizing_plan(app: App, st: dict) -> tuple[dict, Change | None] | None:
    if not app.settings.get("dreaming.tune_sizing"):
        return None
    rows = samples(app)
    if not rows:
        return None
    from kurooto.modules.startby import KINDS, ladder, size_text

    sizes = app.settings.get("startby.sizes") or {}
    mine = (app.settings.user().get("startby") or {}).get("sizes") or {}
    ours = {d["target"]: d.get("set") for d in st.get("decisions") or [] if d.get("area") == "sizing" and d["applied"]}
    skip = blocked(app, st, "sizing")
    base = sum(size_replay(rows, k, float(sizes.get(k, 2))) for k in KINDS)
    best, best_s, cands = None, base, 0
    for kind in KINDS:
        rs = [r for r in rows if r["kind"] == kind]
        if len(rs) < MIN_SAMPLES or kind in skip:
            continue
        if kind in mine and mine[kind] != ours.get(kind):
            continue  # you set it yourself
        cur = float(sizes.get(kind, 2))
        med = statistics.median(r["hours"] for r in rs)
        steps = sorted({float(h) for h, _ in ladder(kind)} | {cur})
        near = min(steps, key=lambda h: abs(math.log(h / med)))
        i = steps.index(cur)
        toward = steps[i + 1] if med > cur and i + 1 < len(steps) else steps[i - 1] if med < cur and i else cur
        for h in {near, toward} - {cur}:
            cands += 1
            s = base - size_replay(rows, kind, cur) + size_replay(rows, kind, h) - CHANGE["sizing"]
            if s > best_s:
                best, best_s = (kind, cur, h, rs, med), s
    d = _decision("sizing", score=round(base, 2), best=round(best_s, 2), candidates=cands + 1, judged=len(rows))
    d["days"] = SIZE_DAYS
    if best is None:
        return d, None
    kind, cur, h, rs, med = best
    tap = sum(r["how"] == "tapped" for r in rs)
    how = ", ".join(
        b for b in (f"{len(rs) - tap} from study time" if len(rs) - tap else "", f"{tap} you sized" if tap else "") if b
    )
    said = f"Start-by sizes {KINDS[kind]} at {size_text(h)}, not {cur:g} h"
    why = f"the last {len(rs)} took about {med:.0f} h ({how})" if med >= 2 else f"the last {len(rs)} took {med:.1f} h"
    d.update(target=kind, set=h, said=said, why=why, trust="sizing.up" if h > cur else "sizing.down")
    return d, Change(said, key=f"startby.sizes.{kind}", value=h)


AREAS = {"effort": effort_plan, "fallbacks": fallbacks_plan, "sizing": sizing_plan}


# -------------------------------------------------------------------------------------------- the night
def night(app: App) -> dict | None:
    """Tonight's round in every area: at most one change. Returns the applied decision (or None). Once a day."""
    st = _load(app)
    day = now().date().isoformat()
    if st.get("day") == day:
        return None
    review(app, st)
    margin = float(app.settings.get("dreaming.tune_margin") or 0)
    plans: list[tuple[str, dict, Change | None]] = []
    msgs = policy.consider(app)
    if msgs is not None:
        d, ch = msgs
        d["trust"] = f"messages.{d.get('lever', '')}"
        plans.append(("messages", d, ch))
    for area, plan in AREAS.items():
        try:
            got = plan(app, st)
        except Exception as e:  # one area's mistake costs only that area tonight
            app.events.emit("dreaming_tuning_failed", area=area, error=f"{type(e).__name__}: {e}"[:200])
            continue
        if got is not None:
            plans.append((area, *got))
    best, best_ratio = None, 0.0
    for area, d, ch in plans:
        need = margin * trust(st, d.get("trust", area))
        d["margin"] = round(need, 2)
        gain = d["best"] - d["score"]
        if ch is not None and gain >= need and gain / max(need, 1e-6) > best_ratio:
            best, best_ratio = (area, d, ch), gain / max(need, 1e-6)
    applied = None
    for area, d, ch in plans:
        won = best is not None and best[0] == area
        if not won and ch is not None and d["best"] - d["score"] >= d["margin"]:
            d["waited"] = True  # it would have gone in, but another change went first tonight
        if area == "messages":
            policy.settle(app, d, ch, won, why=BY)
            if won and d.get("applied"):
                mirror = {k: d[k] for k in ("at", "kind", "lever", "value", "said", "uid", "applied", "trust")}
                st.setdefault("decisions", []).append({**mirror, "area": "messages", "target": d["kind"]})
                applied = d
            continue
        if won:
            ok, _said, uid = app.calm.apply(ch, why=BY)
            d.update(applied=ok, uid=uid)
            applied = d if ok else None
        st.setdefault("decisions", []).append(d)
        app.events.emit("dreaming_tuned", area=area, applied=bool(d.get("applied")), gain=d["best"] - d["score"])
    st["decisions"] = st.get("decisions", [])[-KEEP_DECISIONS:]
    st["day"] = day
    _save(app, st)
    try:
        propose(app)
    except Exception as e:
        app.events.emit("dreaming_tuning_failed", area="prompts", error=f"{type(e).__name__}: {e}"[:200])
    return applied


def line(d: dict) -> str:
    if d.get("area") in (None, "messages"):
        return policy.line(d)
    return f"Learned while you slept: {d['said']}; {d['why']}."


def morning(app: App, send: bool = True) -> tuple[list[str], list]:
    """Dreaming's hook: (its lines for the morning message, their buttons). Tunes only for the sent message; /dream
    shows today's change and the waiting proposal again."""
    try:
        if send:
            night(app)
    except Exception as e:  # tuning must not cost the morning message
        app.events.emit("dreaming_policy_failed", error=f"{type(e).__name__}: {e}"[:200])
    lines, buttons = [], []
    today = now().date().isoformat()
    d = policy.applied_today(app)
    if d is None:
        d = next(
            (
                x
                for x in reversed(_load(app).get("decisions") or [])
                if x.get("applied") and x["at"][:10] == today and x.get("area") not in ("messages", "prompts")
            ),
            None,
        )
    if d is not None and d.get("uid"):
        lines.append(line(d))
        buttons.append([("Undo", f"calm:{d['uid']}:undo")])
    p = proposal(app)
    if p is not None:
        lines.append(
            f"A fix for /{p['name']}, which went wrong {p['n']} times lately: {p['change']} It fixes {p['fixes']} of "
            "them by the AI's own replay; /dream proposal shows it."
        )
        buttons.append([("Apply", f"rsi:{p['pid']}:apply"), ("No", f"rsi:{p['pid']}:no")])
    return lines, buttons


def heard(app: App, text: str) -> str | None:
    """A message that says the last answer missed ("that's not what I asked"): that request keeps your words as a
    miss for the effort replay and the proposals. The request's id, or None."""
    if not (app.settings.get("dreaming.tune_effort") or app.settings.get("dreaming.propose_prompts")):
        return None
    if not CORRECTS.match(text or ""):
        return None
    jid = app.jobs.corrected(text)
    if jid:
        app.events.emit("ai_corrected", job=jid)
    return jid


# ------------------------------------------------------------------------------------------- proposals
def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def failures(app: App) -> dict[str, list[dict]]:
    """Per skill, its answers that went wrong in the last FAIL_DAYS days (corrected, marked Wrong, asked again)."""
    cutoff = (now() - dt.timedelta(days=FAIL_DAYS)).timestamp()
    out: dict[str, list[dict]] = {}
    for r in asks(app):
        if r["skill"] and r["ts"] >= cutoff and {"wrong", "corrected", "retried"} & set(r["misses"]):
            out.setdefault(r["skill"], []).append(r)
    return out


def proposal_file(app: App, pid: str):
    return app.paths.state / "tuning" / f"proposal-{pid}.md"


def proposal(app: App) -> dict | None:
    """The proposal waiting for your Apply or No (ready, not older than PROPOSAL_DAYS), or None."""
    p = _load(app).get("proposal") or {}
    if p.get("status") != "ready":
        return None
    if now() - dt.datetime.fromisoformat(p["at"]) > dt.timedelta(days=PROPOSAL_DAYS):
        return None
    return p


def propose(app: App) -> str | None:
    """Ask the second-look AI for a fix to the skill that went wrong most (REPEAT times or more). The job's id."""
    if not app.settings.get("dreaming.propose_prompts") or not app.is_on("skills"):
        return None
    lrn = app.modules.get("learning")
    if lrn is None:
        return None
    st = _load(app)
    last = st.get("proposal") or {}
    if last.get("at") and now() - dt.datetime.fromisoformat(last["at"]) < dt.timedelta(days=PROPOSE_EVERY_DAYS):
        return None
    skip = blocked(app, st, "prompts")
    bad = {k: v for k, v in failures(app).items() if len(v) >= REPEAT and k not in skip}
    if not bad:
        return None
    from kurooto.modules.learning import asked
    from kurooto.modules.skills import load_skill

    name = max(bad, key=lambda k: (len(bad[k]), k))
    s = load_skill(app, name)
    if s is None or s.internal or not s.path:
        return None
    try:
        from pathlib import Path

        text = Path(s.path).read_text(encoding="utf-8")
    except OSError:
        return None
    cases = []
    for k, r in enumerate(bad[name][-6:], 1):
        what = {"wrong": "marked Wrong", "corrected": "corrected", "retried": "asked again"}
        how = ", ".join(what[m] for m in r["misses"] if m in what)
        said = r["corrected"] if r["corrected"] not in ("", "-") else r["note"]
        cases.append(
            f"{k}. Asked: {asked(r['prompt'])[:400] or r['title']}\n   It went wrong: {how}"
            + (f'; the user said: "{said[:300]}"' if said else "")
        )
    pid = uuid.uuid4().hex[:8]
    jid = app.jobs.submit(
        PROPOSE.format(name=name, n=len(bad[name]), text=text[:12000], cases="\n".join(cases)),
        title=f"A fix for /{name}?",
        effort="medium",
        quiet=True,
        then="dreaming.proposal",
        then_payload={"pid": pid, "name": name, "base": _sha(text), "n": len(bad[name]), "cases": len(cases)},
        background=True,
        text_only=True,
        lane="chk",
        brain=lrn.check_brain(),
    )
    st["proposal"] = {"pid": pid, "name": name, "status": "waiting", "at": now().isoformat(timespec="seconds"),
                      "n": len(bad[name]), "job": jid}  # fmt: skip
    _save(app, st)
    app.events.emit("dreaming_proposal_asked", n=len(bad[name]))
    return jid


def proposal_ready(app: App, job, result, payload: dict) -> None:
    """The second-look AI's answer: offered (status "ready") only if it passes the checks; else dropped."""
    from kurooto.modules.skills import extract_skill, load_skill, make

    st = _load(app)
    p = st.get("proposal") or {}
    if p.get("pid") != payload.get("pid"):
        return

    def drop(why: str) -> None:
        st["proposal"] = {**p, "status": "dropped", "why": why}
        _save(app, st)
        app.events.emit("dreaming_proposal_dropped", why=why)

    if not result.ok:
        return drop("no answer")
    text = str(result.text or "")
    if re.match(r"\s*NONE\b", text):
        return drop("nothing in the skill caused it")
    new = extract_skill(text)
    name = str(payload.get("name") or "")
    s = load_skill(app, name)
    if not new or s is None or not s.path:
        return drop("no usable skill")
    from pathlib import Path

    try:
        old = Path(s.path).read_text(encoding="utf-8")
    except OSError:
        return drop("the skill is gone")
    if _sha(old) != payload.get("base"):
        return drop("the skill changed since")
    new = re.sub(r"(?m)^name:.*$", f"name: {name}", new, count=1)
    if make(new, name, "x") is None or not 0.5 <= len(new) / max(1, len(old)) <= 2.0 or new.strip() == old.strip():
        return drop("not a careful change")
    n = int(payload.get("cases") or 0)
    yes = len(re.findall(r"(?im)^\s*FIXES\s+\d+\s*:\s*yes\b", text))
    need = min(1.0, FIX_SHARE * trust(st, "prompts"))
    if not n or yes / n < need:
        return drop(f"fixes {yes} of {n}")
    m = re.search(r"(?im)^\s*CHANGE\s*:\s*(.+)$", text)
    change = re.sub(r"\s+", " ", m[1]).strip()[:200] if m else "a rewritten step."
    f = proposal_file(app, p["pid"])
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(new, encoding="utf-8")
    st["proposal"] = {**p, "status": "ready", "change": change if change.endswith(".") else change + ".",
                      "fixes": yes, "base": payload.get("base")}  # fmt: skip
    _save(app, st)
    app.events.emit("dreaming_proposal_ready", fixes=yes, of=n)


def answer(app: App, pid: str, act: str) -> str:
    """The proposal's buttons: apply (through Learning, then your test cases replayed) or no."""
    st = _load(app)
    p = st.get("proposal") or {}
    if p.get("pid") != pid or p.get("status") != "ready":
        return "That proposal isn't waiting any more."
    name = p["name"]
    d = _decision("prompts", target=name, trust="prompts", said=f"/{name}: {p.get('change', '')}")
    if act == "no":
        st["proposal"] = {**p, "status": "declined"}
        d.update(declined=True, outcome="undone")
        _outcome(st, "prompts", "undone")
        st.setdefault("decisions", []).append(d)
        _save(app, st)
        app.events.emit("dreaming_proposal", applied=False)
        return f"Left /{name} as it is; I won't propose a change to it for {BLOCK_DAYS} days."
    lrn = app.modules.get("learning")
    try:
        new = proposal_file(app, pid).read_text(encoding="utf-8")
    except OSError:
        return "The proposal's file is gone."
    if lrn is None:
        return "Learning isn't available, so I can't change the skill."
    base = p.get("base")
    cid = lrn._change(name, lambda old: new if _sha(old) == base else None, "proposal")
    if cid is None:
        st["proposal"] = {**p, "status": "dropped", "why": "the skill changed since"}
        _save(app, st)
        return f"/{name} changed since the proposal, so I left it as it is."
    broke = _replay_cases(app)
    if broke:
        lrn.undo(cid)
        st["proposal"] = {**p, "status": "dropped", "why": "a test case went wrong"}
        _save(app, st)
        return f'Put /{name} back: with the change, a test case went wrong ("{broke[:60]}", /cases).'
    st["proposal"] = {**p, "status": "applied", "cid": cid}
    d.update(applied=True, cid=cid)
    st.setdefault("decisions", []).append(d)
    st["decisions"] = st["decisions"][-KEEP_DECISIONS:]
    _save(app, st)
    app.events.emit("dreaming_proposal", applied=True)
    return f"Changed /{name}. Undo with /learned."


def _replay_cases(app: App) -> str:
    """Your test cases, routed as now: the text of one that passed this morning and fails now, or ""."""
    cases = app.modules.get("cases") if app.is_on("cases") else None
    if cases is None:
        return ""
    was = set((jload(app.paths.state / "dreaming.json", {}) or {}).get("passing") or [])
    res = cases.suite()
    return next((r["text"] for r in res["fail"] if r["id"] in was), "")


def show_proposal(app: App) -> str:
    p = proposal(app)
    if p is None:
        on = app.settings.get("dreaming.propose_prompts")
        return "No proposal waiting." + ("" if on else " Proposals are off (dreaming.propose_prompts).")
    try:
        text = proposal_file(app, p["pid"]).read_text(encoding="utf-8")
    except OSError:
        return "The proposal's file is gone."
    return f"Proposed for /{p['name']} ({p['change']}):\n\n{text[:3500]}"


# ------------------------------------------------------------------------------------------------ show
def show(app: App) -> str:
    """/dream policy, after part two's lines: the other areas as they are, and their last decisions."""
    from kurooto.core.jobs import NAMES
    from kurooto.modules.startby import KINDS

    s = app.settings
    on = lambda k: "on" if s.get(f"dreaming.{k}") else f"off (dreaming.{k})"  # noqa: E731
    cur = {o: lv for o, lv in _levels(app).items() if lv != ORIGINS[o]}
    lines = [
        f"Effort for your requests, tuned: {on('tune_effort')}. "
        + ("; ".join(f"{ORIGIN_SAID[o]}: {lv}" for o, lv in cur.items()) or "As the quick check picks it.")
    ]
    pair = _brains(app)
    first = s.get("brain.fallback_first") or []
    order = (
        f"{NAMES.get(pair[0], pair[0])}, then {NAMES.get(pair[1], pair[1])}"
        + (f"; {', '.join(first)} effort: {NAMES.get(pair[1], pair[1])} first" if first else "")
        if pair
        else "no fallback AI set"
    )
    lines.append(f"Which AI goes first, tuned: {on('tune_fallbacks')}. {order}.")
    sizes = s.get("startby.sizes") or {}
    lines.append(
        f"Start-by sizes, tuned: {on('tune_sizing')}. "
        + ", ".join(f"{KINDS[k].split(' ', 1)[1]} {float(sizes.get(k, 2)):g} h" for k in KINDS if k in sizes)
        + "."
    )
    lines.append(f"Fixes to skills that keep going wrong, proposed: {on('propose_prompts')}.")
    st = _load(app)
    wary = {k: trust(st, k) for k in (st.get("outcomes") or {}) if trust(st, k) > 1}
    if wary:
        lines.append(
            "Needs a clearer win, after changes you undid: "
            + ", ".join(f"{k} ×{v:g}" for k, v in sorted(wary.items()))
            + "."
        )
    ds = [d for d in st.get("decisions") or [] if d.get("area") not in ("messages",)]
    if ds:
        lines.append("Last decisions (replay score: as it was / best variant):")
    for d in ds[-6:][::-1]:
        when = dt.datetime.fromisoformat(d["at"])
        if d.get("area") == "prompts":
            what = ("declined: " if d.get("declined") else "applied: ") + d.get("said", "")
            lines.append(f"- {when:%a %d %b}, prompts: {what}.")
            continue
        if d.get("applied"):
            what = d["said"] + (f" ({d['outcome']})" if d.get("outcome") else "")
        else:
            what = "kept as it was" + (f" (best: {d['said']}" + (", waited a night)" if d.get("waited") else ")")
                                       if d.get("said") else "")  # fmt: skip
        lines.append(f"- {when:%a %d %b}, {d['area']}: {what}; {d['score']:+.1f} / {d['best']:+.1f}, "
                     f"{d['candidates']} tried.")  # fmt: skip
    return "\n".join(lines)
