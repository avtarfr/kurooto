"""Your notes, your layout (core/notesfit.py, 0.5.20): reading an existing notes folder without AI, the proposal and its
preview, and moving only Kurooto's own notes as one plan (a dry run first), with Undo and a refusal on name clashes."""

from __future__ import annotations

import datetime as dt
from importlib import resources
from pathlib import Path

import pytest

from kurooto.core import layout, notesfit
from kurooto.core.config import Settings

DAY = dt.date(2026, 10, 20)
MADE = "---\nmade_by: Kurooto\ndate: 2026-10-20\n---\n\n"


def put(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="")
    return root


def snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def kurooto_vault(root: Path) -> Path:
    """Kurooto's own layout, as it writes it: bare daily notes and profile, made_by on what it wrote."""
    return put(
        root,
        {
            "journal/2026-10-18.md": "# 2026-10-18\n\nslept badly\n",
            "journal/2026-10-19.md": "# 2026-10-19\n",
            "journal/2026-10-20.md": "# 2026-10-20\n\n## Check-in\nfine\n",
            "about-me/profile.md": "# About me\n",
            "index.md": "# Home\n\n## Hubs\n- [[research/index|Research]]\n\n## Courses\n"
            "- [[linear-algebra/course|Linear algebra]]\n\nMy own line: [[linear-algebra/course]]\n",
            "research/index.md": MADE + "# Research\n",
            "linear-algebra/course.md": MADE + "# Linear algebra\n\n<!-- kurooto:hubs -->\n"
            "Home: [[index|Home]] · Research: [[research/index|Research]]\n",
            "linear-algebra/2026-10-20-rank.md": MADE + "# Rank\n\nSee [[linear-algebra/course]] and "
            "[the course](course.md).\n\n![board](files/board.jpg)\n",
            "linear-algebra/rank-nullity.md": MADE
            + "# Rank-nullity\n\nFrom [[linear-algebra/2026-10-20-rank|rank]].\n",
            "linear-algebra/my-thoughts.md": "# Mine\n\nAbout [[linear-algebra/rank-nullity]] and "
            "[rank](2026-10-20-rank.md).\n\n<!-- kurooto:seen -->\n- [[linear-algebra/rank-nullity]]\n"
            "<!-- /kurooto:seen -->\n",
            "linear-algebra/files/board.jpg": "jpg",
            "inbox/an-idea.md": MADE + "an idea\n",
            "kurooto/recurring.md": MADE + "| what |\n",
        },
    )


def obsidian_vault(root: Path) -> Path:
    """An Obsidian vault: Daily Notes/, a Courses folder with spaces in names, Inbox, markdown links with .md."""
    head = "---\ntitle: x\ntags: [a]\n---\n\n"
    return put(
        root,
        {
            ".obsidian/app.json": "{}",
            "Daily Notes/2026-10-18.md": head + "[Week 1](../Courses/Linear%20Algebra/Week%201.md)\n",
            "Daily Notes/2026-10-19.md": head + "[sets](../Courses/Real%20Analysis/Sets.md)\n",
            "Daily Notes/2026-10-20.md": head
            + "[idea](../Inbox/thought.md) and [w](<../Courses/Linear Algebra/Week 1.md>)\n",
            "Courses/Linear Algebra/Week 1.md": head + "[sets](../Real%20Analysis/Sets.md)\n",
            "Courses/Real Analysis/Sets.md": head + "text\n",
            "Inbox/thought.md": "a thought, [home](../Home.md)\n",
            "Home.md": "# Home\n",
        },
    )


def zettel_vault(root: Path) -> Path:
    def z(nid, tags="zettel"):
        return f"---\nid: {nid}\naliases: [x]\ntags: [{tags}]\n---\n\n"

    return put(
        root,
        {
            "dailies/2026-10-19.md": z("dailies/2026-10-19", "daily-notes") + "[[zettel/eigen]]\n",
            "dailies/2026-10-20.md": z("dailies/2026-10-20", "daily-notes") + "[[sources/la/2026-10-20-rank]]\n",
            "zettel/eigen.md": z("zettel/eigen") + "[[maps/index]]\n",
            "sources/la/2026-10-20-rank.md": z("sources/la/2026-10-20-rank", "source") + "[[zettel/eigen]]\n",
            "sources/ra/sets.md": z("sources/ra/sets", "source") + "x\n",
            "maps/index.md": z("maps/index", "map") + "[[maps/research]]\n",
            "inbox/fleeting.md": z("inbox/fleeting", "fleeting") + "x\n",
        },
    )


def mixed_vault(root: Path) -> Path:
    return put(
        root,
        {
            "journal/2026-10-17.md": "old journal\n",
            "Daily Notes/2026-10-18.md": "[[Projects/thesis]]\n",
            "Daily Notes/2026-10-19.md": "[thesis](Projects/thesis.md)\n",
            "Daily Notes/2026-10-20.md": "[[Projects/thesis]]\n",
            "Projects/thesis.md": "---\ntags: [p]\n---\n# Thesis\n",
            "Projects/ring-model.md": "# Ring\n",
            "10 University/Semester 5/Topology/notes.md": "x\n",
            "10 University/Semester 5/Algebra/notes.md": "x\n",
        },
    )


def lay(root: Path, preset="kurooto", paths=None) -> layout.Layout:
    return notesfit.layout_for(root, preset, paths or {})


# ------------------------------------------------------------------------------------------------ reading
def test_kurooto_layout_is_read_back_as_itself(tmp_path):
    root = kurooto_vault(tmp_path / "notes")
    got = notesfit.propose(root, lay(root))
    assert got["layout"] == "kurooto" and got["paths"] == {} and got["same"] is True
    lines = {x["kind"]: x for x in got["lines"]}
    assert lines["daily"]["template"] == "journal/{date}.md" and lines["daily"]["found"]
    assert lines["daily"]["confidence"] >= 0.75 and "3 daily notes" in lines["daily"]["why"]
    assert lines["subject"]["template"] == "{subject}" and lines["subject"]["confidence"] >= 0.8
    assert lines["inbox"]["template"] == "inbox"
    assert got["links"]["style"] == "wikilinks" and got["agent_notes"] == 6


def test_an_obsidian_vault_gets_its_own_places(tmp_path):
    root = obsidian_vault(tmp_path / "my vault")
    got = notesfit.propose(root, lay(root))
    assert got["layout"] == "kurooto"
    lines = {x["kind"]: x for x in got["lines"]}
    assert lines["daily"]["template"] == "Daily Notes/{date}.md" and lines["daily"]["confidence"] >= 0.75
    assert lines["subject"]["template"] == "Courses/{subject}" and lines["subject"]["confidence"] == 0.8
    assert lines["inbox"]["template"] == "Inbox"
    assert lines["concept"]["found"] is False and lines["project"]["found"] is False
    assert got["paths"]["daily"] == "Daily Notes/{date}.md"
    assert got["paths"]["course"] == "Courses/{subject}/course.md"
    assert got["paths"]["lecture"] == "Courses/{subject}/{date}-{slug}.md"
    assert got["paths"]["note"] == "Inbox/{slug}.md"
    lk = got["links"]
    assert lk["style"] == "markdown" and lk["with_md"] == 6 and lk["wikilinks"] == 0
    assert any("markdown links (with .md)" in x for x in got["said"])
    assert dict(got["frontmatter"]["keys"])["title"] == 5
    assert ".obsidian" not in [t["name"] for t in got["top"]]
    # the preview, with today's date and an example subject
    pv = {x["kind"]: x["path"] for x in notesfit.preview("kurooto", got["paths"], root, DAY)}
    assert pv["daily"] == "Daily Notes/2026-10-20.md"
    assert pv["note"] == "Inbox/an-idea.md"
    assert pv["course"] == "Courses/linear-algebra/course.md"
    assert pv["lecture"] == "Courses/linear-algebra/2026-10-20-eigenvalues.md"
    assert pv["profile"] == "about-me/profile.md" and pv["mail"] == "mail/2026-10-20-0700.md"


def test_a_zettelkasten_is_read_as_one(tmp_path):
    root = zettel_vault(tmp_path / "zk")
    got = notesfit.propose(root, lay(root))
    assert got["layout"] == "zettelkasten" and got["layout_confidence"] >= 0.8
    assert got["paths"] == {}  # every line is the zettelkasten's own place
    lines = {x["kind"]: x for x in got["lines"]}
    assert lines["daily"]["template"] == "dailies/{date}.md" and lines["daily"]["found"]
    assert lines["subject"]["template"] == "sources/{subject}" and lines["concept"]["template"] == "zettel/{slug}.md"
    assert got["links"]["style"] == "wikilinks" and got["links"]["paths"] == got["links"]["wikilinks"]
    keys = dict(got["frontmatter"]["keys"])
    assert keys["id"] == keys["aliases"] == keys["tags"] == 7
    pv = {x["kind"]: x["path"] for x in notesfit.preview("zettelkasten", {}, root, DAY)}
    assert pv["daily"] == "dailies/2026-10-20.md" and pv["course"] == "maps/courses/linear-algebra.md"


def test_a_mixed_folder_goes_by_the_most_and_is_less_sure(tmp_path):
    root = mixed_vault(tmp_path / "mixed")
    got = notesfit.propose(root, lay(root))
    lines = {x["kind"]: x for x in got["lines"]}
    assert lines["daily"]["template"] == "Daily Notes/{date}.md"
    assert lines["daily"]["confidence"] < notesfit.propose(obsidian_vault(tmp_path / "o"))["lines"][0]["confidence"]
    assert lines["subject"]["template"] == "10 University/Semester 5/{subject}" or lines["subject"]["template"] == (
        "10 University/{subject}"
    )
    assert lines["project"]["template"] == "Projects/{project}.md" and lines["project"]["found"]
    assert got["links"]["wikilinks"] == 2 and got["links"]["markdown"] == 1 and got["links"]["confidence"] == 0.67


def test_daily_notes_by_year_and_month(tmp_path):
    assert notesfit.daily_shape("2026/10/20.md") == "{year}/{month}/{day}.md"
    assert notesfit.daily_shape("Journal/2026/10/20.md") == "Journal/{year}/{month}/{day}.md"
    assert notesfit.daily_shape("Journal/2026/10/2026-10-20.md") == "Journal/{year}/{month}/{date}.md"
    assert notesfit.daily_shape("2026-10-20.md") == "{date}.md"
    assert notesfit.daily_shape("2026/13/40.md") is None and notesfit.daily_shape("la/2026-10-20-rank.md") is None
    root = put(tmp_path / "n", {f"2026/10/{d}.md": "x" for d in ("18", "19", "20")})
    got = notesfit.propose(root)
    assert got["paths"]["daily"] == "{year}/{month}/{day}.md"
    # the layout follows: today's daily note is 2026/10/20.md, and the AI is told that place
    L = lay(root, "kurooto", got["paths"])
    assert L.rel("daily", date="2026-10-20") == "2026/10/20.md"
    assert L.translate("write it in journal/<YYYY-MM-DD>.md") == "write it in <YYYY>/<MM>/<DD>.md"
    assert L.check() == []


def test_an_empty_or_missing_folder_keeps_kurootos_layout(tmp_path):
    for root in (tmp_path / "missing", tmp_path):
        got = notesfit.propose(root)
        assert got["layout"] == "kurooto" and got["paths"] == {} and not any(x["found"] for x in got["lines"])


def test_lines_from_a_page_are_checked_and_windows_slashes_are_fine():
    assert notesfit.lines_in({"layout": "kurooto", "lines": {"daily": "Daily Notes\\{date}.md"}})[1]
    assert notesfit.paths_from("kurooto", {"daily": "Daily Notes\\{date}.md"}) == {"daily": "Daily Notes/{date}.md"}
    for bad in (
        {"layout": "mine"},
        {"layout": "kurooto", "lines": {"profile": "x"}},
        {"layout": "kurooto", "lines": {"daily": "../{date}.md"}},
        {"layout": "kurooto", "lines": {"daily": 3}},
    ):
        with pytest.raises(ValueError):
            notesfit.lines_in(bad)


# ------------------------------------------------------------------------------------------------ moving
OBS_LINES = {"daily": "Daily Notes/{date}.md", "subject": "Courses/{subject}", "inbox": "Inbox"}


def test_the_plan_moves_only_kurootos_notes_and_writes_nothing(tmp_path):
    root = kurooto_vault(tmp_path / "my notes")
    before = snapshot(root)
    new = lay(root, "kurooto", notesfit.paths_from("kurooto", OBS_LINES))
    p = notesfit.plan(root, lay(root), new)
    assert snapshot(root) == before  # a dry run
    moves = {m["from"]: m["to"] for m in p.moves}
    assert moves == {
        "linear-algebra/course.md": "Courses/linear-algebra/course.md",
        "linear-algebra/2026-10-20-rank.md": "Courses/linear-algebra/2026-10-20-rank.md",
        "linear-algebra/rank-nullity.md": "Courses/linear-algebra/rank-nullity.md",
        "inbox/an-idea.md": "Inbox/an-idea.md",
    }
    # your notes stay: the daily notes (counted), the profile, my-thoughts.md, the home note
    assert p.daily_left == 3 and p.daily_from == "journal/<YYYY-MM-DD>" and not p.clashes
    v = p.view()
    assert v["ok"] and v["count"] == 4 and len(v["digest"]) == 16
    # links: in Kurooto's notes and blocks (and the home note's course list) fixed; in your text only counted
    fixes = {e.file: e for e in p.edits}
    assert set(fixes) == {
        "Courses/linear-algebra/2026-10-20-rank.md",
        "Courses/linear-algebra/rank-nullity.md",
        "linear-algebra/my-thoughts.md",
        "index.md",
    }
    rank = fixes["Courses/linear-algebra/2026-10-20-rank.md"].after
    assert "[[Courses/linear-algebra/course]]" in rank and "[the course](course.md)" in rank
    assert "![board](../../linear-algebra/files/board.jpg)" in rank  # the picture stays where it is
    assert "[[Courses/linear-algebra/2026-10-20-rank|rank]]" in fixes["Courses/linear-algebra/rank-nullity.md"].after
    mine = fixes["linear-algebra/my-thoughts.md"].after
    assert "About [[linear-algebra/rank-nullity]] and [rank](2026-10-20-rank.md)" in mine  # your words, as they were
    assert "<!-- kurooto:seen -->\n- [[Courses/linear-algebra/rank-nullity]]" in mine  # Kurooto's block, fixed
    home = fixes["index.md"].after
    assert "- [[Courses/linear-algebra/course|Linear algebra]]" in home
    assert "My own line: [[linear-algebra/course]]" in home
    assert {x["file"]: x["links"] for x in p.theirs} == {"linear-algebra/my-thoughts.md": 2, "index.md": 1}


def test_apply_and_undo_put_everything_back(tmp_path):
    root = kurooto_vault(tmp_path / "my notes")
    state = tmp_path / "state"
    before = snapshot(root)
    new = lay(root, "kurooto", notesfit.paths_from("kurooto", OBS_LINES))
    p = notesfit.plan(root, lay(root), new)
    with pytest.raises(notesfit.Refused):
        notesfit.apply_plan(p, state, "not-the-plan-you-saw")
    assert snapshot(root) == before
    r = notesfit.apply_plan(p, state, p.digest)
    assert r["moved"] == 4 and r["fixed"] >= 4
    assert (root / "Courses/linear-algebra/course.md").is_file() and not (root / "linear-algebra/course.md").exists()
    assert (root / "linear-algebra/my-thoughts.md").is_file()  # yours stays
    assert not (root / "inbox").exists()  # the folder the move left empty
    assert (root / "journal/2026-10-20.md").is_file()
    assert notesfit.last(state)["moved"] == 4
    # the plan from the new places finds nothing more to do
    assert notesfit.plan(root, new, new).moves == []
    u = notesfit.undo(state)
    assert (
        u["ok"]
        and u["moved_back"] == 4
        and u["before"] == {"notes.layout": "kurooto", "notes.paths": {}, "notes.links": "wiki"}
    )
    assert snapshot(root) == before
    assert not (root / "Courses").exists() and not (root / "Inbox").exists()
    assert notesfit.last(state) is None
    with pytest.raises(notesfit.Refused):
        notesfit.undo(state)


def test_undo_leaves_a_note_you_changed_since(tmp_path):
    root = kurooto_vault(tmp_path / "n")
    state = tmp_path / "state"
    new = lay(root, "kurooto", notesfit.paths_from("kurooto", OBS_LINES))
    p = notesfit.plan(root, lay(root), new)
    notesfit.apply_plan(p, state, p.digest)
    (root / "index.md").write_text("# Home\n\nrewritten by you\n", encoding="utf-8")
    u = notesfit.undo(state)
    assert not u["ok"] and any("index.md" in x for x in u["problems"])
    assert (root / "index.md").read_text(encoding="utf-8") == "# Home\n\nrewritten by you\n"
    assert (root / "linear-algebra/course.md").is_file()  # the notes still went back


def test_a_name_clash_refuses_the_whole_plan(tmp_path):
    root = kurooto_vault(tmp_path / "n")
    put(root, {"Inbox/an-idea.md": "your own note with the same name\n"})
    before = snapshot(root)
    new = lay(root, "kurooto", notesfit.paths_from("kurooto", OBS_LINES))
    p = notesfit.plan(root, lay(root), new)
    assert [c["from"] for c in p.clashes] == ["inbox/an-idea.md"] and not p.view()["ok"]
    with pytest.raises(notesfit.Refused, match="already is"):
        notesfit.apply_plan(p, tmp_path / "state", p.digest)
    assert snapshot(root) == before
    # two notes landing on one place is a clash too
    put(root, {"algebra/rank-nullity.md": MADE + "x\n"})
    p2 = notesfit.plan(root, lay(root), lay(root, "kurooto", {"concept": "Concepts/{slug}.md"}))
    assert [c["why"] for c in p2.clashes] == ["algebra/rank-nullity.md would move there too"]


def test_zettelkasten_to_kurooto_moves_agent_notes_and_their_ids(tmp_path):
    z = "---\nid: zettel/eigen\naliases: [Eigen]\ntags: [zettel, agent-written, la]\ntrust_tier: agent_written\n---\n\n"
    root = put(
        tmp_path / "zk",
        {
            "zettel/eigen.md": z + "x\n",
            "zettel/mine.md": "---\nid: zettel/mine\n---\nmine, [[zettel/eigen]]\n",
            "dailies/2026-10-20.md": "---\nid: dailies/2026-10-20\ntags: [daily-notes]\n---\n[[zettel/eigen]]\n",
        },
    )
    old, new = lay(root, "zettelkasten"), lay(root, "kurooto")
    p = notesfit.plan(root, old, new)
    assert [(m["from"], m["to"]) for m in p.moves] == [("zettel/eigen.md", "la/eigen.md")]  # subject from its tags
    after = {e.file: e.after for e in p.edits}
    assert after["la/eigen.md"].startswith("---\nid: la/eigen\n")
    assert "dailies/2026-10-20.md" not in after and p.daily_left == 1
    assert {x["file"] for x in p.theirs} == {"zettel/mine.md", "dailies/2026-10-20.md"}
    # in a folder laid out Kurooto's way, trust_tier alone (another agent's header) doesn't make a note Kurooto's
    assert notesfit.plan(root, lay(root, "kurooto"), lay(root, "kurooto", {"concept": "Z/{slug}.md"})).moves == []


# ------------------------------------------------------------------------------------- the app and the page
@pytest.fixture
def app(tmp_path, monkeypatch):
    from kurooto.app import App

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "home"))
    a = App()
    yield a
    a.close()


def test_the_setup_api_previews_applies_and_undoes(app):
    from kurooto.web.api import Api

    api = Api(app)
    root = kurooto_vault(app.workspace)
    before = snapshot(root)
    code, v = api.get("notes/fit", {})
    assert code == 200 and v["layout"] == "kurooto" and v["same"] and v["undo"] is None
    assert v["in_use"]["lines"]["daily"] == "journal/{date}.md"
    body = {"layout": "kurooto", "lines": OBS_LINES}
    code, pv = api.post("notes/fit/preview", body)
    assert code == 200 and pv["ok"] and pv["plan"]["count"] == 4 and not pv["problems"]
    assert {x["kind"]: x["path"] for x in pv["preview"]}["note"] == "Inbox/an-idea.md"
    assert snapshot(root) == before  # nothing written until confirmed
    code, r = api.post("notes/fit/apply", {**body, "digest": "stale"})
    assert code == 200 and not r["ok"] and snapshot(root) == before
    code, r = api.post("notes/fit/apply", {**body, "digest": pv["plan"]["digest"]})
    assert r["ok"] and r["moved"] == 4
    assert app.settings.get("notes.paths")["daily"] == "Daily Notes/{date}.md"
    assert layout.rel(app, "course", subject="la") == "Courses/la/course.md"
    again = api.get("notes/fit", {})[1]
    assert again["undo"]["moved"] == 4
    # opened again, the proposal keeps what's in use where nothing else was found: nothing more to move
    lines = {x["kind"]: x["template"] for x in again["lines"]}
    assert lines["concept"] == "Courses/{subject}/{slug}.md" and lines["subject"] == "Courses/{subject}"
    assert api.post("notes/fit/preview", {"layout": again["layout"], "lines": lines})[1]["plan"]["count"] == 0
    code, u = api.post("notes/fit/undo", {})
    assert u["ok"] and app.settings.get("notes.paths") == {} and snapshot(root) == before


def test_another_folder_is_only_switched_to(app, tmp_path):
    from kurooto.web.api import Api

    api = Api(app)
    vault = obsidian_vault(tmp_path / "Obsidian Vault")
    before = snapshot(vault)
    v = api.get("notes/fit", {"folder": str(vault)})[1]
    assert v["other_folder"] and v["layout"] == "kurooto"
    lines = {x["kind"]: x["template"] for x in v["lines"]}
    body = {"layout": v["layout"], "lines": lines, "folder": str(vault)}
    pv = api.post("notes/fit/preview", body)[1]
    assert pv["other_folder"] and pv["plan"]["count"] == 0
    r = api.post("notes/fit/apply", {**body, "digest": pv["plan"]["digest"]})[1]
    assert r["ok"] and Path(app.settings.get("you.workspace")) == vault
    assert layout.rel(app, "daily", date="2026-10-20") == "Daily Notes/2026-10-20.md"
    assert snapshot(vault) == before
    assert api.post("notes/fit/preview", {**body, "folder": str(tmp_path / "nope")})[1]["ok"] is False


def test_the_notes_step_is_on_the_setup_page_and_skippable(app):
    from kurooto.core import setupsteps

    assert setupsteps.STEPS[1] == "notes" and "notes" not in setupsteps.REQUIRED
    html = resources.files("kurooto.web").joinpath("static", "setup.html").read_text(encoding="utf-8")
    js = resources.files("kurooto.web").joinpath("static", "setup.js").read_text(encoding="utf-8")
    sec = html.split('<section data-step="notes">')[1].split("</section>")[0]
    assert "data-skip" in sec and 'id="nf-folder"' in sec
    assert '"notes"' in js and 'api("notes/fit/preview"' in js and 'api("notes/fit/apply"' in js
    assert "notes/fit/undo" in js
    home = resources.files("kurooto.web").joinpath("static", "home.js").read_text(encoding="utf-8")
    assert "/setup#notes" in home
    s = Settings(app.paths.config / "settings.json")
    assert s.get("notes.layout") == "kurooto"
