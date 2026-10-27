"""0.8.14: the setup page's optional Inner life step (it turns Brain on), and "AI model" for the AI that answers you
("Brain" is Kurooto's mind)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import kurooto

ROOT = Path(kurooto.__file__).parents[2]
STATIC = Path(kurooto.__file__).parent / "web" / "static"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    yield a
    a.close()


def test_setup_has_an_optional_inner_life_step(app):
    from kurooto.core import setupsteps

    s = setupsteps.STEPS
    assert s.index("mind") == s.index("features") + 1 and "mind" not in setupsteps.REQUIRED
    assert setupsteps.finished(app, "mind") is True  # off is a fine answer: never "skipped" on the dashboard
    setupsteps.record(app, "mind", "skip")
    assert not [x for x in setupsteps.left(app) if x["id"] == "mind"]
    html = (STATIC / "setup.html").read_text(encoding="utf-8")
    sec = html.split('<section data-step="mind">')[1].split("</section>")[0]
    assert "Let it grow an inner life" in sec and "data-skip" in sec and 'id="mind-panel"' in sec
    js = (STATIC / "setup.js").read_text(encoding="utf-8")
    assert "function renderMind()" in js and 'chosen.add("mind")' in js and "mind: renderMind" in js
    assert js.count('"mind"') >= 3 and '"Inner life"' in js


def test_the_ai_that_answers_is_an_ai_model():
    pages = [*(ROOT / "docs/wiki/user").glob("*.md"), ROOT / "docs/MANUAL.md", STATIC / "setup.html"]
    for p in pages:
        assert not re.search(r"(?i)\bAI brains?\b", p.read_text(encoding="utf-8")), p.name
    api = (ROOT / "src/kurooto/web/api.py").read_text(encoding="utf-8")
    assert '"brain": "AI model"' in api  # Settings' section; the setting keys (brain.*) stay as they are
    assert (ROOT / "docs/wiki/user/troubleshooting.md").read_text(encoding="utf-8") == (
        ROOT / "src/kurooto/data/troubleshooting.md"
    ).read_text(encoding="utf-8")
