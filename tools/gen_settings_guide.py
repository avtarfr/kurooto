#!/usr/bin/env python3
"""Write docs/SETTINGS_GUIDE.md: every setting Kurooto has, with its default and what it does, read from the code itself
(every register_defaults call, which is how a module declares its settings, with the comment on each line), so the
guide can't drift from the program. Run it after changing a setting: python tools/gen_settings_guide.py [--check]

--check exits 1 when the committed guide is out of date (CI runs it)."""

# ruff: noqa: E501
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "kurooto"
OUT = ROOT / "docs" / "SETTINGS_GUIDE.md"

NOTES = {  # settings whose source line has no comment: what they do
    "agent_plan.name": "the name of the plan your AI subscription is on, shown in usage lines",
    "agent_plan.remind_min": "minutes before a plan's usage window ends to remind you",
    "alarm.days": "the days the daily alarm rings",
    "alarm.reason": "what the wake-up call says it's for",
    "alarm.retries": "how many more times it rings if you don't answer",
    "alarm.snooze_min": "minutes a snoozed alarm waits",
    "availability.focus_keyword": "a calendar event with this in its title holds messages and calls (focus)",
    "availability.night.alarm_only": "hold calls at night only when a wake-up alarm is set",
    "availability.night.enabled": "no calls during the night hours",
    "availability.night.from": "when the night hours start",
    "availability.night.to": "when the night hours end",
    "availability.nocall_keyword": "a calendar event with this in its title means no calls during it",
    "backups.when": "when the automatic backup runs",
    "books.gemini_model": "the Gemini model that reads scanned book pages when it's chosen",
    "brain.agy.io_mode": "how Kurooto talks to agy: pipe, or a pseudo-terminal where pipes give no output",
    "brain.classify": "who judges how hard a request is: rules, main (your AI) or ollama",
    "brain.fallback": "the AI that takes over when the main one can't answer, or a list of them in order; empty: at a limit (brain.fallback_on), the other agent program, then a Gemini key",
    "brain.main": "the AI that handles requests: agy, claude, gemini, ollama or custom, or an extra Claude account (claude:<name>)",
    "brain.timeout_min.high": "minutes a hard request may run before it's stopped",
    "brain.timeout_min.low": "minutes a quick request may run before it's stopped",
    "brain.timeout_min.medium": "minutes a normal request may run before it's stopped",
    "calendar.days": "how many days ahead Kurooto reads your calendar",
    "calendar.no_calls_in_events": "no calls while a calendar event is on",
    "calendar.private_keyword": "an event with this in its title is never shown or read aloud",
    "calendar.refresh": "how often the calendar is read again",
    "calendar.remind_min": "minutes before an event to remind you (0: off)",
    "calls.live_model": "the Gemini Live voice model for calls",
    "calls.live_models": "other Live models to try, in order, when the first one is down",
    "calls.ntfy_server": "the push server the phone app listens to (change only if you run your own)",
    "calls.voice_by_kind": 'a voice per kind of call, e.g. {"alarm": "Puck"}',
    "calls.voice_by_model": "a voice per Live model",
    "calls.voice_mode": "how calls talk: auto uses Gemini Live and your phone's own speech if Live is down",
    "calls.worker.name": "your call line's name on Cloudflare (set when it's deployed)",
    "calls.worker.url": "your call line's address (set when it's deployed)",
    "calls.worker.version": "the version of the call line that's deployed (set by Kurooto)",
    "capture.delay_min": "minutes after a class ends before it asks what happened",
    "checkins.journal": "add each check-in's answer to your journal",
    "checkins.questions.evening": "the evening check-in's question",
    "checkins.questions.midday": "the midday check-in's question",
    "checkins.questions.night": "the night check-in's question",
    "classroom_notes.at": "when new Classroom posts are fetched",
    "classroom_notes.max_file_mb": "Classroom files bigger than this (MB) aren't downloaded",
    "deadlines.max_files": "the most notes read when looking for deadlines",
    "deadlines.ping_h": "hours before the due time for a deadline's first nudge (one message; closer than urgent_h it's urgent)",
    "deadlines.scan_notes": "also find deadlines written in your notes",
    "deadlines.urgent_h": "a deadline closer than this many hours is urgent",
    "drive_upload.big_files": "files over Telegram's 50 MB go to your Google Drive and you get a link",
    "drive_upload.folder": "the Google Drive folder files go to",
    "files.folder": "a folder for files outside your notes (course files, PDFs); empty: inside the notes",
    "files.links": "how notes link to files: empty is automatic",
    "gbrain.checkup_ignore": "checkup findings starting with these words aren't reported",
    "gbrain.checkup_when": "when the weekly notes-brain checkup runs",
    "gbrain.embeddings": "where the notes brain gets its embeddings: auto, ollama, gemini or off",
    "gbrain.nightly": "when the notes brain's nightly upkeep runs",
    "gbrain.sync": "how often notes are indexed",
    "google.classroom_every": "how often Classroom is checked for deadlines",
    "google.endpoints.auth": "Google's sign-in address (for tests and proxies; leave alone)",
    "google.endpoints.calendar": "Google Calendar's API address (leave alone)",
    "google.endpoints.classroom": "Google Classroom's API address (leave alone)",
    "google.endpoints.drive": "Google Drive's API address (leave alone)",
    "google.endpoints.drive_upload": "Google Drive's upload address (leave alone)",
    "google.endpoints.gmail": "Gmail's API address (leave alone)",
    "google.use": "which signed-in Google account each feature uses (Settings → Google)",
    "handwritten.every": "how often the handwritten-notes folder is checked",
    "handwritten.model": "the Gemini model that reads handwriting when it's chosen",
    "lidsafe.morning": "the time the lid-shut safeguard looks for in the morning",
    "look.hidden_features": "features hidden from the Features list (they still run if on)",
    "look.layout": "dense (everything on one board) or roomy",
    "look.links_in": "where links open: default is your default browser",
    "look.panes": "the dense board's hidden panes: status, systems, notes, terminal (empty: none hidden)",
    "look.projects": "folders of git repositories the PROJECTS box shows (empty: Research's repositories)",
    "look.study_mode": "the dashboard in Study mode: the notes map, the study timer and what's due (Alt+M, /study mode)",
    "mail_digest.at": "when mail digests run",
    "mail_digest.confidential": "what to do with confidential mail: count, hide or skip",
    "mail_digest.query": "an extra Gmail search the digest is limited to",
    "mail_digest.skip_confidential": "don't summarise mail marked confidential",
    "modules.enabled": "the features that are on (the Features list changes it)",
    "notes.layout": "how your notes are laid out: kurooto or zettelkasten",
    "notes.open_with": "the program that opens a note from the dashboard; empty: the system's",
    "notes.paths": 'your own folder for a kind of note, e.g. {"daily": "journal/{date}.md"}',
    "notes_sync.api": "the Git host's API address (leave alone)",
    "notes_sync.branch": "the branch your notes sync to",
    "notes_sync.every": "how often notes sync",
    "notify.app_kinds": "which messages also reach your phone app",
    "notify.desktop": "show notifications on this computer",
    "notify.desktop_kinds": "which messages show on this computer",
    "profile.branch": "the branch your saved profile lives on (set by Kurooto)",
    "profile.when": "when your profile is saved",
    "quiz.per_session": "questions per quiz",
    "quota.background_pct": "the share of an AI's daily free limit background work may use",
    "quota.limits": 'your own limits per AI, e.g. {"agy": 200}',
    "quota.local": "what the model on this computer does for the free limit: quick, background or off",
    "quota.on": "keep part of the free AI limit for what you're waiting on",
    "reply_drafts.ask_days": "days between asking whether drafted replies were useful",
    "reply_drafts.per_day": "the most reply drafts per day",
    "research.endpoints.arxiv": "arXiv's API address (leave alone)",
    "research.endpoints.biorxiv": "bioRxiv's API address (leave alone)",
    "research.endpoints.pubmed": "PubMed's API address (leave alone)",
    "research.log_when": "when commits are written into your project logs",
    "research.max_papers": "the most papers in a digest",
    "retro.max_proposals": "the most changes one look back proposes (it runs at retro.when: nightly by default)",
    "sources.mix": "the source mix for books and notes: how much each kind counts in answers",
    "startby.sizes.exam": "days an exam takes to prepare for",
    "startby.sizes.other": "days other work takes",
    "startby.sizes.problem_set": "days a problem set takes",
    "startby.sizes.quiz": "days a quiz takes to prepare for",
    "startby.sizes.report": "days a report takes",
    "study.idle_min": "minutes without activity before study time stops counting",
    "study.sample_s": "seconds between looks at the active window",
    "subjects.list": "your subjects: name, short names, folder",
    "subjects.margin_min": "minutes around a class when calls are held",
    "subjects.no_calls_in_class": "no calls during a class",
    "subjects.term_note": "the note that holds your term's dates and timetable",
    "subjects.timetable": "your weekly classes",
    "telegram.allowed_users": "Telegram accounts that may use the bot (set when you pair)",
    "telegram.api_base": "Telegram's API address (leave alone)",
    "telegram.chat_id": "your chat with the bot (set when you pair)",
    "telegram.silent_kinds": "message kinds sent without a sound",
    "terminal.font_size": "the Kurooto Terminal's font size",
    "updates.channel": "stable, or beta for earlier versions",
    "updates.mode": "night (update by itself), ask (Telegram question) or off",
    "updates.wait_hours": "hours a new version waits before it's installed",
    "updates.window": "the hours the automatic update may run",
    "voice_notes.api_base": "a different address for the voice-note model (empty: Google's)",
    "voice_notes.model": "the Gemini model that turns voice notes into text",
    "web.port": "the dashboard's port on this computer",
    "you.assistant_name": "the name your assistant goes by in messages",
}

INTRO = """# Settings guide

Every setting Kurooto has, what it does and its default. This file is written by `tools/gen_settings_guide.py` from the
code, so it is complete; the notes on the left come from the comment beside each setting in the source.

## Where settings live, and how to change one

- **The dashboard:** Settings (Alt+S), grouped by feature, with a search box: the core sections (you, notify,
  availability, updates, brain, ask, look, power, notes, files) and the features that are on. Changes apply at once;
  most are read again the next time they're used. A few are read only when Kurooto starts (such as `web.port`): for
  those, restart it with `kurooto stop`, then `kurooto start`. The other core sections (such as `quota`, `health`
  and `sources`) aren't on that page yet: change them in the file.
- **The file:** `settings.json` in Kurooto's config folder (Linux `~/.config/kurooto`, macOS
  `~/Library/Application Support/Kurooto/config`, Windows `%LOCALAPPDATA%\\Kurooto\\config`). It holds only what you changed; delete a
  line to go back to the default. A dotted name such as `brain.main` is the key `main` inside `brain`:
  `{"brain": {"main": "agy"}}`.
- **The terminal:** `kurooto doctor` says what's wrong with the settings that matter.
- Secrets (keys, tokens) are never in `settings.json`: they're in the system keyring or `secrets.json` beside it.

## How an AI is allowed to act (permissions)

Requests run by an agent program (agy, Claude Code) are unattended, so what they may do is decided in advance:

| | agy | Claude Code (from 0.5.6) |
|---|---|---|
| Kurooto's tools (reminders, notes, calls, files) | allowed in agy's own settings, once | given for each request |
| Your own GBrain's tools (`gbrain.agy_mcp` on) | allowed in agy's own settings | given for each request |
| Read | notes, course files, Classroom and mail copies, Documents, Downloads, Screenshots | the same |
| Write | notes folder, course files folder, your add-ons' skills | the same |
| Harmless commands | `cat cd date echo file grep head jq ls mkdir pdftotext pwd stat tail tree uniq wc which` | the same |
| Web pages | yes | yes |
| `kurooto` itself | never | never |
| Where it's kept | agy's `settings.json` (a backup is taken; your own rules stay) | nowhere: nothing is saved in Claude Code's settings |

Codex is no longer offered (0.5.6): a setting that names it is cleared.

A request that tries anything else is refused, and the answer says what was refused. To widen what agy may do, add a
rule to `permissions.allow` in `~/.gemini/antigravity-cli/settings.json` yourself; Kurooto never removes rules it
didn't write. Add-ons run as you, with your own permissions; turn on only ones you wrote or read.

## Add-ons

A Python file in the add-ons folder (`overlay.path`, shown in Settings → Add-ons) that defines a `Module` subclass is loaded
when Kurooto starts, once "Your add-ons" is on. It gets the same settings, features and dashboard cell as a built-in
feature. Add-ons are yours: they aren't part of updates and aren't published.

Add-ons by link (`kurooto addons add <git url>`, Features → Add-ons by link) come from someone else's repository at a
pinned commit, after you've read their card; `addons.on` turns them all off. Their settings are listed in each one's
README, and appear in Settings once their feature is on. Official add-ons (`kurooto addons official`) are add-ons by
link from Kurooto's own list, each at the commit it pins; `addons.official_updates` says when a newer one comes.

## Every setting
"""


def comments(src: str) -> dict[int, str]:
    out = {}
    for no, line in enumerate(src.splitlines(), 1):
        if "#" in line:
            code, _, c = line.partition("#")
            if code.strip() and code.count('"') % 2 == 0:  # a comment after code, not a # inside a string
                out[no] = c.strip()
    return out


def flatten(node: ast.Dict, prefix: str, cm: dict[int, str], out: list) -> None:
    for k, v in zip(node.keys, node.values, strict=False):
        if not isinstance(k, ast.Constant) or not isinstance(k.value, str):
            continue
        name = f"{prefix}.{k.value}"
        if isinstance(v, ast.Dict) and v.keys and all(isinstance(x, ast.Constant) for x in v.keys):
            if cm.get(k.lineno, "") or len(v.keys) <= 40:
                flatten(v, name, cm, out)
                continue
        try:
            value = ast.literal_eval(v)
        except (ValueError, SyntaxError):
            value = "(computed)"
        out.append((name, value, cm.get(k.lineno) or cm.get(getattr(v, "end_lineno", k.lineno), "")))


def collect() -> list[tuple[str, object, str]]:
    found: dict[str, tuple[object, str]] = {}
    for f in sorted(SRC.rglob("*.py")):
        src = f.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        cm = comments(src)
        rows: list = []
        for n in ast.walk(tree):
            if (
                isinstance(n, ast.Call)
                and getattr(n.func, "id", getattr(n.func, "attr", "")) == "register_defaults"
                and len(n.args) == 2
                and isinstance(n.args[0], ast.Constant)
                and isinstance(n.args[1], ast.Dict)
            ):
                flatten(n.args[1], n.args[0].value, cm, rows)
        for name, value, why in rows:
            found.setdefault(name, (value, why))
    return sorted((k, *v) for k, v in found.items())


def show(v: object) -> str:
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else json.dumps(v)
    return (s if len(s) <= 60 else s[:57] + "…").replace("|", "\\|")


def render() -> str:
    rows = collect()
    out = [INTRO]
    section = ""
    for name, value, why in rows:
        top = name.split(".")[0]
        if top != section:
            section = top
            out += ["", f"### `{top}`", "", "| Setting | Default | What it does |", "|---|---|---|"]
        why = why or NOTES.get(name, "")
        out.append(f"| `{name}` | `{show(value)}` | {why.replace('|', '\\|')} |")
    return "\n".join(out) + "\n"


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print("docs/SETTINGS_GUIDE.md is out of date: python tools/gen_settings_guide.py", file=sys.stderr)
            return 1
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {text.count('| `')} settings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
