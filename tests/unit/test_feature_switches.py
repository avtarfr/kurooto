"""Every feature is a switch (owner's rule, 2026-10-24): nothing is forced on anyone; fixes aren't switches.

Features are modules, off until turned on (`modules.enabled` is empty by default), and a module's jobs run only while
it's on. What runs outside a module is checked here: every job core code schedules either names the setting that turns
it off, or is plumbing every feature relies on (with the reason). A new core job without either fails, so it can't ship
without a switch. The phone app's own switches (the line's own connection, the moving background) are in Prefs.java.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "kurooto"
GUIDE = ROOT / "docs" / "SETTINGS_GUIDE.md"

# job -> the settings that turn what it does off
SWITCHED = {
    "agents:export": ["agents.export"],
    "calm:tick": ["notify.calm.on"],
    "health:daily": ["health.on"],
    "infer:sweep": ["infer.on"],
    "keep:tick": ["keep.ask"],
    "local_helper:offer": ["local_helper.offer"],
    "local_helper:tick": ["local_helper.on", "local_helper.offline"],
    "rhythm:tick": [
        "availability.learn_morning",
        "availability.learn_night",
        "availability.absence_days",
        "notify.calm.lighter_after",
    ],
}
# job -> why it isn't a feature
PLUMBING = {
    "proposals:morning": "delivers proposals that switched features made at night (Dreaming RSI, repo refresh)",
    "ask:sweep": "expires questions nobody answered (each feature's questions have their own switch)",
    "memory:nightly": "keeps the memory index in step with the notes for search and /forget (recall and threads are "
    "memory.recall and memory.threads)",
    "proposals:cleanup": "removes unanswered proposals and their scratch folders after proposals.keep_days",
    "reserve:refresh": "the Markdown copies of state the AI reads instead of running commands",
    "retention:expire": "the privacy promise: data past its retention is deleted (a fix-like guarantee, never off)",
}


def core_jobs() -> set[str]:
    files = [*(SRC / "core").glob("*.py"), SRC / "app.py", SRC / "daemon.py"]
    return {m for f in files for m in re.findall(r'every\(\s*"([^"]+)"', f.read_text(encoding="utf-8"))}


def test_every_core_job_has_a_switch_or_is_plumbing():
    missing = core_jobs() - SWITCHED.keys() - PLUMBING.keys()
    assert not missing, f"core jobs with no off switch (add a setting, then list it here): {sorted(missing)}"


def test_the_switches_exist():
    guide = GUIDE.read_text(encoding="utf-8")
    for job, keys in SWITCHED.items():
        for k in keys:
            assert f"`{k}`" in guide, f"{job}: setting {k} isn't in the settings guide"


def test_features_start_off():
    guide = GUIDE.read_text(encoding="utf-8")
    assert "| `modules.enabled` | `[]` |" in guide


def test_the_phone_apps_switches():
    prefs = (ROOT / "android" / "src" / "io" / "github" / "avtarfr" / "kurooto" / "Prefs.java").read_text()
    tab = (ROOT / "android" / "src" / "io" / "github" / "avtarfr" / "kurooto" / "PhoneTab.kt").read_text()
    for pref, label in (("direct", "Connect straight to your call line"), ("moving", "Moving background")):
        assert f'getBoolean("{pref}", true)' in prefs
        assert label in tab
