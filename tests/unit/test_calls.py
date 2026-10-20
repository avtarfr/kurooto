"""Phone calls without a call line: the shared crypto, which tools exist for which features, ringing when the line
is down, what calls hand back to features (check-ins, the alarm), voice notes, staying awake, and the deploy helpers.
The call line itself is tested end to end in tests/integration/test_call_line.py."""

from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import kurooto
from kurooto.modules import awake as awake_mod
from kurooto.modules.calls import deploy, line
from kurooto.modules.calls.tools import keyword_search, notes_index, read_note
from tests.fakes.cloud import FakeCloud

VECTORS = Path(__file__).parent.parent / "fixtures" / "call-vectors.json"
WORKER = Path(kurooto.__file__).parent / "data" / "worker"


# --------------------------------------------------------------------------------------------- crypto
def test_k1_and_t1_match_the_shared_vectors():
    v = json.loads(VECTORS.read_text(encoding="utf-8"))
    k = v["k1"]
    assert line.seal_k1(k["key"], k["plain"], bytes.fromhex(k["nonce_hex"])) == k["sealed"]
    assert line.open_k1(k["key"], k["sealed"]) == k["plain"]
    assert line.open_k1(k["key"], k["sealed"][:-2] + "AA") is None
    assert line.open_k1(line.new_key(), k["sealed"]) is None
    t = v["t1"]
    assert line.ticket(t["secret"], t["hours"], t["now_ms"]) == t["ticket"]
    assert line.ticket_ok(t["secret"], t["ticket"], now_ms=t["now_ms"])
    assert not line.ticket_ok(t["secret"], t["ticket"], now_ms=t["now_ms"] + 3 * 3600_000)
    assert not line.ticket_ok("other", t["ticket"], now_ms=t["now_ms"])
    assert not line.ticket_ok(t["secret"], "t1.123.abc")


@pytest.mark.skipif(
    not shutil.which("node") or not (WORKER / "node_modules" / "@google" / "genai").is_dir(),
    reason="needs Node and the Worker's packages",
)
def test_the_worker_agrees_with_the_vectors():
    js = Path(__file__).parent.parent / "js" / "vectors.mjs"
    r = subprocess.run(
        ["node", str(js), str(WORKER / "src" / "worker.js"), str(VECTORS)], capture_output=True, text=True, timeout=60
    )
    assert r.returncode == 0, r.stderr
    assert "vectors ok" in r.stdout


def test_vapid_keys_and_pair_codes():
    from cryptography.hazmat.primitives.asymmetric import ec

    jwk, pub = line.vapid_keys()
    j = json.loads(jwk)
    assert j["crv"] == "P-256" and len(line.unb64url(j["d"])) == 32
    raw = line.unb64url(pub)
    assert raw[0] == 4 and raw[1:33] == line.unb64url(j["x"])
    ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), raw)
    codes = {line.pair_code() for _ in range(50)}
    assert len(codes) == 50 and all(len(c) == 8 and set(c) <= set(line.CODE_ALPHABET) for c in codes)


# ---------------------------------------------------------------------------------------------- notes
def test_notes_index_search_and_safe_reading(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "probability.md").write_text("---\naliases: [stats]\n---\n# Probability\n\n## Bayes\n\nprior")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "x.md").write_text("# hidden")
    idx = notes_index(tmp_path)
    assert [e["s"] for e in idx] == ["a/probability"] and idx[0]["a"] == "stats" and idx[0]["h"] == "Bayes"
    assert keyword_search(tmp_path, "bayes stats")[0]["slug"] == "a/probability"
    assert "prior" in read_note(tmp_path, "a/probability")
    (tmp_path.parent / "outside.md").write_text("secret")
    assert read_note(tmp_path, "../outside") is None and read_note(tmp_path, "/etc/passwd") is None


# ----------------------------------------------------------------------------------- the feature
@pytest.fixture
def calls(env):
    env.app.secrets.set("gemini.api_key", "k")
    deploy.ensure_secrets(env.app)
    env.app.settings.set("calls.worker", {"url": "https://kurooto-abc.your-subdomain.workers.dev"})
    env.app.settings.set("availability.night.enabled", False)  # the tests ring at the real time, maybe at night
    env.on("calls")
    return env


def test_tools_follow_the_features_you_have_on(calls):
    c = calls.app.modules["calls"]
    names = {t.name for t in c.tools()}
    assert {"pending_items", "search_notes", "read_note", "schedule_call", "hold_calls"} <= names
    assert "run_task" not in names and "set_alarm" not in names and "add_reminder" not in names
    calls.on("reminders", "deadlines", "checkins", "alarm")
    names = {t.name for t in c.tools()}
    assert {"add_reminder", "mark_deadline_done", "add_deadline", "change_checkin", "set_alarm"} <= names
    cfg = c.config_template()
    decl = cfg["tools"][0]["functionDeclarations"]
    assert all(d["behavior"] == "NON_BLOCKING" and d["parameters"]["type"] == "object" for d in decl)
    assert "%%NOW%%" in cfg["systemInstruction"] and "set_alarm" in cfg["systemInstruction"]
    st = c.state_message()
    assert "pending_items" in st["offline"]["brief"] and "set_alarm" in st["offline"]["queue"]
    assert "pending_items" in st["brief"] and st["names"]["assistant"] == "Kurooto"


def test_ringing_without_a_connected_line_falls_back_to_telegram(calls):
    c = calls.app.modules["calls"]
    since = c.ring("Stand-up in 5")
    last = calls.fake.texts()[-1]
    assert "isn't connected" in last and "Stand-up in 5" in last
    assert calls.app.scheduler.get(f"calls:missed:{since}")
    c._missed({"since": since})
    assert "Missed call: Stand-up in 5" in calls.fake.texts()[-1]
    assert calls.press(f"call:{since}:later").startswith("I'll call again at")
    assert calls.app.scheduler.jobs("calls:ring:")


def test_call_me_intent_and_commands(calls):
    out = calls.say("call me in 20 minutes about the laundry")
    assert out.startswith("I'll call you") and "the laundry" in out
    job = calls.app.scheduler.jobs("calls:ring:")[0]
    assert job.payload["reason"] == "the laundry" and job.respect == "call_block"
    assert "isn't set up" not in calls.say("/call")
    link = [b for m, p in calls.fake.sent if m == "sendMessage" for b in [p]][-1]
    assert "#t1." in json.dumps(link)


def test_check_in_by_call_rings_and_journals_what_you_said(calls):
    app = calls.app
    calls.on("checkins")
    app.settings.set("checkins.by_call", True)
    ck = app.modules["checkins"]
    day = dt.date.today().isoformat()
    ck.move("evening", "23:59")
    sched = app.modules["calls"].schedule_list()
    assert any(x["key"] == f"checkins:evening:{day}" for x in sched)
    ck._fire({"name": "evening", "day": day})
    assert ck.today()["evening"]["status"] == "calling"
    rings = json.loads((app.paths.state / "calls" / "rings.json").read_text())
    since = next(k for k, r in rings.items() if r["key"] == f"checkins:evening:{day}")
    c = app.modules["calls"]
    c.on_event({"name": "call_started", "since": since})
    assert ck.today()["evening"]["status"] == "answered"
    c.handle_request(
        "POST",
        "/transcript",
        json.dumps(
            {
                "since": since,
                "lines": [{"who": "Sam", "text": "Good day, finished the essay."}, {"who": "Kurooto", "text": "Nice."}],
            }
        ).encode(),
    )
    journal = (app.workspace / "journal" / f"{day}.md").read_text()
    assert "Evening check-in, by call" in journal and "finished the essay" in journal and "Nice." not in journal


def test_missed_check_in_call_asks_on_telegram(calls):
    calls.on("checkins")
    calls.app.settings.set("checkins.by_call", True)
    ck = calls.app.modules["checkins"]
    day = dt.date.today().isoformat()
    ck.move("evening", "23:59")
    ck._fire({"name": "evening", "day": day})
    ck.call_outcome(f"checkins:evening:{day}", "missed")
    assert "missed call" in calls.fake.texts()[-1] and ck.today()["evening"]["status"] == "asked"


def test_check_in_call_waits_out_a_block_or_asks_by_message(calls, monkeypatch):
    from kurooto.modules import checkins as ck_mod

    app = calls.app
    calls.on("checkins")
    app.settings.set("checkins.by_call", True)
    ck = app.modules["checkins"]
    today = dt.date.today()
    monkeypatch.setattr(ck_mod, "now", lambda: dt.datetime.combine(today, dt.time(15, 0)))
    monkeypatch.setattr(app.availability, "call_block", lambda t=None: ("a class", None))
    later = dt.datetime.combine(today, dt.time(16, 0))
    monkeypatch.setattr(app.availability, "next_callable", lambda t=None, limit=24: (later, None))
    f = app.paths.state / "calls" / "rings.json"
    rang = lambda: f.exists() and bool(json.loads(f.read_text()))  # noqa: E731
    ck.move("evening", "23:59")
    ck._fire({"name": "evening", "day": today.isoformat()})
    assert not rang() and ck.today()["evening"]["status"] == "planned"
    job = app.scheduler.jobs("checkins:evening")[0]
    assert (
        job.when.astimezone().replace(tzinfo=None) == later and "waits until 16:00 (a class)" in calls.fake.texts()[-1]
    )
    tomorrow = later + dt.timedelta(days=1)
    monkeypatch.setattr(app.availability, "next_callable", lambda t=None, limit=24: (tomorrow, None))
    ck._fire({"name": "evening", "day": today.isoformat()})  # blocked until tomorrow: a message instead
    assert ck.today()["evening"]["status"] == "asked" and "Evening check-in:" in calls.fake.texts()[-1]
    assert not rang()


def test_alarm(calls):
    calls.on("alarm")
    a = calls.app.modules["alarm"]
    assert calls.say("wake me at 6:45").startswith("Alarm set for")
    at = a.next()
    assert at and (at.hour, at.minute) == (6, 45)
    assert a.call_schedule()[0]["alarm"] is True and a.call_brief()["alarm"]
    assert calls.say("/alarm off") == "Alarm off."
    assert a.next() is None
    # not answered: rings again in 5 minutes, at most twice
    a.set(dt.datetime.now() + dt.timedelta(hours=1))
    assert a.call_outcome("alarm:next", "missed") is True
    assert a.next() < dt.datetime.now() + dt.timedelta(minutes=6)
    a._ring({"tries": 2})
    assert a.call_outcome("alarm:next", "missed") is False
    assert a.call_outcome("alarm:next", "later") is True  # snooze 10 min, handled by the alarm itself


def test_alarm_daily_default(calls):
    calls.app.settings.set("alarm.daily", "05:30")
    calls.on("alarm")
    at = calls.app.modules["alarm"].next()
    assert at and (at.hour, at.minute) == (5, 30) and at > dt.datetime.now()


def test_tool_requests_and_tasks(calls):
    c = calls.app.modules["calls"]
    code, out = c.handle_request("POST", "/tool", json.dumps({"name": "hold_calls", "args": {"until": "2h"}}).encode())
    assert code == 200 and out["result"].startswith("No calls until")
    assert calls.app.availability.call_block()[0]
    c.run_tool("hold_calls", {"until": "off"})
    assert (
        not calls.app.availability.call_block()[0] or calls.app.availability.call_block()[0] != "you asked for no calls"
    )
    code, out = c.handle_request("GET", "/tasks", b"")
    assert out == {"finished": [], "running": 0, "approvals": [], "computer": "online"}


def test_upload_limits(calls):
    c = calls.app.modules["calls"]
    code, out = c.handle_request("POST", "/upload?name=big.bin&id=x&part=0&parts=1", b"x" * ((1 << 20) + 1))
    assert code == 413
    code, out = c.handle_request("POST", "/upload?name=../../evil.sh", b"hi")
    assert code == 200 and out["saved"].startswith("inbox/") and "/.." not in out["saved"]


# ------------------------------------------------------------------------------------- voice notes
def test_voice_notes_are_written_out_and_handled(env, tmp_path):
    cloud = FakeCloud()
    try:
        env.app.secrets.set("gemini.api_key", "k")
        env.app.settings.set("voice_notes.api_base", cloud.base)
        env.on("reminders", "voice_notes")
        f = tmp_path / "v.ogg"
        f.write_bytes(b"OggS fake audio")
        text = env.app.modules["voice_notes"].transcribe(f)
        assert text == "remind me at nine to call home"
        sent = cloud.generate[-1]
        assert sent["headers"]["x-goog-api-key"] == "k"
        assert sent["body"]["contents"][0]["parts"][0]["inline_data"]["mime_type"] == "audio/ogg"
    finally:
        cloud.close()


# ------------------------------------------------------------------------------------------ awake
@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="the Linux path (systemd-inhibit)")
def test_stay_awake_holds_only_on_ac(env, monkeypatch, tmp_path):
    fake = tmp_path / "systemd-inhibit"
    fake.write_text("#!/bin/sh\nexec sleep 30\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
    a = env.app.modules["awake"]
    plugged = {"v": True}
    monkeypatch.setattr(awake_mod, "on_ac", lambda: plugged["v"])
    a.tick()
    assert a.holding and a.holder.poll() is None
    plugged["v"] = False
    a.tick()
    assert not a.holding and a.holder is None
    a.release()


# ------------------------------------------------------------------------------------------ deploy
def test_deploy_helpers(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "should-not-pass")
    env = deploy.wrangler_env(tmp_path / "cfg", tmp_path / "cache", account="a" * 32)
    home = str(tmp_path / "cfg" / "cloudflare")
    assert env["HOME"] == env["USERPROFILE"] == env["XDG_CONFIG_HOME"] == home
    assert "CLOUDFLARE_API_TOKEN" not in env and env["CLOUDFLARE_ACCOUNT_ID"] == "a" * 32
    assert env["WRANGLER_SEND_METRICS"] == "false"
    tpl = (WORKER / "wrangler.template.toml").read_text()
    vals = {
        "name": "kurooto-x",
        "owner_id": "owner",
        "tz": "Asia/Tokyo",
        "public_url": "https://u",
        "version": "1",
        "live_model": "m",
        "ntfy_server": "https://ntfy.sh",
        "notes_repo": 'we"ird',
    }
    import tomllib

    cfg = tomllib.loads(deploy.render_toml(tpl, vals))
    assert cfg["name"] == "kurooto-x" and cfg["vars"]["NOTES_REPO"] == 'we"ird' and cfg["triggers"]["crons"]
    with pytest.raises(ValueError):
        deploy.render_toml(tpl, {k: v for k, v in vals.items() if k != "tz"})
    who = "Account Name | Account ID\nMe | 0123456789abcdef0123456789abcdef\n"
    assert deploy.accounts_from_whoami(who) == ["0123456789abcdef0123456789abcdef"]
    assert deploy.new_name().startswith("kurooto-") and len(deploy.new_name()) == 14
    h1 = deploy.source_hash()
    assert h1 == deploy.source_hash() and len(h1) == 16


def test_secrets_are_made_once(env):
    env.app.secrets.set("gemini.api_key", "g")
    a = deploy.ensure_secrets(env.app)
    b = deploy.ensure_secrets(env.app)
    assert a == b and a["GEMINI_API_KEY"] == "g" and len(a["CALL_SECRET"]) == 64
    assert a["NTFY_TOPIC"].startswith("kurooto-") and json.loads(a["VAPID_JWK"])["kty"] == "EC"


# ------------------------------------------------------------------------------------ the pages' API
def test_gemini_key_check_and_phone_endpoints(env):
    from kurooto.web.api import Api

    cloud = FakeCloud()
    try:
        env.app.settings.set("voice_notes.api_base", cloud.base)
        api = Api(env.app)
        assert api.post("keys/gemini", {"key": "bad"})[1] == {"ok": False, "error": "Google didn't accept that key."}
        assert not env.app.secrets.get("gemini.api_key")
        assert api.post("keys/gemini", {"key": " good-key "})[1] == {"ok": True}
        assert env.app.secrets.get("gemini.api_key") == "good-key"
        assert api.get("state")[1]["keys"] == {"gemini": True}
        assert api.get("phone")[1] == {"on": False}
        assert api.post("phone/test", {})[1]["ok"] is False
        env.app.settings.set("calls.worker", {"url": "https://kurooto-abc.your-subdomain.workers.dev"})
        deploy.ensure_secrets(env.app)
        env.on("calls")
        ph = api.get("phone")[1]
        assert ph["on"] and ph["connected"] is False and ph["devices"] is None
        r = api.post("phone/pair", {})[1]
        assert r["ok"] is False and "call line" in r["error"]
        assert api.post("phone/test", {})[1] == {"ok": True}  # rings (here: the Telegram fallback)
        assert "isn't connected" in env.fake.texts()[-1]
    finally:
        cloud.close()


def test_line_is_redeployed_only_when_its_code_changed(calls, monkeypatch):
    c = calls.app.modules["calls"]
    ran = []
    monkeypatch.setattr(deploy, "deploy", lambda app, progress=None: ran.append(1) or (True, "ok"))
    w = calls.app.settings.get("calls.worker")
    calls.app.settings.set("calls.worker", {**w, "hash": deploy.fingerprint(calls.app)})
    assert c._line_update() is False
    calls.app.settings.set("calls.worker", {**w, "hash": "old"})
    calls.app.settings.set("updates.mode", "off")
    assert c._line_update() is False
    calls.app.settings.set("updates.mode", "night")
    assert c._line_update() is True
    import time as _t

    for _ in range(50):
        if ran:
            break
        _t.sleep(0.05)
    assert ran == [1]


def test_the_call_page_source_is_copied_and_the_built_one_is_not(tmp_path):
    """Skipping every app.js once left web/app.js behind, so building the call page failed for everyone."""
    import shutil

    src = tmp_path / "src"
    for rel in ("web/app.js", "public/app.js", "public/index.html", "node_modules/x/y.js", "src/worker.js"):
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text("x")
    dst = tmp_path / "dst"
    shutil.copytree(src, dst, ignore=deploy.skip_built)
    assert (dst / "web" / "app.js").is_file() and (dst / "public" / "index.html").is_file()
    assert not (dst / "public" / "app.js").exists() and not (dst / "node_modules").exists()
    assert (dst / "src" / "worker.js").is_file()
