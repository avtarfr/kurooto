"""0.5.1: Google grants Classroom coursework under its older name (classroom.student-submissions.*), which must count
as the permission asked for, or every sign-in says a box wasn't ticked and Classroom → notes never turns on. And
which Google account is which: /google, the card and the sign-in page show each account's address."""

from __future__ import annotations

from kurooto.modules.google import AUTH, SCOPES, granted_scopes
from kurooto.web.api import Api
from tests.unit.test_google import CLIENT, allow, gx  # noqa: F401 (gx: the signed-in fixture)

NEW_ME, OLD_ME = "classroom.coursework.me.readonly", "classroom.student-submissions.me.readonly"
NEW_ST, OLD_ST = "classroom.coursework.students.readonly", "classroom.student-submissions.students.readonly"


def old_names(scope: str) -> str:
    """What Google's token answer says: the older names for Classroom coursework."""
    return scope.replace(NEW_ME, OLD_ME).replace(NEW_ST, OLD_ST)


def test_old_and_new_names_count_as_both():
    assert {AUTH + NEW_ME, AUTH + OLD_ME} <= granted_scopes(f"openid {AUTH}{OLD_ME}")
    assert {AUTH + NEW_ME, AUTH + OLD_ME} <= granted_scopes(f"{AUTH}{NEW_ME}")  # the other way round
    assert {AUTH + NEW_ST, AUTH + OLD_ST} <= granted_scopes(AUTH + OLD_ST)
    assert AUTH + "userinfo.email" in granted_scopes("openid email")
    assert granted_scopes("") == set() and granted_scopes(None) == set()
    assert AUTH + NEW_ME not in granted_scopes(AUTH + "classroom.courses.readonly")


def test_a_sign_in_answered_with_the_old_names_turns_classroom_notes_on(gx):  # noqa: F811
    env, g, ai = gx
    app, gm = env.app, env.app.modules["google"]
    # the first sign-in (Classroom deadlines) came back with the new name; this time Google answers with the old one
    r = Api(app).post("modules/configure", {"id": "classroom_notes", "values": {}})[1]
    assert r["ok"] and r["open"]
    code, state = g.issue_code(r["open"])
    assert NEW_ME in g.scope
    g.scope = old_names(g.scope)
    ok, msg = gm.finish_signin(code, state)
    assert ok and "weren't ticked" not in msg and "Turned on: Classroom → notes" in msg, msg
    assert OLD_ME in gm.tokens()["scope"] and NEW_ME not in gm.tokens()["scope"]  # kept as Google said it
    assert gm.granted("classroom") and gm.granted("classroom_notes") and gm.ready() == (True, "")
    cn = app.modules["classroom_notes"]
    assert app.is_on("classroom_notes") and cn.ready() == (True, "") and cn.allowed()
    # the next Save on the card doesn't send you round again for a box that was ticked
    assert gm._next_account(["classroom_notes"]) == "main"


def test_a_box_really_left_unticked_is_still_said(gx):  # noqa: F811
    env, g, ai = gx
    msg = allow(env, g, "classroom_notes", drop="courseworkmaterials")
    assert "weren't ticked" in msg and "Classroom materials" in msg and not env.app.is_on("classroom_notes")


def test_which_account_is_which(gx):  # noqa: F811
    env, g, ai = gx
    app, gm = env.app, env.app.modules["google"]
    assert gm.email("main") == g.me  # main's address is asked for too now
    assert "openid" in g.last_auth["scope"] and set(SCOPES["classroom"]) <= set(g.last_auth["scope"].split())
    r = Api(app).post("modules/configure", {"id": "mail_digest", "values": {"account": "personal"}})[1]
    code, state = g.issue_code(r["open"], who="sam@home.example")
    msg = gm.finish_signin(code, state)[1]
    assert msg.startswith("Signed in with Google as sam@home.example (personal).")  # the account it just saved
    out = env.say("/google")
    assert f"- main ({g.me}): Classroom (deadlines and posts)" in out
    assert "- personal (sam@home.example): Mail digest" in out
    card = next(m for m in Api(app)._modules() if m["id"] == "google")["card"]
    assert f"- main ({g.me}): Classroom (deadlines and posts)" in card["lines"]
    label = app.modules["mail_digest"].setup_form()["fields"][0]["label"]
    assert "empty keeps personal (sam@home.example)" in label
    assert app.modules["mail_digest"].setup_form()["fields"][0]["placeholder"] == "personal"
