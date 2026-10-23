"""Dreaming folds what it learned into your profile (modules/fold.py): lasting things you said, found by rules in your
chats, calls, requests and journal, offered in the morning message with Keep / Not that; nothing is written until a
tap, each line keeps where it came from, a Keep has an Undo, and never health, money or anyone else's words."""

import json
import time

from kurooto.core import aboutyou, layout
from kurooto.core.clock import now
from kurooto.core.state import jload, jsave
from kurooto.modules import fold, remember
from kurooto.providers.base import Result, Verdict


def keyboard(env) -> dict:
    sent = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
    markup = sent.get("reply_markup") or {}
    markup = json.loads(markup) if isinstance(markup, str) else markup
    return {b["text"]: b["callback_data"] for row in markup.get("inline_keyboard", []) for b in row}


def chat(app, *said):
    f = app.paths.state / "chat" / "history.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    turns = jload(f, []) or []
    turns += [{"user": s, "assistant": "ok", "at": time.time()} for s in said]
    jsave(f, turns)


def test_the_rules():
    k = fold.kind_of
    assert k("I'm a second-year geology student") == "about"
    assert k("btw my thesis is on sea ice under Prof Lena Ortiz") == "about"
    assert k("I work as a data analyst at a small firm") == "about"
    assert k("Please don't call me before 9") == "help"
    assert k("I prefer short answers in the morning") == "help"
    assert k("I'm most focused in the evenings") == "help"
    for no in (
        "I'm a bit tired today",  # only now
        "I'm a student, can you help with this?",  # a question
        "Maybe I'm a morning person",  # not sure
        "My friend is a data analyst at a bank",  # someone else
        "She said I work at the library",  # someone else's words
        "I'm a diabetic so remind me about insulin",  # health
        "I work at a bank and my salary is low",  # money
        "Fix the plot in figure 3",  # nothing about you
        "remember that I hate calls before 8",  # Remember keeps those at once
    ):
        assert k(no) == "", no


def test_nothing_is_written_until_keep_and_undo_takes_it_out(env):
    app = env.app
    env.on("dreaming")
    app.settings.set("dreaming.fold_ai", "off")
    chat(app, "I'm a second-year geology student. Can you check my essay?", "Please don't call me before 9")
    prof, helpf = app.about.profile_file, remember.help_file(app)
    text = app.modules["dreaming"].morning()
    assert "For your profile (what you said that seems to last; nothing is written until you tap Keep):" in text
    assert '"I\'m a second-year geology student" (a chat, ' in text and "→ your profile" in text
    assert '"Please don\'t call me before 9" (a chat, ' in text and "→ how to help you" in text
    assert not prof.exists() and not helpf.exists()  # never a silent write
    btn = {k: v for k, v in keyboard(env).items() if v.startswith("dfo:")}
    assert set(btn) == {"1: Keep", "1: Not that", "2: Keep", "2: Not that"}
    assert env.press(btn["1: Keep"]).startswith("Added to about-me/profile.md: I'm a second-year geology student")
    day = f"{now():%Y-%m-%d}"
    body = prof.read_text()
    assert f"- I'm a second-year geology student (from a chat, {day})" in body
    assert "<!-- kurooto:learned -->" in body and "<!-- /kurooto:learned -->" in body
    assert "I'm a second-year geology student" in app.about.brief()  # goes along with every request
    assert not app.about.edited()  # a profile only Kurooto wrote isn't yours yet: building one won't ask first
    assert env.press(keyboard(env)["Undo"]) == "Taken out of about-me/profile.md."
    assert "geology" not in prof.read_text()
    assert env.press(btn["2: Not that"]) == "Left out; I won't offer that one again."
    assert not helpf.exists()
    fold.scan(app)
    text, _ = fold.section(app, send=False)
    assert "geology" in text and "call me before 9" not in text  # the Undo offers it again; Not that never


def test_a_help_line_keeps_where_it_came_from_and_is_rechecked_like_the_others(env):
    app = env.app
    app.settings.set("dreaming.fold_ai", "off")
    d = app.paths.state / "calls" / "transcripts"
    d.mkdir(parents=True)
    (d / f"{now():%Y-%m-%d-%H%M%S}.txt").write_text(
        f"# check-in\n{app.name}: How was the day?\nYou: Fine. I prefer short answers on calls.\n"
        f"{app.name}: I prefer short answers too.\n"
    )
    assert fold.scan(app) == 1  # your line, not Kurooto's
    st = jload(fold.state_file(app), {})
    ref = st["items"][0]["ref"]
    assert fold.button(app, ref, "keep").startswith("Added to about-me/how-to-help-me.md")
    kept = remember.kept_lines(app)
    assert kept[0]["fact"] == "I prefer short answers on calls" and kept[0]["section"] == remember.LEARNED
    assert f"(from a call, {now():%Y-%m-%d})" in kept[0]["line"]
    assert fold.button(app, ref, "keep") == "That's settled already."
    fold.scan(app)
    assert fold.section(app, send=False) == ("", [])  # in the note now: not offered again


def test_journal_requests_and_what_is_known_already(env, monkeypatch):
    app = env.app
    app.settings.set("dreaming.fold_ai", "off")
    f = layout.path(app, "daily", date=f"{now():%Y-%m-%d}")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        "# Journal\n\n- I'm learning Portuguese for the exchange term\n"
        "<!-- kurooto:plan -->\n- I'm a robot line Kurooto wrote\n<!-- /kurooto:plan -->\n"
    )
    remember.keep(app, "I'm learning Portuguese for the exchange term")  # in the note already
    t = time.time()
    done = [
        ("j1", "x", "I work as a teaching assistant on Fridays. Draft a mail to the class.", "ok", t, "you", ""),
        ("j2", "x", "I work as a cook, says the background pass", "ok", t, "background", ""),
    ]
    monkeypatch.setattr(app.jobs, "finished_since", lambda lo, limit=500: [j for j in done if j[4] > lo])
    assert fold.scan(app) == 1
    items = jload(fold.state_file(app), {})["items"]
    assert [(i["src"], i["text"]) for i in items] == [("request", "I work as a teaching assistant on Fridays")]
    assert fold.scan(app) == 0  # new text only


def test_profile_edits_stay_and_rebuilding_carries_the_block(env):
    app = env.app
    prof = app.about.profile_file
    prof.parent.mkdir(parents=True, exist_ok=True)
    mine = "# About me\n\n## In brief (for the assistant)\nA student of rivers.\n\n## Who I am\nSee above.\n"
    prof.write_text(mine)
    assert app.about.add_learned("I'm a second-year geology student (from a chat, 2026-10-23)")
    text = prof.read_text()
    assert aboutyou.LEARNED_BLOCK.sub("", text).replace("\n", "") == mine.replace("\n", "")  # yours, untouched
    assert text.index("<!-- kurooto:learned") < text.index("## Who I am")  # inside the In-brief part
    assert app.about.brief().startswith("A student of rivers.") and "geology" in app.about.brief()
    assert not app.about.add_learned("I'm a second-year geology student (from a call, 2026-10-24)")  # once
    # a profile built again by the AI keeps the lines you kept
    app.settings.set("brain.main", "gemini")

    class R:
        ok, text, detail, usage = True, "## In brief (for the assistant)\nRivers and rocks.\n", "", {}

    app.about.save_profile(None, R(), {"base": aboutyou._outside(prof.read_text())})
    new = prof.read_text()
    assert "Rivers and rocks." in new and "- I'm a second-year geology student (from a chat, 2026-10-23)" in new
    assert app.about.remove_learned("I'm a second-year geology student (from a chat, 2026-10-23)")
    assert "geology" not in prof.read_text() and not app.about.remove_learned("anything")


def test_a_second_look_only_when_allowed_and_off_switch(env, monkeypatch):
    from kurooto.modules import consolidate

    app = env.app
    asked = []

    class Brain:
        def complete(self, prompt, **kw):
            asked.append(prompt)
            return Result(Verdict.OK, "SKIP")

    monkeypatch.setattr(consolidate, "_brain", lambda app, how: Brain())
    chat(app, "I'm a fan of long walks")
    app.settings.set("dreaming.fold_ai", "local")
    assert fold.scan(app) == 0 and len(asked) == 1 and "long walks" in asked[0]
    app.settings.set("dreaming.fold", False)
    chat(app, "I'm a night owl at heart")
    assert fold.scan(app) == 0 and fold.section(app, send=False) == ("", [])
    assert fold.show(app).startswith("Folding what I learn into your profile is off")
