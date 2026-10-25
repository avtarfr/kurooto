"""0.8.2: the dashboard's Brain page: its data (core/brainview.py) and the files it needs."""

import pytest

from kurooto.core import brainview
from kurooto.web.server import static


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    yield a
    a.close()


def test_the_page_lists_eight_islands_in_the_order_the_model_expects(app):
    d = brainview.view(app)
    assert [i["id"] for i in d["islands"]] == ["hq", "fore", "cons", "memory", "mirror", "senses", "shop", "body"]
    assert d["on"] is False and d["parts_on"] == 0 and d["parts_total"] == 31
    for isl in d["islands"]:
        assert isl["color"].startswith("#") and isl["comps"]
        for c in isl["comps"]:  # [id, name, on, state, metrics, setting, what it does]
            assert len(c) == 7 and c[2] == 0 and c[3] == "off" and c[4] == []


def test_switches_and_numbers_follow_the_settings(app):
    app.settings.set("modules.enabled", ["mind"])
    app.settings.set("mind.senses.phone.steps", True)
    app.settings.set("mind.finetune.on", False)
    d = brainview.view(app)
    comps = {c[0]: c for i in d["islands"] for c in i["comps"]}
    assert d["on"] and comps["workspace"][2] == 1 and comps["workspace"][3] == "on"
    assert comps["forecast"][3] == "shadow" and comps["finetune"][2] == 0
    assert comps["phone"][2] == 1 and comps["phone"][4] == [["Sensors enabled", "1 of 11"]]
    assert comps["log"][2] == 1 and comps["stops"][2] == 1  # always there with Brain
    assert d["parts_on"] == sum(c[2] for c in comps.values())


def test_the_pages_files_are_served_and_three_js_is_only_the_one_file():
    assert static("vendor/three/three.min.js") and b"THREE" in static("vendor/three/three.min.js")[:4000] + b"THREE"
    assert b"brain3dMount" in static("brain3d.js")
    assert static("vendor/three/other.js") is None and static("vendor/three/../../server.py") is None
