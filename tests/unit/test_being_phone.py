"""0.8.10: the being on the phone (Views → Being). The computer's side: the "being" block in each Systems copy
(calls/views.py being_snapshot) in the dashboard's own shapes, sealed like the rest, never what a note says, its
settings without tooltips and only when they changed or a phone starts watching, and its switch (calls.views_being).
The page's side, as far as it can be read without a phone: being.js keeps the dashboard as it was (every phone hook
behind PH), being-phone.js answers being.js's api from the copy and asks the computer only the four sealed requests,
and the app serves exactly the files being.html loads. The phone's own handling of the requests (sealed out, opened
back, refused plainly) is android/test/BeingTest.java."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import kurooto
from kurooto.modules.calls import views
from tests.unit.test_phone import phone  # noqa: F401 (the shared fixture)
from tests.unit.test_views import BODY_TEXT, Connector, v  # noqa: F401 (the views' fixture: an Android phone's key, notes)

STATIC = Path(kurooto.__file__).parent / "web" / "static"
ANDROID = Path(kurooto.__file__).parents[2] / "android"


def test_the_switch_is_on_by_default_and_documented(v):  # noqa: F811
    assert v.app.settings.get("calls.views_being") is True
    guide = (Path(kurooto.__file__).parents[2] / "docs" / "SETTINGS_GUIDE.md").read_text(encoding="utf-8")
    assert "calls.views_being" in guide
    assert "being" in v.views.systems_snapshot()
    v.app.settings.set("calls.views_being", False)  # off: Systems as it was, nothing more
    assert "being" not in v.views.systems_snapshot()


def test_the_being_block_has_what_being_js_reads_in_the_dashboards_shapes(v):  # noqa: F811
    v.on("deadlines")
    v.app.events.emit("job_done", title="secret words of a request")
    v.app.events.emit("senses_phone", sensor="phone:motion", value=3.5, extra="not this")
    b = v.views.systems_snapshot()["being"]
    assert {"cells", "jobs", "schedule", "calls", "link", "sys", "events", "voice", "look", "settings", "brain"} <= set(
        b
    )
    cells = {c["id"]: c for c in b["cells"]}
    assert cells["deadlines"]["on"] is True and any(not c["on"] for c in b["cells"])  # off ones too: dim lights
    assert set(b["cells"][0]) == {"id", "title", "on", "act", "events"}
    assert all(set(j) == {"status", "title"} for j in b["jobs"]) and all(
        set(s) == {"when", "what"} for s in b["schedule"]
    )
    assert b["link"] in ({"off": True},) or set(b["link"]) == {"connected", "beat"}
    assert {"cpu", "cores", "mem", "mem_used", "mem_total", "disks", "temps", "load"} <= set(
        b["sys"]
    )  # the coil's bars
    ev = {e["kind"]: e for e in b["events"]}
    assert set(ev["job_done"]) == {"kind", "ts"}  # an event's kind and time only: its words stay here
    assert ev["senses_phone"] == {
        "kind": "senses_phone",
        "ts": ev["senses_phone"]["ts"],
        "sensor": "phone:motion",
        "value": 3.5,
    }
    assert b["look"] == {"theme": "void", "hints": True, "rest": True}
    secs = b["settings"]["sections"]
    assert secs and all("tips" not in s and {"section", "title", "values"} <= set(s) for s in secs)
    comps = [c for i in b["brain"]["islands"] for c in i["comps"]]
    assert comps and all(
        len(c) == 7 and c[6] == "" for c in comps
    )  # no tooltips; the switch key where being.js reads it


def test_never_what_a_note_says(v):  # noqa: F811
    v.app.settings.set("calls.views", True)
    snap = v.views.systems_snapshot()
    assert BODY_TEXT not in json.dumps(snap)
    assert "secret words" not in json.dumps(snap["being"]["events"])


def test_settings_go_when_changed_when_a_phone_starts_watching_or_now_and_then(v, monkeypatch):  # noqa: F811
    first = v.views.systems_snapshot()["being"]
    again = v.views.systems_snapshot()["being"]
    assert "settings" in first and "settings" not in again and again["settings_digest"] == first["settings_digest"]
    v.app.settings.set("look.being_hints", False)  # a change goes at once
    changed = v.views.systems_snapshot()["being"]
    assert "settings" in changed or changed["look"]["hints"] is False
    v.app.settings.set("calls.views_notes", 4000)
    changed = v.views.systems_snapshot()["being"]
    assert "settings" in changed and changed["settings_digest"] != first["settings_digest"]
    assert "settings" not in v.views.systems_snapshot()["being"]
    v.app.settings.set("calls.views", True)
    c = Connector(v.line)
    v.calls.connector = c
    v.views.looping = True  # (a stretch of watching is going on: no copies sent here)
    try:
        v.views.until = time.time() + 30
        v.views.watchers = {"abcd1234"}
        v.views.watch({"device": "ffff0000"})  # a new phone joins it
        assert "settings" in v.views.systems_snapshot()["being"]
        v.views.watch({"device": "ffff0000"})  # the same phone again: nothing more
        assert "settings" not in v.views.systems_snapshot()["being"]
    finally:
        c.loop.call_soon_threadsafe(c.loop.stop)
    monkeypatch.setattr(views, "SETTINGS_S", 0)  # and now and then anyway
    assert "settings" in v.views.systems_snapshot()["being"]


def test_voice_mute_and_state_for_the_ear(v):  # noqa: F811
    b = v.views.systems_snapshot()["being"]
    if b["voice"] is not None:
        assert {"on", "state", "listening", "muted", "portal", "speak"} <= set(b["voice"])


# ------------------------------------------------------------------------------------------- the page and the app
def test_being_js_keeps_the_dashboard_as_it_was():
    js = (STATIC / "being.js").read_text(encoding="utf-8")
    assert (
        'const PH = opts.mode === "phone" && window.beingPhone ? window.beingPhone : null, UI = PH ? PH.ui : null;'
        in js
    )
    # the dashboard's own input is untouched, only skipped on the phone
    for ev in ("pointerdown", "pointermove", "pointerup", "wheel"):
        assert f'if (!PH) gl.addEventListener("{ev}"' in js
    # every other use of the phone's part is behind PH or UI
    for line in js.splitlines():
        for m in re.finditer(r"\b(PH|UI)\.\w+", line):
            head = line[: m.start()]
            assert re.search(r"\b(PH|UI)\s*(\?|&&|\)|$)|if \((PH|UI)\)|\(UI\) \? |UI \? |PH \? ", head + " "), (
                line.strip()[:120]
            )
    assert "beingPhone" not in (STATIC / "home.js").read_text(encoding="utf-8")  # the dashboard never loads it


def test_the_phone_page_asks_only_the_four_sealed_requests_and_answers_the_rest_from_the_copy():
    js = (STATIC / "being-phone.js").read_text(encoding="utf-8")
    asked = set(re.findall(r'ask\("([a-z.]+)"', js))
    assert asked == {"settings.set", "module", "note.get", "voice.mute"}
    rules = (ANDROID / "src/io/github/avtarfr/kurooto/BeingRules.java").read_text(encoding="utf-8")
    assert all(f'"{op}"' in rules for op in asked)  # the app sends these and nothing else
    assert "fetch(" in js and not re.search(r"fetch\(\s*[`\"']https?:", js)  # only the app's own addresses
    for path in ("settings", "brain3d", "voice", "note", "modules/enable", "modules/disable", "voice/mute"):
        assert f'"{path}"' in js
    # chat.py's ops: the computer answers these (the chat-core part) with the dashboard's own validation
    assert "Your computer is off: try again when it's on." in js


def test_the_app_serves_exactly_what_being_html_loads():
    html = (STATIC / "views" / "being.html").read_text(encoding="utf-8")
    assert "connect-src 'self'" in html and "script-src 'self'" in html and "unsafe-eval" not in html
    srcs = re.findall(r'<script src="([^"]+)"', html)
    pane = (ANDROID / "src/io/github/avtarfr/kurooto/ViewsPane.java").read_text(encoding="utf-8")
    pat = re.search(r"Pattern ASSET = Pattern.compile\((.*?)\);", pane, re.S).group(1)
    regex = "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', pat)).replace("\\\\", "\\")
    loaded = [s if s.startswith("/") else "/views/" + s for s in srcs] + [
        "/static/body/anatomy.bin",
        "/static/body/cerebrum.vol",
        "/static/being-layout.js",
        "/views/being.css",
    ]
    for path in loaded:
        assert re.fullmatch(regex, path), path
        f = (
            STATIC / path.removeprefix("/static/").removeprefix("/")
            if path.startswith("/static/")
            else STATIC / path.lstrip("/")
        )
        assert f.is_file(), path
    for bad in (
        "/static/home.js",
        "/static/body/../being.js",
        "/views/../home.js",
        "/static/vendor/three/x.min.js.map",
    ):
        assert not re.fullmatch(regex, bad), bad
    gradle = (ANDROID / "build.gradle.kts").read_text(encoding="utf-8")
    for f in ("being.js", "being-layout.js", "being-phone.js", "body/anatomy.bin", "body/cerebrum.vol", "vendor/three"):
        assert f in gradle, f


def test_no_code_is_hidden_in_a_line_comment():
    # 0.8.10 review: a "// phone: ..." note put in the middle of a line once commented out the dashboard's own drawing
    # (tag's lead lines, then a ReferenceError on every frame: the dashboard's being stopped at mount). A line comment
    # must hold words, never statements.
    code = re.compile(r";\s*[A-Za-z_$][\w$.]*\s*(\(|=)")
    for name in ("being.js", "being-phone.js", "being-layout.js"):
        for i, line in enumerate((STATIC / name).read_text(encoding="utf-8").splitlines(), 1):
            m = re.search(r"(?<![:\"'`\\])//(.*)$", line)
            assert not (m and code.search(m.group(1))), f"{name}:{i}: {line.strip()[:120]}"
    js = (STATIC / "being.js").read_text(encoding="utf-8")
    for statement in (  # the dashboard's lead lines and the lanes' words, each starting its own code
        "\n    const lx = x + dx, ly = y + dy; c2.save();",
        '/* phone: edge to edge */ c.font = "600 10px Inter,sans-serif"; c.fillStyle = P.mute; c.fillText(lab,',
    ):
        assert statement in js, statement


def test_the_brain_choice_uses_the_brain_consoles_own_page_and_is_watched():
    # the brain-console part writes views/brain.html and brainconsole.js (KurootoView.take, as Systems); the Brain is
    # sent only while a phone watches it (/view/watch?kind=brain)
    pane = (ANDROID / "src/io/github/avtarfr/kurooto/ViewsPane.java").read_text(encoding="utf-8")
    views_java = (ANDROID / "src/io/github/avtarfr/kurooto/Views.java").read_text(encoding="utf-8")
    assert '"being".equals(mode) ? "KurootoBeing" : "KurootoView"' in pane
    assert 'Views.watch(a, brain ? "brain" : "systems")' in pane and "(live || brain)" in pane
    assert '"?kind=brain"' in views_java
    assert not (STATIC / "views" / "brain-phone.js").exists()


def test_the_organ_pages_call_only_what_the_page_offers_and_have_a_switch():
    # 0.8.10: Views → Brain, Heart, Senses, Memory (OrganViews.kt): one WebView, the organ switched on the page
    js = (STATIC / "being-phone.js").read_text(encoding="utf-8")
    offered = set(re.search(r"window\.KurootoBeing = \{([^}]*)\}", js).group(1).replace(" ", "").split(","))
    assert {"take", "back", "only", "organState", "pick", "setting", "feature", "mode", "inset"} <= offered
    src = ANDROID / "src/io/github/avtarfr/kurooto"
    pane = (src / "ViewsPane.java").read_text(encoding="utf-8")
    called = set(re.findall(r"KurootoBeing\.(\w+)\(", pane))
    assert called and called <= offered, called - offered
    assert 'js("KurootoBeing.only(" + JSONObject.quote(o) + ")");' in pane  # switched, never loaded again
    assert 'u.getQueryParameter("rev")' in pane and "rev=${encodeURIComponent(rev)}" in js  # the list changed: read it
    assert "only: PV.only || undefined, still: PV.still" in js  # the page mounts as an organ page
    # the switch (off: the whole being as before), and its guide entry
    prefs = (src / "Prefs.java").read_text(encoding="utf-8")
    assert 'getBoolean("viewsOrgans", true)' in prefs
    tab = (src / "ViewsTab.kt").read_text(encoding="utf-8")
    assert "if (remember { Prefs.viewsOrgans(a) }) OrganViews(a, ui, room) else WholeViews(a, ui, room)" in tab
    settings = (src / "SettingsPane.kt").read_text(encoding="utf-8")
    assert 'help = "app.viewsOrgans"' in settings
    guide = (Path(kurooto.__file__).parents[2] / "tools" / "settings_guide" / "26-phone-app.toml").read_text(
        encoding="utf-8"
    )
    assert '[s."app.viewsOrgans"]' in guide and '[s."app.viewOrgan"]' in guide
    organs = (src / "OrganViews.kt").read_text(encoding="utf-8")
    for page in ("brain", "heart", "senses", "memory"):
        assert f'"{page}" to "' in organs  # each a page of its own
    for more in ("systems", "notes", "brain"):
        assert f'"{more}" to "' in organs  # and the rest of Views behind More
    assert "LocalReducedMotion.current" in organs and ".organs(reduced)" in organs
