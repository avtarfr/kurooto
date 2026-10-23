"""Near-duplicate concepts in the concept graph (0.5.22): two notes that look like one concept ("Wiener process" and
"Brownian motion") come as one question a night, at most three pairs, each with Merge / Keep both / Add alias.

    found by     core/conceptgraph.py:near_duplicates: the same name, a name they share (an alias), or embeddings at
                 least 0.92 alike (the notes the night's reading touched, and a slice of the rest each night). No AI.
    Merge        the first note keeps everything: the other's typed links, its "Seen in" rows, its names (as aliases),
                 its notation, and a "Merged here" block saying what came from it. The other becomes a redirect (a
                 `merged-into` block under its title); its own text stays, unless Kurooto wrote all of it (then it
                 moved into the kept note's block). Typed link lines elsewhere that pointed at it point at the kept one.
    Keep both    they're different: never asked again.
    Add alias    both stay: the second name becomes an alias of the first, and each links the other as equivalent-to.
    Undo         every one of them: files go back to their before-copies (a file you changed since stays as it is, and
                 the message says so), and the graph's own records too.

Off: integrate.duplicates = false. /graph same asks now (also pairs asked before and not answered). State:
<state>/integrate/dupes.json; the before-copies are kept there with the pair.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import conceptgraph as cg
from kurooto.core import graphwrite as gw
from kurooto.core import layout
from kurooto.core.clock import now
from kurooto.core.tools import write_note_file

if TYPE_CHECKING:
    from kurooto.modules.integrate import Integrate

FILE = "dupes.json"
MOST = 3  # pairs a night (two when the phone app's chat is the only channel: it shows six buttons)
SWEEP = 40  # notes compared by meaning each night besides the fresh ones (a slice of the rest, in turn)
REASK_DAYS = 14  # a pair asked and not answered comes back after this long
DONE = ("merge", "keep", "alias")
WHY = {
    "name": "the same name",
    "alias": 'they share the name "{shared}"',
    "meaning": "their text means nearly the same ({shared})",
}


def day() -> str:
    return f"{now():%Y-%m-%d}"


def pid_of(key: str) -> str:
    return hashlib.sha1(key.encode(), usedforsecurity=False).hexdigest()[:8]


def load(ig: Integrate) -> dict:
    st = ig.load(FILE, {}) or {}
    st.setdefault("pairs", {})
    return st


def fresh(ig: Integrate, slugs: list[str]) -> None:
    """The notes a batch just wrote: compared by meaning with everything at the next check."""
    with ig.lock:
        st = load(ig)
        st["fresh"] = list(dict.fromkeys([*(st.get("fresh") or []), *slugs]))[-500:]
        ig.save(FILE, st)


# ------------------------------------------------------------------------------------------------ finding
def find(ig: Integrate, again: bool = False) -> tuple[list[cg.Pair], cg.Index]:
    """Up to MOST pairs to ask about now. again=True (/graph same): pairs asked before and not answered come too."""
    index = ig.index()
    st = load(ig)
    today = now().date()
    skip = set()
    for rec in st["pairs"].values():
        key = cg.pair_key(rec["a"], rec["b"])
        if rec.get("state") in DONE:
            skip.add(key)
        elif not again and rec.get("asked"):
            try:
                if (today - dt.date.fromisoformat(rec["asked"])).days < REASK_DAYS:
                    skip.add(key)
            except ValueError:
                pass
    every = sorted(index.vec)
    cur = int(st.get("cursor") or 0) % max(1, len(every)) if every else 0
    focus = list(dict.fromkeys([*(st.get("fresh") or []), *every[cur : cur + SWEEP]]))
    app_main = getattr(ig.app, "app_main", None)
    most = 2 if callable(app_main) and app_main() else MOST  # the phone app's chat shows six buttons
    pairs = cg.near_duplicates(index, skip, focus)[:most]
    if again:  # /graph same: the night's slice and fresh notes stay for the night
        return pairs, index
    with ig.lock:
        st = load(ig)
        st["cursor"] = (cur + SWEEP) if every and cur + SWEEP < len(every) else 0
        st["fresh"] = []
        ig.save(FILE, st)
    return pairs, index


def message(ig: Integrate, pairs: list[cg.Pair], index: cg.Index) -> tuple[str, list]:
    """The question and its buttons; the pairs are recorded as asked."""
    lines = ["Concept notes that may be one concept:"]
    buttons = []
    with ig.lock:
        st = load(ig)
        for i, p in enumerate(pairs, 1):
            pid = pid_of(p.key)
            old = st["pairs"].get(pid) or {}
            st["pairs"][pid] = {
                **{k: v for k, v in old.items() if k in ("history",)},
                "a": p.a,
                "b": p.b,
                "why": p.why,
                "shared": p.shared,
                "score": p.score,
                "asked": day(),
                "state": "open",
            }
            ta, tb = index.notes[p.a].title, index.notes[p.b].title
            lines.append(f"{i}. {ta} and {tb}: {WHY[p.why].format(shared=p.shared)}.")
            buttons.append(
                [
                    (f"{i} Merge", f"dup:{pid}:merge"),
                    (f"{i} Keep both", f"dup:{pid}:keep"),
                    (f"{i} Add alias", f"dup:{pid}:alias"),
                ]
            )
        ig.save(FILE, st)
    lines.append(
        "Merge keeps the first and points the second at it (nothing you wrote is deleted). Keep both: never asked "
        "again. Add alias: both stay, the second name becomes an alias of the first. Each has Undo."
    )
    return "\n".join(lines), buttons


def night(ig: Integrate, payload: dict | None = None) -> str:
    """The nightly check: one message with up to MOST pairs (none when there are none, or one went today)."""
    if not ig.app.is_on(ig.id) or not ig.setting("duplicates"):
        return ""
    if load(ig).get("sent") == day():
        return ""
    pairs, index = find(ig)
    if not pairs:
        return ""
    text, buttons = message(ig, pairs, index)
    with ig.lock:
        st = load(ig)
        st["sent"] = day()
        ig.save(FILE, st)
    ig.app.notify(text, kind="question", buttons=buttons, why="integrate.duplicates", about=f"{len(pairs)} pairs")
    ig.app.events.emit("integrate_duplicates", pairs=len(pairs))
    return text


def ask_now(ig: Integrate) -> tuple[str, list | None]:
    """/graph same: the pairs now, asked before or not."""
    pairs, index = find(ig, again=True)
    if not pairs:
        return "No concept notes look like the same concept (by name, a shared name, or meaning).", None
    return message(ig, pairs, index)


# ------------------------------------------------------------------------------------------------ the buttons
def button(ig: Integrate, pid: str, act: str) -> str:
    with ig.lock:
        st = load(ig)
        rec = st["pairs"].get(pid)
        if rec is None:
            return "That question is gone."
        if act == "undo":
            return undo(ig, pid)
        if rec.get("state") in DONE:
            return f"Already answered ({rec['state']}). Undo is under that answer."
        if act == "keep":
            rec.update(state="keep", at=now().isoformat(timespec="seconds"))
            ig.save(FILE, st)
            said = "Kept both; that pair won't be asked about again."
        elif act in ("merge", "alias"):
            index = ig.index()
            if rec["a"] not in index.notes or rec["b"] not in index.notes:
                return "One of those notes is gone, or merged already."
            said = merge(ig, pid, rec, index) if act == "merge" else alias(ig, pid, rec, index)
            if said.startswith("Not "):
                return said
        else:
            return "There's no such button."
    ig.app.events.emit("integrate_duplicate", act=act)
    ig.app.notify(said, kind="result", buttons=[[("Undo", f"dup:{pid}:undo")]], why="asked")
    return said[:190]


def _write(journal: dict, path: Path, old: str, new: str) -> None:
    if new != old:
        write_note_file(path, new)
        journal[str(path)] = [old, new]


def merge(ig: Integrate, pid: str, rec: dict, index: cg.Index) -> str:
    """Merge b into a (call with ig.lock held). Returns what to tell the user ("Not merged: ..." when it can't)."""
    a, b = rec["a"], rec["b"]
    na, nb = index.notes[a], index.notes[b]
    ta, tb = na.path.read_text(encoding="utf-8"), nb.path.read_text(encoding="utf-8")
    made = ig.load("made.json", {}) or {}
    seen = ig.load("seen.json", {}) or {}
    notation = ig.load("notation.json", {}) or {}
    today = day()
    whole = gw.made_by_graph(tb, made.get(b))
    st = load(ig)
    lay = layout.of(ig.app)  # links in your link style (notes.links), relative to the note they're in
    ra, rb = lay.shown(na.path), lay.shown(nb.path)
    in_a = lambda target, label=None: lay.note_link(target, label, from_note=na.path)  # noqa: E731
    # the note that stays
    moved = [(t, gw.relink(ln, t, lay.note_style, ra, rb)) for t, ln in gw.link_lines(tb, rb) if t not in (a, b)]
    new_a, _ = gw.add_links(ta, moved, ra)
    rows = [*(seen.get(a) or []), *[r for r in seen.get(b) or [] if r not in (seen.get(a) or [])]]
    if rows:
        new_a = gw.put_block(new_a, "seen", ig.seen_body(rows, in_a))
    new_a = ig.add_alias(new_a, nb.title, nb.aliases)
    marks = [*(notation.get(a) or []), *[r for r in notation.get(b) or [] if r not in (notation.get(a) or [])]]
    table = ig.notation_body(marks) if ig.notation_on() else ""
    if table:
        new_a = gw.put_block(new_a, "notation", table)
    merges = st.setdefault("merges", {}).setdefault(a, [])
    merges.append({"pid": pid, "from": b, "title": nb.title, "day": today, "text": gw.own_body(tb) if whole else ""})
    new_a = gw.put_block(new_a, "merges", merges_body(merges, in_a))
    if not gw.guarded(ta, new_a).ok:
        st["merges"][a] = [m for m in merges if m["pid"] != pid]
        return "Not merged: it would have changed text in the note that stays that isn't Kurooto's."
    # the note that goes
    if whole:
        new_b = gw.redirect_note(tb, a, na.title, today, lay.note_link(a, na.title, from_note=nb.path))
    else:
        new_b = gw.drop_block(gw.drop_block(gw.drop_link_lines(tb, from_rel=rb), "seen"), "notation")
        body = (
            f"Merged into {lay.note_link(a, na.title, from_note=nb.path)} on {today}: its links and where it's seen "
            "are there now; what you wrote here stays."
        )
        new_b = gw.put_block_top(new_b, "merged-into", body)
        if not gw.guarded(tb, new_b).ok:
            st["merges"][a] = [m for m in merges if m["pid"] != pid]
            return "Not merged: it would have changed text of yours in the other note."
    journal: dict[str, list[str]] = {}
    _write(journal, na.path, ta, new_a)
    _write(journal, nb.path, tb, new_b)
    for s, n in index.notes.items():  # typed links elsewhere follow
        if s in (a, b) or b not in n.typed:
            continue
        old = n.path.read_text(encoding="utf-8")
        new = gw.retarget(old, b, a, lay.note_style, lay.shown(n.path))
        if new != old and gw.guarded(old, new).ok:
            _write(journal, n.path, old, new)
    rec.update(
        state="merge",
        at=now().isoformat(timespec="seconds"),
        journal=journal,
        before={"seen": {a: seen.get(a), b: seen.get(b)}, "notation": {a: notation.get(a), b: notation.get(b)}},
    )
    st["pairs"][pid] = rec
    for name, data, moved in (("seen", seen, rows), ("notation", notation, marks)):
        if moved:
            data[a] = moved
        data.pop(b, None)
        ig.save(f"{name}.json", data)
    ig.save(FILE, st)
    ig.commit(list(journal), f"graph: merged {Path(b).name} into {Path(a).name}")
    return f"Merged {nb.title} into {na.title}; {nb.title} now points there."


def merges_body(merges: list[dict], link=None) -> str:
    """The "Merged here" block; `link(target, label)` writes a link (default: [[wikilinks]])."""
    link = link or (lambda target, label=None: f"[[{target}|{label}]]" if label else f"[[{target}]]")
    lines = ["## Merged here"]
    for m in merges:
        lines += ["", f"### From {link(m['from'], m['title'])} ({m['day']})"]
        lines.append(m["text"] or "(what you wrote there stays in that note)")
    return "\n".join(lines)


def alias(ig: Integrate, pid: str, rec: dict, index: cg.Index) -> str:
    """Both stay: b's names become aliases of a, and each links the other as equivalent-to (call with ig.lock)."""
    a, b = rec["a"], rec["b"]
    na, nb = index.notes[a], index.notes[b]
    ta, tb = na.path.read_text(encoding="utf-8"), nb.path.read_text(encoding="utf-8")
    reason = f"{na.title} and {nb.title} name the same concept"
    lay = layout.of(ig.app)
    ra, rb, style = lay.shown(na.path), lay.shown(nb.path), lay.note_style
    new_a, _ = gw.add_links(
        ig.add_alias(ta, nb.title, nb.aliases), [(b, gw.link_line("equivalent-to", b, reason, style, ra))], ra
    )
    new_b, _ = gw.add_links(tb, [(a, gw.link_line("equivalent-to", a, reason, style, rb))], rb)
    if not (gw.guarded(ta, new_a).ok and gw.guarded(tb, new_b).ok):
        return "Not done: it would have changed text of yours."
    journal: dict[str, list[str]] = {}
    _write(journal, na.path, ta, new_a)
    _write(journal, nb.path, tb, new_b)
    st = load(ig)
    rec.update(state="alias", at=now().isoformat(timespec="seconds"), journal=journal)
    st["pairs"][pid] = rec
    ig.save(FILE, st)
    ig.commit(list(journal), f"graph: {Path(b).name} is another name for {Path(a).name}")
    return f"{nb.title} is now an alias of {na.title}; both notes stay, linked as equivalent."


def undo(ig: Integrate, pid: str) -> str:
    """Undo a Merge, Keep both or Add alias (call with ig.lock held)."""
    st = load(ig)
    rec = st["pairs"].get(pid)
    if rec is None or rec.get("state") not in DONE:
        return "Nothing to undo there."
    kept: list[str] = []
    back: list[str] = []
    for path, (old, new) in (rec.get("journal") or {}).items():
        f = Path(path)
        try:
            cur = f.read_text(encoding="utf-8")
        except OSError:
            kept.append(f.name)
            continue
        if cur != new:
            kept.append(f.name)  # changed since: yours now
            continue
        write_note_file(f, old)
        back.append(path)
    if rec["state"] == "merge":
        for name in ("seen", "notation"):
            data = ig.load(f"{name}.json", {}) or {}
            for slug, rows in ((rec.get("before") or {}).get(name) or {}).items():
                if rows:
                    data[slug] = rows
                else:
                    data.pop(slug, None)
            ig.save(f"{name}.json", data)
        st.setdefault("merges", {})[rec["a"]] = [m for m in st.get("merges", {}).get(rec["a"], []) if m["pid"] != pid]
    was = rec["state"]
    rec.update(state="undone", journal={}, before={})
    ig.save(FILE, st)
    if back:
        ig.commit(back, f"graph: undid {was} of {Path(rec['b']).name}")
    said = {"merge": "Merge undone", "keep": "Undone: that pair can be asked about again", "alias": "Alias undone"}[was]
    if kept:
        said += f" (left as they are, changed since: {', '.join(kept)})"
    return said + "."
