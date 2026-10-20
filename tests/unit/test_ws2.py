"""Google, several accounts (WS2), against a fake Google only: each account has its own sign-in and only the
permissions of the features that use it; Google Calendar through the API (other people's calendars left out, private
events as "Busy (private)" everywhere); class calendars count as classes; the mail digest emailed only to your own
address (held back if it mentions confidential material); Drive upload for files you send yourself."""

from __future__ import annotations

import base64
import datetime as dt
import inspect
import json
from email import message_from_bytes, policy

import pytest

from kurooto.core.tools import run_tool
from kurooto.modules import capture, google_drive, skills, subjects
from kurooto.modules.calendar import BUSY, parse_ics
from kurooto.modules.google import SCOPES, id_email
from kurooto.modules.google_calendar import GoogleCalendar
from kurooto.modules.google_drive import DriveUpload
from kurooto.modules.google_mail import DigestEmail
from kurooto.web.api import Api
from tests.unit.test_google import PARTS, allow, gx, run_jobs  # noqa: F401 (gx: the signed-in fixture)

SCHOOL, HOME = "sam@school.example", "sam@home.example"
NEW = (GoogleCalendar, DigestEmail, DriveUpload)


@pytest.fixture
def gw(gx):  # noqa: F811
    env, g, ai = gx
    for cls in NEW:  # registered in the catalog; tests don't depend on that
        env.app.modules.setdefault(cls.id, cls(env.app))
    yield env, g, ai


def setup(env, g, part_id: str, account: str = "", who: str = "", drop: str = "") -> str:
    """Save on a feature's card (with an account name, maybe), then Google's page comes back signed in as `who`."""
    r = Api(env.app).post("modules/configure", {"id": part_id, "values": {"account": account}})[1]
    assert r["ok"] and r["open"], r
    code, state = g.issue_code(r["open"], drop=drop, who=who)
    return env.app.modules["google"].finish_signin(code, state)[1]


def scopes_of(url: str) -> set[str]:
    from urllib.parse import parse_qs, urlsplit

    return set(parse_qs(urlsplit(url).query)["scope"][0].split())


# ------------------------------------------------------------------------------------------------ accounts (I1)
def test_a_feature_on_another_account_signs_that_account_in_with_only_its_permissions(gw):
    env, g, ai = gw
    app, gm = env.app, env.app.modules["google"]
    first = g.last_auth
    assert "openid" not in first["scope"] and "calendar.readonly" not in first["scope"]  # main: Classroom only
    r = Api(app).post("modules/configure", {"id": "mail_digest", "values": {"account": "School"}})[1]
    asked = scopes_of(r["open"])
    assert asked == {*SCOPES["mail_digest"], "openid", "https://www.googleapis.com/auth/userinfo.email"}
    assert "select_account" in r["open"] and "(your school account)" in r["message"]
    code, state = g.issue_code(r["open"], who=SCHOOL)
    msg = gm.finish_signin(code, state)[1]
    assert msg.startswith(f"Signed in with Google (school: {SCHOOL}). Turned on: Mail digest.")
    assert gm.account_names() == ["main", "school"] and app.modules["mail_digest"].account == "school"
    assert "gmail.readonly" not in gm.tokens()["scope"]  # main never got the mail permission
    assert gm.email("school") == SCHOOL and app.secrets.get("google.tokens.school")
    # the digest reads the school mailbox; Classroom stays on main
    g.add_mail("p1", "Dr Lee <lee@school.example>", "Question", "Could you present?")
    app.modules["mail_digest"].digest()
    gm.classroom_sync()
    who = {(p.split("/")[1], w) for _, p, w in g.calls}
    assert ("gmail", SCHOOL) in who and ("gmail", g.me) not in who and ("classroom", g.me) in who
    assert ("classroom", SCHOOL) not in who
    # /google lists them
    out = env.say("/google")
    assert f"- school ({SCHOOL}): Mail digest" in out and "- main (signed in): Classroom (deadlines and posts)" in out
    # the reply drafts always answer the digest's mailbox
    assert gm.account_for("reply_drafts") == "school"


def test_google_use_and_forget(gw):
    env, g, ai = gw
    app, gm = env.app, env.app.modules["google"]
    assert env.say("/google use mail main, school") == "This feature uses one Google account."
    assert "short word" in env.say("/google use mail sch@ol")
    assert env.say("/google use mail school") == "Mail digest uses school."  # not set up yet: nothing to sign in
    allow(env, g, "agent_plan")  # on main
    said = env.say("/google use plan personal")
    assert "needs that account's OK once" in said and "Agent plan calendar → Save" in said
    assert app.modules["agent_plan"].ready()[0] is False
    assert "needs your personal Google account" in app.modules["agent_plan"].ready()[1]
    assert setup(env, g, "agent_plan", who=HOME).startswith(f"Signed in with Google (personal: {HOME}).")
    day = (dt.datetime.now() + dt.timedelta(days=1)).date()
    assert run_tool(app, "plan_block", {"start": f"{day} 14:00", "end": "15:00", "title": "Reading"}).startswith(
        "Planned"
    )
    assert [c["owner"] for c in g.calendars.values()] == [HOME]  # Kurooto's own calendar, on the personal account
    assert env.say("/google forget main").startswith("Not one of your other accounts")
    assert env.say("/google forget personal").startswith("Forgot your personal Google account")
    assert gm.account_names() == ["main", "school"] and gm.account_for("agent_calendar") == "main"
    assert app.secrets.get("google.tokens.personal") is None


def test_same_google_account_twice_is_pointed_out(gw):
    env, g, ai = gw
    allow(env, g, "agent_plan")
    setup(env, g, "digest_email", account="main")  # main now knows its address
    msg = setup(env, g, "drive_upload", account="other", who=g.me)
    assert "same Google account as your main one" in msg


def test_lost_signin_of_another_account_pauses_only_its_features(gw):
    env, g, ai = gw
    app, gm = env.app, env.app.modules["google"]
    setup(env, g, "mail_digest", account="school", who=SCHOOL)
    t = gm.tokens("school")
    app.secrets.set("google.tokens.school", json.dumps({**t, "expires": 0}))
    g.refresh_ok = False
    assert app.modules["mail_digest"].digest() == {"error": "needs sign-in"}
    assert "your school Google account expired" in env.fake.texts()[-1] and "Mail digest" in env.fake.texts()[-1]
    assert gm.ready() == (True, "") and gm.signed_in("main") and not gm.signed_in("school")
    assert app.modules["mail_digest"].ready()[1] == "needs your school Google account: Set up, then sign in"


def test_id_email():
    claims = base64.urlsafe_b64encode(json.dumps({"email": "Sam@example.org"}).encode()).decode().rstrip("=")
    assert id_email(f"h.{claims}.s") == "sam@example.org"
    assert id_email("garbage") == "" and id_email(None) == ""


# ---------------------------------------------------------------------------------- Google Calendar (I2, I3)
def _ev(eid, title, start, end=None, **kw):
    if isinstance(start, dt.date) and not isinstance(start, dt.datetime):
        return {
            "id": eid,
            "summary": title,
            "start": {"date": start.isoformat()},
            "end": {"date": end.isoformat()},
            **kw,
        }
    return {
        "id": eid,
        "summary": title,
        "start": {"dateTime": start.astimezone().isoformat()},
        "end": {"dateTime": (end or start + dt.timedelta(hours=1)).astimezone().isoformat()},
        **kw,
    }


@pytest.fixture
def gcal(gw):
    env, g, ai = gw
    t = dt.datetime.now().replace(second=0, microsecond=0) + dt.timedelta(hours=2)
    today = dt.date.today()
    g.add_calendar(
        g.me,
        g.me,
        "Main",
        [
            _ev("m1", "Dentist", t, location="Clinic", visibility="private", description="checkup"),
            _ev("m2", "Hike", t + dt.timedelta(days=1), description="bring water #private"),
            _ev("m3", "Fest", today + dt.timedelta(days=2), today + dt.timedelta(days=3)),
            _ev("m4", "Old", t, status="cancelled"),
        ],
        primary=True,
        accessRole="owner",
    )
    g.add_calendar(g.me, "friend@example.org", "Friend", [_ev("f1", "Their party", t)], accessRole="reader")
    g.add_calendar(g.me, "hidden-example@group.calendar.google.com", "Hidden", [_ev("h1", "x", t)], hidden=True)
    g.add_calendar(
        SCHOOL,
        "timetable-example@group.calendar.google.com",
        "Timetable",
        [_ev("l1", "Linear Algebra lecture", t), _ev("l2", "Guest talk", t + dt.timedelta(hours=3))],
        accessRole="reader",
    )
    yield env, g, ai, t


def test_google_calendar_from_two_accounts(gcal):
    env, g, ai, t = gcal
    app, gm = env.app, env.app.modules["google"]
    r = Api(app).post("modules/configure", {"id": "google_calendar", "values": {"account": "main, school"}})[1]
    assert scopes_of(r["open"]) >= set(SCOPES["calendar_read"]) and "select_account" not in r["open"]  # main first
    code, state = g.issue_code(r["open"])
    msg = gm.finish_signin(code, state)[1]
    assert "Google Calendar also needs your school account: press Save on its card again." in msg
    assert not app.is_on("google_calendar")
    msg = setup(env, g, "google_calendar", who=SCHOOL)
    assert "Turned on: Google Calendar, Calendar." in msg
    assert app.is_on("calendar") and app.modules["calendar"].ready() == (True, "")
    rows = json.loads((app.paths.state / "calendar.json").read_text())
    titles = [e["title"] for e in rows["events"]]
    assert "Linear Algebra lecture" in titles and "Fest" in titles and "Guest talk" in titles
    assert "Their party" not in titles and "x" not in titles and "Old" not in titles  # theirs, hidden, cancelled
    assert "Dentist" not in titles and "Hike" not in titles and titles.count(BUSY) == 2  # private, #private
    assert "Clinic" not in json.dumps(rows) and "checkup" not in json.dumps(rows)
    assert rows["calendars"] == ["Main", "Timetable"]
    fest = next(e for e in rows["events"] if e["title"] == "Fest")
    assert fest["all_day"] is True
    # what Kurooto tells you: Busy (private), never the title
    cal = app.modules["calendar"]
    told = cal.agenda(t.date()) + json.dumps(cal.call_brief())
    assert BUSY in told and "Dentist" not in told
    # read-only: only GET calls to the Calendar API
    assert {m for m, p, _ in g.calls if p.startswith("/calendar")} == {"GET"}


def test_agent_plan_calendar_is_left_out(gcal):
    env, g, ai, t = gcal
    app = env.app
    allow(env, g, "agent_plan")
    end = t + dt.timedelta(hours=1)
    said = run_tool(
        app, "plan_block", {"start": f"{t:%Y-%m-%d %H:%M}", "end": f"{end:%Y-%m-%d %H:%M}", "title": "Study block"}
    )
    assert said.startswith("Planned")
    setup(env, g, "google_calendar")
    titles = [e["title"] for e in json.loads((app.paths.state / "calendar.json").read_text())["events"]]
    assert "Study block" not in titles and BUSY in titles


ICS = """BEGIN:VCALENDAR
X-WR-CALNAME:Timetable
BEGIN:VEVENT
UID:a
SUMMARY:Probability lecture
DTSTART:{s}
DTEND:{e}
END:VEVENT
BEGIN:VEVENT
UID:b
SUMMARY:Therapy
LOCATION:Room 9
CLASS:PRIVATE
DTSTART:{s2}
DTEND:{e2}
END:VEVENT
END:VCALENDAR
"""


@pytest.fixture
def ical(env):
    app = env.app
    # tomorrow at noon, whatever the time now: never at night (night holds calls before classes do)
    t = dt.datetime.combine(dt.date.today() + dt.timedelta(days=1), dt.time(12, 0))
    f = "%Y%m%dT%H%M%S"
    text = ICS.format(
        s=t.strftime(f),
        e=(t + dt.timedelta(hours=1)).strftime(f),
        s2=(t + dt.timedelta(hours=3)).strftime(f),
        e2=(t + dt.timedelta(hours=4)).strftime(f),
    )
    app.secrets.set("calendar.ics", json.dumps(["https://calendar.example/basic.ics"]))
    cal = app.modules["calendar"]
    cal._fetch = lambda url: parse_ics(text, cal.tz())
    yield env, cal, t


def test_ical_private_events_are_busy_everywhere(ical):
    env, cal, t = ical
    app = env.app
    env.on("deadlines", "calendar")
    rows = json.loads(cal.file.read_text())["events"]
    assert [r["title"] for r in rows] == ["Probability lecture", BUSY]
    assert rows[1]["location"] == "" and rows[1]["private"] is True
    app.settings.set("calendar.mask_private", False)
    cal.refresh()
    assert "Therapy" in [r["title"] for r in json.loads(cal.file.read_text())["events"]]


# ------------------------------------------------------------------------------------------ class calendars (F18)
def test_class_calendar_events_count_as_classes(ical, monkeypatch):
    env, cal, t = ical
    app = env.app
    app.settings.set("subjects.list", [{"slug": "probability", "name": "Probability", "aliases": ["prob"]}])
    env.on("subjects", "calendar", "capture")
    subj = app.modules["subjects"]
    assert subj.classes_on(t.date()) == []  # nothing marked yet
    out = env.say("/cal classes")
    assert "Class calendars: none." in out and "Your calendars: Timetable." in out
    assert env.say("/cal classes timetable").startswith("Events in timetable count as classes now")
    c, private = subj.classes_on(t.date())  # the private event is in Timetable too: a class, but only Busy
    assert c["subject"] == "probability" and c["name"] == "Probability" and c["source"] == "calendar"
    assert private["subject"] == "" and private["name"] == BUSY
    assert c["start"] == f"{t:%H:%M}"
    # no calls in class (Subjects holds them, with its margin)
    reason, until = app.availability.call_block(t + dt.timedelta(minutes=5))
    assert reason == "class: Probability" and until == t + dt.timedelta(hours=1)
    # the after-class question is planned for it (planned on the class's day, that morning)
    for mod in (capture, subjects):
        monkeypatch.setattr(mod, "now", lambda: t - dt.timedelta(hours=3))
    app.modules["capture"]._plan()
    assert app.scheduler.get(f"capture:probability:{c['end']}") is not None
    # skipping it: no class then
    asked = [k.key for k in app.scheduler.jobs("capture:") if k.key != "capture:plan"]
    assert asked == [f"capture:probability:{c['end']}"]  # not for the Busy one: it names no subject
    subj.set_skip(["probability"], day=t.date())
    assert [x["name"] for x in subj.classes_on(t.date())] == [BUSY]
    subj.set_skip(["probability"], add=False, day=t.date())
    # a timetable class at the same time isn't doubled
    wd = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][t.weekday()]
    app.settings.set(
        "subjects.timetable",
        [{"day": wd, "start": f"{t:%H:%M}", "end": f"{t + dt.timedelta(hours=1):%H:%M}", "subject": "probability"}],
    )
    assert [x.get("source") for x in subj.classes_on(t.date())] == [None, "calendar"]  # the timetable's, then Busy
    assert env.say("/cal classes none") == "No calendar counts as classes now."
    app.settings.set("subjects.timetable", [])
    assert subj.classes_on(t.date()) == []


def test_class_events_hold_calls_without_subjects(ical):
    env, cal, t = ical
    app = env.app
    app.settings.set("calendar.class_calendars", ["Timetable"])
    app.settings.set("calendar.nocall_events", "tagged")
    env.on("calendar")
    cal.refresh()
    reason, _ = app.availability.call_block(t + dt.timedelta(minutes=5))
    assert reason == "class: Probability lecture"
    reason, _ = app.availability.call_block(t + dt.timedelta(hours=3, minutes=5))
    assert reason == f"class: {BUSY}"  # a private class: held, and its title isn't told
    app.settings.set("calendar.class_calendars", [])
    cal.refresh()
    assert app.availability.call_block(t + dt.timedelta(minutes=5))[0] is None  # tagged-only: ordinary events don't


# ------------------------------------------------------------------------------------------- digest by email (I12)
@pytest.fixture
def mailed(gw):
    env, g, ai = gw
    g.add_mail("p1", "Dr Lee <lee@school.example>", "Can you present on Thursday?", "Hi, could you present PS3?")
    allow(env, g, "mail_digest")
    msg = setup(env, g, "digest_email", account="personal", who=HOME)
    assert "Turned on: Mail digest by email." in msg
    yield env, g, ai, env.app.modules["digest_email"]


def _sent(g, n=-1):
    m = g.mail_sent[n]
    raw = base64.urlsafe_b64decode(m["raw"] + "=" * (-len(m["raw"]) % 4))
    return m["who"], message_from_bytes(raw, policy=policy.default)


def test_digest_is_emailed_to_your_own_address_only(mailed):
    env, g, ai, de = mailed
    app = env.app
    assert set(SCOPES["digest_email"]) <= set(env.app.modules["google"].tokens("personal")["scope"].split())
    ai.answer = "Needs action\n- Present PS3 on Thursday (Dr Lee)\nNot read: Confidential: 2\nNeeds action: 1"
    app.modules["mail_digest"].digest()
    run_jobs(app)
    assert len(g.mail_sent) == 1
    who, msg = _sent(g)
    assert who == HOME and msg["To"] == HOME and msg["From"] == HOME and msg["Subject"].startswith("Mail digest, ")
    assert "Present PS3" in msg.get_body(("plain",)).get_content()
    assert list(inspect.signature(de.send_digest).parameters) == ["text", "when"]  # no recipient to choose


def test_a_digest_mentioning_confidential_material_is_held_back(mailed):
    env, g, ai, de = mailed
    assert de.send_digest("Admin\n- HR notice (marked do not forward)") == (
        "This mail digest mentions confidential material, so it wasn't emailed (it's here only)."
    )
    assert g.mail_sent == [] and "wasn't emailed" in env.fake.texts()[-1]
    assert de.send_digest("Not read: 3 confidential, Confidential (2)") == f"Emailed the digest to {HOME}."


def test_no_address_no_email(mailed):
    env, g, ai, de = mailed
    gm = env.app.modules["google"]
    t = gm.tokens("personal")
    t.pop("email")
    env.app.secrets.set("google.tokens.personal", json.dumps(t))
    assert de.send_digest("hello").startswith("Mail digest by email: Google didn't tell Kurooto your address")
    assert g.mail_sent == []


# ------------------------------------------------------------------------------------------------ Drive upload (I15)
@pytest.fixture
def drive(gw, tmp_path, monkeypatch):
    env, g, ai = gw
    msg = setup(env, g, "drive_upload")
    assert "Turned on: Drive upload." in msg
    assert set(SCOPES["drive_upload"]) <= set(env.app.modules["google"].tokens()["scope"].split())
    monkeypatch.setattr(google_drive, "CHUNK", 256 * 1024)
    yield env, g, ai, env.app.modules["drive_upload"]


def test_send_a_file_to_drive_in_pieces(drive, tmp_path):
    env, g, ai, du = drive
    app = env.app
    f = tmp_path / "big lecture.pdf"
    f.write_bytes(bytes(range(256)) * 2600)  # 650 KB: three pieces
    r = Api(app).post("send-file", {"path": str(f), "caption": "Slides", "to": "drive"})[1]
    assert r["ok"] and r["message"].startswith("Uploading big lecture.pdf (0.6 MB) to your Google Drive")
    du.last.join(10)
    folders = [k for k, v in g.drive_made.items() if v.get("mimeType", "").endswith("folder")]
    files = [v for v in g.drive_made.values() if v.get("data")]
    assert len(folders) == 1 and g.drive_made[folders[0]]["name"] == "Kurooto"
    assert files[0]["data"] == f.read_bytes() and files[0]["parents"] == folders
    assert files[0]["name"].endswith("-big lecture.pdf")
    assert next(iter(g.uploads.values()))["puts"] == 3
    text = env.fake.texts()[-1]
    assert text.startswith(
        "Slides\nbig lecture.pdf is in your Google Drive (Kurooto folder): https://drive.example.com"
    )
    # the next one goes into the same folder; nothing is ever shared
    f2 = tmp_path / "notes.txt"
    f2.write_text("hello")
    assert skills.send_file(app, f2, to="drive")[0]
    du.last.join(10)
    assert len([v for v in g.drive_made.values() if v.get("mimeType", "").endswith("folder")]) == 1
    assert not [p for _, p, _ in g.calls if "permissions" in p]


def test_files_over_telegrams_limit_go_to_drive(drive, tmp_path, monkeypatch):
    env, g, ai, du = drive
    app = env.app
    monkeypatch.setattr(skills, "TELEGRAM_MAX", 1000)
    f = tmp_path / "video.mp4"
    f.write_bytes(b"x" * 3000)
    ok, said = skills.send_file(app, f)
    assert ok and said.startswith("Uploading video.mp4")
    du.last.join(10)
    assert "video.mp4 is in your Google Drive" in env.fake.texts()[-1]
    app.settings.set("drive_upload.big_files", False)
    ok, said = skills.send_file(app, f)
    assert not ok and "Telegram takes files up to 50 MB" in said
    app.disable("drive_upload")
    ok, said = skills.send_file(app, f, to="drive")
    assert not ok and said.startswith("Drive upload is off")


def test_send_file_tool_to_drive(drive):
    env, g, ai, du = drive
    app = env.app
    env.on("chat", "skills")
    p = app.workspace / "inbox" / "pack.pdf"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"%PDF-1.4 tiny")
    out = run_tool(app, "send_file", {"path": "inbox/pack.pdf", "to": "drive"})
    assert out.startswith("Uploading pack.pdf")
    du.last.join(10)
    assert any(v.get("data") == b"%PDF-1.4 tiny" for v in g.drive_made.values())


def test_new_parts_are_registered():
    from kurooto.modules.catalog import CATALOG

    assert {GoogleCalendar, DigestEmail, DriveUpload} <= set(CATALOG)
    assert all(cls.part in SCOPES for cls in (*PARTS, *NEW))


def test_classroom_moved_to_another_account(gw):
    env, g, ai = gw
    app, gm = env.app, env.app.modules["google"]
    assert "needs that account's OK once" in env.say("/google use classroom school")
    assert gm.ready() == (False, "sign in to your school Google account")
    r = Api(app).post("modules/configure", {"id": "google", "values": {}})[1]
    assert "(your school account)" in r["message"] and scopes_of(r["open"]) >= set(SCOPES["classroom"])
    code, state = g.issue_code(r["open"], who=SCHOOL)
    assert gm.finish_signin(code, state)[0] and gm.ready() == (True, "")
    gm.classroom_sync()
    assert {w for _, p, w in g.calls if p.startswith("/classroom")} >= {SCHOOL}
    assert [w for _, p, w in g.calls if p.startswith("/classroom")][-1] == SCHOOL


def test_google_calendar_added_to_an_ical_calendar_refreshes_soon(ical, gx):  # noqa: F811
    env, cal, t = ical
    _, g, _ = gx
    env.app.modules.setdefault(GoogleCalendar.id, GoogleCalendar(env.app))
    env.on("calendar")
    setup(env, g, "google_calendar")
    assert env.app.is_on("google_calendar") and env.app.scheduler.get("google_calendar:refresh") is not None
