"""Rhythm and machine (WS3): the check-in day from 05:00, the night check-in that finds you asleep, keeping the
computer awake until the alarm and (on the charger) with the lid closed, the study tracker's idle and lock-screen
detection and research time, starting from boot, and Notes sync's clash policies. Fake clocks, fake OS probes, a fake
HOME: nothing here touches systemd, logind or the real desktop."""

import datetime as dt
import json
import shutil
import subprocess
import types

import pytest

from kurooto.core import autostart, idle, inhibit
from kurooto.core.config import Settings
from kurooto.core.secrets import Secrets
from kurooto.modules import alarm as alarm_mod
from kurooto.modules import awake as awake_mod
from kurooto.modules import checkins as ck_mod
from kurooto.modules import daily
from kurooto.modules.calls import deploy

D = dt.date(2026, 10, 21)  # a Wednesday


def at(day, h, m=0):
    return dt.datetime.combine(day, dt.time(h, m))


class Clock:
    """The time the check-ins and the alarm see."""

    def __init__(self, monkeypatch, t):
        self.t = t
        for mod in (ck_mod, alarm_mod):
            monkeypatch.setattr(mod, "now", lambda: self.t)


class FakeProc:
    def __init__(self, args, code=None):
        self.args, self.code, self.pid = args, code, 999999

    def poll(self):
        return self.code

    def wait(self, timeout=None):
        return self.code


class Popen:
    """Records what would have been started; `code` is what the next one exits with (None: keeps running)."""

    def __init__(self):
        self.started: list[list[str]] = []
        self.code = None

    def __call__(self, args, **kw):
        self.started.append(list(args))
        return FakeProc(args, self.code)


@pytest.fixture
def no_kill(monkeypatch):
    killed = []
    monkeypatch.setattr(inhibit.proc, "kill_tree", lambda pid: killed.append(pid))
    return killed


def fake_inhibitor(platform="linux", popen=None, clock=None, set_state=None):
    return inhibit.Inhibitor(
        why="test",
        platform=platform,
        popen=popen or Popen(),
        which=lambda name: f"/usr/bin/{name}",
        set_state=set_state,
        clock=clock or (lambda: 1000.0),
    )


# ------------------------------------------------------------------------------------- the inhibitor
def test_linux_hold_with_the_lid_and_a_length(no_kill):
    popen = Popen()
    inh = fake_inhibitor(popen=popen)
    assert inh.hold(3600, lid=True)
    args = popen.started[0]
    assert args[0] == "/usr/bin/systemd-inhibit" and "--what=sleep:handle-lid-switch" in args
    assert args[-2:] == ["sleep", "3600"] and "--mode=block" in args
    assert inh.hold(3600, lid=True) and len(popen.started) == 1  # held the same way: kept
    assert inh.hold(None, idle=True) and popen.started[1][-4:-2] == ["tail", f"--pid={inhibit.os.getpid()}"]
    assert "--what=sleep:idle" in popen.started[1] and no_kill  # the old one was ended
    inh.release()
    assert not inh.held()


def test_a_refused_lid_hold_falls_back_without_the_lid(no_kill):
    popen = Popen()
    popen.code = 1  # logind's policy says no: systemd-inhibit exits at once
    inh = fake_inhibitor(popen=popen)
    inh.hold(None, lid=True)
    popen.code = None
    assert inh.hold(None, lid=True)
    assert inh.lid_refused and "--what=sleep" in popen.started[-1]
    assert not any("handle-lid-switch" in a for a in popen.started[-1])


def test_hold_ends_by_itself_and_other_systems():
    t = {"now": 1000.0}
    inh = fake_inhibitor(clock=lambda: t["now"])
    inh.hold(60)
    assert inh.held()
    t["now"] += 61
    assert not inh.held()
    popen = Popen()
    mac = fake_inhibitor("darwin", popen)
    mac.hold(600)
    assert popen.started[-1][:2] == ["/usr/bin/caffeinate", "-is"] and popen.started[-1][-2:] == ["-t", "600"]
    mac.hold(None, ac_only=True)
    assert popen.started[-1][1] == "-s" and "-t" not in popen.started[-1]
    flags = []
    win = fake_inhibitor("win32", set_state=flags.append)
    assert win.hold(30) and win.held()
    win.release()
    assert flags == [inhibit.ES_CONTINUOUS | inhibit.ES_SYSTEM_REQUIRED, inhibit.ES_CONTINUOUS]
    none = inhibit.Inhibitor(platform="linux", which=lambda name: None)
    assert not none.supported()[0] and not none.hold(60)


def test_stay_awake_holds_the_lid_on_the_charger(env, monkeypatch, no_kill):
    a = env.app.modules["awake"]
    popen = Popen()
    a.inhibitor = fake_inhibitor(popen=popen)
    plugged = {"v": True}
    monkeypatch.setattr(awake_mod, "on_ac", lambda: plugged["v"])
    a.tick()
    assert a.holding and "--what=sleep:idle" in popen.started[-1]
    env.app.settings.set("awake.lid", True)
    a.tick()
    assert "--what=sleep:idle:handle-lid-switch" in popen.started[-1]
    if awake_mod.sys.platform.startswith("linux"):
        assert "lid closed too" in a.health()[1]
    plugged["v"] = False
    a.tick()
    assert not a.holding and a.holder is None and a.health()[1] == "on battery: sleeping as usual"


# ------------------------------------------------------------------------------- awake until the alarm
@pytest.fixture
def calls(env):
    env.app.secrets.set("gemini.api_key", "k")
    deploy.ensure_secrets(env.app)
    env.app.settings.set("calls.worker", {"url": "https://kurooto-abc.your-subdomain.workers.dev"})
    env.app.settings.set("availability.night.enabled", False)
    env.on("calls")
    return env


def rings(app):
    f = app.paths.state / "calls" / "rings.json"
    return json.loads(f.read_text()) if f.exists() else {}


def test_keep_awake_until_the_alarm(calls, monkeypatch, no_kill):
    app = calls.app
    calls.on("alarm")
    clock = Clock(monkeypatch, at(D, 22, 30))
    a = app.modules["alarm"]
    popen = Popen()
    a.inhibitor = fake_inhibitor(popen=popen)
    a.on_ac = lambda: False
    assert a.set(at(D + dt.timedelta(days=1), 6, 30)) == "Alarm set for Thu 22 Oct, 06:30."  # off by default
    assert popen.started == []
    app.settings.set("alarm.keep_awake", True)
    out = a.set(at(D + dt.timedelta(days=1), 6, 30))
    assert out.endswith("Plug this computer in: it stays awake until then.")
    args = popen.started[-1]
    assert "--what=sleep:handle-lid-switch" in args and args[-1] == str(8 * 3600 + 15 * 60)
    assert "keeping this computer awake, lid closed too" in a.health()[1]
    a.call_outcome("alarm:next", "missed")  # a repeat ring 5 minutes on: still held
    assert a.inhibitor.held()
    a.call_outcome("alarm:next", "answered")
    a.clear()
    assert not a.inhibitor.held()
    # a daily alarm set in the morning doesn't hold all day: from 12 hours before
    clock.t = at(D, 8, 0)
    a.on_ac = lambda: True
    assert a.set(at(D + dt.timedelta(days=1), 7, 0)) == "Alarm set for Thu 22 Oct, 07:00."
    assert not a.inhibitor.held()
    job = app.scheduler.get("alarm:awake")
    assert job and dt.datetime.fromtimestamp(job.next_run) == at(D, 19, 0)
    clock.t = at(D, 19, 0)
    assert a.keep_awake() and a.inhibitor.held()


# --------------------------------------------------------------------------------- the check-in day
@pytest.fixture
def ck(env, monkeypatch):
    env.app.settings.set("checkins.day_starts", "05:00")
    env.app.settings.set("checkins.times.night", "23:30")
    clock = Clock(monkeypatch, at(D, 12, 0))
    env.on("checkins")
    return env, env.app.modules["checkins"], clock


def test_the_check_in_day_runs_from_5_am(ck):
    env, c, clock = ck
    assert c.day_of(at(D + dt.timedelta(days=1), 4, 59)) == D and c.day_of(at(D, 5, 0)) == D
    assert c.at(D, "00:30") == at(D + dt.timedelta(days=1), 0, 30) and c.at(D, "22:00") == at(D, 22, 0)
    assert env.app.scheduler.get("checkins:plan").spec == "daily 05:05"
    # pushed past midnight, the night check-in stays the evening's (it used to move to the morning)
    clock.t = at(D, 23, 40)
    assert c.postpone("night", 30) == "Night check-in at 00:10."
    job = env.app.scheduler.get("checkins:night")
    assert dt.datetime.fromtimestamp(job.next_run) == at(D + dt.timedelta(days=1), 0, 10)
    assert job.payload["day"] == D.isoformat()
    # at 00:10 it asks, and the answer goes into that evening's journal
    clock.t = at(D + dt.timedelta(days=1), 0, 10)
    assert c.today() is not None and c.day_of() == D
    c._fire({"name": "night", "day": D.isoformat()})
    assert "Night check-in:" in env.fake.texts()[-1]
    assert env.reply_to_last("Long day; finished the essay.").startswith("Saved to your journal")
    assert "finished the essay" in daily.note_path(env.app, D).read_text(encoding="utf-8")
    # still up at 1 am: a time already past, or a check-in that's over, means the coming day
    clock.t = at(D + dt.timedelta(days=1), 1, 0)
    assert c.move("evening", "21:00") == "Evening check-in today at 21:00."
    assert c.today(D + dt.timedelta(days=1))["evening"]["time"] == "21:00"
    assert c.skip("night") == "No night check-in today."
    assert c.today(D + dt.timedelta(days=1))["night"]["status"] == "skipped"
    assert c.today(D)["night"]["status"] == "answered"
    assert c.move("night", "01:30") == "Night check-in at 01:30."  # tonight's own, still ahead
    assert c.today(D)["night"]["time"] == "01:30"


def test_plain_english_after_midnight_and_a_late_start(ck):
    env, c, clock = ck
    clock.t = at(D + dt.timedelta(days=1), 0, 20)
    match, run = c.intents()[0].match, c.intents()[0].run
    s = match("push the night check-in by 20 min")
    assert s["day"] == D and run(None, s) == "Night check-in at 00:40."
    s = match("skip tomorrow's check-in")
    assert s["day"] == D + dt.timedelta(days=1)
    # Kurooto starting at 2 am doesn't plan (and then report missing) last evening's check-in
    clock.t = at(D + dt.timedelta(days=2), 2, 0)
    c._plan({})
    assert c.today() == {}  # 22:00 and 23:30 are long over


# ---------------------------------------------------------------------------- asleep: the night check-in
@pytest.fixture
def night(calls, monkeypatch):
    calls.app.settings.set("checkins.times.night", "23:30")
    calls.app.settings.set("checkins.by_call", True)
    clock = Clock(monkeypatch, at(D, 22, 0))
    calls.on("alarm", "checkins")
    return calls, calls.app.modules["checkins"], calls.app.modules["alarm"], clock


def test_night_check_in_with_the_alarm_set_waits_for_the_morning(night):
    env, c, a, clock = night
    a.set(at(D + dt.timedelta(days=1), 7, 0))  # set by hand at 22:00: gone to bed
    clock.t = at(D, 23, 30)
    before = len(rings(env.app))
    c._fire({"name": "night", "day": D.isoformat()})
    assert len(rings(env.app)) == before  # no ring
    assert c.today(D)["night"]["status"] == "deferred" and c.deferred()["name"] == "night"
    assert "took it you're asleep" in env.fake.texts()[-1]
    sent = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
    assert [b["text"] for row in sent["reply_markup"]["inline_keyboard"] for b in row] == ["Call me now", "Skip"]
    assert "Last night's night check-in" in a.script()
    assert env.press(f"chk:night|{D.isoformat()}:now") == "Calling you now."
    assert len(rings(env.app)) == before + 1 and c.deferred() is None


def test_night_check_in_rings_when_you_moved_it_or_turned_this_off(night):
    env, c, a, clock = night
    a.set(at(D + dt.timedelta(days=1), 7, 0))
    clock.t = at(D, 23, 20)
    c.move("night", "23:40")  # asked for after the alarm was set
    clock.t = at(D, 23, 40)
    before = len(rings(env.app))
    c._fire({"name": "night", "day": D.isoformat()})
    assert len(rings(env.app)) == before + 1
    env.app.settings.set("checkins.asleep_defers", False)
    assert not c._asleep({"time": "23:30", "status": "planned"})


def test_daily_alarm_counts_from_bedtime(night):
    env, c, a, clock = night
    env.app.settings.set("availability.night", {"enabled": True, "from": "23:00", "to": "07:00"})
    a.set(at(D + dt.timedelta(days=1), 7, 0), daily=True)
    clock.t = at(D, 22, 45)
    assert not c._asleep({})  # before bedtime: the goodnight call rings
    clock.t = at(D, 23, 30)
    assert c._asleep({})


# ------------------------------------------------------------------------------- idle and the lock screen
class Desk:
    """A fake desktop: answers to commands, running processes, files."""

    def __init__(self, answers=None, procs=(), files=None, env=None, platform="linux"):
        self.answers = answers or {}
        self.asked: list[str] = []
        self.t = 1000.0
        self.probe = idle.IdleProbe(
            None,
            platform=platform,
            env=env if env is not None else {"WAYLAND_DISPLAY": "wayland-1", "USER": "sam"},
            run=self.run,
            which=lambda name: f"/usr/bin/{name}" if name in ("busctl", "loginctl", "xprintidle") else None,
            procs=lambda: set(procs),
            read=lambda path: (files or {}).get(path, ""),
            clock=lambda: self.t,
        )

    def run(self, args):
        line = " ".join(args)
        self.asked.append(line)
        for key, out in self.answers.items():
            if key in line:
                return out() if callable(out) else out
        return ""


def test_gnome_kde_and_logind_idle():
    gnome = Desk({"Mutter.IdleMonitor": "t 4500"})
    assert gnome.probe.idle_seconds() == 4.5 and gnome.probe.how == "gnome"
    v = {"n": 1000}
    kde = Desk({"GetSessionIdleTime": lambda: f"u {v['n']}"})
    assert kde.probe.idle_seconds() == 1.0 and kde.probe.how == "screensaver"  # milliseconds, at first
    kde.t += 30
    v["n"] = 1030  # it grew by 30 in 30 s: it answers in seconds
    assert kde.probe.idle_seconds() == 1030
    hint = Desk({"show-user": "3", "show-session": "IdleHint=yes\nIdleSinceHint=940000000\nLockedHint=no"})
    assert hint.probe.idle_seconds() == 60 and hint.probe.how == "logind"
    x11 = Desk({"xprintidle": "120000"}, env={"DISPLAY": ":0"})
    assert x11.probe.idle_seconds() == 120 and x11.probe.how == "x11"


def test_wayland_without_an_idle_api_watches_for_change():
    counts = {"n": 100}
    irq = lambda: {"/proc/interrupts": f"  1:  {counts['n']}  0  IR-IO-APIC  1-edge  i8042\n 9: 5 0 acpi\n"}  # noqa: E731
    d = Desk()
    d.probe.read = lambda path: irq().get(path, "")
    assert d.probe.idle_seconds("notes.pdf") == 0 and d.probe.how == "watch"
    d.t += 400
    assert d.probe.idle_seconds("notes.pdf") == 400  # nothing changed for 400 s
    counts["n"] += 3  # a key press
    assert d.probe.idle_seconds("notes.pdf") == 0
    d.t += 30
    assert d.probe.idle_seconds("other window") == 0  # the focused window changed
    asked = len([x for x in d.asked if "Mutter" in x])
    d.t += 30
    d.probe.idle_seconds("other window")
    assert len([x for x in d.asked if "Mutter" in x]) == asked  # a bus call that didn't answer isn't asked again soon


def test_your_idle_tool_can_say_away(tmp_path):
    t = {"now": 5000.0}
    probe = idle.IdleProbe(
        tmp_path,
        platform="linux",
        env={},
        run=lambda a: "",
        which=lambda n: None,
        read=lambda p: "",
        clock=lambda: t["now"],
    )
    assert idle.set_away(tmp_path, True, clock=lambda: 4000.0) == "away"
    assert probe.idle_seconds() == 1000 and probe.how == "hook"
    idle.set_away(tmp_path, False)
    assert probe.idle_seconds() is None  # back, and nothing else here can say


def test_locked_screens():
    assert Desk({"show-user": "3", "show-session": "IdleHint=no\nLockedHint=yes"}).probe.locked()
    assert Desk({"org.freedesktop.ScreenSaver GetActive": "b true"}).probe.locked()
    assert Desk(procs={"hyprlock", "kitty"}).probe.locked()
    assert not Desk(procs={"hypridle", "kitty"}).probe.locked()
    mac = Desk(
        {"IOHIDSystem": '"HIDIdleTime" = 3500000000', "Root": '"CGSSessionScreenIsLocked"=Yes'}, platform="darwin"
    )
    assert mac.probe.idle_seconds() == 3.5 and mac.probe.locked()


def test_study_tracker_skips_away_time_and_counts_research(env, monkeypatch, tmp_path):
    from kurooto.modules import study as study_mod

    env.app.settings.set("subjects.list", [{"name": "Linear Algebra", "slug": "linear-algebra", "aliases": ["la"]}])
    env.app.settings.set("study.research_paths", [str(tmp_path / "code" / "flow-model")])
    env.on("subjects", "study")
    st = env.app.modules["study"]
    state = {"locked": False, "idle": 10.0}
    st.probe = types.SimpleNamespace(
        locked=lambda: state["locked"], idle_seconds=lambda title=None: state["idle"], how="watch"
    )
    monkeypatch.setattr(study_mod, "active_title", lambda: "linear-algebra-week3.pdf")
    assert st.sample(30) == "linear-algebra"
    state["locked"] = True
    assert st.sample(30) is None  # the lock screen: away
    state.update(locked=False, idle=600.0)
    assert st.sample(30) is None  # idle for 10 minutes: away
    state["idle"] = 5.0
    monkeypatch.setattr(study_mod, "active_title", lambda: "train.py - flow-model - nvim")
    assert st.sample(30) == "research"
    assert st.totals(1) == {"linear-algebra": 30, "research": 30}
    assert "Research: 0.0 h" in st.report(1)
    assert st.health() == (True, "away time from: input and window changes")


# ------------------------------------------------------------------------------------- start from boot
@pytest.fixture
def boot(tmp_path, monkeypatch):
    linger = tmp_path / "linger"
    linger.mkdir()
    monkeypatch.setattr(autostart, "LINGER_DIR", linger)
    monkeypatch.setattr(autostart.sys, "platform", "linux")
    monkeypatch.setattr(autostart.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(autostart, "managed", lambda home=None: "systemd")
    monkeypatch.setattr(autostart.getpass, "getuser", lambda: "sam")
    ran = []

    def run(args, **kw):
        ran.append(args)
        if args[:2] == ["loginctl", "enable-linger"] and not ran_fail:
            (linger / "sam").touch()
        if args[:2] == ["loginctl", "disable-linger"]:
            (linger / "sam").unlink(missing_ok=True)
        return types.SimpleNamespace(ok=not ran_fail, code=1 if ran_fail else 0, out="", err="")

    ran_fail = []
    monkeypatch.setattr(autostart.proc, "run", run)
    cfg = tmp_path / "config"
    cfg.mkdir()
    return types.SimpleNamespace(
        settings=Settings(cfg / "settings.json"),
        secrets=Secrets(cfg),
        state=tmp_path / "state",
        linger=linger,
        ran=ran,
        fail=ran_fail,
    )


def test_boot_turns_lingering_on_and_login_turns_only_ours_off(boot):
    (boot.state).mkdir()
    ok, msg = autostart.set_when("boot", boot.settings, boot.secrets, boot.state)
    assert ok and msg.startswith("Kurooto now starts when this computer starts")
    assert ["loginctl", "enable-linger"] in boot.ran and autostart.lingering()
    assert autostart.when(boot.settings) == "boot" and boot.secrets.in_file_marker.exists()
    ok, msg = autostart.set_when("login", boot.settings, boot.secrets, boot.state)
    assert ok and msg == "Kurooto starts when you log in." and not autostart.lingering()
    assert not boot.secrets.in_file_marker.exists()
    # lingering someone else turned on is left alone
    (boot.linger / "sam").touch()
    boot.ran.clear()
    ok, msg = autostart.set_when("boot", boot.settings, boot.secrets, boot.state)
    assert ok and boot.ran == []
    ok, msg = autostart.set_when("login", boot.settings, boot.secrets, boot.state)
    assert "not by Kurooto" in msg and autostart.lingering() and boot.ran == []


def test_boot_refused_or_elsewhere(boot, monkeypatch):
    boot.fail.append(True)
    ok, msg = autostart.set_when("boot", boot.settings, boot.secrets, boot.state)
    assert not ok and "loginctl enable-linger" in msg and autostart.when(boot.settings) == "login"
    for plat, says in (("win32", "Windows starts Kurooto when you sign in"), ("darwin", "automatic login")):
        monkeypatch.setattr(autostart.sys, "platform", plat)
        ok, msg = autostart.set_when("boot", boot.settings, boot.secrets, boot.state)
        assert not ok and says in msg


def test_secrets_move_to_the_file_and_back(tmp_path):
    class Keyring:
        def __init__(self):
            self.vals = {"telegram.token": "not-a-real-value"}

        def get_password(self, service, name):
            return self.vals.get(name)

        def set_password(self, service, name, value):
            self.vals[name] = value

    s = Secrets(tmp_path)
    s._kr = kr = Keyring()
    assert s.kr is kr
    assert s.keep_in_file(True, ["telegram.token", "gemini.api_key"]) == 1
    assert s.kr is None and s.get("telegram.token") == "not-a-real-value"
    s.set("gemini.api_key", "new-key-7890")  # while kept in the file, new ones go there too
    assert "gemini.api_key" not in kr.vals
    assert s.keep_in_file(False, []) == 2
    assert kr.vals["gemini.api_key"] == "new-key-7890" and s.names() == []


def test_cli_idle_and_autostart(tmp_path, monkeypatch, capsys):
    from kurooto import cli

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    monkeypatch.setenv("KUROOTO_NO_AUTOSTART", "1")
    assert cli.main(["idle", "away"]) == 0
    assert json.loads((tmp_path / "state" / "away.json").read_text())["since"] > 0
    assert cli.main(["idle", "back"]) == 0 and not (tmp_path / "state" / "away.json").exists()
    assert cli.main(["autostart", "boot"]) == 0
    assert "left alone here" in capsys.readouterr().out


# ----------------------------------------------------------------------------------- notes sync clashes
needs_git = pytest.mark.skipif(not shutil.which("git"), reason="needs git")


def git(cwd, *args):
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def synced(env, tmp_path):
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    env.app.settings.set("notes_sync.remote", str(remote))
    ns = env.app.modules["notes_sync"]
    ws = env.app.workspace
    (ws / "a.md").write_text("# A\n\nfirst\n")
    assert ns.first_sync()[0]
    phone = tmp_path / "phone"
    git(tmp_path, "clone", "-q", str(remote), str(phone))
    return ns, ws, phone, remote


def phone_edit(phone, text=None, delete=False):
    if delete:
        git(phone, "rm", "-q", "a.md")
    else:
        (phone / "a.md").write_text(text)
    git(phone, "commit", "-qam", "phone")
    git(phone, "push", "-q", "origin", "main")


@needs_git
def test_stop_mode_changes_nothing_and_says_so_once(env, tmp_path):
    ns, ws, phone, remote = synced(env, tmp_path)
    env.app.settings.set("notes_sync.on_conflict", "stop")
    phone_edit(phone, "# A\n\nphone\n")
    (ws / "a.md").write_text("# A\n\nlaptop\n")
    ok, why = ns.sync()
    assert not ok and "nothing was changed" in why
    assert (ws / "a.md").read_text() == "# A\n\nlaptop\n" and not list(ws.glob("a (conflict*"))
    assert git(tmp_path, "--git-dir", str(remote), "show", "main:a.md") == "# A\n\nphone\n"
    n = len(env.fake.texts())
    assert not ns.sync()[0] and len(env.fake.texts()) == n  # told once
    # a merge left half done (you, sorting it out): sync keeps out of it
    (ws / ".git" / "MERGE_HEAD").write_text("0" * 40)
    assert "unfinished" in ns.sync()[1]


@needs_git
def test_deleted_on_the_phone_changed_here_keeps_the_note(env, tmp_path):
    ns, ws, phone, remote = synced(env, tmp_path)
    phone_edit(phone, delete=True)
    (ws / "a.md").write_text("# A\n\nlaptop\n")
    assert ns.sync()[0]
    assert (ws / "a.md").read_text() == "# A\n\nlaptop\n" and not list(ws.glob("a (conflict*"))


@needs_git
def test_an_existing_origin_is_kept(env, tmp_path):
    ns = env.app.modules["notes_sync"]
    env.app.settings.set("notes_sync.repo", "sam/notes")
    assert ns.same_repo("ssh://github.com/sam/notes.git") and ns.same_repo("https://github.com/Sam/notes")
    assert ns.same_repo("github.com:sam/notes.git") and not ns.same_repo("github.com:sam/other.git")
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    env.app.settings.set("notes_sync.remote", str(remote))
    ws = env.app.workspace
    git(ws, "init", "-q", "-b", "main")
    git(ws, "remote", "add", "origin", "https://example.invalid/their-own.git")
    (ws / "a.md").write_text("x\n")
    assert ns.first_sync()[0]
    assert git(ws, "remote", "get-url", "origin").strip() == "https://example.invalid/their-own.git"
    assert git(ws, "remote", "get-url", "kurooto").strip() == str(remote)
    assert "a.md" in git(tmp_path, "--git-dir", str(remote), "ls-tree", "-r", "--name-only", "main")
