"""/fixme (core/fixme.py): doctor's and health's failing checks matched by rules to the troubleshooting page and the
known-issues list, Fix buttons from health, free text matched by words, and the AI only explaining, after."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

import pytest

from kurooto import __version__
from kurooto.core import fixme
from kurooto.core.health import Result
from kurooto.modules.base import Incoming
from tests.unit.test_health import T, ev, on, use

ROOT = Path(__file__).resolve().parents[2]


def last_markup(env) -> str:
    return str([p for m, p in env.fake.sent if m == "sendMessage"][-1].get("reply_markup"))


def terminal(app, text: str) -> list[str]:
    out: list[str] = []
    app.handle(Incoming(text=text, via="terminal", respond=lambda t, buttons=None: out.append(t)))
    return out


def test_the_shipped_page_is_the_wikis():
    shipped = resources.files("kurooto.data").joinpath("troubleshooting.md").read_text(encoding="utf-8")
    wiki = (ROOT / "docs/wiki/user/troubleshooting.md").read_text(encoding="utf-8")
    assert shipped == wiki, "cp docs/wiki/user/troubleshooting.md src/kurooto/data/troubleshooting.md"


def test_rows_and_each_check_names_one_row():
    table = fixme.rows()
    assert len(table) > 100 and all(r.seen and r.do and r.section for r in table)
    assert "**" not in "".join(r.do for r in table) and "](" not in "".join(r.do for r in table)
    for cid, pieces in fixme.ROWS.items():
        for piece in pieces:
            assert len([r for r in table if piece.lower() in r.seen.lower()]) == 1, (cid, piece)


def test_free_text_by_words():
    table = fixme.rows()
    assert fixme.find("the phone doesn't ring", table)[0].seen == "The phone doesn't ring"
    assert fixme.find("my phone never rings", table)[0].seen == "The phone doesn't ring"
    assert fixme.find("dashboard won't open", table)[0].seen == "The dashboard won't open"
    assert fixme.find("bot not answering", table)[0].seen == "The bot doesn't answer"
    assert fixme.find("purple elephants", table) == [] and fixme.find("the and of", table) == []


def test_versions_and_known_issue_rules():
    assert fixme.affected("*") and fixme.affected("<0.5.11", "0.5.10") and not fixme.affected("<0.5.11", "0.5.11")
    assert fixme.affected(">=0.5.14,<0.5.16", "0.5.15") and not fixme.affected(">=0.5.14,<0.5.16", "0.5.16")
    assert fixme.affected("0.5.14", "0.5.14") and not fixme.affected("0.5.14", "0.5.15")
    assert not fixme.affected("soon", "0.5.14")
    i = {"checks": ["calls"], "symptom": "429", "keywords": ["phone ring"]}
    assert fixme.hits(i, {"calls"}, [], "")
    assert fixme.hits(i, set(), ["Phone calls: ntfy said 429 Too Many Requests"], "")
    assert fixme.hits(i, set(), [], "the phone won't ring")
    assert not fixme.hits(i, {"google"}, ["Google: signed out"], "the bot is slow")
    assert fixme.hits({"fix": "x"}, set(), [], "")  # no rule: about everyone on those versions


def test_shipped_known_issues_are_well_formed(monkeypatch):
    doc = json.loads(resources.files("kurooto.data").joinpath("known_issues.json").read_text(encoding="utf-8"))
    ids = [i["id"] for i in doc["issues"]]
    assert len(ids) == len(set(ids))
    for i in doc["issues"]:
        assert i["fix"] and str(i.get("action") or "update").startswith(("update", "fix:"))
        fixme.affected(i["versions"])
    assert "notes-map-empty" not in [i["id"] for i in fixme.issues(None)]  # fixed in 0.5.11
    monkeypatch.setattr(fixme, "__version__", "0.5.10")
    assert fixme.issues(None)[0]["id"] == "notes-map-empty"


@pytest.fixture
def broken(env):
    """A paired assistant whose Calendar stopped syncing (a health check with a Fix)."""
    app = env.app
    on(app, "calendar")
    h, clock = use(app, T(8))
    ev(app, T(8), "calendar_synced")
    h.evaluate()
    clock.t = T(23)
    return env


def test_fixme_on_telegram_matches_rules_with_fix_buttons(broken):
    env = broken
    out = env.say("/fixme")
    assert out.startswith("Not working now (1 thing), matched by rules:")
    assert "- Calendar: hasn't worked since" in out and "Fix (put its timers back): the button below" in out
    assert "If your calendar's link changed" in out and "troubleshooting.html" in out
    assert "health:calendar:fix" in last_markup(env) and "fixme:" not in last_markup(env)  # no AI picked
    assert env.press("health:calendar:fix") == "Calendar: its timers are back."
    assert "/fixme" in env.app.help() and "fixme" in [c["command"] for c in env.tg.menu()]


def test_fixme_with_words_and_in_a_terminal(broken):
    env = broken
    out = env.say("/fixme the phone doesn't ring")
    assert out.startswith('About "the phone doesn\'t ring", the troubleshooting page says:')
    assert "- The phone doesn't ring: Is every item on the app's checklist ticked?" in out
    assert "Also not working now (1 thing)" in out
    said = terminal(env.app, "/fixme")[0]
    assert "Fix (put its timers back): /fixme fix calendar" in said
    assert terminal(env.app, "/fixme fix calendar") == ["Calendar: its timers are back."]


def test_all_good_and_a_check_mapped_to_rows(env, monkeypatch):
    assert env.say("/fixme").startswith("Everything Kurooto checks is working. Say what you see:")
    bad = fixme.Problem(
        "calls",
        "Call line",
        "this computer isn't linked to your call line",
        "Set up redeploys it.",
        Result("calls", "Call line", False, "not linked", fix="reconnect"),
    )
    monkeypatch.setattr(fixme, "problems", lambda app, net: [bad])
    out = env.say("/fixme")
    assert 'Page, "Not connected to your call line", or' in out and "Try: Set up redeploys it." in out
    assert "health:calls:fix" in last_markup(env)


def test_doctor_rows_count_too(env, monkeypatch):
    from kurooto import diagnostics

    monkeypatch.setattr(
        diagnostics, "checks", lambda app, health=True, net=True: [("free space", False, "1.2 GB (keeps 5 GB)")]
    )
    out = env.say("/fixme")
    assert "- free space: 1.2 GB (keeps 5 GB)" in out and "Page, A low-disk warning: /space clean" in out


def test_known_issues_downloaded_and_withdrawn(env):
    app = env.app
    newer = "99.0.0"
    (app.paths.state / "update-ready.json").write_text(json.dumps({"version": newer}))
    f = app.paths.app / "versions" / newer / "src" / "src" / "kurooto" / "data" / "known_issues.json"
    f.parent.mkdir(parents=True)
    issue = {"id": "ring-x", "versions": "*", "keywords": ["phone ring"], "fix": "Pair the phone again."}
    f.write_text(json.dumps({"issues": [issue]}))
    out = env.say("/fixme my phone doesn't ring")
    assert f"Known issue in {__version__} (from {newer}'s list, downloaded): Pair the phone again." in out
    assert "ring-x" not in env.say("/fixme the dashboard won't open")
    (app.paths.state / "yank.json").write_text(json.dumps({"yanked": {__version__: "it breaks calls"}}))
    out = env.say("/fixme")
    assert f"{__version__} was withdrawn by its maintainer. it breaks calls. Update to a newer version." in out


def test_the_ai_only_explains_after(broken, monkeypatch):
    env = broken
    assert env.say("/fixme ai") == "Send /fixme first; your AI then explains what it found."
    env.say("/fixme")
    assert env.say("/fixme ai").startswith("Your AI doesn't look like it works right now (no AI is picked)")
    monkeypatch.setattr(fixme, "ai_works", lambda app: (True, ""))
    out = env.say("/fixme")
    assert "Not working now" in out and "Your AI can explain this: Ask my AI below." in out
    assert "fixme:last:ai" in last_markup(env)
    assert not env.app.jobs.recent(1)  # the rules' answer didn't wait for, or ask, the AI
    assert env.press("fixme:last:ai").startswith("Asked your AI")
    j = env.app.jobs.recent(1)[0]
    assert j.title == "Explain /fixme" and "Calendar: hasn't worked since" in j.prompt
    msg = Incoming(text="/fixme ai", via="terminal", respond=lambda t, buttons=None: None)
    env.app.handle(msg)
    assert msg.job == env.app.jobs.recent(1)[0].id  # the dashboard's terminal shows the answer when it comes


def test_kurooto_fixme_in_a_terminal(tmp_path, monkeypatch, capsys):
    from kurooto import cli

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    assert cli.main(["fixme", "the", "dashboard", "won't", "open"]) == 0
    out = capsys.readouterr().out
    assert "- The dashboard won't open: kurooto open" in out and "Ask my AI" not in out
