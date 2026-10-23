"""GBrain used more: the weekly one-line checkup (its doctor, read only), course pages with key concepts and a dated
timeline in Kurooto's own block, and the notes brain on calls. Every test uses a fake gbrain."""

import datetime as dt
import json

import pytest

from kurooto.core import proc
from kurooto.core.clock import now
from kurooto.modules import coursepages


class Fake:
    def __init__(self, answers):
        self.answers, self.calls = answers, []

    def __call__(self, args, **kw):
        self.calls.append(args[1:])
        code, out = self.answers.get(args[1], (0, ""))
        return proc.Result(code, out, "")


@pytest.fixture
def g(env, monkeypatch):
    g = env.app.modules["gbrain"]
    monkeypatch.setattr(g.prereqs.items["gbrain"], "find", lambda: "/x/gbrain")
    (env.app.paths.state / "gbrain.json").write_text(json.dumps({"initialised": True, "embeddings": "off"}))
    env.app.settings.set("notify.desktop", False)
    return g


def texts(env):
    return [p["text"] for m, p in env.fake.sent if m == "sendMessage"]


DOCTOR = {
    "schema_version": 2,
    "status": "warnings",
    "health_score": 80,
    "brain_checks_score": 90,
    "checks": [
        {"name": "connection", "status": "ok", "message": "ok"},
        {"name": "embeddings_stale", "status": "warn", "message": "212 chunks have stale embeddings"},
        {"name": "mcp_wiring", "status": "warn", "message": "no MCP client"},  # ignored: checkup_ignore
    ],
    "top_issues": [{"name": "embeddings_stale", "status": "warn", "tier": "root", "fix": "run gbrain embed --stale"}],
}


def test_the_weekly_line(env, g, monkeypatch):
    fake = Fake({"doctor": (1, "checking...\n" + json.dumps(DOCTOR))})
    monkeypatch.setattr("kurooto.modules.gbrain.proc.run", fake)
    n = len(texts(env))
    line = g.weekly()
    assert line == "Notes brain checkup (score 90/100): 1 thing to look at; first: run gbrain embed --stale"
    assert fake.calls == [["doctor", "--json", "--no-migrate", "--scope=brain"]]  # read only, never migrating
    assert texts(env)[n:] == [line]
    rec = env.app.calm.reason("gbrain.checkup_line")
    assert rec.setting == "gbrain.checkup_line"
    healthy = {**DOCTOR, "checks": DOCTOR["checks"][:1], "top_issues": []}
    monkeypatch.setattr("kurooto.modules.gbrain.proc.run", Fake({"doctor": (0, json.dumps(healthy))}))
    assert g.weekly() == "Notes brain checkup: all well (score 90/100), 1 checks passed."
    env.app.settings.set("gbrain.checkup_line", False)
    n = len(texts(env))
    assert g.weekly() == "" and len(texts(env)) == n  # its off switch


def test_the_line_rides_with_the_advisors_findings(env, g, monkeypatch):
    advisor = {"findings": [{"id": "low_embed_coverage", "severity": "warn", "title": "Embeddings cover 40%"}]}
    fake = Fake({"doctor": (0, json.dumps(DOCTOR)), "advisor": (1, json.dumps(advisor))})
    monkeypatch.setattr("kurooto.modules.gbrain.proc.run", fake)
    env.app.settings.set("gbrain.checkup", True)
    n = len(texts(env))
    g.weekly()
    told = texts(env)[n:]
    assert len(told) == 1 and told[0].startswith("Notes brain checkup (score 90/100)")
    assert "Notes brain checkup: 1 thing(s) need a look." in told[0]


def test_doctor_only_without_migrating_and_on_your_own_brain(env, g, monkeypatch):
    fake = Fake({})
    monkeypatch.setattr("kurooto.modules.gbrain.proc.run", fake)
    r = g.run("doctor", "--json")
    assert not r.ok and "--no-migrate" in r.err and fake.calls == []
    env.app.settings.set("gbrain.managed", False)
    monkeypatch.setattr(g, "exe", lambda: "/x/gbrain")
    assert g.run("doctor", "--json", "--no-migrate").ok
    assert g.run("find-contradictions", "--json").ok
    assert not g.run("eval", "suspected-contradictions").ok  # the probe (an AI model) is never run by Kurooto


@pytest.fixture
def course(env):
    app = env.app
    s = app.settings
    s.set("subjects.list", [{"slug": "stats", "name": "Statistics", "aliases": ["st"]}])
    s.set("subjects.timetable", [{"day": "wed", "start": "11:00", "end": "11:55", "subject": "stats"},
                                 {"day": "mon", "start": "09:00", "end": "09:55", "subject": "stats"}])  # fmt: skip
    env.on("subjects", "deadlines")
    root = app.workspace / "stats"
    root.mkdir(parents=True, exist_ok=True)
    day = (now().date() - dt.timedelta(days=5)).isoformat()
    (root / f"{day}-priors.md").write_text("# Lecture 4: priors\n\nUses [[stats/bayes-theorem]] and [[stats/beta]].\n")
    (root / "bayes-theorem.md").write_text("# Bayes' theorem\n\nP(A|B) = P(B|A)P(A)/P(B).\n")
    (root / "beta.md").write_text("# Beta distribution\n\nA prior on [0, 1]; see [[stats/bayes-theorem]].\n")
    due = dt.datetime.combine(now().date() + dt.timedelta(days=4), dt.time(17, 0))
    app.modules["deadlines"].add("Problem set 3", due, subject="stats")
    return env, root, day, due


def test_course_pages_get_key_concepts_and_a_timeline(course):
    env, root, day, due = course
    app = env.app
    assert coursepages.write_all(app) == 1
    page = (root / "course.md").read_text()
    assert page.startswith("---") and "# Statistics" in page
    assert "<!-- kurooto:course-overview -->" in page and "Classes: Mon 09:00-09:55, Wed 11:00-11:55." in page
    assert page.index("[[stats/bayes-theorem|Bayes' theorem]]") < page.index("[[stats/beta|Beta distribution]]")
    assert f"- **{day}** | lecture — [[stats/{day}-priors|Lecture 4: priors]]" in page
    assert f"- **{due.date().isoformat()}** | deadline — Problem set 3 at 17:00" in page
    assert coursepages.write_all(app) == 0  # nothing new: the page stays as it is
    mine = page.replace("# Statistics\n", "# Statistics\n\nMy own words about the course.\n")
    (root / "course.md").write_text(mine)
    (root / f"{day}-priors.md").rename(root / f"{day}-priors-and-posteriors.md")
    assert coursepages.write_all(app) == 1
    page = (root / "course.md").read_text()
    assert "My own words about the course." in page and "priors-and-posteriors" in page


def test_the_nightly_writes_them_and_the_switch(course, g, monkeypatch):
    env, root, day, due = course
    monkeypatch.setattr("kurooto.modules.gbrain.proc.run", Fake({"extract": (0, "Timeline: 2 entries\n")}))
    out = g.nightly()
    assert out["course_pages"] == 1 and (root / "course.md").exists()
    (root / "course.md").unlink()
    env.app.settings.set("gbrain.course_pages", False)
    assert "course_pages" not in g.nightly() and not (root / "course.md").exists()


def test_the_notes_brain_on_calls(env, g, monkeypatch):
    app = env.app
    app.secrets.set("gemini.api_key", "k")
    app.settings.set("calls.worker", {"url": "https://kurooto-abc.your-subdomain.workers.dev"})
    from kurooto.modules.calls import deploy

    deploy.ensure_secrets(app)
    env.on("calls")
    c = app.modules["calls"]
    prompt = c.config_template()["systemInstruction"]
    assert "notes brain" not in prompt and "note_timeline" not in {t.name for t in c.tools()}
    env.on("gbrain")
    tools = {t.name: t for t in c.tools()}
    assert "note_timeline" in tools and "by meaning" in tools["search_notes"].description
    assert "Their notes brain is on: search_notes finds by meaning" in c.config_template()["systemInstruction"]
    monkeypatch.setattr(g, "search", lambda q, n=5: f"stats/course: the quiz is on Friday ({q})")
    assert "the quiz is on Friday" in tools["search_notes"].run({"query": "when is the stats quiz"})
