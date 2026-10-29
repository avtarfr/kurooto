"""The AI jobs tab says where each request came from (L131, 0.9.0, look.jobs_source): what Chat recorded when it
asked (Telegram, the phone app's chat with its chat, the talk box, voice), else the job itself; off, nothing is
given."""

from __future__ import annotations

from types import SimpleNamespace

from kurooto.core import jobs
from kurooto.web.live import Vitals


def job(jid, reply_to=None, background=False, lane="you"):
    return SimpleNamespace(id=jid, reply_to=reply_to, background=background, lane=lane)


def test_where_a_request_came_from(env):
    app = env.app
    chat = app.modules["chat"]
    chat.job_via("j1", "telegram")
    assert jobs.source(app, job("j1", reply_to="17")) == {"from": "Telegram"}
    chat._job_session("j2", "abcd1234abcd1234")
    chat.job_via("j2", "app")
    assert jobs.source(app, job("j2", reply_to="app:x")) == {"from": "phone chat", "session": "abcd1234abcd1234"}
    assert jobs.source(app, job("j3", reply_to="app:y")) == {"from": "phone chat", "session": "main"}
    chat.job_via("j4", "terminal")
    assert jobs.source(app, job("j4")) == {"from": "talk box or terminal"}
    chat.job_via("j5", "voice")
    assert jobs.source(app, job("j5")) == {"from": "voice at the desk"}
    assert jobs.source(app, job("j6", background=True)) == {"from": "by itself"}
    assert jobs.source(app, job("j7")) == {"from": ""}


def test_the_tab_gets_it_only_with_the_switch(env):
    app = env.app
    jid = app.jobs.submit("hello", title="hello", quiet=True)
    app.modules["chat"].job_via(jid, "terminal")
    row = next(j for j in Vitals(app).snapshot()["jobs"] if j["id"] == jid)
    assert row["source"] == {"from": "talk box or terminal"}
    app.settings.set("look.jobs_source", False)
    row = next(j for j in Vitals(app).snapshot()["jobs"] if j["id"] == jid)
    assert "source" not in row
