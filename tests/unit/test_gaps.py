"""Four settings for people who want it the other way: the night only while an alarm is set
(availability.night.alarm_only), how far ahead "due soon" looks (deadlines.plan_h), after-class questions for some
subjects only (capture.subjects, capture.skip_subjects), and a Gmail search for what the mail digest reads
(mail_digest.query), with the confidentiality gate and the personal-mail rule unchanged. Fakes only."""

from __future__ import annotations

import datetime as dt
import json

from kurooto.core.clock import now
from kurooto.modules import daily
from tests.unit.test_google import gx, mail, run_jobs  # noqa: F401 (gx, mail: the signed-in Gmail fixtures)
from tests.unit.test_rhythm import calls  # noqa: F401 (Phone calls on, with a fake call line)


def at(d: dt.date, h: int, m: int = 0) -> dt.datetime:
    return dt.datetime.combine(d, dt.time(h, m))


# ------------------------------------------------------------------------------------- the night (D6)
def test_night_follows_the_alarm_only_when_you_say_so(calls):  # noqa: F811
    app = calls.app
    av = app.availability
    tomorrow = now().date() + dt.timedelta(days=1)
    app.settings.set("availability.night", {"enabled": True, "from": "23:30", "to": "07:00"})  # an older setting
    # the default: the fixed night hours hold calls, alarm or not
    assert app.settings.get("availability.night.alarm_only") is False
    assert av.night(at(tomorrow, 2)) == ("it's night", at(tomorrow, 7))
    # alarm_only, no alarm: nothing holds calls overnight
    app.settings.set("availability.night.alarm_only", True)
    assert av.night(at(tomorrow, 2)) is None and av.call_block(at(tomorrow, 2)) == (None, None)
    # with the alarm set: from bedtime until it rings, and nothing after
    calls.on("alarm")
    app.settings.set("alarm.bedtime", "22:30")
    ring = at(tomorrow, 6)
    app.modules["alarm"].set(ring, daily=True)
    assert av.night(at(now().date(), 23)) == ("you're asleep (alarm set)", ring)
    assert av.call_block(at(now().date(), 23)) == ("you're asleep (alarm set)", ring)
    assert av.night(at(tomorrow, 6, 30)) is None
    assert av.night(at(tomorrow, 23, 45)) is None  # the next night has no alarm yet
    app.modules["alarm"].clear()
    assert av.night(at(now().date(), 23)) is None
    # off altogether still wins
    app.settings.set("availability.night.enabled", False)
    app.settings.set("availability.night.alarm_only", False)
    assert av.night(at(tomorrow, 2)) is None


# ---------------------------------------------------------------------------------- due soon (plan_h)
def test_plan_h_sets_how_far_ahead_due_soon_looks(env, monkeypatch):
    app = env.app
    env.on("deadlines")
    dl = app.modules["deadlines"]
    dl.add("essay draft", dt.datetime.now() + dt.timedelta(hours=20))
    dl.add("lab report", dt.datetime.now() + dt.timedelta(hours=60))
    assert app.settings.get("deadlines.plan_h") == 72
    assert [d["title"] for d in dl.deadlines_soon()] == ["essay draft", "lab report"]
    assert "Due in the next 3 days:\n  essay draft (" in env.say("/status")
    app.settings.set("deadlines.plan_h", 36)
    assert [d["title"] for d in dl.deadlines_soon()] == ["essay draft"]
    assert [d["title"] for d in dl.deadlines_soon(72)] == ["essay draft", "lab report"]  # asked for: still works
    assert [d["what"] for d in dl.call_brief()["due_soon"]] == ["essay draft"]
    text = env.say("/status")
    assert "Due in the next 36 hours:\n  essay draft (" in text and "lab report" not in text
    soon = env.say("what's due soon?")
    assert "essay draft" in soon and "lab report" not in soon
    assert [d["title"] for d in daily.morning_view(app)["due"]] == ["essay draft"]  # the morning page
    monkeypatch.setattr(daily, "plan", lambda *a, **k: "")
    script = app.modules["alarm"].script()  # the wake-up call
    assert "Due soon: essay draft" in script and "lab report" not in script
    app.settings.set("deadlines.plan_h", 120)
    assert "Due in the next 5 days:" in env.say("/status")
    app.settings.set("deadlines.plan_h", "nonsense")
    assert dl.plan_hours() == 72.0


# --------------------------------------------------------------------------- after-class, some subjects
def test_after_class_question_only_for_chosen_subjects(env):
    app = env.app
    env.on("subjects")
    for s in ("Linear Algebra (la)", "Physical Education (pe)", "Statistics (stats)"):
        env.say(f"/subject add {s}")
    t0 = now().replace(second=0, microsecond=0)
    if (t0 + dt.timedelta(minutes=40)).date() != t0.date() or t0.hour == 0:
        return  # too close to midnight to make classes today
    day = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][t0.weekday()]
    slugs = ("linear-algebra", "physical-education", "statistics")
    ends = {}
    for i, (short, slug) in enumerate(zip(("la", "pe", "stats"), slugs, strict=True)):
        start, ends[slug] = t0 - dt.timedelta(minutes=30 - i), t0 + dt.timedelta(minutes=30 + i)  # one slot each
        env.say(f"/class {day} {start:%H:%M}-{ends[slug]:%H:%M} {short}")
    env.on("capture")
    cap = app.modules["capture"]

    def planned() -> set[str]:
        return {s for s in slugs if app.scheduler.get(f"capture:{s}:{ends[s]:%H:%M}")}

    assert planned() == {"linear-algebra", "physical-education", "statistics"}  # the default: every subject
    # a deny list, by short name: no question after PE
    app.settings.set("capture.skip_subjects", ["pe"])
    for s in slugs:
        app.scheduler.cancel(f"capture:{s}:{ends[s]:%H:%M}")
    cap._plan()
    assert planned() == {"linear-algebra", "statistics"}
    # an allow list, by full name, and the deny list still applies
    app.settings.set("capture.subjects", ["Linear Algebra", "pe"])
    assert cap.wanted("linear-algebra") and not cap.wanted("statistics") and not cap.wanted("physical-education")
    # a question already planned for a subject taken off since: not asked
    n = len(env.fake.texts())
    cap._ask({"subject": "statistics", "name": "Statistics", "day": now().date().isoformat(), "start": "09:00"})
    assert len(env.fake.texts()) == n and cap.statuses() == {}
    cap._ask({"subject": "linear-algebra", "name": "Linear Algebra", "day": now().date().isoformat()})
    assert "How was Linear Algebra?" in env.fake.texts()[-1]
    # "all" (the old style) and an empty list both mean every subject
    app.settings.set("capture.subjects", "all")
    app.settings.set("capture.skip_subjects", [])
    assert all(cap.wanted(s) for s in slugs)
    app.settings.set("capture.subjects", "stats, la")
    assert cap.wanted("statistics") and cap.wanted("linear-algebra") and not cap.wanted("physical-education")


# --------------------------------------------------------------------------------- mail by Gmail search (I8)
def test_mail_query_reads_what_it_matches_and_keeps_every_gate(mail):  # noqa: F811
    env, g, ai, md = mail
    app = env.app
    g.me = "example@gmail.com"  # a personal account: no own domain, so before the query nothing is read
    (md.dir / "state.json").unlink(missing_ok=True)
    g.add_mail("u1", "Dept office <office@uni.example>", "Seminar moved", "Now in room 4", labels=["INBOX", "UNREAD"])
    g.add_mail("sx", "Friends <club@social.example>", "Party", "See you", labels=["INBOX", "CATEGORY_SOCIAL"])
    g.add_mail("k1", "Dean <dean@uni.example>", "Budget", "Private and Confidential\nThe numbers.")
    g.add_mail("h1", "Payroll <pay@hr.uni.example>", "Stipend", "Payroll details")
    env.say("/mail never @hr.uni.example")
    assert env.say("/mail query").startswith("No mail query. /mail query -category:promotions -category:social")
    assert env.say("/mail query -category:promotions   -category:social") == (
        "The digest reads mail matching: -category:promotions -category:social (personal mail among it is only "
        "counted)."
    )
    assert app.settings.get("mail_digest.query") == "-category:promotions -category:social"
    assert "- mail matching your query: -category:promotions -category:social" in env.say("/mail rules")
    r = md.digest({})
    # Gmail found them; Promotions and Social only counted; confidential and never-read still never reach the AI
    assert g.mail_queries[-1].endswith("-in:trash (-category:promotions -category:social)")
    assert r["piles"] == {"promotions": 1, "social": 1, "confidential": 1, "never read": 1}
    assert "x1" not in g.full_fetched and "sx" not in g.full_fetched and "h1" not in g.full_fetched
    assert "k1" in g.full_fetched and md.known("k1") is None  # read for the check, dropped right there
    assert r["read"] == 6  # p1, f1, c1, n1, s1 (no longer this account's own address) and u1
    run_jobs(app)
    prompt = json.dumps(ai.requests[-1])
    assert "Now in room 4" in prompt and "family plans" in prompt  # the AI sees it, and is told the rule:
    assert "Why it was read: matches your mail query (read because it matches their mail query: if it's personal" in (
        prompt
    )
    for secret in ("The numbers", "Payroll", "See you", "Buy now"):
        assert secret not in prompt
    # a sender you chose stays "chosen"; the query can't widen past the base search (sent, drafts, spam, chats)
    env.say("/mail read office@uni.example")
    g.add_mail("u2", "Dept office <office@uni.example>", "Talk", "Thursday talk")
    md.digest({})
    run_jobs(app)
    assert "you chose office@uni.example (you chose this sender or label: summarise it)" in json.dumps(ai.requests[-1])
    assert all(q.startswith("after:") and "-in:sent -in:drafts -in:spam -in:trash" in q for q in g.mail_queries)
    assert env.say("/mail query off") == "Mail query off: the digest reads what /mail rules lists, nothing more."
    assert app.settings.get("mail_digest.query") == ""
    n = len(g.mail_queries)
    md.digest({})
    assert len(g.mail_queries) == n + 1  # one search again, not two


def test_mail_query_default_is_unchanged(mail):  # noqa: F811
    env, g, ai, md = mail
    assert env.app.settings.get("mail_digest.query") == ""
    r = md.digest()
    assert r["read"] == 2 and len(g.mail_queries) == 1  # own domain only (p1, n1), one Gmail search
