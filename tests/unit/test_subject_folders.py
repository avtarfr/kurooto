# ruff: noqa: E501
"""0.8.0: Study mode adds and removes subjects, and a subject's folder is a neighbourhood on the notes map."""

from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from kurooto.core import actions


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["subjects"])
    ws = Path(a.workspace)
    for d in ("physics-notes", "algebra", ".hidden"):
        (ws / d).mkdir(parents=True, exist_ok=True)
    (ws / "algebra" / "week1.md").write_text("# Groups\n\nA group is a set with an operation.\n")
    (ws / "algebra" / "sub").mkdir()
    (ws / "algebra" / "sub" / "rings.md").write_text("# Rings\n\nA ring has two operations.\n")
    yield a
    a.close()


def test_add_with_a_folder_and_remove(app):
    sj = app.modules["subjects"]
    ok, msg = sj.add_subject("Abstract Algebra", ["aa", " alg "], "algebra")
    assert ok and "notes in algebra" in msg and sj.resolve("aa") == "abstract-algebra"
    assert sj.folder_map() == [{"slug": "abstract-algebra", "name": "Abstract Algebra", "folder": "algebra"}]
    v = actions.study_view(app, "abstract-algebra")
    assert v["subjects"][0]["own"] and v["subjects"][0]["folder"] == "algebra"
    assert "algebra" in v["folders"] and ".hidden" not in v["folders"]
    assert {"algebra/week1", "algebra/sub/rings"} <= {
        n["id"] for n in v["notes"]
    }  # the friend's notes show in Study mode
    assert sj.remove_subject("abstract-algebra").startswith("Removed Abstract Algebra")
    assert sj.subjects() == [] and (Path(app.workspace) / "algebra" / "week1.md").exists()  # the notes stay


def test_bad_folders_and_names(app):
    sj = app.modules["subjects"]
    assert (
        not sj.add_subject("X", [], "nope")[0]
        and not sj.add_subject("X", [], "../etc")[0]
        and not sj.add_subject("   ")[0]
    )
    assert sj.add_subject("Physics", ["ph"])[0] and sj.folder_map() == []
    assert sj.add_subject("Physics", [], "physics-notes")[0] and sj.folder_map()[0]["folder"] == "physics-notes"
    assert sj.subjects()[0]["aliases"] == ["ph"]  # adding again changes the folder, not the short names
    assert sj.remove_subject("nothing").startswith("That subject isn't one you added")


def test_the_map_payload_follows_the_subjects(app):
    from kurooto.web.live import Graph

    sj = app.modules["subjects"]
    sj.add_subject("Abstract Algebra", [], "algebra")
    g = Graph(Path(app.workspace))
    g.subjects = sj.folder_map()
    assert g.scan() and g.payload["subjects"] == g.subjects
    sj.remove_subject("abstract-algebra")
    g.subjects = []
    assert g.scan() and g.payload["subjects"] == []  # the map notices a subject going


def test_the_map_uses_the_folder():
    node = shutil.which("node")
    if not node:
        pytest.skip("no node")
    src = Path(__file__).resolve().parents[2] / "src" / "kurooto" / "web" / "static" / "views" / "notesmap.js"
    code = textwrap.dedent(
        """
        const fs = require("fs");
        const PAL = new Proxy({}, { get: () => "#000" });
        eval(fs.readFileSync(process.argv[1], "utf8").replace(/^"use strict";/m, "") + `
        globalThis.__t = { hoodOf, assignHoods };`);
        const t = globalThis.__t;
        console.log(t.hoodOf("algebra/week1", new Set(["abstract-algebra"]), undefined, [["algebra/", "abstract-algebra"]]));
        console.log(t.hoodOf("algebra/week1", new Set(), undefined, []));
        const nodes = new Map();
        for (const id of ["algebra/a", "algebra/b", "algebra/c", "misc/x"]) nodes.set(id, { id, title: id, nb: new Set(), out: [] });
        const hoods = t.assignHoods(nodes, { subjects: [{ slug: "abstract-algebra", name: "Abstract Algebra", folder: "algebra" }] });
        console.log(nodes.get("algebra/a").neighborhood, nodes.get("misc/x").neighborhood, hoods.get("abstract-algebra").label);
        """
    )
    out = subprocess.run([node, "-e", code, str(src)], capture_output=True, text=True, timeout=30, check=False)
    assert out.returncode == 0, out.stderr
    lines = out.stdout.strip().splitlines()
    assert (
        lines[0] == "abstract-algebra" and lines[1] == "null" and lines[2] == "abstract-algebra other Abstract Algebra"
    )
