"""The scanner must catch fake secrets and personal terms without ever printing them.
Fake values are assembled at run time so this file itself contains nothing that looks secret."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("privacy_scan", ROOT / "tools" / "privacy_scan.py")
ps = importlib.util.module_from_spec(spec)
sys.modules["privacy_scan"] = ps  # dataclasses look the module up
spec.loader.exec_module(ps)

A = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEF"
FAKES = {
    "telegram bot token": "123456789" + ":" + A[:35],
    "google api key": "AI" + "za" + A[:35],
    "private key": "-----BEGIN " + "PRIVATE KEY-----",
    "openai key": "sk" + "-" + A[:30],
    "github token": "gh" + "p_" + A[:36],
    "jwt": "ey" + "J" + A[:12] + ".ey" + "J" + A[:12] + "." + A[:12],
    "email address": "some.one" + "@" + "gmail.com",
    "phone number": "+44 20" + " 7946 0958",
    "private ip": "192." + "168.1.20",
    "workers.dev host": "kurooto-call.someone" + ".workers" + ".dev",
    "home folder": "/ho" + "me/alice/notes",
    "secret assignment": 'api_key = "' + A[:20] + '"',
}


@pytest.mark.parametrize("kind", sorted(FAKES))
def test_catches(kind):
    found = ps.Rules().scan_line(f"x {FAKES[kind]} y", "f:1")
    assert any(f.kind == kind for f in found), (kind, [f.kind for f in found])


@pytest.mark.parametrize(
    "ok",
    [
        "123+someone@users.noreply.github.com",
        "Co-Authored-By: Claude <noreply@anthropic.com>",
        "https://kurooto-xxxx.example.workers.dev",
        "/home/runner/work",
        "C:\\Users\\runneradmin\\x",
        "127.0.0.1:8770",
        "token = make_token(secret)",
    ],
)
def test_leaves_normal_text_alone(ok):
    assert ps.Rules().scan_line(ok, "f:1") == []


def test_denylist_terms_regexes_and_allowed_contexts():
    rules = ps.Rules("Jane Roe\nre:acme\\s*uni\nallow:github\\.com/janeroe/kurooto\nJaneroe")
    assert rules.scan_line("written by Jane Roe at ACME  Uni", "f:1")
    assert rules.scan_line("see github.com/janeroe/kurooto", "f:1") == []
    assert rules.scan_line("Janeroe's notes", "f:1")
    assert rules.scan_line("Janeroebot", "f:1") == []  # inside a longer word


def test_values_from_secrets_files_are_never_printed(tmp_path, capsys):
    secret = "Zq" + A[:18]
    (tmp_path / "s.json").write_text(json.dumps({"token": secret, "chat_id": 987654321, "flag": True}))
    rules = ps.Rules(f"@file:{tmp_path / 's.json'}")
    target = tmp_path / "leak.txt"
    target.write_text(f"oops {secret} and chat 987654321\n")
    found = ps.scan_file(rules, target, "leak.txt")
    assert len(found) == 2
    out = "\n".join(map(str, found))
    assert secret not in out and "987654321" not in out


def test_allow_file_skips_patterns_but_not_the_denylist(tmp_path):
    rules = ps.Rules("Jane Roe", ["tests/fixtures/*"])
    text = FAKES["openai key"] + " by Jane Roe"
    kinds = [f.kind for f in rules.scan_text(text, "tests/fixtures/x.txt", "tests/fixtures/x.txt")]
    assert kinds == ["denylist entry #1"]


def test_added_lines_from_a_diff():
    diff = "+++ b/a.py\n@@ -0,0 +3,2 @@\n+one\n+two\n+++ /dev/null\n+gone\n"
    assert list(ps.added_lines(diff)) == [("a.py", 3, "one"), ("a.py", 4, "two")]


def test_added_lines_from_a_merge_keep_no_marker():
    diff = "+++ b/t.py\n@@@ -1,0 -1,2 +1,3 @@@\n++" + "@pytest.fixture(autouse=True)\n+ def f():\n +    pass\n"
    assert list(ps.added_lines(diff)) == [("t.py", 1, "@pytest.fixture(autouse=True)"), ("t.py", 2, "def f():"),
                                          ("t.py", 3, "    pass")]  # fmt: skip


def test_commit_identity_must_be_noreply(tmp_path):
    def git(*a):
        return subprocess.run(["git", *a], cwd=tmp_path, capture_output=True, text=True, check=True).stdout

    git("init", "-q")
    (tmp_path / "f.txt").write_text("hello\n")
    git("add", "f.txt")
    git("-c", "user.name=x", "-c", "user.email=real.person" + "@" + "gmail.com", "commit", "-qm", "first")
    sha = git("rev-parse", "HEAD").strip()
    old = ps.ROOT
    ps.ROOT = tmp_path
    try:
        found = ps.scan_identity(ps.Rules(), sha)
    finally:
        ps.ROOT = old
    assert any("noreply" in f.kind for f in found)


def test_cli_exit_codes(tmp_path):
    clean, dirty = tmp_path / "clean.txt", tmp_path / "dirty.txt"
    clean.write_text("nothing here\n")
    dirty.write_text(FAKES["google api key"] + "\n")
    env = {**os.environ, "KUROOTO_DENYLIST": "", "KUROOTO_DENYLIST_FILE": str(tmp_path / "none")}

    def run(f):
        return subprocess.run(
            [sys.executable, str(ROOT / "tools/privacy_scan.py"), "--files", str(f)],
            capture_output=True,
            text=True,
            env=env,
        )

    assert run(clean).returncode == 0
    r = run(dirty)
    assert r.returncode == 1 and FAKES["google api key"] not in r.stdout + r.stderr


def test_public_fields_in_oauth_files_are_not_treated_as_secrets(tmp_path):
    secret = "ya29" + A[:20]
    (tmp_path / "token.json").write_text(
        json.dumps(
            {
                "token": secret,
                "universe_domain": "googleapis.com",
                "token_uri": "https://oauth2.googleapis.com/token",
                "expiry": "2026-10-19T12:00:00Z",
            }
        )
    )
    rules = ps.Rules(f"@file:{tmp_path / 'token.json'}")
    assert rules.scan_line('url = "https://generativelanguage.googleapis.com/v1beta"', "f:1") == []
    assert rules.scan_line(f"leaked {secret}", "f:1")
