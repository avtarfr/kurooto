"""The 0.9.0 links into phone calls, desk Live and the shared context builder (providers/context.py): what every AI
request is told reaches calls too, call lessons reach every lane, the senses line, read-only agent tools on calls, and
the rest. Each new behaviour has its own switch; these tests turn each off as well."""

# ruff: noqa: F811 (the fixtures imported from test_calls are taken as arguments)
from __future__ import annotations

from kurooto.core import notinterested
from kurooto.modules import remember
from kurooto.providers import context
from tests.unit.test_calls import calls  # noqa: F401 (a pytest fixture)
from tests.unit.test_learning import ai, app, propose, retro_questions  # noqa: F401 (pytest fixtures, helpers)


def profile(app, text="A maths student who likes long walks."):
    f = app.workspace / "about-me" / "profile.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"# Profile\n\n## In brief\n\n{text}\n", encoding="utf-8")


# ------------------------------------------------------------------------- L1, L5: what calls are told about you
def test_a_call_hears_who_they_are_how_to_help_and_the_not_interested_topics(calls):
    app = calls.app
    c = app.modules["calls"]
    profile(app)
    remember.keep(app, "Keep answers short")
    notinterested.add_topic(app, "drama club")
    brief = c.pending(context=True)
    about = brief["about_them"]
    assert "likes long walks" in about and "Keep answers short" in about and "drama club" in about
    assert "about_them" not in c.pending()  # the look back and turn-by-turn calls have headless_context already
    tool = next(t for t in c.tools() if t.name == "pending_items")
    assert "about_them" in tool.run({})  # the call's own tool, and so the brief the call line keeps offline
    app.settings.set("calls.context_brief", False)
    assert "about_them" not in c.pending(context=True)


def test_the_call_brief_never_carries_the_read_hint_and_skips_learned_on_calls(calls, monkeypatch):
    from kurooto import mind
    from kurooto.mind import feelings

    app = calls.app
    monkeypatch.setattr(mind, "part_on", lambda a, part: part == "feelings")
    monkeypatch.setattr(feelings, "hint", lambda a: "Keep it short and calm; they have a lot on.")
    monkeypatch.setattr(feelings, "state", lambda a: {})
    remember.add_line(app, remember.LEARNED_CALLS, "Ask when class ends before setting a reminder (2026-10-01)")
    about = context.call_context(app)
    assert feelings.RULE in about and "they have a lot on" not in about
    assert "Ask when class ends" not in about  # the call hears it as one of its lessons instead
    assert "they have a lot on" in context.headless_context(app)  # every other request as before
    assert "Ask when class ends" in context.headless_context(app)


def test_tell_ai_adds_one_line_to_every_request_and_off_leaves_it_as_it_was(env):
    app = env.app
    before = context.headless_context(app)
    notinterested.add_topic(app, "drama club")
    notinterested.add_topic(app, "chess society", "not this term")
    line = context.not_interested_part(app)
    assert "drama club; chess society" in line and "not this term" not in line
    assert line in context.headless_context(app)
    app.settings.set("notinterested.tell_ai", False)
    assert context.not_interested_part(app) == ""
    assert context.headless_context(app).replace(before.split("\n")[1], "") == before.replace(
        before.split("\n")[1], ""
    )  # the same text (the time line aside)


def test_desk_live_hears_it_in_its_setup(calls):
    app = calls.app
    c = app.modules["calls"]
    profile(app)
    from kurooto.modules.voice.live import Live

    lv = Live(app.modules["voice"])
    si = lv.setup(c, "m")["systemInstruction"]["parts"][0]["text"]
    assert "likes long walks" in si
    app.settings.set("calls.context_brief", False)
    assert "likes long walks" not in lv.setup(c, "m")["systemInstruction"]["parts"][0]["text"]


# ------------------------------------------------------------------------------- L5: the readers, each its own switch
def test_demote_moves_matching_items_last_and_tags_them_only_with_its_switch_on(env):
    app = env.app
    notinterested.add_topic(app, "drama club")
    items = ["Drama club auditions", "Linear algebra notes", "Probability sheet"]
    assert notinterested.demote(app, "research", items, str, lambda x, why: f"{x} ({why})") == items  # off
    app.settings.set("notinterested.filter.research", True)
    out = notinterested.demote(app, "research", items, str, lambda x, why: f"{x} ({why})")
    assert out[:2] == ["Linear algebra notes", "Probability sheet"]
    assert out[2] == "Drama club auditions (you said not interested in drama club)"
    assert notinterested.demote(app, "retro", items, str) == items  # every reader has its own switch


def test_research_digest_puts_a_skipped_topic_last_never_drops_it(env, monkeypatch):
    app = env.app
    notinterested.add_topic(app, "drama club")
    r = app.modules["research"]
    papers = [
        {"id": "1", "title": "Drama club as social network", "authors": ["A. Writer"], "source": "arXiv", "summary": "",
         "link": "https://example.com/1", "group": "g"},
        {"id": "2", "title": "Spectral gaps", "authors": ["B. Writer"], "source": "arXiv", "summary": "",
         "link": "https://example.com/2", "group": "g"},
    ]  # fmt: skip
    monkeypatch.setattr(r, "collect", lambda mark_seen=True: ([dict(p) for p in papers], []))
    app.settings.set("research.rank", False)
    app.settings.set("research.save_note", False)
    r.papers()
    text = env.fake.texts()[-1]
    assert text.index("Drama club") < text.index("Spectral gaps")  # as before, off
    app.settings.set("notinterested.filter.research", True)
    r.papers()
    text = env.fake.texts()[-1]
    assert text.index("Spectral gaps") < text.index("Drama club") and "(you said not interested in drama club)" in text


def test_retro_offers_an_idea_about_a_skipped_topic_last_and_tagged(app, env, ai):
    env.on("chat", "retro")
    notinterested.add_topic(app, "drama club")
    app.settings.set("notinterested.filter.retro", True)
    app.settings.set("retro.max_proposals", 5)
    propose(
        ai,
        {"type": "idea", "idea": "Remind me of drama club rehearsals", "text": "Add to ideas?"},
        {"type": "idea", "idea": "A Sunday reading list", "text": "Add this one?"},
    )
    assert app.modules["retro"].run() == 2
    qs = retro_questions(app)
    assert "Sunday reading list" in qs[0]["text"]
    assert "drama club rehearsals" in qs[1]["text"] and "(you said not interested in drama club)" in qs[1]["text"]


def test_link_cards_about_a_skipped_topic_come_after_the_others(env):
    import datetime as dt

    app = env.app
    notinterested.add_topic(app, "drama club")
    lc = app.modules["quiz"].links
    today = dt.date.today().isoformat()
    card = {"reps": 0, "history": [], "due": today}
    st = {
        "items": {
            "a": {**card, "text": "How does drama club relate to stage fright?", "a": "x/drama-club", "b": "x/fear"},
            "b": {**card, "text": "How is the rank used in the kernel?", "a": "x/rank", "b": "x/kernel"},
        }
    }
    assert lc.next_card(st)[0] == "a"
    app.settings.set("notinterested.filter.quiz_links", True)
    iid, it = lc.next_card(st)
    assert iid == "b"
    st["items"].pop("b")
    iid, it = lc.next_card(st)
    assert iid == "a" and it["not_interested"] == "you said not interested in drama club"
    assert "not_interested" not in st["items"]["a"]  # the stored card is left as it was


def test_the_reading_queue_reads_a_skipped_topic_last(env):
    app = env.app
    notinterested.add_topic(app, "drama club")
    ig = app.modules["integrate"]
    items = {
        "c:1": {"source": "classroom", "key": "c:1", "title": "Drama club handout", "date": "2026-10-02", "added": "2"},
        "c:2": {"source": "classroom", "key": "c:2", "title": "Lecture 4", "date": "2026-10-01", "added": "1"},
    }
    ig.items = lambda: items
    ig.sources = lambda: ["classroom"]
    assert [it["key"] for it in ig.queued_items()] == ["c:1", "c:2"]
    app.settings.set("notinterested.filter.integrate", True)
    assert [it["key"] for it in ig.queued_items()] == ["c:2", "c:1"]

