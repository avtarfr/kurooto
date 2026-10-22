"""The dashboard's scripts must at least parse: one stray bracket blanks the whole page (it did, once), and no test
of the Python side notices."""

import shutil
import subprocess
from pathlib import Path

import pytest

import kurooto

STATIC = Path(kurooto.__file__).parent / "web" / "static"


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
@pytest.mark.parametrize("js", sorted(STATIC.glob("*.js")), ids=lambda p: p.name)
def test_every_dashboard_script_parses(js):
    r = subprocess.run(["node", "--check", str(js)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-400:]
