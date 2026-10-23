"""The AI drafts in a scratch folder of its own; every change to your real files comes as a proposal that only your tap
applies (core/scratch.py, core/proposals.py, modules/projects.py). Fake brains that write files stand in for the AI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from kurooto import providers
from kurooto.core import proposals, scratch, tap
from kurooto.core.tools import run_tool, tools_for
from kurooto.providers.base import Result, Task, Verdict


class Writer:
    """An AI that does what `act(task)` says: write through Kurooto's tools (task.run_tool), or straight into the
    folder it runs in, as an agent program's own file tools would."""

    id, label, kind = "main", "A writing AI", "api"

    def __init__(self, act=None, text="Tidied the headings\nEach heading now says what's under it."):
        self.act, self.text, self.tasks = act, text, []

    def available(self):
        return True, ""

    def run(self, task: Task):
        self.tasks.append(task)
        if self.act:
            self.act(task)
        return Result(Verdict.OK, self.text, 2.0)


@pytest.fixture
def ai(env, monkeypatch):
    brain = Writer()
    monkeypatch.setattr(providers, "build", lambda a, w: brain if w == "main" else None)
    env.app.settings.set("brain.main", "main")
    env.on("chat")
    return brain


def note(app, rel, text):
    f = app.workspace / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    return f


def run_all(app):
    for _ in range(5):
        if app.jobs.run_next() is None and app.jobs.run_next("bg") is None:
            return


def git(repo, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "Ada", "GIT_AUTHOR_EMAIL": "ada@example.org",
           "GIT_COMMITTER_NAME": "Ada", "GIT_COMMITTER_EMAIL": "ada@example.org"}  # fmt: skip
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    if not shutil.which("git"):
        pytest.skip("no git")
    r = tmp_path / "thesis"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.email", "ada@example.org")
    git(r, "config", "user.name", "Ada")
    (r / "chapter2.tex").write_text("\\section{Two}\nA claim.\n", encoding="utf-8")
    (r / "refs.bib").write_text("@book{knuth, title={TAOCP}}\n", encoding="utf-8")
    (r / "old.tex").write_text("unused\n", encoding="utf-8")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "start")
    return r


# --------------------------------------------------------------------------------- your notes, as a proposal
def test_a_notes_change_you_ask_for_is_drafted_in_scratch_and_proposed(env, ai):
    app = env.app
    la = note(app, "la/week1.md", "# Week 1\n## stuff\nVectors.\n")
    outside = app.workspace.parent / "elsewhere.md"

    def act(task):
        assert task.scratch is not None and task.cwd == task.scratch  # it runs in its scratch folder
        assert task.reads == [app.workspace.resolve()] or task.reads == [Path(os.path.abspath(app.workspace))]
        assert "THIS REQUEST CHANGES FILES" in task.context
        assert task.mcp_env["KUROOTO_JOB"]  # an agent program's `kurooto mcp` gets the confined tools by this
        assert "Week 1" in task.run_tool("read_note", {"slug": "la/week1"})
        out = task.run_tool("edit_note", {"slug": "la/week1", "old": "## stuff", "new": "## Vectors"})
        assert out.startswith("Changed in your scratch folder")
        assert "## Vectors" in task.run_tool("read_note", {"slug": "la/week1"})  # its own copy, read back
        refused = task.run_tool("write_note", {"slug": str(outside), "text": "x"})
        assert refused.startswith("Refused") and not outside.exists()  # outside: blocked, and said
        assert "keys or passwords" in task.run_tool("write_note", {"slug": ".env", "text": "K=1"}) or "Hidden" in (
            task.run_tool("write_note", {"slug": ".env", "text": "K=1"})
        )
        names = {t.name for t in task.tools}
        assert {"edit_note", "delete_file", "read_note"} <= names
        assert not names & {"add_reminder", "sync_now", "tick_task", "set_alarm"}  # nothing else changes

    ai.act = act
    assert env.say("tidy my LA notes' headings").startswith("On it: the change comes as a proposal")
    run_all(app)
    assert la.read_text(encoding="utf-8") == "# Week 1\n## stuff\nVectors.\n"  # nothing of yours changed yet
    [p] = proposals.waiting(app)
    assert p["title"] == "Tidied the headings" and p["files"][0]["path"] == "la/week1.md"
    assert p["blocked"] == [str(outside)]
    msg = env.fake.texts()[-1]
    assert msg.startswith("Proposal for your notes: Tidied the headings") and "-## stuff\n+## Vectors" in msg
    assert "Refused while it worked (outside its scratch folder)" in msg
    sent = [x for m, x in env.fake.sent if m == "sendMessage"][-1]
    assert "prop:" + p["id"] + ":apply" in json.dumps(sent.get("reply_markup"))
    # Apply (your tap), then Undo
    assert env.press(f"prop:{p['id']}:apply").startswith("Applied to your notes: 1 file")
    assert la.read_text(encoding="utf-8") == "# Week 1\n## Vectors\nVectors.\n"
    assert scratch.get(app, p["sid"]) is None  # its scratch folder is gone after Apply
    assert env.press(f"prop:{p['id']}:undo").startswith("Undone")
    assert la.read_text(encoding="utf-8") == "# Week 1\n## stuff\nVectors.\n"


def test_apply_refuses_when_you_changed_the_note_since(env, ai):
    app = env.app
    f = note(app, "plan.md", "# Plan\nread ch 3\n")
    ai.act = lambda t: t.run_tool("edit_note", {"slug": "plan", "old": "read ch 3", "new": "read ch 4"})
    env.say("fix my plan notes")
    run_all(app)
    [p] = proposals.waiting(app)
    f.write_text("# Plan\nread ch 3\nmine\n", encoding="utf-8")
    assert "changed since this was proposed" in proposals.apply(app, p["id"])
    assert f.read_text(encoding="utf-8").endswith("mine\n") and proposals.get(app, p["id"])["status"] == "waiting"


def test_edit_note_in_any_request_becomes_a_proposal(env, ai):
    app = env.app
    f = note(app, "inbox/idea.md", "# Idea\nan old line\n")
    out = {}

    def act(task):
        out["edit"] = task.run_tool("edit_note", {"slug": "inbox/idea", "old": "an old line", "new": "a new line"})
        out["read"] = task.run_tool("read_note", {"slug": "inbox/idea"})
        out["add"] = task.run_tool("add_to_note", {"slug": "inbox/other", "text": "added"})  # adding: as always

    ai.act = act
    env.say("what's in my idea note? make the old line new")  # an ordinary request
    run_all(app)
    assert out["edit"].startswith("Proposed: the change to inbox/idea.md waits") and "a new line" in out["read"]
    assert f.read_text(encoding="utf-8") == "# Idea\nan old line\n"
    assert (app.workspace / "inbox" / "other.md").exists()
    [p] = proposals.waiting(app)
    assert p["source"] == "notes" and "+a new line" in proposals.diff_text(app, p)
    app.settings.set("proposals.notes_edits", False)  # off: edit_note changes the note, as before
    jid = app.jobs.submit("x")
    edit = next(t for t in tools_for(app, jid) if t.name == "edit_note")
    assert edit.description.endswith("previous version is kept.")


def test_a_fake_agent_writing_elsewhere_is_reported(env, ai):
    """An agent program's own file tools aren't Kurooto's: what changed in the original while it worked is named."""
    app = env.app
    f = note(app, "a.md", "# A\nx\n")

    def act(task):
        (task.scratch / "a.md").write_text("# A\ny\n", encoding="utf-8")  # in its folder: fine
        note(app, "b.md", "sneaked\n")  # in your notes: it shouldn't

    ai.act = act
    env.say("rewrite my a notes")
    run_all(app)
    [p] = proposals.waiting(app)
    assert p["outside"] == ["b.md"] and "Changed in the original while it worked" in env.fake.texts()[-1]
    assert [c["path"] for c in p["files"]] == ["a.md"] and f.read_text(encoding="utf-8") == "# A\nx\n"


# ------------------------------------------------------------------------------- Change, Discard, cleanup
def test_change_runs_again_in_the_same_scratch_and_discard_deletes_it(env, ai):
    app = env.app
    note(app, "a.md", "# A\none\n")
    ai.act = lambda t: t.run_tool("edit_note", {"slug": "a", "old": "one", "new": "two"})
    env.say("tidy my a notes")
    run_all(app)
    [p] = proposals.waiting(app)
    sid = p["sid"]
    assert env.press(f"prop:{p['id']}:change") == "Say what to change (reply to the question)."
    q = app.ask.pending(source="proposals")[0]
    seen = {}

    def again(task):
        seen["text"] = task.run_tool("read_note", {"slug": "a"})
        task.run_tool("edit_note", {"slug": "a", "old": "two", "new": "three"})

    ai.act, ai.text = again, "Three, not two\nAs you asked."
    app.ask.answer(q["id"], "make it three")
    assert proposals.get(app, p["id"])["status"] == "changing"
    run_all(app)
    assert "two" in seen["text"]  # the same scratch folder, with its earlier change
    p = proposals.get(app, p["id"])
    assert p["status"] == "waiting" and p["rev"] == 1 and p["sid"] == sid and p["title"] == "Three, not two"
    assert "+three" in proposals.diff_text(app, p) and "version 2" in env.fake.texts()[-1]
    assert "make it three" in ai.tasks[-1].prompt
    assert env.press(f"prop:{p['id']}:discard") == "Discarded; nothing of yours changed."
    assert scratch.get(app, sid) is None and (app.workspace / "a.md").read_text(encoding="utf-8") == "# A\none\n"
    assert proposals.apply(app, p["id"]) == "That was discarded."


def test_old_proposals_and_scratch_folders_are_cleaned(env, ai):
    app = env.app
    note(app, "a.md", "# A\none\n")
    ai.act = lambda t: t.run_tool("edit_note", {"slug": "a", "old": "one", "new": "two"})
    env.say("tidy my a notes")
    run_all(app)
    [p] = proposals.waiting(app)
    stray = scratch.create(app, app.workspace, "left over", git_ok=False)
    old = time.time() - 9 * 86400
    p["created"] = old
    proposals.save(app, p)
    stray.created = old
    stray.save()
    assert proposals.cleanup(app) == {"expired": 1, "removed": 1}
    assert proposals.get(app, p["id"])["status"] == "expired" and scratch.every(app) == []
    proposals.start(app)  # daily, and the night's proposals in the morning (App.start)
    assert app.scheduler.get("proposals:cleanup") is not None and app.scheduler.get("proposals:morning") is not None


def test_nothing_changed_and_too_big(env, ai):
    app = env.app
    note(app, "a.md", "# A\n")
    ai.text = "Nothing to change\nThe headings are fine."
    env.say("tidy my a notes")
    run_all(app)
    assert proposals.waiting(app) == [] and env.fake.texts()[-1].startswith("No changes proposed")
    assert scratch.every(app) == []
    app.settings.set("proposals.max_kb", 1)
    ai.act = lambda t: t.run_tool("write_note", {"slug": "big", "text": "x" * 5000})
    env.say("tidy my a notes")
    run_all(app)
    assert "too big to propose" in env.fake.texts()[-1] and proposals.waiting(app) == []


def test_a_proposal_that_deletes_says_so_first(env, ai):
    app = env.app
    note(app, "keep.md", "# Keep\n")
    gone = note(app, "old.md", "# Old\n")
    ai.act = lambda t: t.run_tool("delete_file", {"path": "old.md"})
    env.say("tidy my old notes")
    run_all(app)
    [p] = proposals.waiting(app)
    body = env.fake.texts()[-1]
    assert body.splitlines()[1] == "It deletes 1 file: old.md." and p["deletes"] == ["old.md"]
    assert gone.exists()  # nothing deleted before Apply
    proposals.apply(app, p["id"])
    assert not gone.exists()
    assert proposals.undo(app, p["id"]).startswith("Undone") and gone.read_text(encoding="utf-8") == "# Old\n"


# ------------------------------------------------------------------------------------------- a git project
def test_project_help_in_a_git_worktree_applies_as_one_commit_and_undo_reverts(env, ai, repo):
    app = env.app
    env.on("projects")
    app.settings.set("projects.folders", {"thesis": str(repo)})
    assert "doesn't help with thesis yet" in env.say("/project help thesis add footnotes to chapter 2")
    assert "may help with thesis now" in env.say("/project help on thesis")

    def act(task):
        w = task.scratch
        assert (w / "chapter2.tex").exists() and git(w, "rev-parse", "--abbrev-ref", "HEAD").startswith("kurooto/")
        (w / "chapter2.tex").write_text("\\section{Two}\nA claim.\\footnote{\\cite{knuth}}\n", encoding="utf-8")
        task.run_tool("delete_file", {"path": "old.tex"})
        task.run_tool("write_note", {"slug": "notes/todo.md", "text": "check refs"})
        # the original's own path is taken as the same file in the scratch folder: never the original itself
        assert task.run_tool("write_note", {"slug": str(repo / "extra.tex"), "text": "x"}).startswith("Written in your")

    ai.act, ai.text = act, "Footnotes in chapter 2\nOne footnote citing Knuth."
    assert env.say("in my thesis add footnotes to chapter 2 citing refs.bib").startswith("On it, in a worktree")
    assert "already working on thesis" in env.say("/project help thesis something else entirely")  # one at a time
    run_all(app)
    [p] = proposals.waiting(app)
    assert p["kind"] == "git" and {c["path"]: c["status"] for c in p["files"]} == {
        "chapter2.tex": "changed", "notes/todo.md": "added", "old.tex": "deleted", "extra.tex": "added"}  # fmt: skip
    assert not (repo / "extra.tex").exists() and git(repo, "status", "--porcelain") == ""
    # your uncommitted change in a file it touches: refused, saying so
    (repo / "chapter2.tex").write_text("mine\n", encoding="utf-8")
    assert "uncommitted changes in chapter2.tex" in proposals.apply(app, p["id"])
    git(repo, "checkout", "--", "chapter2.tex")
    (repo / "unrelated.txt").write_text("my own work\n", encoding="utf-8")  # elsewhere: fine, and left alone
    head = git(repo, "rev-parse", "HEAD")
    out = env.press(f"prop:{p['id']}:apply")
    assert out.startswith("Applied to thesis: commit") and "on main" in out and "not pushed" in out
    assert git(repo, "rev-parse", "HEAD^") == head and git(repo, "log", "-1", "--format=%s") == "Footnotes in chapter 2"
    assert "footnote" in (repo / "chapter2.tex").read_text(encoding="utf-8") and not (repo / "old.tex").exists()
    assert git(repo, "status", "--porcelain") == "?? unrelated.txt"
    assert "kurooto/" not in git(repo, "branch", "--list")  # its branch and worktree are gone
    assert env.press(f"prop:{p['id']}:undo").startswith("Undone: commit")
    assert git(repo, "log", "-1", "--format=%s").startswith('Revert "Footnotes in chapter 2"')
    assert (repo / "old.tex").read_text(encoding="utf-8") == "unused\n"
    assert "footnote" not in (repo / "chapter2.tex").read_text(encoding="utf-8")
    assert git(repo, "status", "--porcelain") == "?? unrelated.txt"


def test_a_git_proposal_refuses_a_detached_head(env, ai, repo):
    app = env.app
    sc = scratch.create(app, repo, "thesis", project="thesis")
    (sc.work / "refs.bib").write_text("@book{knuth, title={TAOCP, vol 1}}\n", encoding="utf-8")
    p, _ = proposals.make(app, sc, "Fix a title", "")
    git(repo, "checkout", "-q", "--detach")
    assert "on no branch" in proposals.apply(app, p["id"])


def test_checks_run_in_a_sandbox_inside_the_scratch_folder(env, ai, repo):
    app = env.app
    if scratch.sandbox(repo, []) is None:
        pytest.skip("no sandbox here")
    probe = subprocess.run([*scratch.sandbox(repo, []), "true"], capture_output=True)
    if probe.returncode != 0:
        pytest.skip("bubblewrap can't run here")
    target = repo.parent / "escaped.txt"
    net = "python3 -c 'import socket; socket.create_connection((\"1.1.1.1\", 80), 2)'"
    cmd = f"echo built > out.txt; echo x > {target}; {net}"
    sc = scratch.create(app, repo, "thesis", project="thesis", checks=cmd)
    r = scratch.run_checks(app, sc, timeout=30)
    assert r["ran"] and not r["ok"] and (sc.work / "out.txt").exists()
    assert not target.exists()  # nothing written outside the scratch folder
    assert "unreachable" in r["out"] or "Network" in r["out"] or "network" in r["out"]
    sc.checks = ""
    assert scratch.run_checks(app, sc) == {"ran": False, "why": "checks are off for this project"}


def test_project_commands_and_the_per_project_switch(env, ai, repo):
    app = env.app
    env.on("projects")
    assert env.say("/project").startswith("No projects yet")
    assert "is a project now" in env.say(f"/project add {repo} as thesis")
    assert "thesis: " in env.say("/project") and "· off" in env.say("/project")
    assert "latexmk" in env.say("/project checks thesis") or "no checks" in env.say("/project checks thesis")
    assert "Kurooto runs `make check`" in env.say("/project checks thesis make check")
    assert app.settings.get("projects.checks") == {"thesis": "make check"}
    assert env.say("/project checks thesis off") == "No checks for thesis any more."
    app.settings.set("research.repos", [str(repo)])
    app.settings.set("research.projects", {str(repo): "the-thesis"})
    assert "the-thesis" in env.say("/project")
    it = app.modules["projects"].intents()[0]
    said = it.match("in my thesis add footnotes to chapter 2")
    assert said == {"name": "thesis", "what": "add footnotes to chapter 2"}
    assert it.match("in my garden plant tomatoes") is None  # not a project
    assert it.match("help with my essay: fix the intro") == {"name": "essay", "what": "fix the intro"}
    assert env.say("help with my essay: fix the intro") == 'No project "essay". /project lists them.'


# ------------------------------------------------------------------------------ the tap, the AI, the night
def test_apply_is_a_guarded_tap_the_ai_cannot_reach(env, ai):
    app = env.app
    g = tap.GUARDED["proposal.apply"]
    assert set(g.ways) == {"typed", "button"}
    names = {t.name for t in tools_for(app)} | {t.name for t in tools_for(app, "j00000000")}
    assert not any("apply" in n or "proposal" in n for n in names)
    note(app, "a.md", "# A\none\n")
    ai.act = lambda t: t.run_tool("edit_note", {"slug": "a", "old": "one", "new": "two"})
    env.say("tidy my a notes")
    run_all(app)
    [p] = proposals.waiting(app)
    assert "There's no" in run_tool(app, "apply_proposal", {"id": p["id"]})
    assert (app.workspace / "a.md").read_text(encoding="utf-8") == "# A\none\n"
    text, buttons = proposals.command(app, f"apply {p['id']}")  # typed
    assert text.startswith("Applied") and buttons == [[("Undo", f"prop:{p['id']}:undo")]]


def test_proposals_made_at_night_wait_for_the_morning_message(env, ai):
    app = env.app
    note(app, "a.md", "# A\none\n")
    sc = scratch.create(app, app.workspace, "your notes", git_ok=False)
    ai.act = lambda t: t.run_tool("edit_note", {"slug": "a", "old": "one", "new": "two"})
    before = len(env.fake.texts())
    proposals.submit(app, sc, "tidy a", "Tidy a", background=True, source="notes")
    run_all(app)
    [p] = proposals.waiting(app)
    assert p["night"] and not p["told"] and len(env.fake.texts()) == before  # not one by one
    assert proposals.morning(app) == "1 told"  # Dreaming off: its own message, through Calm
    msg = env.fake.texts()[-1]
    assert "Waiting for your OK:\n- Proposed for your notes" in msg and p["title"] in msg
    assert proposals.morning(app) == "none"  # told once
    # with Dreaming on, the morning message has them
    p2 = dict(p, id="p0000beef", told=False)
    proposals.save(app, p2)
    env.on("dreaming")
    text = app.modules["dreaming"].report(send=False)
    assert f"/proposals {p2['id']}" in text and proposals.morning(app) == "in Dreaming's message"


def test_proposals_command_lists_and_shows(env, ai):
    app = env.app
    assert env.say("/proposals").startswith("Nothing waits for your OK.")
    note(app, "a.md", "# A\none\n")
    ai.act = lambda t: t.run_tool("edit_note", {"slug": "a", "old": "one", "new": "two"})
    env.say("tidy my a notes")
    run_all(app)
    listing = env.say("/proposals")
    assert listing.startswith("Waiting for your OK:\n1. Tidied the headings · your notes · 1 file")
    assert "-one\n+two" in env.say("/proposals 1")
    assert "/proposals" in app.help("all")


def test_the_web_page_lists_shows_and_acts(env, ai):
    from kurooto.web.api import Api

    app = env.app
    note(app, "a.md", "# A\none\n")
    ai.act = lambda t: t.run_tool("edit_note", {"slug": "a", "old": "one", "new": "two"})
    env.say("tidy my a notes")
    run_all(app)
    api = Api(app)
    code, v = api.get("proposals", {})
    assert code == 200 and v["proposals"][0]["status"] == "waiting"
    pid = v["proposals"][0]["id"]
    code, one = api.get(f"proposals/{pid}", {})
    assert "+two" in one["proposal"]["diff"]
    assert api.post("proposals/act", {"id": pid, "act": "nope"})[0] == 400
    assert api.post("proposals/act", {"id": pid, "act": "apply"})[1]["message"].startswith("Applied")
    assert (app.workspace / "a.md").read_text(encoding="utf-8") == "# A\ntwo\n"
    assert api.get("proposals", {})[1]["projects"] is None  # Help with your project is off
    assert api.post("projects/help", {"name": "x", "what": "fix it"})[1]["ok"] is False
    env.on("projects")
    assert api.get("proposals", {})[1]["projects"] == []
    said = api.post("projects/help", {"name": "x", "what": "fix it"})[1]["message"]
    assert said == 'No project "x". /project lists them.'


def test_an_agent_programs_tool_calls_are_confined_by_its_request(env, ai):
    """`kurooto mcp` passes the request's id: a change request's tools write in its scratch folder only."""
    from kurooto.web import tools_api

    app = env.app
    f = note(app, "a.md", "# A\none\n")
    sc = scratch.create(app, app.workspace, "your notes", git_ok=False)
    jid = proposals.submit(app, sc, "tidy a", "Tidy a")
    listed = {t["name"]: t for t in tools_api.get(app, "tools", {"job": jid})[1]["tools"]}
    assert "delete_file" in listed and "add_reminder" not in listed
    r = tools_api.post(app, "tools/call", {"name": "edit_note", "args": {"slug": "a", "old": "one", "new": "two"},
                                           "job": jid, "via": "mcp"})  # fmt: skip
    assert r[1]["result"].startswith("Changed in your scratch folder") and f.read_text(encoding="utf-8") == "# A\none\n"
    r = tools_api.post(app, "tools/call", {"name": "write_note", "args": {"slug": "/etc/x.md", "text": "x"},
                                           "job": jid, "via": "mcp"})  # fmt: skip
    assert r[1]["result"].startswith("Refused")
    assert "delete_file" not in {t["name"] for t in tools_api.get(app, "tools", {})[1]["tools"]}


# --------------------------------------------------------------------------------- how each AI is confined
def test_claude_code_may_edit_only_the_scratch_folder(env, tmp_path):
    from kurooto.providers.claude import ClaudeCode, permissions, rule_path

    app = env.app
    sc = scratch.create(app, app.workspace, "your notes", git_ok=False)
    task = Task(prompt="x", scratch=sc.work, reads=[sc.src], cwd=sc.work, mcp=["kurooto", "mcp"])
    cfg, dirs = permissions(app, task)
    allow, deny = cfg["permissions"]["allow"], cfg["permissions"]["deny"]
    edits = [a for a in allow if a.startswith("Edit(")]
    assert edits == [f"Edit({rule_path(sc.work)}/**)"]
    assert f"Edit({rule_path(app.workspace)}/**)" in deny and f"Read({rule_path(sc.src)}/**)" in allow
    assert f"Read({rule_path(app.workspace)}/**/.env)" in deny and f"Edit({rule_path(sc.work)}/**/*.pem)" in deny
    assert not any(a.startswith(("Bash(mkdir", "Bash(echo")) for a in allow) and "Bash(cat)" in allow
    assert str(sc.work) in dirs and cfg["permissions"]["defaultMode"] == "dontAsk"
    # an ordinary request: as before
    cfg2, _ = permissions(app, Task(prompt="x", cwd=app.workspace))
    assert f"Edit({rule_path(app.workspace)}/**)" in cfg2["permissions"]["allow"]
    args = ClaudeCode(exe="claude", app=app).args(task, tmp_path)
    assert json.loads((tmp_path / "settings.json").read_text())["permissions"]["allow"][0].startswith("Edit(")
    assert "--setting-sources" in args and "dontAsk" in args


def test_places_write_roots_for_a_change_request(env):
    from kurooto.core import places

    app = env.app
    sc = scratch.create(app, app.workspace, "your notes", git_ok=False)
    assert places.write_roots(app, scratch=sc.work) == [Path(os.path.abspath(sc.work))]
    assert Path(os.path.abspath(sc.src)) in places.read_roots(app, extra=[sc.src])


def test_secrets_never_go_into_a_proposal(env, repo):
    app = env.app
    sc = scratch.create(app, repo, "thesis")
    (sc.work / ".env").write_text("TOKEN=1\n", encoding="utf-8")
    (sc.work / "id_rsa").write_text("key\n", encoding="utf-8")
    (sc.work / "a.tex").write_text("ok\n", encoding="utf-8")
    ch = scratch.changes(app, sc)
    assert [c.path for c in ch.files] == ["a.tex"] and set(ch.dropped) == {".env", "id_rsa"}
    assert "TOKEN" not in ch.patch
    assert scratch.secret("config/credentials.json") and scratch.secret("x/server.pem") and not scratch.secret("a.md")
    assert scratch.locate(sc, ".env")[0] is None
