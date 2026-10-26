"""The concept graph's look-alike notes and notation (0.6.0): pairs of notes that look like one concept come as one
question a morning with Merge / Keep both / Add alias (each with Undo), and a concept a second source writes
differently gets a quote-checked "Notation" table. A fake AI answers the reading; the rest is real."""

# ruff: noqa: F811  (the world fixture is imported)
import json

import pytest

from kurooto.core import conceptgraph as cg
from kurooto.core import graphmerge
from kurooto.core import graphwrite as gw
from kurooto.core import integrate_ai as ai
from kurooto.core.state import jsave
from tests.unit.test_integrate import USER_TEXT, answer, c_bp, run_all, world  # noqa: F401 (a fixture)
from tests.unit.test_integrate_sources import file_batch, slides

FRONT = "---\nid: {slug}\naliases: [{aliases}]\ntags: [zettel]\ntrust_tier: agent_written\n---\n"
WIENER_DEF = "A Gaussian process with independent increments and continuous paths, started at zero."


def note(env, slug: str, body: str, aliases: str = "") -> str:
    path = env.app.workspace / f"{slug}.md"
    text = FRONT.format(slug=slug, aliases=aliases) + body
    path.write_text(text, encoding="utf-8")
    return text


def setup_pair(env, made: bool = True, auto: bool = False):
    """Brownian motion (yours, two notes link to it) and Wiener process (written by the graph, sharing the name), and a
    note whose typed link points at the second. auto=False: integrate.auto_merge off, so the pair is asked (0.8.8)."""
    ig = env.integrate
    env.app.settings.set("integrate.auto_merge", auto)
    texts = {
        "bm": note(
            env,
            "zettel/brownian-motion",
            "# Brownian motion\n\nThe random walk in the limit.\n\n" + USER_TEXT,
            '"Brownian motion"',
        ),
        "itô": note(
            env,
            "zettel/ito-integral",
            "# Itô integral\n\nIntegrates against noise.\n\n## Links\n"
            "- needs:: [[zettel/brownian-motion]] — the integrator is a Brownian path with independent increments\n",
        ),
    }
    body = gw.new_note(
        FRONT.format(slug="zettel/wiener-process", aliases='"Wiener process", "Brownian motion"'),
        gw.Concept("Wiener process", "zettel/wiener-process", [], WIENER_DEF),
        ["- needs:: [[zettel/gradient-descent]] — a made-up link that only checks links move across"],
        "Source: Bishop: Deep Learning, pp. 1–6",
    )
    rows = [{"book": "deep-learning/bishop", "note": "x", "title": "Bishop", "batch": "1-6", "pages": [1, 6]}]
    body = gw.put_block(body, "seen", ig.seen_body(rows))
    (env.app.workspace / "zettel" / "wiener-process.md").write_text(body, encoding="utf-8")
    texts["wp"] = body
    gd = env.app.workspace / "zettel" / "gradient-descent.md"
    gd.write_text(
        gd.read_text(encoding="utf-8")
        + "\n## Links\n- used-in:: [[zettel/wiener-process]] — noisy gradient steps follow a Wiener path\n",
        encoding="utf-8",
    )
    texts["gd"] = gd.read_text(encoding="utf-8")
    bp = env.app.workspace / "zettel" / "backpropagation.md"
    bp.write_text(bp.read_text(encoding="utf-8") + "See [[zettel/brownian-motion]] too.\n", encoding="utf-8")
    texts["bp"] = bp.read_text(encoding="utf-8")
    jsave(ig.dir / "seen.json", {"zettel/wiener-process": rows})
    if made:
        jsave(ig.dir / "made.json", {"zettel/wiener-process": gw.outside_hash(body)})
    return texts


def read(env, slug):
    return (env.app.workspace / f"{slug}.md").read_text(encoding="utf-8")


def last(env):
    return [p for m, p in env.fake.sent if m == "sendMessage"][-1]


def buttons(msg):
    return [b["callback_data"] for row in msg["reply_markup"]["inline_keyboard"] for b in row]


# ---------------------------------------------------------------------------------------------------- finding
def test_pairs_by_name_shared_name_and_meaning_but_not_ones_linked_as_different(world):
    env = world
    setup_pair(env)
    note(env, "zettel/back-propagation", "# Back-propagation\n\nThe same again.\n")
    note(env, "zettel/forward-mode", "# Forward mode\n\nTangents.\n")
    note(
        env,
        "zettel/reverse-mode",
        "# Reverse mode\n\nAdjoints.\n\n## Links\n- contrasts-with:: [[zettel/forward-mode]] — x\n",
    )
    lecture = env.app.workspace / "zettel" / "2026-10-20-backpropagation.md"
    lecture.write_text("# Backpropagation\n\nA dated note: a lecture, not a concept.\n", encoding="utf-8")
    index = cg.Index(cg.scan(env.app))
    index.vec = {"zettel/forward-mode": [1.0, 0.0, 0.1], "zettel/reverse-mode": [1.0, 0.0, 0.12]}
    index.vec["zettel/ito-integral"] = [0.0, 1.0, 0.0]
    index.vec["zettel/gradient-descent"] = [0.05, 1.0, 0.0]  # 0.9987 alike: a pair by meaning
    got = {(p.a, p.b, p.why) for p in cg.near_duplicates(index)}
    assert ("zettel/backpropagation", "zettel/back-propagation", "name") in got
    assert ("zettel/brownian-motion", "zettel/wiener-process", "alias") in got  # the one more notes link to stays
    assert any(p.why == "meaning" and {p.a, p.b} == {"zettel/ito-integral", "zettel/gradient-descent"} for p in
               cg.near_duplicates(index))  # fmt: skip
    assert not any({p.a, p.b} == {"zettel/forward-mode", "zettel/reverse-mode"} for p in cg.near_duplicates(index))
    assert not any("2026-10-20" in p.a + p.b for p in cg.near_duplicates(index))
    skip = {cg.pair_key("zettel/backpropagation", "zettel/back-propagation")}
    assert not any(p.why == "name" for p in cg.near_duplicates(index, skip))


def test_one_question_a_morning_with_three_buttons_a_pair(world):
    env = world
    setup_pair(env)
    assert graphmerge.night(env.integrate)
    msg = last(env)
    assert "1. Brownian motion and Wiener process: they share the name" in msg["text"]
    assert [b.split(":")[2] for b in buttons(msg)][:3] == ["merge", "keep", "alias"]
    assert graphmerge.night(env.integrate) == ""  # one a day
    env.app.settings.set("integrate.duplicates", False)
    assert graphmerge.night(env.integrate) == ""


# ---------------------------------------------------------------------------------------------------- merging
def test_merge_moves_links_seen_names_and_text_and_undo_puts_everything_back(world):
    env = world
    texts = setup_pair(env)
    graphmerge.night(env.integrate)
    merge = next(b for b in buttons(last(env)) if b.endswith(":merge"))
    said = env.press(merge)
    assert said.startswith("Merged Wiener process into Brownian motion")
    bm, wp, gd = (
        read(env, "zettel/brownian-motion"),
        read(env, "zettel/wiener-process"),
        read(env, "zettel/gradient-descent"),
    )
    assert USER_TEXT in bm and '"Wiener process"' in bm  # yours untouched; the name is an alias now
    assert "- needs:: [[zettel/gradient-descent]] — a made-up link" in bm and "<!-- kurooto:seen -->" in bm
    assert "### From [[zettel/wiener-process|Wiener process]]" in bm and WIENER_DEF in bm
    # all of it was Kurooto's: it shrinks to a redirect
    assert "<!-- kurooto:merged-into -->" in wp and WIENER_DEF not in wp and "[[zettel/brownian-motion|" in wp
    assert "- used-in:: [[zettel/brownian-motion]] — noisy gradient steps" in gd
    seen = env.integrate.load("seen.json", {})
    assert "zettel/wiener-process" not in seen and seen["zettel/brownian-motion"][0]["title"] == "Bishop"
    index = env.integrate.index()
    assert "zettel/wiener-process" not in index.notes
    assert index.match_name("Wiener process")[0] == "zettel/brownian-motion"  # new reading lands on the kept note
    undo = last(env)
    assert undo["text"].startswith("Merged") and buttons(undo) == [merge.replace(":merge", ":undo")]
    assert env.press(buttons(undo)[0]) == "Merge undone."
    for slug, key in (
        ("zettel/brownian-motion", "bm"),
        ("zettel/wiener-process", "wp"),
        ("zettel/gradient-descent", "gd"),
    ):
        assert read(env, slug) == texts[key], slug
    assert "zettel/wiener-process" in env.integrate.load("seen.json", {})


def test_a_merge_writes_links_in_your_link_style(world):
    env = world
    env.app.settings.set("notes.links", "markdown")
    setup_pair(env)
    graphmerge.night(env.integrate)
    env.press(next(b for b in buttons(last(env)) if b.endswith(":merge")))
    bm, wp, gd = (
        read(env, "zettel/brownian-motion"),
        read(env, "zettel/wiener-process"),
        read(env, "zettel/gradient-descent"),
    )
    assert "- needs:: [gradient descent](gradient-descent.md) — a made-up link" in bm
    assert "### From [Wiener process](wiener-process.md)" in bm
    assert "Merged into [Brownian motion](brownian-motion.md)" in wp
    assert "- used-in:: [brownian motion](brownian-motion.md) — noisy gradient steps" in gd


def test_a_note_with_your_text_keeps_it_and_only_gets_the_redirect(world):
    env = world
    setup_pair(env, made=False)  # not known to be all Kurooto's
    graphmerge.night(env.integrate)
    env.press(next(b for b in buttons(last(env)) if b.endswith(":merge")))
    wp = read(env, "zettel/wiener-process")
    assert WIENER_DEF in wp and "<!-- kurooto:merged-into -->" in wp
    assert wp.index("merged-into") < wp.index(WIENER_DEF)  # under the title, seen first
    assert "<!-- kurooto:seen -->" not in wp and "needs::" not in wp  # Kurooto's parts moved
    assert "(what you wrote there stays in that note)" in read(env, "zettel/brownian-motion")


def test_keep_both_is_never_asked_again_and_add_alias_links_them(world):
    env = world
    setup_pair(env)
    graphmerge.night(env.integrate)
    keep = next(b for b in buttons(last(env)) if b.endswith(":keep"))
    assert env.press(keep).startswith("Kept both")
    assert graphmerge.find(env.integrate, again=True)[0] == []
    env.press(keep.replace(":keep", ":undo"))
    (p,), _ = graphmerge.find(env.integrate, again=True)
    text, rows = graphmerge.ask_now(env.integrate)
    alias = next(b for row in rows for _, b in row if b.endswith(":alias"))
    assert env.press(alias).startswith("Wiener process is now an alias of Brownian motion")
    bm, wp = read(env, "zettel/brownian-motion"), read(env, "zettel/wiener-process")
    assert '"Wiener process"' in bm and "- equivalent-to:: [[zettel/wiener-process]]" in bm
    assert "- equivalent-to:: [[zettel/brownian-motion]]" in wp and WIENER_DEF in wp


def test_graph_same_answers_with_the_pairs(world):
    env = world
    setup_pair(env)
    env.say("/graph same")
    assert "Brownian motion and Wiener process" in last(env)["text"] and buttons(last(env))


# ---------------------------------------------------------------------------------------------------- notation
def test_symbols_must_be_in_their_quote():
    assert ai.symbol_in("W_t", "the process W t is a martingale")
    assert not ai.symbol_in("B_t", "the process W t is a martingale")
    assert ai.symbol_in(r"e^{-2\pi i x \xi}", "we write it as e−2πixξ dx")  # a PDF has the characters
    assert ai.symbol_in(r"2\pi in the exponent", "we put the 2π in the exponent")


def test_a_second_source_with_other_notation_gets_a_checked_table(world):
    env = world
    env.app.settings.set("modules.enabled", [*env.app.settings.get("modules.enabled"), "research_addon"])
    book = {"symbol": "delta", "what": "the local error of a unit", "quote": "The local error delta of a hidden unit"}
    made_up = {"symbol": "\\varepsilon", "what": "made up", "quote": "this sentence is not in the pages at all"}
    env.fake_ai.answer = answer(c_bp(notation=[book, made_up]))
    env.integrate.tick()
    run_all(env)
    rows = env.integrate.load("notation.json", {})["zettel/backpropagation"]
    assert [r["symbol"] for r in rows] == ["delta"]  # the quote that isn't there: dropped
    assert "kurooto:notation" not in read(env, "zettel/backpropagation")  # one source: nothing to compare
    extra = "In these slides the error signal e_j of unit j is passed back to the layer before."
    file_batch(env, slides(extra))
    slide = {"symbol": "e_j", "what": "the local error of a unit", "quote": "the error signal e_j of unit j"}
    env.fake_ai.answer = answer(
        c_bp(pages=[7], quote="the error signal e_j of unit j is passed back", notation=[slide])
    )
    env.integrate.tick()
    run_all(env)
    text = read(env, "zettel/backpropagation")
    assert "<!-- kurooto:notation -->\n## Notation\n| Source | Notation | What it stands for |" in text
    assert "| Bishop: Deep Learning, pp. 1–6 | delta | the local error of a unit |" in text
    assert "| Lecture 8 slides, slides 1–7 | $e_j$ | the local error of a unit |" in text
    assert USER_TEXT in text
    prompt = json.dumps(env.fake_ai.requests[0])
    assert "notation" in prompt and "the notation exactly as these pages write it" in prompt


# ---------------------------------------------------------------------------------------------- fixing itself (0.8.8)
def undo_buttons(msg):
    return [b for b in buttons(msg) if b.endswith(":undo")]


def test_a_clear_pair_merges_by_itself_and_the_morning_line_has_its_undo(world):
    env = world
    texts = setup_pair(env, auto=True)  # a shared name, both notes Kurooto's
    assert graphmerge.night(env.integrate) == ""  # nothing left to ask
    wp = read(env, "zettel/wiener-process")
    assert "<!-- kurooto:merged-into -->" in wp
    assert WIENER_DEF in read(env, "zettel/brownian-motion")  # its text moved into the kept note: nothing lost
    st = graphmerge.load(env.integrate)
    (rec,) = [r for r in st["pairs"].values() if r.get("auto")]
    assert rec["state"] == "merge"
    env.integrate.summary()  # Dreaming is off: the concept graph's morning line carries it
    msg = last(env)
    assert "Merged 1 look-alike concept note by themselves" in msg["text"]
    assert "1. Wiener process into Brownian motion" in msg["text"]
    (undo,) = undo_buttons(msg)
    assert graphmerge.merged_section(env.integrate) == ("", [])  # told once
    assert env.press(undo) == "Merge undone."
    for slug, key in (
        ("zettel/brownian-motion", "bm"),
        ("zettel/wiener-process", "wp"),
        ("zettel/gradient-descent", "gd"),
    ):
        assert read(env, slug) == texts[key], slug
    # undone: never merged by itself again, asked instead
    assert graphmerge.auto(env.integrate) == []
    assert graphmerge.night(env.integrate)
    assert "Brownian motion and Wiener process" in last(env)["text"]


def test_a_note_you_wrote_is_never_merged_by_itself(world):
    env = world
    setup_pair(env, auto=True)
    bm = env.app.workspace / "zettel" / "brownian-motion.md"
    bm.write_text(bm.read_text(encoding="utf-8").replace("trust_tier: agent_written\n", ""), encoding="utf-8")
    assert graphmerge.auto(env.integrate) == []
    assert "merged-into" not in read(env, "zettel/wiener-process")
    text, rows = graphmerge.ask_now(env.integrate)  # asked, as before
    assert "Brownian motion and Wiener process" in text and any(b.endswith(":merge") for r in rows for _, b in r)


def test_meaning_merges_by_itself_only_above_the_strict_threshold(world, monkeypatch):
    env = world
    env.app.settings.set("integrate.auto_merge", True)
    note(env, "zettel/forward-mode", "# Forward mode\n\nTangents pushed forward.\n")
    note(env, "zettel/tangent-propagation", "# Tangent propagation\n\nTangents pushed forward again.\n")
    ig = env.integrate
    vec = {"zettel/forward-mode": [1.0, 0.0, 0.0], "zettel/tangent-propagation": [1.0, 0.3, 0.0]}  # 0.958 alike

    def index(refresh=True):
        i = cg.Index(cg.scan(env.app))
        i.vec = {k: v for k, v in vec.items() if k in i.notes}
        return i

    monkeypatch.setattr(ig, "index", index)
    assert graphmerge.auto(ig) == []  # over the question's 0.92, under 0.97: asked
    (p,), _ = graphmerge.find(ig, again=True)
    assert p.why == "meaning"
    vec["zettel/tangent-propagation"] = [1.0, 0.1, 0.0]  # 0.995 alike
    (m,) = graphmerge.auto(ig)
    assert {m["a"], m["b"]} == {"zettel/forward-mode", "zettel/tangent-propagation"}
    env.app.settings.set("integrate.auto_merge_min", 0.5)  # never below the question's own 0.92
    assert graphmerge.auto_min(ig) == cg.DUP_COSINE


def test_same_name_texts_far_apart_are_asked_not_merged(world, monkeypatch):
    env = world
    env.app.settings.set("integrate.auto_merge", True)
    note(env, "zettel/kernel", "# Kernel\n\nThe vectors a linear map sends to zero.\n")
    note(env, "zettel/kernel-function", "# Kernel\n\nA similarity function for an SVM.\n")
    ig = env.integrate

    def index(refresh=True):
        i = cg.Index(cg.scan(env.app))
        i.vec = {"zettel/kernel": [1.0, 0.0], "zettel/kernel-function": [0.2, 1.0]}
        return i

    monkeypatch.setattr(ig, "index", index)
    assert graphmerge.auto(ig) == []
    (p,), _ = graphmerge.find(ig, again=True)
    assert p.why == "name"  # asked instead


def test_off_switch_and_graph_same_says_what_it_merged(world):
    env = world
    setup_pair(env, auto=False)
    assert graphmerge.auto(env.integrate) == []
    env.app.settings.set("integrate.auto_merge", True)
    env.say("/graph same")
    msg = last(env)
    assert msg["text"].startswith("Merged 1 look-alike concept note by themselves")
    assert "No other look-alike concept notes to ask about." in msg["text"] and undo_buttons(msg)


def test_run_alls_look_alike_step_merges_and_hands_back_the_undo(world):
    from kurooto.core import runall

    env = world
    setup_pair(env, auto=True)
    run = runall.Run(env.app, [])
    assert runall.same_step(run).startswith("1 look-alike pair merged by themselves (Undo below), 0 unsure pairs")
    assert [b for row in run.buttons for _, b in row][0].endswith(":undo")
    env.app.settings.set("integrate.duplicates", False)
    with pytest.raises(runall.Skip):
        runall.same_step(run)


def test_with_dreaming_on_the_merges_are_in_its_morning_message(world):
    env = world
    env.on("dreaming")
    setup_pair(env, auto=True)
    graphmerge.auto(env.integrate)
    assert env.integrate.summary() == ""  # Dreaming's message carries it instead
    text = env.app.modules["dreaming"].report(send=True)
    assert "Merged 1 look-alike concept note by themselves" in text
    assert undo_buttons(last(env))


def test_run_alls_garden_step_waits_for_the_pass_and_a_stop_doesnt_outlive_it(world):
    from kurooto.core import runall

    env = world
    run = runall.Run(env.app, [])
    run.stop.set()  # stopped before the first note: nothing sent, and the next garden isn't held by it
    assert runall.garden_step(run).startswith("0 notes sent to be linked (stopped")
    assert env.integrate.garden_halt is None
    env.app.settings.set("integrate.garden", False)
    with pytest.raises(runall.Skip):
        runall.garden_step(runall.Run(env.app, []))
