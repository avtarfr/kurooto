"""0.8.9: the being (static/being.js), the dashboard's board drawn as one body, and the talk box."""

import json
import re
import struct

import pytest

from kurooto.core import brainview
from kurooto.web.server import TYPES, static


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    yield a
    a.close()


def _ids(js: str, pattern: str) -> set[str]:
    out = set()
    for m in re.finditer(pattern, js):
        out |= set(re.findall(r'"([a-z_]+)"', m.group(1)))
    return out


def test_its_files_are_served_and_nothing_beside_them():
    for name in (
        "being.js",
        "vendor/three/three.min.js",
        "vendor/three/UnrealBloomPass.js",
        "vendor/three/CopyShader.js",
    ):
        assert static(name), name
    for name in ("body/anatomy.bin", "body/cerebrum.vol"):
        assert static(name), name
        assert TYPES["." + name.rsplit(".", 1)[1]] == "application/octet-stream"
    for name in ("body/other.bin", "body/../being.js", "vendor/three/../../server.py", "vendor/three/x.min.js.map"):
        assert static(name) is None, name


def test_the_anatomy_files_are_what_being_js_reads():
    b = static("body/anatomy.bin")
    assert b[:4] == b"KBM1"
    (hl,) = struct.unpack_from("<I", b, 4)
    head = json.loads(b[8 : 8 + hl])
    names = {m["name"] for m in head["meshes"]}
    assert {"grey", "cerebellum", "brainstem", "heart"} <= names  # the meshes being.js draws
    for m in head["meshes"]:  # every mesh lies inside the file
        assert 8 + hl + m["off"] + m["verts"] * 6 + m["tris"] * 12 <= len(b) + 8
    v = static("body/cerebrum.vol")
    assert v[:4] == b"KBV1"
    (vl,) = struct.unpack_from("<I", v, 4)
    vh = json.loads(v[8 : 8 + vl])
    nx, ny, nz = vh["shape"]
    assert len(v) - 8 - vl == nx * ny * nz and {"lo", "step", "range", "white"} <= set(vh)


def test_the_board_settings():
    import kurooto.web.server  # noqa: F401 (registers the look defaults)
    from kurooto.core.choices import CHOICES
    from kurooto.core.config import _DEFAULTS

    look = _DEFAULTS["look"]
    assert look["board"] == "being" and look["being_theme"] == "void" and look["talk_box"] is True
    assert [c[0] for c in CHOICES["look.board"]] == ["being", "three", "classic"]
    assert [c[0] for c in CHOICES["look.being_theme"]] == ["void", "theme"]


def test_every_feature_has_a_home_on_the_body(app):
    js = static("being.js").decode()
    placed = _ids(js, r"feats: \[([^\]]*)\]") | _ids(js, r"const MEMORY_FEATS = \[([^\]]*)\]")
    assert not set(app.modules) - placed  # a new feature needs a place (homeOf would put it on the heart)


def test_the_brain_parts_it_names_exist():
    js = static("being.js").decode()
    named = _ids(js, r"parts: \[([^\]]*)\]")
    real = {p[0] for _i, _n, _t, parts in brainview.ISLANDS for p in parts}
    assert named and named <= real
    assert real - named == set()  # every Brain part sits in some region or sense


def test_it_talks_to_the_real_api():
    js = static("being.js").decode()
    # the shapes web/api.py takes: settings {key, value}; enable {ids}; disable {id}; voice/mute {} flips it
    assert 'api("settings", { key: b.dataset.key, value: on })' in js
    assert 'api(on ? "modules/disable" : "modules/enable", on ? { id } : { ids: [id] })' in js
    assert 'api("voice/mute", {})' in js and "note?id=" in js and 'api("open-note"' in js
    assert "document.hidden || !host.isConnected" in js  # out of sight it stops drawing
    assert "now - lastHover < 40" in js  # hovering never raycasts the full meshes
    assert 'new Worker("/static/being-layout.js")' in js  # the notes' layout runs off the page's thread
    assert "l[2] ? .5 : 1" in js  # every link counts, as on the NOTES map; a via link pulls half as hard


def test_the_dashboard_mounts_it_and_has_the_talk_box():
    home = static("home.js").decode()
    html = static("home.html").decode()
    assert 'id="pane-being"' in html and 'id="talk"' in html and 'id="talk-input"' in html
    assert 'const beingBoard = () => DENSE && BOARD === "being" && !STUDY && !MAX;' in home
    passes = ("CopyShader", "LuminosityHighPassShader", "EffectComposer", "RenderPass", "ShaderPass", "UnrealBloomPass")
    assert all(f'"{f}"' in home and static(f"vendor/three/{f}.js") for f in passes)
    assert all(f"BEING.{f}(m)" in home for f in ("update", "event", "graph", "voice"))
    # the chat tab and the talk box send the same way (POST /api/say), one function
    assert home.count('api("say", { text })') == 1
    assert "askKurooto(text, chatAdd)" in home and "askKurooto(text, talkAdd)" in home
    assert 'key === "look.talk_box"' in home and 'e.code === "KeyK"' in home


def test_the_preview_tool_fills_the_page_from_the_live_one():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "dash_preview", Path(__file__).resolve().parents[2] / "tools" / "dash_preview.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    live = (
        '<html data-palette="rose"><head><meta name="kurooto-token" content="TOK123">'
        '<style id="kurooto-palette">:root{}</style><script src="/static/palette.js" defer></script></head>'
        '<body data-layout="dense" data-study="" data-design="new"></body></html>'
    )
    html, tok = mod.page(live, "preview")
    assert tok == "TOK123" and 'content="TOK123"' in html and "{{" not in html
    assert 'data-palette="rose"' in html and '<style id="kurooto-palette">' in html and 'id="pane-being"' in html
    with pytest.raises(SystemExit):
        mod.page("<html></html>", "preview")


def test_every_part_can_be_focused_and_the_hints_have_a_switch():
    import kurooto.web.server  # noqa: F401 (registers the look defaults)
    from kurooto.core.config import _DEFAULTS

    js = static("being.js").decode()
    for kind in ("region", "heart", "sense", "hood", "note", "feature"):
        assert f'kind: "{kind}"' in js, kind  # the camera flies to it, it brightens, the rest dims
    assert "if (SUB) back();" in js  # Esc goes up one level
    assert _DEFAULTS["look"]["being_hints"] is True and 'key: "look.being_hints"' in js
    home = static("home.js").decode()
    assert 'key === "look.being_hints"' in home and "hints: BEING_HINTS" in home


def test_the_layout_worker_settles_a_graph(tmp_path):
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        pytest.skip("no node here")
    worker = static("being-layout.js").decode()
    harness = (
        "let out=null;const postMessage=(m)=>{out=m};"
        + worker.replace('"use strict";', "")
        + ";const N=60,hood=new Int32Array(N),p=new Float32Array(N*3);"
        "for(let i=0;i<N;i++){p[i*3]=Math.sin(i*7.1)*.2;p[i*3+1]=Math.cos(i*3.3)*.2;p[i*3+2]=Math.sin(i*1.7)*.2;}"
        "const li=new Int32Array([0,1,2,3]),lw=new Float32Array([1,.5]);"
        "onmessage({data:{p,li,lw,hood,ctr:new Float32Array([0,0,0]),iters:220}});"
        "const d=(a,b)=>Math.hypot(out.p[a*3]-out.p[b*3],out.p[a*3+1]-out.p[b*3+1],out.p[a*3+2]-out.p[b*3+2]);"
        "let u=0;for(let j=4;j<N;j++)u+=d(0,j);"
        "console.log(JSON.stringify({done:out.done,linked:d(0,1),apart:u/(N-4),finite:out.p.every(Number.isFinite)}))"
    )
    f = tmp_path / "h.js"
    f.write_text(harness)
    r = json.loads(subprocess.run([node, str(f)], capture_output=True, text=True, check=True).stdout)
    assert r["done"] and r["finite"] and r["linked"] < r["apart"]


def test_a_selection_leaves_only_its_part_solid_and_the_brain_has_three_views():
    js = static("being.js").decode()
    assert "#ifdef SOLID" in js and "function twin(mesh)" in js  # the selected part's solid twin; the rest is glass
    assert "twin(cortex)" in js and "twin(hm)" in js  # the cortex and the heart keep their selected part whole
    for nm in ("thalamus", "hippocampus", "caudate", "callosum"):
        assert f'"{nm}"' in js  # the deep structures, shown in X-ray and through the glass
    assert '["solid", "cut", "xray"]' in js and 'if (p.organ === "mind") setMode("solid")' in js  # opens solid


def test_organ_pages_draw_one_organ_and_leave_the_dashboard_as_it_was():
    # 0.8.10: the phone app's Views pages (Brain, Heart, Senses, Memory) pass opts.only; the dashboard never does
    js = static("being.js").decode()
    pages = re.search(r"const PAGE_ORGAN = \{([^}]*)\}", js).group(1)
    assert dict(re.findall(r"(\w+): \"(\w+)\"", pages)) == {
        "brain": "mind",
        "heart": "heart",
        "senses": "senses",
        "memory": "memory",
    }
    assert "let ONLY = PAGE_ORGAN[opts.only] || null;" in js and "const OM = !!ONLY, STILL = OM && !!opts.still;" in js
    mount = re.search(r"window\.beingMount\(host, \{([^}]*)\}", static("home.js").decode()).group(1)
    assert "only" not in mount and "still" not in mount  # the dashboard's own mount
    # each place the organ pages differ is behind OM: the panel, empty space, the words over the drawing, back
    assert "function openPanel(html, kind) { if (OM) { PANEL = kind; organDirty(); return; }" in js
    assert "if (OM) organDirty(); else if (PH) PH.sheet(panel, false);" in js
    assert "else if (!OM) { closePanel(); focusOn(null); }" in js  # an organ page never leaves its organ
    assert "if (OM) { /* an organ page: the app shows its name and parts */ } else if (UI) UI.header(" in js
    assert "if (OM) { /* an organ page: no voice lanes */ } else if (UI) UI.lanes(" in js
    assert "goal.d = OM ? ONLY_D[name] : T.d;" in js and "goal.d = OM ? s.d * ONLY_SUB : s.d;" in js
    assert "(STILL ? 1 : Math.min(1, dt * 6))" in js  # Remove animations: the camera jumps
    assert "...(OM ? { only, pick, setting, feature, mode:" in js  # the dashboard's being has none of it
    assert "if (OM) only(opts.only);" in js and "if (OM) OTIMER = setInterval(" in js
    # alone: the other organs and everything between them hidden, and nothing hidden can be picked
    only = js[js.index("function only(page)") :]
    only = only[: only.index("\n  }\n")]
    assert "g.visible = k === o" in only and "for (const l of LINKS) l.visible = false;" in only
    assert js.count("LINKS.push(add(") == 3  # the vessels, the nerves and the blood
    assert "(!OM || shown(o))" in js
    for ref in ("ONLY_D", "PAGE_OF", "KREC"):
        assert ref in js
    # every kind of part the list can pick is one the dashboard can focus
    pick = js[js.index("function pick(kind, key)") :]
    pick = pick[: pick.index("\n  }\n")]
    for kind in ("region", "heart", "sense", "hood", "note", "feature"):
        assert f'kind === "{kind}"' in pick and f'kind: "{kind}"' in js, kind


def test_an_organ_pages_list_has_every_part_with_its_live_state():
    js = static("being.js").decode()
    d = js[js.index("async function describe()") :]
    d = d[: d.index("\n  }\n")]
    for org, table, kind in (
        ("mind", "REGIONS", "region"),
        ("heart", "HEART_PARTS", "heart"),
        ("senses", "SENSES", "sense"),
    ):
        assert f'if (o === "{org}") parts = Object.entries({table}).map(([k, r]) => ({{ kind: "{kind}", key: k,' in d
        assert f'live: partLive("{kind}", k)' in d
    assert 'if (o === "memory") parts = memory.hoods' in d
    assert "detail: SUB ? await detail(SUB) : null" in d and "said: SAID" in d
    # its switches go the dashboard's own ways (api settings, modules), so the phone's sealed requests carry them
    assert 'await api("settings", { key, value })' in js
    assert 'await api(on ? "modules/enable" : "modules/disable", on ? { ids: [id] } : { id })' in js


def test_0811_sparks_show_and_the_resting_ones_have_a_switch():
    import kurooto.web.server  # noqa: F401 (registers the look defaults)
    from kurooto.core.config import _DEFAULTS

    js = static("being.js").decode()
    # the sparks run inside the brain: drawn through the solid cortex, in their own colour (not added onto it)
    fire = js[js.index("const fire = new THREE.Points(") :]
    fire = fire[: fire.index("\n")]
    assert "depthTest: false" in fire and "THREE.NormalBlending" in fire
    # resting sparks: on by default, look.being_resting_sparks; off with Remove animations or reduced motion
    assert _DEFAULTS["look"]["being_resting_sparks"] is True
    assert "setRest(opts.restSparks);" in js and "!STILL && !(window.matchMedia" in js and "setRest," in js
    rest = js[js.index("function resting(m)") :]
    rest = rest[: rest.index("\n  }\n")]
    assert "if (!REST.on) return;" in rest and 'mind.fire("feel"' in rest and "m.procs" in rest and "m.schedule" in rest
    home = static("home.js").decode()
    assert 'key === "look.being_resting_sparks"' in home and "restSparks: BEING_REST" in home
    phone = static("being-phone.js").decode()
    assert "restSparks: look.rest !== false" in phone and "PV.being.setRest(b.look.rest)" in phone


def test_0811_vessels_and_nerves_stay_joined_without_new_geometry():
    js = static("being.js").decode()
    # every vessel and nerve ends on an organ's own point (end), followed each frame by an offset the shaders bend to
    links = js[js.index("/* --- the links between the organs --- */") :]
    links = links[: links.index("/* ===================== the camera")]
    assert "BRAIN_C.clone()" not in links and "bstem" not in links  # no fixed world point at the brain any more
    assert links.count("end(mind.b,") == 2 and "end(heart.g," in links and "end(memory.g," in links
    assert "end(senses.organs[k]" in links
    assert "vec4(bend(position," in js and js.count("${BEND}") >= 3  # vessels, fibres, cells
    flow = js[js.index("for (let i = FLOW.length - 1;") :]
    assert "bendAt(cu, uu, cu.getPointAt(uu))" in flow[:400]  # what travels on them follows the same bend
    # the per-frame work is the ends' offsets only: each tube is built once, outside any tick
    ends = js[js.index("ticks.push(() => { for (const e of ENDS)") :]
    assert "Geometry" not in ends[: ends.index("\n")]
    assert "e.d.copy(e.l).applyMatrix4(e.obj.matrixWorld).sub(e.w)" in ends


def test_0811_a_heard_stretch_draws_dimmer_in_the_you_lane():
    js = static("being.js").decode()
    assert 'm.kind === "voice_heard"' in js and "heard: true" in js
    assert '"heard, not to Kurooto"' in js and "L.heard ? .45 : 1" in js
    assert '"heard, not to Kurooto"' in static("being-phone.js").decode()


def _fn(js: str, head: str) -> str:
    body = js[js.index(head) :]
    return body[: body.index("\n  }\n")]


def test_0813_the_you_lane_is_live_from_the_microphones_levels_behind_its_switch():
    import kurooto.web.server  # noqa: F401 (registers the look defaults)
    from kurooto.core.config import _DEFAULTS

    js = static("being.js").decode()
    assert _DEFAULTS["look"]["being_live_waveform"] is True
    # voice_level feeds a fixed ring (no allocation as it comes), only with the switch on; the ear's glow as before
    assert 'if (m.kind === "voice_level" && m.levels) { liveIn(m); senses.level' in js
    assert "on: opts.liveWave !== false, ring: new Float32Array(320)" in js
    live_in = _fn(js, "  function liveIn(m) {")
    assert "if (!LIVE.on || !Array.isArray(m.levels)) return;" in live_in and "r[LIVE.n++ % r.length]" in live_in
    assert "new " not in live_in and "LIVE.at = NOW" in live_in
    # it shows while levels come, settles into the turn's outline, fades out after 1.5 s without one
    assert (
        "if (age > 1.5 || (LANES.you && LIVE.loud <= LIVE.settled)) return 0; return Math.min(1, (1.5 - age) / .5);"
        in js
    )
    for settle in (
        'if (m.who === "you") { senses.hit.hearing = NOW; LIVE.settled = NOW; }',
        "heard: true }; senses.hit.hearing = NOW; LIVE.settled = NOW; }",
        "else { senses.hit.hearing = NOW; LIVE.settled = NOW; } } // the talk box",
    ):
        assert settle in js, settle
    assert "const setLive = (v) => { LIVE.on = v !== false;" in js and "setRest, setLive," in js
    # reduced motion or Remove animations: a sweep, not a scroll
    assert "if (calmEye()) { // a sweep" in _fn(js, "  function liveWave(c, y, h, x0, x1, d) {")
    # the dashboard draws it in the YOU lane only; the phone gets no levels and passes no live argument
    assert "const lv = liveShow();" in js and 'say its name, or type in the talk box", lv);' in js
    assert "if (live > 0) { liveWave(c, y, h, x0, x1, live); return; }" in js
    # the dashboard's path: the setting at mount, on load and when it changes on the Settings page
    home = static("home.js").decode()
    assert "liveWave: BEING_LIVE" in home and "BEING.setLive(BEING_LIVE)" in home
    assert 'key === "look.being_live_waveform"' in home and "look.values.being_live_waveform !== false" in home
    assert '"look.being_live_waveform"' in static("settings-guide.js").decode()


def test_0813_the_lanes_are_smooth_waveforms_not_bars():
    js = static("being.js").decode()
    lane = _fn(js, "  function lane(c, y, h, L, lab, sub, live) {")
    # one fillRect: the baseline; the samples go through wave(), a filled mirrored path with its top edge stroked
    assert lane.count("fillRect(") == 1 and "for (let i = 0; i < shown; i++)" not in lane
    assert "wave(c, y, h, S, 0, shown," in lane and "L.heard ? .45 : 1" in lane
    wave = _fn(js, "  function wave(c, y, h, src, o, n, xa, xb, xn, span, d) {")
    assert "fillRect" not in wave and "cr(at(" in wave and "c.fill();" in wave and "c.stroke();" in wave
    assert "y + WY[k]" in wave and "y - WY[k]" in wave  # mirrored
    assert "createLinearGradient" in wave and "${.3 * d}" in wave  # older samples dimmer, .3 to 1 as the bars were
    assert "const WX = new Float32Array(1600), WY = new Float32Array(1600);" in js  # reused every frame
    # the phone draws through the same lane(), lower and thinner
    phone = static("being-phone.js").decode()
    assert 'lane(c, H - 60, 20, L.you, "YOU",' in phone and 'lane(c, H - 22, 26, L.me, "KUROOTO",' in phone
