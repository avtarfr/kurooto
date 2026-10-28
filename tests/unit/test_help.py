"""/help (core/commands.py): made from the real command table, grouped, each group with its user wiki page, every
message under Telegram's 4096 characters, and every command registered anywhere in it."""

import ast
import inspect
import re
import textwrap
from pathlib import Path

import pytest

from kurooto.app import App
from kurooto.core import commands
from kurooto.modules.base import Incoming
from kurooto.modules.text import tidy

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    a = App()
    yield a
    a.close()


def everything(app):
    app.settings.set("modules.enabled", list(app.modules))


def handled_in_app() -> set[str]:
    """The /commands App.handle answers itself: every string it compares `name` with."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(App.handle)))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == "name":
            for c in node.comparators:
                for k in ast.walk(c):
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        out.add(k.value)
    return out


def test_every_command_registered_anywhere_is_in_help(app):
    everything(app)
    text = "\n".join(app.help_parts())
    core = {n for names, _ in commands.CORE for n in names}
    own = handled_in_app()
    assert {"q", "questions", "forget", "help", "start"} <= own and own <= core, "add it to core/commands.py:CORE"
    names = set(core)
    for m in app.modules.values():
        names |= {c.name for c in m.commands()}
    missing = sorted(n for n in names if not re.search(rf"(?<![\w/])/{re.escape(n)}\b", text))
    assert not missing, f"not in /help: {missing}"
    app.settings.set("modules.enabled", [])
    assert "/sync" in "\n".join(app.help_parts())  # Kurooto's own /sync while Notes sync is off


def test_every_feature_has_a_group_with_a_wiki_page(app):
    pages = {p.stem for p in (ROOT / "docs" / "wiki" / "user").glob("*.md")}
    for g in (*commands.GROUPS, commands.MORE):
        assert g.page in pages, g.key
        assert commands.find_group(g.key) is g and commands.find_group(g.title) is g
    loose = [m.id for m in app.modules.values() if commands.group_of(m.id) is commands.MORE]
    assert loose == [], "add each feature to a group in core/commands.py:GROUPS"
    core = {names[0] for names, _ in commands.CORE} | {"sync"}
    grouped = [n for g in commands.GROUPS for n in g.core]
    assert sorted(grouped) == sorted(core)  # each of Kurooto's own commands in exactly one group


def test_each_message_fits_telegram(app):
    for on in ([], ["reminders"], list(app.modules)):
        app.settings.set("modules.enabled", on)
        for arg in ["", "all", "call", "zzzz", *(g.key for g in commands.GROUPS)]:
            parts = app.help_parts(arg)
            assert parts and all(0 < len(p) < 4096 for p in parts), (on, arg)


def test_help_is_always_the_index_and_a_group_has_the_detail(app):
    app.settings.set("modules.enabled", ["reminders"])
    (index,) = app.help_parts()  # a short list is an index too (0.6.0): one line per group, /help <group> for more
    assert index.startswith("Kurooto, your assistant") and "/help <group>" in index
    assert "Reminders and deadlines (/help reminders; " in index and "wiki/user/reminders-and-deadlines.html" in index
    assert "/remind" in index and "/remind  a reminder" not in index and "Off right now" in index
    detail = app.help_parts("reminders")[0]
    assert "/remind  a reminder" in detail and '"remind me at 9 to call mum"' in detail
    everything(app)
    parts = app.help_parts()
    index = "\n\n".join(parts)
    assert len(parts) <= 2 and "/help <group>" in parts[0] and "Calls and phone (/help calls; " in index
    assert "wiki/user/calls.html): /hold /calls /call" in index and "/alarm" in index
    assert "/alarm  the wake-up call" not in index  # what each does: /help calls
    calls = app.help_parts("calls")[0]
    assert calls.startswith("Calls and phone (more: ") and "/alarm  the wake-up call" in calls
    assert '"wake me at 6:45"' in calls and "Just say:" in calls
    groups = app.help_parts("all")
    assert len(groups) == len(commands.GROUPS) and groups[0].startswith("Talking")


def test_wording_trimmed_to_fit_is_whole_again(app):
    everything(app)
    privacy = app.help_parts("privacy")[0]
    assert '"what was I doing last Thursday?"' in privacy
    assert "/egress  where my requests went in the last 7 days: each host and feature, requests, bytes" in privacy


def test_a_group_says_what_is_off_in_it(app):
    app.settings.set("modules.enabled", ["reminders"])
    out = app.help_parts("calls")[0]
    assert "Off: Phone calls (/call /phone /phones /unpair /lessons). Features → Phone calls → Turn on." in out
    assert app.help_parts("call")[0].startswith('About "call":')  # a word, not a group: what matches it


def test_examples_are_what_each_request_understands(app):
    """Each built-in request's examples (what /help shows) are taken by that request."""
    everything(app)
    for text in ("/subject add Linear Algebra (la)", "/busy add gym mon,wed,fri 18:00-19:00", "/due fri 17:00 ps3"):
        app.handle(Incoming(text, via="terminal", respond=lambda t, buttons=None: None))
    for m in app.modules.values():
        for it in m.intents():
            assert it.examples, f"{m.id}.{it.name}: add examples for /help"
            if it.name == "call_when":  # "I didn't wake up at 7": it depends on the time of day
                continue
            for ex in it.examples:
                assert it.match(tidy(ex)) is not None, f"{it.name}: {ex!r}"


def test_help_on_telegram_and_in_the_phone_app_is_the_same(env):
    env.on("reminders")
    n = len(env.fake.texts())
    env.say("/help all")
    sent = env.fake.texts()[n:]
    assert len(sent) == len(env.app.help_parts("all")) > 1  # one message per group
    got = []
    env.app.handle(Incoming("/help", via="app", respond=lambda t, buttons=None: got.append(t)))
    assert got == env.app.help_parts()


def test_every_plain_english_request_is_in_help_and_understood(env):
    """Every feature's request (its examples) and every one Kurooto understands by itself (CORE_SAY) is in /help, and
    each of Kurooto's own examples is taken by what /help says takes it."""
    from kurooto.core import infer, ledger, meetings, repoproject, syncall, threads

    app = env.app
    everything(app)
    env.say("/subject add Linear Algebra")
    text = "\n".join(app.help_parts("all"))
    missing = []
    for m in app.modules.values():
        for it in m.intents():
            missing += [f"{m.id}.{it.name}: {ex}" for ex in it.examples if f'"{ex}"' not in text]
    assert not missing, f"not in /help: {missing}"
    check = {
        "threads": lambda t: threads.intent(app, t) is not None,
        "memory": lambda t: ledger.intent(app, t) is not None,
        "sync": syncall.wanted,
        "set up from what you say": lambda t: bool(infer.observe(app, t)),
        "meeting minutes": lambda t: bool(meetings.EXPLICIT.search(t)),
        "a project from its repository": lambda t: repoproject.asked(t) is not None,
        "quieter messages": lambda t: app.calm.intent(t) is not None,
    }
    for key, what, examples, _needs in commands.CORE_SAY:
        assert commands.find_group(key) is not None, key
        for ex in examples:
            assert f'"{ex}"' in text, ex
            assert check[what](ex), f"{what}: {ex!r}"
    app.settings.set("infer.on", False)
    assert '"I got a project under Prof Ortiz"' not in "\n".join(app.help_parts("all"))  # off: not offered
    assert 'just say "sync everything"' in app.help_parts("sync")[0]


def test_the_phone_apps_chat_gets_the_index_with_its_wiki_links(env):
    """The app's chat (modules/calls/chat.py:PhoneChat) answers /help with the same index, each group's wiki link in
    it (the Android chat makes them tappable)."""
    app = env.app
    got = []
    app.handle(Incoming("/help", via="app", respond=lambda t, buttons=None: got.append(t)))
    assert got and got == app.help_parts() and commands.wiki() in got[-1]
    assert all(commands.wiki(g.page) in "\n".join(got) for g in commands.GROUPS if f"/help {g.key}" in "\n".join(got))
    # 0.7.6: the Compose chat makes web addresses tappable (0.8.10: the thread is ChatThread.kt, ChatActivity forwards)
    chat = (ROOT / "android" / "src" / "io" / "github" / "avtarfr" / "kurooto" / "ChatThread.kt").read_text()
    assert "LinkAnnotation.Url" in chat


def test_help_settings_links_the_settings_guide(app):
    """/help settings ends with the settings guide's page (0.8.10): every setting, what it does, when to change it."""
    text = "\n".join(app.help_parts("settings"))
    assert "Every setting explained" in text and "wiki/user/settings-guide.html" in text
    assert "settings-guide.html" not in app.help_parts("reminders")[0]
