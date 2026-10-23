"""Dreaming (modules/dreaming.py): the night's work in one morning message, with the loose ends; nothing when
nothing happened; the concept graph's own morning line folds into it."""

import datetime as dt


def test_the_night_in_one_message_with_the_loose_ends(env):
    app = env.app
    env.on("dreaming")
    ev = app.events
    ev.emit("integrate_batch", book="x/y", batch="1-12", new=5, links=9)
    ev.emit("integrate_batch", book="x/y", batch="13-24", new=2, links=4)
    ev.emit("book_read", pages=120)
    ev.emit("integrate_pruned", links=3)
    ev.emit("handwritten_linked", concepts=4, lecture=True, doubts=1)
    ev.emit("call_reviewed", lessons=2)
    ev.emit("learning_skill_learned", name="lab-report")
    ev.emit("learning_remembered", n=1)
    ev.emit("inferred", kind="project", via="journal")
    ev.emit("job_failed", key="x", outcome="error", error="boom")
    hw = app.workspace / "handwritten"
    hw.mkdir(parents=True, exist_ok=True)
    (hw / "n.md").write_text(
        "# Notes\n\n## Doubts\n- What is a component? (page 1)\n- Conditions for droplet formation (page 5)\n"
    )
    text = app.modules["dreaming"].morning()
    assert text.startswith("While you slept:")
    for bit in ("2 stretches of your books", "7 new concept notes, 13 links", "1 new book (120 pages)",
                "Tidied 3 links", "Linked 1 handwritten note", "2 lessons for calls", "1 skill", "Kept 1 thing",
                "Set up 1 thing", "Loose ends:", "What is a component?", "1 AI request failed"):  # fmt: skip
        assert bit in text, bit
    assert "Dreaming" in str(env.fake.sent[-1]) or "While you slept" in env.fake.texts()[-1]
    # the next morning covers only what's new since: nothing happened, no doubts edited lately -> no message
    (hw / "n.md").write_text("# Notes\n")
    n = len(env.fake.texts())
    assert app.modules["dreaming"].morning() == "" and len(env.fake.texts()) == n


def test_the_graphs_own_morning_line_folds_into_dreaming(env):
    app = env.app
    ig = app.modules["integrate"]
    ig.save("ledger.json", {"books": {}, "nights": {dt.date.today().isoformat(): {"batches": 3, "new": 2, "links": 5}}})
    env.on("dreaming")
    n = len(env.fake.texts())
    line = ig.summary()
    assert line.startswith("Concept graph: 3 batches") and len(env.fake.texts()) == n  # not sent on its own
