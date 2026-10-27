#!/usr/bin/env python3
"""Write the settings guide: every setting Kurooto has, read from the code itself (every register_defaults call, which
is how a module declares its settings), explained from the guide's own source, so it can't drift from the program.
Run it after changing a setting: python tools/gen_settings_guide.py [--check]

The source is tools/settings_guide/*.toml, one file per feature group (0.8.10). Each file has the group's title, its
intro, the wiki page that covers it and what its settings cost and depend on, then one table per setting:

    [s."brain.main"]
    tip = "..."     # the tooltip: one line, written for a person (required)
    what = "..."    # more on what it does, when the tip isn't enough
    values = "..."  # what it can be set to (else worked out from the default and core/choices.py)
    when = "..."    # when you'd change it, and what changes when you do (required)
    cost = "..."    # what it costs or sends outward (else the group's)
    needs = "..."   # what it depends on, or switches off with it (else the group's)
    default = "..." # the default in words, where the code computes it

`[parent."availability.night"] tip = "..."` explains a group of settings the dashboard shows as one box.
Settings of the phone app itself are `app.<its key>` (no register_defaults: their default is given). A setting
another branch adds can be written ahead with `pending = "<why>"`: it is left out until the setting exists.

It writes:
    docs/wiki/user/settings-guide.md      the guide (the user wiki, and so the site), grouped, every entry
    docs/SETTINGS_GUIDE.md                every setting in one table, linked to its guide entry
    src/kurooto/data/settings-help.json   {"section.key": tooltip} for the dashboard (web/api.py)
    android/assets/settings-help.json     every entry in full, for the app's long-press (SettingHelp.kt)
    src/kurooto/web/static/settings-guide.js  the same as a script, for the dashboard's Settings page (home.js)

--check exits 1 when a file is out of date, or a setting has no entry (CI and the tests run it)."""

# ruff: noqa: E501
from __future__ import annotations

import ast
import functools
import json
import re
import sys
import textwrap
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "kurooto"
OUT = ROOT / "docs" / "SETTINGS_GUIDE.md"
GUIDE_SRC = ROOT / "tools" / "settings_guide"
WIKI = ROOT / "docs" / "wiki" / "user" / "settings-guide.md"
HELP = SRC / "data" / "settings-help.json"
FULL = SRC / "web" / "static" / "settings-guide.js"  # a script: the dashboard serves .js, not .json
APP = ROOT / "android" / "assets" / "settings-help.json"
SITE = "https://avtarfr.github.io/kurooto/wiki/user/settings-guide.html"  # update/updater.py's PAGES + the page
FIELDS = ("tip", "what", "values", "when", "cost", "needs", "default", "pending")

INTRO = """# Settings guide (the table)

Every setting Kurooto has, its default and what it does, in one table. This file is written by
`tools/gen_settings_guide.py` from the code, so it is complete. Each setting's full entry (what it does, its values,
when you'd change it, what it costs or sends, what it depends on) is in the user wiki's
[Settings guide](wiki/user/settings-guide.md), grouped by feature; the link after each line goes there.

## Where settings live, and how to change one

- **The dashboard:** Settings (Alt+S), grouped by feature, with a search box: the core sections (you, notify,
  availability, updates, brain, ask, look, power, notes, files) and the features that are on. Each setting shows what
  it does under its name; click that line for its whole guide entry. Changes apply at once; most are read again the
  next time they're used. A few are read only when Kurooto starts (such as `web.port`): for those, restart it with
  `kurooto stop`, then `kurooto start`. The other core sections (such as `health` and `sources`) aren't on that page
  yet: change them in the file.
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

WIKI_INTRO = """# Settings guide

Every setting Kurooto has, one entry each: what it does, what it can be set to and its default, when you'd change it
and what changes when you do, what it costs or sends outward, and what it depends on. Grouped by feature; the
[contents](#contents) below lists the groups.

**Finding one.** On the dashboard, Settings (Alt+S) has a search box that also looks through these entries: type what
you want ("night", "calls", "battery") rather than a setting's name. Each setting there shows its one-line tip under
its name; click the tip for the whole entry. In the phone app, long-press a setting for its entry. On this page, your
browser's find (Ctrl+F) finds a name like `brain.main`.

**Changing one.** On the dashboard's Settings page (a feature's settings appear once it's on), or in `settings.json` in
Kurooto's config folder (`kurooto paths` says where), which holds only what you changed: a dotted name such as
`brain.main` is the key `main` inside `brain`, `{"brain": {"main": "agy"}}`, and deleting a line goes back to the
default. Restart Kurooto after editing the file by hand (`kurooto stop`, then `kurooto start`). A few settings are set
by Kurooto itself (pairing, the call line's address); their entries say so. Secrets (keys, tokens) are never settings:
they're in the system keyring.

**Times and schedules.** A time is 24-hour `HH:MM`. A schedule is `daily 07:30` (several times: `daily 07:00,13:00`),
`weekly sun 19:00`, `hourly`, or `every 15m` / `every 3h`.

This page is written by `tools/gen_settings_guide.py` from Kurooto's code and the guide's source
(`tools/settings_guide/`), so every setting is here; [the table](../../SETTINGS_GUIDE.md) lists them all on one page.
"""


# ------------------------------------------------------------------------------------------- the settings in the code
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
    """Every setting in the code: (name, default, the comment beside it)."""
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


# ------------------------------------------------------------------------------------------------- the guide's source
def load() -> list[dict]:
    """The groups, in their files' order: {id, file, title, intro, page, cost, needs, entries, parents}."""
    groups = []
    for f in sorted(GUIDE_SRC.glob("*.toml")):
        d = tomllib.loads(f.read_text(encoding="utf-8"))
        gid = re.sub(r"^\d+-", "", f.stem)
        for key, e in (d.get("s") or {}).items():
            bad = set(e) - set(FIELDS)
            if bad:
                raise SystemExit(f"{f.name}: {key} has fields the guide doesn't know: {sorted(bad)}")
        groups.append(
            {
                "id": gid,
                "file": f.name,
                "title": d["title"],
                "intro": " ".join(d.get("intro", "").split()),
                "page": d.get("page", ""),
                "cost": d.get("cost", ""),
                "needs": d.get("needs", ""),
                "entries": d.get("s") or {},
                "parents": d.get("parent") or {},
            }
        )
    return groups


def slug(title: str) -> str:
    """A heading's id, as the site's Markdown makes it (tools/release.py md_html) and GitHub does for these."""
    return re.sub(r"[^a-z0-9 -]", "", title.lower()).replace(" ", "-")


def anchor(key: str) -> str:
    return slug(f"`{key}`")


def _choices() -> dict:
    sys.path.insert(0, str(SRC.parent))
    try:
        from kurooto.core.choices import CHOICES
    finally:
        sys.path.pop(0)
    return CHOICES


SCHEDULE = re.compile(r"(daily|weekly|every|hourly)\b")


def auto_values(key: str, v: object, choices: dict) -> str:
    """What a setting can be set to, when its entry doesn't say: from its list of choices, else its default's kind."""
    if key in choices:
        return (
            "One of: "
            + "; ".join(f"`{c}`" if c == label else f"`{c}` ({label.split(': ', 1)[-1]})" for c, label in choices[key])
            + "."
        )
    if isinstance(v, bool):
        return "On or off."
    if isinstance(v, int):
        return "A whole number."
    if isinstance(v, float):
        return "A number."
    if isinstance(v, str) and SCHEDULE.match(v):
        return "A schedule: `daily HH:MM` (several: `daily 07:00,13:00`), `weekly sun 19:00`, `hourly` or `every 15m`."
    if isinstance(v, str) and re.fullmatch(r"\d{1,2}:\d{2}", v):
        return "A time of day, 24-hour `HH:MM`."
    if isinstance(v, list):
        return "A list, typed as JSON."
    if isinstance(v, dict):
        return "A JSON object."
    return "Text."


def say_default(v: object) -> str:
    if v is None:
        return "none"
    if v is True:
        return "on"
    if v is False:
        return "off"
    if v == "":
        return "empty"
    if v in ([], {}):
        return "none"
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return f"`{s if len(s) <= 120 else s[:117] + '…'}`"


@functools.cache
def build() -> tuple[list[dict], dict[str, dict], list[str]]:
    """(groups, every entry by key, problems). An entry: the source's fields plus its default, values, group and
    anchor, with the group's cost and needs where it has none."""
    groups, rows = load(), {k: v for k, v, _w in collect()}
    choices = _choices()
    entries: dict[str, dict] = {}
    problems: list[str] = []
    for g in groups:
        for key, e in g["entries"].items():
            if key in entries:
                problems.append(f"{key} has two entries ({entries[key]['file']} and {g['file']})")
                continue
            phone = key.startswith("app.")
            if key not in rows and not phone:
                if not e.get("pending"):
                    problems.append(
                        f"{key} ({g['file']}) isn't a setting in the code: renamed or removed? Remove or rename its entry"
                    )
                continue
            for need in ("tip", "when"):
                if not str(e.get(need, "")).strip():
                    problems.append(f"{key} ({g['file']}) has no {need}")
            if phone and "default" not in e:
                problems.append(f"{key} ({g['file']}) is the phone app's: give its default")
            v = rows.get(key)
            if phone and not e.get("values"):  # no default in the code to tell its kind: a switch, or say what it takes
                if str(e.get("default", "")).strip() in ("on", "off"):
                    v = False
                else:
                    problems.append(f"{key} ({g['file']}) is the phone app's and not a switch: give its values")
            entries[key] = {
                "g": g["id"],
                "file": g["file"],
                "tip": " ".join(str(e.get("tip", "")).split()),
                "what": " ".join(str(e.get("what", "")).split()),
                "values": " ".join(str(e.get("values") or auto_values(key, v, choices)).split()),
                "default": " ".join(str(e["default"]).split()) if "default" in e else say_default(v),
                "when": " ".join(str(e.get("when", "")).split()),
                "cost": " ".join(str(e.get("cost") or g["cost"]).split()),
                "needs": " ".join(str(e.get("needs") or g["needs"]).split()),
                "anchor": anchor(key),
            }
    for key in rows:
        if key not in entries:
            same = next((e["file"] for k, e in entries.items() if k.split(".")[0] == key.split(".")[0]), "")
            where = f"tools/settings_guide/{same}" if same else "a file in tools/settings_guide/"
            problems.append(f"{key} has no entry in the settings guide: add one to {where}")
    seen: dict[str, str] = {}
    for key, e in entries.items():
        if e["anchor"] in seen:
            problems.append(f"{key} and {seen[e['anchor']]} would share a link ({e['anchor']})")
        seen[e["anchor"]] = key
    for g in groups:
        for p in g["parents"]:
            if not any(k.startswith(p + ".") for k in entries):
                problems.append(f"{p} ({g['file']}) groups no settings")
    return groups, entries, problems


def parents(groups: list[dict], entries: dict[str, dict]) -> dict[str, dict]:
    """The settings the dashboard shows as one box (availability.night): their tip and the settings inside."""
    out = {}
    for g in groups:
        for p, d in g["parents"].items():
            kids = [k for k in entries if k.startswith(p + ".")]
            if kids:
                out[p] = {
                    "g": g["id"],
                    "tip": " ".join(str(d.get("tip", "")).split()),
                    "children": kids,
                    "anchor": entries[kids[0]]["anchor"],
                }
    return out


# ------------------------------------------------------------------------------------------------------- the outputs
def page_title(page: str) -> str:
    f = WIKI.parent / page.split("#")[0]
    if f.exists():
        m = re.search(r"(?m)^# (.+)$", f.read_text(encoding="utf-8"))
        if m:
            return re.sub(r"[`*]", "", m[1]).strip()
    return page.split("#")[0].removesuffix(".md").replace("-", " ").capitalize()


def wiki() -> str:
    groups, entries, _ = build()
    out = [WIKI_INTRO, "## Contents", ""]
    live = [(g, [k for k in g["entries"] if k in entries]) for g in groups]
    for g, keys in live:
        if keys:
            out.append(f"- [{g['title']}](#{slug(g['title'])}): {len(keys)} setting{'s' * (len(keys) != 1)}")
    for g, keys in live:
        if not keys:
            continue
        out += ["", f"## {g['title']}", ""]
        intro = g["intro"]
        if g["page"]:
            intro += f" More in [{page_title(g['page'])}]({g['page']})."
        if intro:
            out += [intro.strip(), ""]
        cost, needs = " ".join(g["cost"].split()), " ".join(g["needs"].split())
        if cost or needs:  # once for the group; an entry says its own only where it differs
            out.append("For every setting in this group, unless its entry says otherwise:")
            out += [""] + ([f"- **Costs and what leaves this computer:** {cost}"] if cost else [])
            out += [f"- **Depends on:** {needs}"] if needs else []
            out.append("")
        for key in keys:
            e = entries[key]
            out += ["", f"### `{key}`", "", e["tip"], ""]
            if e["what"]:
                out += [e["what"], ""]
            out.append(f"- **Values:** {e['values']} **Default:** {e['default']}.")
            out.append(f"- **When to change it:** {e['when']}")
            if e["cost"] and e["cost"] != cost:
                out.append(f"- **Costs and what leaves this computer:** {e['cost']}")
            if e["needs"] and e["needs"] != needs:
                out.append(f"- **Depends on:** {e['needs']}")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(wrap(x) for x in out)).rstrip() + "\n"


def wrap(line: str) -> str:
    """A paragraph or list item cut at 120 columns, as the wiki's other pages are (a list item's lines indented)."""
    if len(line) <= 120 or line.startswith(("#", "|")) or "\n" in line:
        return line
    item = line.startswith("- ")
    return textwrap.fill(
        line, 120, subsequent_indent="  " if item else "", break_long_words=False, break_on_hyphens=False
    )


def show(v: object) -> str:
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else json.dumps(v)
    return (s if len(s) <= 60 else s[:57] + "…").replace("|", "\\|")


def render() -> str:
    _, entries, _ = build()
    out = [INTRO]
    section = ""
    for name, value, _why in collect():
        top = name.split(".")[0]
        if top != section:
            section = top
            out += ["", f"### `{top}`", "", "| Setting | Default | What it does |", "|---|---|---|"]
        e = entries.get(name)
        why = f"{e['tip']} ([guide](wiki/user/settings-guide.md#{e['anchor']}))" if e else ""
        out.append(f"| `{name}` | `{show(value)}` | {why.replace('|', '\\|')} |")
    return "\n".join(out) + "\n"


def help_json() -> str:
    """Every setting's tooltip, for the dashboard: {"section.key": text}, with the boxes that hold several."""
    groups, entries, _ = build()
    rows = {k: e["tip"] for k, e in entries.items() if not k.startswith("app.")}
    rows.update({k: p["tip"] for k, p in parents(groups, entries).items() if not k.startswith("app.")})
    return json.dumps(rows, ensure_ascii=False, indent=0, sort_keys=True) + "\n"


def full_json() -> str:
    """Every entry in full, for the dashboard's Settings page and the phone app's long-press."""
    groups, entries, _ = build()
    doc = {
        "page": SITE,
        "groups": [
            {"id": g["id"], "title": g["title"], "intro": g["intro"]}
            for g in groups
            if any(k in entries for k in g["entries"])
        ],
        "settings": {k: {f: v for f, v in e.items() if f != "file" and v} for k, e in sorted(entries.items())},
        "parents": parents(groups, entries),
    }
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"


def outputs() -> dict[Path, str]:
    full = full_json()
    js = "// Written by tools/gen_settings_guide.py: every setting's guide entry, for Settings (home.js). Don't edit.\n"
    return {
        OUT: render(),
        WIKI: wiki(),
        HELP: help_json(),
        FULL: js + "window.KUROOTO_SETTINGS_GUIDE = " + full,
        APP: full,
    }


def main() -> int:
    _, entries, problems = build()
    if problems:
        print("The settings guide has problems:\n- " + "\n- ".join(problems), file=sys.stderr)
        return 1
    files = outputs()
    if "--check" in sys.argv:
        stale = [p for p, text in files.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
        if stale:
            names = ", ".join(str(p.relative_to(ROOT)) for p in stale)
            print(f"{names} out of date: python tools/gen_settings_guide.py", file=sys.stderr)
            return 1
        return 0
    for p, text in files.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    print(f"wrote the settings guide: {len(entries)} entries in {len({e['g'] for e in entries.values()})} groups")
    return 0


if __name__ == "__main__":
    sys.exit(main())
