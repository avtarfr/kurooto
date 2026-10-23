import json
import os
import time
import urllib.error
import urllib.request

import pytest

from kurooto.app import App
from kurooto.web.live import Graph, Vitals, cell_of
from kurooto.web.server import start


def test_graph_reads_notes_links_and_changes(tmp_path):
    (tmp_path / "topology").mkdir()
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "topology" / "compactness.md").write_text("# Compactness\nsee [[Connectedness]] and [[nope]]\n")
    (tmp_path / "topology" / "connectedness.md").write_text("---\ntitle: Connected sets\n---\nbody\n")
    (tmp_path / ".obsidian" / "skip.md").write_text("# hidden\n")
    g = Graph(tmp_path)
    assert g.scan() is True
    p = g.payload
    assert {n["id"] for n in p["nodes"]} == {"topology/compactness", "topology/connectedness"}
    assert p["links"] == [("topology/compactness", "topology/connectedness")]
    assert {n["title"] for n in p["nodes"]} == {"Compactness", "Connected sets"}
    assert g.scan() is False  # nothing changed
    time.sleep(0.01)
    (tmp_path / "topology" / "connectedness.md").write_text("# Connectedness\nnew\n")
    os.utime(tmp_path / "topology" / "connectedness.md", (time.time() + 5, time.time() + 5))
    assert g.scan() is True and g.payload["changed"] == ["topology/connectedness"]


def test_events_map_to_cells():
    assert cell_of("reminder_fired") == "reminders" and cell_of("job_done") == "chat" and cell_of("weird") == "core"


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    app = App()
    srv = start(app, port=18800)
    yield app, srv
    srv.stop()
    app.close()


def call(srv, path, body=None, token=True):
    h = {"Content-Type": "application/json", **({"X-Kurooto": srv.token} if token else {})}
    req = urllib.request.Request(
        srv.url.rstrip("/") + path,
        data=None if body is None else json.dumps(body).encode(),
        headers=h,
        method="GET" if body is None else "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None


def test_snapshot_shape(web):
    app, srv = web
    app.settings.set("modules.enabled", ["telegram"])
    app.events.emit("message_in")
    snap = Vitals(app).snapshot()
    assert snap["t"] == "body" and 0 <= snap["sys"]["cpu"] <= 1 and snap["sys"]["cores"]
    tg = next(c for c in snap["cells"] if c["id"] == "telegram")
    assert tg["on"] and tg["events"] == 1


def test_settings_notes_and_stream(web):
    app, srv = web
    st = call(srv, "/api/settings")[1]
    assert any(s["section"] == "you" for s in st["sections"])
    assert call(srv, "/api/settings", {"key": "you.name", "value": "Riya"}) == (200, {"ok": True})
    assert app.settings.get("you.name") == "Riya"
    assert call(srv, "/api/settings", {"key": "notify.desktop", "value": "yes"})[0] == 400  # wrong type
    assert call(srv, "/api/settings", {"key": "telegram.chat_id", "value": 1})[0] == 400  # not editable here
    (app.workspace / "a.md").write_text("---\ntitle: x\n---\nhello there\n")
    assert call(srv, "/api/note?id=a")[1]["text"] == "hello there\n"
    assert call(srv, "/api/note?id=../../etc/passwd")[0] == 404
    assert call(srv, "/api/stream", token=False)[0] == 401
    with urllib.request.urlopen(srv.url + f"api/stream?t={srv.token}", timeout=20) as r:
        first = r.readline().decode()
    assert first.startswith("data: ") and '"t":"graph"' in first


def test_every_feature_is_listed_in_the_wizard_and_dashboard(web):
    from kurooto.modules.catalog import CATALOG
    from kurooto.web.api import MODULE_ORDER

    assert sorted(MODULE_ORDER) == sorted(m.id for m in CATALOG)


def test_the_settings_page_shows_every_core_section_you_can_set_and_never_pairing(env):
    from kurooto.web.api import Api

    api = Api(env.app)
    env.on("subjects")
    secs = {s["section"]: s for s in api._settings()["sections"]}
    for key in (
        "quota.background_pct",
        "health.when",
        "jobs.stuck_min",
        "sources.budget",
        "agents.export",
        "hardware.force_profile",
        "web.port",
        "brain.models",
        "brain.base_urls",
        "subjects.timetable",
    ):
        sec, k = key.split(".")
        assert k in secs[sec]["values"], key
    assert "modules" not in secs and secs["web"]["title"] == "Dashboard"
    assert "chat_id" not in secs["telegram"]["values"]
    assert api.post("settings", {"key": "jobs.stuck_min", "value": 15}) == (200, {"ok": True})
    assert api.post("settings", {"key": "telegram.chat_id", "value": 1})[0] == 400  # on, but set by pairing
    assert api.post("settings", {"key": "modules.enabled", "value": []})[0] == 400
    assert api.post("settings", {"key": "you", "value": {}})[0] == 400  # one setting at a time, not a section
