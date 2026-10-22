"""docs/SETTINGS_GUIDE.md is written from the code: a setting added or changed without regenerating it fails here."""

import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[2] / "tools" / "gen_settings_guide.py"


@pytest.mark.skipif(not TOOL.exists(), reason="not in a source checkout")
def test_the_settings_guide_is_up_to_date():
    r = subprocess.run([sys.executable, str(TOOL), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
