"""/fixme: what isn't working and what to do about it, found by rules, so it answers when the AI is what broke.

It runs doctor's checks (diagnostics.checks) and the health checks (core/health.py), and matches each failing one,
by rules, to:
    the troubleshooting page's rows: data/troubleshooting.md, a copy of docs/wiki/user/troubleshooting.md that a test
        keeps equal; by the check's id (ROWS), else (with no advice of its own) by the words of its line;
    known issues: data/known_issues.json, inside the signed release (and the list of a newer version that's already
        downloaded and checked, waiting to install); by version, check id, a pattern or keywords. A version its
        maintainer withdrew (the signed yank list) says so too.
A check with a fix (health's FIXES) gets its Fix button (health:<id>:fix); where nothing can be tapped (a terminal),
`/fixme fix <id>` runs it. /fixme <words> ("/fixme the phone doesn't ring") matches the words against the rows too.
/fixme now asks online services as well (like /health now); `kurooto fixme` always does.

Your AI only explains, and only after: /fixme ai (or Ask my AI under the answer) sends the last answer to it, with
what Kurooto is running (core/selfdoc.py: no contents, no secrets), offered only when it looks like it works. The
rule-based answer never waits for it. State: state/fixme.json (the last answer, for /fixme ai). Events: fixme.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from importlib import resources
from typing import TYPE_CHECKING

from kurooto import __version__
from kurooto.core.state import jload, jsave
from kurooto.update.updater import vtuple

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.core.health import Result
    from kurooto.modules.base import Incoming

FILE = "fixme.json"
TAPS = ("telegram", "app")  # channels where a button comes back; elsewhere the answer says what to send instead
# a check's id -> the troubleshooting rows that are about it (a piece of their "What you see" cell; a test checks each
# names one row). Checks not listed here are matched by the words of their line.
ROWS = {
    "telegram": ("The bot doesn't answer", "That token was revoked"),
    "google": ("Google: sign-in expired", "Kurooto asks you to sign in to Google every week"),
    "notes_sync": ("Notes sync refuses the repository",),
    "calls": ("Not connected to your call line", "Your call line couldn't be updated"),
    "alarm": ("Your alarm … might not ring",),
    "backups": ("the backup folder isn't there", "not enough room in the backup folder"),
    "gbrain": ("The nightly upkeep didn't finish",),
    "ai": ("The AI test fails on the setup page", "isn't signed in any more"),
    "space": ("A low-disk warning",),
    "layout": ("Notes appear in the wrong folders", "Photos and PDFs still land in my notes"),
    "addons": ("Your add-ons: a problem in",),
}
DOCTOR = {  # doctor's row names -> check ids (features' rows go by their title)
    "free space": "space",
    "notes layout": "layout",
    "Telegram bot": "telegram",
    "time zone": "timezone",
    "skills in agents": "agents",
}
STOP = frozenset(
    "a an and are as at be but by can cant could did didn do does doesn don for from get got has have how i if in is "
    "isn it its just keep keeps me my no not of on or so that the then this to was wasn what when where why will with "
    "won t s kurooto".split()
)
SAME = {"rang": "ring", "rung": "ring", "texts": "message", "msg": "message"}  # words that mean the same here
MAX = 3800  # Telegram takes 4096 characters


@dataclass
class Row:
    section: str
    seen: str  # the "What you see" cell
    do: str  # the "What to do" cell


@dataclass
class Problem:
    id: str  # a check id ("calls"), or doctor's row name
    title: str
    detail: str
    help: str = ""
    result: Result | None = None  # a health check's result (it may have a Fix)
    rows: list[Row] = field(default_factory=list)


# ------------------------------------------------------------------------------------------- the rows
def plain(md: str) -> str:
    """A Markdown cell as plain text: no bold, code marks or link targets."""
    md = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", md)
    return md.replace("**", "").replace("`", "").strip()


def rows(text: str | None = None) -> list[Row]:
    """The troubleshooting page's table rows, in order."""
    if text is None:
        text = resources.files("kurooto.data").joinpath("troubleshooting.md").read_text(encoding="utf-8")
    out, section = [], ""
    for ln in text.splitlines():
        if ln.startswith("## "):
            section = ln[3:].strip()
        elif ln.startswith("| ") and section and not ln.startswith(("| What you see", "|---")):
            cells = ln.strip().strip("|").split(" | ")
            if len(cells) == 2:
                out.append(Row(section, plain(cells[0]), plain(cells[1])))
    return out


def words(text: str) -> set[str]:
    """The words that matter, roughly stemmed ("rings", "ringing", "rang": ring)."""
    out = set()
    for w in re.findall(r"[a-z0-9]+", text.lower().replace("’", "'")):
        if w in STOP or len(w) < 2:
            continue
        w = SAME.get(w, w)
        for end in ("ing", "ed", "s"):
            if w.endswith(end) and len(w) - len(end) >= 3:
                w = w[: -len(end)]
                break
        out.add(w[:-1] if w.endswith("e") and len(w) > 3 else w)
    return out


def find(text: str, table: list[Row], n: int = 3, least: int = 1) -> list[Row]:
    """The rows whose "What you see" shares the most words with text (at least `least` of them); the section and
    "What to do" count a little."""
    q = words(text)
    if not q:
        return []
    scored = []
    for i, r in enumerate(table):
        hit = q & words(r.seen)
        if len(hit) < least:
            continue
        score = 2 * len(hit) + len(q & words(r.section)) + 0.5 * len(q & words(r.do))
        scored.append((-score, i, r))
    scored.sort()
    if not scored:
        return []
    best = -scored[0][0]
    return [r for s, _, r in scored if -s >= max(2, best * 0.6)][:n]


def for_check(cid: str, table: list[Row]) -> list[Row]:
    return [r for piece in ROWS.get(cid, ()) for r in table if piece.lower() in r.seen.lower()][:2]


# ---------------------------------------------------------------------------------------- known issues
def affected(spec: str, version: str | None = None) -> bool:
    """Does a known issue's versions ("<0.5.11", ">=0.5.14,<0.5.16", "0.5.14", "*") take in this version?"""
    spec = str(spec or "*").strip()
    if spec == "*":
        return True
    v = vtuple(version or __version__)
    for part in spec.split(","):
        m = re.fullmatch(r"\s*(<=|>=|<|>|==)?\s*([0-9][\w.+-]*)\s*", part)
        if not m:
            return False
        ref = vtuple(m[2])
        ok = {"<": v < ref, "<=": v <= ref, ">": v > ref, ">=": v >= ref, "==": v == ref}[m[1] or "=="]
        if not ok:
            return False
    return True


def _load(f) -> list[dict]:
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [i for i in (doc.get("issues") if isinstance(doc, dict) else None) or [] if isinstance(i, dict)]


def issues(app: App | None) -> list[dict]:
    """The known issues for this version: the shipped list, a newer downloaded version's (it knows more), and a
    withdrawn version's reason."""
    out = [dict(i, src="") for i in _load(resources.files("kurooto.data").joinpath("known_issues.json"))]
    if app is not None:
        ready = str((jload(app.paths.state / "update-ready.json", None) or {}).get("version") or "")
        if ready and vtuple(ready) > vtuple(__version__):  # unpacked from its signed tarball (update/updater.py)
            f = app.paths.app / "versions" / ready / "src" / "src" / "kurooto" / "data" / "known_issues.json"
            have = {i.get("id") for i in out}
            out += [dict(i, src=ready) for i in _load(f) if i.get("id") not in have]
        try:
            why = app.updates.u.yanked(False).get(__version__)
        except Exception:
            why = None
        if why:
            seen = f"{__version__} was withdrawn by its maintainer"
            out.append(
                {"id": "withdrawn", "seen": seen, "fix": f"{why}. Update to a newer version.", "action": "update"}
            )
    return [i for i in out if affected(i.get("versions", "*")) and i.get("fix")]


def hits(issue: dict, ids: set[str], lines: list[str], text: str) -> bool:
    """Does a known issue explain one of these failing checks, or what you typed?"""
    checks, pat, kws = set(issue.get("checks") or []), str(issue.get("symptom") or ""), issue.get("keywords") or []
    if not (checks or pat or kws):  # about everyone on those versions
        return True
    if checks & ids:
        return True
    if pat:
        try:
            rx = re.compile(pat, re.I)
        except re.error:
            rx = None
        if rx is not None and any(rx.search(s) for s in [*lines, text] if s):
            return True
    q = words(text)
    return bool(q) and any(words(str(k)) and words(str(k)) <= q for k in kws)


# --------------------------------------------------------------------------------------------- the checks
def _doctor_id(app: App, name: str) -> str:
    if name.startswith("AI"):
        return "ai"
    titles = {m.title: m.id for m in app.modules.values()}
    if name in titles:
        return titles[name]
    if name in DOCTOR:
        return DOCTOR[name]
    if name.endswith(" folder"):
        return "folders"
    return "addons" if ": " in name else name


def problems(app: App, net: bool) -> list[Problem]:
    """What fails now: the health checks (with their fixes) first, then doctor's other rows."""
    from kurooto import diagnostics

    out: list[Problem] = []
    try:
        for r in app.health.evaluate(net=net, save=False):
            if r.ok is False:
                out.append(Problem(r.id, r.title, r.detail, r.help, r))
    except Exception as e:
        out.append(Problem("health", "Health checks", f"they failed: {type(e).__name__}: {e}"[:200]))
    try:
        rows_ = diagnostics.checks(app, health=False, net=net)
    except Exception as e:
        rows_ = [("doctor", False, f"its checks failed: {type(e).__name__}: {e}"[:200])]
    have = {p.id for p in out}
    for name, ok, detail in rows_:
        cid = _doctor_id(app, name)
        if ok is False and cid not in have:
            have.add(cid)
            out.append(Problem(cid, name, str(detail)))
    return out


def ai_works(app: App) -> tuple[bool, str]:
    """Does your AI look like it works (picked, there, its last request didn't fail)? Nothing is asked of it."""
    from kurooto import providers

    main = app.settings.get("brain.main")
    if not main:
        return False, "no AI is picked"
    b = providers.build(app, main)
    ok, why = b.available() if b else (False, "it's unknown")
    if not ok:
        return False, why
    done = [j for j in app.jobs.recent(5) if j.status in ("ok", "failed")]
    if done and done[0].status == "failed":
        return False, "its last request failed"
    return True, ""


# ------------------------------------------------------------------------------------------- the answer
def answer(app: App, text: str = "", how: str = "taps", net: bool = False) -> tuple[str, list | None]:
    """The rule-based answer, and its buttons. how: "taps" (buttons), "chat" (a terminal: say what to send) or "cli"
    (`kurooto fixme`: say what to run)."""
    from kurooto.core.health import Health
    from kurooto.update.updater import PAGES

    table = rows()
    text = text.strip()
    probs = problems(app, net)
    for p in probs:  # a check not in ROWS, with no advice of its own: rows that share its name and more
        p.rows = for_check(p.id, table) or [
            r
            for r in ([] if p.help else find(f"{p.title} {p.detail}", table, n=2, least=2))
            if words(p.title) & words(r.seen)
        ]
    ids, lines = {p.id for p in probs}, [f"{p.title}: {p.detail}" for p in probs]
    known = [i for i in issues(app) if hits(i, ids, lines, text)]
    said = find(text, table) if text else []
    out: list[str] = []
    if text:
        if said:
            out.append(f'About "{text[:80]}", the troubleshooting page says:')
            out += [f"- {r.seen}: {r.do}" for r in said]
        else:
            out.append(f'Nothing on the troubleshooting page matches "{text[:80]}".')
        out.append("")
    if probs:
        n = len(probs)
        out.append(f"{'Also not' if text else 'Not'} working now ({n} thing{'s' if n != 1 else ''}), matched by rules:")
        for p in probs[:8]:
            out.append(f"- {p.title}: {p.detail.rstrip('.')}")
            if p.help:
                out.append(f"  Try: {p.help}")
            out += [f"  Page, {r.seen}: {r.do}" for r in p.rows if r.do != p.help]
            label = p.result.fix_label if p.result else ""
            if label:
                fix = {"taps": "the button below", "chat": f"/fixme fix {p.id}", "cli": f"kurooto doctor --fix {p.id}"}
                out.append(f"  Fix ({label.lower()}): {fix[how]}")
    elif not text:
        out.append(f"Everything {app.name} checks is working. Say what you see: /fixme the phone doesn't ring")
    for i in known:
        where = f" (from {i['src']}'s list, downloaded)" if i.get("src") else ""
        seen = f"{i['seen']}. " if i.get("seen") else ""
        out.append(f"Known issue in {__version__}{where}: {seen}{i['fix']}")
        if i.get("action") == "update" and (how != "taps" or not app.updates.u.managed()):
            out.append("  kurooto update installs the newer version.")
    out += ["", f"Troubleshooting page: {PAGES}/wiki/user/troubleshooting.html"]
    buttons = Health._buttons([p.result for p in probs if p.result is not None]) or []
    if how == "taps":
        for i in known:
            act = str(i.get("action") or "")
            if (
                act.startswith("fix:")
                and act[4:] in ids
                and not any(b[0][1] == f"health:{act[4:]}:fix" for b in buttons)
            ):
                buttons.append([("Fix it", f"health:{act[4:]}:fix")])
            elif act == "update" and app.updates.u.managed() and [("Update", "upd:latest:now")] not in buttons:
                buttons.append([("Update", "upd:latest:now")])
    worth = bool(probs or said or known)
    if worth and how != "cli":
        ok, why = ai_works(app)
        if ok:
            out.append("Your AI can explain this: " + ("Ask my AI below." if how == "taps" else "/fixme ai."))
            if how == "taps":
                buttons.append([("Ask my AI", "fixme:last:ai")])
    body = "\n".join(out).strip()
    if len(body) > MAX:
        body = body[: MAX - 1] + "…"
    jsave(app.paths.state / FILE, {"at": time.time(), "text": text[:300], "answer": body, "problems": len(probs)})
    app.events.emit("fixme", problems=len(probs), rows=len(said), issues=len(known), words=bool(text))
    return body, (buttons[:6] or None)


def explain(app: App, msg: Incoming | None = None) -> str:
    """Your AI explains the last /fixme answer, if it looks like it works (a request like any other)."""
    last = jload(app.paths.state / FILE, {}) or {}
    if not last.get("answer"):
        return "Send /fixme first; your AI then explains what it found."
    ok, why = ai_works(app)
    if not ok:
        return f"Your AI doesn't look like it works right now ({why}), so the rules' answer is all there is."
    asked = f' They said: "{last["text"]}".' if last.get("text") else ""
    from kurooto.core import selfdoc  # what this Kurooto is running (no contents, no secrets: core/selfdoc.py)

    running = selfdoc.refresh(app)[: selfdoc.CONTEXT_MAX]
    prompt = (
        f"{app.name}'s /fixme found the following by fixed rules, without an AI.{asked} Explain in a few plain "
        "sentences what is most likely wrong and which step to take first. Don't run commands or change settings; "
        f"say if the rules' answer looks wrong.\n\n{last['answer']}\n\nWhat {app.name} is running on this computer "
        f"(use it to check the rules' answer):\n{running}"
    )
    terminal = msg is not None and msg.via not in TAPS
    reply = None if msg is None or terminal else msg.message_id
    jid = app.jobs.submit(prompt, title="Explain /fixme", effort="low", text_only=True, reply_to=reply, quiet=terminal)
    if msg is not None:
        msg.job = jid  # a terminal shows the answer when it comes
    return "Asked your AI; its explanation comes when it's ready."


def command(app: App, msg: Incoming, arg: str) -> tuple[str, list | None]:
    """/fixme [words], /fixme now, /fixme ai, /fixme fix <id>."""
    arg = arg.strip()
    low = arg.lower()
    if low == "ai":
        return explain(app, msg), None
    head, _, rest = low.partition(" ")
    if head == "fix" and rest.strip() in {c.id for c in app.health.checks()}:
        return app.health.fix(rest.strip())[1], None
    net = low in ("now", "all")
    return answer(app, "" if net else arg, "taps" if msg.via in TAPS else "chat", net=net)


def button(app: App, ref: str, act: str) -> str:
    if act != "ai":
        return "unknown button"
    return explain(app)


def cli(text: str = "") -> int:
    """`kurooto fixme [words]`: the same answer in a terminal, asking online services too; works with Kurooto stopped.
    The exit code is the number of problems."""
    try:
        from kurooto.app import App

        app = App()
    except Exception as e:  # Kurooto itself can't start: the page's rows still help
        print(f"Kurooto itself can't start: {type(e).__name__}: {e}"[:400])
        for r in find(text, rows()) if text else []:
            print(f"- {r.seen}: {r.do}")
        print("kurooto doctor shows the basics.")
        return 1
    try:
        print(answer(app, text, "cli", net=True)[0])
        return int((jload(app.paths.state / FILE, {}) or {}).get("problems") or 0)
    finally:
        app.close()
