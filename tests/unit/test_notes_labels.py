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
const nodes = new Map(ids.map(([id, title], i) => [id, { id, title, x: (i % 20) * 10, y: Math.floor(i / 20) * 10, deg: 0, nb: new Set(), out: new Set() }]));
for (const [a, b] of links) { const p = nodes.get(a), q = nodes.get(b); p.deg++; q.deg++; p.nb.add(b); q.nb.add(a); p.out.add(b); }
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


def run(vault: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("needs node")
    js = "const PAL = {};\n" + PURE + vault
    r = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module")
def plan():
    return run(VAULT)


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


# ---------------------------------------------------------------- research regions (0.5.21): a real vault, in shape
# Most notes are concept notes in zettel/ (from books), courses are sources/<course>/ with maps/courses/<course>, the
# research hub is maps/research and each project is a small folder: projects/<p>/index plus a note or two.
RESEARCH = """
const ids = [], links = [];
const add = (id, title) => ids.push([id, title]);
const link = (a, b) => links.push([a, b]);
add("maps/research", "Research"); add("maps/index", "Home"); link("maps/index", "maps/research");
for (const [sub, title] of [["dynamics", "MTH310 Dynamical Systems"], ["stats", "MTH220 Statistics"]]) {
  add(`maps/courses/${sub}`, title); link("maps/index", `maps/courses/${sub}`);
  for (let i = 0; i < 10; i++) { add(`sources/${sub}/lecture-${i}`, `Lecture ${i}`); link(`maps/courses/${sub}`, `sources/${sub}/lecture-${i}`); }
  add(`sources/${sub}/books/book`, `A ${sub} book`);
}
// two research projects: an index and one note each; the index links to its topics in zettel/
add("projects/l96/index", "Lorenz-96 subgrid parameterization"); add("projects/l96/log", "Log"); link("projects/l96/log", "projects/l96/index");
add("projects/joy/index", "index"); add("projects/joy/plan", "Plan"); link("projects/joy/plan", "projects/joy/index");  // no title of its own
link("maps/research", "projects/l96/index"); link("maps/research", "projects/joy/index");
for (const c of ["lorenz-96", "subgrid", "closure"]) { add(`zettel/${c}`, c); link("projects/l96/index", `zettel/${c}`); }
add("zettel/ring-model", "Ring atmosphere"); link("projects/joy/index", "zettel/ring-model");
add("zettel/radiation", "Radiation");  // only in the hub's line for joy
// concept notes from books: each seen in a book, some linked to research topics
for (let i = 0; i < 40; i++) { add(`zettel/d${i}`, `Dyn ${i}`); link(`zettel/d${i}`, "sources/dynamics/books/book"); }
for (let i = 0; i < 40; i++) { add(`zettel/s${i}`, `Stat ${i}`); link(`zettel/s${i}`, "sources/stats/books/book"); }
add("zettel/chaos", "Chaos"); link("zettel/chaos", "zettel/lorenz-96"); link("zettel/chaos", "zettel/subgrid"); link("zettel/chaos", "sources/dynamics/books/book");
add("zettel/tie", "Tie"); link("zettel/tie", "zettel/closure"); link("zettel/tie", "sources/stats/lecture-1");
add("zettel/lonely", "Lonely"); link("zettel/lonely", "zettel/lonely-2"); add("zettel/lonely-2", "Lonely 2");
const nodes = new Map(ids.map(([id, title], i) => [id, { id, title, x: (i % 20) * 10, y: Math.floor(i / 20) * 10, deg: 0, nb: new Set(), out: new Set() }]));
for (const [a, b] of links) { const p = nodes.get(a), q = nodes.get(b); p.deg++; q.deg++; p.nb.add(b); q.nb.add(a); p.out.add(b); }
const t0 = Date.now();
const hoods = assignHoods(nodes, {
  layout: { research: "maps/research", project: "projects/{project}/index" },
  research: { joy: { name: "Ring atmosphere model (with a professor)", topics: ["zettel/radiation"] } },
});
const hood = (id) => nodes.get(id).neighborhood;
const spots = regionSpots(nodes.values(), hoods);
// the real size: 2,000 notes, most of them concept notes
const big = new Map();
for (let i = 0; i < 2000; i++) big.set(`zettel/b${i}`, { id: `zettel/b${i}`, title: `B${i}`, x: i, y: i, nb: new Set(), out: new Set() });
for (let i = 1; i < 2000; i++) { big.get(`zettel/b${i}`).nb.add(`zettel/b${i - 1}`); big.get(`zettel/b${i - 1}`).nb.add(`zettel/b${i}`); }
const t1 = Date.now(); assignHoods(big); const bigMs = Date.now() - t1;
console.log(JSON.stringify({
  spots: spots.map((r) => [r.label, r.project, r.n]),
  hoods: Object.fromEntries([...hoods].map(([k, v]) => [k, v.label])),
  of: Object.fromEntries(["zettel/lorenz-96", "zettel/subgrid", "zettel/closure", "zettel/ring-model", "zettel/radiation",
    "zettel/d3", "zettel/s3", "zettel/chaos", "zettel/tie", "zettel/lonely", "projects/l96/log", "sources/stats/lecture-1",
    "sources/dynamics/books/book", "maps/research"].map((id) => [id, hood(id)])),
  bigMs,
}));
"""


@pytest.fixture(scope="module")
def research():
    return run(RESEARCH)


def test_research_projects_are_named_however_small(research):
    named = {label: project for label, project, n in research["spots"]}
    assert named["Lorenz-96 subgrid parameterization"] is True
    assert named["Ring atmosphere model (with a professor)"] is True  # its index has no title: the hub's line names it
    assert named["MTH310 Dynamical Systems"] is False and named["MTH220 Statistics"] is False
    assert not any("book" in label for label in named)  # books are never a region's name


def test_a_project_takes_what_its_index_and_hub_entry_link_to(research):
    of = research["of"]
    assert of["zettel/lorenz-96"] == of["zettel/subgrid"] == of["zettel/closure"] == "project:l96"
    assert of["zettel/ring-model"] == of["zettel/radiation"] == "project:joy"  # the index's link, the hub's topic
    assert of["projects/l96/log"] == "project:l96"
    assert of["sources/stats/lecture-1"] == "stats"  # a note in a course folder stays there
    assert of["maps/research"] == "hub"
    n = {label: n for label, _, n in research["spots"]}
    assert n["Lorenz-96 subgrid parameterization"] == 6  # index, log, three topics and the concept that leans on them


def test_concept_notes_join_the_region_most_of_their_links_come_from(research):
    of = research["of"]
    assert of["zettel/d3"] == "dynamics" and of["zettel/s3"] == "stats"  # the cloud splits by course
    assert of["zettel/chaos"] == "project:l96"  # two research topics beat one book
    assert of["zettel/tie"] == "stats"  # one each: the course
    assert of["zettel/lonely"] == "other"  # nothing to go by: unnamed
    assert research["bigMs"] < 500  # once per graph update, cheap on 2,000 notes


def test_the_research_hubs_entries_are_read_once_per_scan(tmp_path):
    from kurooto.web.live import Graph

    def note(rel, text):
        f = tmp_path / f"{rel}.md"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")

    note(
        "maps/research",
        "# Research\n\n"
        "- [[projects/l96/index|L96 parameterization]]: with [[zettel/subgrid]]\n"
        "  - topics: [[zettel/closure]], [[zettel/lorenz-96]]\n"
        "- **Ring model** - [[projects/joy/index]] and [[radiation]]\n"
        "- Reading: [[zettel/unrelated]]\n",
    )
    for rel in ("projects/l96/index", "projects/joy/index", "zettel/subgrid", "zettel/closure", "zettel/lorenz-96"):
        note(rel, "x\n")
    note("zettel/radiation", "x\n")
    note("zettel/unrelated", "x\n")
    g = Graph(tmp_path)
    g.lay = {"research": "maps/research", "project": "projects/{project}/index"}
    assert g.scan() is True
    r = g.payload["research"]
    assert r == {
        "l96": {"name": "L96 parameterization", "topics": ["zettel/closure", "zettel/lorenz-96", "zettel/subgrid"]},
        "joy": {"name": "Ring model", "topics": ["zettel/radiation"]},
    }
    assert g.payload["layout"]["research"] == "maps/research"
    assert g.scan() is False  # nothing changed: not read again
    g.lay = {"research": "research/index", "project": "research/{project}/index"}
    assert g.scan() is True and g.payload["research"] == {}  # another layout: the map is redrawn for it


def test_the_layout_tells_the_map_where_research_is(tmp_path, monkeypatch):
    from kurooto.app import App
    from kurooto.web.live import graph_layout

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "home"))
    app = App()
    try:
        assert graph_layout(app) == {"research": "research/index", "project": "research/{project}/index"}
        app.settings.set("notes.layout", "zettelkasten")
        assert graph_layout(app) == {"research": "maps/research", "project": "projects/{project}/index"}
    finally:
        app.close()


# ------------------------------------------------- provenance links (0.6.1): "Seen in" and reading lists size nothing
PROVENANCE = """
const ids = [], links = [];
const add = (id, title) => ids.push([id, title]);
add("maps/courses/atmos", "Physics of the Atmosphere");
add("sources/atmos/2026-08-05-books", "Books");  // a class post whose textbook was read: every concept "Seen in" it
add("sources/atmos/2026-08-12-lecture-2", "Lecture 2"); links.push(["maps/courses/atmos", "sources/atmos/2026-08-12-lecture-2"]);
for (let i = 0; i < 155; i++) { add(`zettel/c${i}`, `Concept ${i}`); links.push([`zettel/c${i}`, "sources/atmos/2026-08-05-books", 1]); }
links.push(["zettel/c1", "zettel/c2"], ["zettel/c1", "sources/atmos/2026-08-12-lecture-2"], ["sources/atmos/2026-08-05-books", "maps/courses/atmos"]);
const nodes = new Map(ids.map(([id, title], i) => [id, { id, title, x: i, y: i, deg: 0, nb: new Set(), out: new Set(), snb: new Set() }]));
for (const [a, b, via] of links) { const p = nodes.get(a), q = nodes.get(b); p.deg++; q.deg++; p.nb.add(b); q.nb.add(a); p.out.add(b); if (!via) { p.snb.add(b); q.snb.add(a); } }
assignHoods(nodes);
const post = nodes.get("sources/atmos/2026-08-05-books");
console.log(JSON.stringify({ post: { deg: post.deg, sdeg: post.sdeg }, hood: nodes.get("zettel/c7").neighborhood,
  ranked: rankLabels([...nodes.values()]).slice(0, 3).map((n) => n.id) }));
"""


def test_seen_in_links_keep_their_lines_but_dont_make_a_hub():
    r = run(PROVENANCE)
    assert r["post"] == {"deg": 156, "sdeg": 1}  # 155 "Seen in" links: drawn, but its dot is sized by the one you made
    assert r["hood"] == "atmos"  # a concept still joins the course it was read in
    assert "sources/atmos/2026-08-05-books" not in r["ranked"][1:]
    assert r["ranked"][0] == "maps/courses/atmos"


def test_the_notes_graph_marks_links_only_in_kuroots_provenance_blocks(tmp_path):
    from kurooto.web.live import Graph

    (tmp_path / "zettel").mkdir()
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "books-post.md").write_text("# Books\n", encoding="utf-8")
    (tmp_path / "sources" / "lecture.md").write_text(
        "# Lecture\n<!-- kurooto:material0a1b2c3d -->\n## Concepts in Slides\n[[zettel/ad]]\n"
        "<!-- /kurooto:material0a1b2c3d -->\n",
        encoding="utf-8",
    )
    (tmp_path / "zettel" / "ad.md").write_text(
        "# AD\nsee [[zettel/bp]]\n<!-- kurooto:seen -->\n## Seen in\n- [[sources/books-post|Books]] pp. 1–3\n"
        "- [[zettel/bp]]\n<!-- /kurooto:seen -->\n",
        encoding="utf-8",
    )
    (tmp_path / "zettel" / "bp.md").write_text("# BP\n", encoding="utf-8")
    g = Graph(tmp_path)
    g.scan()
    links = g.payload["links"]
    assert ("zettel/ad", "zettel/bp") in links  # yours (also in the block): a link you'd follow
    assert ("zettel/ad", "sources/books-post", 1) in links and ("sources/lecture", "zettel/ad", 1) in links
    assert len(links) == 3
