"""Processor use is measured from the cores' own counters over a steady window, the same for every reader: two
readers a moment apart used to get windows of milliseconds from psutil.cpu_percent (a core read 98% while idle)."""

from collections import namedtuple

from kurooto.core import vitals

T = namedtuple("T", "user nice system idle iowait irq softirq steal guest guest_nice")


def _times(busy, idle):
    return [T(b, 0, 0, i, 0, 0, 0, 0, 0, 0) for b, i in zip(busy, idle, strict=True)]


def test_two_readers_in_one_second_share_one_reading(monkeypatch):
    clock = [100.0]
    seq = iter([_times([0, 0], [0, 0]), _times([1.0, 0.25], [0.0, 0.75]), _times([1.01, 0.25], [0.0, 0.76])])
    monkeypatch.setattr(vitals.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(vitals.psutil, "cpu_times", lambda percpu=True: next(seq))
    s = vitals.Sampler.__new__(vitals.Sampler)
    s._times, s._cores = None, []
    assert s._core_use() == [0.0, 0.0]  # the baseline: one zero per core until a second has passed
    clock[0] += 1.0
    assert s._core_use() == [1.0, 0.25]  # over the full second
    clock[0] += 0.05
    assert s._core_use() == [1.0, 0.25]  # a second reader 50 ms later gets the same, not a 50 ms window


def test_busy_leaves_out_idle_iowait_and_guest():
    t = T(user=5, nice=1, system=2, idle=10, iowait=2, irq=0, softirq=0, steal=0, guest=3, guest_nice=1)
    busy, total = vitals._busy(t)
    assert total == 5 + 1 + 2 + 10 + 2 - 0  # guest is already counted in user
    assert busy == total - 12


class _P:
    def __init__(self, pid, cpu_s, born=1.0):
        CT = namedtuple("CT", "user system")
        MI = namedtuple("MI", "rss")
        self.pid = pid
        self.info = {"name": f"p{pid}", "memory_info": MI(1000 * pid), "num_threads": 1,
                     "cpu_times": CT(cpu_s, 0.0), "create_time": born}  # fmt: skip

    def as_dict(self, attrs):  # the listed rows' name and threads (Sampler.processes)
        return {a: self.info[a] for a in attrs}


def test_process_use_is_a_share_of_the_whole_machine_over_a_steady_window(monkeypatch):
    clock = [50.0]
    procs = {"now": [_P(1, 0.0), _P(2, 10.0)]}
    monkeypatch.setattr(vitals.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(vitals.psutil, "process_iter", lambda attrs=None: list(procs["now"]))
    monkeypatch.setattr(vitals.psutil, "cpu_count", lambda logical=True: 4)
    s = vitals.Sampler.__new__(vitals.Sampler)
    s._procs, s._share = None, {}
    s.processes()  # the baseline
    clock[0] += 2.0
    procs["now"] = [_P(1, 0.01), _P(2, 18.0)]  # one clock tick; 8 cpu seconds in 2 s on 4 cores
    rows = {r["pid"]: r["cpu"] for r in s.processes()}
    assert abs(rows[2] - 8.0 / (2.0 * 4)) < 1e-6  # 8 cpu seconds over 2 s on 4 cores: the whole machine
    assert rows[1] < 0.002  # a single 10 ms tick is a rounding error, not 0.8%
    clock[0] += 0.5
    procs["now"] = [_P(1, 5.0), _P(2, 18.0)]  # a reader half a second later gets the same numbers
    assert {r["pid"]: r["cpu"] for r in s.processes()} == rows


def test_kurootos_own_figure_is_a_share_of_the_machine_not_of_one_core(monkeypatch):
    from kurooto.web import live

    CT = namedtuple("CT", "user system")
    clock = [10.0]
    times = {"t": 0.0}

    class P:
        pid = 7

        def cpu_times(self):
            return CT(times["t"], 0.0)

        def create_time(self):
            return 1.0

    monkeypatch.setattr(live.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(live.psutil, "cpu_count", lambda logical=True: 16)
    v = live.Vitals.__new__(live.Vitals)
    assert v._share(P()) == 0.0  # the baseline
    clock[0] += 2.0
    times["t"] = 6.0  # three cores busy for 2 s: 300% of one core, 18.75% of a 16-thread machine
    assert abs(v._share(P()) - 6.0 / (2.0 * 16)) < 1e-9
    clock[0] += 0.5
    times["t"] = 9.0
    assert abs(v._share(P()) - 6.0 / (2.0 * 16)) < 1e-9  # inside the window: the same reading
