"""What you know (stage 14, part 1): your estimated mastery of each concept in your notes, in [0, 1].

A simple Bayesian knowledge-tracing model per concept: p(learned), with slip and guess. Evidence, from weak to strong:
having asked about it (a small step toward "not yet"), having written about it in your notes (a small step the other
way),
and quiz results on cards that mention it (graded 3 to 5 is a right answer, below 3 a wrong one). The estimate pitches
explanations: new to you, the prerequisites are defined first; solid, they're skipped. Quizzes and study packs aim at
the
frontier: concepts you haven't mastered whose neighbours you have.

    update(p, correct, weight)   one observation
    observe(app, slug, ...)      keep it as a row (source inferred, evidence ids)
    from_quiz / from_notes       the evidence that already exists
    level(p)                     new, some or solid
    hint(app, text)              the line an AI request gets about concepts it names
    frontier(app, n)             where to study next
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from kurooto.core import conceptgraph
from kurooto.mind.tom import model

if TYPE_CHECKING:
    from kurooto.app import App

P_INIT, P_TRANSIT, P_SLIP, P_GUESS = 0.30, 0.15, 0.10, 0.20
NEW_BELOW, SOLID_FROM = 0.35, 0.70
PART = "knowledge"
LINKS = "_links"  # the quiz file the link recall cards live in (modules/quiz_links.py SUBJECT)


def update(p: float, correct: bool, weight: float = 1.0) -> float:
    """BKT: the posterior of 'learned' after one answer (weighted: a weak sign moves it less), then the chance it was
    learned in between."""
    if correct:
        post = p * (1 - P_SLIP) / (p * (1 - P_SLIP) + (1 - p) * P_GUESS)
    else:
        post = p * P_SLIP / (p * P_SLIP + (1 - p) * (1 - P_GUESS))
    post = p + (post - p) * max(0.0, min(1.0, weight))
    return round(post + (1 - post) * P_TRANSIT * max(0.0, min(1.0, weight)), 4)


def level(p: float) -> str:
    return "new" if p < NEW_BELOW else "solid" if p >= SOLID_FROM else "some"


def row(app: App, slug: str) -> dict | None:
    return next((r for r in model.rows(app, PART) if r["subject"] == slug), None)


def mastery(app: App, slug: str) -> float:
    r = row(app, slug)
    return float(r["p"]) if r and "p" in r else P_INIT


def observe(app: App, slug: str, correct: bool, weight: float = 1.0, evidence: str = "", n: int = 1) -> float | None:
    """Fold in one (or n) observation(s) of this concept; None when the model is off or the topic is not allowed."""
    r = row(app, slug)
    p = float(r["p"]) if r and "p" in r else P_INIT
    for _ in range(max(1, n)):
        p = update(p, correct, weight)
    seen = (
        sorted({*(r.get("evidence") or []), *([evidence] if evidence else [])})[-6:]
        if r
        else ([evidence] if evidence else [])
    )
    got = model.put(
        app, PART, slug, f"mastery {level(p)}", "inferred", min(0.95, 0.4 + 0.1 * len(seen)), seen, by_subject=True, p=p
    )
    return p if got else None


def concepts(app: App) -> dict[str, conceptgraph.Note]:
    try:
        return {s: n for s, n in conceptgraph.scan(app).items() if conceptgraph.concept_like(n) and not n.redirect}
    except Exception:
        return {}


def mentions(text: str, notes: dict[str, conceptgraph.Note]) -> list[str]:
    """Slugs of the concepts whose name (or alias) appears in `text` as whole words."""
    t = f" {model.norm(text)} "
    out = []
    for slug, n in notes.items():
        for name in n.names:
            nm = model.norm(name)
            if len(nm) >= 4 and f" {nm} " in t:
                out.append(slug)
                break
    return out


def item_slugs(it: dict, notes: dict[str, conceptgraph.Note]) -> list[str]:
    """The concepts a quiz item is about: the concept a card Kurooto wrote names (Quiz.add_card), or both ends of a link
    recall card (modules/quiz_links.py), when those notes still exist; else the concepts its text names."""
    named = [s for s in (it.get("concept"), it.get("a"), it.get("b")) if isinstance(s, str) and s in notes]
    return list(dict.fromkeys(named)) or mentions(it.get("text", ""), notes)


def from_quiz(app: App) -> int:
    """Quiz results -> evidence, for cards that name a concept; each graded answer is counted once."""
    quiz = app.modules.get("quiz")
    if quiz is None or not app.is_on("quiz"):
        return 0
    notes, done = concepts(app), 0
    seen = model._state(app).get("quiz_seen") or {}  # noqa: SLF001
    cards = getattr(quiz, "card_subjects", list)()  # 0.8.14: the cards Kurooto wrote count as evidence too
    links = [LINKS] if (quiz._dir() / f"{LINKS}.json").exists() else []  # noqa: SLF001  the link recall cards (0.9.0)
    for subj in list(dict.fromkeys([*quiz.sources(), *cards, *links])):
        for iid, it in quiz.state(subj)["items"].items():
            hist = it.get("history") or []
            k = f"{subj}:{iid}"
            for g in hist[int(seen.get(k, 0)) :]:
                for slug in item_slugs(it, notes):
                    observe(app, slug, int(g.get("q", 0)) >= 3, 1.0, f"quiz:{iid}")
                    done += 1
            seen[k] = len(hist)
    st = model._state(app)  # noqa: SLF001
    st["quiz_seen"] = seen
    model._save(app, st)  # noqa: SLF001
    return done


def from_notes(app: App) -> int:
    """He wrote about a concept (its note changed since last time): a small step toward 'learned', once per version."""
    notes, st, done = concepts(app), model._state(app), 0  # noqa: SLF001
    seen = st.get("notes_seen") or {}
    for slug, n in notes.items():
        if seen.get(slug) != n.hash:
            if slug in seen:  # a change, not the first sight of the folder
                observe(app, slug, True, 0.15, f"note:{slug}")
                done += 1
            seen[slug] = n.hash
    st["notes_seen"] = seen
    model._save(app, st)  # noqa: SLF001
    return done


def asked(app: App, text: str) -> int:
    """He asked a question that names a concept: weak evidence of a gap."""
    n = 0
    for slug in mentions(text, concepts(app)):
        observe(app, slug, False, 0.2, f"asked:{int(time.time())}")
        n += 1
    return n


def hint(app: App, text: str) -> str:
    """A line for an AI request: how to pitch the concepts it names. "" when none is named, or the model is off."""
    if not model.on(app) or not text:
        return ""
    notes = concepts(app)
    lines = []
    for slug in mentions(text, notes)[:5]:
        lv = level(mastery(app, slug))
        title = notes[slug].title
        how = {
            "new": "new to them: define it and its prerequisites first",
            "solid": "solid: skip the basics",
            "some": "partly known: a short reminder, then on",
        }[lv]
        lines.append(f"{title}: {how}")
    if not lines:
        model.guard("level")
        return ""
    model.guard("level")
    return (
        "How well they know what this names (pitch it there; this is an estimate, not a fact): "
        + "; ".join(lines)
        + "."
    )


def frontier(app: App, n: int = 10) -> list[str]:
    """Concepts not yet mastered whose neighbours (the notes they link to, or their typed prerequisites) are."""
    notes, out = concepts(app), []
    for slug, nt in notes.items():
        if mastery(app, slug) >= SOLID_FROM:
            continue
        pre = [t for t, rel in nt.typed.items() if "prereq" in rel.lower()] or sorted(nt.links)
        pre = [p for p in pre if p in notes]
        if pre and all(mastery(app, p) >= SOLID_FROM for p in pre):
            out.append(slug)
    return out[:n]
