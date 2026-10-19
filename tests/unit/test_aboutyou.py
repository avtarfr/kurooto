"""About you: the prompts for other AI accounts, the reports brought back, and the profile the AI builds from them."""

from __future__ import annotations

import stat
import sys

import pytest

from kurooto.core.aboutyou import prompt
from kurooto.providers.base import Result, Verdict
from kurooto.providers.context import headless_context

REPORT = "# Audit\n\n## A. Executive profile\n" + "Studies chemistry; plans experiments weekly. (Explicit)\n" * 10


def test_prompts_are_filled_in_for_the_account():
    main, other = prompt("main", "ChatGPT personal"), prompt("other", "Claude (work)")
    assert "{{" not in main + other
    assert "This is my main AI account (the one I use most): ChatGPT personal." in main
    assert "prefix CHATGPT_PERSONAL" in main and "prefix CLAUDE_WORK" in other
    assert "merged" in main and "multi-account audit" in other
    assert "passwords, API keys" in main and "passwords, API keys" in other
    assert "another of my AI accounts" in prompt("other")


def test_reports_are_kept_privately(env):
    about = env.app.about
    with pytest.raises(ValueError):
        about.add("ChatGPT", "too short")
    r = about.add("ChatGPT personal", REPORT)
    f = about.dir / f"{r['id']}.md"
    assert f.exists() and not str(f).startswith(str(env.app.workspace))  # not in the notes (never synced)
    if sys.platform != "win32":
        assert stat.S_IMODE(f.stat().st_mode) == 0o600
    assert [x["label"] for x in about.reports()] == ["ChatGPT personal"]
    assert about.remove(r["id"]) and about.reports() == []


def test_profile_is_built_kept_and_used(env):
    about = env.app.about
    with pytest.raises(ValueError, match="at least one"):
        about.merge()
    about.add("ChatGPT personal", REPORT)
    about.add("Gemini school", REPORT.replace("chemistry", "biology"))
    with pytest.raises(ValueError, match="Pick an AI"):
        about.merge()
    env.app.settings.set("brain.main", "gemini")
    jid = about.merge()
    job = env.app.jobs.get(jid)
    assert (
        job.quiet and "===== REPORT 2 =====" in job.prompt and "biology" in job.prompt and "## In brief" in job.prompt
    )
    profile = "## In brief (for the assistant)\nA chemistry student; wants short, direct answers.\n\n## Who I am\nx\n"
    about.save_profile(job, Result(Verdict.OK, text="Here you go:\n" + profile), {})
    text = about.profile_file.read_text()
    assert text.startswith("# About me") and "Here you go" not in text
    assert about.brief() == "A chemistry student; wants short, direct answers."
    ctx = headless_context(env.app)
    assert "A chemistry student; wants short, direct answers." in ctx and "about-me/profile.md" in ctx
    about.save_profile(job, Result(Verdict.OK, text=profile.replace("chemistry", "physics")), {})
    assert "physics" in about.brief() and len(list(about.profile_file.parent.glob("profile-*.md"))) == 1  # kept
    about.save_profile(job, Result(Verdict.ERROR, detail="rate limited"), {})
    assert "didn't work" in env.fake.texts()[-1] and "physics" in about.brief()  # a failure keeps the profile


def test_through_the_api(env):
    from kurooto.web.api import Api

    api = Api(env.app)
    got = api.get("aboutyou", {"source": "Copilot"})[1]
    assert "Copilot" in got["prompts"]["other"] and got["reports"] == [] and got["profile"]["exists"] is False
    r = api.post("aboutyou/add", {"label": "Copilot", "text": REPORT})[1]
    assert r["ok"] and len(r["reports"]) == 1
    assert api.post("aboutyou/add", {"label": "x", "text": ""})[1]["ok"] is False
    assert api.post("aboutyou/merge", {})[1]["error"].startswith("Pick an AI")
    env.app.settings.set("brain.main", "gemini")
    r = api.post("aboutyou/merge", {})[1]
    assert r["ok"] and r["profile"]["building"] is True
