"""Your command words: a word works as if you'd typed what it stands for, through Kurooto's usual handling; commands
win over words; a word can't stand for another word."""

from __future__ import annotations

import pytest


@pytest.fixture
def app(env, load_addon):
    load_addon("habits", env.app)
    env.on("habits", "reminders")
    return env.app


def test_a_word_works_like_what_it_stands_for(app, env):
    assert "/hm now works like /help" in env.say("/words add hm = /help")
    before = len(env.fake.texts())
    env.say("/hm")
    got = env.fake.texts()[before:]
    assert got and any("/words" in t or "Reminders" in t or "reminders" in t for t in got)
    assert "/hm → /help" in env.say("/words")


def test_a_word_for_the_start_of_a_request(app, env):
    env.say("/words add rem = remind me")
    said = env.say("/rem at 21:30 to water the plants")
    assert "water the plants" in said and "21:30" in said


def test_commands_win_and_words_dont_chain(app, env):
    assert "already a command" in env.say("/words add help = /status")
    env.say("/words add hm = /help")
    assert "can't stand for another word" in env.say("/words add h2 = /hm")
    assert "/hm is gone" in env.say("/words remove hm")
    assert "No command words yet" in env.say("/words")
