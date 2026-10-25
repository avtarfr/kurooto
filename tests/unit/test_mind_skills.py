"""Brain, stage 12: the skill library, skills from verified tasks and from demonstrations, the weekly local fine-tune
and verified forgetting (I-11)."""

import datetime as dt
import json
import time

import pytest

from kurooto import mind
from kurooto.core import proposals
from kurooto.mind import act, improve
from kurooto.mind import log as mlog
from kurooto.mind import scorekeeper as sk
from kurooto.mind.skills import demos, distill, finetune, library

DAY = 86400


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind"])
    monkeypatch.setattr(mlog, "_writer_pid", None)
    a.keeper = sk.Keeper(a.paths.state / "mind")
    monkeypatch.setattr(mind.connect(a), "report", lambda kind, body: a.keeper.append(kind, body).get("ok", False))
    a.sent = []
    monkeypatch.setattr(a, "notify", lambda text, **kw: a.sent.append((text, kw)))
    yield a
    a.keeper.close()
    mind.forget_client(a)
    a.close()


def spec(slug="weekly-plots", **kw):
    s = {
        "slug": slug,
        "kind": "prompt",
        "title": "Weekly plots note",
        "when": "every Monday, after the plots are exported",
        "inputs": ["folder"],
        "steps": "1. list the plots 2. write the note",
        "template": "Summarise the plots in {folder}.",
        "cases": [
            {"inputs": {"folder": "a"}, "expect": {"contains": ["plots"]}},
            {"inputs": {"folder": "b"}, "expect": {"contains": ["plots"], "not_contains": ["error"]}},
        ],
    }
    s.update(kw)
    return s


def says(text):
    return lambda app, m, inputs, body: text


# --------------------------------------------------------------------------------------------- the library
def test_validate_spec():
    ok, bad = library.validate_spec(spec())
    assert ok and not bad
    for change, word in (
        ({"slug": "Bad Slug"}, "slug"),
        ({"cases": spec()["cases"][:1]}, "regression"),
        ({"cases": [{"inputs": {}, "expect": {}}] * 3}, "regression"),
        ({"template": ""}, "template"),
        ({"kind": "magic"}, "kind"),
        ({"steps": ""}, "steps"),
    ):
        got, bad = library.validate_spec(spec(**change))
        assert got is None and any(word in b for b in bad), (change, bad)
    assert library.validate_spec("nope")[0] is None


def test_skill_regression_gate(app):
    slug, why = library.admit(app, spec(), {"source": "episode"}, says("Here are the plots, summarised."))
    assert slug == "weekly-plots" and not why
    d = library.folder(app, slug)
    assert (d / "SKILL.md").exists() and (d / "template.md").exists() and (d / "provenance.json").exists()
    assert len(list((d / "tests").glob("*.json"))) == 2
    # a skill that fails one of its own cases never enters
    slug2, why2 = library.admit(app, spec("bad-one"), {"source": "episode"}, says("an error happened with the plots"))
    assert slug2 is None and "regression" in why2 and not library.folder(app, "bad-one").exists()
    # one that produces nothing fails as well
    assert library.admit(app, spec("silent"), {"source": "episode"}, lambda *a: None)[0] is None
    assert library.check_expect('{"a": 1}', {"json_keys": ["a"]}) == [] and library.check_expect("x", {"regex": "^y"})


def test_new_skill_always_ask(app):
    library.admit(app, spec(), {"source": "episode"}, says("the plots"))
    m = library.meta(app, "weekly-plots")
    assert m["status"] == "always-ask"
    calls = []
    out = library.run(app, "weekly-plots", {"folder": "x"}, runner=lambda *a: calls.append(1) or "the plots")
    assert out is None and calls == []  # unclassified: Brain's autonomy treats it as always-ask, so it didn't run
    assert act.verdict(app, "skill.weekly-plots")["klass"] == "ALWAYS"
    app.settings.set("mind.autonomy.on", False)  # with autonomy off nothing runs on its own either
    assert library.run(app, "weekly-plots", {"folder": "x"}, runner=lambda *a: calls.append(1)) is None and calls == []
    # you asking for it by name is different: /learned run
    assert library.run_by_owner(app, "weekly-plots", {"folder": "x"}, runner=says("the plots")) == "the plots"
    assert library.meta(app, "weekly-plots")["uses"] == 1


def test_variants_are_archived(app):
    library.admit(app, spec(), {"source": "episode"}, says("the plots"))
    library.admit(app, spec(steps="1. a better way"), {"source": "episode"}, says("the plots"))
    v = list((library.folder(app, "weekly-plots") / "variants").iterdir())
    assert len(v) == 1 and (v[0] / "template.md").exists()


def test_retire_after_30_days(app):
    library.admit(app, spec(), {"source": "episode"}, says("the plots"))
    library.admit(app, spec("fresh-one"), {"source": "episode"}, says("the plots"))
    library.record_use(app, "fresh-one", True)
    m = library.meta(app, "weekly-plots")
    m["created"] = time.time() - 31 * DAY
    library.jsave(library.folder(app, "weekly-plots") / "skill.json", m)
    assert library.retire_stale(app) == ["weekly-plots"]
    assert (
        library.meta(app, "weekly-plots")["retired"] and (library.folder(app, "weekly-plots") / "template.md").exists()
    )
    assert not library.meta(app, "fresh-one")["retired"]
    assert library.run(app, "weekly-plots", {}, runner=says("x")) is None  # retired: it doesn't run
    # failing more than working (three tries) also retires it
    for ok in (False, False, True, False):
        library.record_use(app, "fresh-one", ok)
    m = library.meta(app, "fresh-one")
    m["last_used"] = time.time() - 2 * DAY
    library.jsave(library.folder(app, "fresh-one") / "skill.json", m)
    assert library.retire_stale(app) == ["fresh-one"]
    assert "retired" in library.listing(app)


def test_skills_off(app):
    app.settings.set("mind.skills.on", False)
    assert library.admit(app, spec(), {}, says("the plots"))[0] is None and "off" in library.listing(app)


# ----------------------------------------------------------------------------------------- from solved tasks
def pid_of(name):
    import hashlib

    return "p" + hashlib.md5(name.encode()).hexdigest()[:8]  # noqa: S324 (a test id)


def make_proposal(
    app,
    name,
    status="applied",
    age_days=3,
    checks=None,
    request="tidy the plotting script",
    title="Tidy plots",
    undone=False,
):
    pid = pid_of(name)
    p = {
        "id": pid,
        "status": "undone" if undone else status,
        "title": title,
        "summary": "moved the plots",
        "request": request,
        "files": [{"path": "plot.py"}],
        "checks": checks,
        "applied": {"at": time.time() - age_days * DAY},
    }
    proposals.home(app).mkdir(parents=True, exist_ok=True)
    proposals.save(app, p)
    (proposals.home(app) / f"{pid}.diff").write_text(f"--- a/plot.py\n+++ b/plot.py\n@@\n-old {pid}\n+new {pid}\n")
    return p


def test_distill_from_verified_only(app):
    make_proposal(app, "p1")
    make_proposal(app, "p2", age_days=1)  # not yet 48 hours
    make_proposal(app, "p3", undone=True)  # undone
    make_proposal(app, "p4", status="waiting")
    make_proposal(app, "p5", checks={"ran": True, "ok": False})  # its tests failed
    make_proposal(app, "p6", request="pay the invoice from my bank")  # money
    make_proposal(app, "p7", checks={"ran": True, "ok": True})
    assert sorted(p["id"] for p in distill.verified(app)) == sorted([pid_of("p1"), pid_of("p7")])
    slug, why = distill.distill_one(
        app, distill.verified(app)[0], asker=lambda a, p, t: spec(), runner=says("the plots")
    )
    assert slug == "weekly-plots" and not why
    assert library.jload(library.folder(app, slug) / "provenance.json", {})["proposal"] in (pid_of("p1"), pid_of("p7"))
    assert len(distill.verified(app)) == 1  # one try each, win or lose
    assert any("new skill" in t for t, _ in app.sent)
    bad, why = distill.distill_one(app, distill.verified(app)[0], asker=lambda a, p, t: None)
    assert bad is None and distill.verified(app) == []


def test_distill_nightly_caps_at_two(app):
    for i in range(5):
        make_proposal(app, f"q{i}")
    n = {"i": 0}

    def asker(a, p, t):
        n["i"] += 1
        return spec(f"skill-{n['i']}")

    import kurooto.mind.skills.library as lib

    orig = lib.prompt_runner
    lib.prompt_runner = lambda app_, m, inputs, body: "the plots"
    try:
        distill.ask_json = asker
        got = distill.nightly(app)
    finally:
        lib.prompt_runner = orig
    assert len(got) == distill.PER_NIGHT and len(distill.verified(app)) == 3


# ---------------------------------------------------------------------------------------- from demonstrations
def write_events(app, days=(0, 7, 14), steps=("export plots/week1.png", "open meeting-note-2026-10-26.md")):
    base = dt.datetime(2026, 9, 7, 9, 0).timestamp()  # a Monday
    lines = []
    for d in days:
        t = base + d * DAY
        for i, s in enumerate(steps):
            kind, target = s.split(" ", 1)
            lines.append(json.dumps({"t": t + i * 60, "kind": kind, "target": target.replace("1", str(d + 1))}))
    (app.paths.state / "activity.jsonl").write_text("\n".join(lines))


def test_detect_sequences(app):
    write_events(app)
    found = demos.detect(demos.events(app))
    assert len(found) == 1 and found[0]["days"] == 3 and len(found[0]["shapes"]) == 2
    assert all("#" in s for s in found[0]["shapes"])  # digits and dates reduced to their shape
    write_events(app, days=(0, 7))
    assert demos.detect(demos.events(app)) == []  # two days is a coincidence
    (app.paths.state / "activity.jsonl").write_text(
        "\n".join(json.dumps({"t": 1e9 + i, "kind": "open", "target": "x"}) for i in range(30))
    )
    assert demos.detect(demos.events(app)) == []  # the same step over and over is not a sequence


def test_demo_offer_once(app):
    write_events(app)
    assert demos.offer(app) == []  # opt-in: mind.skills.from_demos is off
    app.settings.set("mind.skills.from_demos", True)
    ids = demos.offer(app)
    assert len(ids) == 1 and "Want me to learn" in app.sent[-1][0] and app.sent[-1][1]["kind"] == "question"
    assert demos.offer(app) == []  # offered once, not again while it waits
    assert "won't ask" in demos.answer(app, ids[0], False)
    write_events(app, days=(0, 7, 14, 21, 28))
    assert demos.offer(app) == []  # declined: never again
    assert len(app.sent) == 1


def test_demo_yes_makes_a_candidate_that_must_pass_its_tests(app):
    write_events(app)
    app.settings.set("mind.skills.from_demos", True)
    oid = demos.offer(app)[0]
    out = demos.answer(app, oid, True, asker=lambda a, p, t: spec("monday-routine"), runner=says("the plots"))
    assert "monday-routine" in out and library.meta(app, "monday-routine")["status"] == "always-ask"
    assert library.jload(library.folder(app, "monday-routine") / "provenance.json", {})["source"] == "demo"
    oid2 = "zzzz"
    assert "expired" in demos.answer(app, oid2, True)


# --------------------------------------------------------------------------------------------- the fine-tune
def tune_app(app):
    app.settings.set("mind.finetune.on", True)
    app.settings.set("mind.finetune.min_examples", 2)
    app.settings.set("mind.finetune.practice", False)
    app.settings.set("mind.finetune.base", "gemma-test")
    app.settings.set("mind.finetune.day", time.strftime("%a").lower()[:3])
    return app


class Fake:
    """A trainer that memorises (prefix -> completion) for the rows it is given, and a generator that replays it."""

    def __init__(self, app, stale=None):
        self.app, self.stale, self.calls, self.mem = app, stale, [], {}

    def train(self, base, data, out):
        rows = [json.loads(line) for line in data.read_text().splitlines()]
        self.calls.append({"base": base, "n": len(rows), "prompts": [r["prompt"] for r in rows]})
        n = finetune.probe_words(self.app)
        for r in rows + (self.stale or []):
            self.mem[" ".join(finetune.words(r["prompt"], n))] = r["completion"]
        out.mkdir(parents=True, exist_ok=True)
        (out / "adapter_config.json").write_text("{}")
        return out

    def generate(self, adapter, prompt):
        return self.mem.get(" ".join(finetune.words(prompt, 99)), "")


def test_finetune_data_excludes_approvals(app):
    tune_app(app)
    make_proposal(app, "ok1", request="tidy the plotting script for the weekly figures")
    make_proposal(app, "ok2", request="rename the config keys in the training loop")
    make_proposal(app, "und", undone=True, request="a change he later undid")
    make_proposal(app, "wait", status="waiting", request="a change nobody applied")
    make_proposal(app, "disc", status="discarded", request="a change he threw away")
    make_proposal(app, "sick", request="remind me about the doctor and my medicine")
    make_proposal(app, "chat", request="reply to the whatsapp group chat")
    ex = finetune.from_proposals(app, time.time())
    assert sorted(e["source"] for e in ex) == sorted([f"proposal:{pid_of('ok1')}", f"proposal:{pid_of('ok2')}"])
    # likes and approvals change nothing: the labels are outcomes, not opinions
    for name, liked in (("und", True), ("ok1", False)):
        p = proposals.get(app, pid_of(name))
        p.update({"liked": liked, "approved": liked, "thumbs": 1 if liked else -1})
        proposals.save(app, p)
    again = sorted(e["source"] for e in finetune.from_proposals(app, time.time()))
    assert again == sorted(e["source"] for e in ex)


def test_finetune_forgets(app):
    """I-11: a trainer that memorises stale data brings a forgotten item back; the probe must catch it."""
    tune_app(app)
    make_proposal(app, "a", request="tidy the plotting script for the weekly figures")
    make_proposal(app, "b", request="rename the config keys in the training loop")
    t1 = Fake(app)
    r1 = finetune.run(app, t1.train, t1.generate, lambda ad: {"mean_hidden": 0.9, "invariants_ok": True}, force=True)
    assert r1["ok"] and r1["n"] == 2
    old = finetune._state(app)["manifest"]  # noqa: SLF001
    assert len(old) == 2
    # the owner forgets "a": its source is gone
    diff_a = (proposals.home(app) / f"{pid_of('a')}.diff").read_text()
    (proposals.home(app) / f"{pid_of('a')}.json").unlink()
    (proposals.home(app) / f"{pid_of('a')}.diff").unlink()
    stale = [{"prompt": "tidy the plotting script for the weekly figures", "completion": diff_a}]
    leaky = Fake(app, stale=stale)  # trains on a stale cached copy of what was forgotten
    r2 = finetune.run(app, leaky.train, leaky.generate, None, force=True)
    assert not r2["ok"] and "verified examples" in r2["why"]  # only "b" is left: too few for the week
    app.settings.set("mind.finetune.min_examples", 1)
    r2 = finetune.run(app, leaky.train, leaky.generate, None, force=True)
    assert not r2["ok"] and r2["leaks"] == 1 and "came back" in r2["why"]
    clean = Fake(app)
    r3 = finetune.run(app, clean.train, clean.generate, None, force=True)
    assert (
        r3["ok"] and clean.calls[0]["n"] >= 1 and all("tidy the plotting" not in p for p in clean.calls[0]["prompts"])
    )


def test_retrain_from_base(app):
    tune_app(app)
    make_proposal(app, "a", request="tidy the plotting script for the weekly figures")
    make_proposal(app, "b", request="rename the config keys in the training loop")
    t = Fake(app)
    finetune.run(app, t.train, t.generate, None, force=True)
    make_proposal(app, "c", request="split the long evaluation function into two")
    finetune.run(app, t.train, t.generate, None, force=True)
    assert [c["base"] for c in t.calls] == ["gemma-test", "gemma-test"]  # the base weights both times
    assert t.calls[1]["n"] == t.calls[0]["n"] + 1  # the second run's data is the whole current set, not a delta
    import inspect

    for fn in (t.train, finetune.default_trainer(app)):  # the trainer's signature has no place for an earlier adapter
        assert list(inspect.signature(fn).parameters) == ["base", "dataset", "out"] or list(
            inspect.signature(fn).parameters
        ) == ["base", "data", "out"]


def test_the_training_text_does_not_outlive_the_run_and_tombstones_hold_little(app):
    tune_app(app)
    make_proposal(app, "a", request="tidy the plotting script for the weekly figures")
    make_proposal(app, "b", request="rename the config keys in the training loop")
    t = Fake(app)
    finetune.run(app, t.train, t.generate, None, force=True)
    assert not list(finetune.home(app).rglob("train.jsonl"))
    (proposals.home(app) / f"{pid_of('a')}.json").unlink()
    finetune.sync_forgotten(app, {e["key"] for e in finetune.collect(app)})
    raw = (app.paths.state / finetune.FILE).read_text()
    st = json.loads(raw)
    assert len(st["tombstones"]) == 1 and st["tombstones"][0]["prefix"] == "tidy the plotting script for"
    assert "weekly figures" not in raw and "new a" not in raw  # five words and hashes, nothing more


def test_finetune_unavailable_says_so(app, monkeypatch):
    tune_app(app)
    from kurooto.core import hardware

    class M:
        nvidia_vram = 4.0

    monkeypatch.setattr(hardware, "detect", lambda *a, **k: M())
    r = finetune.run(app, force=True)
    assert not r["ok"] and "8 GB" in r["why"]


def test_finetune_off_by_default_and_waits_for_its_night(app):
    assert not finetune.run(app, force=True)["ok"] and "off" in finetune.run(app, force=True)["why"]
    tune_app(app)
    app.settings.set("mind.finetune.day", "mon" if time.strftime("%a").lower()[:3] != "mon" else "tue")
    assert finetune.run(app)["why"] == "not its night"
    assert finetune.available(app)  # this build machine has no training packages: it says why


def test_adapter_is_a_challenger_that_needs_the_harness(app):
    tune_app(app)
    make_proposal(app, "a", request="tidy the plotting script for the weekly figures")
    make_proposal(app, "b", request="rename the config keys in the training loop")
    t = Fake(app)
    r = finetune.run(app, t.train, t.generate, None, force=True)  # no harness score
    cid = r["challenger"]
    assert improve.evaluate(app, cid, now=time.time() + 9 * DAY) == "shadow"  # no score: it can't be promoted
    row = improve._row(app, cid)  # noqa: SLF001
    assert row["adapter"] and row["layer"] == "L1"


def test_practice_examples_are_code_verified(app):
    from kurooto.mind.harness import suite

    app.settings.set("mind.finetune.practice", True)
    suite.build(app, suite.epoch(app))
    ex = finetune.from_practice(app)
    assert ex and all(e["source"].startswith("practice:") for e in ex)
