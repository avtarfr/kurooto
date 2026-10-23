"""Holiday calendars (Calendar: /cal holidays): all-day events in them are days without classes."""

import datetime as dt
import json

from kurooto.modules.calendar import parse_ics

ICS = """BEGIN:VCALENDAR
X-WR-CALNAME:Holidays in Testland
BEGIN:VEVENT
UID:h1
SUMMARY:Founders' Day
DTSTART;VALUE=DATE:{d}
DTEND;VALUE=DATE:{d2}
END:VEVENT
BEGIN:VEVENT
UID:h2
SUMMARY:Parade (timed, not a holiday)
DTSTART:{t}
DTEND:{t2}
END:VEVENT
END:VCALENDAR
"""


def test_a_holiday_calendars_all_day_events_are_days_without_classes(env):
    app = env.app
    day = dt.date.today() + dt.timedelta(days=2)
    t = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(10))
    f = "%Y%m%dT%H%M%S"
    text = ICS.format(
        d=f"{day:%Y%m%d}",
        d2=f"{day + dt.timedelta(days=1):%Y%m%d}",
        t=t.strftime(f),
        t2=(t + dt.timedelta(hours=1)).strftime(f),
    )
    app.secrets.set("calendar.ics", json.dumps(["https://calendar.example/holidays.ics"]))
    cal = app.modules["calendar"]
    cal._fetch = lambda url: parse_ics(text, cal.tz())
    app.settings.set("subjects.list", [{"slug": "probability", "name": "Probability", "aliases": []}])
    app.settings.set(
        "subjects.timetable", [{"day": d, "start": "09:00", "end": "09:55", "subject": "probability"}
                               for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")]
    )  # fmt: skip
    env.on("subjects", "calendar")
    subj = app.modules["subjects"]
    assert subj.classes_on(day) and "Holiday calendars: none." in env.say("/cal holidays")
    out = env.say("/cal holidays testland")
    assert out.startswith("All-day events in testland are holidays now") and "(1 in the next 14 days)" in out
    assert subj.no_classes(day) == "holiday" and subj.classes_on(day) == []
    assert subj.no_classes(day + dt.timedelta(days=1)) is None  # a timed event isn't a holiday
    assert env.say("/cal holidays none") == "No calendar marks holidays now."
    assert subj.no_classes(day) is None
