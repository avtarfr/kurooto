"""The memory ledger: one encrypted store of what's remembered (gists, threads, how-to-help-me lines, daily notes,
project meetings), each row with its source and a Forget; only kinds, times and keyed hashes on disk; a key it can't
read writes and shows nothing; /memory finds, forgets and exports; "when did I last talk to ...?" and "what was I
doing last Thursday?" are answered from it by rules."""

import datetime as dt
import time

import pytest

from kurooto.core import gists, ledger, retention, threads
from kurooto.core.clock import now
from kurooto.modules import remember

SECRET_WORDS = (b"zeolite", b"glacier", b"Ortiz", b"forcing", b"topology")


def on_disk(app) -> bytes:
    """Every byte Kurooto keeps in its state folder (the ledger, its -wal and -shm, everything else)."""
    return b"".join(p.read_bytes() for p in app.paths.state.rglob("*") if p.is_file())


def last_thursday() -> dt.date:
    today = now().date()
    return today - dt.timedelta(days=(today.weekday() - 3) % 7 or 7)


@pytest.fixture
def notes(env):
    """A project note with a meeting, a daily note from last Thursday and a kept how-to-help-me line."""
    app = env.app
    proj = app.workspace / "research" / "glacier-flow" / "index.md"
    proj.parent.mkdir(parents=True)
    proj.write_text(
        "# Glacier flow\n\nWith: Prof Lena Ortiz (supervisor)\n\n## Meetings\n"
        "- 2026-10-20: met Ortiz, we fixed the forcing\n- 2026-10-02: first chat about the project\n\n## Log\n"
    )
    day = last_thursday()
    note = app.workspace / "journal" / f"{day.isoformat()}.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        f"# {day.isoformat()}\n\n## Plan\n\n- [ ] Topology problem set 3\n- Lab: zeolite samples\n\n"
        "## Evening check-in\n\nGot the topology set half done. My bank account is overdrawn.\n"
    )
    remember.keep(app, "I study best in the morning")
    return env, proj, note, day


def test_rows_are_sealed_and_nothing_readable_is_on_disk(notes):
    env, proj, note, day = notes
    app = env.app
    t = time.time() - 3600
    gists._save(app, [{"at": t, "kind": "call", "text": "Call (Lab): set reminder: book the zeolite slot"}])
    said = threads.observe(app, "I'll send the glacier draft to Ortiz tonight.")
    assert said == ["send the glacier draft to Ortiz tonight"]
    led = ledger.of(app)
    led.refresh(force=True)
    kinds = sorted({r["kind"] for r in led.rows()})
    assert kinds == ["day", "fact", "gist", "meeting", "thread"]
    assert gists.load(app) == [{"at": t, "kind": "call", "text": "Call (Lab): set reminder: book the zeolite slot"}]
    # the key is a secret (the owner-only secrets file here: KUROOTO_HOME has no keychain), never in the state folder
    key = app.secrets.get(ledger.KEY)
    assert key and len(key) == 44 and key.encode() not in on_disk(app)
    led._db.execute("pragma wal_checkpoint(full)")
    raw = on_disk(app)
    assert not [w for w in SECRET_WORDS if w in raw]  # no words, no note paths: only kinds, times and keyed hashes
    assert not (app.paths.state / "gists.jsonl").exists()
    assert "overdrawn" not in " ".join(r["text"] for r in led.rows())  # a money line of the journal is left out

    # another key opens nothing (and says so in the event log, by count only)
    other = ledger.Ledger(app)
    other._key = b"\x01" * 32
    assert other.rows() == []
    assert app.events.tail(5, kinds=["ledger_unreadable"])
    other.close()


def test_a_key_it_cant_read_writes_and_shows_nothing(notes):
    env, proj, note, day = notes
    app = env.app
    gists._save(app, [{"at": time.time(), "kind": "chat", "text": "what is a compact space"}])
    key = app.secrets.get(ledger.KEY)
    app.secrets.delete(ledger.KEY)  # a keychain still locked at boot
    ledger.close(app)
    assert gists.load(app) == []
    with pytest.raises(ledger.Locked):
        gists._save(app, [])  # nothing changes, and no new key is made over the old rows
    assert app.secrets.get(ledger.KEY) is None
    assert env.say("/memory") == ledger.LOCKED
    app.secrets.set(ledger.KEY, key)
    ledger.close(app)
    assert [g["text"] for g in gists.load(app)] == ["what is a compact space"]


def test_old_gists_move_into_the_ledger(env):
    app = env.app
    old = '{"at": 5.0, "kind": "request", "text": "plan my topology revision"}\n'
    (app.paths.state / "gists.jsonl").write_text(old)
    assert [g["text"] for g in gists.load(app)] == ["plan my topology revision"]
    assert not (app.paths.state / "gists.jsonl").exists()
    assert b"topology" not in on_disk(app)


def test_when_did_i_last_talk_and_what_was_i_doing(notes):
    env, proj, note, day = notes
    out = env.say("when did I last talk to Prof Lena Ortiz?")
    assert out.startswith("Last: Tue 20 Oct") and "fixed the forcing" in out and "research/glacier-flow" in out
    assert "Before that:" in out and "first chat" in out
    assert "nothing with Prof Okafor" in env.say("when did I last meet Prof Okafor?")
    out = env.say("what was I doing last Thursday?")
    assert out.startswith(f"{day:%a %d %b}:") and "Topology problem set 3" in out and "zeolite" in out
    assert "overdrawn" not in out
    assert ledger.a_past_day("on 20 Oct", dt.date(2026, 10, 23)) == dt.date(2026, 10, 20)
    assert ledger.a_past_day("last thursday", dt.date(2026, 10, 23)) == dt.date(2026, 10, 22)
    assert ledger.a_past_day("thursday", dt.date(2026, 10, 22)) == dt.date(2026, 10, 15)  # the one before today


def test_memory_lists_forgets_and_exports(notes):
    env, proj, note, day = notes
    app = env.app
    threads.observe(app, "I need to email the glacier draft to Ortiz.")
    gists._save(app, [{"at": time.time() - 60, "kind": "call", "text": "Call: set reminder: book the zeolite slot"}])
    out = env.say("/memory")
    assert out.startswith("What I remember (") and "encrypted on this computer" in out
    out = env.say("/memory forcing")
    n = out.split("\n")[1].split(".")[0]
    assert "met Ortiz, we fixed the forcing" in out
    said = env.say(f"/memory forget {n}")
    assert said.startswith("Forgot it: Meeting with Prof Lena Ortiz") and "still in your note" in said
    meet = "## Meetings\n- 2026-10-22: Ortiz liked the plots\n"
    proj.write_text(proj.read_text().replace("## Meetings\n", meet))  # the note changes: it's read again
    out = env.say("/memory Ortiz")
    assert "liked the plots" in out and "fixed the forcing" not in out  # forgotten here stays forgotten
    assert "fixed the forcing" in proj.read_text()  # the note is yours

    out = env.say("/memory morning")
    n = out.split("\n")[1].split(".")[0]
    assert "Taken out of about-me/how-to-help-me.md too" in env.say(f"/memory forget {n}")
    assert "study best in the morning" not in remember.help_file(app).read_text()

    out = env.say("/memory export")
    assert out.startswith("Wrote 2 lines (gists and threads) to inbox/memory-")
    (f,) = (app.workspace / "inbox").glob("memory-*.md")
    text = f.read_text()
    assert "## Threads" in text and "email the glacier draft to Ortiz" in text and "book the zeolite slot" in text


def test_forget_covers_threads_and_the_gists(notes):
    env, proj, note, day = notes
    app = env.app
    threads.observe(app, "I'll send the glacier draft tonight.")
    gists._save(app, [{"at": time.time() - 60, "kind": "chat", "text": "what is a compact space"}])
    out = retention.summary(retention.forget(app, time.time() - 3600))
    assert "1 thread" in out and threads.open_threads(app) == []
    assert len(gists.load(app)) == 1  # /forget 7d keeps the gists
    assert gists.clear(app) == 1 and gists.load(app) == []  # /forget all → Forget gists too


def test_backups_leave_it_out_unless_chosen_and_the_profile_never_carries_its_key(env):
    from kurooto.core import profile
    from kurooto.modules import backups

    app = env.app
    threads.observe(app, "I'll send the glacier draft tonight.")
    names = [n for n, _ in backups.sources(app.paths, None, notes=False, secrets=False, index=True)]
    assert "state/ledger.db" not in names and "state/jobs.db" in names
    names = [n for n, _ in backups.sources(app.paths, None, notes=False, secrets=False, index=True, memory=True)]
    assert "state/ledger.db" in names
    assert ledger.KEY not in profile.secret_names(app)


def test_a_nightly_day_row_from_events_only(env):
    """L91 (0.9.0, memory.day_rows, off): the desk in coarse words, study minutes by subject, classes by your taps."""
    import json as _json

    app = env.app
    day = dt.date.today() - dt.timedelta(days=1)
    at = lambda h, m=0: dt.datetime.combine(day, dt.time(h, m)).isoformat(timespec="seconds")  # noqa: E731
    with open(app.paths.state / "events.jsonl", "a", encoding="utf-8") as f:
        for rec in (
            {"ts": at(9), "kind": "face_back"},
            {"ts": at(12, 10), "kind": "face_left"},
            {"ts": at(14), "kind": "study_logged", "subject": "la", "minutes": 50},
            {"ts": at(16), "kind": "study_session_end", "subject": "la", "minutes": 40},
            {"ts": at(8), "kind": "class_skip", "subjects": ["topo"]},
        ):
            f.write(_json.dumps(rec) + "\n")
    text = ledger.day_row(app, day)
    assert text == "at the desk about 3 h; studied la 1 h 30 min; skipped topo."
    assert ledger.write_day_row(app, day) is False  # off by default
    app.settings.set("memory.day_rows", True)
    assert ledger.write_day_row(app, day) and ledger.write_day_row(app, day)
    rows = ledger.of(app).rows(("dayrow",))
    assert len(rows) == 1 and rows[0]["text"] == text  # sealed, and one a day
    assert "The day in short: at the desk about 3 h" in ledger.day_story(app, day)
