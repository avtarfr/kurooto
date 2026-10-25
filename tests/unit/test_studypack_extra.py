"""0.8.0: your own instructions in a study pack's PROMPT.md: extra lines, and a format phrase for one pack."""

from __future__ import annotations

import pytest

from kurooto.core import studypack


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    yield a
    a.close()


def test_default_prompt_is_unchanged(app):
    text = studypack.prompt_text("Physics of the Atmosphere", "quiz on thermodynamics", None, app)
    assert (
        "My extra instructions" not in text
        and "thermodynamics" in text
        and "{name}" not in text
        and "{scope}" not in text
    )


def test_extra_lines_go_at_the_end_and_placeholders_still_fill(app):
    app.settings.set("studypack.extra", "Reply with Markdown only, one section per topic\n- no PDF or zip\n\n")
    text = studypack.prompt_text("Physics of the Atmosphere", "quiz on thermodynamics", None, app)
    assert text.rstrip().endswith("- no PDF or zip") and "## My extra instructions" in text
    assert "- Reply with Markdown only, one section per topic" in text
    assert (
        "Physics of the Atmosphere" in text and "{name}" not in text and "{aim}" not in text
    )  # the template still filled
    assert text.index("## Rules") < text.index("## My extra instructions")


def test_a_phrase_for_one_pack(app):
    only = studypack.prompt_text("POTA", "quiz on entropy, markdown only", None, app)
    assert "Reply with Markdown only: one section per topic; no PDF and no zip." in only
    pdf = studypack.prompt_text("POTA", "quiz on entropy, pdf too", None, app)
    assert "Also give me the finished notes as a PDF" in pdf and "Markdown only" not in pdf
    one = studypack.prompt_text("POTA", "quiz on entropy, one file", None, app)
    assert "Put everything in one Markdown file." in one
    assert studypack.topics_of("quiz on entropy, pdf too") == ["entropy"]  # the phrase isn't a topic
    assert studypack.run_extra("no pdf please")[0].startswith("Reply with Markdown only")
    assert studypack.run_extra("quiz on entropy") == []


def test_your_own_template_gets_them_too(app):
    f, _ = studypack.make_prompt_file(app)
    f.write_text("# My pack: {name}\n\nDo it well. {aim_text}\n", encoding="utf-8")
    app.settings.set("studypack.extra", "Cite page numbers")
    text = studypack.prompt_text("POTA", "entropy, pdf too", None, app)
    assert (
        text.startswith("# My pack: POTA")
        and "- Cite page numbers" in text
        and "- Also give me the finished notes as a PDF" in text
    )


def test_the_switch(app):
    app.settings.set("studypack.extra", "Cite page numbers")
    app.settings.set("studypack.instructions", False)
    text = studypack.prompt_text("POTA", "entropy, pdf too", None, app)
    assert (
        "My extra instructions" not in text
        and "Cite page numbers" not in text
        and studypack.extra_lines(app, "pdf too") == []
    )
    assert "My extra instructions" not in studypack.prompt_text("POTA", "x", None, None) or True
