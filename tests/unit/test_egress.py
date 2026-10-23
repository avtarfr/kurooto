"""Egress ledger: every request on the internet goes through core/egress.py, which counts it per day, host and feature
and, with privacy.egress enforce, refuses a host that isn't on the list; this computer is always allowed and never
counted; programs that go online by themselves are counted as "handed to"; /egress shows the week."""

import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from kurooto.core import egress

DAY = 86400


class Fake:
    """urllib.request.urlopen's stand-in for the internet: answers `body`, remembers what was asked. This computer
    (the fake Telegram) still gets the real thing."""

    def __init__(self, body=b"hello"):
        self.body, self.asked, self.real = body, [], urllib.request.urlopen

    def __call__(self, req, timeout=30):
        url = req.full_url if isinstance(req, urllib.request.Request) else req
        if egress.host_of(url) in egress.LOOPBACK:
            return self.real(req, timeout=timeout)
        self.asked.append(url)
        body = self.body

        class R:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return None

            def read(self, n=-1):
                return body

        return R()


@pytest.fixture
def net(env, monkeypatch):
    fake = Fake()
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return env, fake


def rows(env):
    return {(r["via"] or r["host"], r["feature"]): r for r in egress.week(env.app.paths.state)}


def test_an_unlisted_host_is_blocked_in_enforce_mode(net):
    env, fake = net
    env.app.settings.set("privacy.egress", "enforce")
    with pytest.raises(urllib.error.URLError) as e:
        egress.urlopen("https://tracker.example.net/x", "Research")
    assert isinstance(e.value, egress.Blocked)
    assert "tracker.example.net" in str(e.value) and "privacy.allow_hosts" in str(e.value)
    assert fake.asked == []  # nothing went out
    r = rows(env)[("tracker.example.net", "Research")]
    assert r["blocked"] == 1


def test_an_unlisted_host_is_recorded_in_record_mode(net):
    env, fake = net
    assert egress.mode() == "record"  # the default
    req = urllib.request.Request("https://tracker.example.net/x", data=b"12345")
    with egress.urlopen(req, "Research") as r:
        assert r.read() == b"hello" and r.status == 200
    assert fake.asked == ["https://tracker.example.net/x"]
    r = rows(env)[("tracker.example.net", "Research")]
    assert (r["n"], r["out"], r["in"], r["unlisted"], r["blocked"]) == (1, 5, 5, 1, 0)


def test_listed_configured_and_your_own_hosts_are_allowed(net):
    env, fake = net
    env.app.settings.set("privacy.egress", "enforce")
    env.app.settings.set("privacy.allow_hosts", ["feeds.example.org", ".example.edu"])
    for url in (
        "https://api.telegram.org/botX/getMe",  # Kurooto's own list
        "https://kurooto-abc.your-subdomain.workers.dev/health",  # ".workers.dev": any call line
        "https://feeds.example.org/rss",  # privacy.allow_hosts
        "https://news.dept.example.edu/feed",  # a ".domain" entry there
    ):
        with egress.urlopen(url, "test") as r:
            r.read()
    with egress.urlopen("https://calendar.example.com/private.ics", "Calendar", own=True) as r:  # a link you gave
        r.read()
    assert len(fake.asked) == 5
    assert not any(r["blocked"] or r["unlisted"] for r in egress.week(env.app.paths.state))


def test_this_computer_is_always_allowed_and_never_counted(net):
    env, fake = net
    env.app.settings.set("privacy.egress", "enforce")
    with egress.urlopen("http://127.0.0.1:11434/api/tags", "Local AI models") as r:
        r.read()
    assert not egress.week(env.app.paths.state)


def test_off_checks_and_counts_nothing(net):
    env, fake = net
    env.app.settings.set("privacy.egress", "off")
    with egress.urlopen("https://tracker.example.net/x", "Research") as r:
        r.read()
    egress.handed("git", "Notes sync")
    assert fake.asked and not egress.week(env.app.paths.state)
    assert "off" in env.say("/egress")


def test_the_ledger_adds_up_per_day_and_keeps_a_bounded_window(env, tmp_path):
    st = env.app.paths.state
    t = time.time()
    for i in range(3):
        egress.record("api.telegram.org", "Telegram", out=10, got=100, now=t - i * DAY)
    egress.record("api.telegram.org", "Telegram", out=1, got=1, now=t - 10 * DAY)  # before the week
    for d in range(egress.DAYS + 5):  # older days fall off
        egress.record("ntfy.sh", "Phone calls", now=t - (40 + d) * DAY)
    led = json.loads((st / "egress.json").read_text())
    assert len(led["days"]) <= egress.DAYS
    week = rows(env)
    tg = week[("api.telegram.org", "Telegram")]
    assert (tg["n"], tg["out"], tg["in"]) == (3, 30, 300)
    assert ("ntfy.sh", "Phone calls") not in week
    assert egress.week(st, days=11)[0]["n"] == 4


def test_programs_that_go_online_are_handed_to(net):
    env, _ = net
    egress.handed("git", "Notes sync")
    egress.handed("git", "Notes sync")
    egress.handed("agy", "AI requests")
    r = rows(env)
    assert r[("git", "Notes sync")]["n"] == 2 and r[("agy", "AI requests")]["n"] == 1


def test_slash_egress_shows_the_week(net):
    env, _ = net
    assert "Nothing has left" in env.say("/egress")
    with egress.urlopen("https://api.telegram.org/x", "Telegram") as r:
        r.read()
    egress.handed("Claude Code", "AI requests")
    env.app.settings.set("privacy.egress", "enforce")
    with pytest.raises(egress.Blocked):
        egress.urlopen("https://tracker.example.net/x", "Research")
    out = env.say("/egress")
    assert "api.telegram.org (Telegram): 1 request" in out
    assert "handed to Claude Code (AI requests): 1 run" in out
    assert "Blocked" in out and "tracker.example.net (Research): 1 time" in out
    assert "privacy.allow_hosts" in out
    assert "/egress" in env.app.help()


def test_research_feeds_are_yours_and_its_sources_are_listed(net):
    env, fake = net
    env.app.settings.set("privacy.egress", "enforce")
    res = env.app.modules["research"]
    assert res._get("https://blog.example.org/feed.xml", own=True) == b"hello"  # a feed you added
    assert res._get(res.ep("arxiv") + "?search_query=x") == b"hello"  # export.arxiv.org is on the list
    env.app.settings.set("research.endpoints", {"arxiv": "https://mirror.example.net/api/query"})
    with pytest.raises(egress.Blocked):
        res._get(res.ep("arxiv") + "?search_query=x")


def test_the_privacy_page_lists_the_same_hosts():
    """docs/PRIVACY.md's "Where requests go" table is the list's source of truth for people; it must match HOSTS."""
    text = (Path(__file__).resolve().parents[2] / "docs" / "PRIVACY.md").read_text(encoding="utf-8")
    part = text.split("## Where requests go", 1)[1].split("\n## ", 1)[0]
    hosts = re.findall(r"^\| `([^`]+)` \|", part, re.M)
    assert hosts and set(hosts) == set(egress.HOSTS)
