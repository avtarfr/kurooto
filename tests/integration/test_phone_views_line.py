"""Systems and the Notes map on the Android app, end to end on this computer: the real Worker under `wrangler dev`, the
real connector and Phone calls feature (see test_call_line.py for the setup).

With calls.views on, the notes map goes to the call line sealed for the Android phone alone (the line can't read it)
and /view hands that phone its copy, also while this computer is away; a web app gets none. The app saying it's
watching Systems (/view/watch) reaches this computer, which sends Systems live until the watching stops. Parts come
in order and only the newest whole copy shows; turned off, the line drops every copy.
"""

from __future__ import annotations

import base64
import json
import time

import pytest

from kurooto.modules.calls import line
from tests.integration.test_call_line import Loop, pytestmark, wait, world  # noqa: F401 (the shared fixture)
from tests.integration.test_lidsafe_line import away, back, on_loop
from tests.integration.test_phone_line import phones  # noqa: F401
from tests.unit.test_lidsafe import Phone

BODY_TEXT = "a-sentence-only-the-note-holds"


@pytest.fixture(scope="module")
def seen(phones):  # noqa: F811
    app, ln = phones["app"], phones["line"]
    phone = Phone()
    assert ln.call("POST", "/device/key", {"pub": phone.pub}, key=phones["keys"]["android"]) == (200, {"ok": True})
    for i in range(12):
        (app.workspace / f"note-{i}.md").write_text(
            f"# Note {i}\n\n{BODY_TEXT}\n\n[[note-{(i + 1) % 12}]]\n", encoding="utf-8"
        )
    phones.update(phone=phone, android=phones["keys"]["android"])  # (away() and back() use it)
    return phones


def view(w, kind, who="android"):
    code, got = w["line"].call("GET", f"/view?kind={kind}", key=w["keys"][who])
    assert code == 200, got
    return got


def opened(w, got):
    v = got["view"]
    out = line.open_v1(w["phone"].key, v["key"], line.unb64url(v["data"]))
    assert out is not None
    return json.loads(out[2])


def test_the_notes_map_reaches_the_phone_sealed_and_stays_with_the_computer_away(seen):
    w = seen
    w["app"].settings.set("calls.views", True)
    on_loop(w, w["calls"].connector.push_state())
    got = wait(lambda: view(w, "notes")["view"] and view(w, "notes"), 30, "the notes map on the line")
    assert BODY_TEXT not in json.dumps(got) and "Note 3" not in json.dumps(got)  # only the phone can open it
    snap = opened(w, got)
    assert "Note 3" in [n[1] for n in snap["nodes"]] and BODY_TEXT not in json.dumps(snap)
    assert got["computer"] == "online" and not got["off"] and got["view"]["at"]
    assert view(w, "notes", "web")["view"] is None  # the web app has no key of its own
    assert w["line"].call("GET", "/view?kind=notes")[0] == 401
    assert w["line"].call("GET", "/view?kind=diary", key=w["keys"]["android"])[0] == 400
    away(w)
    still = view(w, "notes")
    assert still["view"] == got["view"] and still["computer"] == "offline"
    back(w)


def test_watching_systems_makes_it_live(seen):
    w = seen
    assert view(w, "systems")["view"] is None  # nobody watched yet: nothing sent
    code, out = w["line"].call("POST", "/view/watch", {}, key=w["keys"]["android"])
    assert code == 200 and out["ok"] and out["told"] and out["computer"] == "online"
    got = wait(lambda: view(w, "systems")["view"] and view(w, "systems"), 30, "Systems on the line")
    snap = opened(w, got)
    assert snap["kind"] == "systems" and [c["id"] for c in snap["cells"]] == [f["id"] for f in snap["features"]] != []
    rev = got["view"]["rev"]
    wait(lambda: view(w, "systems")["view"]["rev"] > rev, 30, "a fresher copy while watched")
    assert w["line"].call("POST", "/view/watch", {}, key=w["keys"]["web"])[0] == 403  # only the Android app


def test_parts_and_the_newest_only(seen):
    w = seen
    c = w["calls"].connector
    blob = bytes(range(256)) * 900  # 230 KB: three parts
    parts = [blob[i : i + 96 * 1024] for i in range(0, len(blob), 96 * 1024)]
    key = line.seal_s1(w["phone"].pub, "v1 notes 1 x y")

    def put(rev, i, **kw):
        return on_loop(w, c.admin("view-put", view="notes", rev=rev, part=i, parts=len(parts),
                                  data=base64.b64encode(parts[i]).decode(), **kw))  # fmt: skip

    now = time.time_ns() // 1000
    assert put(now, 1).get("error")  # in order, from part 0
    assert put(now, 0, size=len(blob), keys={w["keys"]["android"].split(".")[1]: key})["ok"]
    assert put(now, 1)["ok"] and view(w, "notes")["view"]["rev"] < now  # not ready: the last whole one shows
    assert put(now, 2)["ready"]
    got = view(w, "notes")
    assert got["view"]["rev"] == now and line.unb64url(got["view"]["data"]) == blob
    assert put(now - 5, 0, size=len(blob), keys={})["stale"]  # never an older one


def test_turned_off_the_line_drops_every_copy(seen):
    w = seen
    w["app"].settings.set("calls.views", False)
    on_loop(w, w["calls"].connector.push_state())
    got = wait(lambda: view(w, "notes")["off"] and view(w, "notes"), 20, "the line dropping it")
    assert got["view"] is None and view(w, "systems")["view"] is None
    code, out = w["line"].call("POST", "/view/watch", {}, key=w["keys"]["android"])
    assert code == 200 and out.get("off")
    w["app"].settings.set("calls.views", True)
