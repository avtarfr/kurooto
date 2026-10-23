"""Proposals: every change the AI makes to your real files arrives as one, and only your tap applies it.

The AI drafts in a scratch folder of its own (core/scratch.py). When its request ends, Kurooto compares that folder with
the original and makes a proposal: a title, a few lines in plain English, the files changed and the diff. You get it
as the answer (on Telegram and in the phone app's chat a short summary, the diff in the message when it's short and as
a file when it's long; the dashboard's Proposals page shows the whole diff), with three buttons:
    Apply    writes it (a guarded tap, core/tap.py "proposal.apply"). Notes and folders: the files are written and their
             earlier versions kept, Undo puts them back. A git repository: one commit on your current branch (never a
             push; Undo is a revert commit), refused when you have uncommitted changes in the same files, or the
             repository is mid-merge or on no branch, saying which.
    Change   asks what to change, then the AI works again in the same scratch folder; the proposal comes back updated.
    Discard  deletes the scratch folder; nothing of yours changed.
A proposal that deletes files says so first. /proposals lists what's waiting. Proposals made by work nobody was waiting
for (Dreaming's fixes, at night) come in the morning message (through Calm), not one by one.

Who makes them: Help with your project (modules/projects.py), a change to your notes you asked for ("tidy my LA notes'
headings": notes_request() below), edit_note in any AI request (proposals.notes_edits: the change to text that's
already there becomes a proposal instead of being made), and Dreaming's fixes to skills (core/tuning.py).

Settings (proposals.*): keep_days, max_kb, max_files, notes_edits, inline_lines, morning.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kurooto.core import scratch
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "proposals",
    {
        "keep_days": 7,  # a proposal nobody answered goes after this many days, with its scratch folder
        "max_kb": 400,  # a bigger change isn't proposed (ask for a smaller part)
        "max_files": 60,  # nor one that touches more files than this
        "notes_edits": True,  # a change to text already in your notes becomes a proposal (Apply / Change / Discard)
        "inline_lines": 30,  # a diff up to this many lines comes inside the message; a longer one as a file
        "morning": "daily 07:30",  # the night's proposals, told then when Dreaming is off (else in Dreaming's message)
    },
)

OPEN = ("waiting", "changing")
BUTTONS = lambda pid: [[("Apply", f"prop:{pid}:apply"), ("Change", f"prop:{pid}:change"),  # noqa: E731
                        ("Discard", f"prop:{pid}:discard")]]  # fmt: skip
HOOK = "proposals.change"  # app.ask.hooks: what you said to change
THEN = "proposal.make"  # app.jobs.then_actions: a scratch request ended
# special Apply / Undo for a kind of proposal (a skill Dreaming rewrote goes through Learning, with your test cases)
APPLY: dict[str, Callable] = {}  # name -> fn(app, p, sc) -> (ok, message, undo info)
UNDO: dict[str, Callable] = {}  # name -> fn(app, p) -> (ok, message)
NOTES_ASK = re.compile(
    r"(?i)^(?:please\s+|can you\s+|could you\s+)?(?:tidy|clean\s*up|fix|reorgani[sz]e|restructure|rewrite|reword|"
    r"rename|proofread|correct|format|reformat|shorten|split|merge|add\s+(?:an?\s+|the\s+)?(?:summary|summaries|"
    r"headings?|footnotes?|links?|tags?|front\s*matter|table of contents|toc))\b.*\b(?:my|the|this|these|that)\s+"
    r"(?:[\w'’-]+\s+){0,4}?(?:notes?|lecture\s+notes?|class\s+notes?)\b"
)


# ------------------------------------------------------------------------------------------------- storage
def home(app: App) -> Path:
    return app.paths.state / "proposals"


def _file(app: App, pid: str) -> Path:
    return home(app) / f"{pid}.json"


def get(app: App, pid: str | None) -> dict | None:
    if not pid or not re.fullmatch(r"p[0-9a-f]{8}", str(pid)):
        return None
    p = jload(_file(app, pid), None)
    return p if isinstance(p, dict) else None


def save(app: App, p: dict) -> None:
    p["updated"] = time.time()
    jsave(_file(app, p["id"]), p)


def every(app: App) -> list[dict]:
    d = home(app)
    out = [jload(f, None) for f in sorted(d.glob("p*.json"))] if d.is_dir() else []
    return sorted([p for p in out if isinstance(p, dict)], key=lambda p: -float(p.get("created") or 0))


def waiting(app: App) -> list[dict]:
    return [p for p in every(app) if p.get("status") in OPEN]


def diff_text(app: App, p: dict) -> str:
    f = home(app) / f"{p['id']}.diff"
    try:
        return f.read_text(encoding="utf-8")
    except OSError:
        return ""


def find(app: App, ref: str) -> dict | None:
    """A proposal by its id, or by its number in /proposals (1 = the newest waiting)."""
    ref = str(ref or "").strip()
    if ref.isdigit():
        w = waiting(app)
        return w[int(ref) - 1] if 0 < int(ref) <= len(w) else None
    return get(app, ref)


# ------------------------------------------------------------------------------------------------ making one
def submit(
    app: App,
    sc: scratch.Scratch,
    prompt: str,
    title: str,
    reply_to=None,
    background: bool = False,
    source: str = "project",
    pid: str | None = None,
    request: str = "",
    effort: str = "auto",
) -> str:
    """An AI request that works in this scratch folder; when it ends, a proposal (or, with pid, that one updated)."""
    payload = {"sid": sc.id, "source": source, "pid": pid, "request": (request or prompt)[:2000]}
    jid = app.jobs.submit(
        prompt,
        title=title,
        effort=effort,
        reply_to=reply_to,
        quiet=True,  # its answer comes as the proposal (or says why there isn't one)
        then=THEN,
        then_payload=payload,
        background=background,
        why="proposals.night" if background else None,
        scratch=sc.id,
    )
    scratch.attach(app, sc, jid)
    return jid


def job_done(app: App, job, result, payload: dict) -> None:
    """A scratch request ended: its proposal, or a line saying why there isn't one."""
    sc = scratch.get(app, payload.get("sid"))
    reply_to = job.reply_to
    if sc is None:
        return
    p = get(app, payload.get("pid"))
    if not result.ok:
        if p is not None:  # a Change that failed: the proposal as it was is still there
            p["status"] = "waiting"
            save(app, p)
        if job.lane == "you":  # your request failed: said as any failed answer is; the night's only in the log
            app.jobs._deliver(job, result, None)
        app.events.emit("proposal_job_failed", job=job.id, verdict=result.verdict.value)
        if p is None:
            scratch.remove(app, sc)
        return
    title, summary = split_answer(result.text, job.title)
    made, msg = make(
        app,
        sc,
        title,
        summary,
        request=str(payload.get("request") or job.prompt),
        source=str(payload.get("source") or "project"),
        job=job.id,
        night=job.lane != "you",
        existing=p,
        brain=job.brain or "",
    )
    if made is None:
        app.notify(msg, kind="result", reply_to=_reply(reply_to), why="asked")
        return
    if not made.get("night"):
        tell(app, made, reply_to=_reply(reply_to))


def watch(app: App, job, result, info: dict) -> None:
    """Every finished request (app.jobs.watchers): a change edit_note made in an ordinary request (a lazy scratch
    folder) becomes a proposal now."""
    sc = scratch.for_job(app, job.id)
    if sc is None or not sc.lazy:
        return
    said = "\n".join(ln.strip() for ln in str(result.text or "").splitlines() if ln.strip())[:600]
    made, msg = make(
        app,
        sc,
        f"Changes to your notes: {job.title}"[:80],
        said or "From your request; the change waits for your OK.",
        request=job.prompt,
        source="notes",
        job=job.id,
        night=job.lane != "you",
        brain=job.brain or "",
    )
    if made is None:
        if "No changes" not in msg:
            app.notify(msg, kind="result", reply_to=_reply(job.reply_to), why="asked")
        return
    if not made.get("night"):
        tell(app, made, reply_to=_reply(job.reply_to))


def _reply(ref):
    return int(ref) if isinstance(ref, str) and ref.isdigit() else ref


def split_answer(text: str, fallback: str) -> tuple[str, str]:
    """The AI's answer as (title, summary): its first line, then a few lines."""
    lines = [ln.strip() for ln in str(text or "").strip().splitlines() if ln.strip()]
    if not lines:
        return fallback[:80], ""
    title = re.sub(r"^(?:#+\s*|title:\s*|\*\*)", "", lines[0], flags=re.I).strip("* ")[:80] or fallback[:80]
    summary = "\n".join(lines[1:7])[:900]
    return title, summary


def make(
    app: App,
    sc: scratch.Scratch,
    title: str,
    summary: str,
    request: str = "",
    source: str = "project",
    job: str | None = None,
    night: bool = False,
    existing: dict | None = None,
    apply_hook: str = "",
    meta: dict | None = None,
    brain: str = "",
) -> tuple[dict | None, str]:
    """The proposal for what's in this scratch folder (or `existing` updated): (proposal, "") or (None, why not)."""
    s = app.settings
    try:
        ch = scratch.changes(app, sc)
    except Exception as e:
        app.events.emit("proposal_failed", error=f"{type(e).__name__}: {e}"[:200])
        if existing is None:
            scratch.remove(app, sc)
        return None, f"I couldn't compare the changes with the original ({type(e).__name__}); nothing changed."
    if not ch.files:
        if existing is not None:
            existing["status"] = "waiting"
            save(app, existing)
            return None, f"No changes this time; the proposal stays as it was. {summary}".strip()
        scratch.remove(app, sc)
        return None, f"No changes proposed: {title}. {summary}".strip()
    max_kb, max_files = int(s.get("proposals.max_kb") or 400), int(s.get("proposals.max_files") or 60)
    if ch.size > max_kb * 1024 or len(ch.files) > max_files:
        if existing is None:
            scratch.remove(app, sc)
        else:
            existing["status"] = "waiting"
            save(app, existing)
        return None, (
            f"That change is too big to propose ({len(ch.files)} files, {ch.size // 1024} KB; the limit is "
            f"{max_files} files and {max_kb} KB): ask for a smaller part. Nothing changed."
        )
    checks = None
    if sc.checks:
        checks = scratch.run_checks(app, sc, float(s.get("projects.check_timeout_s") or 300))
    p = existing or {"id": "p" + uuid.uuid4().hex[:8], "created": time.time(), "rev": 0, "told": False}
    p.update(
        {
            "sid": sc.id,
            "title": title[:80],
            "summary": summary,
            "request": request[:2000],
            "source": source,
            "label": sc.label,
            "project": sc.project,
            "origin": sc.origin,
            "kind": sc.kind,
            "files": [c.__dict__ for c in ch.files],
            "deletes": ch.deletes,
            "dropped": ch.dropped[:20],
            "blocked": list(sc.blocked),
            "outside": list(sc.outside),
            "checks": checks,
            "status": "waiting",
            "job": job,
            "brain": brain,
            "night": bool(night),
            "rev": int(p.get("rev") or 0) + (1 if existing else 0),
            "apply_hook": apply_hook or p.get("apply_hook") or "",
            "meta": {**(p.get("meta") or {}), **(meta or {})},
            "size": ch.size,
        }
    )
    if existing is not None:
        p["told"] = False
    home(app).mkdir(parents=True, exist_ok=True)
    (home(app) / f"{p['id']}.diff").write_text(ch.patch, encoding="utf-8")
    save(app, p)
    app.events.emit("proposal_made", id=p["id"], files=len(ch.files), deletes=len(ch.deletes), source=source,
                    night=bool(night), rev=p["rev"])  # fmt: skip
    return p, ""


# ------------------------------------------------------------------------------------------------- telling
def counts(c: dict) -> str:
    if c.get("status") == "deleted":
        return "deleted"
    if c.get("binary"):
        return "binary" if c.get("status") != "added" else "new, binary"
    bits = f"+{c.get('added', 0)} −{c.get('removed', 0)}"
    return f"new, {bits}" if c.get("status") == "added" else bits


def text(app: App, p: dict, with_diff: bool = True) -> tuple[str, Path | None]:
    """The proposal as a message: (text, the diff file when it's too long to show)."""
    head = f"Proposal for {p.get('label') or 'your files'}: {p['title']}"
    if p.get("rev"):
        head += f" (changed, version {p['rev'] + 1})"
    lines = [head]
    if p.get("deletes"):
        n = len(p["deletes"])
        lines.append(f"It deletes {n} file{'s' if n != 1 else ''}: {', '.join(p['deletes'][:8])}.")
    if p.get("summary"):
        lines.append(p["summary"])
    files = p.get("files") or []
    lines.append(
        f"Files ({len(files)}): "
        + "; ".join(f"{c['path']} ({counts(c)})" for c in files[:12])
        + (f"; and {len(files) - 12} more" if len(files) > 12 else "")
    )
    ck = p.get("checks")
    if ck:
        lines.append(
            ("Checks passed" if ck.get("ok") else f"Checks failed ({ck.get('why') or 'exit ' + str(ck.get('code'))})")
            + (f" in {ck.get('seconds')} s." if ck.get("ran") else f": didn't run ({ck.get('why')}).")
            if ck.get("ran") or ck.get("why")
            else ""
        )
    if p.get("blocked"):
        lines.append(f"Refused while it worked (outside its scratch folder): {', '.join(p['blocked'][:5])}.")
    if p.get("outside"):
        lines.append(
            "Changed in the original while it worked (by you, a sync, or the AI writing where it shouldn't; "
            f"not part of this proposal): {', '.join(p['outside'][:6])}."
        )
    if p.get("kind") == "git":
        lines.append("Apply makes one commit on your current branch (never a push); Undo reverts it.")
    else:
        lines.append("Apply writes these files; the earlier versions are kept, and Undo puts them back.")
    diff = diff_text(app, p)
    attach = None
    limit = int(app.settings.get("proposals.inline_lines") or 30)
    if with_diff and diff:
        if diff.count("\n") <= limit and len(diff) < 3000:
            lines.append("\n" + diff.rstrip())
        else:
            attach = home(app) / f"{p['id']}.diff"
            lines.append("The diff is attached; the dashboard's Proposals page shows it in full.")
    return "\n".join(x for x in lines if x), attach


def tell(app: App, p: dict, reply_to=None, why: str = "asked") -> None:
    body, attach = text(app, p)
    app.notify(body, kind="result", reply_to=reply_to, buttons=BUTTONS(p["id"]), why=why)
    if attach is not None:
        app.notify(f"{p['title']} (diff)", kind="result", file=str(attach), reply_to=reply_to, why=why)
    p["told"] = True
    save(app, p)


def morning_lines(app: App, send: bool = True, skip: set | None = None) -> tuple[list[str], list]:
    """Proposals made at night, for the morning message: one line each, with their buttons (sent: marked told).
    skip: ones said in their own line already (Dreaming's fix for a skill)."""
    lines, buttons = [], []
    for p in reversed(waiting(app)):
        if not p.get("night") or p.get("told") or p["id"] in (skip or set()):
            continue
        n = len(p.get("files") or [])
        dels = f"; it deletes {len(p['deletes'])}" if p.get("deletes") else ""
        lines.append(f"Proposed for {p.get('label')}: {p['title']} ({n} file{'s' if n != 1 else ''}{dels}; "
                     f"/proposals {p['id']} shows it).")  # fmt: skip
        buttons += BUTTONS(p["id"])
        if send:
            p["told"] = True
            save(app, p)
    return lines, buttons


def morning(app: App, payload: dict | None = None) -> str:
    """With Dreaming off: the night's proposals in a message of their own (Calm decides when it reaches you)."""
    if app.is_on("dreaming"):
        return "in Dreaming's message"
    lines, buttons = morning_lines(app, send=True)
    if not lines:
        return "none"
    app.notify("Waiting for your OK:\n" + "\n".join(f"- {x}" for x in lines), kind="result",
               why="proposals.morning", buttons=buttons, title="Proposals")  # fmt: skip
    return f"{len(lines)} told"


# ------------------------------------------------------------------------------------------------- Apply
def apply(app: App, pid: str, via: str = "button") -> str:
    """Apply a waiting proposal (only from your tap: core/tap.py "proposal.apply")."""
    p = get(app, pid)
    if p is None:
        return "No such proposal."
    if p.get("status") != "waiting":
        said = {
            "applied": "That's applied already.",
            "discarded": "That was discarded.",
            "changing": "That's being changed; wait for the new version.",
            "undone": "That was applied and undone.",
        }
        return said.get(p.get("status"), "That proposal isn't waiting any more.")  # fmt: skip
    sc = scratch.get(app, p.get("sid"))
    if sc is None:
        p["status"] = "expired"
        save(app, p)
        return "Its scratch folder is gone (it waited too long), so there's nothing to apply."
    hook = APPLY.get(p.get("apply_hook") or "")
    try:
        ok, msg, undo = (
            hook(app, p, sc) if hook else _apply_git(app, p, sc) if sc.kind == "git" else _apply_files(app, p, sc)
        )
    except Exception as e:
        app.events.emit("proposal_apply_failed", id=pid, error=f"{type(e).__name__}: {e}"[:200])
        return f"That failed ({type(e).__name__}: {e})"[:300] + "; nothing was changed."
    if not ok:
        app.events.emit("proposal_refused", id=pid)
        return msg
    p.update({"status": "applied", "applied": {**(undo or {}), "at": time.time(), "via": via}})
    save(app, p)
    scratch.remove(app, sc)
    app.events.emit("proposal_applied", id=pid, files=len(p.get("files") or []), kind=p.get("kind"), via=via)
    return msg


def _apply_files(app: App, p: dict, sc: scratch.Scratch) -> tuple[bool, str, dict]:
    origin = sc.src
    changed_since = []
    for c in p.get("files") or []:
        now_sha = scratch.file_sha(origin / c["path"])
        if now_sha != c.get("old_sha"):
            changed_since.append(c["path"])
    if changed_since:
        return (
            False,
            (
                f"Not applied: {', '.join(changed_since[:5])} changed since this was proposed (or appeared). Tap "
                "Change to have it redone on the new version, or Discard."
            ),
            {},
        )
    keep = home(app) / p["id"] / "before"
    keep.mkdir(parents=True, exist_ok=True)
    done = []
    try:
        for c in p.get("files") or []:
            rel, dst = c["path"], origin / c["path"]
            if dst.is_file():
                (keep / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, keep / rel)
            if c["status"] == "deleted":
                dst.unlink(missing_ok=True)
            else:
                data = (sc.work / rel).read_bytes()
                dst.parent.mkdir(parents=True, exist_ok=True)
                _write_bytes(dst, data)
            done.append(c)
    except OSError as e:  # half-way: what was written is put back
        _restore(origin, keep, done)
        return False, f"Not applied: writing {c['path']} failed ({e.strerror or e}); nothing changed.", {}
    n = len(done)
    where = p.get("label") or "your files"
    return (
        True,
        (
            f"Applied to {where}: {n} file{'s' if n != 1 else ''} "
            + ("(" + ", ".join(c["path"] for c in done[:4]) + (", ..." if n > 4 else "") + ")")
            + ". The earlier versions are kept: Undo puts them back."
        ),
        {"before": str(keep)},
    )


def _write_bytes(dst: Path, data: bytes) -> None:
    tmp = dst.with_name(f".{dst.name}.kurooto{os.getpid()}")
    tmp.write_bytes(data)
    for attempt in range(10):
        try:
            os.replace(tmp, dst)
            return
        except PermissionError:  # Windows: a scanner or sync client holds it for a moment
            if attempt == 9:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(0.05 * (attempt + 1))


def _restore(origin: Path, keep: Path, files: list[dict]) -> None:
    for c in files:
        dst, was = origin / c["path"], keep / c["path"]
        if was.is_file():
            _write_bytes(dst, was.read_bytes())
        else:
            dst.unlink(missing_ok=True)


def _branch(app: App, repo: Path) -> tuple[str | None, str]:
    r = scratch.git(app, repo, "symbolic-ref", "-q", "--short", "HEAD")
    if not r.ok or not r.out.strip():
        return None, "Not applied: the repository is on no branch (a detached HEAD). Check out a branch, then Apply."
    for name in ("MERGE_HEAD", "rebase-merge", "rebase-apply", "CHERRY_PICK_HEAD", "REVERT_HEAD"):
        g = scratch.git(app, repo, "rev-parse", "--git-path", name)
        f = Path(g.out.strip()) if g.ok else None
        if f is not None and not f.is_absolute():
            f = repo / f
        if f is not None and f.exists():
            return (
                None,
                "Not applied: the repository is in the middle of a merge, rebase or cherry-pick. Finish it first.",
            )
    return r.out.strip(), ""


def _dirty(app: App, repo: Path, paths: list[str]) -> list[str]:
    r = scratch.git(app, repo, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", *paths)
    return sorted({x[3:] for x in r.out.split("\0") if len(x) > 3})


def _commit(app: App, repo: Path, sc: scratch.Scratch, patch: Path, message: str, reverse: bool, paths: list[str],
            deleted: list[str]) -> tuple[str | None, str]:  # fmt: skip
    """One commit on the current branch made from the patch, without touching anything else of yours: a temporary
    index, then the branch moved only if it's still where it was, then just these files brought up to date."""
    branch, why = _branch(app, repo)
    if branch is None:
        return None, why
    dirty = _dirty(app, repo, paths)
    if dirty:
        return None, (
            f"Not applied: you have uncommitted changes in {', '.join(dirty[:5])} (or files there that aren't in "
            "git). Commit or stash them, then tap Apply again."
        )
    head = scratch.git(app, repo, "rev-parse", "-q", "--verify", "HEAD").out.strip()
    idx = sc.root / f"apply-index-{uuid.uuid4().hex[:6]}"
    env = {"GIT_INDEX_FILE": str(idx)}
    try:
        r = scratch.git(app, repo, "read-tree", head, env=env)
        if not r.ok:
            return None, f"Not applied: git couldn't read your branch ({r.err.strip()[-150:]})."
        r = scratch.git(app, repo, "apply", "--cached", "--binary", *(["-R"] if reverse else []), str(patch), env=env)
        if not r.ok:
            return None, (
                "Not applied: it no longer fits your branch (those files changed there since). Tap Change to have it "
                "redone on the new version, or Discard."
                if not reverse
                else "Undo didn't fit: those files changed since it was applied. Revert the commit yourself."
            )
        tree = scratch.git(app, repo, "write-tree", env=env).out.strip()
        who = {}
        if not scratch.git(app, repo, "config", "user.email").out.strip():
            who = {"GIT_AUTHOR_NAME": "Kurooto", "GIT_AUTHOR_EMAIL": "kurooto@localhost",
                   "GIT_COMMITTER_NAME": "Kurooto", "GIT_COMMITTER_EMAIL": "kurooto@localhost"}  # fmt: skip
        c = scratch.git(app, repo, "commit-tree", tree, "-p", head, "--no-gpg-sign", "-m", message, env={**env, **who})
        commit = c.out.strip()
        if not c.ok or not commit:
            return None, f"Not applied: git couldn't make the commit ({(c.err or c.out).strip()[-150:]})."
        u = scratch.git(app, repo, "update-ref", "-m", "kurooto: apply a proposal", f"refs/heads/{branch}", commit,
                        head)  # fmt: skip
        if not u.ok:
            return None, "Not applied: your branch moved while it was being applied. Tap Apply again."
    finally:
        idx.unlink(missing_ok=True)
    keep = [x for x in paths if x not in deleted]
    if keep:
        scratch.git(app, repo, "checkout", "-q", commit, "--", *keep)
    if deleted:
        scratch.git(app, repo, "rm", "-q", "--cached", "-f", "--ignore-unmatch", "--", *deleted)
        for d in deleted:
            (repo / d).unlink(missing_ok=True)
    return commit, branch


def _git_lists(p: dict, reverse: bool) -> tuple[list[str], list[str]]:
    files = p.get("files") or []
    paths = [c["path"] for c in files]
    deleted = [c["path"] for c in files if c["status"] == ("added" if reverse else "deleted")]
    return paths, deleted


def _apply_git(app: App, p: dict, sc: scratch.Scratch) -> tuple[bool, str, dict]:
    repo = sc.src
    patch = home(app) / f"{p['id']}.diff"
    paths, deleted = _git_lists(p, reverse=False)
    body = (p.get("summary") or "").strip()
    message = f"{p['title']}\n\n{body}\n\nProposed by Kurooto from: {p.get('request', '')[:300]}".strip()
    commit, branch = _commit(app, repo, sc, patch, message, False, paths, deleted)
    if commit is None:
        return False, branch, {}
    return (
        True,
        (
            f"Applied to {p.get('label')}: commit {commit[:7]} on {branch} ({len(paths)} file"
            f"{'s' if len(paths) != 1 else ''}; not pushed). Undo reverts it."
        ),
        {"commit": commit, "branch": branch, "patch": str(patch)},
    )


# -------------------------------------------------------------------------------------------------- Undo
def undo(app: App, pid: str) -> str:
    p = get(app, pid)
    if p is None or p.get("status") != "applied":
        return "That isn't an applied proposal."
    hook = UNDO.get(p.get("apply_hook") or "")
    try:
        if hook:
            ok, msg = hook(app, p)
        elif p.get("kind") == "git":
            ok, msg = _undo_git(app, p)
        else:
            ok, msg = _undo_files(app, p)
    except Exception as e:
        return f"Undo failed ({type(e).__name__}: {e})"[:300]
    if ok:
        p["status"] = "undone"
        save(app, p)
        app.events.emit("proposal_undone", id=pid)
    return msg


def _undo_files(app: App, p: dict) -> tuple[bool, str]:
    origin = Path(p["origin"])
    keep = Path((p.get("applied") or {}).get("before") or "")
    changed = [c["path"] for c in p.get("files") or [] if scratch.file_sha(origin / c["path"]) != c.get("new_sha")]
    if changed:
        return False, (
            f"Not undone: {', '.join(changed[:5])} changed since it was applied, and Undo would lose that. The "
            f"earlier versions are in {keep}."
        )
    _restore(origin, keep, p.get("files") or [])
    shutil.rmtree(keep.parent, ignore_errors=True)
    return True, f"Undone: {p.get('label')} is as it was before {p['title']!r}."


def _undo_git(app: App, p: dict) -> tuple[bool, str]:
    a = p.get("applied") or {}
    repo = Path(p["origin"])
    patch = Path(a.get("patch") or home(app) / f"{p['id']}.diff")
    tmp = scratch.home(app) / f"undo-{p['id']}"
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        sc = scratch.Scratch("s00000000", "git", str(repo), dir=str(tmp))
        paths, deleted = _git_lists(p, reverse=True)
        commit, branch = _commit(app, repo, sc, patch, f"Revert \"{p['title']}\"\n\nThis reverts commit "
                                 f"{a.get('commit', '')}.", True, paths, deleted)  # fmt: skip
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if commit is None:
        return False, branch
    return True, f"Undone: commit {commit[:7]} on {branch} reverts {str(a.get('commit', ''))[:7]} (not pushed)."


# ------------------------------------------------------------------------------------------ Change, Discard
def discard(app: App, pid: str) -> str:
    p = get(app, pid)
    if p is None or p.get("status") not in OPEN:
        return "That proposal isn't waiting any more."
    sc = scratch.get(app, p.get("sid"))
    if sc is not None:
        scratch.remove(app, sc)
    p["status"] = "discarded"
    save(app, p)
    hook = UNDO.get(f"{p.get('apply_hook')}.discard") if p.get("apply_hook") else None
    if hook:
        try:
            hook(app, p)
        except Exception as e:
            app.events.emit("proposal_hook_failed", id=pid, error=str(e)[:200])
    app.events.emit("proposal_discarded", id=pid)
    return "Discarded; nothing of yours changed."


def change(app: App, pid: str) -> str:
    """Change: ask what to change (the answer runs the AI again in the same scratch folder)."""
    p = get(app, pid)
    if p is None or p.get("status") != "waiting":
        return "That proposal isn't waiting any more."
    if scratch.get(app, p.get("sid")) is None:
        return "Its scratch folder is gone, so it can't be changed; ask again."
    app.ask.ask(
        f'What should change in "{p["title"]}"? Reply with what you want different.',
        hook=HOOK,
        hook_payload={"pid": pid},
        source="proposals",
        title="Change the proposal",
        why="asked",
        about=p["title"][:60],
    )
    return "Say what to change (reply to the question)."


def change_answer(app: App, q: dict, answer: str) -> str | None:
    if q.get("nothing"):
        return "Left the proposal as it is."
    return change_with(app, (q.get("hook_payload") or {}).get("pid"), answer)


def change_with(app: App, pid: str | None, answer: str) -> str:
    """Run the AI again in the proposal's scratch folder with what you want different (Change's answer, or the
    dashboard's box)."""
    p = get(app, pid)
    if p is None or p.get("status") != "waiting" or not str(answer or "").strip():
        return "Left the proposal as it is."
    sc = scratch.get(app, p.get("sid"))
    if sc is None:
        return "Its scratch folder is gone, so it can't be changed; ask again."
    busy = scratch.busy(app, sc.src)
    if busy:
        return f"The AI is already working on {p.get('label')} ({busy}); try again when it's done."
    prompt = (
        f"Earlier request: {p.get('request', '')}\n\n"
        f"What you proposed (they saw it as a diff): {p['title']}\n{p.get('summary', '')}\n\n"
        f"They want this changed: {answer}\n\n"
        "Your scratch folder still holds your earlier changes: change them there, and answer as before (a title line, "
        "then what you changed)."
    )
    p["status"] = "changing"
    save(app, p)
    jid = submit(app, sc, prompt, f"Change: {p['title']}"[:80], source=p.get("source") or "project", pid=p["id"],
                 request=p.get("request", ""))  # fmt: skip
    p["job"] = jid
    save(app, p)
    return "Working on it in the same scratch folder; the new version comes as before."


# --------------------------------------------------------------------------------------- buttons, commands
def button(app: App, ref: str, act: str) -> str:
    """The "prop" buttons: Apply, Change, Discard, Undo, Show."""
    if act == "apply":
        out = apply(app, ref, via="button")
        p = get(app, ref)
        if p is not None and p.get("status") == "applied":
            app.notify(out, kind="result", why="asked", buttons=[[("Undo", f"prop:{ref}:undo")]])
        elif not out.startswith(("That", "No such")):
            app.notify(out, kind="result", why="asked")
        return out[:190]
    if act == "discard":
        return discard(app, ref)
    if act == "change":
        return change(app, ref)
    if act == "undo":
        out = undo(app, ref)
        app.notify(out, kind="result", why="asked")
        return out[:190]
    if act == "show":
        p = get(app, ref)
        if p is None:
            return "No such proposal."
        if p.get("status") in OPEN:
            tell(app, p)
        else:
            app.notify(text(app, p, with_diff=False)[0] + f"\n({p.get('status')})", kind="result", why="asked")
        return "Sent."
    return "unknown button"


def line(p: dict, i: int | None = None) -> str:
    n = len(p.get("files") or [])
    when = dt.datetime.fromtimestamp(float(p.get("created") or 0)).strftime("%a %d %b %H:%M")
    dels = f", deletes {len(p['deletes'])}" if p.get("deletes") else ""
    state = "" if p.get("status") == "waiting" else f" · {p.get('status')}"
    num = f"{i}. " if i is not None else "- "
    return f"{num}{p['title']} · {p.get('label')} · {n} file{'s' if n != 1 else ''}{dels} · {when}{state} ({p['id']})"


def command(app: App, arg: str) -> tuple[str, list | None]:
    """/proposals: what waits for your OK; /proposals <id or number> shows one; apply|discard|undo <id>."""
    words = str(arg or "").split()
    if words and words[0].lower() in ("apply", "discard", "undo", "change") and len(words) > 1:
        p = find(app, words[1])
        if p is None:
            return f"No proposal {words[1]} (/proposals lists them).", None
        act = words[0].lower()
        if act == "apply":
            out = apply(app, p["id"], via="typed")
            return out, [[("Undo", f"prop:{p['id']}:undo")]] if get(app, p["id"]).get("status") == "applied" else None
        return {"discard": discard, "undo": undo, "change": change}[act](app, p["id"]), None
    if words:
        p = find(app, words[0])
        if p is None:
            return f"No proposal {words[0]} (/proposals lists them).", None
        body, _ = text(app, p)
        if p.get("status") in OPEN:
            return body, BUTTONS(p["id"])
        return body + f"\n({p.get('status')})", [[("Undo", f"prop:{p['id']}:undo")]] if p.get(
            "status"
        ) == "applied" else None
    w = waiting(app)
    lines = ["Waiting for your OK:", *(line(p, i) for i, p in enumerate(w, 1))] if w else ["Nothing waits for your OK."]
    done = [p for p in every(app) if p.get("status") == "applied"][:3]
    if done:
        lines += ["", "Applied lately (Undo puts them back):", *(line(p) for p in done)]
    lines.append("\n/proposals <number> shows one with its diff; the dashboard's Proposals page too.")
    buttons = [[(f"Show: {p['title'][:40]}", f"prop:{p['id']}:show")] for p in w[:6]]
    buttons += [[(f"Undo: {p['title'][:40]}", f"prop:{p['id']}:undo")] for p in done]
    return "\n".join(lines), buttons or None


def public(app: App, p: dict, diff: bool = False) -> dict:
    out = {k: p.get(k) for k in ("id", "title", "summary", "label", "project", "kind", "files", "deletes", "status",
                                 "created", "updated", "rev", "checks", "blocked", "outside", "dropped", "source",
                                 "night", "size")}  # fmt: skip
    if diff:
        out["diff"] = diff_text(app, p)
    return out


# ----------------------------------------------------------------------------------- your notes, upkeep
def notes_request(app: App, msg: Any, text_: str) -> str | None:
    """A change to your notes you asked for in plain words ("tidy my LA notes' headings", "add a summary to this
    lecture note"): an AI request in a scratch folder of your notes, whose answer is a proposal. None: not one."""
    if not app.settings.get("proposals.notes_edits") or not NOTES_ASK.search(str(text_ or "").strip()):
        return None
    root = Path(os.path.abspath(app.workspace))
    if scratch.busy(app, root):
        return "I'm already working on a change to your notes; it comes as a proposal. Ask again after that one."
    sc = scratch.create(app, root, "your notes", git_ok=False)
    terminal = getattr(msg, "via", "") in ("terminal", "setup")
    jid = submit(app, sc, text_, text_.strip()[:80], reply_to=None if terminal else getattr(msg, "message_id", None),
                 source="notes", request=text_)  # fmt: skip
    if msg is not None:
        msg.job = jid
    return "On it: the change comes as a proposal (a diff to Apply, Change or Discard); nothing changes before that."


def cleanup(app: App, payload: dict | None = None) -> dict:
    """Daily: proposals nobody answered in proposals.keep_days expire, and scratch folders no proposal or running
    request needs go."""
    days = float(app.settings.get("proposals.keep_days") or 7)
    cutoff = time.time() - days * 86400
    expired = 0
    for p in every(app):
        if p.get("status") == "waiting" and float(p.get("created") or 0) < cutoff:
            sc = scratch.get(app, p.get("sid"))
            if sc is not None:
                scratch.remove(app, sc)
            p["status"] = "expired"
            save(app, p)
            expired += 1
    keep = {p.get("sid") for p in waiting(app)}
    for j in app.jobs.active():
        sc = scratch.for_job(app, j.id)
        if sc is not None:
            keep.add(sc.id)
    gone = scratch.cleanup(app, days, keep)
    old = time.time() - max(days, 30) * 86400  # the records themselves (and kept earlier versions) after a month
    for p in every(app):
        if p.get("status") not in OPEN and float(p.get("updated") or 0) < old:
            _file(app, p["id"]).unlink(missing_ok=True)
            (home(app) / f"{p['id']}.diff").unlink(missing_ok=True)
            shutil.rmtree(home(app) / p["id"], ignore_errors=True)
    return {"expired": expired, "removed": gone}


def start(app: App) -> None:
    app.scheduler.action("proposals.cleanup", lambda p: cleanup(app, p))
    app.scheduler.every("proposals:cleanup", "daily 04:20", "proposals.cleanup", module="proposals")
    app.scheduler.action("proposals.morning", lambda p: morning(app, p))
    app.scheduler.every("proposals:morning", app.settings.get("proposals.morning") or "daily 07:30",
                        "proposals.morning", module="proposals")  # fmt: skip


def attach(app: App) -> None:
    """Wired at App start: the scratch requests' follow-up, the watcher for edit_note's proposals, Change's hook."""
    app.jobs.then_actions[THEN] = lambda job, result, payload: job_done(app, job, result, payload)
    app.jobs.watchers.append(lambda job, result, info: watch(app, job, result, info))
    app.ask.hooks[HOOK] = lambda q, answer: change_answer(app, q, answer)


__all__ = ["apply", "undo", "discard", "change", "make", "submit", "command", "button", "morning_lines", "start"]
