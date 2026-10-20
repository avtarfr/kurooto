"""Wrong button and test cases (modules/cases.py): the Wrong button and /wrong, requests that fell through kept as
cases, teaching a phrasing only when every passing test case still passes, never for send/delete/call/approve
requests, the monthly look back, Undo, 30-day retention, out of backups, `kurooto cases` and the pytest export. A fake
Telegram, a fake AI service and a fake clock; nothing leaves the test's folder."""

import datetime as dt
import importlib.util
import json

import pytest

from kurooto.app import App
from kurooto.modules import cases as cases_mod
from kurooto.modules.backups import sources
from kurooto.modules.base import Incoming, Intent, Module
from kurooto.modules.cases import Store, learnable, norm, route
from tests.fakes.openai import FakeOpenAI

T0 = dt.datetime(2026, 10, 4, 18, 30)  # a Sunday evening


class Clock:
    """The time the cases feature sees."""

    def __init__(self, monkeypatch, t=T0):
        self.t = t
        monkeypatch.setattr(cases_mod, "now", lambda: self.t)

    def add(self, **kw):
        self.t += dt.timedelta(**kw)


@pytest.fixture
def clock(monkeypatch):
    return Clock(monkeypatch)


@pytest.fixture
def ai(env):
    fake = FakeOpenAI()
    app = env.app
    app.secrets.set("custom.api_key", fake.key)
    app.settings.set("brain.base_urls", {"custom": fake.base})
    app.settings.set("brain.models", {"custom": {"low": "m", "medium": "m", "high": "m"}})
    app.settings.set("brain.main", "custom")
    app.settings.set("notify.desktop", False)
    fake.answer = "Here is what I think."
    yield fake
    fake.close()


@pytest.fixture
def on(env, ai, clock):
    """Telegram, Chat, Deadlines and Reminders on, then this feature."""
    env.on("chat", "deadlines", "reminders", "cases")
    return env


def sent(env):
    return [p for m, p in env.fake.sent if m == "sendMessage"]


def buttons(p):
    return [b["callback_data"] for row in (p.get("reply_markup") or {}).get("inline_keyboard", []) for b in row]


def wrong_of(p):
    return next(b for b in buttons(p) if b.startswith("wrong:"))


def store(app):
    return Store(app.paths.state).load()


def kept(app):
    """The texts of the cases on disk (none when nothing was ever kept)."""
    return [c["text"] for c in store(app)["cases"].values()]


def only_case(app):
    cs = list(store(app)["cases"].values())
    assert len(cs) == 1, cs
    return cs[0]


# --------------------------------------------------------------------------------------------- off by default
def test_off_by_default_nothing_kept_and_no_button(env, ai):
    env.on("chat", "deadlines")
    assert not env.app.is_on("cases")
    env.say("whats on my plate")
    assert buttons(sent(env)[-1]) == []
    assert not (env.app.paths.state / "cases").exists()


def test_needs_telegram_and_is_listed():
    from kurooto.modules.catalog import CATALOG
    from kurooto.web.api import MODULE_ORDER

    assert cases_mod.Cases in CATALOG and "cases" in MODULE_ORDER
    assert cases_mod.Cases.requires == ("telegram",)


# -------------------------------------------------------------------------------------------- Wrong button
def test_wrong_button_on_an_instant_reply_keeps_message_what_it_did_clock_and_settings(on):
    app = on.app
    app.settings.set("telegram.chat_id", 7)
    app.settings.set("deadlines.ping_h", 30)
    reply = on.say("what's due this week")
    assert reply == "Nothing due in that time."
    p = sent(on)[-1]
    ref = wrong_of(p)
    assert not store(app)["cases"]  # an instant request that worked isn't kept until you say so
    assert on.press(ref).startswith("Kept as a case")
    c = only_case(app)
    assert c["text"] == "what's due this week" and c["kind"] == "wrong" and c["wrong"] is True
    assert c["did"] == "show_due" and c["at"] == T0.isoformat() and c["said"] == "Nothing due in that time."
    snap = c["settings"]
    assert {"telegram", "chat", "deadlines", "reminders", "cases"} <= set(snap["modules"])
    assert snap["deadlines"] == {"ping_h": 30}
    assert "chat_id" not in json.dumps(snap) and "api_base" not in json.dumps(snap)  # chats and links stay out
    ev = app.events.tail(20, {"case_kept"})[-1]
    assert ev["did"] == "show_due" and "text" not in ev and "what's due" not in json.dumps(ev)
    assert on.press(ref).startswith("Kept as a case")  # a second tap changes nothing
    assert len(store(app)["cases"]) == 1


def test_a_request_the_ai_got_is_kept_and_its_answer_has_a_wrong_button_too(on):
    app = on.app
    assert on.say("whats on my plate") == "On it."
    ref = wrong_of(sent(on)[-1])
    c = only_case(app)
    assert c["kind"] == "fallthrough" and c["did"] == "ai" and not c["wrong"] and c["job"]
    assert app.jobs.run_next() is not None
    answer = sent(on)[-1]
    assert answer["text"].endswith("Here is what I think.") and wrong_of(answer) == ref
    assert on.press(ref).startswith("Kept as a case")
    c = only_case(app)
    assert c["kind"] == "wrong" and c["wrong"] and c["answer"] == "Here is what I think."


def test_long_sensitive_and_command_messages_are_not_kept(on):
    app = on.app
    on.say("what should I do about my bank loan, it's due soon")
    on.say("tell me " + "about eigenvalues " * 10)  # long: meant for the AI
    on.say("/help")
    assert kept(app) == []
    on.say("whats on my plate")
    assert kept(app) == ["whats on my plate"]


def test_fallthroughs_can_be_left_out_and_the_button_hidden(on):
    on.app.settings.set("cases.fallthroughs", False)
    on.app.settings.set("cases.button", False)
    on.say("whats on my plate")
    assert buttons(sent(on)[-1]) == []
    assert kept(on.app) == []
    assert "Kept" in on.say("/wrong")  # /wrong works without the button


def test_wrong_command_marks_the_last_reply(on):
    assert on.say("/wrong").startswith("Nothing to mark")
    on.say("what's due this week")
    out = on.say("/wrong")
    assert out.startswith('Kept "what\'s due this week" (it was taken as "what\'s due")')
    assert only_case(on.app)["wrong"]


def test_from_a_terminal_kept_without_a_button(on):
    said = []
    msg = Incoming(text="whats on my plate", via="terminal", respond=lambda t, buttons=None: said.append((t, buttons)))
    on.app.handle(msg)
    assert said == [("On it.", None)]
    assert only_case(on.app)["via"] == "terminal"


# ------------------------------------------------------------------------------------------------- teaching
def test_wrong_with_what_you_meant_teaches_the_phrasing(on):
    app = on.app
    on.say("whats on my plate?")
    out = on.say("/wrong what's due")
    assert out.startswith('Learned: "whats on my plate?" is now taken as "what\'s due"')
    assert buttons(sent(on)[-1]) == [f"case:{only_case(app)['id']}:unlearn"]
    c = only_case(app)
    assert c["status"] == "test" and c["expect"] == "show_due" and c["learned"]
    jobs = len(app.jobs.recent(50))
    assert on.say("Whats on my plate") == "Nothing due in that time."  # instant now, any case or punctuation
    assert len(app.jobs.recent(50)) == jobs
    assert app.events.tail(5, {"intent"})[-1]["via"] == "taught"
    assert len(store(app)["cases"]) == 1  # what's taught isn't kept again
    assert on.press(f"case:{c['id']}:unlearn").startswith("Unlearned")
    assert on.say("whats on my plate") == "On it."  # back to the AI; the test case stays
    assert store(app)["learned"] == [] and only_case(app)["status"] == "test"


def test_taught_requests_run_with_todays_time(on, monkeypatch):
    from kurooto.modules import text as text_mod

    on.say("stretch break")
    assert on.say("/wrong remind me in 20 min to stretch").startswith("Learned")
    later = dt.datetime.now().replace(microsecond=0) + dt.timedelta(hours=3)
    monkeypatch.setattr(text_mod, "now", lambda: later)  # said three hours after it was taught
    on.say("stretch break")
    jobs = on.app.scheduler.jobs("reminders:")
    assert len(jobs) == 1 and jobs[0].payload["what"] == "stretch"
    assert jobs[0].when == (later + dt.timedelta(minutes=20)).astimezone(dt.UTC)


def test_the_ai_and_unknown_words(on):
    app = on.app
    on.say("what's due this week")
    out = on.say("/wrong blorp the frobnicator")
    assert 'I don\'t understand "blorp the frobnicator" either' in out and only_case(app)["note"]
    assert only_case(app)["status"] == "new"
    out = on.say("/wrong the AI")
    assert out.startswith('Learned: "what\'s due this week" is now sent to the AI')
    assert on.say("what's due this week") == "On it."


def test_never_learned_send_delete_call_approve(on):
    app = on.app
    for name in ("call_me", "call_now"):
        it = next(i for i in app.modules["calls"].intents() if i.name == name)
        assert not learnable(it)
    assert not learnable(next(i for i in app.modules["telegram"].intents() if i.name == "hold_calls"))
    assert not learnable(app.modules["alarm"].intents()[0])
    assert not learnable(app.modules["quiz"].intents()[0])  # "quiz me ... by call"
    assert learnable(next(i for i in app.modules["deadlines"].intents() if i.name == "show_due"))
    assert learnable(app.modules["reminders"].intents()[0])
    assert learnable(next(i for i in app.modules["checkins"].intents() if i.name == "move_checkin"))  # "postpone"

    class Notes(Module):
        id = "fake_notes"
        title = "Fake notes"

        def intents(self):
            def match(t):
                return {} if t.lower().startswith("delete note") else None

            return [Intent("delete_note", "delete a note", match, lambda m, s: "deleted")]

    app.modules["fake_notes"] = Notes(app)
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "fake_notes"])
    on.say("bin the shopping list")
    out = on.say("/wrong delete note shopping")
    assert out.startswith('Saved as a test case: "bin the shopping list" should be taken as "delete a note"')
    assert "never learned" in out and store(app)["learned"] == []
    assert on.say("bin the shopping list") == "On it."  # still the AI, never the delete


def test_not_learned_when_it_would_break_a_passing_test_case(on):
    app = on.app
    on.say("whats on my plate")
    assert on.say("/wrong ai").startswith('Saved as a test case: "whats on my plate" already goes to the AI')
    on.say("whats on my plate!")
    out = on.say("/wrong what's due")
    assert out.startswith("Saved as a test case, but not learned: it would break 1 other test case")
    assert '"whats on my plate" (it should go to the AI)' in out
    assert store(app)["learned"] == []
    assert on.say("whats on my plate") == "On it."


def test_learning_off_keeps_the_test_case_only(on):
    on.app.settings.set("cases.learn", False)
    on.say("whats on my plate")
    assert "learning is off" in on.say("/wrong what's due")
    assert store(on.app)["learned"] == []


def test_suite_and_gate_rows(on):
    cases = on.app.modules["cases"]
    on.say("whats on my plate")
    on.say("/wrong what's due")
    on.say("what's due this week")
    on.say("/wrong ai")  # learned: this phrasing now goes to the AI
    r = cases.suite()
    assert sorted(x["expect"] for x in r["pass"]) == ["ai", "show_due"] and not r["fail"]
    on.app.disable("deadlines")
    r = cases.suite()
    assert [x["expect"] for x in r["skip"]] == ["show_due"]  # its feature is off: not run, not failed


# ------------------------------------------------------------------------------------------- the look back
def test_monthly_look_back_shows_common_phrasings_and_makes_a_test_case(on, clock):
    app, cases = on.app, on.app.modules["cases"]
    assert app.scheduler.get("cases:review").spec == "weekly sun 19:00"
    for _ in range(3):
        on.say("whats on my plate")
    on.say("am i free tonight")  # once, never tapped Wrong: not common enough to show
    on.say("what's due this week")
    on.press(wrong_of(sent(on)[-1]))
    assert cases.review() == 0  # not yet: about once a month
    clock.add(days=28)
    n = len(sent(on))
    assert cases.review() == 2
    p = sent(on)[n]
    assert p["text"].startswith("Look back") and [ln for ln in p["text"].splitlines() if ln[:1].isdigit()] == [
        '1. "what\'s due this week" (once; you tapped Wrong; it was taken as "what\'s due")',
        '2. "whats on my plate" (3 times; went to the AI)',
    ]
    assert [b.split(":")[2] for b in buttons(p)] == ["test", "test", "why", "less"]  # + Why? / Less of this
    assert app.events.tail(5, {"cases_review"})[-1]["shown"] == 2
    assert cases.review() == 0  # told once a month
    ref = buttons(p)[1]
    assert on.press(ref) == "Reply to my message with what you meant."
    ask = sent(on)[-1]
    assert ask["text"].startswith('Test case\n\nWhat should "whats on my plate" do?') and buttons(ask) == [
        f"case:{ref.split(':')[1]}:ai"
    ]
    out = on.reply_to_last("what's due")
    assert out.startswith('Learned: "whats on my plate" is now taken as "what\'s due"')
    assert [norm(t) for t in kept(app)].count("whats on my plate") == 1  # the test case stands for the others
    assert [g["phrase"] for g in cases.groups()] == ["whats due this week", "am i free tonight"]


def test_the_ai_button_and_cases_command(on):
    app, cases = on.app, on.app.modules["cases"]
    on.say("whats on my plate")
    on.say("whats on my plate")
    n = len(sent(on))
    on.say("/cases review")  # the look back now, whatever the date
    ref = buttons(sent(on)[n])[0]
    assert ref.endswith(":test")
    cid = ref.split(":")[1]
    on.press(ref)
    assert on.press(f"case:{cid}:ai").startswith('Saved as a test case: "whats on my plate" already goes to the AI')
    c = store(app)["cases"][cid]
    assert c["status"] == "test" and c["expect"] == "ai"
    out = on.say("/cases")
    assert out.startswith("Test cases: 1 (1 pass, 0 fail, 0 for features that are off). Waiting for review: 0")
    assert cases.groups() == []


# ------------------------------------------------------------------------------- retention, backups, health
def test_kept_30_days_unless_a_test_case(on, clock):
    app = on.app
    on.say("whats on my plate")
    on.say("what's due this week")
    on.say("/wrong ai")
    clock.add(days=31)
    on.say("am i free tonight")  # any change forgets what's old
    texts = sorted(c["text"] for c in store(app)["cases"].values())
    assert texts == ["am i free tonight", "what's due this week"]


def test_cases_stay_out_of_backups(on):
    on.say("whats on my plate")
    p = on.app.paths
    names = [n for n, _ in sources(p, None, notes=False, secrets=False, index=False)]
    assert names and not any(n.startswith("state/cases") for n in names)
    assert (p.state / "cases" / "cases.json").exists()


def test_health_check_says_when_a_taught_phrasing_stopped_working(on):
    app, cases = on.app, on.app.modules["cases"]
    assert cases.health_check().probe(False) == (True, "nothing taught yet")
    on.say("whats on my plate")
    on.say("/wrong what's due")
    assert cases.health_check().probe(False) == (True, "1 taught phrasings work")

    def break_it(d):
        d["learned"][0]["means"] = "what's on fire"  # its words no longer reach that request

    cases.store.change(break_it)
    ok, detail = cases.health_check().probe(False)
    assert ok is False and detail == "1 phrasing you taught no longer works"
    row = next(r for r in app.health.evaluate(save=False) if r.id == "cases")  # in the registry: doctor, /health
    assert row.ok is False and row.title == "Phrasings you taught" and "/cases" in row.line()
    assert on.say("whats on my plate") == "On it."  # a stale phrasing falls through, as before


# --------------------------------------------------------------------------- `kurooto cases` and the export
def load_export(path):
    spec = importlib.util.spec_from_file_location("exported_cases", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cli_lists_exports_and_forgets(on, tmp_path, monkeypatch, capsys):
    app = on.app
    on.say("whats on my plate")
    on.say("/wrong what's due")  # learned
    on.say("what's due this week")
    on.say("/wrong")  # wrong, not reviewed
    on.say("am i free tonight")  # fell through
    from kurooto.cli import main

    assert main(["cases"]) == 0
    out = capsys.readouterr().out
    assert "Test cases (1):" in out and "expect show_due (taught)" in out
    assert "Waiting for review (2: 1 wrong, 1 not understood):" in out
    assert "'whats on my plate' -> show_due (\"what's due\")" in out
    dest = tmp_path / "exported" / "test_kurooto_cases.py"
    dest.parent.mkdir()
    assert main(["cases", "export", "--all", "--out", str(dest)]) == 0
    assert "Wrote 3 cases" in capsys.readouterr().out
    mod = load_export(dest)
    by = {c["text"]: c for c in mod.CASES}
    assert set(by) == {"whats on my plate", "what's due this week", "am i free tonight"}
    assert "chat_id" not in dest.read_text() and by["whats on my plate"]["at"] == T0.isoformat()
    # replayed on a fresh Kurooto at the case's own time: the taught phrasing isn't there, so this one fails (a pattern
    # Kurooto could learn for everyone); unreviewed ones are skipped
    with pytest.MonkeyPatch.context() as mp:
        with pytest.raises(AssertionError):
            mod.test_case(by["whats on my plate"], tmp_path / "r1", mp)
        from kurooto.core import clock
        from kurooto.modules import text as text_mod

        assert clock.now() == T0 and text_mod.now() == T0  # every `now` read the case's clock
    with pytest.MonkeyPatch.context() as mp, pytest.raises(pytest.skip.Exception):
        mod.test_case(by["am i free tonight"], tmp_path / "r2", mp)
    ok = {**by["what's due this week"], "expect": "show_due"}
    with pytest.MonkeyPatch.context() as mp:
        mod.test_case(ok, tmp_path / "r3", mp)
    other = tmp_path / "exported" / "conftest.py"
    other.write_text("# mine\n")
    assert main(["cases", "export", "--out", str(other)]) == 1 and other.read_text() == "# mine\n"
    assert main(["cases", "export", "--out", str(dest)]) == 0  # an earlier export is written over
    capsys.readouterr()
    assert main(["cases", "check"]) == 0
    assert "1 pass, 0 fail" in capsys.readouterr().out
    cid = by["am i free tonight"]["id"]
    assert main(["cases", "forget", cid]) == 0 and cid not in store(app)["cases"]
    assert main(["cases", "forget", "all"]) == 0
    assert store(app)["cases"] == {} and store(app)["learned"] == []
    assert main(["cases", "export"]) == 1


def test_route_is_a_dry_run(on):
    app = on.app
    assert route(app, "/due") == "/due"
    assert route(app, "what's due this week") == "show_due"
    assert route(app, "sync everything") == "sync"
    assert route(app, "whats on my plate") == "ai"
    taught = [{"phrase": "whats on my plate", "intent": "show_due", "means": "what's due"}]
    assert route(app, "Whats on my plate?", taught) == "show_due"
    app.disable("chat")
    assert route(app, "whats on my plate") == "none"
    assert app.scheduler.jobs("reminders:") == [] and not app.jobs.recent(5)  # nothing was done


def test_a_fresh_install_has_no_cases_file(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    app = App()
    try:
        assert not app.is_on("cases") and not (app.paths.state / "cases").exists()
    finally:
        app.close()
