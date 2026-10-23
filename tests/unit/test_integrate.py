"""The concept graph: reading becomes linked notes. A fake AI answers; everything else is real: the sections of the
book, finding related notes, the checks on the answer, the second look, the safe writes and the ledger."""

import json

import pytest

from kurooto.core import conceptgraph as cg
from kurooto.core import graphwrite as gw
from kurooto.core import integrate_ai as ai
from kurooto.core.state import jsave
from tests.fakes.openai import FakeOpenAI

PAGES = {
    1: "8. BACKPROPAGATION\n8.1. Evaluation of Gradients\nBackpropagation evaluates the gradient of the error function "
    "with respect to every weight in a feed-forward network.",
    2: "8.1. EVALUATION OF GRADIENTS 233\nThe local error delta of a hidden unit is the weighted sum of the deltas "
    "of the units that receive input from it.",
    3: "234 8. BACKPROPAGATION\nSection 3.4\nThe derivatives are then accumulated over the forward and backward pass.",
    4: "8.2. Automatic Differentiation\nForward-mode automatic differentiation propagates tangent vectors alongside "
    "the values of the intermediate variables.",
    5: "8.2. AUTOMATIC DIFFERENTIATION 244\nReverse-mode automatic differentiation computes all partial derivatives "
    "of a scalar output in one backward sweep.",
    6: "246 8. BACKPROPAGATION\nBackpropagation is the special case of reverse-mode automatic differentiation for "
    "layered networks.",
}
QUOTE_AD = (
    "Reverse-mode automatic differentiation computes all partial derivatives of a scalar output in one backward sweep"
)
QUOTE_BP = "Backpropagation evaluates the gradient of the error function with respect to every weight"
USER_TEXT = "My own remark: remember the chain rule derivation from the lecture.\n"


@pytest.fixture
def world(env, tmp_path, monkeypatch):
    """A paired assistant with Books and the concept graph on, a fake AI, one book read, and one concept note."""
    from kurooto import providers

    monkeypatch.setattr(providers, "AGENT_PROGRAMS", ())  # whatever agent programs this computer has stay out of it
    fake = FakeOpenAI()
    app = env.app
    app.secrets.set("custom.api_key", fake.key)
    app.settings.set("brain.base_urls", {"custom": fake.base})
    app.settings.set("brain.models", {"custom": {"low": "m", "medium": "m", "high": "m"}})
    app.settings.set("brain.main", "custom")
    app.settings.set("notes.layout", "zettelkasten")
    app.settings.set("books.folder", str(tmp_path / "shelf"))
    app.settings.set("integrate.embeddings", "off")
    app.power.current = "normal"
    jsave(app.paths.state / "books.json", {"set_up": True})
    env.on("books", "integrate")
    shelf = tmp_path / "shelf" / "deep-learning"
    shelf.mkdir(parents=True)
    (shelf / "bishop.pdf").write_bytes(b"%PDF-1.4 fake")
    books = app.modules["books"]
    b = next(x for x in books.library() if x["id"] == "bishop")
    d = books.book_dir(b)
    d.mkdir(parents=True)
    text = "# Bishop\n\n" + "".join(f'<a id="p-{n}"></a>\n## [p. {n}]\n\n{t}\n\n' for n, t in PAGES.items())
    (d / "text.md").write_text(text, encoding="utf-8")
    jsave(d / "meta.json", {"pages": 6, "done": 6, "title": "Bishop: Deep Learning", "routes": {"text": 6}})
    ws = app.workspace
    (ws / "zettel").mkdir(parents=True, exist_ok=True)
    note = ws / "zettel" / "backpropagation.md"
    note.write_text(
        "---\nid: zettel/backpropagation\naliases: [backprop]\ntags: [zettel]\ntrust_tier: agent_written\n---\n"
        "# Backpropagation\n\nBackpropagation computes the gradient of the error in a network.\n\n"
        + USER_TEXT
        + "\n## Links\n- [[zettel/gradient-descent]]: it supplies the gradient that gradient descent uses\n",
        encoding="utf-8",
    )
    (ws / "zettel" / "gradient-descent.md").write_text(
        "---\nid: zettel/gradient-descent\naliases: []\ntags: [zettel]\n---\n"
        "# Gradient descent\n\nMoves against the gradient.\n",
        encoding="utf-8",
    )
    (ws / "maps" / "courses").mkdir(parents=True, exist_ok=True)
    (ws / "maps" / "courses" / "deep-learning.md").write_text("# Deep learning\n", encoding="utf-8")
    env.fake_ai = fake
    env.integrate = app.modules["integrate"]
    env.book = b
    yield env
    fake.close()


def answer(*concepts):
    return json.dumps({"concepts": list(concepts)})


def c_ad(**kw):
    base = {
        "name": "Automatic differentiation",
        "aliases": ["autodiff"],
        "role": "core",
        "kind": "method",
        "definition": "A family of methods that evaluate exact derivatives of a program by applying the chain rule.",
        "formulas": [],
        "prereqs": [],
        "pages": [4, 5],
        "quote": QUOTE_AD,
        "same_as": None,
        "update": "",
        "links": [
            {
                "target": "zettel/backpropagation",
                "relation": "generalises",
                "reason": "backpropagation is reverse-mode differentiation applied to a layered network",
                "confidence": 0.9,
            }
        ],
    }
    return {**base, **kw}


def c_bp(**kw):
    base = {
        "name": "Backpropagation",
        "aliases": ["backprop"],
        "role": "core",
        "kind": "method",
        "definition": "Evaluates the gradient of the error with respect to every weight.",
        "formulas": [],
        "prereqs": [],
        "pages": [1],
        "quote": QUOTE_BP,
        "same_as": "zettel/backpropagation",
        "update": "Chapter 8 states the local error delta of a hidden unit as a weighted sum over the units it feeds.",
        "links": [],
    }
    return {**base, **kw}


def run_all(env):
    """Run every queued AI request (bulk and second looks) to completion."""
    n = 0
    while env.app.jobs.run_next():
        n += 1
        assert n < 20
    return n


# ----------------------------------------------------------------------------------------------------- the flow
def test_a_batch_becomes_notes_links_and_a_chapter_list(world):
    env = world
    env.fake_ai.answer = answer(c_ad(), c_bp())
    assert env.integrate.tick() == {"submitted": 1}
    run_all(env)
    ws = env.app.workspace
    new = (ws / "zettel" / "automatic-differentiation.md").read_text(encoding="utf-8")
    assert "# Automatic differentiation" in new and 'aliases: ["Automatic differentiation", "autodiff"]' in new
    assert "- generalises:: [[zettel/backpropagation]] — backpropagation is reverse-mode" in new
    assert "<!-- kurooto:seen -->" in new and "pp. 1–6" in new and "trust_tier: agent_written" in new
    old = (ws / "zettel" / "backpropagation.md").read_text(encoding="utf-8")
    assert USER_TEXT in old and "[[zettel/gradient-descent]]: it supplies" in old  # what was there is untouched
    assert "### Added from the books" in old and "local error delta" in old
    stub = env.integrate.stub(env.book)
    assert not stub.exists()  # (the books module wrote no stub in this test) ...
    course = (ws / "maps" / "courses" / "deep-learning.md").read_text(encoding="utf-8")
    assert "## From the books" in course and "[[zettel/automatic-differentiation|Automatic differentiation]]" in course
    led = env.integrate.load("ledger.json", {})
    rec = led["books"]["deep-learning/bishop"]["batches"]["1-6"]
    assert rec["state"] == "done" and rec["new"] == 1 and rec["same"] == 1 and rec["links"] == 1
    assert env.integrate.tick().get("idle")  # nothing left


def test_the_prompt_shows_the_pages_and_the_related_notes_only(world):
    env = world
    env.fake_ai.answer = answer()
    env.integrate.tick()
    run_all(env)
    prompt = json.dumps(env.fake_ai.requests[0])
    assert "[p. 4]" in prompt and "zettel/backpropagation" in prompt
    assert "Section 3.4" in prompt  # the page text is given as it is
    assert "Gradient descent" in prompt or "gradient-descent" in prompt  # a neighbour of the best match


def test_a_name_that_matches_an_existing_note_is_never_a_second_note(world):
    env = world
    env.fake_ai.answer = answer(c_bp(name="Back-propagation", aliases=[], same_as=None, update=""))
    env.integrate.tick()
    run_all(env)
    notes = sorted(p.name for p in (env.app.workspace / "zettel").glob("*.md"))
    assert notes == ["backpropagation.md", "gradient-descent.md"]
    assert "<!-- kurooto:seen -->" in (env.app.workspace / "zettel" / "backpropagation.md").read_text(encoding="utf-8")


def test_running_the_same_batch_twice_changes_nothing_the_second_time(world):
    env = world
    env.fake_ai.answer = answer(c_ad(), c_bp())
    env.integrate.tick()
    run_all(env)
    ws = env.app.workspace
    before = {p.name: p.read_text(encoding="utf-8") for p in (ws / "zettel").glob("*.md")}
    led = env.integrate.load("ledger.json", {})
    led["books"]["deep-learning/bishop"]["batches"]["1-6"]["state"] = "pending"
    env.integrate.save("ledger.json", led)
    env.integrate.tick()
    run_all(env)
    after = {p.name: p.read_text(encoding="utf-8") for p in (ws / "zettel").glob("*.md")}
    assert before == after


# ---------------------------------------------------------------------------------------------------- the checks
def test_a_quote_that_is_not_in_the_pages_gets_a_second_look_and_is_dropped_if_not_confirmed(world):
    env = world
    env.fake_ai.answer = answer(c_ad(quote="Automatic differentiation was invented by a committee in 1952 for weather"))
    env.integrate.tick()
    assert env.app.jobs.run_next()  # the bulk answer
    assert [r["kind"] for r in [{"kind": "concept"}]] and (
        env.app.workspace / "zettel" / "automatic-differentiation.md"
    ).exists() is False
    env.fake_ai.answer = json.dumps({"items": [{"id": 1, "keep": False}]})
    run_all(env)
    assert not (env.app.workspace / "zettel" / "automatic-differentiation.md").exists()
    rec = env.integrate.load("ledger.json", {})["books"]["deep-learning/bishop"]["batches"]["1-6"]
    assert rec["state"] == "done" and rec["flagged"] == 1 and rec["dropped"] == 1 and rec["new"] == 0


def test_a_second_look_can_confirm_a_doubtful_concept(world):
    env = world
    env.fake_ai.answer = answer(
        c_ad(quote="reverse-mode differentiation gets every partial derivative in a single backward pass")
    )
    env.integrate.tick()
    env.app.jobs.run_next()
    env.fake_ai.answer = json.dumps({"items": [{"id": 1, "keep": True}]})
    run_all(env)
    assert (env.app.workspace / "zettel" / "automatic-differentiation.md").exists()


def test_a_reason_that_fits_any_two_notes_is_checked_and_dropped(world):
    env = world
    vague = c_ad()
    vague["links"][0]["reason"] = "Related to the same family of ideas in the book"
    env.fake_ai.answer = answer(vague)
    env.integrate.tick()
    env.app.jobs.run_next()
    env.fake_ai.answer = json.dumps({"items": [{"id": 1, "keep": False}]})
    run_all(env)
    text = (env.app.workspace / "zettel" / "automatic-differentiation.md").read_text(encoding="utf-8")
    assert "Related to" not in text and "generalises::" not in text  # the concept is there; the vague link isn't


def test_a_second_look_can_improve_a_link_but_only_with_a_real_reason(world):
    env = world
    vague = c_ad()
    vague["links"][0]["reason"] = "connected formulation"
    env.fake_ai.answer = answer(vague)
    env.integrate.tick()
    env.app.jobs.run_next()
    env.fake_ai.answer = json.dumps(
        {"items": [{"id": 1, "keep": True, "relation": "generalises", "reason": "related to it"}]}
    )  # still vague: dropped
    run_all(env)
    assert "generalises::" not in (env.app.workspace / "zettel" / "automatic-differentiation.md").read_text(
        encoding="utf-8"
    )


def test_links_to_notes_that_do_not_exist_are_dropped(world):
    env = world
    bad = c_ad()
    bad["links"].append(
        {
            "target": "zettel/does-not-exist",
            "relation": "needs",
            "reason": "it needs a thing that isn't there at all",
            "confidence": 0.9,
        }
    )
    env.fake_ai.answer = answer(bad)
    env.integrate.tick()
    run_all(env)
    assert "does-not-exist" not in (env.app.workspace / "zettel" / "automatic-differentiation.md").read_text(
        encoding="utf-8"
    )


def test_an_unusable_answer_is_tried_again_then_given_up_on(world):
    env = world
    env.fake_ai.answer = "I could not do that."
    for _ in range(ai.PROMPT_VERSION + 2):
        env.integrate.tick()
        run_all(env)
    rec = env.integrate.load("ledger.json", {})["books"]["deep-learning/bishop"]["batches"]["1-6"]
    assert rec["state"] == "failed" and rec["tries"] == 3
    assert env.integrate.tick().get("idle")


# ------------------------------------------------------------------------------------------------------ safety
def test_a_write_that_would_change_your_text_is_refused(world, monkeypatch):
    env = world
    path = env.app.workspace / "zettel" / "backpropagation.md"
    before = path.read_text(encoding="utf-8")
    monkeypatch.setattr(
        gw, "put_block", lambda text, key, body, attrs="": text.replace("# Backpropagation", "# Backprop REWRITTEN")
    )
    env.fake_ai.answer = answer(c_bp())
    env.integrate.tick()
    run_all(env)
    assert path.read_text(encoding="utf-8") == before


def test_graphwrite_blocks_are_replaced_not_stacked_and_your_text_survives():
    text = "# T\n\nmine\n"
    one = gw.put_block(text, "seen", "## Seen in\n- a")
    two = gw.put_block(one, "seen", "## Seen in\n- a\n- b")
    assert two.count("<!-- kurooto:seen -->") == 1 and two.startswith("# T\n\nmine\n") and "- b" in two
    assert gw.outside_hash(text) == gw.outside_hash(two)
    assert gw.guarded(two, two.replace("mine", "changed")).ok is False


def test_links_already_in_the_note_are_not_added_again():
    text = "# T\n\nSee [[zettel/x]].\n\n## Links\n- [[zettel/y]]: because\n"
    new, n = gw.add_links(
        text,
        [
            ("zettel/x", "- needs:: [[zettel/x]] — a reason of some length"),
            ("zettel/z", "- needs:: [[zettel/z]] — a reason of some length"),
        ],
    )
    assert n == 1 and new.count("zettel/x") == 1 and "[[zettel/z]]" in new


def test_vague_reasons_are_recognised():
    for bad in (
        "Related to the course",
        "connected formulation of the idea",
        "Topical syllabus & examination alignment",
        "too short",
    ):
        assert gw.lint_reason(bad)
    assert gw.lint_reason("the deltas are the adjoints of reverse-mode differentiation on a layered graph") is None


# ----------------------------------------------------------------------------------------------------- finding
def test_candidates_find_aliases_titles_and_keywords_and_neighbours(world):
    env = world
    index = env.integrate.index()
    assert index.match_name("Backprop") == ("zettel/backpropagation", "alias")
    assert index.match_name("Back-propagation")[0] == "zettel/backpropagation"
    got = index.candidates("gradient of the error function in a network", limit=5)
    assert got[0].slug == "zettel/backpropagation" and "keyword" in got[0].evidence
    assert any(c.slug == "zettel/gradient-descent" for c in got)  # linked from the best match


def test_embeddings_add_meaning_when_there_is_a_model(world):
    env = world
    notes = cg.scan(env.app)
    vocab = ["gradient", "network", "error", "moves", "weights"]

    def embed(texts):
        return [[float(t.lower().count(w)) for w in vocab] + [0.01] for t in texts]

    embed.tag = "fake:"
    store = cg.VectorStore(env.integrate.dir / "v.db")
    index = cg.Index(notes, embed, store)
    assert len(index.vec) == 2
    got = index.candidates("gradient of the error in a network", limit=3)
    assert any("embedding" in c.evidence for c in got)
    again = cg.Index(notes, embed, store)  # nothing is embedded twice
    assert again.vec.keys() == index.vec.keys()


def test_parse_json_reads_fenced_and_wordy_answers():
    assert ai.parse_json('Here you go:\n```json\n{"concepts": []}\n```') == {"concepts": []}
    assert ai.parse_json('Sure. {"concepts": [{"name": "A"}]} Hope that helps.') == {"concepts": [{"name": "A"}]}
    assert ai.parse_json("no json here") is None


# ------------------------------------------------------------------------------------------------------- roles
def test_two_agent_programs_split_the_work_and_one_does_both(world, monkeypatch):
    env = world
    from kurooto import providers

    class Fake:
        kind = "cli"

        def __init__(self, id):
            self.id = id

        def available(self):
            return True, ""

    have = {"agy", "claude"}
    monkeypatch.setattr(providers, "AGENT_PROGRAMS", ("agy", "claude"))
    monkeypatch.setattr(providers, "build", lambda a, w: Fake(w) if w in have else None)
    assert env.integrate.roles() == ("agy", "claude")
    have.discard("agy")
    assert env.integrate.roles() == ("claude", "claude")
    env.app.settings.set("integrate.roles", {"bulk": "claude", "check": "agy"})
    have.add("agy")
    assert env.integrate.roles() == ("claude", "agy")


def test_with_no_agent_program_the_main_ai_does_both(world):
    assert world.integrate.roles() == ("custom", "custom")


# ---------------------------------------------------------------------------------------- order and the garden
def test_subjects_you_name_go_first_and_unread_pages_wait(world, tmp_path):
    env = world
    books = env.app.modules["books"]
    other = tmp_path / "shelf" / "topology"
    other.mkdir()
    (other / "munkres.pdf").write_bytes(b"%PDF-1.4 fake")
    b2 = next(x for x in books.library() if x["id"] == "munkres")
    d = books.book_dir(b2)
    d.mkdir(parents=True)
    (d / "text.md").write_text(  # as books.finish writes it: pages 3 and 4 aren't read yet
        "".join(f'<a id="p-{n}"></a>\n## [p. {n}]\n\nText {n}\n' for n in range(1, 3))
        + "".join(f'<a id="p-{n}"></a>\n## [p. {n}] (not read: not yet)\n\n\n' for n in range(3, 5)),
        encoding="utf-8",
    )
    jsave(d / "meta.json", {"pages": 4, "done": 2, "title": "Munkres"})
    todo = env.integrate.ready_batches()
    assert [b["id"] for b, _ in todo] == ["bishop"]  # the other has pages left to read: its batch isn't ready
    (d / "text.md").write_text(
        "".join(f'<a id="p-{n}"></a>\n## [p. {n}]\n\nText {n}\n' for n in range(1, 5)), encoding="utf-8"
    )
    jsave(d / "meta.json", {"pages": 4, "done": 4, "title": "Munkres"})
    env.app.settings.set("integrate.first", ["topology"])
    assert [b["id"] for b, _ in env.integrate.ready_batches()][0] == "munkres"


def test_the_garden_links_notes_nothing_links_to_and_checks_the_answer(world):
    env = world
    index = env.integrate.index()
    assert "zettel/backpropagation" in env.integrate.orphans(index)  # nothing links to it yet
    env.fake_ai.answer = json.dumps(
        {
            "links": [
                {
                    "target": "zettel/gradient-descent",
                    "relation": "needs",
                    "reason": "it needs the gradient that gradient descent also uses",
                    "confidence": 0.8,
                },
                {"target": "zettel/gradient-descent", "relation": "needs", "reason": "related to", "confidence": 0.9},
                {
                    "target": "zettel/nowhere",
                    "relation": "needs",
                    "reason": "this note does not exist anywhere in the vault",
                    "confidence": 0.9,
                },
            ]
        }
    )
    assert env.integrate.garden()["asked"] >= 1
    run_all(env)
    # gradient-descent is already linked by backpropagation: not added twice; nowhere doesn't exist
    gd = (env.app.workspace / "zettel" / "gradient-descent.md").read_text(encoding="utf-8")
    assert gd.count("[[zettel/") <= 1 and "nowhere" not in gd


def test_metrics_count_broken_links_and_vague_reasons(world):
    env = world
    p = env.app.workspace / "zettel" / "gradient-descent.md"
    p.write_text(
        p.read_text(encoding="utf-8") + "\n## Links\n- [[zettel/missing]]: Connected formulation of the idea\n",
        encoding="utf-8",
    )
    m = env.integrate.metrics()
    assert m["concepts"] == 2 and m["broken"] == 1 and m["boilerplate_reasons"] == 1
    out = env.say("/graph")
    assert "2 concepts" in out and "1 broken" in out


def test_a_job_can_be_pinned_to_an_ai_and_another_program_stands_in(world, monkeypatch):
    env = world
    from kurooto import providers
    from kurooto.providers.base import Result, Verdict

    ran = []

    class Fake:
        kind = "cli"
        denied_help = ""

        def __init__(self, id, verdict):
            self.id, self.label, self.verdict = id, id, verdict

        def available(self):
            return True, ""

        def prepare(self, app):
            pass

        def run(self, task):
            ran.append(self.id)
            return Result(self.verdict, "ok" if self.verdict == Verdict.OK else "")

    fakes = {"agy": Fake("agy", Verdict.OK), "claude": Fake("claude", Verdict.RATE_LIMITED)}
    monkeypatch.setattr(providers, "AGENT_PROGRAMS", ("agy", "claude"))
    monkeypatch.setattr(providers, "build", lambda a, w: fakes.get(w))
    env.app.jobs.submit("pinned", background=True, text_only=True, quiet=True, lane="chk", brain="claude")
    run_all(env)
    assert ran[:2] == ["claude", "agy"]  # pinned to Claude; it was at its limit, so agy took over


def test_smallest_books_go_first_unless_you_name_a_subject(world, tmp_path):
    env = world
    books = env.app.modules["books"]
    for name, pages in (("tiny", 3), ("huge", 9)):
        shelf = tmp_path / "shelf" / f"{name}-subject"
        shelf.mkdir()
        (shelf / f"{name}.pdf").write_bytes(b"%PDF-1.4 fake")
        bk = next(x for x in books.library() if x["id"] == name)
        d = books.book_dir(bk)
        d.mkdir(parents=True)
        (d / "text.md").write_text(
            "".join(f'<a id="p-{n}"></a>\n## [p. {n}]\n\nText {n}\n' for n in range(1, pages + 1)), encoding="utf-8"
        )
        jsave(d / "meta.json", {"pages": pages, "done": pages, "title": name})
    order = [b["id"] for b, _ in env.integrate.ready_batches()]
    assert order.index("tiny") < order.index("huge") and order.index("tiny") < order.index("bishop")
    env.app.settings.set("integrate.first", ["deep-learning"])
    assert [b["id"] for b, _ in env.integrate.ready_batches()][0] == "bishop"
    env.app.settings.set("integrate.order", "name")
    env.app.settings.set("integrate.first", [])
    assert [b["id"] for b, _ in env.integrate.ready_batches()][0] == "bishop"


def test_a_rate_limit_waits_and_is_not_a_failed_try(world):
    env = world
    env.fake_ai.mode = "429"
    env.integrate.tick()
    while env.app.jobs.run_next():
        pass
    rec = env.integrate.load("ledger.json", {})["books"]["deep-learning/bishop"]["batches"]["1-6"]
    assert rec["state"] == "pending" and rec.get("tries", 0) == 0
    env.fake_ai.mode = "ok"
    env.fake_ai.answer = answer(c_ad())
    assert env.integrate.tick()["submitted"] == 1  # asked again later


def test_effort_goes_up_for_a_book_that_needs_many_second_looks_or_a_retry(world):
    env = world
    bt = env.integrate.plan(env.book)[0]
    assert env.integrate.effort_for(env.book, bt) == "low"
    env.integrate.record(env.book, "x1", state="done", concepts=5, flagged=3)
    assert env.integrate.effort_for(env.book, bt) == "medium"
    env.integrate.record(env.book, bt.id, state="pending", tries=1)
    assert env.integrate.effort_for(env.book, bt) == "medium"


def test_cost_and_requests_are_counted_and_shown(world):
    from kurooto.providers.base import Result, Verdict

    env = world
    env.integrate.spend(Result(Verdict.OK, "x", usage={"cost": 0.0123}))
    env.integrate.spend(Result(Verdict.OK, "x", usage={}))
    out = env.say("/graph")
    assert "2 AI requests" in out and "$0.01" in out


def test_a_concept_dropped_after_a_second_look_is_linked_by_nobody(world):
    env = world
    ad = c_ad(quote="this quote is not anywhere in the pages at all, not one bit")
    bp = c_bp(same_as=None, name="Error backpropagation in layers", aliases=[], update="")
    bp["quote"] = QUOTE_BP
    bp["links"] = [
        {
            "target": "Automatic differentiation",
            "relation": "special-case-of",
            "reason": "the deltas are the adjoints of reverse-mode differentiation on a layered graph",
            "confidence": 0.9,
        }
    ]
    env.fake_ai.answer = answer(ad, bp)
    env.integrate.tick()
    env.app.jobs.run_next()
    env.fake_ai.answer = json.dumps({"items": [{"id": 1, "keep": False}]})  # the quote check fails: AD is dropped
    run_all(env)
    ws = env.app.workspace
    assert not (ws / "zettel" / "automatic-differentiation.md").exists()
    for p in (ws / "zettel").glob("*.md"):
        assert "[[zettel/automatic-differentiation]]" not in p.read_text(encoding="utf-8"), p.name


def test_the_daily_pass_takes_out_kuroots_links_to_notes_that_do_not_exist(world):
    env = world
    p = env.app.workspace / "zettel" / "gradient-descent.md"
    p.write_text(
        p.read_text(encoding="utf-8")
        + "\n## Links\n- needs:: [[zettel/gone-forever]] — a reason that is long enough to pass the check\n"
        + "- [[zettel/also-gone]]: your own link, kept as you wrote it\n",
        encoding="utf-8",
    )
    assert env.integrate.prune_dangling(env.integrate.index()) == 1
    text = p.read_text(encoding="utf-8")
    assert "gone-forever" not in text and "also-gone" in text


def test_a_signed_out_stand_in_retries_soon_instead_of_in_hours(world):
    env = world
    env.fake_ai.mode = "401"
    env.integrate.tick()
    while env.app.jobs.run_next():
        pass
    assert env.app.scheduler.get("integrate:soon") is not None


def test_graph_stop_holds_every_start_until_the_next_night_even_after_a_restart(world, monkeypatch):
    import datetime as dt

    from kurooto.modules import integrate as integrate_mod

    env = world
    t = {"now": dt.datetime(2026, 10, 21, 3, 0)}
    monkeypatch.setattr(integrate_mod, "now", lambda: t["now"])
    env.fake_ai.answer = answer(c_ad())
    out = env.say("/graph stop")
    assert "Stopped" in out and "Thu 01:30" in out, out
    assert env.app.scheduler.get("integrate:night") is not None  # the night's own start stays
    again = integrate_mod.Integrate(env.app)  # a restart: the stop is kept on disk
    for start in (again.tick, env.integrate.tick):  # the 3-hourly and 20-minute retries, a book read, an answer
        assert start({}) == {"submitted": 0, "stopped": True}
    t["now"] = dt.datetime(2026, 10, 22, 1, 30)
    assert env.integrate.tick({})["submitted"] == 1  # the next night goes ahead


def test_graph_now_goes_on_after_a_stop(world):
    env = world
    env.fake_ai.answer = answer(c_ad())
    env.say("/graph stop")
    assert env.integrate.tick()["submitted"] == 0
    assert env.say("/graph now") == "Started."


def test_a_merge_the_second_look_turns_down_becomes_its_own_note_and_leaves_the_other_alone(world):
    env = world
    gd = env.app.workspace / "zettel" / "gradient-descent.md"
    before = gd.read_text(encoding="utf-8")
    wrong = c_bp(name="Error backpropagation in layers", aliases=[], same_as="zettel/gradient-descent", update="")
    env.fake_ai.answer = answer(wrong)
    env.integrate.tick()
    env.app.jobs.run_next()
    env.fake_ai.answer = json.dumps({"items": [{"id": 1, "same": False}]})  # not the same note
    run_all(env)
    assert gd.read_text(encoding="utf-8") == before
    own = env.app.workspace / "zettel" / "error-backpropagation-in-layers.md"
    assert own.is_file() and "Evaluates the gradient of the error" in own.read_text(encoding="utf-8")


def test_a_book_with_a_skipped_page_still_finishes_its_last_batch(world):
    """ "done" counts pages read: with page 3 skipped (waiting for a reader), done is 5 of 6, and the last batch
    (pages 1-6) used to wait for page 6 <= 5 forever."""
    env = world
    d = env.app.modules["books"].book_dir(env.book)
    text = (d / "text.md").read_text(encoding="utf-8").replace("## [p. 3]\n", "## [p. 3] (not read: needs OCR)\n")
    (d / "text.md").write_text(text, encoding="utf-8")
    meta = {"pages": 6, "done": 5, "title": "Bishop", "skipped": {"3": "needs OCR"}}
    jsave(d / "meta.json", meta)
    assert env.integrate.ready_batches() == []  # still reading: the skipped page may come yet
    jsave(d / "meta.json", {**meta, "finished": "2026-10-21T02:00:00"})
    assert [bt.id for _, bt in env.integrate.ready_batches()] == ["1-6"]


def test_ready_batches_see_new_pages_though_each_books_pages_are_kept(world):
    """pages_read keeps a book's page numbers while its text file stays the same (0.6.1); a page read since counts at
    once, and the ledger handed to plan() gives the same batches as reading it there."""
    env = world
    d = env.app.modules["books"].book_dir(env.book)
    full = (d / "text.md").read_text(encoding="utf-8")
    cut = full[: full.index('<a id="p-6">')]
    (d / "text.md").write_text(cut, encoding="utf-8")
    assert env.integrate.pages_read(env.book) == {1, 2, 3, 4, 5}
    assert env.integrate.ready_batches() == []  # page 6 not read yet: the one batch (1-6) waits
    (d / "text.md").write_text(full, encoding="utf-8")
    assert env.integrate.pages_read(env.book) == {1, 2, 3, 4, 5, 6}
    assert [bt.id for _, bt in env.integrate.ready_batches()] == ["1-6"]
    led = env.integrate.load("ledger.json", {})
    assert env.integrate.plan(env.book, led) == env.integrate.plan(env.book)


def test_batches_follow_the_bookmarks_but_a_book_already_begun_keeps_its_batches(world):
    env = world
    env.app.settings.set("integrate.batch_pages", 3)
    d = env.app.modules["books"].book_dir(env.book)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    by_text = [bt.id for bt in env.integrate.plan(env.book)]
    jsave(d / "meta.json", {**meta, "outline": [[1, "Backpropagation", 1], [2, "Gradients", 1], [2, "Autodiff", 3]]})
    assert [bt.id for bt in env.integrate.plan(env.book)] == ["1-2", "3-6"] != by_text
    env.integrate.save("ledger.json", {"books": {"deep-learning/bishop": {"batches": {by_text[0]: {"state": "done"}}}}})
    assert [bt.id for bt in env.integrate.plan(env.book)] == by_text  # begun before: the same batches to the end
    env.integrate.record(env.book, by_text[1], state="pending")
    assert env.integrate.load("ledger.json", {})["books"]["deep-learning/bishop"]["plan"] == "text"


def test_the_both_ways_check_flags_two_notes_that_each_generalise_the_other_not_a_consistent_pair(world):
    index = world.integrate.index()

    def flags(rel_a, rel_b):
        a = ai.Proposed(**{**c_ad(links=[]), "slug": "zettel/a"})
        a.links = [ai.Link("zettel/backpropagation", rel_a, "backpropagation is reverse-mode on a layered net", 0.9)]
        b = ai.Proposed(**{**c_bp(same_as=None, links=[]), "slug": "zettel/backpropagation"})
        b.links = [ai.Link("Automatic differentiation", rel_b, "the deltas are the adjoints of reverse-mode AD", 0.9)]
        _, items = ai.check([a, b], index, PAGES, {cg.normalise("Automatic differentiation"): "zettel/a"})
        return [it.why for it in items if it.kind == "link"]

    assert flags("generalises", "special-case-of") == []  # the same fact said from both ends
    assert flags("generalises", "generalises") == ["both ways"]
    assert flags("special-case-of", "special-case-of") == ["both ways"]
