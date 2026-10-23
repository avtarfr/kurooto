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


@pytest.mark.skipif(not TOOL.exists(), reason="not in a source checkout")
def test_the_guide_documents_only_settings_that_exist(tmp_path, monkeypatch):
    """Settings come from register_defaults alone: a class attribute `defaults` was never read by Kurooto, so the
    guide mustn't list one (it used to)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("gen_settings_guide", TOOL)
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    (tmp_path / "m.py").write_text('class M:\n    id = "m"\n    defaults = {"x": 1}  # never registered\n')
    monkeypatch.setattr(gen, "SRC", tmp_path)
    assert gen.collect() == []
