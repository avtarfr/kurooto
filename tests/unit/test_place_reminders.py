"""Location reminders (0.5.22): "remind me when I reach the library to return the book" goes to the Android app as a
"place" message (the place's name and the text; the app keeps it and says it on arrival). Off by default."""

from __future__ import annotations

from kurooto.modules.reminders import PLACE
from tests.unit import test_phone
from tests.unit.test_phone import last_item

phone = test_phone.phone  # the fixture: Phone calls set up, without a call line


def parse(text: str):
    m = PLACE.match(text)
    return (m["place"], m["what"], m["when"].lower()) if m else None


def test_what_counts_as_a_place_reminder():
    assert parse("remind me when I reach the library to return the book") == ("the library", "return the book", "when")
    assert parse("Remind me when I get home: water the plants") == ("home", "water the plants", "when")
    assert parse("remind me whenever I'm at the gym, stretch first") == ("the gym", "stretch first", "whenever")
    assert parse("remind me when I get to the station to buy a ticket")[:2] == ("the station", "buy a ticket")
    assert parse("remind me at 9 to call a friend") is None
    assert parse("remind me in 20 minutes to take the tea off") is None


def test_off_by_default_then_sent_to_the_phone(phone):
    app = phone.app
    phone.on("reminders")
    assert app.settings.get("reminders.places") is False
    out = phone.say("remind me when I reach the library to return the book")
    assert "Location reminders are off" in out and not any(op == "notify" for op, _ in phone.ops)
    app.settings.set("reminders.places", True)
    out = phone.say("remind me when I reach the library to return the book")
    assert out.startswith("Sent to your phone: when you reach library, it reminds you: return the book")
    it = last_item(phone)
    assert it["kind"] == "place" and it["title"] == "library" and it["text"] == "return the book"
    assert it["reply"] is False and "card" not in it
    phone.say("remind me whenever I'm at the gym to stretch")
    it = last_item(phone)
    assert it["kind"] == "place_every" and it["title"] == "gym" and it["text"] == "stretch"


def test_time_reminders_still_work_beside_it(phone):
    phone.on("reminders")
    assert phone.say("remind me in 20 minutes to take the tea off").startswith("I'll remind you")


def test_needs_the_phone_set_up(env):
    env.on("reminders")
    env.app.settings.set("reminders.places", True)
    assert "set up Phone calls" in env.say("remind me when I reach the library to return the book")
