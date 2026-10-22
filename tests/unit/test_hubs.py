"""The hub notes: a home note and a research hub exist, list the courses, and the course pages link back, so nothing is
an island. Lines are added only, and never twice."""

from kurooto.core import hubs, layout


def seed(env, preset="zettelkasten"):
    app = env.app
    app.settings.set("notes.layout", preset)
    app.settings.set("research.about", "stochastic climate models")
    env.on("subjects")
    env.say("/subject add Real Analysis (ra)")
    lay = layout.of(app)
    course = lay.path("course", subject="real-analysis")
    course.parent.mkdir(parents=True, exist_ok=True)
    course.write_text("# Real Analysis\n\nMy own words here.\n", encoding="utf-8")
    return lay, course


def test_hubs_are_made_and_list_the_course_and_the_course_links_back(env):
    lay, course = seed(env)
    did = hubs.ensure(env.app)
    assert "research hub" in did and "home note" in did and "real-analysis course page" in did
    home = lay.path("home").read_text(encoding="utf-8")
    assert "[[maps/courses/real-analysis|Real Analysis]]" in home and "[[maps/research|Research]]" in home
    assert "What I work on: stochastic climate models" in lay.path("research").read_text(encoding="utf-8")
    back = course.read_text(encoding="utf-8")
    assert back.startswith("# Real Analysis\n\nMy own words here.") and "[[maps/index|Home]]" in back


def test_running_again_changes_nothing(env):
    lay, course = seed(env)
    hubs.ensure(env.app)
    before = {p: p.read_text(encoding="utf-8") for p in (lay.path("home"), lay.path("research"), course)}
    assert hubs.ensure(env.app) == []
    assert before == {p: p.read_text(encoding="utf-8") for p in before}


def test_your_own_hub_text_is_kept(env):
    lay, course = seed(env)
    research = lay.path("research")
    research.parent.mkdir(parents=True, exist_ok=True)
    research.write_text("# My research\n\nMine.\n", encoding="utf-8")
    hubs.ensure(env.app)
    assert research.read_text(encoding="utf-8") == "# My research\n\nMine.\n"


def test_the_plain_layout_has_its_own_paths(env):
    lay, course = seed(env, "kurooto")
    hubs.ensure(env.app)
    assert lay.path("home").name == "index.md" and lay.path("home").parent == lay.root
    assert "[[" in lay.path("home").read_text(encoding="utf-8")
