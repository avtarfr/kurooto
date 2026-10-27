"""The Brain console (0.8.10): one read-only view of everything Brain keeps, for the dashboard's Brain console page
(GET /api/brain/console, static/views/brainconsole.js) and the phone app's Brain view (the "brain" copy
modules/calls/views.py seals for each phone).

What it reads, all read-only, from the Brain's own stores:
    the mind log (<state>/mind/log.db)   decisions with their reasons, a timeline filterable by part and day, search
    the score tables (score.db)          what it has learned about a kind of action: trust, values, recent misses
    each part's own file                 beliefs, lab projects, challengers, play, skills, plans, the model of you,
                                         the spotlight, promises, what it forgot, the journal and story (headings only)
    the settings                         each part's switches and settings, next to what that part is doing

Plain facts only. Nothing named for money or health passes (records.MONEY_OR_HEALTH on field names; a text that names
either is left out, as the skills distiller and the model of you leave it out); the senses give counts only; the
journal and the story give their headings (day or week, how many lines), never their sentences; what it forgot is a
count and a time, never what. The log itself never held a message's words (invariant I-11).

    view(app, q)       the API: q["view"] is "all" (default), "timeline", "decision", "search"
    snapshot(app)      everything at once, bounded (the phone's copy: decisions carry their evidence, so they open
                       without the computer)

Off (`mind.console.on` false): the API says so and the phone gets no copy. With Brain off it says Brain is off.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
import time
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.config import register_defaults
from kurooto.core.state import jload

if TYPE_CHECKING:
    from pathlib import Path

    from kurooto.app import App

register_defaults(
    "mind",
    {
        "console": {
            "on": True,  # the Brain console: the dashboard page and the phone's Brain view that read what Brain keeps
        }
    },
)

PART = "console"  # its switch: mind.console.on (it only reads; it writes nothing anywhere)
PAGE = 80  # timeline rows a page by default
PAGE_MAX = 400
PHONE_ROWS = 240  # timeline rows in the phone's copy
DECISIONS = 40  # decisions listed (each opens to its reasons and evidence)
PHONE_DECISIONS = 25  # decisions whose evidence goes with the phone's copy
AROUND_S = 600  # a decision's evidence: what the log holds this long before and after it
WINDOW = 200_000  # per-part activity is counted over the last this many records
SEARCH_MAX = 60
TEXT_MAX = 160
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HEX = re.compile(r"^[A-Za-z0-9_.:@+-]{1,64}$")

# a text that names money or health is left out (the skills distiller's and the model of you's lists, together)
PRIVATE = re.compile(
    r"\b(health\w*|ill(?:ness)?|sick\w*|medic\w*|doctor|hospital|therap\w*|depress\w*|anxi\w*|diagnos\w*|symptom\w*|"
    r"pill\w*|dose|blood|pulse|weight|calorie\w*|bank\w*|salary|invoice\w*|payment\w*|pay(?:ing)?|paid|credit card|"
    r"loan\w*|debt\w*|tax(?:es)?|rent|income|money|rupees?|dollars?|euros?|price\w*|bill\w*|fees?|password\w*|"
    r"passwd|token\w*)\b",
    re.I,
)
LEFT_OUT = "(left out: it names money or health)"

# --------------------------------------------------------------------------------------- which part wrote what
# log kinds -> the Brain part they belong to (core/brainview.py's part ids); everything else is Kurooto's own events
# mirrored in ("log": what it saw)
KIND_PART = {
    "decision": "autonomy", "outcome": "autonomy", "mind_act": "autonomy", "trust_evidence": "autonomy",
    "stop_span": "stops", "kurooto_crashed": "stops", "module_failed": "stops", "mind_keeper_exited": "stops",
    "keeper_started": "stops", "keeper_stopped": "stops", "power_pause": "stops", "power_resume": "stops",
    "power_off": "stops", "lidsafe_sleep": "stops",
    "read_day": "read", "read_answer": "read", "signal": "read", "read_forget": "read", "read_off": "read",
    "forecast": "forecast", "forecast_score": "forecast", "score_forecast": "forecast",
    "mind_feeling": "feelings",
    "budget_tick": "budget", "talk_heard": "budget", "talk_unprompted": "budget", "talk_rejected": "budget",
    "talk_met": "budget",
    "learning_verdict": "budget", "learning_freeze": "budget",
    "harness_result": "harness",
    "workspace": "workspace", "workspace_cycle": "workspace",
    "attention_check": "attention",
    "belief_outcome": "beliefs",
    "lab_prereg": "lab", "lab_result": "lab",
    "improve_event": "improve",
    "skill_event": "skills",
    "finetune_event": "finetune",
    "forget_event": "forget",
    "history_import": "history", "history_forgot": "history",
}  # fmt: skip
PREFIX_PART = (("gate_", "gate"), ("promise_", "promises"))

# a few kinds in words; the rest are their names with spaces
WORDS = {
    "decision": "decided",
    "outcome": "what came of a decision",
    "mind_act": "did something on its own",
    "stop_span": "was stopped",
    "kurooto_crashed": "Kurooto ended with an error",
    "module_failed": "a feature failed",
    "mind_keeper_exited": "the scorekeeper ended",
    "keeper_started": "the scorekeeper started",
    "keeper_stopped": "the scorekeeper stopped",
    "read_day": "read the day",
    "read_answer": "you answered its read",
    "forecast": "froze a forecast",
    "forecast_score": "scored a forecast",
    "mind_feeling": "a feeling changed",
    "harness_result": "tested itself on the hidden harness",
    "workspace": "the spotlight changed",
    "workspace_cycle": "the spotlight changed",
    "attention_check": "checked its model of its attention",
    "belief_outcome": "a belief was settled",
    "lab_prereg": "pre-registered an experiment",
    "lab_result": "an experiment finished",
    "improve_event": "self-improvement",
    "skill_event": "a skill changed",
    "finetune_event": "fine-tune",
    "forget_event": "forgot something you asked it to",
    "history_import": "imported the past",
    "history_forgot": "forgot the imported past",
    "gate_receipt": "the gate passed a message",
    "gate_lint": "the gate reworded a sentence",
    "gate_mute": "the gate muted a kind of message",
    "gate_call": "the gate decided on a call",
    "promise_made": "made a promise",
    "promise_kept": "kept a promise",
    "promise_broken": "broke a promise",
    "refused": "the scorekeeper refused a request",
}
HIDDEN_KEYS = frozenset({"at", "prev", "hash"})


def on(app: App) -> bool:
    """The console's own switch (the page and the phone's copy); Brain itself is the Features switch."""
    return app.settings.get("mind.console.on") is not False


def part_of(kind: str) -> str:
    if kind in KIND_PART:
        return KIND_PART[kind]
    for pre, part in PREFIX_PART:
        if kind.startswith(pre):
            return part
    return "log"


# ---------------------------------------------------------------------------------------------------- privacy
def private(text) -> bool:
    return bool(PRIVATE.search(str(text or "")))


def clean_text(text, n: int = TEXT_MAX) -> str:
    """A text as the console may show it: one line, cut to n, or LEFT_OUT when it names money or health."""
    s = " ".join(str(text or "").split())
    if private(s):
        return LEFT_OUT
    return s if len(s) <= n else s[: n - 1] + "…"


def clean_body(body) -> dict:
    """A log record's body: nothing named for money or health, text cut short, a few levels deep."""
    from kurooto.mind.records import MONEY_OR_HEALTH

    def walk(v, depth):
        if isinstance(v, dict):
            if depth <= 0:
                return {}
            return {
                str(k)[:40]: walk(x, depth - 1)
                for k, x in list(v.items())[:30]
                if not MONEY_OR_HEALTH.search(str(k)) and str(k) not in HIDDEN_KEYS
            }
        if isinstance(v, list):
            return [walk(x, depth - 1) for x in v[:20]] if depth > 0 else []
        if isinstance(v, str):
            return clean_text(v, 120)
        if isinstance(v, float):
            return round(v, 4)
        return v

    return walk(body if isinstance(body, dict) else {}, 4)


# ----------------------------------------------------------------------------------------------------- the log
def _db_path(app: App) -> Path:
    return app.paths.state / "mind" / "log.db"


def _q(app: App, sql: str, args: tuple = ()) -> list[tuple]:
    """Rows from the mind log, opened read-only (mode=ro); [] when there's no log yet."""
    p = _db_path(app)
    if not p.exists():
        return []
    db = sqlite3.connect(f"{p.resolve().as_uri()}?mode=ro", uri=True, check_same_thread=False, timeout=10)
    try:
        return db.execute(sql, args).fetchall()
    except sqlite3.Error:
        return []
    finally:
        db.close()


def _body(raw) -> dict:
    try:
        b = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return b if isinstance(b, dict) else {}


def describe(kind: str, body: dict) -> str:
    """One plain line for a record (ids and numbers: the log holds nothing else)."""
    b = body or {}
    head = WORDS.get(kind, kind.replace("_", " "))
    if kind == "decision":
        why = b.get("scored_reason") or b.get("stated_reason") or ""
        out = f"decided {b.get('action', '?')} ({b.get('source', 'rules')})"
        return out + (f": {clean_text(why, 80)}" if why else "")
    if kind == "outcome":
        return f"what came of a decision: {b.get('result', '?')}"
    if kind == "mind_act":
        return f"did {b.get('action', 'something')} on its own" + (f" ({b['klass']})" if b.get("klass") else "")
    if kind == "stop_span":
        try:
            mins = (float(b["end"]) - float(b["start"])) / 60
            return f"was stopped ({b.get('gap') or 'stop'}) for {_dur(mins * 60)}"
        except (KeyError, TypeError, ValueError):
            return head
    if kind == "gate_receipt":
        did, would = b.get("did") or "", b.get("would_have") or ""
        return f"the gate: {did or 'passed'}" + (f" (would have: {would})" if would and would != did else "")
    if kind == "forget_event":
        n = int(b.get("n") or 0)
        return f"forgot {n} thing{'s' if n != 1 else ''} you asked it to"
    if kind in ("skill_event", "improve_event", "finetune_event") and b.get("status"):
        return f"{head}: {str(b['status']).replace('_', ' ')}"
    if kind == "lab_result":
        return f"an experiment on {b.get('project', '?')} finished: {b.get('wins', 0)} win(s), " + (
            f"{b.get('replicated', 0)} replicated"
        )
    if kind == "belief_outcome":
        return f"a belief ({b.get('source', '?')}) turned out {'true' if b.get('outcome') else 'false'}"
    if kind in ("job_ended", "job_failed", "job_queued", "job_crashed", "job_cancelled"):
        return head + (f" ({b['verdict']})" if b.get("verdict") else "")
    if kind == "button_tapped" and b.get("prefix"):
        return f"you tapped a button ({b['prefix']})"
    if kind in ("module_enabled", "module_disabled") and b.get("module"):
        return f"{b['module']} turned {'on' if kind == 'module_enabled' else 'off'}"
    return head


def _dur(s: float) -> str:
    s = max(0.0, float(s))
    if s < 90:
        return f"{round(s)} s"
    if s < 5400:
        return f"{round(s / 60)} min"
    if s < 172800:
        return f"{s / 3600:.1f} h"
    return f"{s / 86400:.1f} days"


def _row(seq, ts, kind, raw) -> dict:
    b = _body(raw)
    return {
        "seq": int(seq),
        "ts": round(float(b.get("at", ts) if isinstance(b.get("at"), (int, float)) else ts), 3),
        "kind": str(kind),
        "part": part_of(str(kind)),
        "text": describe(str(kind), b),
        "body": clean_body(b),
    }


def _kind_filter(part: str) -> tuple[str, list]:
    """SQL (and its arguments) for the records of one part."""
    if not part:
        return "", []
    if part == "log":
        mine = sorted(KIND_PART)
        sql = f" AND kind NOT IN ({','.join('?' * len(mine))})" + "".join(" AND kind NOT LIKE ?" for _ in PREFIX_PART)
        return sql, [*mine, *(f"{p}%" for p, _ in PREFIX_PART)]
    kinds = sorted(k for k, p in KIND_PART.items() if p == part)
    pre = [f"{p}%" for p, q in PREFIX_PART if q == part]
    if not kinds and not pre:
        return " AND 0", []
    terms = ([f"kind IN ({','.join('?' * len(kinds))})"] if kinds else []) + ["kind LIKE ?" for _ in pre]
    return f" AND ({' OR '.join(terms)})", [*kinds, *pre]


def day_span(day: str) -> tuple[float, float] | None:
    """[start, end) of a local day "YYYY-MM-DD"."""
    if not DAY.match(day or ""):
        return None
    try:
        d = dt.datetime.fromisoformat(day)
    except ValueError:
        return None
    return d.timestamp(), (d + dt.timedelta(days=1)).timestamp()


def _like(text: str) -> str:
    return "%" + re.sub(r"([%_\\])", r"\\\1", text) + "%"


def timeline(app: App, part: str = "", day: str = "", before: int = 0, limit: int = PAGE, q: str = "") -> dict:
    """The log newest first: one part's records (or all), one day's (or every day's), older than `before` (a seq),
    and with `q`, only records whose kind or fields hold it."""
    limit = max(1, min(PAGE_MAX, int(limit or PAGE)))
    sql, args = "SELECT seq, ts, kind, body FROM records WHERE 1", []
    f, fa = _kind_filter(part)
    sql, args = sql + f, args + fa
    span = day_span(day)
    if span:
        sql += " AND ts >= ? AND ts < ?"
        args += list(span)
    if before:
        sql += " AND seq < ?"
        args.append(int(before))
    if q:
        sql += " AND (kind LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\')"
        args += [_like(q.replace(" ", "_")), _like(q)]
    rows = _q(app, sql + " ORDER BY seq DESC LIMIT ?", (*args, limit + 1))
    out = [_row(*r) for r in rows[:limit]]
    if q:  # a hit in a field the console leaves out isn't a hit
        ql = q.lower()
        out = [r for r in out if ql in (r["kind"] + " " + r["text"] + " " + json.dumps(r["body"])).lower()]
    return {"rows": out, "more": len(rows) > limit, "part": part, "day": day if span else "", "q": q}


def days(app: App, n: int = 14) -> list[dict]:
    """The last n days with records: [{day, n}] newest first (for the day filter)."""
    since = time.time() - (n + 1) * 86400
    rows = _q(app, "SELECT ts FROM records WHERE ts >= ? ORDER BY seq", (since,))
    count: dict[str, int] = {}
    for (ts,) in rows:
        d = dt.date.fromtimestamp(float(ts)).isoformat()
        count[d] = count.get(d, 0) + 1
    return [{"day": d, "n": c} for d, c in sorted(count.items(), reverse=True)][:n]


# --------------------------------------------------------------------------------------------------- decisions
def _decision_row(seq, ts, raw, outcomes: dict) -> dict:
    b = _body(raw)
    did = str(b.get("id") or "")
    oc = outcomes.get(did) or []
    return {
        "id": did,
        "seq": int(seq),
        "ts": round(float(b.get("at", ts) if isinstance(b.get("at"), (int, float)) else ts), 3),
        "action": clean_text(b.get("action"), 80),
        "source": str(b.get("source") or "rules")[:40],
        "risk": str(b.get("risk_class") or "")[:20],
        "reason": clean_text(b.get("scored_reason"), 200),
        "stated": clean_text(b.get("stated_reason"), 300),
        "candidates": [
            {"action": clean_text(c.get("action"), 80), "score": c.get("score")}
            for c in (b.get("candidates") or [])[:12]
            if isinstance(c, dict)
        ],
        "setpoints": [clean_text(s, 60) for s in (b.get("setpoints") or [])[:12]],
        "claim": _claim(b.get("claim")),
        "outcome": oc[-1]["result"] if oc else "",
        "outcomes": oc,
    }


def _claim(c) -> dict | None:
    """A decision's pre-registered claim: the setpoint it named, which way, by when (cleaned like the rest)."""
    if not isinstance(c, dict) or not c.get("setpoint"):
        return None
    return {
        "setpoint": clean_text(c.get("setpoint"), 60),
        "effect": "+" if c.get("effect") == "+" else "-",
        "by": clean_text(c.get("by"), 40),
    }


def _outcomes(app: App, after_seq: int) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for seq, ts, raw in _q(
        app, "SELECT seq, ts, body FROM records WHERE kind = 'outcome' AND seq > ? ORDER BY seq", (after_seq,)
    ):
        b = _body(raw)
        out.setdefault(str(b.get("decision") or ""), []).append(
            {"seq": int(seq), "ts": float(ts), "result": str(b.get("result") or "")[:40], "value": b.get("value")}
        )
    return out


def decisions(app: App, limit: int = DECISIONS, before: int = 0) -> list[dict]:
    """The newest decisions it made on its own, each with its reasons and what came of it."""
    sql, args = "SELECT seq, ts, body FROM records WHERE kind = 'decision'", []
    if before:
        sql += " AND seq < ?"
        args.append(int(before))
    rows = _q(app, sql + " ORDER BY seq DESC LIMIT ?", (*args, max(1, min(PAGE_MAX, int(limit)))))
    if not rows:
        return []
    oc = _outcomes(app, min(int(r[0]) for r in rows))
    return [_decision_row(*r, oc) for r in rows]


def decision(app: App, did: str) -> dict | None:
    """One decision with its reasons and the evidence behind it: what came of it, what the log holds around it,
    what it has learned about this kind of action (trust for its class, values of the action, misses in the last day),
    its earlier decisions of the same action, and the journal lines that cite it."""
    if not HEX.match(did or ""):
        return None
    rows = _q(
        app,
        "SELECT seq, ts, body FROM records WHERE kind = 'decision' AND body LIKE ? ESCAPE '\\' "
        "ORDER BY seq DESC LIMIT 1",
        (_like(f'"id":"{did}"'),),
    )
    if not rows:
        return None
    d = _decision_row(*rows[0], _outcomes(app, int(rows[0][0])))
    d["evidence"] = evidence(app, d)
    return d


def evidence(app: App, d: dict) -> dict:
    seq, ts = d["seq"], d["ts"]
    around = [
        _row(*r)
        for r in _q(
            app,
            "SELECT seq, ts, kind, body FROM records WHERE ts >= ? AND ts <= ? AND seq != ? ORDER BY seq LIMIT 40",
            (ts - AROUND_S, ts + AROUND_S, seq),
        )
    ]
    before = [r for r in around if r["seq"] < seq][-12:]
    after = [r for r in around if r["seq"] > seq][:12]
    action = d["action"]
    earlier = [
        {"seq": int(s), "ts": float(t)}
        for s, t in _q(
            app,
            "SELECT seq, ts FROM records WHERE kind = 'decision' AND seq < ? AND body LIKE ? ESCAPE '\\' "
            "ORDER BY seq DESC LIMIT 6",
            (seq, _like(f'"action":"{action}"')),
        )
    ]
    learned: list[list[str]] = []
    try:
        c = mind.connect(app)
        klass = d["risk"]
        if not klass:
            from kurooto.mind import risk

            klass = risk.classify(action)
        if klass:
            t = c.trust(klass)
            n = ((t or {}).get("meta") or {}).get("n") or {}
            from kurooto.mind import risk, trust

            if klass in risk.PRIORS:
                p = trust.p10((t or {}).get("meta"), klass, time.time())
                learned.append(
                    [
                        f"Trust for {klass} ({risk.LABELS.get(klass, '')})",
                        f"{p:.2f}; OK {n.get('ok', 0)}, undo {n.get('undo', 0)}, complaints {n.get('complaint', 0)}",
                    ]
                )
            else:
                learned.append(["Its class", f"{klass}: {risk.LABELS.get(klass, 'not known')}"])
        qs = [r for r in c.values_rows("Q:") if str(r["key"]).endswith("|" + action)]
        if qs:
            vals = [float(r["value"]) for r in qs]
            learned.append(["Learned value", f"{sum(vals) / len(vals):+.3f} over {len(qs)} situation(s)"])
        neg = c.vars_rows(f"negd:{action}")
        if neg and float(neg[0]["value"] or 0):
            learned.append(["Bad outcomes in the last day", str(int(float(neg[0]["value"])))])
    except Exception:  # the score tables may not exist yet
        pass
    return {
        "before": before,
        "after": after,
        "earlier": earlier,
        "learned": learned,
        "journal": _journal_citing(app, seq, ts),
    }


def _journal_citing(app: App, seq: int, ts: float) -> list[dict]:
    """Journal lines (that day and the next) that cite this record, struck ones left out."""
    from kurooto.mind import journal

    out = []
    day = dt.date.fromtimestamp(ts)
    for d in (day, day + dt.timedelta(days=1)):
        e = jload(app.paths.state / journal.DIR / f"{d.isoformat()}.json", None)
        for ln in (e or {}).get("lines", []) if isinstance(e, dict) else []:
            if seq in (ln.get("seqs") or []) and not ln.get("struck"):
                out.append({"day": d.isoformat(), "text": clean_text(ln.get("text"), 200)})
    return out[:6]


# ------------------------------------------------------------------------------------------------------ parts
def _tips() -> dict:
    from importlib import resources

    try:
        d = json.loads(resources.files("kurooto").joinpath("data", "settings-help.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for k, v in (d or {}).items() if isinstance(d, dict) else ():
        if isinstance(v, dict):
            v = v.get("tip") or v.get("short") or v.get("what") or ""
        if isinstance(v, str) and v:
            out[str(k)] = v
    return out


def _flat(d: dict, pre: str) -> dict:
    out = {}
    for k, v in (d or {}).items():
        key = f"{pre}.{k}"
        if isinstance(v, dict) and v and not key.endswith(".thresholds"):
            out.update(_flat(v, key))
        else:
            out[key] = v
    return out


def _shown(v):
    """A setting's value as the console shows it: folders in a list are counted, not named."""
    if isinstance(v, list):
        if any(isinstance(x, str) and ("/" in x or "\\" in x) for x in v):
            return f"{len(v)} folder{'s' if len(v) != 1 else ''}"
        return v[:12]
    if isinstance(v, str):
        return clean_text(v, 80)
    return v


# which settings belong to a part, beyond its own `mind.<x>.` prefix
EXTRA = {
    "log": ["mind.anchor_every", "mind.hardened", "mind.console."],
    "budget": ["mind.stimulation.", "mind.talk.", "mind.pest."],
}
EXCLUDE = {"tom": ["mind.tom.attention"]}


def _keys_for(cid: str, key: str, flat: dict) -> list[str]:
    pre: list[str] = []
    if cid == "phone":
        pre = ["mind.senses.phone."]
    elif key.endswith(".on"):
        pre = [key[: -len("on")]]
    elif key:
        pre = [key]
    pre += EXTRA.get(cid, [])
    out = [k for k in flat if any(k == p or (p.endswith(".") and k.startswith(p)) for p in pre)]
    return [k for k in sorted(out, key=lambda k: (k != key, not k.endswith(".on"), k)) if k not in EXCLUDE.get(cid, [])]


def _activity(app: App) -> dict[str, dict]:
    """Per part: its last record (seq, ts, line) and how many it wrote in the last 24 hours."""
    head = _q(app, "SELECT MAX(seq) FROM records")
    top = int(head[0][0] or 0) if head and head[0] else 0
    since = time.time() - 86400
    out: dict[str, dict] = {}
    for kind, n, n24, last in _q(
        app,
        "SELECT kind, COUNT(*), SUM(ts >= ?), MAX(seq) FROM records WHERE seq > ? GROUP BY kind",
        (since, top - WINDOW),
    ):
        p = out.setdefault(part_of(str(kind)), {"n": 0, "n24": 0, "last": 0})
        p["n"] += int(n or 0)
        p["n24"] += int(n24 or 0)
        p["last"] = max(p["last"], int(last or 0))
    lasts = [p["last"] for p in out.values() if p["last"]]
    if lasts:
        got = {
            int(s): (float(t), str(k), r)
            for s, t, k, r in _q(
                app,
                f"SELECT seq, ts, kind, body FROM records WHERE seq IN ({','.join('?' * len(lasts))})",  # noqa: S608
                tuple(lasts),
            )
        }
        for p in out.values():
            if p["last"] in got:
                t, k, r = got[p["last"]]
                p["ts"], p["line"] = t, describe(k, _body(r))
    return out


def _now_line(app: App, cid: str) -> str:
    """What a part holds right now, in a few words (its own file; nothing it read of you)."""
    s = app.paths.state
    try:
        if cid == "workspace":
            w = (jload(s / "mind-workspace.json", {}) or {}).get("winners") or []
            return f"{len(w)} item{'s' if len(w) != 1 else ''} in the spotlight"
        if cid == "beliefs":
            rows = (jload(s / "mind-beliefs.json", {}) or {}).get("rows") or []
            return f"{len(rows)} beliefs kept, {sum(1 for r in rows if r.get('outcome') is None)} not yet settled"
        if cid == "promises":
            rows = (jload(s / "mind-promises.json", {}) or {}).get("rows") or []
            return f"{sum(1 for r in rows if r.get('state') == 'open')} open, {len(rows)} kept on file"
        if cid == "gate":
            from kurooto.mind import gate

            today = dt.date.today().isoformat()
            st = jload(s / "mind-gate.json", {}) or {}
            return f"{int((st.get('days') or {}).get(today, 0))} of {gate.day_cap(app)} unasked messages today"
        if cid == "autonomy":
            from kurooto.mind import act

            st = jload(s / act.FILE, {}) or {}
            days_ = float(app.settings.get("mind.autonomy.shadow_days") or 21)
            left = days_ - (time.time() - float(st.get("started") or time.time())) / 86400
            acts = len(st.get("acts") or [])
            return (f"in shadow, {left:.0f} days left" if left > 0 else "out of shadow") + f"; {acts} acts on file"
        if cid == "skills":
            from kurooto.mind.skills import library

            sk = library.all_skills(app)
            return f"{sum(1 for m in sk.values() if not m.get('retired'))} skills"
        if cid == "plans":
            last = jload(s / "mind-plan-last.json", {}) or {}
            return f"{len(last.get('risks') or {})} milestones, planned {last.get('on') or 'not yet'}"
        if cid == "tom":
            rows = (jload(s / "mind-tom.json", {}) or {}).get("rows") or []
            return f"{len(rows)} things it thinks of you"
        if cid == "forget":
            return f"{int((jload(s / 'mind-forget.json', {}) or {}).get('forgets') or 0)} times asked to forget"
        if cid == "improve":
            rows = (jload(s / "mind-improve.json", {}) or {}).get("rows") or []
            return f"{sum(1 for r in rows if r.get('status') == 'shadow')} challengers in shadow, {len(rows)} in all"
        if cid == "play":
            st = jload(s / "mind-play.json", {}) or {}
            return f"{len(st.get('played') or [])} questions explored"
        if cid == "journal":
            from kurooto.mind import journal

            idx = jload(s / journal.DIR / "index.json", {}) or {}
            return f"last written {max(idx)}" if idx else "nothing written yet"
        if cid == "story":
            from kurooto.mind import story

            d = s / story.DIR / "weeks"
            n = len(list(d.glob("*.json"))) if d.is_dir() else 0
            return f"{n} chapter{'s' if n != 1 else ''}"
    except Exception:
        return ""
    return ""


def parts(app: App, act: dict | None = None) -> list[dict]:
    """Each island's parts: on or off, its switch and every setting it has (with what it does), next to what it's
    doing (its last record, how many in the last day, what it holds now, the Brain page's numbers)."""
    from kurooto.core import brainview

    on_ = mind.on(app)
    flat = _flat((app.settings.all() or {}).get("mind") or {}, "mind")
    tips = _tips()
    act = _activity(app) if act is None else act
    try:
        st = mind.connect(app).state() if on_ else {}
    except Exception:
        st = {}
    out = []
    for iid, name, tag, comps in brainview.ISLANDS:
        rows = []
        for cid, cname, key, desc in comps:
            if cid == "phone":
                live = on_ and any(app.settings.get(f"mind.senses.phone.{p}") for p in brainview.PHONE)
            elif key:
                live = on_ and bool(app.settings.get(key))
            else:
                live = on_
            shadow = live and cid in brainview.SHADOW and brainview._shadow(app, cid)  # noqa: SLF001
            a = act.get(cid) or {}
            rows.append(
                {
                    "id": cid,
                    "name": cname,
                    "desc": desc,
                    "on": bool(live),
                    "state": "off" if not live else ("shadow" if shadow else "on"),
                    "switch": key or "",
                    "settings": [
                        {"key": k, "value": _shown(flat[k]), "tip": tips.get(k, "")} for k in _keys_for(cid, key, flat)
                    ],
                    "doing": {
                        "last": a.get("ts"),
                        "line": a.get("line", ""),
                        "n24": a.get("n24", 0),
                        "n": a.get("n", 0),
                        "now": _now_line(app, cid) if live else "",
                        "metrics": brainview._metrics(app, cid, st) if live else [],  # noqa: SLF001
                    },
                }
            )
        out.append({"id": iid, "name": name, "tag": tag, "color": brainview.COLORS[iid], "parts": rows})
    return out


# ------------------------------------------------------------------------------- beliefs, experiments, skills ...
def beliefs(app: App, limit: int = 120) -> dict:
    from kurooto.mind import beliefs as b

    rows = (jload(app.paths.state / b.FILE, {}) or {}).get("rows") or []
    out, hidden = [], 0
    for r in reversed(rows):
        if private(r.get("text")) or private(r.get("topic")):
            hidden += 1
            continue
        out.append(
            {
                "id": str(r.get("id") or "")[:60],
                "text": clean_text(r.get("text"), 200),
                "source": str(r.get("source") or ""),
                "confidence": r.get("confidence"),
                "topic": clean_text(r.get("topic"), 40),
                "at": r.get("at"),
                "outcome": r.get("outcome"),
                "settled": r.get("settled"),
            }
        )
    try:
        brier = {k: {"n": n, "brier": round(v, 3)} for k, (n, v) in b.brier(app).items()}
    except Exception:
        brier = {}
    return {"on": b.on(app), "rows": out[:limit], "total": len(rows), "hidden": hidden, "brier": brier}


def experiments(app: App) -> dict:
    """The lab's projects (protocol, batches, wins, replications), self-improvement's challengers, and play."""
    from kurooto.mind.lab import runner

    lab = []
    try:
        projects = runner.projects(app) if mind.part_on(app, "lab") else {}
    except Exception:
        projects = {}
    for slug, root in projects.items():
        try:
            st, p, _ = runner.status(app, slug, root)
        except Exception:
            st, p = "unknown", None
        d = runner.folder(app, slug)
        regs = sorted(d.glob("prereg-*.json")) if d.is_dir() else []
        res = sorted(d.glob("results-*.json")) if d.is_dir() else []
        wins = reps = 0
        last = None
        for f in res:
            a = (jload(f, {}) or {}).get("analysis") or {}
            wins += len(a.get("wins") or [])
            reps += len(a.get("replicated") or [])
        if res:
            r = jload(res[-1], {}) or {}
            a = r.get("analysis") or {}
            last = {
                "batch": res[-1].stem.split("-")[-1],
                "ok": a.get("n_ok"),
                "failed": a.get("n_failed"),
                "wins": len(a.get("wins") or []),
                "replicated": len(a.get("replicated") or []),
                "nulls": [clean_text(x, 40) for x in (a.get("nulls") or [])[:8]],
                "baseline": r.get("baseline"),
            }
        pre = jload(regs[-1], {}) if regs else {}
        q = jload(d / "queue.json", {}) if d.is_dir() else {}
        lab.append(
            {
                "project": slug,
                "protocol": st,
                "objective": clean_text(getattr(p, "objective", "") if p else "", 120),
                "metric": clean_text((pre or {}).get("metric") or (getattr(p, "metric", "") if p else ""), 60),
                "hypothesis": clean_text((pre or {}).get("hypothesis"), 200),
                "registered": len(regs),
                "finished": len(res),
                "wins": wins,
                "replicated": reps,
                "rate": round(reps / wins, 3) if wins else None,
                "waiting": len((q or {}).get("pending") or []),
                "last": last,
            }
        )
    imp = [
        {
            "id": str(r.get("id") or "")[:20],
            "layer": str(r.get("layer") or ""),
            "title": clean_text(r.get("title"), 120),
            "status": str(r.get("status") or ""),
            "shadow_until": r.get("shadow_until"),
        }
        for r in ((jload(app.paths.state / "mind-improve.json", {}) or {}).get("rows") or [])[-30:]
    ][::-1]
    play = jload(app.paths.state / "mind-play.json", {}) or {}
    return {
        "lab": lab,
        "lab_on": mind.part_on(app, "lab"),
        "improve": imp,
        "improve_on": mind.part_on(app, "improve"),
        "play": {
            "on": mind.part_on(app, "play"),
            "explored": len(play.get("played") or []),
            "credited": len(play.get("credits") or {}),
            "outputs": len(play.get("outputs") or {}),
        },
    }


def skills(app: App) -> dict:
    from kurooto.mind.skills import library

    rows = []
    try:
        sk = library.all_skills(app)
    except Exception:
        sk = {}
    for slug, m in sorted(sk.items(), key=lambda kv: -float(kv[1].get("updated") or 0)):
        if private(m.get("title")) or private(m.get("when")):
            continue
        rows.append(
            {
                "slug": str(slug)[:60],
                "title": clean_text(m.get("title"), 120),
                "when": clean_text(m.get("when"), 160),
                "kind": str(m.get("kind") or ""),
                "status": str(m.get("status") or ""),
                "uses": int(m.get("uses") or 0),
                "ok": int(m.get("ok") or 0),
                "fail": int(m.get("fail") or 0),
                "retired": bool(m.get("retired")),
                "source": str(m.get("source") or ""),
                "created": m.get("created"),
                "last_used": m.get("last_used"),
            }
        )
    return {"on": mind.part_on(app, "skills"), "rows": rows}


def plans(app: App) -> dict:
    """The milestones the week plans weigh (from deadlines, projects and goals you said), each with the chance of
    missing it from the last plan, and how well past plans held. No simulation runs here."""
    from kurooto.mind.plans import tree

    if not mind.part_on(app, "plans"):
        return {"on": False, "rows": []}
    last = jload(app.paths.state / "mind-plan-last.json", {}) or {}
    risks = last.get("risks") or {}
    preds = ((jload(app.paths.state / tree.FILE, {}) or {}).get("predictions") or [])[-1:]
    p50 = {k: v.get("p50") for k, v in ((preds[0] if preds else {}).get("nodes") or {}).items()}
    try:
        nodes = tree.build(app)
    except Exception:
        nodes = []
    rows = []
    for n in nodes:
        if private(n.title):
            continue
        rows.append(
            {
                "id": n.id,
                "title": clean_text(n.title, 100),
                "kind": n.kind,
                "source": n.source,
                "due": n.due.timestamp(),
                "effort_h": round(n.effort_h, 2),
                "guessed": n.guessed,
                "done": round(n.done_frac, 2),
                "risk": risks.get(n.id),
                "p50": p50.get(n.id),
            }
        )
    try:
        from kurooto.mind.plans import score

        n, frac, skill = score.calibration(app)
        cal = {"n": n, "on_time": frac, "skill": skill}
    except Exception:
        cal = {"n": 0, "on_time": None, "skill": None}
    return {"on": True, "rows": rows[:40], "planned": last.get("on"), "calibration": cal}


def model(app: App, limit: int = 80) -> dict:
    """The model of you: what it thinks you know, believe, want, prefer and attend to, each with its source."""
    st = jload(app.paths.state / "mind-tom.json", {}) or {}
    rows = st.get("rows") or []
    counts: dict[str, int] = {}
    out = []
    for r in sorted(rows, key=lambda r: -float(r.get("updated") or 0)):
        counts[str(r.get("part"))] = counts.get(str(r.get("part")), 0) + 1
        if private(r.get("claim")) or private(r.get("subject")):
            continue
        out.append(
            {
                "id": str(r.get("id") or "")[:40],
                "part": str(r.get("part") or ""),
                "subject": clean_text(r.get("subject"), 60),
                "claim": clean_text(r.get("claim"), 160),
                "source": str(r.get("source") or ""),
                "confidence": r.get("confidence"),
                "updated": r.get("updated"),
                "evidence": len(r.get("evidence") or []),
            }
        )
    return {
        "on": mind.part_on(app, "tom"),
        "counts": counts,
        "rows": out[:limit],
        "forgot": len(st.get("forgot") or []),
        "denied": int(st.get("denied") or 0),
    }


def thinking(app: App) -> dict:
    """The spotlight: what won the last cycle (its words only when the item isn't about you)."""
    st = jload(app.paths.state / "mind-workspace.json", {}) or {}
    rows = []
    for w in st.get("winners") or []:
        hide = bool(w.get("private")) or private(w.get("text"))
        rows.append(
            {
                "item": str(w.get("item_id") or "")[:60],
                "kind": str(w.get("kind") or ""),
                "text": "" if hide else clean_text(w.get("text"), 120),
                "salience": round(float(w.get("salience") or 0), 3),
                "source": str(w.get("source") or ""),
                "pinned": bool(w.get("pinned")),
                "since": w.get("since"),
            }
        )
    return {
        "on": mind.part_on(app, "workspace"),
        "rows": rows,
        "at": st.get("cycle_at") or None,
        "pins": len(st.get("pins") or []),
        "mutes": len(st.get("mutes") or []),
        "vetoes": len(st.get("vetoes") or []),
    }


def senses(app: App) -> dict:
    """Counts only: for each sense, on or off and how many readings it kept today."""
    from kurooto.mind.senses import phone

    p = app.paths.state / "mind-senses" / "senses.db"
    start = dt.datetime.combine(dt.date.today(), dt.time()).timestamp()
    counts: dict[str, int] = {}
    if p.exists():
        db = sqlite3.connect(f"{p.resolve().as_uri()}?mode=ro", uri=True, timeout=10)
        try:
            counts = {
                str(s): int(n)
                for s, n in db.execute("SELECT sensor, COUNT(*) FROM events WHERE t >= ? GROUP BY sensor", (start,))
            }
        except sqlite3.Error:
            counts = {}
        finally:
            db.close()
    rows = [
        {"id": "intero", "name": "its own machine", "on": bool(app.settings.get("mind.senses.intero"))},
        {"id": "activity", "name": "your activity", "on": bool(app.settings.get("mind.senses.activity"))},
    ] + [
        {"id": f"phone:{s}", "name": f"phone {s}", "on": bool(app.settings.get(f"mind.senses.phone.{s}"))}
        for s in phone.SENSORS
    ]
    for r in rows:
        r["today"] = counts.get(r["id"], 0)
    return {"rows": rows}


def memory(app: App, act: dict | None = None) -> dict:
    """What it forgot (counts and times, never what), its stops and limits, promises, and the journal's and story's
    headings."""
    from kurooto.mind import journal, stops, story

    s = app.paths.state
    since = time.time() - 30 * 86400
    forgot = [
        {"seq": int(q), "ts": float(t), "n": int(_body(r).get("n") or 0)}
        for q, t, r in _q(
            app, "SELECT seq, ts, body FROM records WHERE kind = 'forget_event' ORDER BY seq DESC LIMIT 20"
        )
    ]
    from kurooto.mind.log import Record

    recs = [
        Record(int(q), float(t), str(k), _body(r), "", "")
        for q, t, k, r in _q(
            app,
            "SELECT seq, ts, kind, body FROM records WHERE ts >= ? AND kind IN "
            "('stop_span','power_pause','power_resume','module_enabled','module_disabled') ORDER BY seq",
            (since,),
        )
    ]
    try:
        spans = stops.spans(recs, time.time())
    except Exception:
        spans = []
    crash = _q(
        app,
        "SELECT COUNT(*) FROM records WHERE ts >= ? AND kind IN "
        "('kurooto_crashed','module_failed','mind_keeper_exited')",
        (since,),
    )
    limits: list[list[str]] = []
    try:
        from kurooto.mind import gate

        g = jload(s / "mind-gate.json", {}) or {}
        today = dt.date.today().isoformat()
        num = lambda k, d: gate._num(app, k, d)  # noqa: E731, SLF001
        touches = sum(((g.get("touches") or {}).get(today) or {}).values())
        muted = sum(1 for m in (g.get("mutes") or {}).values() if float(m.get("until", 0)) > time.time())
        limits += [
            ["Unasked messages today", f"{int((g.get('days') or {}).get(today, 0))} of {gate.day_cap(app)}"],
            ["In the last hour", f"{len(g.get('hour') or [])} of {num('max_per_hour', 3)}"],
            ["Touches today", f"{touches} of {num('touches_per_day', 3)}"],
            ["Feelings this week", f"{len(g.get('feelings') or [])} of {num('feelings_per_week', 3)}"],
            ["Held back, waiting", str(len(g.get("held") or []))],
            ["Kinds muted", str(muted)],
        ]  # fmt: skip
    except Exception:
        pass
    idx = jload(s / journal.DIR / "index.json", {}) or {}
    jrows = [
        {"day": d, "lines": v.get("lines", 0), "rejected": v.get("rejected", 0), "facts": v.get("facts", 0)}
        for d, v in sorted(idx.items(), reverse=True)[:30]
        if isinstance(v, dict)
    ]
    wk = s / story.DIR / "weeks"
    chapters = []
    for f in sorted(wk.glob("*.json"), reverse=True)[:12] if wk.is_dir() else []:
        c = jload(f, {}) or {}
        lines = c.get("lines") or []
        chapters.append(
            {
                "week": str(c.get("week") or f.stem),
                "lines": sum(1 for ln in lines if not ln.get("struck")),
                "struck": sum(1 for ln in lines if ln.get("struck")),
                "quoted": len(c.get("quoted") or []),
            }
        )
    prom = (jload(s / "mind-promises.json", {}) or {}).get("rows") or []
    pcount = {k: sum(1 for r in prom if r.get("state") == k) for k in ("open", "kept", "broken", "renegotiated")}
    return {
        "forgot": {
            "times": int((jload(s / "mind-forget.json", {}) or {}).get("forgets") or 0),
            "events": forgot,
            "model": len((jload(s / "mind-tom.json", {}) or {}).get("forgot") or []),
        },
        "stops": {
            "spans": [{"kind": x.kind, "start": x.start, "end": x.end} for x in spans[-20:]][::-1],
            "crashes": int(crash[0][0] or 0) if crash else 0,
        },
        "limits": limits,
        "promises": {
            "counts": pcount,
            "rows": [
                {"text": clean_text(r.get("text"), 120), "due": r.get("due"), "state": r.get("state")}
                for r in sorted(prom, key=lambda r: -float(r.get("due") or 0))[:12]
            ],
        },
        "journal": jrows,
        "story": chapters,
    }


# ---------------------------------------------------------------------------------------------------- search
def search(app: App, q: str, limit: int = SEARCH_MAX) -> dict:
    """Across what it has logged (the log's kinds and fields), its beliefs, the model of you, skills, plans, lab
    projects and its settings."""
    q = " ".join(str(q or "").split())[:80]
    if len(q) < 2:
        return {"q": q, "log": [], "other": []}
    ql = q.lower()
    log = timeline(app, q=q, limit=limit)["rows"]
    other = []
    for r in beliefs(app)["rows"]:
        if ql in r["text"].lower() or ql in r["topic"].lower():
            sure = f", {round(float(r['confidence']) * 100)}% sure" if isinstance(r["confidence"], (int, float)) else ""
            other.append({"in": "beliefs", "text": r["text"], "note": f"{r['source']}{sure}"})
    for r in model(app, 600)["rows"]:
        if ql in r["claim"].lower() or ql in r["subject"].lower():
            other.append({"in": "model", "text": r["claim"], "note": f"{r['part']}, {r['source']}"})
    for r in skills(app)["rows"]:
        if ql in (r["slug"] + " " + r["title"] + " " + r["when"]).lower():
            other.append({"in": "skills", "text": r["title"], "note": r["slug"]})
    for r in plans(app).get("rows") or []:
        if ql in r["title"].lower():
            other.append({"in": "plans", "text": r["title"], "note": r["kind"]})
    for r in experiments(app)["lab"]:
        if ql in (r["project"] + " " + r["objective"] + " " + r["metric"]).lower():
            other.append({"in": "experiments", "text": r["project"], "note": r["protocol"]})
    for isl in parts(app):
        for p in isl["parts"]:
            if ql in (p["name"] + " " + p["desc"]).lower():
                other.append({"in": "parts", "text": p["name"], "note": p["state"], "part": p["id"]})
            for st in p["settings"]:
                if ql in (st["key"] + " " + st["tip"]).lower():
                    v = st["value"]
                    word = ("on" if v else "off") if isinstance(v, bool) else str(v)
                    other.append({"in": "settings", "text": st["key"], "note": word, "part": p["id"]})
    return {"q": q, "log": log, "other": other[:limit]}


# ----------------------------------------------------------------------------------------------------- whole
# --------------------------------------------------------------------------------- measurements (0.8.14)
# What each part changed outwardly: a message held, reworded or made quieter, an act it did on its own, a decision it
# recorded before acting, a promise it made you. Information only: nothing is turned off by these numbers.
OUTWARD_KINDS = ("decision", "mind_act", "gate_receipt", "gate_lint", "gate_mute", "gate_call", "promise_made")
AUDIT_DAYS = 30
LATENCY_DAYS = 7
# a decision's action names the part that made it ("message:mind.feeling", "proposal:lab", "job:play"...)
ACTION_PART = (("feeling", "feelings"), ("lab", "lab"), ("play", "play"), ("plan", "plans"), ("dream", "dreaming"),
               ("forecast", "forecast"), ("checkin", "forecast"), ("belief", "beliefs"), ("precedent", "precedents"),
               ("improve", "improve"), ("skill", "skills"), ("promise", "promises"), ("workspace", "workspace"),
               ("arbiter", "workspace"), ("concern", "feelings"), ("study", "tom"), ("quiz", "tom"))  # fmt: skip


def _decision_part(body: dict) -> str:
    act = f"{body.get('action') or ''} {body.get('scored_reason') or ''}".lower()
    return next((part for word, part in ACTION_PART if word in act), "autonomy")


def audit(app: App, days: int = AUDIT_DAYS) -> dict:
    """The decoration audit: per Brain part, how many outward decisions it changed in the last `days` days, from the
    mind log. A part that's on and changed none is labelled decoration (it still runs; this is information)."""
    since = time.time() - days * 86400
    marks = ",".join("?" * len(OUTWARD_KINDS))
    count: dict[str, int] = {}
    sql = f"SELECT kind, body FROM records WHERE ts >= ? AND kind IN ({marks})"  # noqa: S608 (placeholders only)
    for kind, raw in _q(app, sql, (since, *OUTWARD_KINDS)):
        part = _decision_part(_body(raw)) if kind == "decision" else part_of(kind)
        count[part] = count.get(part, 0) + 1
    rows = []
    for isl in parts(app, {}):
        for p in isl["parts"]:
            n = count.pop(p["id"], 0)
            rows.append(
                {"id": p["id"], "name": p["name"], "on": p["on"], "changed": n, "decoration": bool(p["on"] and n == 0)}
            )
    for pid, n in sorted(count.items()):  # a part the islands don't list (dreaming, an add-on's)
        rows.append({"id": pid, "name": pid, "on": True, "changed": n, "decoration": False})
    return {"days": days, "parts": rows, "decoration": [r["id"] for r in rows if r["decoration"]]}


def _p95(xs: list[float]) -> float | None:
    xs = sorted(x for x in xs if x >= 0)
    return round(xs[min(len(xs) - 1, int(0.95 * len(xs)))], 2) if xs else None


def latency(app: App, days: int = LATENCY_DAYS) -> dict:
    """p95 reply latency of your own requests (lane "you", queued to finished) over the last `days` days, and Brain's
    own share of it: the p95 of building its block for a request (providers/context.py mind_context)."""
    secs: list[float] = []
    jobs = getattr(app, "jobs", None)
    if jobs is not None:
        try:
            rows = jobs._read(  # noqa: SLF001
                "select created, finished from jobs where coalesce(lane, 'you') = 'you' and finished is not null "
                "and created >= ? and status not in ('queued', 'running')",
                (time.time() - days * 86400,),
                one=False,
            )
            secs = [float(f) - float(c) for c, f in rows if c is not None and f is not None]
        except Exception:
            secs = []
    try:
        from kurooto.providers.context import p95_ms

        ctx = p95_ms()
    except Exception:
        ctx = None
    return {"days": days, "n": len(secs), "p95_s": _p95(secs), "context_p95_ms": ctx, "brain_on": mind.on(app)}


def measurements(app: App) -> dict:
    """/mind measures and the console's Measurements: the decoration audit and the reply latency. Information only."""
    return {"audit": audit(app), "latency": latency(app)}


def measures_text(app: App) -> str:
    """/mind measures in words."""
    m = measurements(app)
    a, lat = m["audit"], m["latency"]
    lines = [f"What each part changed outwardly in {a['days']} days (information only; nothing is turned off by it):"]
    for r in sorted(a["parts"], key=lambda r: (-r["changed"], r["name"])):
        if r["on"] or r["changed"]:
            tail = "  decoration: on, changed nothing" if r["decoration"] else ""
            lines.append(f"  {r['name']}: {r['changed']}{tail}")
    if lat["p95_s"] is None:
        lines.append(f"Reply latency: no requests of yours finished in {lat['days']} days.")
    else:
        lines.append(f"Reply latency (your requests, {lat['days']} days, {lat['n']}): p95 {lat['p95_s']:.1f} s.")
    if lat["context_p95_ms"] is not None:
        lines.append(f"Brain's share (its block for each request): p95 {lat['context_p95_ms']:.1f} ms.")
    return "\n".join(lines)


def head(app: App) -> dict:
    on_ = mind.on(app)
    try:
        c = mind.connect(app)
        up, _ = c.running() if on_ else (False, 0)
    except Exception:
        up = False
    h = _q(app, "SELECT MAX(seq), COUNT(*) FROM records")
    seq, n = (int(h[0][0] or 0), int(h[0][1] or 0)) if h else (0, 0)
    return {"on": on_, "running": bool(up), "head": seq, "records": n}


def _safe_measurements(app: App) -> dict | None:
    try:
        return measurements(app)
    except Exception:
        return None


def snapshot(app: App, phone: bool = False) -> dict:
    """Everything the console shows, bounded. The phone's copy also carries the newest decisions' evidence and a
    longer timeline, so it opens and filters without the computer."""
    act = _activity(app)
    ps = parts(app, act)
    flat = [p for isl in ps for p in isl["parts"]]
    out = {
        "v": 1,
        "kind": "brain",
        **head(app),
        "console": on(app),
        "parts_on": sum(1 for p in flat if p["on"]),
        "parts_total": len(flat),
        "islands": ps,
        "decisions": decisions(app),
        "timeline": timeline(app, limit=PHONE_ROWS if phone else PAGE),
        "days": days(app),
        "thinking": thinking(app),
        "beliefs": beliefs(app, 60 if phone else 120),
        "experiments": experiments(app),
        "skills": skills(app),
        "plans": plans(app),
        "model": model(app, 50 if phone else 80),
        "senses": senses(app),
        "memory": memory(app, act),
        "measurements": _safe_measurements(app),
        "made": int(time.time()),
    }
    if phone:
        for d in out["decisions"][:PHONE_DECISIONS]:
            try:
                d["evidence"] = evidence(app, d)
            except Exception:
                d["evidence"] = None
    return out


def view(app: App, q: dict | None = None) -> tuple[int, dict]:
    """GET /api/brain/console. q: view=all|timeline|decision|search, with part, day, before, limit, id, q."""
    q = q or {}
    if not on(app):
        return 200, {"off": True, "on": mind.on(app), "why": "The Brain console is off (mind.console.on)."}
    v = str(q.get("view") or "all")
    try:
        before, limit = int(q.get("before") or 0), int(q.get("limit") or PAGE)
    except ValueError:
        return 400, {"error": "before and limit are numbers"}
    part = str(q.get("part") or "")
    if part and not re.fullmatch(r"[a-z]{2,20}", part):
        return 400, {"error": "no such part"}
    if v == "timeline":
        return 200, timeline(app, part, str(q.get("day") or ""), before, limit, str(q.get("q") or "")[:80])
    if v == "decisions":
        return 200, {"rows": decisions(app, limit, before)}
    if v == "decision":
        d = decision(app, str(q.get("id") or ""))
        return (200, d) if d else (404, {"error": "no such decision"})
    if v == "search":
        return 200, search(app, str(q.get("q") or ""))
    if v == "measurements":
        return 200, measurements(app)
    if v == "all":
        return 200, snapshot(app)
    return 400, {"error": "which view? all, timeline, decisions, decision, search or measurements"}
