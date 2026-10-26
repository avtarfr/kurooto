"""Feeding Brain what happened before it was switched on (0.8.1; every source and its own chain in 0.8.7). Off until
you turn it on: `mind.backfill.on`, then one switch per source (`mind.backfill.<source>`, all on).

Brain's log began the day Brain was switched on, so its read, forecasts and plans started with no past. This reads
Kurooto's own stores, read-only, and hands what they hold to the scorekeeper in batches. The scorekeeper files each row
on that source's own hash chain in `history.db` (mind/log.py PastLog), in the time order of the original events, never
in the live log's chain; one witness record per batch goes in the live log. History is never a reward and never an
outcome: it trains priors only (what a normal day was, your pace, how you finish deadlines; invariants I-3 and I-4).
Only ids and numbers pass (records.clean_past): never the words of a message, never names, never health or money.

The sources, each read from where Kurooto writes it, and skipped when it isn't there:

    events     events.jsonl (and events.jsonl.1): the mirrored kinds (deadlines added and moved, reminders set and
               fired, calls, AI requests, buttons, power)
    jobs       jobs.db: one row per AI request (effort, ok or not, how long, its lane), never its words
    deadlines  deadlines.json: when each was due and when it was marked done (its kind and a hashed subject id)
    checkins   checkins/<day>.json: each check-in's name and what became of it (planned, asked, answered, skipped)
    quiz       quiz/<subject>.json: per day and subject id, questions asked, right and wrong
    calls      calls/rings.json: each ring (answered, missed ...), the feature that placed it, and its length from the
               transcript files' names (never their contents)
    learning   learning/history.db: AI requests and calls indexed per day (counts only; chats are left out)
    study      study/<day>.json: the day's study time (seconds, how many subjects)

    plan(app)      a dry run: counts per source and kind, and the dates; nothing written
    run(app)       the import, source by source, with a progress bar (`<logs>/mind-backfill.log`): resumable and
                   idempotent (each row has a fixed key; a source restarts from its chain's head)
    verify(app)    the chains, and every head the live log witnessed
    forget(app)    remove all of it (or one source), and what was learned only from it
    the priors     daily, study_days, weekday_baselines, forecast_priors, pace_prior, deadline_pattern: small functions
                   the read, the forecast, week plans and the model of you call
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sqlite3
import statistics
import time
from collections import defaultdict
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.mind import log as mlog
from kurooto.mind import records

if TYPE_CHECKING:
    from kurooto.app import App

PART = "backfill"  # its switch: mind.backfill.on

register_defaults(
    "mind",
    {
        "backfill": {
            "on": False,  # off until you turn it on: Brain reads what Kurooto kept before it was on (`/mind backfill`)
            "events": True,  # read Kurooto's own event history (deadlines, reminders, calls, AI requests, buttons)
            "jobs": True,  # read the AI request history: effort, whether it worked, how long it took (never its words)
            "deadlines": True,  # read when past deadlines were due and when you marked them done (no titles)
            "checkins": True,  # read which check-ins were asked, answered or skipped each day (never what you said)
            "quiz": True,  # read quiz history: questions asked, right and wrong, per day and subject (no questions)
            "calls": True,  # read past calls: answered or missed, who placed them, how long (never what was said)
            "learning": True,  # read the request and call index's counts per day (never its words; chats left out)
            "study": True,  # read the study tracker's time per day (for your real pace in week plans)
        }
    },
)

SOURCES = mlog.PAST_SOURCES
BATCH = 500
MAX_DAY_S = 14 * 3600  # a day's study can't count for more (as plans/pace.MAX_DAY_H)
DAY_FILE = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")
TRANSCRIPT = re.compile(r"^(\d{4}-\d{2}-\d{2}-\d{6})")
CALL_MAX_S = 3 * 3600


def _state_file(app: App) -> Path:
    return Path(app.paths.state) / "mind" / "history-import.json"


def _log_file(app: App) -> Path:
    return Path(app.paths.logs) / "mind-backfill.log"


def _epoch(ts) -> float | None:
    try:
        return dt.datetime.fromisoformat(str(ts)).timestamp()  # stamped in local time
    except (TypeError, ValueError):
        return None


def _noon(day: str) -> float | None:
    try:
        return dt.datetime.combine(dt.date.fromisoformat(day), dt.time(12)).timestamp()
    except ValueError:
        return None


def _h(*parts) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:16]


def subject_id(slug: str) -> str:
    """A subject as an id, never its name: "s" and 8 hex digits."""
    return "s" + hashlib.sha256(f"kurooto-past:{slug}".encode()).hexdigest()[:8]


def _cutoff(app: App) -> float | None:
    """When Brain's own log began: what happened from then on is already in it."""
    recs = mind.connect(app).log(after=0, limit=1)
    return recs[0].ts if recs else None


def _before(until: float | None) -> Callable[[float], bool]:
    lim = until if until is not None else time.time()
    return lambda t: t < lim


def _day_before(until: float | None) -> Callable[[str], bool]:
    last = dt.date.fromtimestamp(until) if until is not None else dt.date.today()
    return lambda day: day < last.isoformat()  # whole days only: the day Brain began is its own


def _ro(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    try:
        return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=10)
    except sqlite3.Error:
        return None


def _word(v, allowed: frozenset[str]) -> str:
    v = str(v or "").lower()
    return v if v in allowed else "other"


# ---------------------------------------------------------------------------------------------------- the readers
# Each yields (key, at, kind, body) for what happened before `until`. They read only; what they hand on is checked
# again by the scorekeeper (records.clean_past), so a field picked here by mistake still can't carry words.
Row = tuple[str, float, str, dict]


def read_events(app: App, until: float | None) -> Iterator[Row]:
    st = Path(app.paths.state)
    ok = _before(until)
    seen: dict[str, int] = defaultdict(int)
    for f in (st / "events.jsonl.1", st / "events.jsonl"):  # the older file first: it moved aside when full
        if not f.exists():
            continue
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(e, dict):
                    continue
                kind = str(e.get("kind") or "")
                at = _epoch(e.get("ts"))
                if at is None or not mlog.mirrored(kind) or not ok(at):
                    continue
                h = _h(line.strip())
                seen[h] += 1  # the same line twice (same second, same fields) is two events
                body = {k: v for k, v in e.items() if k not in ("ts", "kind")}
                yield f"ev:{h}:{seen[h]}", at, kind, body


def read_jobs(app: App, until: float | None) -> Iterator[Row]:
    from kurooto.mind.records import PAST_WORDS

    db = _ro(Path(app.paths.state) / "jobs.db")
    if db is None:
        return
    ok = _before(until)
    try:
        have = {r[1] for r in db.execute("pragma table_info(jobs)")}
        cols = [
            c for c in ("id", "created", "effort", "status", "verdict", "seconds", "lane", "background") if c in have
        ]
        if not {"id", "created"} <= set(cols):
            return
        sql = f"select {', '.join(cols)} from jobs where status not in ('queued', 'running')"  # noqa: S608
        rows = db.execute(sql).fetchall()
    except sqlite3.Error:
        return
    finally:
        db.close()
    for r in rows:
        d = dict(zip(cols, r, strict=True))
        try:
            at = float(d["created"])
        except (TypeError, ValueError):
            continue
        if not ok(at):
            continue
        body = {
            "effort": _word(d.get("effort"), PAST_WORDS["effort"]),
            "verdict": _word(d.get("verdict"), PAST_WORDS["verdict"]),
            "ok": str(d.get("verdict") or "") == "ok",
            "lane": _word(d.get("lane") or "you", PAST_WORDS["lane"]),
            "background": bool(d.get("background")),
        }
        if isinstance(d.get("seconds"), (int, float)):
            body["seconds"] = round(float(d["seconds"]), 1)
        yield f"job:{_h(d['id'])}", at, "job", body


def read_deadlines(app: App, until: float | None) -> Iterator[Row]:
    from kurooto.mind.records import PAST_WORDS

    items = jload(Path(app.paths.state) / "deadlines.json", {}) or {}
    if not isinstance(items, dict):
        return
    ok = _before(until)
    for iid, it in items.items():
        if not isinstance(it, dict):
            continue
        due = _epoch(it.get("due"))
        done = _epoch(it.get("done_at")) if it.get("status") == "done" else None
        base = {"dkind": _word(it.get("kind"), PAST_WORDS["dkind"])}
        if it.get("subject"):
            base["subj"] = subject_id(str(it["subject"]))
        if due is not None and ok(due):
            body = {**base, "state": _word(it.get("status"), PAST_WORDS["state"])}
            if done is not None:
                body["done_before_h"] = round((due - done) / 3600, 2)
            yield f"dl:{_h(iid)}:due", due, "deadline_due", body
        if done is not None and ok(done):
            body = dict(base)
            if due is not None:
                body["done_before_h"] = round((due - done) / 3600, 2)
            yield f"dl:{_h(iid)}:done", done, "deadline_finished", body


def read_checkins(app: App, until: float | None) -> Iterator[Row]:
    from kurooto.mind.records import PAST_WORDS

    d = Path(app.paths.state) / "checkins"
    if not d.is_dir():
        return
    ok = _day_before(until)
    for f in sorted(d.iterdir()):
        if not DAY_FILE.match(f.name) or not ok(f.stem):
            continue
        plan = jload(f, {}) or {}
        if not isinstance(plan, dict):
            continue
        for name, c in plan.items():
            if not isinstance(c, dict) or name not in PAST_WORDS["checkin"]:
                continue
            try:
                t = dt.time.fromisoformat(str(c.get("time") or ""))
                day = dt.date.fromisoformat(f.stem) + dt.timedelta(days=1 if t < dt.time(5) else 0)
                at = dt.datetime.combine(day, t).timestamp()
            except ValueError:
                at = _noon(f.stem)
            if at is None:
                continue
            state = _word(c.get("status"), PAST_WORDS["state"])
            yield (
                f"ci:{f.stem}:{name}",
                at,
                "checkin",
                {"checkin": name, "state": state, "answered": state == "answered"},
            )


def read_quiz(app: App, until: float | None) -> Iterator[Row]:
    d = Path(app.paths.state) / "quiz"
    if not d.is_dir():
        return
    ok = _day_before(until)
    days: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    for f in sorted(d.glob("*.json")):
        st = jload(f, {}) or {}
        items = st.get("items") if isinstance(st, dict) else None
        if not isinstance(items, dict):
            continue  # session.json and the like
        subj = subject_id(f.stem)
        for it in items.values():
            for h in (it.get("history") if isinstance(it, dict) else None) or []:
                day = str(h.get("date") or "") if isinstance(h, dict) else ""
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) or not ok(day):
                    continue
                q = h.get("q")
                c = days[(day, subj)]
                c[0] += 1
                if isinstance(q, (int, float)) and not isinstance(q, bool):
                    c[1 if q >= 3 else 2] += 1
    for (day, subj), (asked, right, wrong) in sorted(days.items()):
        at = _noon(day)
        if at is not None:
            yield f"qz:{day}:{subj}", at, "quiz_day", {"subj": subj, "asked": asked, "right": right, "wrong": wrong}


def read_calls(app: App, until: float | None) -> Iterator[Row]:
    from kurooto.mind.records import PAST_WORDS

    d = Path(app.paths.state) / "calls"
    rings = jload(d / "rings.json", {}) or {}
    if not isinstance(rings, dict) or not rings:
        return
    try:
        from kurooto.modules.catalog import CATALOG

        known = {str(m.id) for m in CATALOG}
    except Exception:
        known = set()
    ends = []  # when each transcript was written, from its file name only (never opened)
    td = d / "transcripts"
    if td.is_dir():
        for f in td.iterdir():
            m = TRANSCRIPT.match(f.name)
            if m:
                try:
                    ends.append(dt.datetime.strptime(m[1], "%Y-%m-%d-%H%M%S").timestamp())
                except ValueError:
                    pass
    ends.sort()
    ok = _before(until)
    order = []
    for s, r in rings.items():
        try:
            at = float(r.get("at") or 0) if isinstance(r, dict) else 0.0
        except (TypeError, ValueError):
            at = 0.0
        if at:
            order.append((at, str(s), r))
    order.sort(key=lambda x: (x[0], x[1]))
    for i, (at, since, r) in enumerate(order):
        if not ok(at):
            continue
        mod = str(r.get("key") or "").split(":")[0]
        state = _word(r.get("state"), PAST_WORDS["state"])
        again = r.get("again")
        body = {
            "state": state,
            "module": mod if mod in known else "other",
            "alarm": bool(r.get("alarm")),
            "again": again if isinstance(again, int) and not isinstance(again, bool) else 0,
        }
        if state == "answered":
            nxt = order[i + 1][0] if i + 1 < len(order) else at + CALL_MAX_S
            end = next((e for e in ends if at < e <= min(nxt, at + CALL_MAX_S)), None)
            if end is not None:
                body["minutes"] = round((end - at) / 60, 1)
        yield f"call:{_h(since)}", at, "call", body


def read_learning(app: App, until: float | None) -> Iterator[Row]:
    db = _ro(Path(app.paths.state) / "learning" / "history.db")
    if db is None:
        return
    try:
        rows = db.execute("select kind, at from docs where kind in ('request', 'call')").fetchall()
    except sqlite3.Error:
        return
    finally:
        db.close()
    days: dict[tuple[str, str], int] = defaultdict(int)
    ok = _day_before(until)
    for kind, at in rows:
        try:
            day = dt.date.fromtimestamp(float(at)).isoformat()
        except (TypeError, ValueError, OverflowError, OSError):
            continue
        if ok(day):
            days[(day, str(kind))] += 1
    for (day, kind), n in sorted(days.items()):
        at = _noon(day)
        if at is not None:
            yield f"ln:{day}:{kind}", at, "learning_day", {"via": kind, "n": n}


def read_study(app: App, until: float | None) -> Iterator[Row]:
    d = Path(app.paths.state) / "study"
    if not d.is_dir():
        return
    ok = _day_before(until)
    for f in sorted(d.iterdir()):
        if not DAY_FILE.match(f.name) or not ok(f.stem):
            continue
        day = jload(f, {}) or {}
        if not isinstance(day, dict):
            continue
        vals = {
            str(k): float(v)
            for k, v in day.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0
        }
        at = _noon(f.stem)
        if at is None or not vals:
            continue
        body = {
            "seconds": round(min(sum(vals.values()), MAX_DAY_S)),
            "subjects": len({k.split("|")[0] for k in vals}),
            "manual_s": round(sum(v for k, v in vals.items() if k.endswith("|manual"))),
        }
        yield f"st:{f.stem}", at, "study_day", body


READERS: dict[str, Callable[[App, float | None], Iterator[Row]]] = {
    "events": read_events,
    "jobs": read_jobs,
    "deadlines": read_deadlines,
    "checkins": read_checkins,
    "quiz": read_quiz,
    "calls": read_calls,
    "learning": read_learning,
    "study": read_study,
}


def enabled(app: App) -> list[str]:
    """The sources that are read: each with its switch on, and none while mind.backfill.on is off."""
    if not app.settings.get("mind.backfill.on"):
        return []
    return [s for s in SOURCES if app.settings.get(f"mind.backfill.{s}") is not False]


def rows_of(app: App, source: str, until: float | None) -> list[Row]:
    """A source's rows before `until`, in time order (ties by key): the order its chain keeps."""
    try:
        return sorted(READERS[source](app, until), key=lambda r: (r[1], r[0]))
    except OSError:
        return []


# ---------------------------------------------------------------------------------------------------- the import
def plan(app: App) -> dict:
    """A dry run: how many rows each source would give, of which kinds, and the dates they span. Writes nothing.
    {rows, kinds, from, to, sources: {source: {rows, kinds}}}, for every source whose own switch is on (even with
    mind.backfill.on off, so you can look before you turn it on)."""
    until = _cutoff(app)
    kinds_all: dict[str, int] = defaultdict(int)
    out: dict = {"rows": 0, "from": None, "to": None, "sources": {}}
    for s in SOURCES:
        if app.settings.get(f"mind.backfill.{s}") is False:
            continue
        rows = rows_of(app, s, until)
        kinds: dict[str, int] = defaultdict(int)
        for _, _at, kind, _ in rows:
            kinds[kind] += 1
            kinds_all[kind] += 1
        if rows:
            out["from"] = rows[0][1] if out["from"] is None else min(out["from"], rows[0][1])
            out["to"] = rows[-1][1] if out["to"] is None else max(out["to"], rows[-1][1])
        out["rows"] += len(rows)
        out["sources"][s] = {"rows": len(rows), "kinds": dict(kinds)}
    out["kinds"] = dict(sorted(kinds_all.items(), key=lambda kv: -kv[1]))
    return out


def _hms(s: float | None) -> str:
    if s is None:
        return "?"
    s = int(max(0, s))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def bar(label: str, done: int, total: int, started: float, width: int = 20) -> str:
    """A tqdm-style line: `jobs       |████████░░░░░░░░░░░░| 400/1,000  40% 0:00:03 ETA 0:00:04`."""
    frac = done / total if total else 1.0
    fill = int(round(frac * width))
    took = time.monotonic() - started
    eta = took * (total - done) / done if done else (0.0 if not total else None)
    return (
        f"{label:<10} |{'█' * fill}{'░' * (width - fill)}| {done:,}/{total:,} {frac:4.0%} {_hms(took)} ETA {_hms(eta)}"
    )


def _log(app: App, line: str) -> None:
    try:
        f = _log_file(app)
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as fh:
            fh.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {line}\n")
    except OSError:
        pass


def run(app: App, progress: Callable[[str, int, int], None] | None = None, only: str = "") -> dict:
    """Import every source that's on (or `only` one), source by source, before Brain's own log began. Safe to run
    again and to stop halfway: each source starts from its chain's head, and the scorekeeper skips a key it already
    has. {rows, batches, late, sources: {source: {rows, total, dup, late}}, bars, from, to}, or {error, ...}."""
    if not mind.on(app) or not app.settings.get("mind.backfill.on"):
        return {"error": "Turn on Brain and mind.backfill.on first."}
    todo = [s for s in enabled(app) if not only or s == only]
    if not todo:
        return {"error": f"mind.backfill.{only} is off." if only else "Every source is off (mind.backfill.<source>)."}
    c = mind.connect(app)
    if not c.running()[0]:
        return {"error": "The scorekeeper isn't running."}
    until = _cutoff(app)
    heads = c.past_heads()
    out: dict = {"rows": 0, "batches": 0, "late": 0, "sources": {}, "bars": [], "from": None, "to": None}
    _log(app, f"start: {', '.join(todo)}")
    for s in todo:
        rows = rows_of(app, s, until)
        _n, head_ts = heads.get(s, (0, 0.0))
        fresh = [r for r in rows if r[1] >= head_ts]  # resume: what's older than the chain's head is in already
        done = len(rows) - len(fresh)
        started = time.monotonic()
        res = {"rows": 0, "total": len(rows), "dup": 0, "late": 0}
        out["sources"][s] = res
        for i in range(0, len(fresh), BATCH):
            chunk = fresh[i : i + BATCH]
            batch = f"{s}-{int(chunk[0][1])}-{i // BATCH:05d}"
            payload = [  # cleaned here already, so no words cross even to the scorekeeper (which checks again)
                {"key": k, "at": at, "kind": kind, "body": records.clean_past(s, kind, body)}
                for k, at, kind, body in chunk
            ]
            r = c.import_history(s, batch, payload)
            if not r.get("ok"):
                _log(app, f"{s}: the scorekeeper refused or didn't answer at {done:,}/{len(rows):,}; stopped")
                out["bars"].append(bar(s, done, len(rows), started))
                out["error"] = f"The scorekeeper refused a batch of {s}; run it again to carry on from there."
                return out
            res["rows"] += int(r.get("rows") or 0)
            res["dup"] += int(r.get("dup") or 0)
            res["late"] += int(r.get("late") or 0)
            out["batches"] += 1
            done += len(chunk)
            _log(app, bar(s, done, len(rows), started))
            if progress:
                progress(s, done, len(rows))
        line = bar(s, len(rows), len(rows), started)
        out["bars"].append(line)
        _log(app, f"{line} added {res['rows']:,}")
        out["rows"] += res["rows"]
        out["late"] += res["late"]
        if rows:
            out["from"] = rows[0][1] if out["from"] is None else min(out["from"], rows[0][1])
            out["to"] = rows[-1][1] if out["to"] is None else max(out["to"], rows[-1][1])
    st = jload(_state_file(app), {}) or {}
    st.update({"done_at": time.time(), "from": out["from"], "to": out["to"]})
    st.setdefault("sources", {}).update({s: v["total"] for s, v in out["sources"].items()})
    jsave(_state_file(app), st)
    _log(app, f"done: {out['rows']:,} rows added")
    if mind.part_on(app, "tom"):
        try:
            from kurooto.mind.tom import goals

            goals.from_past(app)
        except Exception:  # noqa: S110 (the model of you catches up on its own next run)
            pass
    return out


def status(app: App) -> dict:
    """{imported, sources: {source: rows}, old (0.8.1's table, read until events is imported again), done_at, from,
    to}."""
    st = jload(_state_file(app), {}) or {}
    c = mind.connect(app)
    counts = {s: n for s, (n, _) in c.past_heads().items()}
    old = len(c.history_rows()) if not counts.get("events") else 0
    return {
        "imported": sum(counts.values()) + old,
        "sources": counts,
        "old": old,
        "done_at": st.get("done_at"),
        "from": st.get("from"),
        "to": st.get("to"),
    }


def verify(app: App) -> dict:
    return mind.connect(app).verify_history()


def forget(app: App, source: str = "") -> int:
    """Remove the imported past (one source, or all), and what was learned only from it: the model of you's rows from
    past deadlines (the other priors are worked out from the history each time, so they go with it)."""
    res = mind.connect(app).forget_history(source)
    if not source:
        try:
            _state_file(app).unlink()
        except OSError:
            pass
    if source in ("", "deadlines"):
        try:
            from kurooto.mind.tom import goals

            goals.forget_past(app)
        except Exception:  # noqa: S110
            pass
    return int(res.get("rows") or 0)


# ---------------------------------------------------------------------------------------------------- the priors
# Each reads the imported past and returns plain numbers: what a normal day, week or deadline was. Nothing here is a
# reward or an outcome (I-3, I-4), and nothing that scores reads them (test_history_is_never_reward).
def _rows(app: App, source: str, kinds=None) -> list[dict]:
    if not mind.part_on(app, "backfill"):
        return []
    return mind.connect(app).past_rows(source, kinds)


def daily(app: App) -> dict[str, dict[str, int]]:
    """{date: {kind: count}} of the imported events (0.8.1's table while the events chain is empty)."""
    if not mind.part_on(app, "backfill"):
        return {}
    rows = [(r["ts"], r["kind"]) for r in _rows(app, "events")]
    if not rows:
        rows = [(float(r["value"]), (r.get("meta") or {}).get("k")) for r in mind.connect(app).history_rows()]
    out: dict[str, dict[str, int]] = {}
    for at, k in rows:
        if not k:
            continue
        d = out.setdefault(dt.date.fromtimestamp(at).isoformat(), {})
        d[k] = d.get(k, 0) + 1
    return out


def study_days(app: App) -> dict[str, float]:
    """{date: study minutes} from the study tracker's past (days it kept; a day it didn't is unknown, not 0)."""
    return {
        dt.date.fromtimestamp(r["ts"]).isoformat(): round(float(r["body"].get("seconds") or 0) / 60, 1)
        for r in _rows(app, "study", {"study_day"})
    }


def weekday_baselines(app: App) -> dict[str, dict[int, list[float]]]:
    """{signal: {weekday: [values, oldest first]}} for the read's signals the history really holds: deadline moves
    (on a day with any imported event) and study minutes (on a day the study tracker kept). Nothing else is made up:
    no wake or sleep times, no alarm snoozes, no reply speed."""
    out: dict[str, dict[int, list[float]]] = {"deadline_moves": defaultdict(list), "study_min": defaultdict(list)}
    for day, ks in sorted(daily(app).items()):
        out["deadline_moves"][dt.date.fromisoformat(day).weekday()].append(float(ks.get("deadline_moved", 0)))
    for day, mins in sorted(study_days(app).items()):
        out["study_min"][dt.date.fromisoformat(day).weekday()].append(mins)
    return {k: dict(v) for k, v in out.items() if v}


def forecast_priors(app: App, weekday: int, min_n: int = 3) -> dict[str, list[float]]:
    """Forecast parameters for that weekday from the past (forecast.baseline over its last 8 same weekdays), for a
    channel the last 28 days can't fit yet. Only channels the history holds, with at least `min_n` same weekdays."""
    from kurooto.mind import forecast

    out = {}
    for name, by_wd in weekday_baselines(app).items():
        v = by_wd.get(weekday) or []
        if name in forecast.CHANNELS and len(v) >= min_n:
            p = forecast.baseline(name, v[-8:])
            if p is not None:
                out[name] = [round(float(x), 4) for x in p]
    return out


def pace_prior(app: App, min_n: int = 2) -> dict[int, float]:
    """{weekday: mean study hours} from the study tracker's past: week plans' prior for a weekday with few recent
    samples (instead of a flat 2 hours)."""
    by: dict[int, list[float]] = defaultdict(list)
    for day, mins in study_days(app).items():
        by[dt.date.fromisoformat(day).weekday()].append(min(mins / 60, MAX_DAY_S / 3600))
    return {wd: round(sum(v) / len(v), 2) for wd, v in by.items() if len(v) >= min_n}


def deadline_pattern(app: App) -> dict[str, dict]:
    """{kind: {n, done, late, lead_h}}: how past deadlines of each kind went: how many were due, how many were marked
    done, how many of those after their due time, and the median hours before the due time they were done (negative:
    after)."""
    out: dict[str, dict] = {}
    for r in _rows(app, "deadlines", {"deadline_due", "deadline_finished"}):
        b = r["body"]
        o = out.setdefault(str(b.get("dkind") or "other"), {"n": 0, "done": 0, "late": 0, "leads": []})
        if r["kind"] == "deadline_due":
            o["n"] += 1
        elif isinstance(b.get("done_before_h"), (int, float)):
            o["done"] += 1
            o["leads"].append(float(b["done_before_h"]))
            o["late"] += int(b["done_before_h"] < 0)
    for o in out.values():
        leads = o.pop("leads")
        o["lead_h"] = round(statistics.median(leads), 1) if leads else None
    return out


def describe(app: App) -> list[str]:
    """What /mind backfill says about the imported past: what's in, and a normal week from it."""
    st = status(app)
    if not st["imported"]:
        return ["Nothing from before Brain was on is imported."]
    out = []
    if st["sources"]:
        out.append("Imported: " + ", ".join(f"{s} {n:,}" for s, n in st["sources"].items()) + ".")
    days = daily(app)
    if days:
        out.append(f"{len(days)} days imported ({min(days)} to {max(days)}).")
    names = "Mon Tue Wed Thu Fri Sat Sun".split()
    base = weekday_baselines(app)
    if "study_min" in base:
        line = ", ".join(f"{names[i]} {sum(v) / len(v):.0f}" for i, v in sorted(base["study_min"].items()))
        out.append(f"A normal week's study, minutes a day: {line}.")
    if days:
        wd: dict[int, list[int]] = defaultdict(list)
        for day, ks in days.items():
            wd[dt.date.fromisoformat(day).weekday()].append(ks.get("reminder_fired", 0) + ks.get("deadline_added", 0))
        line = ", ".join(f"{names[i]} {sum(v) / len(v):.0f}" for i, v in sorted(wd.items()))
        out.append(f"Reminders and new deadlines a day, on average: {line}.")
    return out
