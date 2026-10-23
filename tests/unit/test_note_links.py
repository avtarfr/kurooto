"""The link style (notes.links, 0.5.22): Kurooto writes [[wikilinks]] or markdown links between notes, as your notes do,
and reads both back, so switching never breaks the concept graph, the hubs or the link cards."""

from __future__ import annotations

from pathlib import Path

import pytest

from kurooto.core import conceptgraph as cg
from kurooto.core import graphwrite as gw
from kurooto.core import hubs, layout, notesfit
from kurooto.core.config import Settings
from kurooto.modules import quiz_links


def lay(root: Path, links: str, preset: str = "zettelkasten") -> layout.Layout:
    s = Settings(root / "settings.json")
    s.set("notes.layout", preset)
    s.set("notes.links", links)
    return layout.Layout(root, s)


def test_render_in_both_styles():
    assert layout.render_link("wiki", "zettel/ito-lemma", "Itô's lemma") == "[[zettel/ito-lemma|Itô's lemma]]"
    assert layout.render_link("wiki", "zettel/ito-lemma") == "[[zettel/ito-lemma]]"
    md = layout.render_link("markdown", "zettel/ito lemma", "Itô [lemma]", from_rel="sources/sde/course.md")
    assert md == "[Itô (lemma)](../../zettel/ito%20lemma.md)"
    assert layout.render_link("markdown", "maps/home") == "[home](maps/home.md)"  # from the notes folder


def test_targets_read_both_styles_and_skip_files_and_pages():
    text = (
        "[[zettel/a|A]] then [B](../zettel/b.md) and [C](/maps/c.md) [D](d) "
        "![pic](x.png) [pdf](x.pdf) [web](https://example.org/y.md) [[zettel/e#part]]"
    )
    assert layout.link_targets(text, "sources/course.md") == ["zettel/a", "zettel/b", "maps/c", "sources/d", "zettel/e"]
    assert layout.link_targets("[up](../../out.md)", "a.md") == []  # outside the notes folder


def test_the_setting_picks_the_style(tmp_path):
    assert lay(tmp_path, "wiki").note_link("zettel/x", "X") == "[[zettel/x|X]]"
    m = lay(tmp_path, "markdown")
    assert m.note_link("zettel/x", "X", from_note=tmp_path / "maps" / "index.md") == "[X](../zettel/x.md)"
    assert m.note_link("zettel/x", "X", from_note="maps/index.md") == "[X](../zettel/x.md)"
    assert lay(tmp_path, "nonsense").note_style == "wiki"
    assert layout.Layout(tmp_path).note_style == "wiki"  # no settings: the default


def test_the_ai_is_told_when_links_are_markdown(tmp_path):
    assert lay(tmp_path, "wiki", "kurooto").describe() == ""  # the default: the skills already say it
    said = lay(tmp_path, "markdown", "kurooto").describe()
    assert "markdown links, not [[wikilinks]]" in said
    assert "links are [[wikilinks]]" not in lay(tmp_path, "markdown").describe()


def test_typed_link_lines_in_markdown_are_kurooto_s_and_dedupe_across_styles():
    line = gw.link_line("needs", "zettel/ito-lemma", "the drift term comes from it.", "markdown", "zettel/fp.md")
    assert line == "- needs:: [ito lemma](ito-lemma.md) — the drift term comes from it"
    assert gw.LINK_LINE.match(line) and gw.line_target(line, "zettel/fp.md") == "zettel/ito-lemma"
    old = "# Fokker–Planck\n\nMine.\n\n## Links\n- needs:: [[zettel/ito-lemma]] — the drift term comes from it\n"
    new, n = gw.add_links(old, [("zettel/ito-lemma", line)], "zettel/fp.md")
    assert n == 0 and new == old  # already linked, in the other style
    two = gw.link_line("used-in", "zettel/sde", "the equation the density solves forward", "markdown", "zettel/fp.md")
    new, n = gw.add_links(old, [("zettel/sde", two)], "zettel/fp.md")
    assert n == 1 and gw.guarded(old, new).ok  # a markdown link line is Kurooto's own, like a wikilink line


def test_the_concept_graph_and_link_cards_read_markdown_links(tmp_path):
    (tmp_path / "zettel").mkdir()
    note = tmp_path / "zettel" / "fp.md"
    note.write_text(
        "# Fokker–Planck\n\n## Links\n- needs:: [Itô's lemma](ito-lemma.md) — the drift term comes from it\n",
        encoding="utf-8",
    )
    n = cg.read_note(tmp_path, note)
    assert n is not None and n.links == {"zettel/ito-lemma"}
    m = quiz_links.LINE.match("- needs:: [Itô's lemma](ito-lemma.md) — the drift term comes from it")
    assert m and m[1] == "needs" and m[3] == "the drift term comes from it"
    assert layout.link_targets(m[2], "zettel/fp.md") == ["zettel/ito-lemma"]
    assert quiz_links.LINE.match("- needs:: [[zettel/ito-lemma|Itô]] — the drift term comes from it")


@pytest.fixture
def md_env(env):
    app = env.app
    app.settings.set("notes.layout", "zettelkasten")
    app.settings.set("notes.links", "markdown")
    env.on("subjects")
    env.say("/subject add Real Analysis (ra)")
    lay = layout.of(app)
    course = lay.path("course", subject="real-analysis")
    course.parent.mkdir(parents=True, exist_ok=True)
    course.write_text("# Real Analysis\n\nMine.\n", encoding="utf-8")
    return env, lay, course


def test_hubs_write_markdown_links_and_dont_add_them_twice_after_a_switch(md_env):
    env, lay, course = md_env
    hubs.ensure(env.app)
    home = lay.path("home").read_text(encoding="utf-8")
    assert "- [Real Analysis](courses/real-analysis.md)" in home and "- [Research](research.md)" in home
    assert "[Home](../index.md)" in course.read_text(encoding="utf-8")
    env.app.settings.set("notes.links", "wiki")
    assert hubs.ensure(env.app) == []  # what's linked in markdown is linked


def test_the_notes_step_proposes_markdown_and_undo_puts_it_back(tmp_path, monkeypatch):
    from kurooto.app import App
    from kurooto.web.api import Api

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "home"))
    app = App()
    try:
        root = app.workspace
        for rel, text in {
            "Notes/a.md": "See [B](b.md) and [C](sub/c.md).\n",
            "Notes/b.md": "Back to [A](a.md).\n",
            "Notes/sub/c.md": "Up: [A](../a.md).\n",
        }.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        api = Api(app)
        v = api.get("notes/fit", {})[1]
        assert v["link_style"]["value"] == "markdown" and v["link_style"]["found"] and not v["same"]
        assert v["in_use"]["links"] == "wiki" and any("Links: markdown" in x for x in v["said"])
        lines = {x["kind"]: x["template"] for x in v["lines"]}
        body = {"layout": v["layout"], "lines": lines, "links": "markdown"}
        pv = api.post("notes/fit/preview", body)[1]
        assert pv["ok"] and pv["links"] == "markdown"
        r = api.post("notes/fit/apply", {**body, "digest": pv["plan"]["digest"]})[1]
        assert r["ok"] and r["links"] == "markdown" and app.settings.get("notes.links") == "markdown"
        assert api.post("notes/fit/preview", {**body, "links": "html"})[1]["ok"] is False
        assert api.post("settings", {"key": "notes.links", "value": "html"})[0] == 400
        # Undo of a move puts the style back with the layout (the move log keeps what was in effect)
        monkeypatch.setattr(notesfit, "undo", lambda state, log_id="": {"ok": True, "before": r_before})
        r_before = {"notes.layout": "kurooto", "notes.paths": {}, "notes.links": "wiki"}
        notesfit.undo_app(app)
        assert app.settings.get("notes.links") == "wiki"
    finally:
        app.close()


def test_the_proposal_keeps_the_style_in_use_when_nothing_links(tmp_path):
    (tmp_path / "x.md").write_text("no links here\n", encoding="utf-8")
    p = notesfit.propose(tmp_path, lay(tmp_path, "markdown", "kurooto"))
    assert p["link_style"] == {
        "value": "markdown",
        "confidence": 0.5,
        "found": False,
        "why": "no links between notes found: the style in use",
    }
