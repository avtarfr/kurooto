import sys
import time

from kurooto.core import proc

PY = sys.executable


def test_stdin_carries_awkward_text_unchanged():
    text = 'quotes " & ^ % ! < > | and नमस्ते\n' + "x" * 40000
    r = proc.run([PY, "-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"], input=text, timeout=30)
    assert r.ok and r.out == text


def test_timeout_kills_the_whole_tree():
    child = "import time; time.sleep(60)"
    code = f"import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', {child!r}]); time.sleep(60)"
    t0 = time.monotonic()
    r = proc.run([PY, "-c", code], timeout=2)
    assert r.code is None and time.monotonic() - t0 < 20


def test_exit_codes_and_stderr():
    r = proc.run([PY, "-c", "import sys; print('oops', file=sys.stderr); sys.exit(3)"])
    assert r.code == 3 and not r.ok and "oops" in r.err


def test_which_finds_in_extra_dirs(tmp_path):
    exe = tmp_path / ("tool.exe" if proc.WINDOWS else "tool")
    exe.write_text("")
    assert proc.which("tool-that-does-not-exist") is None
    assert proc.which("tool", [tmp_path]) == str(exe)
