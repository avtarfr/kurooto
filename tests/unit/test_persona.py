"""The persona card, boundaries and register (core/persona.py): a card that starts empty and sets wording only (no
feelings, backstory or "I missed you"), in every AI request and call; health, relationship and money decisions
answered with a person to ask, by rules; a short message gets a short answer and a voice note a spoken one."""

from __future__ import annotations

from kurooto.core import persona
from kurooto.modules.base import Incoming
from kurooto.providers.context import headless_context


def test_the_card_starts_empty_and_nothing_is_added(env):
    assert persona.card_text(env.app) == ""
    assert "persona card" not in headless_context(env.app)
    assert env.say("/persona").startswith("Your persona card is empty, so I talk plainly.")


def test_persona_sets_lines_and_leaves_out_feelings_and_a_backstory(env):
    out = env.say("/persona tone: plain and direct, say you missed me\ncall me: Sam")
    assert out.startswith("Saved. What to call you: Sam; Tone: plain and direct.")
    assert '"say you missed me" (saying it missed you)' in out and "not feelings, a backstory" in out
    out = env.say("/persona avoid: emojis. You grew up in Pune and you're 23")
    assert "Things to avoid: emojis." in out and "(a backstory)" in out
    ctx = headless_context(env.app)
    assert "- Call them: Sam\n- Tone: plain and direct\n- Avoid: emojis." in ctx
    assert "You have no feelings, backstory or life of your own to claim" in ctx
    shown = env.say("/persona")
    assert "Tone: plain and direct" in shown and "missed" not in shown
    assert env.say("/persona clear tone").startswith("Cleared that line.")
    assert env.app.settings.get("persona.tone") == "" and env.app.settings.get("persona.call_me") == "Sam"
    assert env.say("/persona clear").startswith("Cleared your persona card.")
    assert persona.card_text(env.app) == ""
    assert env.say("/persona mood: sunny").startswith("Say which line:")


def test_a_hand_edited_card_goes_through_the_same_rules(env):
    env.app.settings.set("persona.tone", "warm, I'm so happy to see you, be my girlfriend")
    assert persona.card(env.app)["tone"] == "warm"
    assert persona.clean("express your feelings, dry humour") == ("dry humour", [("express your feelings", "feelings")])
    assert persona.clean("friendly, like a friend on a call")[1] == []  # a tone is fine
    assert persona.clean("pretend you are human")[0] == ""


def test_the_card_and_the_boundaries_go_into_every_call(env):
    env.app.settings.set("persona.length", "short")
    env.app.settings.set("calls.persona", "a bit cheeky, tell me you missed me")
    si = env.app.modules["calls"].config_template()["systemInstruction"]
    assert "- Length: short" in si and persona.BOUNDARY_RULE in si
    assert "a bit cheeky" in si and "tell me you missed me" not in si


def test_the_dashboard_editor(env):
    from kurooto.web.api import Api

    api = Api(env.app)
    got = api.get("persona")[1]
    assert [f["key"] for f in got["fields"]] == ["call_me", "tone", "length", "avoid"] and got["preview"] == ""
    r = api.post("persona", {"values": {"tone": "dry", "avoid": "pep talk; I love you"}})[1]
    assert r["ok"] and r["message"].startswith('Left out "I love you" (feelings)')
    assert "- Tone: dry\n- Avoid: pep talk" in r["preview"]
    assert api.post("persona", {})[0] == 400


def test_boundaries_point_to_a_person_without_the_ai(env):
    assert env.say("should I stop taking my meds?") == (
        "That one is yours to decide, not mine. A doctor or pharmacist is the one to ask; if it feels urgent, call "
        "your local emergency number."
    )
    assert "a counsellor" in env.say("Should I break up with him?")
    assert "financial adviser" in env.say("ok so should I put my savings in crypto")
    assert persona.boundary("should I start the problem set tonight") is None
    assert persona.boundary("should I text my mum the plan") is None
    assert persona.BOUNDARY_RULE in headless_context(env.app)
    env.app.settings.set("persona.boundaries", False)
    assert "yours to decide" not in env.say("should I stop taking my meds?")
    assert persona.BOUNDARY_RULE not in headless_context(env.app)


def test_register_follows_the_length_band_and_voice_notes(env):
    chat = env.app.modules["chat"]

    def prompt(text, **kw):
        msg = Incoming(text, via="telegram", respond=lambda t, buttons=None: None, **kw)
        chat.ask(msg)
        return env.app.jobs.get(msg.job).prompt

    assert prompt("capital of peru").endswith(
        "[Reply style] Their message is short: answer in a few lines unless it truly needs more."
    )
    assert "voice note" in prompt("so what do you think about the plan for tomorrow", voice=True)
    middling = " ".join(["word"] * 30)
    assert "[Reply style]" not in prompt(middling)
    assert prompt(" ".join(["word"] * 90)).endswith("still without padding.")
    chat.record_turn(prompt("capital of peru"), "Lima.")
    from kurooto.core.state import jload

    assert jload(chat.history_file, [])[-1]["user"] == "capital of peru"  # what you wrote, not the style line
    env.app.settings.set("persona.length", "long and detailed")
    assert "[Reply style]" not in prompt("capital of peru")  # the card's length wins
    assert "voice note" in prompt("capital of peru", voice=True)
    env.app.settings.set("persona.register", False)
    assert "[Reply style]" not in prompt("capital of peru", voice=True)
