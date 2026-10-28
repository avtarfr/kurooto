"""The 0.9.0 links into phone calls, desk Live and the shared context builder (providers/context.py): what every AI
request is told reaches calls too, call lessons reach every lane, the senses line, read-only agent tools on calls, and
the rest. Each new behaviour has its own switch; these tests turn each off as well."""

# ruff: noqa: F811 (the fixtures imported from test_calls are taken as arguments)
from __future__ import annotations

from kurooto.core import notinterested
from kurooto.modules import remember
from kurooto.providers import context
from tests.unit.test_calls import calls  # noqa: F401 (a pytest fixture)


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
