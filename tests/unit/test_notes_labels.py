"""The NOTES map's names (0.5.19): at the usual zoom it names its regions (each course by its course page's title, each
research project by its index note's title) instead of its best-linked notes, so a book whose index note has hundreds
of "Seen in" links doesn't take every label. The pure part of home.js (roles, neighbourhoods, ranking, where the
region names go) runs here in node on a pretend notes folder: 2 courses, 1 research project and a book with 300
links."""

# ruff: noqa: E501

import json
import shutil
import subprocess
from importlib import resources

import pytest

JS = (resources.files("kurooto.web") / "static" / "home.js").read_text(encoding="utf-8")
PURE = JS.split("// -- the pure part")[1].split("// -- end of the pure part")[0].split("\n", 1)[1]

VAULT = """
const ids = [];
const links = [];
const add = (id, title) => ids.push([id, title]);
for (const [sub, title] of [["linear-algebra", "MTH201 Linear Algebra"], ["probability", "MTH205 Probability"]]) {
  add(`maps/courses/${sub}`, title);
  for (let i = 0; i < 12; i++) { add(`sources/${sub}/lecture-${i}`, `Lecture ${i}`); links.push([`maps/courses/${sub}`, `sources/${sub}/lecture-${i}`]); }
}
add("projects/l96/index", "Lorenz-96 forcing inference");
for (let i = 0; i < 8; i++) { add(`projects/l96/run-${i}`, `Run ${i}`); links.push([`projects/l96/run-${i}`, "projects/l96/index"]); }
add("sources/linear-algebra/books/axler", "Linear Algebra Done Right");
for (let i = 0; i < 300; i++) { add(`zettel/c${i}`, `Concept ${i}`); links.push([`zettel/c${i}`, "sources/linear-algebra/books/axler"]); }
links.push(["zettel/c1", "sources/probability/lecture-3"], ["zettel/c1", "projects/l96/index"], ["zettel/c1", "zettel/c2"]);
add("maps/index", "Home"); links.push(["maps/index", "maps/courses/linear-algebra"], ["maps/index", "projects/l96/index"]);
const nodes = new Map(ids.map(([id, title], i) => [id, { id, title, x: (i % 20) * 10, y: Math.floor(i / 20) * 10, deg: 0, nb: new Set() }]));
for (const [a, b] of links) { const p = nodes.get(a), q = nodes.get(b); p.deg++; q.deg++; p.nb.add(b); q.nb.add(a); }
const hoods = assignHoods(nodes);
const book = nodes.get("sources/linear-algebra/books/axler");
const out = {
  regions: regionSpots(nodes.values(), hoods).map((r) => r.label),
  hoods: [...hoods.values()].map((h) => h.label),
  ranked: rankLabels([...nodes.values()]).slice(0, 6).map((n) => n.id),
  last: rankLabels([...nodes.values()]).at(-1).id,
  book: { role: book.role, deg: book.deg, sdeg: book.sdeg },
  c1: { hood: nodes.get("zettel/c1").neighborhood, bridge: nodes.get("zettel/c1").bridge },
  run: nodes.get("projects/l96/run-0").neighborhood,
  course: nodes.get("maps/courses/probability").role,
};
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def plan():
    node = shutil.which("node")
    if not node:
        pytest.skip("needs node")
    js = "const PAL = {};\n" + PURE + VAULT
    r = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_the_regions_are_named_by_their_course_and_project_not_the_book(plan):
    assert set(plan["regions"]) >= {"MTH201 Linear Algebra", "MTH205 Probability", "Lorenz-96 forcing inference"}
    assert "Linear Algebra Done Right" not in plan["regions"] + plan["hoods"]


def test_a_books_reading_links_dont_make_it_big_or_first(plan):
    assert plan["book"] == {"role": "book", "deg": 300, "sdeg": 4}  # drawn as a small dot
    assert plan["last"] == "sources/linear-algebra/books/axler"  # named last, and never at the usual zoom
    assert set(plan["ranked"][:4]) == {
        "maps/courses/linear-algebra",
        "maps/courses/probability",
        "projects/l96/index",
        "maps/index",
    }
    assert plan["ranked"][4] == "zettel/c1"  # then a note that links across neighbourhoods
    assert plan["c1"]["bridge"] >= 2 and plan["run"] == "project:l96" and plan["course"] == "course"


def test_the_map_only_names_notes_when_asked_or_zoomed_in():
    draw = JS.split("  draw() {\n    const { ctx, w, h } = fitCanvas(this.cv); this.w = w;")[1].split("\n  hud(")[0]
    assert "const zoomed = this.view.k >= ZOOM_NAMES" in draw and "regionSpots(" in draw
    assert (
        'filter((n) => n.role !== "book")' in draw
    )  # zoomed in, a book's index note still waits for a point or a search
