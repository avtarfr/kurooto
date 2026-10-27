"""Never without a tap (core/tap.py): every AI tool and every plain-English request is run with the guarded actions
watched (an alarm set, a call placed, a new mail sender read, something sent out, a repository attached, your data
deleted). One that reaches a guarded action must carry that tag, and the tag must name a way core/tap.py's table allows;
an unattended AI run never reaches one: it gets an Approve / Deny, and only Approve does it."""

import pytest

from kurooto.app import App
from kurooto.core import addons, ledger, proposals, retention, tap, uninstall
from kurooto.core.config import Settings
from kurooto.core.tools import agent_tools, run_tool
from kurooto.modules.alarm import Alarm
from kurooto.modules.calls import Calls
from kurooto.modules.google import Google
from kurooto.modules.quiz import Quiz

SETTING_SINKS = {
    "mail_digest.read": "mail.read",
    "mail_digest.query": "mail.read",
    "research.repos": "repo.attach",
    "research.projects": "repo.attach",
    "research_addon.latex_repos": "repo.attach",
    "projects.folders": "repo.attach",
}
# what a tool gets for each argument (anything else: "test"; booleans: True)
VALUES = {
    "when": "tomorrow 7:00",
    "time": "7:30",
    "until": "2h",
    "reason": "the essay",
    "text": "Hello",
    "question": "Which chapter?",
    "then": "Note it: {answer}",
    "request": "plan my week",
    "subject": "la",
    "days": "7",
    "minutes": "30",
    "fact": "no calls before 8",
    "query": "eigenvalues",
    "slug": "inbox/tap-test",
    "name": "evening",
    "done": "1",
    "total": "3",
}
SKIP = {"fetch_url", "sync_now"}  # the web, and every sync at once: neither is guarded, both have their own tests


@pytest.fixture
def hits(monkeypatch):
    """The guarded actions reached, in order. The real ones don't run (no alarm is set, no phone rings)."""
    got: list[str] = []

    def stand_in(action):
        def f(*a, **k):
            got.append(action)
            return "ok"

        return f

    for name in ("set", "set_daily", "clear", "clear_at", "clear_all", "skip"):
        monkeypatch.setattr(Alarm, name, stand_in("alarm.set"))
    for name in ("place", "schedule", "ring"):
        monkeypatch.setattr(Calls, name, stand_in("call.place"))
    monkeypatch.setattr(retention, "forget", stand_in("data.delete"))
    monkeypatch.setattr(addons, "install", stand_in("addon.install"))
    monkeypatch.setattr(proposals, "apply", stand_in("proposal.apply"))
    monkeypatch.setattr(ledger, "forget", stand_in("data.delete"))
    monkeypatch.setattr(uninstall, "remove", stand_in("install.remove"))
    real_set, real_api = Settings.set, Google.api

    def setting(self, dotted, value):
        if dotted in SETTING_SINKS:
            got.append(SETTING_SINKS[dotted])
        return real_set(self, dotted, value)

    def api(self, service, path, *a, **k):
        if "/send" in str(path):
            got.append("send.out")
            return {}
        return real_api(self, service, path, *a, **k)

    monkeypatch.setattr(Settings, "set", setting)
    monkeypatch.setattr(Google, "api", api)
    return got


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    a = App()
    a.settings.set("modules.enabled", list(a.modules))  # every feature on, so every tool and request is there
    monkeypatch.setattr(Quiz, "_calls_ok", lambda self: True)  # a quiz by call can ring
    yield a
    a.close()


def args_for(t) -> dict:
    return {
        k: VALUES.get(k, True if isinstance(spec, dict) and spec.get("type") == "boolean" else "test")
        for k, spec in t.params.items()
    }


def every_tool(app) -> list:
    seen, out = set(), []
    for t in app.modules["calls"].tools() + agent_tools(app):  # live calls, then unattended runs
        if t.name not in seen:
            seen.add(t.name)
            out.append(t)
    return out


def test_the_table_names_each_action_and_how_it_is_approved():
    assert set(tap.GUARDED) == {
        "alarm.set",
        "call.place",
        "mail.read",
        "send.out",
        "repo.attach",
        "addon.install",
        "data.delete",
        "proposal.apply",
        "install.remove",
        "voice.enrol",  # (voice id) enrolling and changing the voice it knows: typed or a button, never by voice
    }
    for action, g in tap.GUARDED.items():
        assert g.what and g.where and g.ways, action
        assert set(g.ways) <= set(tap.WAYS), action
    assert "call" not in tap.GUARDED["send.out"].ways  # sending out always waits for a tap, on a call too
    for prefix, action in tap.BUTTONS.items():  # a button that does a guarded action: a way the table allows
        assert action in tap.GUARDED and "button" in tap.GUARDED[action].ways, prefix


def test_every_tool_that_acts_says_so(app, hits):
    """Each tool, run as on a live call: what it reached must be its tag, and its tag's ways must allow it there."""
    wrong, reached = [], {}
    for t in every_tool(app):
        if t.guarded:
            assert t.guarded in tap.GUARDED, t.name
            assert ("approval" if t.asks else "call") in tap.GUARDED[t.guarded].ways, t.name
        if t.name in SKIP:
            continue
        hits.clear()
        try:
            t.run(args_for(t))
        except Exception:
            pass  # a tool that can't run with made-up arguments reached nothing either
        reached[t.name] = set(hits)
        if set(hits) - ({t.guarded} - {""}):
            wrong.append(f"{t.name} reached {sorted(set(hits))} but is tagged {t.guarded or 'nothing'}")
    assert not wrong, "untagged guarded actions (Tool(guarded=...), core/tap.py):\n" + "\n".join(wrong)
    # the tags are real: these do reach what they say
    for name, action in {
        "set_alarm": "alarm.set",
        "schedule_call": "call.place",
        "call_now": "call.place",
        "schedule_quiz": "call.place",
    }.items():
        assert reached[name] == {action}, name


def test_unattended_ai_runs_ask_first_and_only_approve_does_it(app, hits):
    for via in ("ai", "mcp", "api"):
        for t in agent_tools(app):
            if t.name not in SKIP:
                run_tool(app, t.name, args_for(t), via=via)
    assert hits == []  # nothing guarded happened by itself
    asked = app.ask.pending(kind="approval", source="tap")
    tools = sorted({q["hook_payload"]["tool"] for q in asked})
    assert tools == ["schedule_call", "schedule_quiz", "set_alarm"]
    assert len(asked) == 3  # asked once each, however often the AI tries
    assert "already waits for the user's tap" in run_tool(app, "set_alarm", {"time": "7:30"})
    out = run_tool(app, "set_alarm", {"time": "6:15"})
    assert out.startswith("Not done yet") and "Approve" in out and hits == []
    q = next(q for q in asked if q["hook_payload"]["tool"] == "set_alarm")
    assert "set, move or clear an alarm" in q["text"] and "time: 7:30" in q["text"]
    assert app.ask.answer(q["id"], "Approve")["note"] == "ok" and hits == ["alarm.set"]
    q = next(q for q in asked if q["hook_payload"]["tool"] == "schedule_call")
    assert app.ask.answer(q["id"], "Deny")["note"].startswith("Not done") and hits == ["alarm.set"]
    # a quiz that only sends a message isn't guarded
    hits.clear()
    assert not run_tool(app, "schedule_quiz", {"when": "21:00", "by_call": False}).startswith("Not done")
    assert hits == []
    # on a live call (and a call that went on as text) you're there: it runs
    app.modules["calls"].run_tool("set_alarm", {"time": "6:45"})
    run_tool(app, "schedule_call", {"when": "in 2 hours", "reason": "x"}, via="call")
    assert hits == ["alarm.set", "call.place"]


def test_a_reply_draft_asks_by_itself():
    from kurooto.modules.google_mail import ReplyDrafts

    t = next(t for t in ReplyDrafts.agent_tools(ReplyDrafts.__new__(ReplyDrafts)) if t.name == "draft_reply")
    assert t.guarded == "send.out" and t.asks and tap.action_of(t, {}) == ""


def test_every_request_that_acts_says_so(env, hits):
    """Each plain-English request's examples, said on Telegram with every feature on: what it reached must be its tag,
    and the tag's ways must allow asking in plain words."""
    app = env.app
    app.settings.set("modules.enabled", list(app.modules))
    for setup in ("/subject add Linear Algebra (la)", "/busy add gym mon,wed,fri 18:00-19:00", "/due fri 17:00 ps3"):
        env.say(setup)
    owner = {}
    for m in app.modules.values():
        for it in m.intents():
            assert it.name not in owner, f"two requests are called {it.name}"
            owner[it.name] = it
            if it.guarded:
                assert it.guarded in tap.GUARDED and "said" in tap.GUARDED[it.guarded].ways, it.name
    wrong = []
    for it in list(owner.values()):
        assert it.examples, f"{it.name} has no examples for /help"
        for ex in it.examples:
            hits.clear()
            n = len(app.events.tail(500))
            env.say(ex)
            ran = [e["name"] for e in app.events.tail(500)[n:] if e["kind"] == "intent"]
            tags = {owner[r].guarded for r in ran if r in owner} - {""}
            if set(hits) - tags:
                wrong.append(f"{ex!r} ({', '.join(ran) or 'no request'}) reached {sorted(set(hits))}")
    assert not wrong, "untagged guarded actions (Intent(guarded=...), core/tap.py):\n" + "\n".join(wrong)


def test_what_you_say_in_passing_never_acts(app, hits):
    """Setting itself up from what you say (core/infer.py) never sets an alarm, calls, mails or attaches code."""
    from kurooto.core import infer

    for text in (
        "I got a project under Prof Lena Ortiz",
        "meeting with Ortiz friday at 4",
        "every Monday at 9 I have a Linear Algebra lab",
        "every Tuesday and Thursday at 7pm I go to the gym",
        "gym Tue Thu 7am",
        "call mum Tue Thu 7pm",
        "wake up Mon Wed 6am",
        "Also there's a quiz on Linear Algebra every Monday at 10.",
        "I have lab every Thursday 2-5",
        "LA problem set tonight. More LA tomorrow.",
        "I need to wake up at 6 tomorrow",
        "I'll call mum at 5",
        "I should email Prof Ortiz about the draft",
        "my code for the project is in ~/code/thesis",
        "I want to delete my old notes",
    ):
        infer.observe(app, text)
    assert hits == []
