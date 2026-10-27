"""The settings guide is written from the code and its own source (tools/settings_guide/*.toml): a setting added or
changed without its guide entry, or without regenerating the guide, fails here. Every setting has an entry (what it
does, values and default, when to change it, what it costs or sends, what it depends on) and a tooltip written for a
person, not the comment beside it in the code."""

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "gen_settings_guide.py"
pytestmark = pytest.mark.skipif(not TOOL.exists(), reason="not in a source checkout")


def load_gen():
    spec = importlib.util.spec_from_file_location("gen_settings_guide", TOOL)
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    return gen


@pytest.fixture(scope="module")
def gen():
    return load_gen()


def test_the_settings_guide_is_up_to_date():
    r = subprocess.run([sys.executable, str(TOOL), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_the_guide_documents_only_settings_that_exist(tmp_path, monkeypatch):
    """Settings come from register_defaults alone: a class attribute `defaults` was never read by Kurooto, so the
    guide mustn't list one (it used to)."""
    gen = load_gen()
    (tmp_path / "m.py").write_text('class M:\n    id = "m"\n    defaults = {"x": 1}  # never registered\n')
    monkeypatch.setattr(gen, "SRC", tmp_path)
    assert gen.collect() == []


def test_every_setting_has_an_entry_and_a_tooltip(gen):
    _, entries, problems = gen.build()
    assert not problems, problems
    for key, _v, _why in gen.collect():
        e = entries[key]
        for field in ("tip", "values", "default", "when", "cost", "needs"):
            assert e[field].strip(), f"{key} has no {field}"


def test_a_setting_without_an_entry_fails(tmp_path, monkeypatch):
    gen = load_gen()
    (tmp_path / "m.py").write_text('register_defaults("zz", {"knob": 1})  # a new setting\n')
    monkeypatch.setattr(gen, "SRC", tmp_path)
    _, _, problems = gen.build()
    assert any(p.startswith("zz.knob has no entry") for p in problems), problems
    assert gen.main() == 1  # and the tool says so instead of writing a guide


def test_an_entry_for_a_setting_that_went_fails(tmp_path, monkeypatch):
    gen = load_gen()
    src = tmp_path / "src"
    src.mkdir()
    (src / "m.py").write_text('register_defaults("zz", {"knob": 1})  # a setting\n')
    (tmp_path / "01-zz.toml").write_text(
        'title = "Z"\ncost = "c"\nneeds = "n"\n'
        '[s."zz.knob"]\ntip = "t"\nwhen = "w"\n[s."zz.gone"]\ntip = "t"\nwhen = "w"\n'
    )
    monkeypatch.setattr(gen, "SRC", src)
    monkeypatch.setattr(gen, "GUIDE_SRC", tmp_path)
    monkeypatch.setattr(gen, "_choices", dict)
    _, entries, problems = gen.build()
    assert "zz.knob" in entries
    assert any(p.startswith("zz.gone") for p in problems), problems


def test_tooltips_are_written_for_a_person(gen):
    """Not the code comment copied, one line, short enough for a tooltip, and no Python in it (None, True)."""
    _, entries, _ = gen.build()
    comments = {k: why for k, _v, why in gen.collect()}

    def plain(t: str) -> str:
        return t.rstrip(".").lower()

    same = [k for k, e in entries.items() if comments.get(k) and plain(e["tip"]) == plain(comments[k])]
    assert not same, f"tooltips copied from the code's comment: {same}"
    for key, e in entries.items():
        tip = e["tip"]
        assert "\n" not in tip and len(tip) <= 140, key
        assert tip.endswith((".", "?", ")")), f"{key}: a tooltip is a sentence: {tip}"
        for field in ("tip", "what", "values", "when", "cost", "needs"):
            assert not re.search(r"\b(None|True|False)\b", e[field]), f"{key}.{field} speaks Python: {e[field]}"


def test_the_dashboards_tooltips_cover_every_setting_and_every_box(gen):
    help_ = json.loads((ROOT / "src" / "kurooto" / "data" / "settings-help.json").read_text(encoding="utf-8"))
    assert {k for k, _v, _w in gen.collect()} <= set(help_)
    nested = {".".join(k.split(".")[:2]) for k, _v, _w in gen.collect() if k.count(".") >= 2}
    assert nested <= set(help_), f"boxes of settings with no tooltip: {sorted(nested - set(help_))}"
    assert not any(k.startswith("app.") for k in help_)  # the phone app's own: only in its asset


def test_every_entry_is_on_the_wiki_page_with_its_link(gen):
    _, entries, _ = gen.build()
    wiki = (ROOT / "docs" / "wiki" / "user" / "settings-guide.md").read_text(encoding="utf-8")
    anchors = [e["anchor"] for e in entries.values()]
    assert len(set(anchors)) == len(anchors)
    for key, e in entries.items():
        assert f"### `{key}`" in wiki, key
        assert gen.slug(f"`{key}`") == e["anchor"]
    table = (ROOT / "docs" / "SETTINGS_GUIDE.md").read_text(encoding="utf-8")
    assert "(wiki/user/settings-guide.md#brainmain)" in table
    index = (ROOT / "docs" / "wiki" / "user" / "index.md").read_text(encoding="utf-8")
    assert "(settings-guide.md)" in index  # the site lists it with the wiki's pages


def test_the_app_and_the_dashboard_get_the_same_entries(gen):
    app = json.loads((ROOT / "android" / "assets" / "settings-help.json").read_text(encoding="utf-8"))
    js = (ROOT / "src" / "kurooto" / "web" / "static" / "settings-guide.js").read_text(encoding="utf-8")
    dash = json.loads(js.split("window.KUROOTO_SETTINGS_GUIDE = ", 1)[1])
    assert app == dash
    assert app["page"].endswith("/wiki/user/settings-guide.html")
    e = app["settings"]["brain.main"]
    assert e["tip"] and e["when"] and e["anchor"] == "brainmain"
    assert app["parents"]["availability.night"]["children"]


def test_the_phone_apps_own_settings_are_real_keys(gen):
    """app.<key>: a key Prefs, Senses or Places keeps on the phone (so the Settings pane's long-press finds it)."""
    _, entries, _ = gen.build()
    src = ROOT / "android" / "src" / "io" / "github" / "avtarfr" / "kurooto"
    prefs = (src / "Prefs.java").read_text(encoding="utf-8")
    senses = (src / "SensesRules.java").read_text(encoding="utf-8")
    places = (src / "Places.java").read_text(encoding="utf-8")
    phone = [k for k in entries if k.startswith("app.")]
    assert phone
    for key in phone:
        rest = key[4:]
        if rest.startswith("senses."):
            assert f'"{rest[7:]}"' in senses, key
        elif rest.startswith("places."):
            assert f'"{rest[7:]}"' in places, key
        else:
            assert f'"{rest}"' in prefs, key
