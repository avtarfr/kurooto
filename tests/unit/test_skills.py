import datetime as dt
import json
import time
from pathlib import Path

import pytest

from kurooto.core.clock import now
from kurooto.modules import skills as sk
from kurooto.modules.library import Library, capture
from kurooto.modules.skills import Skills, all_skills, build, load_skill, make, parse, parse_every, skill_prompt
from tests.fakes.openai import FakeOpenAI

SHIPPED = {
    "journal",
    "study-log",
    "add-to-notes",
    "assignment",
    "connect-notes",
    "term-setup",
    "goodnight",
    "morning",
    "morning-prep",
    "revision-pack",
}


@pytest.fixture
def ai(env):
    """The paired assistant with a fake AI, Chat, Skills and quick notes on."""
    fake = FakeOpenAI()
    app = env.app
    app.secrets.set("custom.api_key", fake.key)
    app.settings.set("brain.base_urls", {"custom": fake.base})
    app.settings.set("brain.models", {"custom": {"low": "m", "medium": "m", "high": "m"}})
    app.settings.set("brain.main", "custom")
    app.modules["skills"] = Skills(app)
    app.modules["library"] = Library(app)
    env.on("chat", "skills", "library")
    yield fake
    fake.close()


def docs(env):
    return [p for m, p in env.fake.sent if m == "sendDocument"]


def last_prompt(ai):
    return ai.requests[-1]["messages"][-1]["content"]


# ------------------------------------------------------------------------------------------ the files
def test_header_parsing_handles_quotes_and_missing_headers():
    meta, body = parse("---\nname: x\ndescription: 'It''s quoted: yes'\nother: \"a \\\"b\\\"\"\n---\nBody\n")
    assert meta == {"name": "x", "description": "It's quoted: yes", "other": 'a "b"'} and body == "Body\n"
    assert parse("no header\n") == ({}, "no header\n")
    assert make("---\nname: Bad Name\n---\nbody", "", "x") is None  # names are lowercase-with-hyphens
    assert make("---\nname: ok-name\n---\n\n", "", "x") is None  # no instructions
    s = make("---\nname: ok-name\neffort: extreme\n---\nDo it.", "", "x")
    assert s.effort == "auto" and s.description == "ok-name"


def test_every_shipped_skill_is_generic_and_complete(env):
    found = all_skills(env.app)
    assert SHIPPED <= set(found)
    for name in SHIPPED:
        s = found[name]
        assert s.source == "shipped" and s.effort in ("low", "medium", "high") and s.description != name
        assert "$ARGUMENTS" in s.body and s.args, name
        text = Path(s.path).read_text(encoding="utf-8")  # the privacy scanner guards personal details
        assert "journal/" in text or "<subject>/" in text or "[[" in text, name  # Kurooto's notes layout
        assert "shell command" not in text and "python" not in text.lower(), name  # the tools, not programs
    assert found["revision-pack"].output == "latex"


def test_your_skills_and_prompts_replace_shipped_ones(env):
    ws = env.app.workspace
    (ws / "kurooto/skills/journal").mkdir(parents=True)
    (ws / "kurooto/skills/journal/SKILL.md").write_text("---\nname: journal\neffort: low\n---\nMine: $ARGUMENTS\n")
    (ws / "prompts/sub").mkdir(parents=True)
    (ws / "prompts/sub/tldr.md").write_text("---\ntitle: TL;DR\nskill: true\ndescription: shorten\n---\nShorten.\n")
    (ws / "prompts/other.md").write_text("---\nskill: haiku-me\n---\nA haiku about $ARGUMENTS\n")
    (ws / "prompts/plain.md").write_text("---\ntitle: Plain\n---\nNot a skill.\n")
    found = all_skills(env.app)
    assert found["journal"].source == "yours" and found["journal"].effort == "low"
    assert found["tldr"].source == "prompt" and found["haiku-me"].source == "prompt"
    assert "plain" not in found
    p = skill_prompt(env.app, "haiku-me", "autumn")
    assert "A haiku about autumn" in p and "Never delete, reorder or reword" in p
    assert skill_prompt(env.app, "nope") is None


def test_arguments_are_filled_in_or_appended_with_files(env):
    s = make("---\nname: a-b\n---\nNo placeholder here.", "", "x")
    f = env.app.workspace / "inbox" / "slides.pdf"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"%PDF")
    out = build(env.app, s, "lecture 3", [f])
    assert "What they gave you: lecture 3" in out and "inbox/slides.pdf" in out
    assert "(nothing given)" in build(env.app, load_skill(env.app, "journal"), "")


# ----------------------------------------------------------------------------------------- running
def test_a_typed_skill_runs_and_a_reply_carries_on(env, ai):
    ai.answer = "Saved your entry in journal/today."
    assert env.say("/journal Finished the essay draft, felt good") == "On it."
    assert env.app.jobs.run_next()
    prompt = last_prompt(ai)
    assert "Finished the essay draft, felt good" in prompt and "Skill: journal" in prompt
    answer = env.fake.texts()[-1]
    assert answer.startswith("[") and answer.endswith("Saved your entry in journal/today.")
    assert "/journal Finished the essay" in answer.split("\n")[0]
    ai.answer = "Added the meeting."
    assert env.reply_to_last("also add: meeting at 4") == "On it."
    env.app.jobs.run_next()
    p = last_prompt(ai)
    assert "also add: meeting at 4" in p and "Saved your entry in journal/today." in p  # it knows what it said


def test_multiline_commands_and_unknown_ones(env, ai):
    assert env.say("/journal\nLine one\nLine two") == "On it."
    assert "Line one\nLine two" in env.app.jobs.get(env.app.jobs.recent(1)[0].id).prompt
    env.say("/no-such-skill hello")  # not a skill: Chat answers it as before
    assert env.app.jobs.recent(1)[0].prompt.startswith("/no-such-skill")


def test_internal_skills_are_hidden_but_runnable(env, ai):
    d = env.app.workspace / "kurooto/skills/look-back"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("---\nname: look-back\ninternal: true\n---\nLook back at $ARGUMENTS\n")
    assert "look-back" not in env.say("/skills")
    env.say("/look-back the week")
    assert not env.app.jobs.recent(1)[0].prompt.startswith("Skill: look-back")  # not run as a skill
    jid = env.app.modules["skills"].run("look-back", "the week", quiet=True)
    assert "Look back at the week" in env.app.jobs.get(jid).prompt


def test_skills_list_details_and_copy(env, ai):
    out = env.say("/skills")
    assert "/journal" in out and "/revision-pack" in out and "/newskill" in out
    assert "Effort: high" in env.say("/skills study-log")
    out = env.say("/skills copy morning")
    copy = env.app.workspace / "kurooto/skills/morning/SKILL.md"
    assert "kurooto/skills/morning/SKILL.md" in out and copy.is_file()
    assert load_skill(env.app, "morning").source == "yours"
    assert env.app.modules["skills"].customize("morning") == copy  # a second copy never overwrites yours


# -------------------------------------------------------------------------------------- new skills
DRAFT = """Here it is:

```markdown
---
name: weekly-review
description: Turn the week's daily notes into a short review
effort: medium
args: anything to focus on
---
1. Read journal/ for the last 7 days.
2. Write a review in journal/<today> under ## Weekly review: $ARGUMENTS
```
"""


def test_newskill_is_shown_in_full_and_saved_only_on_save(env, ai):
    ai.answer = DRAFT
    assert "before anything is saved" in env.say("/newskill a weekly review from my daily notes")
    env.app.jobs.run_next()
    assert "search_notes" in last_prompt(ai) and "journal" in last_prompt(ai)  # it knows the tools and names taken
    shown = env.fake.texts()[-1]
    assert "/weekly-review" in shown and "## Weekly review" in shown
    sent = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
    buttons = [b["callback_data"] for row in sent["reply_markup"]["inline_keyboard"] for b in row]
    assert not (env.app.workspace / "kurooto/skills/weekly-review").exists()
    assert env.press(buttons[0]) == "Saved as /weekly-review"
    saved = env.app.workspace / "kurooto/skills/weekly-review/SKILL.md"
    assert saved.is_file() and "Turn the week's daily notes" in saved.read_text()
    assert env.press(buttons[0]) == "That draft is gone."
    assert env.say("/weekly-review exams") == "On it."


def test_newskill_discard_bad_drafts_and_taken_names(env, ai):
    ai.answer = DRAFT.replace("weekly-review", "journal")
    env.say("/newskill another journal")
    env.app.jobs.run_next()
    assert "/journal-2" in env.fake.texts()[-1]  # never takes a shipped skill's or a command's name
    sent = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
    discard = sent["reply_markup"]["inline_keyboard"][0][1]["callback_data"]
    assert env.press(discard) == "Discarded."
    assert not (env.app.workspace / "kurooto/skills/journal-2").exists()
    ai.answer = "I'd rather not."
    env.say("/newskill something")
    env.app.jobs.run_next()
    assert "wasn't a usable skill" in env.fake.texts()[-1]
    ai.answer = DRAFT.replace("weekly-review", "remind")
    env.say("/newskill reminders")
    env.app.jobs.run_next()
    assert "/remind-2" in env.fake.texts()[-1]


# ---------------------------------------------------------------------------------------- routines
def test_reading_schedules():
    r = parse_every("monday 9:00 /journal plan my week")
    assert r["spec"] == "weekly mon 09:00" and r["only"] is None and r["what"] == "/journal plan my week"
    r = parse_every("every friday at 6pm send me a summary of my week")
    assert r["spec"] == "weekly fri 18:00" and r["what"] == "send me a summary of my week"
    r = parse_every("weekdays 7:45 /morning-prep")
    assert r["spec"] == "daily 07:45" and r["only"] == [0, 1, 2, 3, 4]
    r = parse_every("mon, thu 20:00 /connect-notes")
    assert r["spec"] == "daily 20:00" and r["only"] == [0, 3] and r["label"].startswith("Mon, Thu")
    assert parse_every("daily 21:30 how was my day?")["spec"] == "daily 21:30"
    for bad in ("", "monday /journal", "someday 9:00 x", "monday 25:00 x", "monday 9:00"):
        with pytest.raises(ValueError):
            parse_every(bad)


def test_routines_run_list_and_cancel(env, ai):
    sm = env.app.modules["skills"]
    out = env.say("/every monday 9:00 /journal plan my week")
    assert out.startswith("Mondays") is False and "Mon at 09:00" in out
    r = sm.routines()[0]
    job = env.app.scheduler.get(f"skills:routine:{r['id']}")
    assert job.spec == "weekly mon 09:00" and job.when.astimezone().strftime("%a %H:%M") == "Mon 09:00"
    assert "There's no /nonsense" in env.say("/every daily 9:00 /nonsense")
    assert "can't set up routines" in env.say("/every daily 9:00 /every daily 10:00 /journal")
    sm._routine({"id": r["id"]})
    assert env.app.jobs.recent(1)[0].title.startswith("Routine: /journal")
    assert "Skill: journal" in env.app.jobs.recent(1)[0].prompt
    env.say("/routines")
    sent = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
    cancel = sent["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    assert env.press(cancel) == "Cancelled." and sm.routines() == []
    assert env.app.scheduler.get(f"skills:routine:{r['id']}") is None
    assert sm._routine({"id": r["id"]}) == "gone"


def test_routines_survive_turning_skills_off_and_on(env, ai):
    env.say("/every daily 21:00 how was my day?")
    rid = env.app.modules["skills"].routines()[0]["id"]
    env.app.disable("skills")
    assert env.app.scheduler.get(f"skills:routine:{rid}") is None
    env.on("skills")
    assert env.app.scheduler.get(f"skills:routine:{rid}") is not None


def test_routine_days_commands_and_plain_requests(env, ai):
    sm = env.app.modules["skills"]
    other = [d for d in range(7) if d != now().weekday()][:2]
    days = ",".join(sk.DAYS[d] for d in other)
    env.say(f"/every {days} 8:00 /journal x")
    assert sm._routine({"id": sm.routines()[-1]["id"]}) == "not today"
    env.say("/every daily 8:00 /routines")  # any command works too; its answer comes as a message
    n = len(env.fake.texts())
    assert sm._routine({"id": sm.routines()[-1]["id"]}) == "ran"
    for _ in range(50):
        if len(env.fake.texts()) > n:
            break
        time.sleep(0.05)
    assert "Every day at 08:00: /routines" in env.fake.texts()[-1]
    out = env.say("every friday at 6pm send me a summary of my week")  # plain English
    assert "Fri at 18:00" in out
    before = len(sm.routines())
    env.say("every monday at 9 I have a lab")  # a fact, not a request: no routine
    assert len(sm.routines()) == before
    jid = sm._routine({"id": sm.routines()[-1]["id"]})
    assert env.app.jobs.get(jid).prompt == "send me a summary of my week"


# ----------------------------------------------------------------------------------- revision packs
TEX = r"""\documentclass[10pt]{article}
\begin{document}
Rank--nullity.
\end{document}"""


def pack_answer(tex=TEX):
    return f"```latex\n{tex}\n```\nCovers rank-nullity."


def wait_for(cond, secs=5.0):
    end = time.time() + secs
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


def test_pack_without_tectonic_sends_the_tex_and_offers_the_install(env, ai, monkeypatch):
    monkeypatch.setattr(sk, "tectonic", lambda app: None)
    env.on("subjects")
    env.say("/subject add Linear Algebra (la)")
    assert "as LaTeX" in env.say("/pack la midterm friday")
    ai.answer = pack_answer()
    env.app.jobs.run_next()
    p = last_prompt(ai)
    assert "Subject: Linear Algebra" in p and "linear-algebra/" in p and "midterm friday" in p
    tex = env.app.workspace / "linear-algebra" / f"revision-pack-{now():%Y-%m-%d}.tex"
    assert wait_for(lambda: len(docs(env)) == 1 and "Install Tectonic" in str(env.fake.sent[-1]))
    assert tex.read_text().startswith("\\documentclass")
    q = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
    no = q["reply_markup"]["inline_keyboard"][0][1]["callback_data"]
    assert env.press(no).startswith("OK")
    env.say("/pack la again")  # declined: not asked again this month, and the old pack is kept
    env.app.jobs.run_next()
    assert wait_for(lambda: len(docs(env)) == 2)
    assert tex.with_name(tex.stem + "-2.tex").is_file()
    assert sum("Install Tectonic so" in (t or "") for t in env.fake.texts()) == 1


def test_pack_compiles_sends_the_pdf_and_links_it(env, ai, monkeypatch):
    monkeypatch.setattr(sk, "tectonic", lambda app: "/fake/tectonic")

    def fake_compile(app, tex, timeout=900):
        tex.with_suffix(".pdf").write_bytes(b"%PDF-1.7 fake")
        return True, ""

    monkeypatch.setattr(sk, "compile_tex", fake_compile)
    env.say("/pack Topology: final exam")  # no such subject: a pack of its own
    ai.answer = pack_answer()
    env.app.jobs.run_next()
    pdf = env.app.workspace / "revision-packs" / f"{now():%Y-%m-%d}-topology.pdf"
    assert wait_for(lambda: len(docs(env)) == 1)
    assert pdf.is_file()
    daily = (env.app.workspace / "journal" / f"{now():%Y-%m-%d}.md").read_text()
    assert "## Added" in daily and "revision-packs/" in daily and "Revision pack: Topology" in daily


def test_a_pack_that_fails_to_compile_gets_one_fix(env, ai, monkeypatch):
    monkeypatch.setattr(sk, "tectonic", lambda app: "/fake/tectonic")
    calls = []

    def failing(app, tex, timeout=900):
        calls.append(tex.read_text())
        return False, "error: Undefined control sequence \\foo"

    monkeypatch.setattr(sk, "compile_tex", failing)
    env.say("/pack calculus")
    ai.answer = pack_answer()
    env.app.jobs.run_next()
    assert wait_for(lambda: env.app.jobs.recent(1)[0].title.startswith("Fixing"))
    assert "Undefined control sequence" in env.app.jobs.recent(1)[0].prompt
    ai.answer = pack_answer(TEX.replace("Rank", "Fixed rank"))
    env.app.jobs.run_next()
    assert wait_for(lambda: len(docs(env)) == 1)  # gave up after the fix: the .tex comes instead
    assert len(calls) == 2 and "Fixed rank" in calls[1]
    assert len(list((env.app.workspace / "revision-packs").glob("*.tex"))) == 1  # the fix replaced its own file


def test_an_answer_without_latex_is_delivered_as_is(env, ai, monkeypatch):
    env.say("/pack biology")
    ai.answer = "I couldn't find any biology notes."
    env.app.jobs.run_next()
    assert "couldn't find any biology notes" in env.fake.texts()[-1] and "no PDF" in env.fake.texts()[-1]


def test_real_tectonic_compile(tmp_path, env):
    """Runs only where Tectonic is installed (it fetches packages the first time)."""
    if not sk.tectonic(env.app):
        pytest.skip("Tectonic isn't installed here")
    f = tmp_path / "t.tex"
    f.write_text(TEX)
    ok, err = sk.compile_tex(env.app, f)
    assert ok, err


# --------------------------------------------------------------------------------------- send-file
def test_send_file_limits_and_api(env, ai, monkeypatch):
    from kurooto.web.api import Api

    f = env.app.workspace / "out.pdf"
    f.write_bytes(b"%PDF data")
    ok, msg = sk.send_file(env.app, f, "Here you go")
    assert ok and len(docs(env)) == 1
    assert sk.send_file(env.app, env.app.workspace / "missing.pdf")[0] is False
    (env.app.workspace / "empty.txt").write_text("")
    assert "empty" in sk.send_file(env.app, env.app.workspace / "empty.txt")[1]
    monkeypatch.setattr(sk, "TELEGRAM_MAX", 3)
    assert "up to 50 MB" in sk.send_file(env.app, f)[1]
    monkeypatch.setattr(sk, "TELEGRAM_MAX", 50 * 1024 * 1024)
    outside = env.app.paths.config / "settings.json"
    tool = next(t for t in env.app.modules["skills"].call_tools() if t.name == "send_file")
    assert "only send files from the notes" in tool.run({"path": str(outside)})
    assert tool.run({"path": "out.pdf"}).startswith("Sent out.pdf")
    r = Api(env.app).post("send-file", {"path": str(f), "caption": "From a script"})
    assert r == (200, {"ok": True, "message": "Sent out.pdf to your Telegram."})
    assert Api(env.app).post("send-file", {"path": ""})[1]["ok"] is False


def test_send_file_without_telegram(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    app = App()
    try:
        f = tmp_path / "a.txt"
        f.write_text("x")
        assert sk.send_file(app, f) == (False, "Telegram isn't set up, so there's nowhere to send it.")
    finally:
        app.close()


def test_cli_send_and_note(env, monkeypatch, capsys):
    from kurooto.cli import main

    assert main(["send", str(env.app.workspace / "nope.pdf")]) == 1
    f = env.app.workspace / "x.txt"
    f.write_text("x")
    assert main(["send", str(f)]) == 2  # not running here
    assert "isn't running" in capsys.readouterr().err
    assert main(["note", "--title", "Idea: graphs", "Use", "spectral", "methods"]) == 0
    path = Path(capsys.readouterr().out.strip())
    assert path.parent == env.app.workspace / "inbox" and path.name.endswith("-idea-graphs.md")
    text = path.read_text()
    assert 'title: "Idea: graphs"' in text and text.rstrip().endswith("Use spectral methods")


# ----------------------------------------------------------------------------------- quick notes
def test_note_command_with_files_and_no_overwrite(env, ai):
    out = env.say("/note Buy graph paper and a ruler")
    assert out.startswith("Saved to inbox/") and out.endswith("-buy-graph-paper-and-a-ruler.md.")
    f = env.app.workspace / out[len("Saved to ") : -1]
    assert f.read_text().rstrip().endswith("Buy graph paper and a ruler") and "source: telegram" in f.read_text()
    second = env.say("/note Buy graph paper and a ruler")
    assert second != out
    photo = env.app.workspace / "inbox" / "2026-10-19-120000-photo.jpg"
    photo.write_bytes(b"jpg")
    g = capture(env.app.workspace, "whiteboard", files=[photo])
    assert "[2026-10-19-120000-photo.jpg](2026-10-19-120000-photo.jpg)" in g.read_text()
    assert "What should I save?" in env.say("/note")


def test_prompt_library(env, ai):
    assert "No prompts yet" in env.say("/prompts")
    assert env.say("/prompt save Summarise\nSummarise this in 5 bullets:\n- keep numbers") == "Saved: /prompt summarise"
    (env.app.workspace / "prompts/writing").mkdir(parents=True)
    (env.app.workspace / "prompts/writing/tighten.md").write_text(
        "---\ntitle: Tighten prose\nskill: true\ndescription: tighten\n---\nTighten this: $ARGUMENTS\n"
    )
    listing = env.say("/prompts")
    assert "summarise" in listing and "writing/tighten (also /tighten): Tighten prose" in listing
    assert env.say("/prompt summarise") == "Summarise this in 5 bullets:\n- keep numbers"
    assert env.say("/prompt tighten prose") == "Tighten this: $ARGUMENTS"
    assert "No prompt matches" in env.say("/prompt zzz")
    assert env.say("/tighten my essay") == "On it."  # a prompt marked as a skill runs as one
    assert "Tighten this: my essay" in env.app.jobs.recent(1)[0].prompt


# ---------------------------------------------------------------------------------------- prereqs
def test_tectonic_is_pinned_with_checksums_for_every_system(tmp_path):
    from kurooto.core.prereqs import Prereqs

    for osn in ("windows", "macos", "linux"):
        p = Prereqs(tmp_path, tmp_path, os=osn).items["tectonic"]
        assert p.programs == ["tectonic"]
        for a in ("amd64", "arm64"):
            url, digest = p.step["urls"][a], p.step["sha256s"][a]
            assert url.startswith("https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40")
            assert len(digest) == 64 and int(digest, 16) >= 0


def test_download_tar_checks_its_checksum(tmp_path):
    import hashlib
    import io
    import sys
    import tarfile
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from kurooto.core.prereqs import Prereqs, arch

    b = io.BytesIO()
    with tarfile.open(fileobj=b, mode="w:gz") as t:
        data = b"#!/bin/sh\n"
        info = tarfile.TarInfo("tool")
        info.size, info.mode = len(data), 0o755
        t.addfile(info, io.BytesIO(data))
    blob = b.getvalue()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(blob)))
            self.end_headers()
            self.wfile.write(blob)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    osn = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    url = f"http://127.0.0.1:{srv.server_address[1]}/tool.tar.gz"
    try:
        for digest, good in (("0" * 64, False), (hashlib.sha256(blob).hexdigest(), True)):
            step = {"kind": "download-tar", "into": "{app}/tool", "urls": {arch(): url}, "sha256s": {arch(): digest}}
            m = Prereqs(
                tmp_path / "app",
                tmp_path / "cache",
                manifest={
                    "tool": {
                        "title": "Tool",
                        "programs": ["tool"],
                        "dirs": {osn: ["{app}/tool"]},
                        "install": {osn: step},
                    }
                },
            )
            ok, msg = m.install("tool", progress=lambda s: None, margin_gb=0)
            assert ("checksum" in msg) is not good
            assert (tmp_path / "app/tool/tool").exists() is good
    finally:
        srv.shutdown()


def test_day_names_are_mondays_first():
    assert sk.DAYS[dt.date(2026, 10, 19).weekday()] == "mon"
    assert json.loads(json.dumps(parse_every("sun 7:00 x")))["spec"] == "weekly sun 07:00"


def test_a_link_on_its_own_is_filed(env, ai):
    assert env.say("https://example.com/notes/fourier.pdf for signals") == "Filing it into your notes…"
    p = env.app.jobs.recent(1)[0].prompt
    assert "Skill: add-to-notes" in p and "https://example.com/notes/fourier.pdf for signals" in p
    env.say("can you summarise https://example.com/a")  # a request about a link goes to Chat
    assert env.app.jobs.recent(1)[0].prompt.startswith("can you summarise")
