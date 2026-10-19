#!/usr/bin/env python3
"""privacy_scan: refuse commits and pushes that would publish a secret or something personal.

    privacy_scan.py --staged              what `git commit` is about to record (the pre-commit hook)
    privacy_scan.py --commits A..B        commits about to be pushed, with their authors and messages (pre-push)
    privacy_scan.py --tree                every tracked file as it is now
    privacy_scan.py --history             every commit ever made (CI)
    privacy_scan.py --files F [F ...]     just these files

Three layers:
  1. patterns: API keys and tokens, private keys, emails, phone numbers, private IPs, workers.dev hosts, home
     folders. Paths listed in tools/privacy_allow.txt skip this layer (example data that only looks secret).
  2. a denylist of personal terms, never committed: the env var KUROOTO_DENYLIST (newline-separated, used in CI)
     and the file ~/.config/kurooto-dev/denylist.txt (or $KUROOTO_DENYLIST_FILE). Each line is one of
         a term                 matched case-insensitively, not inside a longer word
         re:<regex>             a regular expression
         @file:<path>           every value in that secrets file (JSON values, or the text and its lines)
         allow:<regex>          text that may contain a denied term (e.g. the public repo's own URL)
  3. author and committer identities must be GitHub noreply addresses.

Findings are reported as path:line and the kind of match. Matched values are never printed, only their length.
Exit status: 0 clean, 1 findings, 2 usage error. Standard library only.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOW_FILE = ROOT / "tools" / "privacy_allow.txt"
ZERO = "0" * 40

PATTERNS = [
    ("telegram bot token", r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b"),
    ("google api key", r"AIza[0-9A-Za-z_-]{30,}"),
    ("private key", r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP |ENCRYPTED )?PRIVATE KEY"),
    ("openai key", r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    ("anthropic key", r"\bsk-ant-[A-Za-z0-9_-]{20,}"),
    ("github token", r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"),
    ("slack token", r"\bxox[abposr]-[A-Za-z0-9-]{10,}"),
    ("hugging face token", r"\bhf_[A-Za-z0-9]{30,}"),
    ("nvidia key", r"\bnvapi-[A-Za-z0-9_-]{30,}"),
    ("jwt", r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    (
        "secret assignment",
        r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|secret|password|passwd)\b[\"']?\s*[:=]\s*"
        r"[\"']([A-Za-z0-9+/_=.-]{16,})[\"']",
    ),
    ("email address", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"),
    ("phone number", r"(?<![\w.+])\+\d{1,3}[ -]?\d{2,5}[ -]?\d{3,5}[ -]?\d{3,5}(?![\w.])"),
    ("private ip", r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b"),
    ("workers.dev host", r"\b[a-z0-9-]+\.[a-z0-9-]+\.workers\.dev\b"),
    ("home folder", r"(?:/home/|/Users/|[A-Za-z]:\\+Users\\+)[A-Za-z0-9._-]+"),
    # split so this file doesn't match its own patterns
]
# matches that are fine anywhere
SAFE = [
    r"^[0-9]+\+[A-Za-z0-9-]+@users\.noreply\.github\.com$",
    r"@(?:example\.(?:com|org|net)|users\.noreply\.github\.com)$",
    r"^noreply@anthropic\.com$",
    r"^(?:/home/|/Users/|[A-Za-z]:\\+Users\\+)(?:runner|runneradmin|user|you|someone|example|me)$",
    r"(?:example|xxxx|your-subdomain|<[^>]*>)",
]


# fields in OAuth and config files that are public, and values that are only addresses or dates
NOT_SECRET_KEYS = {
    "universe_domain",
    "token_uri",
    "auth_uri",
    "auth_provider_x509_cert_url",
    "redirect_uris",
    "javascript_origins",
    "scopes",
    "scope",
    "expiry",
    "type",
    "token_type",
}
PUBLIC_VALUE = re.compile(r"^(?:https?://\S+|[a-z0-9-]+(?:\.[a-z0-9-]+)+|\d{4}-\d{2}-\d{2}[T ][\d:.]+Z?|Bearer)$", re.I)


@dataclass
class Finding:
    where: str
    kind: str
    length: int

    def __str__(self):
        return f"{self.where}: {self.kind} ({self.length} chars)"


class Rules:
    def __init__(self, denylist_text: str = "", allow_globs: list[str] | None = None):
        self.patterns = [(k, re.compile(p)) for k, p in PATTERNS]
        self.safe = [re.compile(p) for p in SAFE]
        self.allow_globs = allow_globs or []
        self.terms: list[re.Pattern] = []
        self.values: list[str] = []
        self.allow_ctx: list[re.Pattern] = []
        for raw in denylist_text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("re:"):
                self.terms.append(re.compile(line[3:], re.I))
            elif line.startswith("allow:"):
                self.allow_ctx.append(re.compile(line[6:], re.I))
            elif line.startswith("@file:"):
                self.values += load_values(Path(os.path.expanduser(line[6:].strip())))
            else:
                self.terms.append(re.compile(r"(?<![A-Za-z0-9])" + re.escape(line) + r"(?![A-Za-z0-9])", re.I))
        self.values = sorted({v for v in self.values if len(v) >= 6}, key=len, reverse=True)

    def exempt(self, path: str) -> bool:
        return any(fnmatch.fnmatch(path, g) for g in self.allow_globs)

    def scan_text(self, text: str, where: str, path: str = "") -> list[Finding]:
        out = []
        use_patterns = not (path and self.exempt(path))
        for lineno, line in enumerate(text.splitlines(), 1):
            loc = f"{where}:{lineno}" if where else f"line {lineno}"
            out += self.scan_line(line, loc, use_patterns)
        return out

    def scan_line(self, line: str, loc: str, use_patterns: bool = True) -> list[Finding]:
        out = []
        if use_patterns:
            for kind, rx in self.patterns:
                for m in rx.finditer(line):
                    s = m.group(0)
                    if not any(sp.search(s) for sp in self.safe):
                        out.append(Finding(loc, kind, len(s)))
        masked = line
        for ctx in self.allow_ctx:
            masked = ctx.sub(lambda m: " " * len(m.group(0)), masked)
        for i, rx in enumerate(self.terms, 1):
            for m in rx.finditer(masked):
                out.append(Finding(loc, f"denylist entry #{i}", len(m.group(0))))
        for v in self.values:
            if v in line:
                out.append(Finding(loc, "a secret value from your secrets files", len(v)))
        return out


def load_values(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    vals: list[str] = []

    def walk(o, key=""):
        if key in NOT_SECRET_KEYS:
            return
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, str(k))
        elif isinstance(o, list):
            for v in o:
                walk(v, key)
        elif isinstance(o, bool):
            return
        elif isinstance(o, int) and abs(o) >= 100000:
            vals.append(str(o))
        elif isinstance(o, str) and len(o.strip()) >= 6 and not PUBLIC_VALUE.match(o.strip()):
            vals.append(o.strip())

    try:
        walk(json.loads(text))
    except ValueError:
        vals += [ln.strip() for ln in text.splitlines() if len(ln.strip()) >= 6]
        if len(text.strip()) >= 6:
            vals.append(text.strip())
    return vals


def denylist_text() -> str:
    parts = [os.environ.get("KUROOTO_DENYLIST", "")]
    f = Path(os.environ.get("KUROOTO_DENYLIST_FILE") or Path.home() / ".config" / "kurooto-dev" / "denylist.txt")
    if f.is_file():
        parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts)


def allow_globs() -> list[str]:
    if not ALLOW_FILE.is_file():
        return []
    return [
        ln.strip()
        for ln in ALLOW_FILE.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True
    ).stdout


def added_lines(diff: str):
    """(path, line number, text) for every added line in a unified diff made with -U0."""
    path, n = None, 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            n = int(m.group(1)) if m else 0
        elif line.startswith("+") and path:
            yield path, n, line[1:]
            n += 1


def scan_diff(rules: Rules, diff: str, prefix: str = "") -> list[Finding]:
    out = []
    for path, n, text in added_lines(diff):
        out += rules.scan_line(text, f"{prefix}{path}:{n}", not rules.exempt(path))
    return out


def scan_identity(rules: Rules, sha: str) -> list[Finding]:
    out = []
    meta = git("show", "-s", "--format=%an%x00%ae%x00%cn%x00%ce%x00%B", sha).split("\x00")
    an, ae, cn, ce, body = (meta + [""] * 5)[:5]
    for label, email in (("author", ae), ("committer", ce)):
        if not re.fullmatch(r"[0-9]+\+[A-Za-z0-9-]+@users\.noreply\.github\.com", email.strip()):
            out.append(Finding(f"commit {sha[:9]} {label} email", "not a GitHub noreply address", len(email)))
    out += rules.scan_line(f"{an} {cn}", f"commit {sha[:9]} names", use_patterns=False)
    out += rules.scan_text(body, f"commit {sha[:9]} message")
    return out


def scan_commits(rules: Rules, shas: list[str]) -> list[Finding]:
    out = []
    for sha in shas:
        out += scan_identity(rules, sha)
        out += scan_diff(rules, git("show", "--no-color", "-U0", "--format=", sha), f"commit {sha[:9]} ")
    return out


def scan_tree(rules: Rules) -> list[Finding]:
    out = []
    for path in git("ls-files", "-z").split("\0"):
        if not path:
            continue
        out += rules.scan_line(path, f"{path} (file name)", use_patterns=False)
        out += scan_file(rules, ROOT / path, path)
    return out


def scan_file(rules: Rules, file: Path, shown: str) -> list[Finding]:
    try:
        data = file.read_bytes()
    except OSError:
        return []
    if b"\0" in data[:8192]:
        return []
    return rules.scan_text(data.decode("utf-8", "replace"), shown, shown)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--staged", action="store_true")
    g.add_argument("--commits", metavar="A..B")
    g.add_argument("--tree", action="store_true")
    g.add_argument("--history", action="store_true")
    g.add_argument("--files", nargs="+")
    a = ap.parse_args(argv)
    rules = Rules(denylist_text(), allow_globs())

    if a.staged:
        found = scan_diff(rules, git("diff", "--cached", "--no-color", "-U0", "--diff-filter=ACMR"))
        for path in git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR").split("\0"):
            if path:
                found += rules.scan_line(path, f"{path} (file name)", use_patterns=False)
    elif a.commits:
        lo, _, hi = a.commits.partition("..")
        span = hi if lo in ("", ZERO) else f"{lo}..{hi}"
        found = scan_commits(rules, [s for s in git("rev-list", span).split() if s])
    elif a.history:
        found = scan_commits(rules, [s for s in git("rev-list", "--all").split() if s])
    elif a.tree:
        found = scan_tree(rules)
    else:
        found = []
        for f in a.files:
            found += scan_file(rules, Path(f), f)

    for f in found:
        print(f)
    if found:
        print(
            f"privacy_scan: {len(found)} finding(s). Nothing was committed or pushed. Fix them, or for example data"
            " that only looks secret, list the path in tools/privacy_allow.txt.",
            file=sys.stderr,
        )
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
