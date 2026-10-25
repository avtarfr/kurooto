"""Brain, stage 04: the statistics read (shadow mode), the tone tag, what's kept and what leaves (I-11)."""

import datetime as dt
import json
import random

import pytest

from kurooto import mind
from kurooto.mind import log as mlog
from kurooto.mind import mood, read, stats, tone
from kurooto.mind import scorekeeper as sk


def day(i, exam=False, **sig):
    load = {
        "deadlines_w": 6 if exam else 1,
        "deadlines_n": 3 if exam else 1,
        "class_h": 4,
        "exam_season": exam,
        "weekday": i % 7,
    }
    return read.Day(f"d{i:03d}", load, sig)


def history(n=28, exam_from=None, seed=1):
    """n days of a steady student; days from exam_from on are exam days (late nights, long study)."""
    rnd = random.Random(seed)  # noqa: S311 (a fixed seed for a test)
    out = []
    for i in range(n):
        ex = exam_from is not None and i >= exam_from
        out.append(
            day(
                i,
                ex,
                sleep_min=1380 + rnd.gauss(0, 12) + (90 if ex else 0),
                wake_min=420 + rnd.gauss(0, 10) + (40 if ex else 0),
                study_min=120 + rnd.gauss(0, 10) + (60 if ex else 0),
            )
        )
    return out


def test_stats_basics():
    X = [[i, i % 7] for i in range(28)]
    y = [2 + 0.5 * a + 1.0 * b for a, b in X]
    beta = stats.ridge(X, y, 1e-4)
    assert [round(v, 2) for v in beta] == [2.0, 0.5, 1.0]
    assert stats.cusum([2] * 6, 0.5, 4.0) == [2, 5]
    f = stats.isotonic([1, 2, 3, 4], [0, 1, 0, 1])
    assert [f(x) for x in (1, 2, 3, 4)] == [0.0, 0.5, 0.5, 1.0]
    assert stats.mad_scale([1, 2, 3, 4, 100]) == pytest.approx(1.4826)


def test_load_regression_explains_exam_week():
    hist = history(28, exam_from=14)  # two weeks of exams are in the history, so the calendar explains late nights
    exam = day(40, True, sleep_min=1380 + 90, wake_min=420 + 40, study_min=180)
    assert read.read_day(hist, exam).label == "steady" and read.read_day(hist, exam).n_votes == 0
    calm = history(28)  # the same pattern with no exams on the calendar is out of the ordinary
    odd = day(40, False, sleep_min=1380 + 95, wake_min=420 + 40, study_min=30)
    r = read.read_day(calm, odd)
    assert r.n_votes >= 2 and r.label in ("low", "stretched")


def test_votes_and_sleep_cluster():
    calm = history(28)
    odd = day(40, False, sleep_min=1380 + 95, wake_min=420 + 60, study_min=120)  # sleep and wake both off
    r = read.read_day(calm, odd)
    assert [n for n, _ in r.votes] == ["sleep cluster"] and r.n_votes == 1


def test_two_day_rule():
    a = read.Read("d1", "low", [("x", 3)] * 3, 3, 9.0, {})
    b = read.Read("d2", "low", [("x", 3)] * 3, 3, 9.0, {})
    weak = read.Read("d3", "steady", [("x", 3)] * 2, 2, 6.0, {})
    assert read.counts(a, b) and not read.counts(None, b) and not read.counts(a, weak)
    assert read.counts(None, weak, answer="low")  # your own answer says so


def test_not_enough_data():
    pairs = [(float(i % 10), i % 3 != 0) for i in range(49)]
    assert read.confidence(pairs, 5.0) is None
    pairs.append((5.0, True))
    assert read.confidence(pairs, 5.0) is not None


def test_accuracy_gate():
    good = [(1.0, True)] * 20
    bad = [(1.0, True)] * 7 + [(1.0, False)] * 13  # 35% right over the last 20
    assert read.accuracy_ok(good) and not read.accuracy_ok(bad) and read.accuracy_ok(bad[:10])


# ------------------------------------------------------------------------------------------------ the tone tag
class FakeLM:
    def __init__(self, word="tired"):
        self.word = word
        self.calls = []

    def have(self):
        return {"gemma:e4b"}

    def wanted(self):
        return [{"key": "helper", "tag": "gemma:e4b"}]

    def api(self, path, body=None, timeout=10):
        self.calls.append(body["prompt"])
        word = self.word

        class R:
            def __enter__(s):
                return s

            def __exit__(s, *a):
                return False

            def read(s):
                return json.dumps({"response": word}).encode()

        return R()


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind", "local_models"])
    a.settings.set("mind.tone.on", True)
    facts = []
    monkeypatch.setattr(mind.connect(a), "report", lambda kind, body: facts.append((kind, body)) or True)
    a.facts = facts
    yield a
    mind.forget_client(a)
    a.close()


def _machine(monkeypatch, profile, ram, ac=True, app=None):
    from kurooto.core import hardware

    monkeypatch.setattr(hardware, "detect", lambda *a, **k: type("M", (), {"ram_gb": ram})())
    monkeypatch.setattr(hardware, "profile", lambda m: profile)
    monkeypatch.setattr(app.power, "on_ac", lambda: ac)


def test_tone_tiers(app, monkeypatch):
    lm = FakeLM()
    monkeypatch.setitem(app.modules, "local_models", lm)
    _machine(monkeypatch, "small-gpu", 16, app=app)
    assert tone.tier(app) == "gpu"
    _machine(monkeypatch, "light", 16, app=app)
    assert tone.tier(app) == "cpu"
    _machine(monkeypatch, "light", 8, ac=False, app=app)
    assert tone.tier(app) == "none"  # 8 GB on battery: skip tone
    app.settings.set("mind.tone.on", False)
    _machine(monkeypatch, "big-gpu", 32, app=app)
    assert tone.tier(app) == "none"  # off by default
    app.settings.set("mind.tone.on", True)
    monkeypatch.setitem(app.modules, "local_models", type("L", (), {"have": lambda s: set(), "wanted": lambda s: []})())
    assert tone.tier(app) == "none"  # no local model


def test_tone_tags_locally_keeps_numbers_and_drops_them(app, monkeypatch):
    lm = FakeLM("tired")
    monkeypatch.setitem(app.modules, "local_models", lm)
    _machine(monkeypatch, "light", 16, app=app)  # the cpu tier: batched
    tone.seen(app, "ugh, up till 4 again, everything is due")
    assert lm.calls == []  # nothing yet: it waits in memory for the hour
    assert tone.batch(app) == 1 and "everything is due" in lm.calls[0]
    f = app.paths.state / tone.FILE
    kept = f.read_text(encoding="utf-8")
    assert "ugh" not in kept and "due" not in kept  # the words are never written
    assert tone.daily_mean(app, mood.today()) == -0.5
    f.write_text(json.dumps({"day": "2000-01-01", "tags": [1.0]}))
    assert tone.roll(app) and not f.exists()  # tags of an earlier day are dropped


# ------------------------------------------------------------------------------------------- what's kept, what leaves
@pytest.fixture
def keeper(tmp_path, monkeypatch):
    monkeypatch.setattr(mlog, "_writer_pid", None)  # restored afterwards
    k = sk.Keeper(tmp_path / "mind")
    yield k
    k.close()


def put_days(k, n=28, start=dt.date(2026, 9, 1)):
    for i in range(n):
        d = (start + dt.timedelta(days=i)).isoformat()
        for name, v in (("wake_min", 420 + i % 3), ("study_min", 120), ("sleep_min", 1380), ("load_deadlines_w", 1)):
            assert k.append("signal", {"day": d, "name": name, "value": v}).get("ok")


def test_state_never_leaves_the_log(keeper, tmp_path):
    """I-11: the log keeps counts, ids and a hash, never the label, the evidence or a signal's value."""
    put_days(keeper)
    keeper.append(
        "read_day",
        {
            "day": "2026-09-28",
            "label": "stretched",
            "votes": [["sleep cluster", 3.1]],
            "evidence": {"sleep_min": 3.1},
            "strength": 3.1,
            "counted": True,
        },
    )
    keeper.append("read_answer", {"day": "2026-09-28", "right": False, "strength": 3.1, "label": "stretched"})
    keeper.append("forecast", {"day": "2026-09-29", "params": {"wake_min": [431.5, 9.0]}, "planned": []})
    blob = " ".join(json.dumps(r.body) for r in keeper.log.read(0, None, 1000))
    for word in ("stretched", "sleep cluster", "431.5", "1380", "wake_min", "evidence"):
        assert word not in blob
    kinds = {r.kind for r in keeper.log.read(0, None, 1000)}
    assert {"read_day", "read_answer", "forecast"} <= kinds
    rows = keeper.score.rows("reads", "read:2026-09-28")
    assert rows and rows[0]["meta"]["label"] == "stretched"  # the label lives in score.db, with a retention


def test_a_signal_must_be_a_known_number(keeper):
    assert keeper.append("signal", {"day": "2026-09-01", "name": "wake_min", "value": 420}).get("ok")
    for bad in (
        {"day": "yesterday", "name": "wake_min", "value": 1},
        {"day": "2026-09-01", "name": "my_secret", "value": 1},
        {"day": "2026-09-01", "name": "wake_min", "value": "late"},
        {"day": "2026-09-01", "name": "wake_min", "value": True},
    ):
        assert "error" in keeper.append("signal", bad)


def test_retention(keeper, monkeypatch):
    import time

    put_days(keeper, 3)
    keeper.append("read_answer", {"day": "2026-09-01", "right": True, "strength": 2.0})
    t = time.time()
    monkeypatch.setattr(time, "time", lambda: t + 8 * 86400)
    keeper.retention()
    assert keeper.score.rows("reads", "answer:") == []  # your answers: 7 days
    assert keeper.score.rows("reads", "cal:") != []  # the calibration pair (no date, no words) stays
    assert keeper.score.rows("signals", "") != []  # the day's numbers: 30 days
    monkeypatch.setattr(time, "time", lambda: t + 31 * 86400)
    keeper.retention()
    assert keeper.score.rows("signals", "") == []


def test_forget_cascades(app, monkeypatch, keeper):
    """I-11: Forget this removes the day's numbers, read, answer, forecast and what core/retention kept."""
    put_days(keeper, 3)
    keeper.append(
        "read_day",
        {"day": "2026-09-02", "label": "low", "votes": [], "evidence": {}, "strength": 1.0, "counted": False},
    )
    keeper.append("read_answer", {"day": "2026-09-02", "right": False, "strength": 1.0})
    keeper.append("forecast", {"day": "2026-09-02", "params": {"wake_min": [420.0, 8.0]}})
    spans = []
    from kurooto.core import retention

    monkeypatch.setattr(retention, "forget", lambda app, lo, hi, **kw: spans.append((lo, hi)) or {})
    monkeypatch.setattr(app, "events", app.events)
    sent = []
    monkeypatch.setattr(
        mind.connect(app), "report", lambda kind, body: sent.append((kind, body)) or keeper.append(kind, body)
    )
    (app.paths.state / tone.FILE).write_text(json.dumps({"day": "2026-09-02", "tags": [-1.0]}))
    assert "Forgot 2026-09-02" in mood.forget_day(app, "2026-09-02")
    assert keeper.score.rows("signals", "2026-09-02:") == []
    for pre in ("read:2026-09-02", "answer:2026-09-02", "cal:2026-09-02", "forecast:2026-09-02"):
        assert keeper.score.rows("reads", pre) == []
    assert keeper.score.rows("signals", "2026-09-01:") != []  # other days stay
    assert len(spans) == 1 and spans[0][1] - spans[0][0] == 86400  # the day's messages, calls and requests go too
    assert not (app.paths.state / tone.FILE).exists()


def test_off_asks_then_deletes(app, monkeypatch, keeper):
    put_days(keeper, 3)
    out = []
    monkeypatch.setattr(app, "notify", lambda text, **kw: out.append((text, kw)))
    monkeypatch.setattr(mind.connect(app), "report", lambda kind, body: keeper.append(kind, body))
    assert "asks" in mood.off(app)
    assert (
        app.settings.get("mind.read.on") is False and out and keeper.score.rows("signals", "") != []
    )  # not yet deleted
    assert "Deleted" in mood.off(app, confirm=True)
    assert keeper.score.rows("signals", "") == []


def test_shadow_mode_nothing_reads_the_read():
    """Nothing in the gate, Calm, the notifier or the decision records reads the read or the forecast yet."""
    import inspect

    from kurooto.core import calm, notify
    from kurooto.mind import gate, records

    for m in (gate, calm, notify, records):
        src = inspect.getsource(m)
        for word in (
            "kurooto.mind.mood",
            "mind import mood",
            "import mood",
            "read.read_day",
            "mood.view",
            "mood.run_",
            "forecast.predict",
            "forecast.fit",
            "from kurooto.mind import read",
        ):
            assert word not in src, (m.__name__, word)


def test_a_whole_day_sends_nothing_out(app, monkeypatch, keeper):
    """I-11: run a day (tone, numbers, read, forecast, view, an ask) with the cloud faked; no request leaves, and
    nothing Kurooto says through a channel names the read."""
    import urllib.request

    from kurooto.core import egress

    leaks = []
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *a, **k: leaks.append(a) or (_ for _ in ()).throw(OSError("no"))
    )
    monkeypatch.setattr(egress, "allow", lambda *a, **k: leaks.append(a) or "no")
    lm = FakeLM("stressed")
    monkeypatch.setitem(app.modules, "local_models", lm)
    _machine(monkeypatch, "small-gpu", 16, app=app)
    said = []
    monkeypatch.setattr(app, "notify", lambda text, **kw: said.append(text))
    monkeypatch.setattr(mind.connect(app), "report", lambda kind, body: keeper.append(kind, body))
    d = mood.today()
    for i in range(14):
        for name, v in (("wake_min", 420), ("study_min", 120), ("load_class_h", 4)):
            keeper.append(
                "signal", {"day": (d - dt.timedelta(days=i + 1)).isoformat(), "name": name, "value": v + i % 3}
            )
    from kurooto.mind import signals

    signals.run(app)
    r = mood.run_read(app)
    mood.run_forecast(app)
    text, _ = mood.view(app)
    mood.ask(app)
    assert r is not None and leaks == []
    for msg in said:
        assert not any(w in msg.lower() for w in ("stretched", "low", "buoyant", "stressed", "tired"))
