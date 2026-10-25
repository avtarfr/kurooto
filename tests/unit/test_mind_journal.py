"""Brain, stage 07: a true journal (I-10): code decides what must be in it and checks every line against the log."""

import datetime as dt
import json
import random

import pytest

from kurooto import mind
from kurooto.core.clock import now
from kurooto.mind import journal
from kurooto.mind import log as mlog
from kurooto.mind import scorekeeper as sk
from kurooto.mind.journal import Fact


def fixture_days(n=30, seed=7):
    """Thirty days of facts (a seeded stand-in for recorded days): every kind the manifest requires, with varied
    numbers."""
    rnd = random.Random(seed)  # noqa: S311 (a fixed seed for a test)
    days = []
    for d in range(n):
        fs = []
        seq = 1
        for _ in range(rnd.randint(3, 8)):
            kind = rnd.choice(
                ["promise_broken", "undo", "failure", "wrong_read", "swing", "feeling", "act", "proposal"]
            )
            t = 1_800_000_000.0 + d * 86400 + rnd.randint(0, 80000)
            if kind == "promise_broken":
                f = Fact(kind, [seq], t, {"due": rnd.randint(0, 1439)}, cause=rnd.choice(["", "stop"]))
            elif kind == "undo":
                f = Fact(kind, [seq], t, words={"what": rnd.choice(["deadline", "retro_fix", "calm"])})
            elif kind == "failure":
                f = Fact(kind, [seq], t, words={"what": rnd.choice(["job_failed", "module_failed", "kurooto_crashed"])})
            elif kind == "wrong_read":
                f = Fact(kind, [seq], t, about_him=True)
            elif kind == "swing":
                f = Fact(
                    kind,
                    [seq],
                    t,
                    {"r": round(rnd.uniform(0.31, 1.0), 2), "time": rnd.randint(0, 1439)},
                    words={"dir": rnd.choice(["fell", "rose"])},
                )
            elif kind == "feeling":
                lab = rnd.choice(["uneasy", "satisfied", "relieved", "frustrated"])
                nums = {
                    "uneasy": {"valence": -0.5},
                    "satisfied": {"valence": 0.5},
                    "relieved": {"r": 0.8},
                    "frustrated": {"neg": 4},
                }[lab]
                f = Fact(kind, [seq], t, nums, words={"object": rnd.choice(["promise_slack", "health"])}, label=lab)
            elif kind == "act":
                f = Fact(
                    kind,
                    [seq],
                    t,
                    words={
                        "klass": rnd.choice(["R2", "R3"]),
                        "what": rnd.choice(["schedule.cross_day", "setting.own_nonsafety"]),
                    },
                )
            else:
                f = Fact(kind, [seq], t, words={"what": rnd.choice(["made", "applied", "discarded"])})
            fs.append(f)
            seq += 1
        days.append(fs)
    return days


def test_every_kind_has_a_sentence_that_passes():
    for fs in fixture_days():
        for f in fs:
            s = journal.words_for(f)
            assert journal.check(f, s, {1, 2, 3, 4, 5, 6, 7, 8, 9}) == "", (f.kind, s)


@pytest.mark.parametrize(
    ("rule", "fact", "sentence"),
    [
        (
            "number",
            Fact("swing", [1], 0, {"r": 0.45, "time": 600}, words={"dir": "fell"}),
            "My drive fell by 0.55 at 10:00.",
        ),
        (
            "invented",
            Fact("failure", [1], 0, words={"what": "job_failed"}),
            "Something of mine failed: job_failed. I also deleted your notes.",
        ),
        (
            "feeling",
            Fact("swing", [1], 0, {"r": 0.45, "time": 600}, words={"dir": "fell"}),
            "I was frustrated: my drive fell by 0.45 at 10:00.",
        ),
        (
            "feeling",
            Fact("feeling", [1], 0, {"valence": -0.1}, words={"object": "health"}, label="uneasy"),
            "I became uneasy about health.",
        ),  # not below its threshold
        (
            "cause",
            Fact("failure", [1], 0, words={"what": "job_failed"}),
            "Something of mine failed: job_failed because you were asleep.",
        ),
        (
            "cause",
            Fact("promise_broken", [1], 0, {"due": 1080}, cause="stop"),
            "I broke a promise: I said I'd do something at 18:00 because the network was down.",
        ),
        ("seq", Fact("failure", [99], 0, words={"what": "job_failed"}), "Something of mine failed: job_failed."),
    ],
)
def test_checker_rules(rule, fact, sentence):
    assert journal.check(fact, sentence, {1, 2, 3}) == rule


def test_a_true_cause_and_a_true_feeling_pass():
    f = Fact("promise_broken", [1], 0, {"due": 1080}, cause="stop")
    assert (
        journal.check(
            f, "I broke a promise: I said I'd do something at 18:00 and it didn't happen because the computer was off."
        )
        == ""
    )
    g = Fact("feeling", [1], 0, {"valence": -0.5}, words={"object": "promise_slack"}, label="uneasy")
    assert journal.check(g, "I became uneasy about promise slack.") == ""
    assert journal.check(g, "I became relieved about promise slack.") == "feeling"  # the wrong label for that fact


def test_journal_mutation_suite():
    """I-10: over thirty days the checker rejects 99% of corrupted lines and keeps 95% of true ones."""
    kept = rej = n_true = n_bad = 0
    for fs in fixture_days(30):
        r = journal.rates(fs, set(range(1, 20)))
        kept += r["kept"] * r["n_true"]
        n_true += r["n_true"]
        rej += r["rejected"] * r["n_bad"]
        n_bad += r["n_bad"]
    assert n_true > 100 and n_bad > 300
    assert kept / n_true >= journal.KEEP_MIN
    assert rej / n_bad >= journal.REJECT_MIN


def test_mutations_are_really_different():
    f = Fact("swing", [1], 0, {"r": 0.45, "time": 600}, words={"dir": "fell"})
    s = journal.words_for(f)
    kinds = {k for k, m in journal.mutations(f, s) if m != s}
    assert {"number", "cause", "feeling", "invented"} <= kinds


# ------------------------------------------------------------------------------------------------ with an app
@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind"])
    monkeypatch.setattr(mlog, "_writer_pid", None)
    a.keeper = sk.Keeper(a.paths.state / "mind")
    said = []
    monkeypatch.setattr(a, "notify", lambda text, **kw: said.append((text, kw)) or "m1")
    a.said = said
    monkeypatch.setattr(mind.connect(a), "report", lambda kind, body: a.keeper.append(kind, body).get("ok", False))
    yield a
    a.keeper.close()
    mind.forget_client(a)
    a.close()


def seed_day(app):
    """A day in the log: a broken promise, an undo, a crash, a wrong read, a big swing, a feeling, an R2 act, a
    proposal."""
    k = app.keeper
    k.append("promise_broken", {"id": "p1", "due_s": int(now().timestamp()) - 3600, "made_s": 0})
    k.append("deadline_undo", {"id": "d1"})
    k.append("kurooto_crashed", {"code": 1})
    k.append("read_answer", {"day": now().date().isoformat(), "right": False, "strength": 3.0})
    k.append(
        "budget_tick",
        {"x": {"promise_slack": 0.9, "health": 0.95}, "hour": 9, "at_computer": True},
        now().timestamp() - 600,
    )
    k.append(
        "budget_tick",
        {"x": {"promise_slack": -0.9, "health": 0.95}, "hour": 9, "at_computer": True},
        now().timestamp() - 300,
    )
    k.append("mind_feeling", {"label": "uneasy", "object": "promise_slack", "valence": -0.6, "r": 0.0, "neg": 0})
    k.append("mind_act", {"klass": "R2", "action": "schedule.cross_day"})
    k.append("mind_act", {"klass": "R1", "action": "job.queue"})  # R1: not required
    k.append("proposal_applied", {"id": "pr1"})


def test_manifest_coverage(app):
    """Every required fact kind produces a line; an R1 act doesn't."""
    seed_day(app)
    kinds = [f.kind for f in journal.manifest(app, now().date())]
    assert sorted(kinds) == sorted(
        ["promise_broken", "undo", "failure", "wrong_read", "swing", "feeling", "act", "proposal"]
    )
    out = journal.write_day(app, now().date(), use_model=False)
    entry = journal.read_day(app, now().date())
    assert out["lines"] == 8 and entry["facts"] == 8 and entry["rejected"] == 0
    text = (journal.folder(app) / f"{now().date().isoformat()}.md").read_text(encoding="utf-8")
    assert "I broke a promise" in text and "[#" in text  # each line cites its log records
    assert oct((journal.folder(app) / f"{now().date().isoformat()}.json").stat().st_mode & 0o777)[-3:] in ("600", "644")


def test_a_model_line_that_invents_is_replaced_by_the_fixed_one(app, monkeypatch):
    """Lines that fail are deleted, not rewritten: the fixed sentence takes the place (coverage)."""
    from kurooto.mind import tone

    seed_day(app)

    class LM:
        def __init__(self, said):
            self.said = said

        def have(self):
            return {"m"}

        def wanted(self):
            return [{"key": "helper", "tag": "m"}]

        def api(self, path, body=None, timeout=10):
            said = self.said

            class R:
                def __enter__(s):
                    return s

                def __exit__(s, *a):
                    return False

                def read(s):
                    return json.dumps({"response": said}).encode()

            return R()

    app.settings.set("modules.enabled", ["mind", "local_models"])
    monkeypatch.setitem(app.modules, "local_models", LM("I called you and you shouted."))
    assert tone.model(app) == "m"
    out = journal.write_day(app, now().date())
    entry = journal.read_day(app, now().date())
    assert out["lines"] == 8 and entry["rejected"] == 8  # every model line failed its checks; all fixed sentences stand
    assert all("shouted" not in ln["text"] for ln in entry["lines"])


def test_a_model_line_that_stays_true_is_used(app, monkeypatch):
    seed_day(app)
    app.settings.set("modules.enabled", ["mind", "local_models"])

    class LM:
        def have(self):
            return {"m"}

        def wanted(self):
            return [{"key": "helper", "tag": "m"}]

        def api(self, path, body=None, timeout=10):
            word = "yes" if "follow from the fact" in body["prompt"] else "My read of you was wrong that day."

            class R:
                def __enter__(s):
                    return s

                def __exit__(s, *a):
                    return False

                def read(s):
                    return json.dumps({"response": word}).encode()

            return R()

    monkeypatch.setitem(app.modules, "local_models", LM())
    f = next(x for x in journal.manifest(app, now().date()) if x.kind == "wrong_read")
    assert journal.wording(app, f) == ("My read of you was wrong that day.", False)


def test_journal_never_cloud(app, monkeypatch):
    """Writing a day touches no cloud brain and no request leaves the computer."""
    import urllib.request

    from kurooto.core import egress

    leaks = []
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *a, **k: leaks.append(a) or (_ for _ in ()).throw(OSError("no"))
    )
    monkeypatch.setattr(egress, "allow", lambda *a, **k: leaks.append(a) or "no")
    submitted = []
    monkeypatch.setattr(app.jobs, "submit", lambda *a, **k: submitted.append(a) or "j")
    seed_day(app)
    journal.write_day(app, now().date())
    journal.selfcheck(app)
    assert leaks == [] and submitted == []


def test_strike_and_forget(app, monkeypatch):
    seed_day(app)
    journal.write_day(app, now().date(), use_model=False)
    forgot = []
    from kurooto.mind import mood

    monkeypatch.setattr(mood, "forget_day", lambda a, day: forgot.append(day) or "ok")
    entry = journal.read_day(app, now().date())
    i = next(n for n, ln in enumerate(entry["lines"], 1) if ln["about_him"])
    assert journal.strike(app, now().date(), i) == f"Struck line {i}." and forgot == [now().date().isoformat()]
    j = next(n for n, ln in enumerate(entry["lines"], 1) if not ln["about_him"])
    journal.strike(app, now().date(), j)
    assert len(forgot) == 1  # only a line about you follows the forget cascade
    text = (journal.folder(app) / f"{now().date().isoformat()}.md").read_text(encoding="utf-8")
    assert "(struck)" in text and journal.strike(app, now().date(), 99) == "No such line."


def test_selfcheck_freezes_learning_when_the_checker_slips(app, monkeypatch):
    seed_day(app)
    r = journal.selfcheck(app)
    assert r["rejected"] >= journal.REJECT_MIN and r["kept"] >= journal.KEEP_MIN and not app.said
    assert not app.keeper.engine.frozen_learning()
    monkeypatch.setattr(journal, "check", lambda *a, **k: "")  # a checker that lets everything through
    journal.selfcheck(app)
    assert app.keeper.engine.frozen_learning() and app.said and app.said[-1][1]["why"] == "mind.journal_check"


def test_journal_off_or_brain_off(app):
    app.settings.set("mind.journal.on", False)
    assert journal.write_day(app) is None and journal.selfcheck(app) is None


def test_the_journal_text_is_in_state_not_in_the_scorekeepers_folder(app):
    seed_day(app)
    journal.write_day(app, now().date(), use_model=False)
    assert (app.paths.state / "mind-journal").is_dir() and not (app.paths.state / "mind" / "journal").exists()
    assert dt.date.today().isoformat() in json.loads((journal.folder(app) / "index.json").read_text())
