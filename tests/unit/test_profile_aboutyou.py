"""About you: the profile is editable from the setup page (through the API), building it again never
silently replaces your edits, and /aboutme shows the In-brief part."""

from __future__ import annotations

import json

from kurooto.core.aboutyou import MAX_PROFILE, brief_of
from kurooto.providers.base import Result, Verdict
from kurooto.providers.context import headless_context
from kurooto.web.api import Api

REPORT = "# Audit\n\n## A. Executive profile\n" + "Studies chemistry; plans experiments weekly. (Explicit)\n" * 10
BUILT = "## In brief (for the assistant)\nA chemistry student; wants short, direct answers.\n\n## Who I am\nSam.\n"


def built(env, text: str = BUILT) -> None:
    """A profile as "Build my profile" leaves it."""
    about = env.app.about
    if not about.reports():
        about.add("ChatGPT personal", REPORT)
    env.app.settings.set("brain.main", "gemini")
    jid = about.merge(replace=True)
    about.save_profile(env.app.jobs.get(jid), Result(Verdict.OK, text=text), payload_of(env, jid))


def payload_of(env, jid: str) -> dict:
    row = env.app.jobs._db.execute("select then_payload from jobs where id=?", (jid,)).fetchone()
    return json.loads(row[0] or "{}")


def kept(env) -> list:
    return sorted(env.app.about.profile_file.parent.glob("profile-*.md"))


def test_the_profile_is_edited_through_the_api(env):
    api, about = Api(env.app), env.app.about
    assert api.get("aboutyou/profile")[1]["exists"] is False
    built(env)
    v = api.get("aboutyou/profile")[1]
    assert (
        v["exists"] and "## Who I am" in v["text"] and v["brief"] == "A chemistry student; wants short, direct answers."
    )
    assert v["edited"] is False and v["warning"] == ""

    # the preview is exactly what goes along with requests, worked out the same way
    edited = v["text"].replace("short, direct answers", "worked examples first")
    p = api.post("aboutyou/preview", {"text": edited})[1]
    assert p["brief"] == brief_of(edited) == "A chemistry student; wants worked examples first."
    assert 'no "## In brief"' in api.post("aboutyou/preview", {"text": "# About me\n\nnothing"})[1]["warning"]

    # empty and absurdly long texts are refused; nothing changes
    assert api.post("aboutyou/profile", {"text": "  \n "})[1]["ok"] is False
    assert "characters" in api.post("aboutyou/profile", {"text": "x" * (MAX_PROFILE + 1)})[1]["error"]
    assert api.post("aboutyou/profile", {})[0] == 400
    assert kept(env) == [] and about.brief() == "A chemistry student; wants short, direct answers."

    # a save keeps the previous version beside it, and the next AI request carries the edit
    r = api.post("aboutyou/profile", {"text": edited})[1]
    assert r["ok"] and r["changed"] and r["brief"].endswith("worked examples first.") and r["edited"] is True
    assert len(kept(env)) == 1 and "short, direct answers" in kept(env)[0].read_text()
    assert "worked examples first" in headless_context(env.app)
    assert api.post("aboutyou/profile", {"text": edited})[1]["changed"] is False and len(kept(env)) == 1

    # no In-brief part: saved, with a warning (then nothing goes along with requests)
    r = api.post("aboutyou/profile", {"text": "# About me\n\nJust notes for myself.\n"})[1]
    assert r["ok"] and "nothing from your profile goes along" in r["warning"] and r["brief"] == ""
    assert "Who they are" not in headless_context(env.app)


def test_building_again_asks_before_replacing_your_edits(env):
    api, about = Api(env.app), env.app.about
    built(env)
    assert api.post("aboutyou/merge", {})[1]["ok"]  # not edited: no question
    api.post("aboutyou/profile", {"text": about.text().replace("Sam.", "Sam, a night owl.")})
    r = api.post("aboutyou/merge", {})[1]
    assert r["ok"] is False and r["edited"] is True and "Build it again anyway?" in r["error"]
    r = api.post("aboutyou/merge", {"replace": True})[1]  # they said yes
    assert r["ok"]
    jid = [j for j in env.app.jobs.recent(5) if j.title == "Building your profile"][0].id
    about.save_profile(env.app.jobs.get(jid), Result(Verdict.OK, text=BUILT), payload_of(env, jid))
    assert "night owl" not in about.text() and about.edited() is False
    assert any("night owl" in f.read_text() for f in kept(env))  # their version is kept beside it


def test_edits_made_while_building_stay(env):
    about = env.app.about
    built(env)
    jid = about.merge()
    about.save_text(about.text().replace("Sam.", "Sam, edited while it was building."))
    about.save_profile(
        env.app.jobs.get(jid), Result(Verdict.OK, text=BUILT.replace("chemistry", "physics")), payload_of(env, jid)
    )
    assert "edited while it was building" in about.text() and "chemistry" in about.brief()
    new = list(about.profile_file.parent.glob("profile-new-*.md"))
    assert len(new) == 1 and "physics" in new[0].read_text()
    assert "yours stays as it is" in env.fake.texts()[-1]


def test_a_profile_kurooto_did_not_build_counts_as_yours(env):
    about = env.app.about
    about.profile_file.parent.mkdir(parents=True)
    about.profile_file.write_text("## In brief\nWritten by hand.\n", encoding="utf-8")
    about.add("ChatGPT personal", REPORT)
    env.app.settings.set("brain.main", "gemini")
    assert about.edited() is True
    r = Api(env.app).post("aboutyou/merge", {})[1]
    assert r["edited"] is True


def test_aboutme_on_telegram(env):
    assert "No profile yet" in env.say("/aboutme")
    built(env)
    out = env.say("/aboutme")
    assert "A chemistry student; wants short, direct answers." in out and "setup#about" in out
    assert "/aboutme" in env.say("/help")


def test_the_editor_is_on_both_pages():
    from kurooto.web.server import static

    assert b"function aboutEditor" in static("aboutme.js")
    assert b"/static/aboutme.js" in static("setup.html")
    assert b'"aboutyou/preview"' in static("aboutme.js") and b'location.hash === "#about"' in static("setup.js")
