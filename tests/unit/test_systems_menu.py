"""SYSTEMS (0.5.21): a cell's menu acts through the API. GET cell says which actions a feature has; POST cell/sync
syncs that feature alone in the background (its end is the event sync_one, on the feature's cell); POST cell/quiet
puts what it sends by itself on Calm's stop list, with an undo (POST calm/undo); GET events carries each event's cell,
as the live ones do."""

import time
from importlib import resources

from kurooto.web.api import Api

STATIC = resources.files("kurooto.web") / "static"


def _on(app, *ids):
    app.settings.set("modules.enabled", [*(app.settings.get("modules.enabled") or []), *ids])


def test_a_cells_menu_knows_what_its_feature_can_do(env):
    app = env.app
    _on(app, "calendar", "checkins")
    api = Api(app)
    assert api.get("cell", {"id": "nope"})[0] == 404
    code, cal = api.get("cell", {"id": "calendar"})
    assert code == 200 and cal["on"] is True and cal["sync"] is True
    chk = api.get("cell", {"id": "checkins"})[1]
    assert chk["sync"] is False and chk["quiet"] is True
    off = api.get("cell", {"id": "backups"})[1]
    assert off["on"] is False and off["sync"] is False and off["quiet"] is False


def test_sync_now_runs_that_feature_alone_and_says_so_on_its_cell(env, monkeypatch):
    app = env.app
    _on(app, "calendar")
    monkeypatch.setattr(app.modules["calendar"], "refresh", lambda *a, **k: 3)
    api = Api(app)
    assert api.post("cell/sync", {"id": "checkins"})[1] == {"ok": False, "message": "That feature has nothing to sync."}
    code, r = api.post("cell/sync", {"id": "calendar"})
    assert code == 200 and r == {"ok": True, "message": "Syncing Calendar."}
    for _ in range(100):
        done = [e for e in app.events.tail(20) if e["kind"] == "sync_one"]
        if done:
            break
        time.sleep(0.02)
    assert done and done[-1]["cell"] == "calendar" and done[-1]["ok"] is True and done[-1]["detail"] == "3 events"
    assert any(e["kind"] == "sync_one" and e["cell"] == "calendar" for e in api.get("events")[1]["events"])


def test_quiet_goes_through_calm_and_undo_puts_it_back(env):
    app = env.app
    _on(app, "checkins")
    api = Api(app)
    before = list(app.settings.get("notify.calm.stopped") or [])
    r = api.post("cell/quiet", {"id": "checkins"})[1]
    assert r["ok"] is True and r["undo"] and "stops messaging you" in r["message"]
    assert len(app.settings.get("notify.calm.stopped")) > len(before)
    assert api.post("cell/quiet", {"id": "checkins"})[1] == {"ok": False, "message": "Nothing of it left to quiet."}
    u = api.post("calm/undo", {"id": r["undo"]})[1]
    assert u["ok"] is True and u["message"].startswith("Undone")
    assert list(app.settings.get("notify.calm.stopped") or []) == before
    assert api.post("cell/quiet", {"id": "nope"})[1]["ok"] is False


def test_the_page_has_the_menu_the_list_and_the_living_drawing():
    html = (STATIC / "home.html").read_text(encoding="utf-8")
    js = "".join((STATIC / f).read_text(encoding="utf-8") for f in ("home.js", "views/common.js", "views/systems.js"))
    assert 'id="body-cells"' in html and 'id="body-menu"' in html and "<b>ping</b>" in html  # the ? guide says how
    for part in ("membrane(", "neuron(", "axon(", "synapses(", "meshLayer(", "openMenu(", "closeMenu(", "springs("):
        assert part in js, part
    assert "api(`cell?id=" in js and "api(`cell/${act}`" in js and 'api("calm/undo"' in js
    assert 'matchMedia("(prefers-reduced-motion: reduce)")' in js and 'matchMedia("(hover: hover)")' in js
    assert 'el.classList.toggle("instant", !!byKey)' in js  # a menu opened from the keyboard isn't animated
