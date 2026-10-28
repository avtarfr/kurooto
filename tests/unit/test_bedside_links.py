"""Bedside mode's links (0.9.0): the phone says when bedside mode opens or closes (L11, phone.bedside.signal: a
flag, no sensor; one kept on the line while the computer was off is dropped), and the Today list it reads carries
"asleep" while Kurooto sleeps (L135)."""

from __future__ import annotations

from tests.unit.test_phone import phone  # noqa: F401 (the shared fixture)
from tests.unit.test_phone_chat import body


def test_bedside_opening_and_closing_reach_the_computer(phone):  # noqa: F811
    app, pc = phone.app, phone.calls.chat
    code, out = pc.take(body(app, "a" * 16, op="bedside", args={"on": True}))
    assert code == 200 and out["ok"] and pc.bedside()
    assert [e for e in app.events.tail(20) if e["kind"] == "phone_bedside"][-1]["on"] is True
    pc.take(body(app, "b" * 16, op="bedside", args={"on": False}))
    assert not pc.bedside()
    # kept on the line while the computer was off: stale, dropped
    code, out = pc.take(body(app, "c" * 16, op="bedside", args={"on": True}), queued=True)
    assert out["ok"] is False and not pc.bedside()
    # not sealed (anyone could post it): refused
    assert pc.take(body(app, "d" * 16, sealed=False, op="bedside", args={"on": True}))[0] == 403
    app.settings.set("phone.bedside.signal", False)
    code, out = pc.take(body(app, "e" * 16, op="bedside", args={"on": True}))
    assert out["ok"] is False and not pc.bedside()


def test_the_today_list_says_asleep(phone, monkeypatch):  # noqa: F811
    from kurooto.mind import sleep

    t = phone.calls.today
    monkeypatch.setattr(sleep, "asleep", lambda app: False)
    assert "asleep" not in t.snapshot()
    monkeypatch.setattr(sleep, "asleep", lambda app: True)
    assert t.snapshot()["asleep"] is True
