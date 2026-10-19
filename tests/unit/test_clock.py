import datetime as dt

import pytest

from kurooto.core.clock import parse_when

BASE = dt.datetime(2026, 10, 19, 17, 40)  # a Monday


@pytest.mark.parametrize(
    "text,want",
    [
        ("21:30", dt.datetime(2026, 10, 19, 21, 30)),
        ("9pm", dt.datetime(2026, 10, 19, 21, 0)),
        ("7:00", dt.datetime(2026, 10, 20, 7, 0)),  # already past today: tomorrow
        ("at 12am", dt.datetime(2026, 10, 20, 0, 0)),
        ("in 20 minutes", BASE + dt.timedelta(minutes=20)),
        ("30m", BASE + dt.timedelta(minutes=30)),
        ("+45", BASE + dt.timedelta(minutes=45)),
        ("2h", BASE + dt.timedelta(hours=2)),
        ("in 3 days", BASE + dt.timedelta(days=3)),
        ("tomorrow 7am", dt.datetime(2026, 10, 20, 7, 0)),
        ("tomorrow", dt.datetime(2026, 10, 20, 9, 0)),
        ("tonight", dt.datetime(2026, 10, 19, 21, 0)),
        ("Wed 9:15", dt.datetime(2026, 10, 21, 9, 15)),
        ("monday", dt.datetime(2026, 10, 26, 9, 0)),  # next week's, not today's
        ("next friday at 6pm", dt.datetime(2026, 10, 23, 18, 0)),
        ("2026-11-02 14:00", dt.datetime(2026, 11, 2, 14, 0)),
        ("2026-11-02", dt.datetime(2026, 11, 2, 9, 0)),
    ],
)
def test_reads(text, want):
    assert parse_when(text, BASE) == want


@pytest.mark.parametrize("text", ["", "monkey", "25:00", "whenever", "in 3 fortnights"])
def test_refuses(text):
    with pytest.raises(ValueError):
        parse_when(text, BASE)
