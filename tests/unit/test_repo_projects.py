"""Projects from repositories (core/repoproject.py): a fake repository made here with git, a GitHub address cloned from
a folder standing in for GitHub (file://, no network), a fake AI answer. Nothing in a repository runs; secrets aren't
read; the project note is written only inside Kurooto's block; each piece has Undo; milestones wait for a tap."""

import json
import subprocess

import pytest

from kurooto.core import graphwrite as gw
from kurooto.core import infer, repoproject
from kurooto.core.state import jsave
from kurooto.modules import research
from kurooto.providers.base import Result, Verdict

README = """# Glacier Flow

Glacier Flow is a small model of ice flow over a bed of varying slope, used to study how basal sliding responds to \
meltwater pulses in alpine glaciers. It couples a shallow-ice approximation to a simple hydrology model and is \
calibrated against surface velocities from field campaigns.

Supervisor: Dr Lena Ortiz

## Installation

```
pip install -e .
python -m glacier.run --config configs/base.toml
```

## Roadmap

- Add a sliding law that depends on effective pressure
- Compare against the 2025 velocity survey

The shallow-ice approximation treats the glacier as thin compared with its length, so the stress balance reduces to a \
local relation between the surface slope and the basal shear stress, which keeps each time step cheap enough to run \
ensembles over many melt seasons.
"""
DOC = """# The flow model

The ice thickness evolves by mass conservation: the change in thickness equals the accumulation minus the divergence \
of the ice flux. The flux follows Glen's flow law with exponent three, integrated over the depth of the glacier.

Basal sliding is a Weertman-type law: the sliding velocity grows with a power of the basal shear stress and falls \
with effective pressure. Effective pressure is the ice overburden minus the water pressure in the subglacial \
drainage system, which the hydrology model supplies at each step.

The drainage system switches between distributed cavities and channels as the meltwater input rises, which is what \
makes the speed-up after a melt pulse short-lived.
"""
NOTEBOOK = {
    "cells": [
        {
            "cell_type": "markdown",
            "source": ["# Calibration\n", "We fit the sliding coefficient to surface speeds. " * 16],
        },
        {"cell_type": "code", "source": ["import os\n", "os.system('echo never runs')\n"]},
    ]
}


def git(cwd, *args, who="Ana Ruiz"):
    subprocess.run(
        [
            "git",
            "-c",
            f"user.name={who}",
            "-c",
            "user.email=someone@example.com",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "init.defaultBranch=main",
            *args,
        ],  # fmt: skip
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def make_repo(root, name="glacier-flow"):
    """A repository on disk: README, docs, a manifest, a notebook, code, a picture, and secrets that must stay out."""
    r = root / name
    (r / "docs").mkdir(parents=True)
    (r / "src" / "glacier").mkdir(parents=True)
    (r / "notebooks").mkdir()
    (r / "secrets").mkdir()
    git(r, "init", "-q")
    (r / "README.md").write_text(README, encoding="utf-8")
    (r / "docs" / "model.md").write_text(DOC, encoding="utf-8")
    (r / "pyproject.toml").write_text(
        '[project]\nname = "glacier-flow"\ndependencies = ["numpy>=1.26", "xarray"]\nkeywords = ["glaciology"]\n',
        encoding="utf-8",
    )
    (r / "notebooks" / "calibrate.ipynb").write_text(json.dumps(NOTEBOOK), encoding="utf-8")
    (r / "src" / "glacier" / "run.py").write_text("raise SystemExit('this must never run')\n", encoding="utf-8")
    (r / "plot.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 64)
    (r / ".env").write_text("PASSWORD=" + "hunter2" * 4 + "\n", encoding="utf-8")
    (r / "secrets" / "notes.txt").write_text("the lab's wifi password\n", encoding="utf-8")
    (r / "LICENSE").write_text("MIT License\n\nPermission is hereby granted, free of charge, ...\n", encoding="utf-8")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "Start the flow model")
    (r / "docs" / "hydrology.md").write_text("# Hydrology\n\nCavities and channels.\n", encoding="utf-8")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "Notes on the drainage system", who="Mira Castell")
    return r


@pytest.fixture
def rp(env, tmp_path, monkeypatch):
    """A paired assistant, the background work run at once, no gh, a repository on disk and a stand-in for GitHub."""
    app = env.app
    app.settings.set("availability.night.enabled", False)
    monkeypatch.setattr(repoproject, "_spawn", lambda fn: fn())
    monkeypatch.setattr(repoproject, "gh_extras", lambda app, t: {})
    env.repo = make_repo(tmp_path / "code")
    bare = tmp_path / "github" / "glacier-flow.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(env.repo), str(bare)], check=True, capture_output=True)
    subprocess.run(["git", "config", "uploadpack.allowFilter", "true"], cwd=bare, check=True)
    env.bare = bare
    monkeypatch.setattr(repoproject, "remote_url", lambda t: bare.as_uri())
    return env


def graph_on(env, tmp_path):
    app = env.app
    app.settings.set("books.folder", str(tmp_path / "shelf"))
    app.settings.set("integrate.embeddings", "off")
    jsave(app.paths.state / "books.json", {"set_up": True})
    env.on("books", "integrate")
    return app.modules["integrate"]


def chat_on(env):
    env.app.settings.set("brain.main", "gemini")
    env.app.secrets.set("gemini.api_key", "k")
    env.on("chat")


def last_buttons(env):
    sent = [p for m, p in env.fake.sent if m == "sendMessage" and "reply_markup" in p]
    if not sent:
        return []
    rm = sent[-1]["reply_markup"]
    return (json.loads(rm) if isinstance(rm, str) else rm)["inline_keyboard"]


def told(env, start):
    return next(t for t in reversed(env.fake.texts()) if t.startswith(start))


# --------------------------------------------------------------------------------------------- addresses
def test_github_addresses_and_folders_are_read_and_anything_else_is_refused(tmp_path):
    for s in (
        "https://github.com/ana-ruiz/glacier-flow",
        "github.com/ana-ruiz/glacier-flow.git",
        "https://github.com/ana-ruiz/glacier-flow/tree/main/docs",
        "git@github.com:ana-ruiz/glacier-flow.git",
        "<https://www.github.com/Ana-Ruiz/Glacier-Flow>",
    ):
        t = repoproject.parse(s)
        assert t.kind == "github" and t.key == "github.com/ana-ruiz/glacier-flow", s
    assert repoproject.parse("git@github.com:ana-ruiz/glacier-flow.git").ssh
    assert repoproject.remote_url(repoproject.parse("github.com/a/b")) == "https://github.com/a/b.git"
    for s, why in (
        ("https://gitlab.com/ana/glacier", "only GitHub"),
        ("code/glacier", "full path"),
        (str(tmp_path / "missing"), "no folder"),
        ("", "give the repository"),
    ):
        with pytest.raises(repoproject.RepoError, match=why):
            repoproject.parse(s)
    (tmp_path / "x").mkdir()
    assert repoproject.parse(str(tmp_path / "x")).kind == "local"


def test_secret_files_are_never_read_and_keys_are_taken_out():
    for name in (".env", ".env.local", "deploy/id_ed25519", "config/client_secret_123.json", ".aws/config",
                 "secrets/notes.txt", "keys/server.pem", "token.json", "infra/prod.tfvars"):  # fmt: skip
        assert repoproject.secret(name), name
        assert repoproject.kind_of(name, 10) is None
    for name in ("README.md", "docs/model.md", "src/tokenizer.py", "environment.yml"):
        assert not repoproject.secret(name), name
    key = "AIza" + "x" * 35
    pem = "-----BEGIN " + "PRIVATE KEY-----\nabc\n-----END " + "PRIVATE KEY-----"
    out = repoproject.redact(f"use {key}\n{pem}\npassword = '{'s3cret' * 3}'\n")
    assert key not in out and "abc" not in out and "s3cret" not in out and out.count("[secret]") == 3
    assert repoproject.kind_of("plot.png", 10) is None and repoproject.kind_of("big.csv", 5_000_000) is None
    assert repoproject.kind_of("README.md", 10) == "doc" and repoproject.kind_of("pyproject.toml", 10) == "manifest"


# ----------------------------------------------------------------------------------------- a local folder
def test_a_folder_sets_up_the_note_the_commit_log_and_the_graph_each_with_undo(rp, tmp_path):
    env, app = rp, rp.app
    integ = graph_on(env, tmp_path)
    assert not app.is_on("research")
    reply = env.say(f"/project add {env.repo}")
    assert reply.startswith("Reading ")
    msg = told(env, "Set up Glacier Flow from")
    assert "from its files alone" in msg and "/inferred lists these" in msg
    note = research.project_note(app, "Glacier Flow")
    text = note.read_text(encoding="utf-8")
    from kurooto.core import meetings

    block = meetings.block_body(text, "repo")
    assert "**What it is:** Glacier Flow is a small model of ice flow" in block
    assert "pip install -e ." in block and "Add a sliding law" in block and "**Licence:** MIT" in block
    assert "Mira Castell (collaborator" in block and "Dr Lena Ortiz (supervisor)" in block
    assert "Ana Ruiz (collaborator" in block  # git here has no name of yours, so every author is listed
    assert "With: Dr Lena Ortiz (supervisor)" in text and "## Meetings" in text  # the repository says so
    assert "hunter2" not in text and "wifi" not in text
    hub = (app.workspace / "research" / "index.md").read_text(encoding="utf-8")
    assert "research/glacier-flow/index" in hub
    # the commit log: Research on, the folder watched under the project's name
    assert app.is_on("research") and str(env.repo) in app.settings.get("research.repos")
    assert app.modules["research"].project_of(env.repo) == "Glacier Flow"
    # the graph: README, docs/model.md and the notebook's text (docs/hydrology.md is too short)
    assert "repos" in integ.sources()
    items = [it for it in integ.items().values() if it["source"] == "repos"]
    assert sorted(it["title"] for it in items) == [
        "Glacier Flow: README.md",
        "Glacier Flow: docs/model.md",
        "Glacier Flow: notebooks/calibrate.ipynb",
    ]
    assert {it["note"] for it in items} == {"research/glacier-flow/index"} and items[0]["subject"] == "research"
    assert not any("never runs" in (integ.dir / "texts" / f"{it['id']}.txt").read_text() for it in items)
    # /inferred lists the three pieces; Undo is under the message
    listed = infer.command(app, "")
    assert listed.count("glacier-flow") >= 1 and "commits go into" in listed and "concept graph" in listed
    undo = [b for row in last_buttons(env) for b in row if b["text"].startswith("Undo")]
    assert [b["text"] for b in undo] == ["Undo note", "Undo commit log", "Undo graph"]
    for b in undo:
        assert env.press(b["callback_data"]).startswith("Undone")
    assert str(env.repo) not in (app.settings.get("research.repos") or [])
    assert not app.is_on("research")  # it was turned on for this, and has nothing else to do
    assert "repos" not in integ.sources() and not [it for it in integ.items().values() if it["source"] == "repos"]
    assert not note.exists()  # nothing of yours was in it
    assert "glacier-flow" not in (app.workspace / "research" / "index.md").read_text(encoding="utf-8")
    assert not list(env.repo.glob("*.kurooto*")) and (env.repo / ".env").exists()  # the folder itself is untouched


def test_writing_again_changes_only_kuroottos_block_and_adding_again_updates(rp):
    env, app = rp, rp.app
    env.say(f"/project add {env.repo} as Glacier Flow")
    note = research.project_note(app, "Glacier Flow")
    mine = "\nMy own plan: talk to the field team about the 2025 survey.\n"
    note.write_text(note.read_text(encoding="utf-8") + mine, encoding="utf-8")
    before = gw.outside_hash(note.read_text(encoding="utf-8"))
    (env.repo / "README.md").write_text(README.replace("small model", "compact model"), encoding="utf-8")
    env.say(f"/project add {env.repo}")
    upd = next(p for m, p in reversed(env.fake.sent) if m == "sendMessage" and p["text"].startswith("Updated"))
    assert "reply_markup" not in upd  # nothing new to undo: the pieces are there already
    text = note.read_text(encoding="utf-8")
    assert "compact model" in text and "small model" not in text and mine.strip() in text
    assert gw.outside_hash(text) == before and text.count("<!-- kurooto:repo") == 1
    assert app.settings.get("research.repos").count(str(env.repo)) == 1
    assert len(repoproject.records(app)) == 1
    assert len([x for x in infer._load(app)["items"] if x["kind"].startswith("repo-")]) == 2  # note, commit log
    # undoing the note now keeps it (your text is in it) and takes out Kurooto's part
    iid = repoproject.records(app)[str(env.repo)]["pieces"]["project"]
    assert infer.undo(app, iid).startswith("Undone")
    text = note.read_text(encoding="utf-8")
    assert "kurooto:repo" not in text and mine.strip() in text


# ------------------------------------------------------------------------------------------ a GitHub address
def test_a_github_address_is_cloned_shallow_with_no_secrets_binaries_or_code_run(rp):
    env, app = rp, rp.app
    reply = env.say("/project add https://github.com/ana-ruiz/glacier-flow")
    assert reply.startswith("Getting github.com/ana-ruiz/glacier-flow (a shallow copy, read only)")
    copy = app.paths.data / "repos" / "ana-ruiz__glacier-flow"
    assert (copy / "README.md").is_file() and (copy / "docs" / "model.md").is_file()
    assert (copy / "src" / "glacier" / "run.py").is_file()  # text is checked out to be read, never run
    assert not (copy / ".env").exists() and not (copy / "secrets").exists() and not (copy / "plot.png").exists()
    tree = json.loads((copy / ".git" / "kurooto-tree.json").read_text())
    assert "plot.png" in tree and ".env" not in tree and "secrets/notes.txt" not in tree
    cfg = ["git", "config", "remote.origin.partialclonefilter"]
    filt = subprocess.run(cfg, cwd=copy, capture_output=True, text=True)
    assert filt.stdout.strip() == "blob:none"  # no file contents came but the ones checked out
    assert not list((app.paths.data / "repos" / ".staging").iterdir())
    msg = told(env, "Set up Glacier Flow from github.com/ana-ruiz/glacier-flow")
    assert "Its commits go into the project's Log" in msg
    assert str(copy) in app.settings.get("research.repos")
    text = research.project_note(app, "Glacier Flow").read_text(encoding="utf-8")
    assert "https://github.com/ana-ruiz/glacier-flow" in text and "Code: github.com/ana-ruiz/glacier-flow." in text
    # the same repository again (another way of writing it): updated, not doubled
    env.say("/project add git@github.com:ana-ruiz/glacier-flow.git")
    assert told(env, "Updated Glacier Flow")
    assert len(repoproject.records(app)) == 1 and app.settings.get("research.repos").count(str(copy)) == 1
    assert repoproject.command(app, "").startswith("Projects from repositories:\n- Glacier Flow ←")


def test_a_repository_git_cannot_reach_says_how_to_sign_in(rp, monkeypatch, tmp_path):
    env = rp
    monkeypatch.setattr(repoproject, "remote_url", lambda t: (tmp_path / "nowhere.git").as_uri())
    env.say("/project add github.com/ana-ruiz/private-flow")
    said = told(env, "Couldn't set up a project from github.com/ana-ruiz/private-flow")
    assert "never asks for a token" in said or "git couldn't clone it" in said
    assert not repoproject.records(env.app)


# ----------------------------------------------------------------------------------------------- your AI
AI = {
    "name": "Glacier Flow",
    "what": "A shallow-ice glacier model with basal sliding driven by meltwater.",
    "goal": "Explain short speed-ups after melt pulses.",
    "field": "glaciology",
    "topics": ["basal sliding", "subglacial hydrology"],
    "stack": ["Python", "NumPy", "xarray"],
    "status": "Early: the flow model runs, the sliding law is next.",
    "run": ["pip install -e ."],
    "next": ["Effective-pressure sliding law"],
    "people": [
        {"name": "Mira Castell", "role": "supervisor"},  # the repository doesn't say so
        {"name": "Dr Lena Ortiz", "role": "supervisor"},
        {"name": "Prof Invented Person", "role": "collaborator"},  # not in the repository
    ],
    "subjects": ["fluid-dynamics", "Numerical Methods", "made-up-subject"],
    "projects": ["Sea ice", "Not mine"],
    "concepts": ["Glen's flow law"],
}


def test_the_ai_reads_it_once_and_its_answer_is_checked(rp, tmp_path):
    env, app = rp, rp.app
    chat_on(env)
    app.settings.set(
        "subjects.list",
        [
            {"slug": "fluid-dynamics", "name": "Fluid Dynamics"},
            {"slug": "numerical-methods", "name": "Numerical Methods"},
        ],
    )
    research.ensure_project(app, "Sea ice")
    env.say(f"/project add {env.repo}")
    got = told(env, "Got ")
    assert "Your AI is reading it" in got
    job = app.jobs.recent(1)[0]
    assert job.title.startswith("Reading ") and "## README (README.md)" in job.prompt
    assert "Fluid Dynamics" in job.prompt and "Sea ice" in job.prompt and "Recent commits" in job.prompt
    assert "hunter2" not in job.prompt and "wifi" not in job.prompt and "never runs" not in job.prompt
    row = app.jobs._db.execute("select then_payload, text_only from jobs where id=?", (job.id,)).fetchone()
    assert row[1] == 1  # text only: no tools, no files opened
    app.jobs.then_actions["repoproject.understood"](job, Result(Verdict.OK, json.dumps(AI)), json.loads(row[0]))
    msg = told(env, "Set up Glacier Flow")
    assert "(your AI read it)" in msg
    text = research.project_note(app, "Glacier Flow").read_text(encoding="utf-8")
    assert "A shallow-ice glacier model" in text and "**Field:** glaciology" in text
    assert "Mira Castell (collaborator" in text and "Dr Lena Ortiz (supervisor" in text
    assert "Invented" not in text and "made-up" not in text and "Not mine" not in text
    assert "Fluid Dynamics" in text and "Numerical Methods" in text and "[[research/sea-ice/index|Sea ice]]" in text


def test_when_the_ai_fails_it_is_set_up_from_the_files_alone(rp):
    env, app = rp, rp.app
    chat_on(env)
    env.say(f"/project add {env.repo}")
    job = app.jobs.recent(1)[0]
    payload = json.loads(app.jobs._db.execute("select then_payload from jobs where id=?", (job.id,)).fetchone()[0])
    app.jobs.then_actions["repoproject.understood"](job, Result(Verdict.ERROR, "", detail="down"), payload)
    msg = told(env, "Your AI's answer didn't come")
    assert "Set up Glacier Flow" in msg and research.project_note(app, "Glacier Flow").is_file()


# --------------------------------------------------------------------------------------- milestones
def test_dated_milestones_come_as_add_buttons_and_nothing_is_added_before_a_tap(rp, monkeypatch):
    env, app = rp, rp.app
    env.on("deadlines")
    import datetime as dt

    due = (dt.date.today() + dt.timedelta(days=20)).isoformat()
    monkeypatch.setattr(
        repoproject,
        "gh_extras",
        lambda app, t: {
            "milestones": [{"title": "v1.0", "due": due, "open": 3}, {"title": "Someday", "due": ""}],
            "issues": [{"n": 4, "title": "Sliding law blows up at zero pressure", "labels": []}],
        },  # fmt: skip
    )
    env.say("/project add github.com/ana-ruiz/glacier-flow")
    msg = told(env, "Set up Glacier Flow")
    assert "Dated milestones:" in msg and "Glacier Flow: v1.0" in msg and "Someday" not in msg
    assert not app.modules["deadlines"].items()
    add = next(b for row in last_buttons(env) for b in row if b["text"].startswith("Add: Glacier Flow: v1.0"))
    env.press(add["callback_data"])
    (it,) = app.modules["deadlines"].items().values()
    assert it["title"] == "Glacier Flow: v1.0" and it["due"].startswith(due) and it["source"] == "repository"
    text = research.project_note(app, "Glacier Flow").read_text(encoding="utf-8")
    assert "#4 Sliding law blows up at zero pressure" in text  # open issues are the next steps without an AI
    env.say("/project update Glacier Flow")
    assert "Dated milestones" not in told(env, "Updated Glacier Flow")  # offered once


# ---------------------------------------------------------------------------------------- plain English
def test_plain_english_asks_first_and_the_tap_sets_it_up(rp):
    env, app = rp, rp.app
    reply = env.say("set up my project from github.com/ana-ruiz/glacier-flow")
    assert reply.startswith("Set up a project from github.com/ana-ruiz/glacier-flow? I'll make a shallow copy")
    assert not repoproject.records(app) and not (app.paths.data / "repos").exists()  # nothing fetched yet
    go = last_buttons(env)[0]
    assert [b["text"] for b in go] == ["Set it up", "Not now"]
    assert env.press(go[0]["callback_data"]).startswith("Getting github.com/ana-ruiz/glacier-flow")
    assert told(env, "Set up Glacier Flow") and len(repoproject.records(app)) == 1
    assert env.press(go[0]["callback_data"]).startswith("That offer is gone")
    reply = env.say(f"add {env.repo} as a project called Ice")
    assert reply.startswith("Set up a project from") and " as Ice?" in reply
    env.press(last_buttons(env)[0][1]["callback_data"])  # Not now
    assert len(repoproject.records(app)) == 1


@pytest.mark.parametrize(
    "said,hit",
    [
        ("set up my project from github.com/ana-ruiz/glacier-flow", "github.com/ana-ruiz/glacier-flow"),
        ("Please create a project from https://github.com/ana/flow.", "https://github.com/ana/flow."),
        ("add a new project from the repo git@github.com:ana/flow.git", "git@github.com:ana/flow.git"),
        ("add github.com/ana-ruiz/glacier-flow as a project", "github.com/ana-ruiz/glacier-flow"),
        ("track ~/code/glacier as my project named Glacier", "~/code/glacier"),
        ("set up a project for my thesis", None),
        ("I got a project under Prof Lena Ortiz", None),
        ("add milk to the shopping list", None),
        ("what's in github.com/ana-ruiz/glacier-flow?", None),
    ],
)  # fmt: skip
def test_which_words_ask_for_a_project_from_a_repository(said, hit):
    got = repoproject.asked(said)
    assert (got[0] if got else None) == hit


def test_a_project_for_something_that_isnt_a_repository_is_left_to_the_rest(rp):
    assert repoproject.intent(rp.app, "set up a project for my thesis") is None
    assert repoproject.intent(rp.app, "set up a project from gitlab.com/ana/glacier")[0].startswith(
        "Can't set up a project from that: only GitHub"
    )


# ----------------------------------------------------------------------------------------- keeping current
def test_the_nightly_look_refreshes_changed_docs_only_and_says_a_new_release(rp, tmp_path):
    env, app = rp, rp.app
    integ = graph_on(env, tmp_path)
    env.say(f"/project add {env.repo}")
    n0 = len([it for it in integ.items().values() if it["source"] == "repos"])
    assert repoproject.refresh(app) == []  # nothing changed
    (env.repo / "docs" / "model.md").write_text(DOC + "\nA new section on calving at the terminus.\n", encoding="utf-8")
    git(env.repo, "commit", "-qam", "Calving")
    git(env.repo, "tag", "v0.2")
    said = repoproject.refresh(app)
    assert said == [
        "- Glacier Flow: docs changed (note refreshed, 1 file queued for the concept graph); new release v0.2."
    ]
    items = [it for it in integ.items().values() if it["source"] == "repos"]
    assert len(items) == n0 + 1 and items[-1]["title"] == "Glacier Flow: docs/model.md"
    assert repoproject.refresh(app) == []


def test_a_clone_is_fetched_again_when_github_has_new_commits(rp):
    env, app = rp, rp.app
    env.say("/project add github.com/ana-ruiz/glacier-flow")
    copy = app.paths.data / "repos" / "ana-ruiz__glacier-flow"
    (env.repo / "README.md").write_text(README.replace("small model", "small model with a calving front"), "utf-8")
    git(env.repo, "commit", "-qam", "Calving front")
    subprocess.run(["git", "push", "-q", str(env.bare), "HEAD:main"], cwd=env.repo, check=True, capture_output=True)
    said = repoproject.refresh(app)
    assert said and said[0].startswith("- Glacier Flow: README changed")
    assert "calving front" in (copy / "README.md").read_text(encoding="utf-8")
    assert "calving front" in research.project_note(app, "Glacier Flow").read_text(encoding="utf-8").lower()


# --------------------------------------------------------------------------------------------- the graph
def test_a_repository_file_is_read_into_concept_notes_seen_in_the_project_note(rp, tmp_path):
    from tests.fakes.openai import FakeOpenAI
    from tests.unit.test_integrate import answer, run_all

    env, app = rp, rp.app
    from kurooto import providers

    fake = FakeOpenAI()
    try:
        app.secrets.set("custom.api_key", fake.key)
        app.settings.set("brain.base_urls", {"custom": fake.base})
        app.settings.set("brain.models", {"custom": {"low": "m", "medium": "m", "high": "m"}})
        app.settings.set("brain.main", "custom")
        app.settings.set("notes.layout", "zettelkasten")
        app.power.current = "normal"
        mp = pytest.MonkeyPatch()
        mp.setattr(providers, "AGENT_PROGRAMS", ())
        integ = graph_on(env, tmp_path)
        env.say(f"/project add {env.repo}")
        quote = "The flux follows Glen's flow law with exponent three, integrated over the depth of the glacier"
        concept = {
            "name": "Glen's flow law", "aliases": [], "role": "core", "kind": "law",
            "definition": "A power law relating strain rate to stress in ice.", "formulas": [], "prereqs": [],
            "pages": [1, 1], "quote": quote, "same_as": None, "update": "", "links": [],
        }  # fmt: skip
        fake.answer = answer(concept)
        for _ in range(4):
            if not [b for b, _bt in integ.ready_batches() if b.get("source") == "repos"]:
                break
            integ.tick()
            run_all(env)
        notes = list((app.workspace / "zettel").glob("glen*.md"))
        assert notes, "no concept note"
        text = notes[0].read_text(encoding="utf-8")
        assert "## Seen in" in text and "[[projects/glacier-flow/index|Glacier Flow: docs/model.md]]" in text
        prompt = json.dumps(fake.requests)
        assert "Project documentation: Glacier Flow" in prompt
        mp.undo()
    finally:
        fake.close()


# ---------------------------------------------------------------------------------------------------- the CLI
def test_kurooto_project_add_types_the_command_to_the_running_kurooto(monkeypatch, capsys):
    from kurooto import cli

    sent = []
    monkeypatch.setattr(cli, "say", lambda text: sent.append(text) or {"ok": True, "replies": ["Getting it…"]})
    assert cli.main(["project", "add", "github.com/ana-ruiz/glacier-flow", "--as", "Glacier"]) == 0
    assert cli.main(["project"]) == 0
    assert sent == ['/project add "github.com/ana-ruiz/glacier-flow" as Glacier', "/project"]
    assert "Getting it…" in capsys.readouterr().out
