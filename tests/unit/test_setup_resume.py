"""The setup page picks up where you left off (core/setupsteps.py): each step finished, skipped for now or not yet,
kept by Kurooto, not the browser. Skipped steps wait on the dashboard and in `kurooto doctor` as notes; the time spent
on each step goes into `kurooto doctor --bundle` only, and the daily message limit is said on the features step."""

import json
import zipfile
from importlib import resources

import pytest

from kurooto.core import setupsteps
from kurooto.web.api import Api


def static(name: str) -> str:
    return resources.files("kurooto.web").joinpath("static", name).read_text(encoding="utf-8")


@pytest.fixture
def app(tmp_path, monkeypatch):
    from kurooto.app import App

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    a = App()
    yield a
    a.close()


def step(api, name, how, seconds=5, **extra):
    return api.post("setup/step", {"step": name, "how": how, "seconds": seconds, **extra})


def test_reopening_lands_on_the_first_step_not_finished(app):
    api = Api(app)
    assert api.get("setup")[1]["resume"] == "you"
    assert step(api, "you", "next")[1]["resume"] == "computer"
    assert step(api, "computer", "next")[1]["resume"] == "brain"
    # no AI that answers yet: Next goes on, but the step stays open and setup comes back to it
    code, v = step(api, "brain", "next")
    assert code == 200 and v["steps"]["brain"]["status"] == "open" and v["resume"] == "brain"
    # going back (or closing the page) leaves a step as it was, and counts the time
    step(api, "you", "leave", seconds=40)
    v = api.get("setup")[1]
    you = v["steps"]["you"]
    assert you["status"] == "done" and you["seconds"] == 45 and you["visits"] == 2
    # an AI that answers: the step is finished, and the page lands on the next one not done
    brain = {"main": "custom", "key": "k" * 12, "base_url": "http://127.0.0.1:9/v1", "models": {"medium": "m"}}
    api.post("brain", brain)
    assert setupsteps.finished(app, "brain") is True
    v = step(api, "brain", "next")[1]
    assert v["steps"]["brain"]["status"] == "done" and v["resume"] == "about"
    # in /api/state too, with the features ticked before the page was closed
    step(api, "features", "leave", chosen=["chat", "reminders", "not-a-feature"])
    st = api.get("state")[1]
    assert st["setup"]["resume"] == "about" and st["setup"]["chosen"] == ["chat", "reminders"]
    # the page asks the server, not the browser, where to land
    js = static("setup.js")
    assert "state.setup.resume" in js and 'localStorage.getItem("kurooto.setup.step"' not in js
    assert 'api("setup/step"' in js and '"pagehide"' in js and "keepalive: true" in js


def test_skip_for_now_except_where_setup_cant_finish_without_it(app, capsys):
    from kurooto import cli, diagnostics

    api = Api(app)
    for required in ("you", "brain", "finish"):
        code, out = step(api, required, "skip")
        assert code == 400 and "can't be skipped" in out["error"], required
    assert step(api, "nowhere", "next")[0] == 400 and step(api, "about", "sideways")[0] == 400
    step(api, "you", "next")
    step(api, "computer", "skip")
    step(api, "about", "next")  # nothing added: Next on an optional step with nothing done skips it
    step(api, "features", "next")
    step(api, "telegram", "next")  # not connected
    v = api.get("setup")[1]
    assert [x["id"] for x in v["left"]] == ["computer", "about", "telegram"]
    assert v["left"][0]["link"] == "/setup#computer"
    # all the rest finished or skipped: reopening lands on the first one not finished, then the first skipped
    assert v["resume"] == "brain"
    # doctor: notes (never problems), each with the way back
    rows = [r for r in diagnostics.checks(app, health=False, net=False) if r[0].startswith("setup: ")]
    assert [r[1] for r in rows] == [None, None, None]
    assert any("kurooto setup telegram" in r[2] for r in rows)
    # and the command opens that step, refusing one that doesn't exist
    assert cli.main(["setup", "fax"]) == 2 and "Not a setup step" in capsys.readouterr().err
    # the setup page has the button on those steps only; the dashboard lists them with links back
    html = static("setup.html")
    for sid in ("computer", "about", "features", "telegram"):
        sec = html.split(f'<section data-step="{sid}">')[1].split("</section>")[0]
        assert "data-skip" in sec, sid
    for sid in ("you", "brain", "finish"):
        sec = html.split(f'<section data-step="{sid}">')[1].split("</section>")[0]
        assert "data-skip" not in sec, sid
    home = static("home.js")
    assert "Finish setting up" in home and 'api("setup")' in home and "setupBlock()" in home


def test_a_skipped_step_done_later_leaves_the_list(env):
    api = Api(env.app)  # Telegram is paired here
    env.app.settings.set("setup.channel", "telegram")
    step(api, "telegram", "skip")  # skipping something already done finishes it
    assert api.get("setup")[1]["steps"]["telegram"]["status"] == "done"
    path = env.app.paths.state / "setup.json"
    data = json.loads(path.read_text())
    data["steps"]["telegram"]["status"] = "skipped"  # skipped before Telegram was paired on the dashboard
    path.write_text(json.dumps(data))
    assert not api.get("setup")[1]["left"]
    step(api, "about", "skip")
    assert [x["id"] for x in api.get("setup")[1]["left"]] == ["about"]
    env.app.about.add("ChatGPT", "I study maths and like long walks. " * 20)
    assert not api.get("setup")[1]["left"]


def test_the_bundle_has_each_steps_time_and_nothing_typed(env):
    from kurooto import diagnostics

    api = Api(env.app)
    env.app.settings.set("you.name", "Samira")
    step(api, "you", "next", seconds=30)
    step(api, "computer", "next", seconds=12.4)
    step(api, "brain", "next", seconds=99999)  # left open overnight: one visit counts an hour at most
    step(api, "about", "skip", seconds=8)
    api.post("setup/done", {})
    dest, names = diagnostics.bundle(env.app)
    assert "setup.json" in names
    with zipfile.ZipFile(dest) as z:
        got = json.loads(z.read("setup.json"))
        assert "setup.json" in z.read("README.txt").decode()
    rows = {r["step"]: r for r in got["steps"]}
    assert got["setup_done"] is True and list(rows) == list(setupsteps.STEPS)
    assert rows["you"] == {"step": "you", "status": "done", "seconds": 30, "visits": 1}
    assert rows["computer"]["seconds"] == 12.4 and rows["brain"]["seconds"] == setupsteps.MAX_VISIT
    assert rows["brain"]["status"] == "open" and rows["about"]["status"] == "skipped"
    assert rows["finish"]["status"] == "done" and rows["telegram"]["status"] == "done"  # paired here
    assert rows["features"]["status"] == "skipped"  # never opened: Finish counts it as skipped
    assert "Samira" not in json.dumps(got)


def test_the_daily_message_limit_is_said_on_the_features_step(app):
    api = Api(app)
    st = api.get("state")[1]
    assert st["calm"] == {"on": True, "messages": 6, "evening_at": "20:00"}
    assert api.post("settings", {"key": "notify.calm.messages", "value": 4})[1]["ok"]
    assert app.settings.get("notify.calm.messages") == 4
    html, js = static("setup.html"), static("setup.js")
    feat = html.split('<section data-step="features">')[1].split("</section>")[0]
    assert 'id="calm-messages"' in feat and 'type="number"' in feat
    assert "Kurooto sends at most ${n} message" in js and "the rest wait for one " in js
    assert "Your own reminders, alarms and approvals always come." in js
    assert '"notify.calm.messages"' in js
