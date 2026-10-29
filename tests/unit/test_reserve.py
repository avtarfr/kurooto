"""The reserve: Kurooto's state as Markdown files an AI program can open (alarms, deadlines, calendar, settings,
add-ons, and one guide to what it may do), without any secret, rewritten only when the text changes."""

from kurooto.core import places, reserve


def test_every_file_is_written_and_a_second_run_writes_nothing(env):
    env.on("deadlines", "reminders")
    changed = reserve.refresh(env.app)
    assert set(changed) == set(reserve.BUILDERS)
    folder = reserve.folder(env.app)
    assert all((folder / n).is_file() for n in reserve.BUILDERS)
    assert reserve.refresh(env.app) == []  # unchanged text isn't written again


def test_settings_never_carry_a_secret_and_say_what_is_on(env):
    env.app.settings.set("telegram.token", "123:ABC-do-not-leak")
    env.app.settings.set("calls.worker", {"url": "https://x.example"})
    env.app.settings.set("look.layout", "roomy")
    env.on("reminders")
    text = reserve.settings_md(env.app)
    assert "do-not-leak" not in text and "telegram.token" not in text
    assert "look.layout" in text and "roomy" in text and "reminders" in text.split("Features that are on")[1]


def test_the_guide_lists_what_an_ai_may_do_and_where_the_state_is(env):
    env.on("reminders")
    text = reserve.guide_md(env.app)
    assert "## It may read" in text and "## It may write" in text and "Never `kurooto` itself" in text
    assert str(env.app.workspace) in text and "alarm.md" in text and "deadlines.md" in text
    assert "`" in text.split("## Kurooto's tools")[1]  # the tools, by name


def test_the_reserve_folder_is_readable_by_an_ai_and_not_writable(env):
    folder = reserve.folder(env.app)
    assert folder in places.read_roots(env.app)
    assert folder not in places.write_roots(env.app)


def test_deadlines_are_listed_nearest_first(env):
    import datetime as dt

    from kurooto.core.clock import now

    env.on("deadlines")
    dl = env.app.modules["deadlines"]
    dl.add("Second thing", now() + dt.timedelta(days=9))
    dl.add("First thing", now() + dt.timedelta(hours=30))
    text = reserve.deadlines_md(env.app)
    assert "First thing" in text and text.index("First thing") < text.index("Second thing")


def test_a_feature_in_a_bad_state_does_not_stop_the_other_files(env, monkeypatch):
    monkeypatch.setitem(reserve.BUILDERS, "calendar.md", lambda app: 1 / 0)
    changed = reserve.refresh(env.app)
    assert "settings.md" in changed
    assert "Couldn't be written" in (reserve.folder(env.app) / "calendar.md").read_text(encoding="utf-8")


def test_the_command_writes_them(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "home"))
    from kurooto import cli

    assert cli.main(["reserve"]) == 0
    assert "settings.md" in capsys.readouterr().out
    assert cli.main(["reserve"]) == 0
    assert "already up to date" in capsys.readouterr().out


def test_today_at_a_glance(env):
    """L33 (0.9.0, reserve.today): today's classes, what's due today and tomorrow, never a health or money line."""
    import datetime as dt

    from kurooto.core.clock import now

    env.on("deadlines")
    dl = env.app.modules["deadlines"]
    t = now()
    dl.add("Group theory sheet", t.replace(hour=23, minute=0) if t.hour < 23 else t + dt.timedelta(minutes=30))
    dl.add("Pay the rent", t + dt.timedelta(hours=20))
    dl.add("Thesis chapter", t + dt.timedelta(days=9))
    text = reserve.today_md(env.app)
    assert text.startswith("# Today") and "Group theory sheet" in text
    assert "Pay the rent" not in text and "Thesis chapter" not in text
    assert "today.md" in reserve.guide_md(env.app)
    env.app.settings.set("reserve.today", False)
    assert "Off" in reserve.today_md(env.app) and "today.md" not in reserve.guide_md(env.app)
