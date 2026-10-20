"""WS4: research parity (arXiv searches in arXiv's own words, the digest kept as a note, runs kept in repositories,
the Python `Run`, the reminder call), handwriting read page by page by a model on this computer, revision packs the
evening before an exam, and "use my own GBrain". Fakes only: no network, no real models, and a fake gbrain first on
PATH so the real one can never run."""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time

import pytest

from kurooto.core.clock import now
from kurooto.modules import research as rmod
from tests.unit.test_books import make_pdf
from tests.unit.test_research import FakeSources
from tests.unit.test_skills import ai  # noqa: F401 (fixture)


# ================================================================================================== research
@pytest.fixture
def research(env, monkeypatch):
    fake = FakeSources()
    env.app.settings.set(
        "research.endpoints",
        {"arxiv": f"{fake.base}/arxiv", "biorxiv": f"{fake.base}/details", "pubmed": f"{fake.base}/eutils"},
    )
    monkeypatch.setattr(rmod, "ARXIV_GAP", 0)
    yield env, fake, env.app.modules["research"]
    fake.server.shutdown()


def test_arxiv_searches_in_its_own_words_named_and_kept_as_a_note(research):
    env, fake, r = research
    q = 'abs:"graph neural network" AND (abs:molecule OR abs:protein)'
    f = rmod.validate({"type": "arxiv", "name": " Molecules ", "query": f"  {q} "})
    assert f == {"type": "arxiv", "query": q, "categories": [], "keywords": [], "name": "Molecules"}
    with pytest.raises(ValueError):
        rmod.validate({"type": "arxiv", "query": "(abs:x"})
    assert rmod.describe(f) == f"Molecules — arXiv: {q}"
    assert len(r.fetch(f)) == 2 and fake.queries[-1] == f"({q})"  # as written; no keyword words added
    r.fetch({"type": "arxiv", "query": "ti:galaxy", "categories": ["astro-ph.GA"], "keywords": ["galaxy"]})
    assert fake.queries[-1] == "(ti:galaxy) AND (cat:astro-ph.GA)"

    rss = {"type": "rss", "url": f"{fake.base}/rss", "keywords": []}
    env.app.settings.set("research.feeds", [f, {"type": "arxiv", "name": "Galaxies", "query": "ti:galaxy"}, rss])
    env.app.settings.set("research.save_note", True)
    env.on("research")
    assert len(r.papers()) == 3  # the second search finds only papers the first one had
    note = env.app.workspace / "inbox" / f"papers-{now():%Y-%m-%d}.md"
    text = note.read_text(encoding="utf-8")
    assert "## Molecules" in text and "## Feed: " in text and "## Galaxies" not in text
    assert "- [Graph networks for molecules](https://arxiv.org/abs/2610.00001) · A. Author" in text
    assert f"All 3 are in inbox/papers-{now():%Y-%m-%d}.md." in env.fake.texts()[-1]
    assert r.papers() == [] and note.read_text(encoding="utf-8") == text


def git(repo, *a):
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", *a],
        check=True,
        capture_output=True,
    )


@pytest.mark.skipif(not shutil.which("git"), reason="needs git")
def test_runs_kept_in_a_repository_reach_the_project_log(env, tmp_path, monkeypatch):
    from kurooto.runlog import Run

    repo = tmp_path / "solver"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "fit.py").write_text("x")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "the model")
    monkeypatch.chdir(repo)
    monkeypatch.delenv("RUNLOG_DIR", raising=False)
    monkeypatch.delenv("KUROOTO_PROJECT", raising=False)
    with Run("lr sweep", config={"lr": 0.01}) as run:
        run.log(step=1, loss=0.5)
        run.note("fine")
    with pytest.raises(ValueError), Run("boom") as bad:
        raise ValueError("diverged")
    meta = json.loads((repo / "runs" / bad.id / "meta.json").read_text())
    assert meta["status"] == "failed" and "ValueError: diverged" in meta["error"] and meta["commit"]
    assert json.loads((repo / "runs" / run.id / "config.json").read_text()) == {"lr": 0.01}
    assert (repo / "runs" / run.id / "metrics.jsonl").read_text().count("\n") == 1

    env.app.settings.set("research.topics", ["x"])
    env.on("research")
    env.say(f"/repos add {repo} as Solver")
    r = env.app.modules["research"]
    r.project_logs()
    log = (env.app.workspace / "research" / "solver" / "index.md").read_text(encoding="utf-8")
    assert f"run:solver/{run.id} — ok after 0s (step=1, loss=0.5)" in log
    assert f"run:solver/{bad.id} — failed after 0s" in log
    r.project_logs()
    again = (env.app.workspace / "research" / "solver" / "index.md").read_text(encoding="utf-8")
    assert again.count(run.id) == 1  # each run once


def test_a_run_into_the_notes_follows_the_layout(env, tmp_path, monkeypatch):
    from kurooto.runlog import Run

    env.app.settings.set("notes.layout", "zettelkasten")
    monkeypatch.chdir(tmp_path)
    with Run("fit", config={"lr": 0.1}, project="Thesis") as run:
        run.log(step=0, loss=1.25)
    ws = env.app.workspace
    d = ws / "projects" / "thesis" / "runs" / run.id
    assert json.loads((d / "meta.json").read_text())["status"] == "ok"
    assert "[[projects/thesis/index|Thesis]]" in (d / "run.md").read_text(encoding="utf-8")
    log = (ws / "projects" / "thesis" / "index.md").read_text(encoding="utf-8")
    assert f"[[projects/thesis/runs/{run.id}/run|details]]" in log and "loss=1.25" in log


class FakeCalls:
    def __init__(self):
        self.scheduled = []

    def ready(self):
        return True, ""

    def schedule(self, at, reason, key=None, alarm=False):
        self.scheduled.append((at, reason, key))
        return "ok"


def test_remind_me_tomorrow_is_a_call_when_calls_are_on(env, monkeypatch):
    r = env.app.modules["research"]
    q = {"hook_payload": {"project": "solver"}}
    assert r._idle_answer(q, "Remind me tomorrow") == "I'll remind you about solver tomorrow at 18:00."
    calls = FakeCalls()
    monkeypatch.setitem(env.app.modules, "calls", calls)
    real = env.app.is_on
    monkeypatch.setattr(env.app, "is_on", lambda m: m == "calls" or real(m))
    assert r._idle_answer(q, "Remind me tomorrow") == "I'll call you about solver tomorrow at 18:00."
    at, reason, key = calls.scheduled[0]
    assert at == dt.datetime.combine(now().date() + dt.timedelta(days=1), dt.time(18, 0))
    assert "solver" in reason and key == "research:solver"
    r.call_outcome(key, "missed")
    assert "Missed my call" in env.fake.texts()[-1]
    env.app.settings.set("research.remind_by_call", False)
    assert r._idle_answer(q, "Remind me tomorrow").startswith("I'll remind you")


# ============================================================================================== handwriting
GRAY = (4, 4, bytes(range(16)))


@pytest.fixture
def hw(env, monkeypatch):
    """Handwritten notes with a fake model on this computer, no Poppler, the GPU free, the night any time."""
    app = env.app
    app.settings.set("handwritten.local_model", "fake-vision")
    app.settings.set("handwritten.cloud", False)
    env.on("handwritten")
    h = app.modules["handwritten"]
    monkeypatch.setattr(h, "pdf_tools", lambda: {"pdftoppm": None, "pdfinfo": None, "pdftotext": None})
    monkeypatch.setattr(h, "gpu_room", lambda model: None)
    seen = []

    def read(model, data, prompt="x"):
        seen.append((model, prompt))
        page = prompt.split("page ", 1)[1].split(" ", 1)[0] if "page " in prompt else "?"
        return f"Page {page}: $\\int_0^1 f$"

    monkeypatch.setattr(h, "_ollama", read)
    return env, h, seen


def drop(folder, name, pages=3):
    f = folder / name
    make_pdf(f, [("image", GRAY)] * pages)
    os.utime(f, (time.time() - 60, time.time() - 60))
    return f


def test_a_pdf_is_read_page_by_page_at_night_and_resumes(hw, monkeypatch):
    env, h, seen = hw
    f = drop(h.folder(), "lecture_07-eigenvalues.pdf")
    monkeypatch.setattr(h, "in_hours", lambda t=None: False)
    assert h.scan() == [] and seen == []
    assert "at night" in env.fake.texts()[-1] and "3 pages" in env.fake.texts()[-1]
    told = len(env.fake.texts())
    h.scan()
    assert len(env.fake.texts()) == told  # told once
    monkeypatch.setattr(h, "in_hours", lambda t=None: True)
    unplug = {"after": 2}
    real = env.app.power.may_run
    monkeypatch.setattr(env.app.power, "may_run", lambda m: len(seen) < unplug["after"] and real(m))
    assert h.scan() == []  # unplugged after two pages
    assert len(seen) == 2 and len(list((h._cache(f.name) / "pages").glob("*.md"))) == 2
    unplug["after"] = 99
    done = h.scan()
    assert len(seen) == 3 and seen[-1] == ("fake-vision", h_prompt(3))  # carried on from page 3
    assert done == [f"handwritten/{now():%Y-%m-%d}-lecture-07-eigenvalues.md"]
    note = env.app.workspace / done[0]
    text = note.read_text(encoding="utf-8")
    assert "# Lecture 07 eigenvalues" in text and "## Page 1\n\nPage 1: $\\int_0^1 f$" in text
    assert "by fake-vision on this computer, 3 pages, unchecked" in text
    assert note.with_suffix(".pdf").read_bytes() == f.read_bytes()  # the copy next to the note
    assert not h._cache(f.name).exists()

    # you write under it; the page changes on the tablet: the same note, Kurooto's part again, yours kept
    note.write_text(text + "\nMy own remark.\n", encoding="utf-8")
    make_pdf(f, [("image", GRAY)] * 2)
    os.utime(f, (time.time() - 30, time.time() - 30))
    assert h.scan() == done
    text = note.read_text(encoding="utf-8")
    assert "My own remark." in text and "## Page 2" in text and "## Page 3" not in text and "2 pages" in text


def test_a_models_fence_is_taken_off():
    from kurooto.modules.handwritten import _tidy

    assert _tidy("```markdown\n# T\n\n$x$\n```") == "# T\n\n$x$"


def h_prompt(n):
    from kurooto.modules.handwritten import PAGE_PROMPT

    return PAGE_PROMPT.format(page=n)


def test_link_to_the_original_and_photos_right_away(hw, monkeypatch):
    env, h, seen = hw
    env.app.settings.set("handwritten.keep_original", "link")
    monkeypatch.setattr(h, "in_hours", lambda t=None: False)
    photo = h.folder() / "board.jpg"
    photo.write_bytes(b"\xff\xd8 fake jpeg")
    os.utime(photo, (time.time() - 60, time.time() - 60))
    done = h.scan()  # a photo doesn't wait for the night
    assert len(done) == 1 and seen[0][1].startswith("These are handwritten notes")
    text = (env.app.workspace / done[0]).read_text(encoding="utf-8")
    assert "(../handwritten-inbox/board.jpg)" in text and not list((env.app.workspace / "handwritten").glob("*.jpg"))


def test_without_poppler_a_drawn_pdf_needs_it_and_nothing_goes_to_the_cloud(hw):
    env, h, seen = hw
    f = h.folder() / "ink.pdf"
    make_pdf(f, [("text", "")])  # a page that is drawing, not a picture: only Poppler draws it
    os.utime(f, (time.time() - 60, time.time() - 60))
    assert h.scan(force=True) == [] and seen == []
    assert "Poppler" in env.fake.texts()[-1]
    assert "ink.pdf" in env.say("/handwritten status")


def test_the_card_must_have_room(env, monkeypatch):
    from contextlib import contextmanager

    from kurooto.modules.handwritten import Waiting

    h = env.app.modules["handwritten"]
    lm = env.app.modules["local_models"]
    loaded = {"models": []}

    @contextmanager
    def api(path, body=None, timeout=10):
        yield __import__("io").BytesIO(json.dumps(loaded).encode())

    monkeypatch.setattr(lm, "api", api)
    monkeypatch.setattr(lm, "wanted", lambda: [{"key": "helper-large", "tag": "gemma4:e4b", "size_gb": 6.6}])
    monkeypatch.setattr("kurooto.modules.handwritten.proc.which", lambda n, *a: "/x/nvidia-smi")
    used = {"mib": 6000}
    monkeypatch.setattr(
        "kurooto.modules.handwritten.proc.run",
        lambda args, **kw: __import__("kurooto.core.proc", fromlist=["Result"]).Result(0, f"{used['mib']}, 8188\n", ""),
    )
    with pytest.raises(Waiting):
        h.gpu_room("gemma4:e4b")  # a training run fills the card
    used["mib"] = 400
    h.gpu_room("gemma4:e4b")
    used["mib"] = 8000
    loaded["models"] = [{"name": "gemma4:e4b"}]
    h.gpu_room("gemma4:e4b")  # loaded already


def test_the_8gb_helper_reads_handwriting(env, monkeypatch):
    lm = env.app.modules["local_models"]
    hw_file = env.app.paths.state / "hardware.json"

    def rec(*keys):
        from kurooto.core.hardware import _models

        table = _models()["models"]
        models = [{"key": k, **{x: y for x, y in table[k].items() if x != "vision"}} for k in keys]
        hw_file.write_text(json.dumps({"recommendation": {"local_models": models}}))

    rec("embed", "helper-large")  # 8 GB (a recommendation saved before the flag existed)
    assert lm.vision_model()["tag"] == "gemma4:e4b"
    rec("embed", "helper-large", "vision")  # 12 GB
    assert lm.vision_model()["tag"] == "gemma4:12b"
    rec("embed", "helper-small")  # 4 GB: no
    assert lm.vision_model() is None
    h = env.app.modules["handwritten"]
    real = env.app.is_on
    monkeypatch.setattr(env.app, "is_on", lambda m: m == "local_models" or real(m))
    rec("embed", "helper-large")
    assert h.local_model() == "gemma4:e4b"
    env.app.settings.set("handwritten.local", False)
    assert h.local_model() is None


# ========================================================================================= revision packs
def test_a_pack_is_offered_the_evening_before_an_exam(env, ai, monkeypatch):  # noqa: F811
    from kurooto.modules import skills as smod

    env.on("deadlines")
    dl = env.app.modules["deadlines"]
    sk = env.app.modules["skills"]
    dl.add("Midterm", now() + dt.timedelta(hours=20), kind="exam", subject="linear-algebra")
    dl.add("Essay", now() + dt.timedelta(hours=20), kind="task", subject="linear-algebra")
    dl.add("Final", now() + dt.timedelta(days=5), kind="exam", subject="linear-algebra")
    evening = dt.datetime.combine(now().date(), dt.time(18, 0))
    monkeypatch.setattr(smod, "now", lambda: evening.replace(hour=15))
    assert sk.auto_packs() == 0  # not before 16:00
    monkeypatch.setattr(smod, "now", lambda: evening)
    assert sk.auto_packs() == 1 and sk.auto_packs() == 0  # once
    msg = env.fake.texts()[-1]
    assert "Midterm is in 20 h. A revision pack for it tonight?" in msg
    ref = next(iter(json.loads((sk.dir / "auto-packs.json").read_text())))
    before = len(env.app.jobs.recent(50))
    assert env.press(f"skp:{ref}:yes").startswith("Building it")
    job = env.app.jobs.recent(1)[0]
    assert len(env.app.jobs.recent(50)) == before + 1 and job.title.startswith("Before your exam: Revision pack:")
    assert "Midterm on " in job.prompt
    assert env.press(f"skp:{ref}:yes") == "It's on its way already."

    env.app.settings.set("skills.auto_pack", "auto")
    dl.add("Quiz 4", now() + dt.timedelta(hours=30), kind="exam", subject="probability")
    assert sk.auto_packs() == 1
    assert env.app.jobs.recent(1)[0].title.startswith("Before your exam: Revision pack:")
    env.app.settings.set("skills.auto_pack", "off")
    dl.add("Quiz 5", now() + dt.timedelta(hours=30), kind="exam", subject="probability")
    assert sk.auto_packs() == 0


# ====================================================================================== your own GBrain
FAKE_GBRAIN = """#!{python}
import json, os, sys
with open({log!r}, "a") as f:
    f.write(json.dumps({{"argv": sys.argv[1:], "home": os.environ.get("GBRAIN_HOME"), "cwd": os.getcwd()}}) + "\\n")
out = json.loads(os.environ.get("FAKE_GBRAIN_OUT") or "{{}}")
print(out.get(sys.argv[1] if len(sys.argv) > 1 else "", ""))
sys.exit(int(os.environ.get("FAKE_GBRAIN_EXIT", "0")))
"""


@pytest.fixture
def own_brain(env, tmp_path, monkeypatch):
    """A fake gbrain FIRST on PATH (the real one can never run), and a brain folder that isn't the real one."""
    if sys.platform == "win32":
        pytest.skip("the fake gbrain is a script with a #! line")
    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir()
    log = tmp_path / "gbrain.log"
    exe = bin_dir / "gbrain"
    exe.write_text(FAKE_GBRAIN.format(python=sys.executable, log=str(log)))
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setenv("GBRAIN_HOME", str(tmp_path / "not-a-brain"))
    assert shutil.which("gbrain") == str(exe)
    home = tmp_path / "my-brain"
    home.mkdir()
    s = env.app.settings
    s.set("gbrain.managed", False)
    s.set("gbrain.exe", str(exe))
    s.set("gbrain.home", str(home))

    def calls():
        return [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []

    return env, env.app.modules["gbrain"], home, exe, calls


def test_your_own_brain_is_used_never_created_or_migrated(own_brain, monkeypatch):
    env, g, home, exe, calls = own_brain
    assert g.external() and g.exe() == str(exe) and g.ready() == (True, "")
    ok, msg = g.setup(progress=lambda s: None)
    assert ok and msg == "Kurooto uses your own brain now."
    assert [c["argv"] for c in calls()] == [["search", "kurooto"]]  # no init, no migrations, no embeddings set-up
    assert all(c["home"] == str(home) and c["cwd"] == str(home) for c in calls())
    assert g.sync() == (True, "your brain keeps itself in step (no gbrain.source)") and len(calls()) == 1
    env.app.settings.set("gbrain.source", "notes")
    monkeypatch.setenv("FAKE_GBRAIN_OUT", json.dumps({"sync": "12 pages imported"}))
    assert g.sync() == (True, "12 pages imported")
    assert [c["argv"] for c in calls()[-2:]] == [
        ["sync", "--source", "notes", "--no-hard-deadline"],
        ["embed", "--stale", "--source", "notes"],
    ]
    n = len(calls())
    for refused in (("init", "--pglite"), ("apply-migrations", "--yes"), ("embeddings", "enable"), ("config", "set")):
        r = g.run(*refused)
        assert not r.ok and "doesn't own" in r.err
    assert len(calls()) == n
    assert g._button("x", "migrate") == "That checkup is old; the next one comes on Sunday."
    (env.app.paths.state / "gbrain-checkup.json").write_text(json.dumps({"r1": ["pending_migration"]}))
    assert g._button("r1", "migrate").startswith("Kurooto doesn't change a brain it doesn't own")
    assert len(calls()) == n


def test_the_nightly_steps_you_choose(own_brain):
    env, g, home, exe, calls = own_brain
    env.app.settings.set("gbrain.upkeep_steps", ["lint", "edge_contradictions", "purge", "rm -rf", "lint"])
    assert g.upkeep_steps() == ["lint", "edge_contradictions"]  # purge and unknown names never run
    g.upkeep()
    assert calls()[-1]["argv"] == ["dream", "--json", "--phase", "lint", "--phase", "edge_contradictions"]
    env.app.settings.set("gbrain.managed", True)  # Kurooto's own brain: over your notes folder, light steps
    env.app.settings.set("gbrain.upkeep_steps", [])
    assert g.upkeep_steps() == ["backlinks", "extract", "extract_facts", "embed", "orphans"]


def test_the_brain_found_on_path_and_a_missing_folder(own_brain, tmp_path):
    env, g, home, exe, calls = own_brain
    env.app.settings.set("gbrain.exe", "")
    assert g.exe() == str(exe)  # the fake, pinned first on PATH
    env.app.settings.set("gbrain.home", str(tmp_path / "gone"))
    assert g.ready() == (False, f"your brain's folder isn't there: {tmp_path / 'gone'} (gbrain.home)")
    env.app.settings.set("gbrain.exe", str(tmp_path / "nope"))
    assert not g.ready()[0] and "gbrain.exe" in g.ready()[1]


FAKE_AGY = """#!{python}
import json, os, sys
with open({log!r}, "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
if sys.argv[1:3] == ["mcp", "list"]:
    print(os.environ.get("FAKE_AGY_LIST", ""))
"""


def test_agy_gets_your_brains_own_tools_after_you_approve(own_brain, tmp_path, monkeypatch):
    from kurooto.providers import agy

    env, g, home, exe, calls = own_brain
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    log = tmp_path / "agy.log"
    fake_agy = tmp_path / "agy-fake"
    fake_agy.write_text(FAKE_AGY.format(python=sys.executable, log=str(log)))
    fake_agy.chmod(0o755)
    app = env.app
    env.on("gbrain")
    assert agy.GBRAIN_ALLOW not in agy.wanted_rules(app)  # not unless you ask for it
    app.settings.set("gbrain.agy_mcp", True)
    assert agy.GBRAIN_ALLOW in agy.wanted_rules(app)
    qid = agy.ask_consent(app, str(fake_agy))
    assert "your own GBrain's tools" in app.ask.get(qid)["text"]

    ok, msg = agy.connect_tools(app, [str(fake_agy)])
    assert ok and msg.endswith("agy has your GBrain's tools"), msg
    argv = [json.loads(x) for x in log.read_text().splitlines()]
    assert argv[1] == ["mcp", "list"]
    assert argv[2] == ["mcp", "add", "--env", f"GBRAIN_HOME={home}", "gbrain", "--", str(exe), "serve"] + [
        "--surface",
        "full",
    ]
    allow = json.loads(agy.settings_file().read_text())["permissions"]["allow"]
    assert agy.GBRAIN_ALLOW in allow and agy.ALLOW in allow
    assert not calls()  # registering it doesn't run it

    # agy has a "gbrain" of its own already, and you picked its tools yourself: both kept as they are
    f = agy.settings_file()
    f.write_text(json.dumps({"permissions": {"allow": ["mcp(gbrain/search)"]}}))
    log.unlink()
    monkeypatch.setenv("FAKE_AGY_LIST", "kurooto: kurooto mcp\ngbrain: gbrain serve --surface full")
    ok, msg = agy.connect_tools(app, [str(fake_agy)])
    assert ok and "already" in msg
    assert [json.loads(x)[:2] for x in log.read_text().splitlines()] == [["mcp", "add"], ["mcp", "list"]]
    allow = json.loads(f.read_text())["permissions"]["allow"]
    assert agy.GBRAIN_ALLOW not in allow and "mcp(gbrain/search)" in allow
