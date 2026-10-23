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
    s._core_use()  # the baseline
    clock[0] += 1.0
    assert s._core_use() == [1.0, 0.25]  # over the full second
    clock[0] += 0.05
    assert s._core_use() == [1.0, 0.25]  # a second reader 50 ms later gets the same, not a 50 ms window


def test_busy_leaves_out_idle_iowait_and_guest():
    t = T(user=5, nice=1, system=2, idle=10, iowait=2, irq=0, softirq=0, steal=0, guest=3, guest_nice=1)
    busy, total = vitals._busy(t)
    assert total == 5 + 1 + 2 + 10 + 2 - 0  # guest is already counted in user
    assert busy == total - 12
