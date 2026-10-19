import datetime as dt
import json

from kurooto.core.clock import now
from tests.fakes.openai import FakeOpenAI


def test_after_class_question_goes_to_the_class_log(env):
    env.on("subjects")
    env.say("/subject add Linear Algebra (la)")
    end = now() + dt.timedelta(minutes=30)
    day = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][now().weekday()]
    if end.date() != now().date():
        return  # too close to midnight to make a class today
    env.say(f"/class {day} {(now() - dt.timedelta(minutes=30)):%H:%M}-{end:%H:%M} la")
    env.on("capture")
    job = env.app.scheduler.get(f"capture:linear-algebra:{end:%H:%M}")
    assert job is not None
    env.app.modules["capture"]._ask(job.payload)
    assert "How was Linear Algebra?" in env.fake.texts()[-1]
    out = env.reply_to_last("Defined eigenvectors; doubt about diagonalisation.")
    assert out == "Saved to linear-algebra/class-log.md."
    log = (env.app.workspace / "linear-algebra" / "class-log.md").read_text(encoding="utf-8")
    assert "diagonalisation" in log and log.startswith("# Linear Algebra: class log")


def test_retro_proposes_only_allowed_changes_and_waits_for_approval(env):
    ai = FakeOpenAI()
    try:
        app = env.app
        app.secrets.set("custom.api_key", ai.key)
        app.settings.set("brain.base_urls", {"custom": ai.base})
        app.settings.set("brain.models", {"custom": {"medium": "m", "low": "m", "high": "m"}})
        app.settings.set("brain.main", "custom")
        env.on("chat", "checkins", "retro")
        ai.answer = json.dumps(
            {
                "proposals": [
                    {"key": "checkins.times.evening", "value": "21:30", "why": "You answered earlier evenings."},
                    {"key": "telegram.chat_id", "value": 1, "why": "sneaky"},
                    {"key": "deadlines.ping_h", "value": "lots", "why": "wrong type"},
                ]
            }
        )
        assert app.modules["retro"].run() == 1
        msg = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
        assert "checkins.times.evening" in msg["text"]
        assert app.settings.get("checkins.times.evening") == "22:00"  # unchanged until approved
        data = msg["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        assert env.press(data).startswith("Done: checkins.times.evening")
        assert app.settings.get("checkins.times.evening") == "21:30"
        assert env.press(data) == "That suggestion is gone."
    finally:
        ai.close()
