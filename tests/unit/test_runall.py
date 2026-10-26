"""/run all and `kurooto run all` (0.8.8): every nightly process that's on, in order, one at a time, with a progress
line and a summary; skips what's off, never runs twice at once, stops when told. Fake steps stand in for the heavy
ones."""

import threading
import time

import pytest

from kurooto.core import runall


@pytest.fixture(autouse=True)
def quick(monkeypatch):
    monkeypatch.setattr(runall, "POLL", 0.01)


def finish(app, timeout=10.0):
    run = getattr(app, "_runall", None)
    assert run is not None
    run.thread.join(timeout)
    assert run.finished
    return run


class Msg:
    def __init__(self, via="terminal"):
        self.via, self.out = via, []

    def reply(self, text, buttons=None):
        self.out.append((text, buttons))
        return None


# ---------------------------------------------------------------------------------------------------- the line
def test_the_progress_line():
    assert runall.line(3, 5, "Concept graph", 4, 10, "batches", 125) == (
        "[3/5] Concept graph |########------------| 40% 4/10 batches, 2:05 elapsed, ETA 3:08"
    )
    assert runall.line(1, 5, "Books", 0, 100, "pages", 3).endswith("0% 0/100 pages, 0:03 elapsed, ETA ?")
    assert runall.line(5, 5, "Garden", 3, 3, "notes", 4000).endswith("100% 3/3 notes, 1:06:40 elapsed, ETA 0:00")
    assert (
        runall.line(2, 5, "Inbox", 0, None, "pass", 1)
        == "[2/5] Inbox |--------------------| 0 pass, 0:01 elapsed, ETA ?"
    )


# ---------------------------------------------------------------------------------------------------- order
def test_steps_run_in_order_each_after_the_last_and_the_summary_says_each(env):
    seen, lines = [], []

    def step(key):
        def fn(run):
            assert seen == [s for s in "abc"[: "abc".index(key)]]  # the ones before have finished
            for k in range(3):
                run.progress(k + 1, 3)
                lines.append(run.line())
            seen.append(key)
            return f"{key} done"

        return fn

    steps = tuple(runall.Step(k, k.upper(), "things", step(k)) for k in "abc")
    runall.start(env.app, steps=steps)
    run = finish(env.app)
    assert seen == ["a", "b", "c"]
    assert lines[0].startswith("[1/3] A |#######-------------| 33% 1/3 things")
    assert lines[-1].startswith("[3/3] C |####################| 100% 3/3 things")
    s = run.summary()
    assert s.startswith("Run all finished in ") and "- A: a done (" in s and "- C: c done (" in s


def test_features_that_are_off_are_skipped(env):
    env.app.settings.set("modules.enabled", [])
    runall.start(env.app)
    run = finish(env.app)
    assert [n for n, _ in run.results] == ["Books", "Inbox", "Concept graph", "Look-alike notes", "Garden"]
    assert all(w.startswith("skipped (") and "is off" in w for _, w in run.results), run.results


def test_a_failing_step_doesnt_stop_the_next(env):
    def boom(run):
        raise RuntimeError("disk full")

    steps = (runall.Step("a", "A", "x", boom), runall.Step("b", "B", "x", lambda run: "fine"))
    runall.start(env.app, steps=steps)
    run = finish(env.app)
    assert run.results[0][1].startswith("failed: RuntimeError: disk full") and run.results[1][1].startswith("fine")


# ---------------------------------------------------------------------------------------------------- lock, stop
def test_never_twice_at_once_and_stop(env, monkeypatch):
    gate = threading.Event()

    def slow(run):
        run.progress(1, 4)
        gate.set()
        while not run.wait(0.01):
            pass
        return "stopped there"

    def after(run):
        raise AssertionError("a step after a stop must not start")

    steps = (runall.Step("a", "Slow", "x", slow), runall.Step("b", "After", "x", after))
    monkeypatch.setattr(runall, "STEPS", steps)
    msg = Msg()
    assert runall.command(env.app, msg, "all").startswith("Running everything that's on, in order: Slow, After.")
    assert gate.wait(5)
    assert runall.start(env.app, steps=steps) is None  # the lock
    again = runall.command(env.app, Msg(), "all")
    assert again.startswith("Already running:") and "[1/2] Slow |#####" in again
    status = runall.command(env.app, Msg(), "all status")
    assert status.startswith("Running:\n[1/2] Slow") and "ETA" in status
    assert runall.command(env.app, Msg(), "all stop").startswith("Stopping: [1/2] Slow")
    run = finish(env.app)
    assert run.results == [("Slow", run.results[0][1]), ("After", "not started (stopped)")]
    assert run.summary().startswith("Run all stopped")
    assert runall.command(env.app, Msg(), "all status").startswith("Nothing running. Last run: Run all stopped")
    assert runall.command(env.app, Msg(), "all stop") == "Nothing running."


def test_the_switch_and_usage(env):
    assert runall.command(env.app, Msg(), "").startswith("Usage: /run all")
    env.app.settings.set("runall.on", False)
    assert runall.command(env.app, Msg(), "all") == "Run all is off (runall.on)."


def test_on_telegram_a_step_line_and_the_summary(env, monkeypatch):
    steps = (runall.Step("a", "A", "x", lambda run: "one"), runall.Step("b", "B", "x", lambda run: "two"))
    monkeypatch.setattr(runall, "STEPS", steps)
    env.say("/run all")
    finish(env.app)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not any("Run all finished" in t for t in env.fake.texts()):
        time.sleep(0.02)
    texts = env.fake.texts()
    assert any(t.startswith("Running everything that's on, in order: A, B.") for t in texts)
    assert any(t.startswith("Run all finished") and "- A: one" in t and "- B: two" in t for t in texts)


# ---------------------------------------------------------------------------------------------------- the CLI
def test_kurooto_run_all_follows_it_to_the_summary(monkeypatch, capsys):
    from kurooto import cli

    answers = iter(
        [
            ["Running everything that's on, in order: Books, Inbox."],
            ["Running:\n[1/2] Books |----------| 0% 0/3 pages, 0:00 elapsed, ETA ?"],
            ["Running:\nBooks: 3 pages read (0:02)\n[2/2] Inbox |----| 0% 0/1 pass, 0:00 elapsed, ETA ?"],
            ["Nothing running. Last run: Run all finished in 0:03:\n- Books: 3 pages read\n- Inbox: 2 filed"],
        ]
    )
    asked = []
    monkeypatch.setattr(cli, "say", lambda text: asked.append(text) or {"ok": True, "replies": next(answers)})
    assert cli.run_all(["all"], poll=0) == 0
    out = capsys.readouterr().out
    assert asked[0] == "/run all" and set(asked[1:]) == {"/run all status"}
    assert "[1/2] Books" in out and "[2/2] Inbox" in out and out.rstrip().endswith("- Inbox: 2 filed")
    assert cli.run_all(["books"]) == 2
    monkeypatch.setattr(cli, "say", lambda text: {"ok": True, "replies": ["Nothing running."]})
    assert cli.run_all(["all", "status"]) == 0


def test_kurooto_run_alone_still_runs_the_assistant(monkeypatch):
    from kurooto import cli, daemon

    monkeypatch.setattr(daemon, "run", lambda: 7)
    monkeypatch.setattr(cli, "run_all", lambda what: 9)
    assert cli.main(["run"]) == 7
    assert cli.main(["run", "all"]) == 9
