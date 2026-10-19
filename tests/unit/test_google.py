"""Google add-ons against a fake Google: each asks for its own permission (one sign-in turns it on), Classroom → notes
(materials, Drive files, batches for the AI, retries, the exam-prep note), the mail digest (only what you chose is
read; the rest is counted and never fetched), reply drafts (nothing sent without a tap) and the Agent plan calendar
(Kurooto writes only to its own calendar)."""

from __future__ import annotations

import base64
import datetime as dt
import io
import json
import zipfile
from email import message_from_bytes

import pytest

from kurooto.core.tools import run_tool
from kurooto.modules import google_classroom as gc
from kurooto.modules import google_mail as gmail
from kurooto.modules.google import SCOPES, run_skill, shipped_skill
from kurooto.modules.google_classroom import ClassroomNotes, extract_text, write_exam_prep
from kurooto.modules.google_mail import MailDigest, ReplyDrafts
from kurooto.modules.google_plan import AgentPlan
from tests.fakes.google import RECENT, FakeGoogle
from tests.fakes.openai import FakeOpenAI

CLIENT = json.dumps({"installed": {"client_id": "cid.apps.googleusercontent.com", "client_secret": "csec"}})
PARTS = (ClassroomNotes, MailDigest, ReplyDrafts, AgentPlan)


def docx(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        z.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="{w}"><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>',
        )
    return buf.getvalue()


@pytest.fixture
def gx(env):
    """Google signed in (Classroom deadlines), the add-ons known to the app, and a fake AI brain."""
    g, ai = FakeGoogle(), FakeOpenAI()
    app = env.app
    for cls in PARTS:  # the coordinator registers these in the catalog; tests don't depend on that
        app.modules.setdefault(cls.id, cls(app))
    app.settings.set("google.endpoints", g.endpoints())
    app.power.current = "normal"  # background work runs now, on battery or not
    app.secrets.set("custom.api_key", ai.key)
    app.settings.set("brain.base_urls", {"custom": ai.base})
    app.settings.set("brain.models", {"custom": {"low": "fast", "medium": "smart", "high": "smart"}})
    app.settings.set("brain.main", "custom")
    gm = app.modules["google"]
    gm.set_client(CLIENT)
    code, state = g.issue_code(gm.start_signin())
    assert gm.finish_signin(code, state)[0]
    env.on("deadlines", "google")
    yield env, g, ai
    g.close()
    ai.close()


def allow(env, g, part_id: str, drop: str = "") -> str:
    """Set an add-on up the way the dashboard does: Save on its card, then Google's sign-in comes back."""
    from kurooto.web.api import Api

    r = Api(env.app).post("modules/configure", {"id": part_id, "values": {}})[1]
    assert r["ok"] and r["open"], r
    code, state = g.issue_code(r["open"], drop=drop)
    return env.app.modules["google"].finish_signin(code, state)[1]


def run_jobs(app, n: int = 10) -> int:
    done = 0
    while done < n and app.jobs.run_next():
        done += 1
    return done


# ------------------------------------------------------------------------------------------- permissions
def test_each_add_on_asks_for_its_own_permission(gx):
    env, g, ai = gx
    app, gm = env.app, env.app.modules["google"]
    md = app.modules["mail_digest"]
    assert md.ready() == (False, "needs Google's OK for this: Set up, then sign in")
    assert app.enable("mail_digest")[0] is False
    form = md.setup_form()
    assert form["fields"] == [] and "read your email (read-only" in form["intro"] and "hasn't verified" in form["intro"]
    # the user unticks Gmail on Google's consent screen: nothing turns on, Classroom keeps working
    msg = allow(env, g, "mail_digest", drop="gmail.readonly")
    assert "Turned on" not in msg and not app.is_on("mail_digest") and gm.ready() == (True, "")
    msg = allow(env, g, "mail_digest")
    assert msg == "Signed in with Google. Turned on: Mail digest. You can close this tab."
    assert app.is_on("mail_digest") and md.ready() == (True, "")
    assert "gmail.readonly" in g.scope and "gmail.compose" not in g.scope  # nothing it didn't ask for
    assert set(SCOPES["agent_calendar"]) == {"https://www.googleapis.com/auth/calendar.app.created"}
    # access later removed for that part only: the feature pauses and says how to fix it, once a day
    t = gm.tokens()
    app.secrets.set("google.tokens", json.dumps({**t, "scope": t["scope"].replace(SCOPES["mail_digest"][0], "")}))
    n = len(env.fake.texts())
    assert md.digest({}) == {"skipped": "needs Google's OK"}
    assert "Mail digest is paused" in env.fake.texts()[-1] and "Features → Mail digest" in env.fake.texts()[-1]
    md.digest({})
    assert len(env.fake.texts()) == n + 1
    assert gm.ready() == (True, "")


def test_add_on_needs_google_first(env):
    md = MailDigest(env.app)
    assert md.configure({})["ok"] is False
    assert md.ready()[0] is False


# ------------------------------------------------------------------------------------- Classroom → notes
@pytest.fixture
def classroom(gx):
    env, g, ai = gx
    g.drive = {
        "DOCX000000000000000000001": {
            "name": "Lecture 5.docx",
            "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "data": docx("Eigenvalues are roots"),
        },
        "GDOC000000000000000000001": {
            "name": "Reading list",
            "mimeType": "application/vnd.google-apps.document",
            "data": b"Read chapter 6 on diagonalisation.",
        },
        "VIDEO00000000000000000001": {"name": "Recording.mp4", "mimeType": "video/mp4", "data": b"x"},
        "SECRET0000000000000000001": {"name": "x.pdf", "mimeType": "application/pdf", "data": b"x", "forbidden": True},
    }
    g.materials["c1"] = [
        {
            "id": "m1",
            "title": "Lecture 5: eigenvalues",
            "description": "Slides and notes. Reading: https://docs.google.com/document/d/GDOC000000000000000000001/edit",
            "creationTime": RECENT,
            "updateTime": RECENT,
            "alternateLink": "https://classroom.example.com/m1",
            "materials": [
                {"driveFile": {"driveFile": {"id": "DOCX000000000000000000001", "title": "Lecture 5.docx"}}},
                {"driveFile": {"driveFile": {"id": "VIDEO00000000000000000001", "title": "Recording"}}},
                {"driveFile": {"driveFile": {"id": "SECRET0000000000000000001", "title": "Answers"}}},
                {"link": {"url": "https://example.org/notes"}},
            ],
        },
        {"id": "m0", "title": "Old slides", "creationTime": "2020-01-01T00:00:00Z", "updateTime": "2020-01-01T00:00Z"},
    ]
    g.posts["c1"].append({"id": "a9", "text": "Midterm on Nov 5, 10:00", "creationTime": RECENT, "updateTime": RECENT})
    g.courses.append({"id": "c2", "name": "Chess club"})
    g.materials["c2"] = None  # this course doesn't share materials: it's skipped quietly
    env.app.settings.set("classroom_notes.skip", ["chess"])
    assert allow(env, g, "classroom_notes").endswith("Turned on: Classroom → notes. You can close this tab.")
    yield env, g, ai, env.app.modules["classroom_notes"]


def test_classroom_notes_fetches_posts_files_and_hands_them_to_the_ai(classroom, monkeypatch):
    env, g, ai, cn = classroom
    app = env.app
    app.settings.set("subjects.list", [{"name": "Linear Algebra", "slug": "lin-alg", "aliases": ["la"]}])
    env.on("subjects")
    monkeypatch.setattr(gc, "not_interested", lambda a, text: "pep rally" if "pep rally" in text.lower() else None)
    g.posts["c1"].append({"id": "a8", "text": "Pep rally tomorrow!", "creationTime": RECENT, "updateTime": RECENT})
    r = cn.sync()
    # m1, the welcome post, the midterm notice and three coursework items (the fake has no dates on those); not m0
    assert r == {"items": 6, "courses": 1, "not_interested": 1, "queued": 1}
    assert not any("/c2/" in p for _, p in g.requests)  # a skipped course isn't even read
    batch = json.loads(next((cn.dir / "batches").glob("*.json")).read_text())
    assert batch["folder"] == "lin-alg" and batch["not_interested"] == 1
    m1 = next(i for i in batch["items"] if i["title"] == "Lecture 5: eigenvalues")
    files = {f["title"]: f for f in m1["files"]}
    assert files["Lecture 5.docx"]["chars"] > 0 and files["Reading list"]["chars"] > 0
    assert files["Recording"]["note"] == "video: open the link" and files["Answers"]["note"] == "no access (403)"
    assert m1["links"] == ["https://example.org/notes"]
    saved = list((app.paths.data / "classroom" / "lin-alg").iterdir())
    assert any(p.name.endswith(".docx.txt") for p in saved)
    assert not list(app.workspace.rglob("*.docx"))  # files stay in Kurooto's data folder, not your notes
    # the AI gets the skill with the batch in it, including the file text
    assert run_jobs(app) == 1
    prompt = json.dumps(ai.requests[-1])
    assert "Eigenvalues are roots" in prompt and "chapter 6 on diagonalisation" in prompt
    assert "Notes folder: lin-alg/" in prompt and "update_exam_prep" in prompt and "Pep rally" not in prompt
    assert env.fake.texts()[-1] == "Classroom: filed 6 new items from Linear Algebra into lin-alg/."
    assert not list((cn.dir / "batches").glob("*.json"))
    assert cn.sync()["items"] == 0  # nothing new
    g.materials["c1"][0]["updateTime"] = "2099-01-01T00:00:00Z"  # edited post: filed again
    assert cn.sync()["items"] == 1


def test_classroom_batches_are_retried_until_filed(classroom):
    env, g, ai, cn = classroom
    ai.mode = "500"
    cn.sync()
    run_jobs(env.app)
    b = next((cn.dir / "batches").glob("*.json"))
    assert json.loads(b.read_text())["tries"] == 1
    assert cn.queue() == 1 and cn.queue() == 0  # queued again once, not twice while waiting
    run_jobs(env.app)
    run_jobs(env.app, 0)
    ai.mode = "ok"
    cn.queue()
    run_jobs(env.app)
    assert not b.exists()


def test_classroom_command_and_courses(classroom):
    env, g, ai, cn = classroom
    assert env.say("/classnotes courses") == "Linear Algebra: linear-algebra/\nChess club: skipped/"
    assert env.say("/classnotes unskip chess") == 'Courses with "chess" in their name are filed again.'
    assert env.say("/classnotes").startswith("Found 6 new item(s) in 1 course(s)")
    assert env.say("/classnotes") == "Nothing new in Classroom."


def test_course_file_tool_and_exam_prep(classroom):
    env, g, ai, cn = classroom
    app = env.app
    cn.sync()
    rel = next(p for p in (app.paths.data / "classroom").rglob("*.docx")).relative_to(app.paths.data / "classroom")
    out = run_tool(app, "read_course_file", {"file": rel.as_posix(), "start": "0"})
    assert out.startswith("[characters 0-") and "Eigenvalues" in out
    assert run_tool(app, "read_course_file", {"file": "../../config/settings.json"}).startswith("No such file")
    # the exam-prep block is Kurooto's; the user's own text around it stays
    prep = "## Must know\n- An eigenvalue of A is a root of det(A - tI) = 0.\n"
    assert run_tool(app, "update_exam_prep", {"subject": "linear-algebra", "text": prep}) == (
        "Updated linear-algebra/exam-prep.md."
    )
    f = app.workspace / "linear-algebra" / "exam-prep.md"
    f.write_text(f.read_text() + "\n## Key ideas\n- my own line\n")
    run_tool(
        app, "update_exam_prep", {"subject": "linear-algebra", "text": "## Must know\n- Trace = sum of eigenvalues"}
    )
    text = f.read_text()
    assert "Trace = sum" in text and "det(A - tI)" not in text and "- my own line" in text
    assert text.count("kurooto:exam-prep") == 2 and text.startswith("---\nmade_by: Kurooto")
    assert "Exam prep: Linear Algebra" in text
    assert run_tool(app, "update_exam_prep", {"subject": "../x", "text": "y"}).startswith("The subject must be")
    env.on("quiz")
    assert "linear-algebra" in app.modules["quiz"].sources()


def test_write_exam_prep_keeps_a_note_without_markers(tmp_path):
    f = tmp_path / "physics" / "exam-prep.md"
    f.parent.mkdir()
    f.write_text("# Mine\n\n- my notes\n")
    write_exam_prep(tmp_path, "physics", "## Gaps\n- optics <!-- /kurooto:exam-prep -->", "Physics", "K")
    text = f.read_text()
    assert text.startswith("# Mine\n\n- my notes\n\n<!-- kurooto:exam-prep") and text.count("/kurooto:exam-prep") == 1


def test_text_from_office_files_and_notebooks(tmp_path):
    p = tmp_path / "a.docx"
    p.write_bytes(docx("Hello there"))
    assert extract_text(p) == "Hello there"
    pp = tmp_path / "s.pptx"
    a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    with zipfile.ZipFile(pp, "w") as z:
        for n, t in ((2, "Second"), (1, "First"), (10, "Tenth")):
            z.writestr(
                f"ppt/slides/slide{n}.xml",
                f'<p:sld xmlns:p="urn:p" xmlns:a="{a}"><a:p><a:r><a:t>{t}</a:t></a:r></a:p></p:sld>',
            )
    assert extract_text(pp) == "--- slide 1 ---\nFirst\n\n--- slide 2 ---\nSecond\n\n--- slide 3 ---\nTenth"
    nb = tmp_path / "n.ipynb"
    nb.write_text(json.dumps({"cells": [{"source": ["x = 1\n", "y = 2"]}, {"source": ["# notes"]}]}))
    assert extract_text(nb) == "x = 1\ny = 2\n\n# notes"
    assert extract_text(tmp_path / "missing.docx") is None


# ------------------------------------------------------------------------------------------- mail digest
@pytest.fixture
def mail(gx):
    env, g, ai = gx
    g.add_mail("p1", "Dr Lee <lee@school.example>", "Can you present on Thursday?", "Hi, could you present PS3?")
    g.add_mail("f1", "Mum <mum@gmail.example>", "Dinner on Sunday", "Our private family plans")
    g.add_mail("x1", "Shop <deals@school.example>", "50% off", "Buy now", labels=["INBOX", "CATEGORY_PROMOTIONS"])
    g.add_mail(
        "c1",
        "Lab office <lab@other.example>",
        "Lab report due Nov 2",
        "Due 2026-11-02 17:00",
        labels=["INBOX", "Label_7"],
    )
    g.add_mail("n1", "Clubs <clubs@school.example>", "Pep rally tickets", "Tickets on sale")
    g.add_mail("s1", "Me <me@school.example>", "note to self", "mine")
    assert allow(env, g, "mail_digest").endswith("Turned on: Mail digest. You can close this tab.")
    yield env, g, ai, env.app.modules["mail_digest"]


def test_mail_digest_reads_only_what_you_chose(mail, monkeypatch):
    env, g, ai, md = mail
    app = env.app
    monkeypatch.setattr(gmail, "not_interested", lambda a, text: "pep rally" if "pep rally" in text.lower() else None)
    r = md.digest()
    # own domain is read (a school account); a personal sender, promotions, an unchosen label and pep rally are not
    assert r["read"] == 1 and r["piles"] == {"other": 2, "promotions": 1, "not interested": 1}
    assert g.full_fetched == ["p1"]  # the others' text was never even downloaded
    assert g.mail_queries[0].startswith("after:") and "-in:sent" in g.mail_queries[0]
    run_jobs(app)
    prompt = json.dumps(ai.requests[-1])
    assert "could you present PS3" in prompt and "message id p1" in prompt
    assert "family plans" not in prompt and "Dinner on Sunday" not in prompt and "Buy now" not in prompt
    assert "only counted (never describe these): 2 other, 1 not interested, 1 promotions." in prompt
    assert "if it's personal (not study or work), only count it" in prompt
    assert "Reply drafts: off" in prompt and "mail/" in prompt
    assert env.fake.texts()[-1] == "Mail digest\n\nParis."  # the AI's digest, sent to you
    # you choose a label: from now on that label's mail is read and summarised, whatever its sender
    assert env.say("/mail read label:Courses") == "The digest reads mail matching label:Courses."
    g.add_mail("c2", "Lab office <lab@other.example>", "Lab moved", "Room 4 now", labels=["INBOX", "Label_7"])
    assert md.digest()["read"] == 1 and g.full_fetched[-1] == "c2"
    run_jobs(app)
    second = json.dumps(ai.requests[-1])
    assert "you chose label:Courses (you chose this sender or label: summarise it)" in second
    assert "Labels: Courses" in second and "CATEGORY" not in second


def test_mail_on_a_personal_account_reads_nothing_until_you_choose(mail):
    env, g, ai, md = mail
    g.me = "example@gmail.com"  # a personal account: no "own domain"
    (md.dir / "state.json").unlink(missing_ok=True)
    r = md.digest({})  # the scheduled run
    assert r["read"] == 0 and r["queued"] == 0 and g.full_fetched == []
    assert "none from senders or labels you chose" in env.fake.texts()[-1]
    n = len(env.fake.texts())
    g.add_mail("z1", "Dr Lee <lee@school.example>", "Hi", "text")
    md.digest({})
    assert len(env.fake.texts()) == n  # the hint comes at most once a day
    env.say("/mail read @school.example")
    g.add_mail("z2", "Dr Lee <lee@school.example>", "Again", "more text")
    r = md.digest({})
    assert r["read"] == 1 and g.full_fetched == ["z2"]
    batch = json.loads(next((md.dir / "batches").glob("*.json")).read_text())
    assert batch["counted"]["other"] >= 5  # counts carried over to the next digest


def test_mail_rules_command(mail):
    env, g, ai, md = mail
    assert env.say("/mail read nonsense").startswith("Usage: /mail read")
    assert env.say("/mail read SAM@example.org") == "The digest reads mail matching sam@example.org."
    assert (
        env.say("/mail rules") == "The digest reads:\n- sam@example.org\n- mail from @school.example (your own domain)"
        "\nNever read either: mail marked confidential."
    )
    assert env.say("/mail unread sam@example.org") == "The digest no longer reads mail matching sam@example.org."
    assert env.app.settings.get("mail_digest.read") == []
    assert env.say("/mail").startswith("Reading 2 new message(s) (3 only counted)")
    assert env.say("/mail").startswith("No new mail to digest")


def test_mail_failures_are_retried_and_told_twice_at_most(mail):
    env, g, ai, md = mail
    ai.mode = "500"
    md.digest()
    for _ in range(4):
        run_jobs(env.app)
        md.queue()
    told = [t for t in env.fake.texts() if "didn't come together" in t]
    assert len(told) == 2
    ai.mode = "ok"
    run_jobs(env.app)
    assert not list((md.dir / "batches").glob("*.json"))


def test_body_text_prefers_plain_and_drops_quotes():
    html_part = {"mimeType": "text/html", "body": {"data": base64.urlsafe_b64encode(b"<p>Hi&amp;bye</p>").decode()}}
    assert gmail.body_text({"parts": [html_part]}) == "Hi&bye"
    plain = b"Yes please.\n\nOn Mon, Oct 19, 2026 Sam wrote:\n> old text\n"
    p = {"mimeType": "text/plain", "body": {"data": base64.urlsafe_b64encode(plain).decode()}}
    assert gmail.body_text({"parts": [html_part, p]}) == "Yes please."


# ------------------------------------------------------------------------------------------- reply drafts
@pytest.fixture
def drafts(mail):
    env, g, ai, md = mail
    g.add_mail("nr", "Robot <no-reply@school.example>", "Your ticket", "Automated")
    md.digest()
    run_jobs(env.app)
    assert allow(env, g, "reply_drafts").endswith("Turned on: Email reply drafts. You can close this tab.")
    assert "gmail.compose" in g.scope
    yield env, g, ai, env.app.modules["reply_drafts"]


def test_reply_draft_waits_for_your_tap(drafts):
    env, g, ai, rd = drafts
    app = env.app
    out = run_tool(app, "draft_reply", {"message_id": "p1", "text": "Subject: x\n\nYes, I can.", "why": "a request"})
    assert out.startswith("Draft saved in Gmail")
    assert g.sent == [] and len(g.draft_store) == 1
    did, sent = next(iter(g.draft_store.items()))
    msg = message_from_bytes(base64.urlsafe_b64decode(sent["raw"]))
    assert msg["To"] == "Dr Lee <lee@school.example>" and msg["Subject"] == "Re: Can you present on Thursday?"
    assert msg["In-Reply-To"] == "<p1@mail.example>" and sent["threadId"] == "t-p1"
    assert msg.get_payload().strip() == "Yes, I can."
    q = app.ask.pending(source="reply_drafts")[-1]
    assert q["kind"] == "approval" and q["choices"] == ["Send", "Edit", "Discard"] and "Yes, I can." in q["text"]
    # refused: unknown mail, no-reply senders, a second draft for the same mail
    assert run_tool(app, "draft_reply", {"message_id": "zzz", "text": "hi"}).startswith("I only draft replies")
    assert "doesn't take replies" in run_tool(app, "draft_reply", {"message_id": "nr", "text": "hi"})
    assert run_tool(app, "draft_reply", {"message_id": "p1", "text": "again"}).startswith("There's already a draft")
    # Edit: say what to change; the AI rewrites it, the draft in Gmail changes, and you're asked again
    r = app.ask.answer(q["id"], "Edit", "telegram")
    assert r["ok"]
    change = app.ask.pending(source="reply_drafts")[-1]
    assert change["kind"] == "question" and "What should I change" in change["text"]
    ai.answer = "Yes, I can present on Thursday at 10."
    app.ask.answer(change["id"], "say I can do 10am", "telegram")
    run_jobs(app)
    assert "say I can do 10am" in json.dumps(ai.requests[-1])
    body = message_from_bytes(base64.urlsafe_b64decode(g.draft_store[did]["raw"])).get_payload()
    assert "Thursday at 10" in body and ("PUT", f"/gmail/users/me/drafts/{did}") in g.requests
    assert g.sent == []
    again = app.ask.pending(source="reply_drafts")[-1]
    assert again["kind"] == "approval" and "Thursday at 10" in again["text"]
    app.ask.answer(again["id"], "Send", "telegram")
    assert g.sent == [did]
    assert rd.answer(did, "Send") == "That draft was already sent."


def test_reply_draft_discard_and_gone(drafts):
    env, g, ai, rd = drafts
    app = env.app
    run_tool(app, "draft_reply", {"message_id": "p1", "text": "No, sorry."})
    did = next(iter(g.draft_store))
    assert rd.answer(did, "Discard") == "Discarded the draft to Dr Lee."
    assert g.draft_store == {} and g.sent == []
    g.add_mail("p2", "Dr Lee <lee@school.example>", "Another", "Can you check?")
    env.app.modules["mail_digest"].digest()
    run_tool(app, "draft_reply", {"message_id": "p2", "text": "Will do."})
    did = next(iter(g.draft_store))
    g.send_fails = True  # Gmail has a bad moment: you're asked again, nothing is lost
    q = app.ask.pending(source="reply_drafts")[-1]
    assert app.ask.answer(q["id"], "Send", "telegram")["ok"]
    again = [x for x in app.ask.pending(source="reply_drafts") if "Will do." in x["text"]]
    assert len(again) == 1 and again[0]["id"] != q["id"] and g.sent == []
    g.send_fails = False
    g.draft_store.clear()  # you deleted it in Gmail yourself
    assert rd.answer(did, "Send").startswith("That draft isn't in Gmail any more")
    assert g.sent == []


def test_reply_drafts_per_day_cap(drafts):
    env, g, ai, rd = drafts
    env.app.settings.set("reply_drafts.per_day", 1)
    g.add_mail("p3", "Dr Lee <lee@school.example>", "Q", "?")
    env.app.modules["mail_digest"].digest()
    run_tool(env.app, "draft_reply", {"message_id": "p1", "text": "a"})
    assert "enough reply drafts" in run_tool(env.app, "draft_reply", {"message_id": "p3", "text": "b"})


# --------------------------------------------------------------------------------------------- agent plan
def test_agent_plan_writes_only_to_its_own_calendar(gx):
    env, g, ai = gx
    app = env.app
    assert allow(env, g, "agent_plan").endswith("Turned on: Agent plan calendar. You can close this tab.")
    ap = app.modules["agent_plan"]
    day = (dt.datetime.now() + dt.timedelta(days=1)).date()
    out = run_tool(app, "plan_block", {"start": f"{day} 14:00", "end": "15:30", "title": "Problem set 4"})
    assert out == f"Planned {dt.datetime.combine(day, dt.time(14)):%a} 14:00–15:30: Problem set 4."
    ((cid, cal),) = g.calendars.items()
    assert cal["summary"] == "Agent plan"
    ev = next(iter(cal["events"].values()))
    assert ev["summary"] == "Problem set 4" and ev["extendedProperties"]["private"]["kurooto"] == "1"
    assert dt.datetime.fromisoformat(ev["end"]["dateTime"]) - dt.datetime.fromisoformat(ev["start"]["dateTime"]) == (
        dt.timedelta(minutes=90)
    )
    assert run_tool(app, "plan_block", {"start": f"{day} 14:00", "end": "15:30", "title": "problem set 4"}).startswith(
        "Already planned"
    )
    assert run_tool(app, "plan_block", {"start": f"{day} 16:00", "end": f"{day} 15:00", "title": "x"}) == (
        "The block has to end after it starts."
    )
    assert "smaller blocks" in run_tool(
        app, "plan_block", {"start": f"{day} 01:00", "end": f"{day} 20:00", "title": "x"}
    )
    assert run_tool(app, "plan_block", {"start": "whenever", "end": "later", "title": "x"}).startswith(
        "I couldn't read"
    )
    assert [b["title"] for b in ap.plan_blocks(day)] == ["Problem set 4"]
    # deleted in Google Calendar: a new one is made next time
    g.calendars.clear()
    assert ap.plan_blocks(day) == []
    run_tool(app, "plan_block", {"start": f"{day} 09:00", "end": "10:00", "title": "Reading"})
    assert len(g.calendars) == 1 and ap.clear_plan(day) == 1
    # every call went to Kurooto's own calendars, never to "primary" or another calendar
    cal_paths = [p for _, p in g.requests if p.startswith("/calendar")]
    assert cal_paths and all(p == "/calendar/calendars" or "group.calendar.google.com" in p for p in cal_paths)


def test_blocks_command_and_brief(gx):
    env, g, ai = gx
    allow(env, g, "agent_plan")
    later = dt.datetime.now() + dt.timedelta(minutes=30)
    if later.date() != dt.datetime.now().date():
        pytest.skip("too close to midnight")
    t1, t2 = f"{later:%H:%M}", f"{later + dt.timedelta(minutes=5):%H:%M}"
    if t2 < t1:
        pytest.skip("too close to midnight")
    assert env.say(f"/blocks add {t1}-{t2} stretch").startswith("Planned")
    assert env.say("/blocks") == f"Today's plan:\n{t1}–{t2}  stretch"
    assert env.app.modules["agent_plan"].call_brief() == {"plan_today": [f"{t1}–{t2} stretch"]}
    assert env.say("/blocks add nonsense") == "Usage: /blocks add 14:00-15:30 problem set 4"
    assert env.say("/blocks clear") == "Removed 1 block(s) from today's Agent plan."
    assert env.say("/blocks") == "No blocks planned today."


# --------------------------------------------------------------------------------------------------- skills
def test_shipped_skills_and_the_fallback_without_the_skills_feature(gx):
    env, g, ai = gx
    for name in ("classroom-digest", "mail-digest"):
        text, effort = shipped_skill(name, "Course: X\nNotes folder: x/")
        assert "Course: X" in text and "$ARGUMENTS" not in text and effort in ("high", "medium")
    jid = run_skill(env.app, "mail-digest", "Mail to digest: 1 message", "Mail digest", "x.y", {})
    job = env.app.jobs.get(jid)
    assert job.effort_req == "medium" and "Mail to digest: 1 message" in job.prompt and job.quiet


def test_sync_now_runs_every_google_part(mail):
    env, g, ai, md = mail
    assert env.app.modules["google"].sync_now() == (
        True,
        "Classroom: 2 due, 0 new posts; Mail digest: 2 new for the AI",
    )
    assert env.app.modules["google"].sync_now() == (
        True,
        "Classroom: 2 due, 0 new posts; Mail digest: 0 new for the AI",
    )
    env.app.secrets.set("google.tokens", "{}")
    assert env.app.modules["google"].sync_now() == (None, "not ready: sign in with Google")


def test_digests_go_through_the_skills_feature_when_it_is_on(gx):
    env, g, ai = gx
    if "skills" not in env.app.modules:
        pytest.skip("the Skills feature isn't on this branch")
    env.on("chat", "skills")
    jid = run_skill(env.app, "classroom-digest", "Course: X\nNotes folder: x/", "Classroom → notes: X", "x.y", {})
    job = env.app.jobs.get(jid)
    assert job.effort_req == "high" and job.quiet and "Notes folder: x/" in job.prompt
    assert job.title == "Classroom → notes: X"


# ------------------------------------------------------------------------------- confidential mail (policy)
def test_confidential_and_never_read_mail_is_only_counted(mail):
    env, g, ai, md = mail
    g.labels.append({"id": "Label_9", "name": "Restricted"})
    g.add_mail("k1", "Registrar <reg@school.example>", "CONFIDENTIAL: exam paper draft", "The paper is attached.")
    g.add_mail("k2", "Dr Lee <lee@school.example>", "Marks", "Private and Confidential\nPlease review the marks.")
    g.add_mail("k3", "Office <office@school.example>", "Room list", "Rooms for the week", labels=["INBOX", "Label_9"])
    g.add_mail("k4", "Library <lib@school.example>", "Unrestricted access to journals", "Now open to everyone.")
    g.add_mail("k5", "Payroll <pay@hr.school.example>", "Stipend", "Payroll details")
    g.add_mail("k6", "Dean <dean@school.example>", "Please do NOT   forward", "Committee notes")
    assert env.say("/mail never @hr.school.example") == (
        "The digest never reads mail matching @hr.school.example; it's only counted."
    )
    env.say("/mail read label:Restricted")  # choosing a label doesn't override a confidential marking
    r = md.digest()
    assert r["piles"]["confidential"] == 4 and r["piles"]["never read"] == 1
    # subject, label and the never-read list are checked before the body is even downloaded
    assert not {"k1", "k3", "k5", "k6"} & set(g.full_fetched)
    assert "k2" in g.full_fetched and "k4" in g.full_fetched  # opening lines need the body; k2 is dropped right there
    run_jobs(env.app)
    prompt = json.dumps(ai.requests[-1])
    for secret in ("exam paper", "review the marks", "Rooms for the week", "Payroll", "Committee notes", "Stipend"):
        assert secret not in prompt
    assert "Now open to everyone" in prompt  # "unrestricted" isn't the word "restricted"
    assert "4 confidential" in prompt and "1 never read" in prompt
    assert md.known("k2") is None and md.known("k1") is None  # nothing kept to draft a reply to
    assert "Never read:\n- @hr.school.example" in env.say("/mail rules")
    assert env.say("/mail unnever @hr.school.example") == "@hr.school.example is off the never-read list."
    # the words can be tuned, and the check turned off (it's on by default)
    env.app.settings.set("mail_digest.confidential_words", ["embargoed"])
    g.add_mail("k7", "Press <press@school.example>", "Embargoed until Monday", "News")
    g.add_mail("k8", "Dean <dean@school.example>", "Confidential memo", "Memo text")
    r = md.digest()
    assert r["piles"]["confidential"] == 1 and "k8" in g.full_fetched and "k7" not in g.full_fetched
    env.app.settings.set("mail_digest.skip_confidential", False)
    g.add_mail("k9", "Press <press@school.example>", "Embargoed again", "More news")
    assert md.digest()["read"] == 1 and "k9" in g.full_fetched


def test_no_ai_drafts_for_confidential_or_never_read_mail(drafts):
    env, g, ai, rd = drafts
    app, md = env.app, env.app.modules["mail_digest"]
    env.say("/mail never lee@school.example")  # p1 was digested before this
    out = run_tool(app, "draft_reply", {"message_id": "p1", "text": "Yes."})
    assert out.startswith("That mail is marked confidential or on the never-read list")
    env.say("/mail unnever lee@school.example")
    app.settings.set("mail_digest.skip_confidential", False)  # read while the check was off...
    g.add_mail("q1", "Dr Lee <lee@school.example>", "Question", "Do not forward.\nCan you join the panel?")
    md.digest()
    app.settings.set("mail_digest.skip_confidential", True)  # ...and it's back on: still no draft
    assert run_tool(app, "draft_reply", {"message_id": "q1", "text": "Yes."}).startswith("That mail is marked")
    assert g.draft_store == {} and g.sent == []
    assert run_tool(app, "draft_reply", {"message_id": "p1", "text": "Yes."}).startswith("Draft saved in Gmail")
