"""Curious and remembering: the two lines the morning message (modules/dreaming.py) may add. Rules only, no AI;
nothing leaves the computer.

Curious (dreaming.curious, on): a topic you asked about 3 or more times in the last 7 days that has no note, or only a
stub: "You've asked about the Fokker–Planck equation 3 times this week and there's no note on it. Want one?" with
Make a stub (a concept note in that subject's folder, linked from its course page) and Not interested (your
not-interested list, core/notinterested.py). Asking is: your requests to the AI (their titles), what calls searched
your notes for, and quiz questions you got wrong. A topic is, to stay on the safe side: the name or an alias of one of
your concept notes, or a phrase of two or three words that comes back in those and ends in a word like equation, lemma,
theorem or distribution (or a pair of names like Navier–Stokes). Nothing else counts.

Resurfacing (dreaming.resurface, on): one line from a shared past. An anniversary first (a whole number of months or
years since a project's first Log line or a repository's first commit: "A month ago today you started work on L96"),
else a concept or lecture note you last changed 10 to 30 days ago, or a subject you last practised in a quiz then,
those whose subject has an exam in the next two weeks first ("You last worked on Itô's lemma 12 days ago"). Open it
(or Practise) and Less of this (resurfacing off, with Undo).

Each comes at most once a day, and the same topic, note or project not again for 30 days
(<state>/dreaming-curious.json). What calls searched your notes for is kept 8 days at most (<state>/calls/searches.json;
/forget and privacy.keep_days clear it with the call transcripts).
"""

from __future__ import annotations

import calendar
import datetime as dt
import hashlib
import os
import re
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import conceptgraph as cg
from kurooto.core import layout
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.notinterested import matcher
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "dreaming",
    {
        "curious": True,  # a topic you asked about 3+ times this week with no note on it: one line, Make a stub
        "resurface": True,  # one line from the past: a note or quiz subject from 10-30 days ago, or an anniversary
    },
)
ASK_DAYS = 7  # how far back asking counts
ASK_MIN = 3  # asked this many times (in different requests) before it's a gap
AGAIN_DAYS = 30  # the same topic, note or project isn't brought up again for this long
PAST = (10, 30)  # a note or quiz subject last touched this many days ago may come back
STUB_WORDS = 15  # a note with fewer words of its own is a stub
SEARCH_DAYS = 8  # what calls searched for is kept this long
STUB_LINE = "A stub: you asked about this a few times. Say what it is in a line or two, then link what it needs."
# the last word of a phrase that is a topic ("the Fokker–Planck equation", "Itô's lemma", "the chain rule")
HEADS = set(
    "equation equations lemma theorem law laws principle inequality distribution distributions process processes "
    "method transform transformation algorithm series conjecture formula rule effect space spaces integral "
    "integrals operator operators matrix matrices estimator regression expansion approximation decomposition "
    "criterion identity hypothesis paradox dynamics manifold manifolds".split()
)
# words that are never part of a topic phrase: everyday request words (the concept graph's STOP is added)
REQUEST_WORDS = set(
    "explain explanation tell me about please help make write note notes quiz remind reminder today tomorrow tonight "
    "yesterday week my mine your our i im is are was do does did why who whom whose give show find need want know "
    "more some any again example examples question questions answer answers problem problems first second third last "
    "next previous same other another new main key general basic simple whole following every each all both just "
    "really very much many few lot can could would should will shall may might must hey hi hello thanks thank ok okay "
    "summary summarise summarize difference versus vs derive derivation proof prove solve solution read check send "
    "open file files disk storage free simulate compute calculate define describe compare plot implement code learn "
    "study revise review practise practice understand apply get got go going look like".split()
)
WORD = re.compile(r"[^\W\d_][\w'’\-–]*")
CHUNK = re.compile(r"[.,;:!?()\[\]{}\"“”/|\n]+")
NAMES = re.compile(r"[A-Z][a-z'’]+[-–][A-Z][a-z'’]+")  # Navier–Stokes, Black-Scholes (after accents are folded)
DATE = re.compile(r"(\d{4}-\d\d-\d\d)")


def fold(s: str) -> str:
    s = re.sub(r"[‐-―]", "-", s or "")  # dashes stay dashes
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def key(tok: str) -> str:
    """A word as it's compared: no accents, lowercase, no possessive, a hyphen between names a space."""
    t = re.sub(r"['’]s$", "", fold(tok).lower())
    return re.sub(r"[-–—]+", " ", t.replace("'", "").replace("’", "")).strip()


def squash(text: str) -> str:
    return "".join(key(t) for t in WORD.findall(text or "")).replace(" ", "")


def chunks(text: str) -> list[list[str]]:
    return [WORD.findall(c) for c in CHUNK.split(text or "") if c.strip()]


def stop(tok: str) -> bool:
    k = key(tok)
    return not k or k in cg.STOP or k in REQUEST_WORDS


def phrases(text: str) -> dict[str, str]:
    """{key: as written} for the topic-shaped phrases in one request."""
    out: dict[str, str] = {}
    for toks in chunks(text):
        runs, cur = [], []
        for t in [*toks, ""]:
            if t and not stop(t):
                cur.append(t)
            elif cur:
                runs.append(cur)
                cur = []
        for run in runs:
            for i in range(len(run)):
                for n in (1, 2, 3):
                    g = run[i : i + n]
                    if len(g) < n:
                        break
                    if (n > 1 and key(g[-1]) in HEADS) or (n == 1 and NAMES.fullmatch(fold(g[0]))):
                        out.setdefault(" ".join(key(t) for t in g), " ".join(g))
    return out


def grams(text: str) -> set[str]:
    """Every run of 1 to 5 words of a request, as keys (for matching note names)."""
    out = set()
    for toks in chunks(text):
        ks = [key(t) for t in toks]
        for i in range(len(ks)):
            for n in range(1, 6):
                if i + n <= len(ks):
                    out.add(" ".join(ks[i : i + n]))
    return out


# ------------------------------------------------------------------------------------------------ what you asked
def searches_file(app: App) -> Path:
    return Path(app.paths.state) / "calls" / "searches.json"


def searched(app: App, query: str) -> None:
    """A call searched your notes (modules/calls: search_notes): kept SEARCH_DAYS for the curious line."""
    q = re.sub(r"\s+", " ", str(query or "")).strip()[:120]
    if not q:
        return
    f = searches_file(app)
    cut = time.time() - SEARCH_DAYS * 86400
    rows = [r for r in jload(f, []) or [] if isinstance(r, dict) and float(r.get("at") or 0) > cut]
    jsave(f, [*rows[-199:], {"at": time.time(), "q": q}])


def asks(app: App, days: int = ASK_DAYS) -> list[dict]:
    """What you asked in the last `days`: [{text, via, subject}]: your AI requests' titles, calls' note searches and
    the quiz questions you got wrong."""
    cut = time.time() - days * 86400
    out = []
    for _jid, title, _p, _r, _f, lane, then in app.jobs.finished_since(cut, limit=1000):
        if lane == "you" and not then and title and title != "(forgotten)":
            out.append({"text": title, "via": "request"})
    for r in jload(searches_file(app), []) or []:
        if isinstance(r, dict) and float(r.get("at") or 0) > cut and r.get("q"):
            out.append({"text": r["q"], "via": "call"})
    quiz = app.modules.get("quiz")
    if quiz is not None:
        day = (now() - dt.timedelta(days=days)).date().isoformat()
        for f in sorted(quiz._dir().glob("*.json")) if quiz._dir().is_dir() else []:
            for it in quiz.load(f.stem)["items"].values():
                for h in it.get("history") or []:
                    if str(h.get("date") or "") >= day and int(h.get("q") or 0) < 3:
                        out.append({"text": it["text"], "via": "quiz", "subject": f.stem})
    subj = app.modules.get("subjects")
    if subj is not None and app.is_on("subjects"):
        for a in out:
            if not a.get("subject"):
                found = subj.find_in(a["text"])
                a["subject"] = found[0] if found else ""
    return out


def is_stub(n: cg.Note) -> bool:
    return len(n.head.replace(STUB_LINE, "").split()) < STUB_WORDS


def note_names(app: App, notes: dict[str, cg.Note]) -> set[str]:
    """Every name a note goes by, squashed: concept notes' titles and aliases, and every note's file name."""
    out = set()
    for n in notes.values():
        for name in n.names:
            out |= {squash(name), cg.normalise(name)}
    root = Path(app.workspace)
    for _dir, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.endswith(".md"):
                stem = re.sub(r"^\d{4}-\d\d-\d\d-?", "", f[:-3])
                out |= {squash(stem), cg.normalise(stem)}
    return out - {""}


def gaps(app: App) -> list[dict]:
    """Topics asked about ASK_MIN+ times with no note or only a stub, most asked first:
    [{key, topic, n, subject, note (the stub's path in the notes, or "")}]."""
    said = asks(app)
    if len(said) < ASK_MIN:
        return []
    notes = cg.scan(app)
    have = note_names(app, notes)
    skip = matcher(app)
    out: dict[str, dict] = {}

    def subject_of(hits: list[dict]) -> str:
        c = Counter(a["subject"] for a in hits if a.get("subject"))
        return c.most_common(1)[0][0] if c else ""

    g = [grams(a["text"]) for a in said]
    for n in notes.values():  # your concept notes, by name: only a stub is a gap
        keys = set()
        for name in [n.title, *n.aliases]:
            k = " ".join(key(t) for t in WORD.findall(name))
            if k and (" " in k or len(k) >= 6) and k not in cg.STOP:
                keys |= {k, k + "s"}
        hits = [a for a, gs in zip(said, g, strict=True) if keys & gs]
        if len(hits) >= ASK_MIN and is_stub(n) and not skip(n.title):
            k = squash(n.title)
            out[k] = {"key": k, "topic": n.title, "n": len(hits), "subject": subject_of(hits), "note": n.slug}
    seen: Counter = Counter()
    shown: dict[str, Counter] = {}
    for a in said:  # phrases that come back and look like a topic
        for k, as_written in phrases(a["text"]).items():
            seen[k] += 1
            shown.setdefault(k, Counter())[as_written] += 1
    for k, c in seen.items():
        if c < ASK_MIN or any(k != o and f" {k} " in f" {o} " and seen[o] >= c for o in seen):
            continue  # too few, or part of a longer phrase asked as often
        topic = shown[k].most_common(1)[0][0]
        sq = squash(topic)
        bare = squash(topic.rsplit(" ", 1)[0])  # "fokkerplanck": a note on Fokker-Planck counts too
        if sq in out or {sq, cg.normalise(topic)} & have or (len(bare) >= 6 and bare in have):
            continue
        if skip(topic) or skip(fold(topic)):
            continue
        if not any("'" in t or "’" in t for t in topic.split()):
            topic = "the " + topic
        hits = [a for a in said if k in phrases(a["text"])]
        out[sq] = {"key": sq, "topic": topic, "n": c, "subject": subject_of(hits), "note": ""}
    return sorted(out.values(), key=lambda x: (-x["n"], x["topic"].lower()))


# ------------------------------------------------------------------------------------------------ the past
def months_since(start: dt.date, today: dt.date) -> int | None:
    """Whole months from start to today when today is that day of the month (the month's last day for a 31st)."""
    n = (today.year - start.year) * 12 + today.month - start.month
    last = calendar.monthrange(today.year, today.month)[1]
    if n >= 1 and (today.day == start.day or (start.day > last and today.day == last)):
        return n
    return None


def ago(n: int) -> str:
    if n % 12 == 0:
        return "A year ago today" if n == 12 else f"{n // 12} years ago today"
    return "A month ago today" if n == 1 else f"{n} months ago today"


def first_log(text: str) -> dt.date | None:
    """The first date under a project note's "## Log"."""
    m = re.search(r"(?ms)^## Log\s*\n(.*?)(?=^## |\Z)", text)
    d = DATE.search(m[1]) if m else None
    try:
        return dt.date.fromisoformat(d[1]) if d else None
    except ValueError:
        return None


def title_of(p: Path, text: str) -> str:
    h1 = re.search(r"^#\s+(.+?)\s*$", cg.parse_front(text)[1], re.M)
    return h1[1] if h1 else p.stem.replace("-", " ")


def anniversaries(app: App, st: dict) -> list[dict]:
    """Projects started, and repositories first committed to, a whole number of months or years ago today."""
    today, out = now().date(), []
    lay, root = layout.of(app), Path(app.workspace)
    shape = lay.rel("project", project="*")
    for p in sorted(root.glob(shape)) if not Path(shape).is_absolute() else []:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        start = first_log(text)
        n = months_since(start, today) if start else None
        if n:
            name = title_of(p, text)
            out.append(
                {
                    "key": f"anniv:{lay.shown(p)}:{n}",
                    "kind": "anniv",
                    "path": lay.shown(p),
                    "topic": name,
                    "line": f"{ago(n)} you started work on {name}.",
                }
            )
    rs = app.modules.get("research")
    if rs is not None and app.is_on("research"):
        roots = st.setdefault("roots", {})
        git = None
        for project, repos in rs.projects().items():
            for repo in repos:
                if repo not in roots:
                    git = git or rs.git_exe()
                    roots[repo] = _first_commit(git, Path(repo)) if git else ""
                try:
                    n = months_since(dt.date.fromisoformat(roots[repo]), today) if roots[repo] else None
                except ValueError:
                    n = None
                if n:
                    from kurooto.modules import research

                    note = research.project_note(app, project)
                    out.append(
                        {
                            "key": f"anniv:{repo}:{n}",
                            "kind": "anniv",
                            "topic": Path(repo).name,
                            "path": lay.shown(note) if note.is_file() else "",
                            "line": f"{ago(n)} you made the first commit in {Path(repo).name}.",
                        }
                    )
    return out


def _first_commit(git: str, repo: Path) -> str:
    from kurooto.core import proc

    if not (repo / ".git").exists():
        return ""
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"}
    roots = proc.run([git, "-C", str(repo), "rev-list", "--max-parents=0", "HEAD"], timeout=30, env=env).out.split()
    if not roots:
        return ""
    r = proc.run([git, "-C", str(repo), "log", "-1", "--format=%cd", "--date=short", roots[-1]], timeout=30, env=env)
    return r.out.strip()[:10]


def faded(app: App) -> list[dict]:
    """Concept and lecture notes last changed, and quiz subjects last practised, PAST days ago; those whose subject
    has an exam in the next two weeks first, then the longest ago."""
    today, lay, root = now().date(), layout.of(app), Path(app.workspace)
    subj = app.modules.get("subjects")
    slugs = [s["slug"] for s in subj.subjects()] if subj is not None and app.is_on("subjects") else []
    dl = app.modules.get("deadlines")
    exams: dict[str, dict] = {}
    if dl is not None and app.is_on("deadlines"):
        for r in dl.exams_soon(14):
            if r.get("subject"):
                exams.setdefault(r["subject"], r)
    skip = matcher(app)
    out = []

    def add(key_: str, kind: str, topic: str, age: int, subject: str, path: str = "") -> None:
        if PAST[0] <= age <= PAST[1] and not skip(topic):
            ex = exams.get(subject)
            what = f"practised {topic} in a quiz" if kind == "quiz" else f"worked on {topic}"
            line = f"You last {what} {age} days ago" + (f"; {ex['title']} is {ex['when']}." if ex else ".")
            out.append(
                {
                    "key": key_,
                    "kind": kind,
                    "topic": topic,
                    "subject": subject,
                    "path": path,
                    "line": line,
                    "rank": (0 if ex else 1, ex["hours"] if ex else 0, -age),
                }
            )

    files = [n.path for n in cg.scan(app).values()]
    pages = {lay.path(k, subject=s) for s in slugs for k in ("course", "class_log", "exam_prep", "doubts")}
    for s in slugs:
        d = lay.path("subject", subject=s)
        files += sorted(d.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-*.md")) if d.is_dir() else []
    for f in dict.fromkeys(files):
        n = cg.read_note(root, f) if lay.inside_notes(f) and f not in pages else None
        if n is None or is_stub(n):
            continue
        try:
            age = (today - dt.date.fromtimestamp(f.stat().st_mtime)).days
        except OSError:
            continue
        subject = next((p for p in Path(n.slug).parts[:-1] if p in slugs), "")
        add(f"note:{n.slug}", "note", n.title, age, subject, lay.shown(f))
    quiz = app.modules.get("quiz")
    if quiz is not None and app.is_on("quiz") and quiz._dir().is_dir():
        for f in sorted(quiz._dir().glob("*.json")):
            days = [str(h.get("date")) for it in quiz.load(f.stem)["items"].values() for h in it.get("history") or []]
            try:
                last = dt.date.fromisoformat(max(days)) if days else None
            except ValueError:
                last = None
            if last:
                add(f"quiz:{f.stem}", "quiz", subj.name_of(f.stem) if slugs else f.stem, (today - last).days, f.stem)
    return sorted(out, key=lambda x: x["rank"])


# ------------------------------------------------------------------------------------------------ the two lines
def state_file(app: App) -> Path:
    return Path(app.paths.state) / "dreaming-curious.json"


def pick(app: App, kind: str, items: list[dict], send: bool) -> dict | None:
    """The first item not brought up in AGAIN_DAYS (one already shown today stays today's). Marked shown, and kept
    for its buttons, when the morning message is sent."""
    f = state_file(app)
    st = jload(f, {}) or {}
    today = now().date().isoformat()
    cut = (now().date() - dt.timedelta(days=AGAIN_DAYS)).isoformat()
    shown = {k: d for k, d in (st.get("shown") or {}).items() if d > cut}
    acted = {k: d for k, d in (st.get("acted") or {}).items() if d > cut}  # Make a stub, Not interested
    was = (st.get("today") or {}).get(kind) or ["", ""]
    if was[0] == today:
        it = next((x for x in items if x["key"] == was[1] and x["key"] not in acted), None)
    else:
        it = next((x for x in items if x["key"] not in shown and x["key"] not in acted), None)
    if it is None:
        return None
    it["id"] = hashlib.sha1(f"{kind}|{it['key']}".encode(), usedforsecurity=False).hexdigest()[:8]
    offers = dict(st.get("offers") or {})
    offers.pop(it["id"], None)
    offers[it["id"]] = {k: v for k, v in it.items() if k not in ("rank", "line")}
    st["offers"] = dict(list(offers.items())[-30:])
    if send:
        shown[it["key"]] = today
        st.setdefault("today", {})[kind] = [today, it["key"]]
        app.events.emit("dreaming_" + kind, what=it.get("kind") or "gap")
    st["shown"], st["acted"] = shown, acted
    jsave(f, st)
    return it


def acted(app: App, key_: str) -> None:
    """A button settled this topic: it doesn't come back for AGAIN_DAYS, today included."""
    f = state_file(app)
    st = jload(f, {}) or {}
    st.setdefault("acted", {})[key_] = now().date().isoformat()
    jsave(f, st)


def curious_line(app: App, send: bool) -> tuple[str, list]:
    it = pick(app, "curious", gaps(app), send)
    if it is None:
        return "", []
    if it["note"]:
        return (
            f"You've asked about {it['topic']} {it['n']} times this week and its note is only a stub "
            f"([[{it['note']}]]). Want to fill it in?",
            [[("Open it", f"drm:{it['id']}:open"), ("Not interested", f"drm:{it['id']}:no")]],
        )
    return (
        f"You've asked about {it['topic']} {it['n']} times this week and there's no note on it. Want one?",
        [[("Make a stub", f"drm:{it['id']}:stub"), ("Not interested", f"drm:{it['id']}:no")]],
    )


def resurface_line(app: App, send: bool) -> tuple[str, list]:
    st = jload(state_file(app), {}) or {}
    items = anniversaries(app, st)
    if st.get("roots"):  # first commits never change: kept so git runs once per repository
        cur = jload(state_file(app), {}) or {}
        jsave(state_file(app), {**cur, "roots": st["roots"]})
    it = pick(app, "resurface", items + faded(app), send)
    if it is None:
        return "", []
    first = [("Practise", f"drm:{it['id']}:quiz")] if it["kind"] == "quiz" else []
    first += [("Open it", f"drm:{it['id']}:open")] if it.get("path") else []
    return it["line"], [[*first, ("Less of this", f"drm:{it['id']}:less")]]


# ------------------------------------------------------------------------------------------------ the buttons
def make_stub(app: App, it: dict) -> str:
    from kurooto.core.tools import add_to_section, write_note_file

    lay = layout.of(app)
    name = re.sub(r"^the ", "", it["topic"])
    name = name[:1].upper() + name[1:]
    subj, slug = it.get("subject") or "", cg.slug_of(name)
    if subj or "{subject}" not in lay.template("concept"):
        kind, path = "concept", lay.path("concept", subject=subj or "-", slug=slug)
    else:  # no subject to put it in (the default layout keeps concepts in subject folders): a loose note
        kind, path = "note", lay.path("note", slug=slug)
    target = lay.shown(path).removesuffix(".md")
    if path.exists():
        return f"There's a note there already: {target}."
    head = lay.frontmatter(kind, path, title=name, **({"subject": subj} if subj else {}))
    try:
        write_note_file(path, f"{head}# {name}\n\n{STUB_LINE}\n\n## Links\n", create=True)
    except FileExistsError:
        return f"There's a note there already: {target}."
    course = lay.path("course", subject=subj) if subj else None
    if course is not None and course.is_file():
        text = course.read_text(encoding="utf-8")
        if target not in lay.note_targets(text, course):  # in either link style
            write_note_file(
                course, add_to_section(text, "Concepts", f"- {lay.note_link(target, name, from_note=course)}")
            )
    app.events.emit("dreaming_stub", kind=kind, linked=bool(course and course.is_file()))
    return f"Made a stub: {target}."


def button(app: App, ref: str, act: str) -> str:
    """drm:<offer>:stub|no|open|quiz|less, under the morning message's curious and resurfacing lines."""
    it = ((jload(state_file(app), {}) or {}).get("offers") or {}).get(ref)
    if not it:
        return "That's gone already."
    if act in ("stub", "no"):
        acted(app, it["key"])
    if act == "stub":
        return make_stub(app, it)[:190]
    if act == "no":
        from kurooto.core.notinterested import add_topic

        topic = re.sub(r"^the ", "", it["topic"])
        add_topic(app, topic, "from the morning message")
        return f"OK, not interested in {topic} (/unignore {topic} takes it back)."[:190]
    if act == "open":
        from kurooto.core import opener

        p = Path(app.workspace) / (it.get("path") or f"{it.get('note')}.md")
        if not p.is_file():
            return "That note isn't there any more."
        ok, note = opener.open_note(app.settings, p, app.workspace)
        return (note or ("Opened it on your computer." if ok else "Couldn't open it."))[:190]
    if act == "quiz":
        quiz = app.modules.get("quiz")
        if quiz is None or not app.is_on("quiz"):
            return "Quiz is off."
        return quiz.start_session(it.get("subject") or None)[:190]
    if act == "less":
        from kurooto.core.calm import Change

        ok, said, uid = app.calm.apply(
            Change("no more lines from the past in the morning message", key="dreaming.resurface", value=False),
            "dreaming.morning",
        )
        if ok:
            app.notify(f"Done: {said}.", kind="info", why="asked", buttons=[[("Undo", f"calm:{uid}:undo")]])
        return f"Done: {said}."[:190]
    return "ok"
