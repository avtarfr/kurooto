"""The Research add-on (modules/research_addon.py): run compare (kurooto/runcompare.py: config, code from a real git
repository, metrics and curves into the project's notes; /runs and `kurooto runlog diff`), the LaTeX tracker
(modules/latex_tracker.py: the log read, words counted, a nightly build with a stand-in engine, the morning line, a
BibTeX entry only after two taps) and the bundle's one switch. No network; the AI is a stand-in."""

from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from kurooto import runcompare as rc
from kurooto.core import proc
from kurooto.modules import latex_tracker as lt
from kurooto.modules.base import Module

needs_git = pytest.mark.skipif(not shutil.which("git"), reason="needs git")


def git(repo, *a):
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", *a],
        check=True,
        capture_output=True,
    )


def two_runs(env, tmp_path, monkeypatch):
    """A repository with two commits and a run at each: lr 0.1 then 0.01 (and a new wd), loss falling faster."""
    from kurooto.runlog import Runlog

    repo = tmp_path / "solver"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "fit.py").write_text("lr = 0.1\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "first")
    rl = Runlog(env.app.paths, env.app.workspace)
    a = rl.start("Solver", "base", {"lr": 0.1, "opt": {"name": "adam", "beta": 0.9}}, repo)
    for step, loss in enumerate([1.0, 0.8, 0.6, 0.5]):
        rl.metric({"loss": loss, "acc": 0.5 + step / 10}, step=step, rid=a)
    rl.end("ok", a)
    (repo / "fit.py").write_text("lr = 0.01\nwd = 0.1\n", encoding="utf-8")
    git(repo, "commit", "-qam", "smaller steps")
    b = rl.start("Solver", "smaller", {"lr": 0.01, "opt": {"name": "adam", "beta": 0.9}, "wd": 0.1}, repo)
    for step, loss in enumerate([1.0, 0.6, 0.3, 0.2]):
        rl.metric({"loss": loss}, step=step, rid=b)
    rl.end("ok", b)
    monkeypatch.setattr(rc, "has_matplotlib", lambda: False)  # the text curves, whatever this Python has
    return rl, a, b, repo


# ================================================================================================ run compare
def test_config_flattened_and_compared():
    a = {"lr": 0.1, "opt": {"name": "adam", "beta": 0.9}, "seed": 1}
    b = {"lr": 0.01, "opt": {"name": "adam", "beta": 0.95}, "wd": 0.1, "seed": 1}
    d = {k: (va, vb) for k, va, vb in rc.config_diff(a, b)}
    assert d == {"lr": (0.1, 0.01), "opt.beta": (0.9, 0.95), "wd": (rc.MISSING, 0.1)}
    assert rc._v(rc.MISSING) == "(not set)"


def test_sparklines_share_one_scale():
    assert rc.sparkline([0, 1], 0, 1) == "▁█"
    assert rc.sparkline([0.5], 0, 1) == "▅"  # halfway on the scale both runs share
    assert len(rc.sparkline(list(range(100)), 0, 99, width=20)) == 20
    rows = rc.metric_rows(
        rc.RunInfo("a", Path("."), {}, {}, [{"step": 0, "loss": 1.0}, {"step": 1, "loss": 0.5}]),
        rc.RunInfo("b", Path("."), {}, {}, [{"step": 0, "loss": 1.0}, {"step": 1, "loss": 0.25}]),
    )
    assert rows[0]["metric"] == "loss" and rows[0]["change"] == -0.25 and round(rows[0]["pct"]) == -50
    spark = rc.spark_table(rows)
    assert spark[0].startswith("loss   A █") and spark[1].strip().startswith("B █")


def test_finding_a_run_by_number_piece_or_id():
    runs = [("20261022-090000-b", Path("b")), ("20261021-090000-a", Path("a"))]
    assert rc.find(runs, "1")[0] == "20261022-090000-b"
    assert rc.find(runs, "-a")[0] == "20261021-090000-a"
    with pytest.raises(rc.CompareError, match="matches 2"):
        rc.find(runs, "2026102")
    with pytest.raises(rc.CompareError, match="no run"):
        rc.find(runs, "zzz")


@needs_git
def test_runs_compare_writes_config_code_metrics_and_curves_into_the_project(env, tmp_path, monkeypatch):
    rl, a, b, repo = two_runs(env, tmp_path, monkeypatch)
    env.on("research_addon")
    listing = env.say("/runs")
    assert listing.startswith("Recent runs:\n1. " + b) and f"2. {a} (Solver, ok)" in listing
    said = env.say("/runs compare 2 1")
    assert said.startswith(f"{a} vs {b}: 2 config changes (lr 0.1 → 0.01; wd (not set) → 0.1)")
    assert "solver: " in said and "(1 commit after A), 1 file changed" in said and "loss 0.5 → 0.2 (-60%)" in said
    folder = env.app.workspace / "research" / "solver" / "runs" / "compare"
    note = folder / f"{a}--{b}.md"
    text = note.read_text(encoding="utf-8")
    assert "<!-- kurooto:run-compare -->" in text and "| `lr` | 0.1 | 0.01 |" in text
    assert "| `wd` | (not set) | 0.1 |" in text and "opt.beta" not in text  # unchanged keys aren't listed
    assert "+lr = 0.01" in text and "fit.py" in text  # the code diff between the two commits
    assert "| loss | 0.5 | 0.2 | -0.3 (-60%) | 0.5 | 0.2 |" in text
    assert "| acc | 0.8 |  |" in text  # a metric only one run logged
    assert "## Curves" in text and "loss   A █" in text  # text sparklines without matplotlib
    assert f"[[research/solver/runs/{a}/run|{a}]]" in text
    assert (
        subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True).stdout == ""
    )

    project = env.app.workspace / "research" / "solver" / "index.md"
    p = project.read_text(encoding="utf-8")
    project.write_text(p.replace("Notes on this project go here.", "My own words here."), encoding="utf-8")
    env.say(f"/runs compare {a} {b}")  # again: the same line, replaced, and your text untouched
    p = project.read_text(encoding="utf-8")
    assert p.count(f"[[research/solver/runs/compare/{a}--{b}|base vs smaller]]") == 1
    assert "My own words here." in p and "<!-- kurooto:run-compare -->" in p
    assert env.say("/runs compare 1 1") == "That's the same run twice."


@needs_git
def test_compare_alone_takes_the_last_two_runs_of_a_project(env, tmp_path, monkeypatch):
    rl, a, b, repo = two_runs(env, tmp_path, monkeypatch)
    env.on("research_addon")
    assert env.say("/runs compare").startswith(f"{a} vs {b}:")


@needs_git
def test_the_command_line_needs_the_add_on_and_then_compares(env, tmp_path, monkeypatch, capsys):
    from kurooto import cli

    rl, a, b, repo = two_runs(env, tmp_path, monkeypatch)
    assert cli.main(["runlog", "diff", a, b]) == 2
    assert "part of the Research add-on" in capsys.readouterr().out
    env.on("research_addon")
    assert cli.main(["runlog", "diff", a[-6:], b]) == 0
    out = capsys.readouterr().out
    assert f"{a} vs {b}: 2 config changes" in out and f"research/solver/runs/compare/{a}--{b}.md" in out
    assert cli.main(["runlog", "diff", "nothing", b]) == 2
    assert "no run 'nothing'" in capsys.readouterr().out
    env.app.settings.set("research_addon.run_compare", False)
    assert cli.main(["runlog", "diff", a, b]) == 2
    assert "Run compare is off" in capsys.readouterr().out


@needs_git
def test_runs_kept_in_a_repository_compare_into_its_project(env, tmp_path, monkeypatch):
    from kurooto.runlog import Run

    repo = tmp_path / "model_v2"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "x.py").write_text("x", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "x")
    monkeypatch.chdir(repo)
    monkeypatch.delenv("KUROOTO_PROJECT", raising=False)
    monkeypatch.delenv("RUNLOG_DIR", raising=False)
    with Run("one", config={"n": 1}) as r1:
        r1.log(step=0, loss=2.0)
    with Run("two", config={"n": 2}) as r2:
        r2.log(step=0, loss=1.0)
    env.app.settings.set("research.repos", [str(repo)])
    env.app.settings.set("research.projects", {str(repo): "Climate model"})
    monkeypatch.setattr(rc, "has_matplotlib", lambda: False)
    env.on("research_addon")
    said = env.say(f"/runs compare {r1.id} {r2.id}")
    assert "1 config change (n 1 → 2); same commit" in said and "loss 2 → 1 (-50%)" in said
    assert (env.app.workspace / "research" / "climate-model" / "runs" / "compare" / f"{r1.id}--{r2.id}.md").exists()


@needs_git
@pytest.mark.skipif(not rc.has_matplotlib(), reason="matplotlib isn't in this Python")
def test_curves_as_a_png_with_matplotlib(env, tmp_path, monkeypatch):
    rl, a, b, repo = two_runs(env, tmp_path, monkeypatch)
    monkeypatch.setattr(rc, "has_matplotlib", lambda: True)
    r = rc.compare(rl, a, b)
    png = Path(r["png"])
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    text = (png.parent / f"{a}--{b}.md").read_text(encoding="utf-8")
    assert f"![curves]({png.name})" in text and "loss   A" not in text


# ================================================================================================ LaTeX tracker
LOG = (
    "This is a TeX log.\n"
    "! Undefined control sequence.\n"
    "l.12 \\foo\n"
    "         {bar}\n"
    "LaTeX Warning: Reference `fig:flow' on page 2 undefined on input line 30.\n"
    "LaTeX Warning: Citation `smith2020' on page 3 undefined on input line 41.\n"
    "Package natbib Warning: Citation `doe19' on page 3 undefined on input line 44.\n"
    "Package biblatex Warning: The following entry could not be found\n"
    "(biblatex)                in the database:\n"
    "(biblatex)                roe2021\n"
)


def test_the_log_gives_errors_references_and_citations():
    whole = "Package natbib Warning: Citation `averyveryverylongcitationkey2024' on page 3 undefined on line 50."
    log = LOG + whole[:79] + "\n" + whole[79:] + "\n"  # TeX breaks log lines at 79 characters, mid-key here
    got = lt.parse_log(log, "error: main.tex:7: Missing $ inserted\nerror: halted on potentially-recoverable error")
    assert got["errors"] == [
        {"line": 12, "file": "", "message": "Undefined control sequence."},
        {"line": 7, "file": "main.tex", "message": "Missing $ inserted"},
    ]
    assert got["refs"] == ["fig:flow"]
    assert got["cites"] == ["smith2020", "doe19", "averyveryverylongcitationkey2024", "roe2021"]
    assert lt.parse_log("", "", 'Warning--I didn\'t find a database entry for "kim22"')["cites"] == ["kim22"]


def paper(folder: Path, extra: str = "") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "chapters").mkdir(exist_ok=True)
    (folder / "chapters" / "intro.tex").write_text(
        "Flows are hard to model. % a comment that isn't counted\nWe use $x^2 + y$ here \\cite{smith2020}.\n"
        "\\begin{equation}\n a = b + c\n\\end{equation}\n" + extra,
        encoding="utf-8",
    )
    main = folder / "main.tex"
    main.write_text(
        "\\documentclass{article}\n\\usepackage{amsmath}\n\\title{Preamble words}\n\\begin{document}\n"
        "\\section{Introduction}\n\\input{chapters/intro}\n\\bibliography{refs}\n\\end{document}\n",
        encoding="utf-8",
    )
    (folder / "refs.bib").write_text("@article{other1, title={Other}}\n", encoding="utf-8")
    return main


def test_words_are_prose_only_from_the_files_the_document_takes_in(tmp_path):
    main = paper(tmp_path / "thesis")
    (tmp_path / "thesis" / "unused.tex").write_text("many words never included anywhere at all", encoding="utf-8")
    assert [p.name for p in lt.tex_files(main)] == ["main.tex", "intro.tex"]
    # Introduction / Flows are hard to model / We use here: no preamble, comments, maths or commands
    assert lt.count_words(main) == 9
    assert lt.bib_files(main) == [(tmp_path / "thesis" / "refs.bib").resolve()]
    assert lt.cite_context(main, "smith2020") == "We use $x^2 + y$ here \\cite{smith2020}."
    assert lt.pick_main(tmp_path / "thesis")[0] == main
    (tmp_path / "thesis" / "talk.tex").write_text("\\documentclass{beamer}", encoding="utf-8")
    assert lt.pick_main(tmp_path / "thesis")[0] == main  # main.tex wins among several
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "a.tex").write_text("\\documentclass{article}", encoding="utf-8")
    (tmp_path / "other" / "b.tex").write_text("\\documentclass{article}", encoding="utf-8")
    p, why = lt.pick_main(tmp_path / "other")
    assert p is None and "2 documents there (a.tex, b.tex): name one" in why


class FakeTeX:
    """A stand-in engine: writes the log the test wants into the output folder, never into the document's."""

    def __init__(self, monkeypatch):
        self.log, self.calls = "", []
        real = proc.run

        def run(args, **kw):
            if args[0] != "/fake/tectonic":
                return real(args, **kw)
            self.calls.append((args, kw.get("cwd")))
            out = Path(args[args.index("--outdir") + 1])
            (out / (Path(args[-1]).stem + ".log")).write_text(self.log, encoding="utf-8")
            return proc.Result(1 if "! " in self.log else 0, "", "")

        monkeypatch.setattr(lt.proc, "run", run)
        monkeypatch.setattr(lt, "engine", lambda app: ("tectonic", "/fake/tectonic"))


def test_latex_attach_build_and_the_morning_line(env, tmp_path, monkeypatch):
    tex = FakeTeX(monkeypatch)
    folder = tmp_path / "thesis"
    main = paper(folder)
    env.on("research_addon")
    assert env.say(f"/latex add {tmp_path / 'nothing'}") == f"There's no folder {tmp_path / 'nothing'}."
    assert env.say(f"/latex add {folder}").startswith("Following thesis (main.tex): a build every night")
    assert env.app.settings.get("research_addon.latex_repos") == [{"path": str(folder.resolve()), "main": "main.tex"}]
    before = sorted(p.name for p in folder.rglob("*"))
    m = env.app.modules["research_addon"]

    m.nightly()  # the first night: it builds, 9 words
    (args, cwd) = tex.calls[-1]
    assert "--untrusted" in args and cwd == main.parent.resolve()
    assert sorted(p.name for p in folder.rglob("*")) == before  # nothing written beside your files
    assert m.morning() is None  # nothing broke, nothing to compare the words with yet

    st = m.latex.state()  # the count from the day before was 4 words less
    rec = st[lt.key(str(folder.resolve()))]
    rec["words"] = {(dt.date.today() - dt.timedelta(days=1)).isoformat(): 5, **rec["words"]}
    m.latex.save(st)
    (folder / "chapters" / "intro.tex").write_text(
        (folder / "chapters" / "intro.tex").read_text() + "More words written today.\n", encoding="utf-8"
    )
    tex.log = LOG
    m.nightly()  # the next night: an error, a missing reference and citations, and words written
    text = m.morning()
    assert text.startswith(
        "LaTeX: thesis: 1 error: Undefined control sequence. (line 12); undefined reference fig:flow"
    )
    assert "missing citations smith2020, doe19, roe2021; +8 words. (/latex for the rest)" in text
    last = env.fake.sent[-1][1]
    assert "BibTeX for smith2020" in json.dumps(last.get("reply_markup"))
    assert m.morning() is None  # said once

    status = env.say("/latex")
    assert "thesis (main.tex): 1 error" in status and "missing citations: smith2020, doe19, roe2021" in status
    assert "13 words (+8 since the day before)" in status
    assert env.say(f"/latex remove {folder}") == f"Stopped following {folder}. Your files are as they were."
    assert env.app.settings.get("research_addon.latex_repos") == []


def test_no_engine_says_how_to_get_one(env, tmp_path, monkeypatch):
    monkeypatch.setattr(lt, "engine", lambda app: None)
    paper(tmp_path / "p")
    env.on("research_addon")
    env.say(f"/latex add {tmp_path / 'p'}")
    assert "/latex install fetches Tectonic" in env.say("/latex build")
    m = env.app.modules["research_addon"]
    assert m.health() == (False, "the LaTeX tracker needs Tectonic or LaTeX: /latex install")


@pytest.mark.skipif(not (shutil.which("latexmk") and shutil.which("pdflatex")), reason="needs LaTeX")
def test_a_real_build_with_the_computers_own_latex(env, tmp_path, monkeypatch):
    from kurooto.modules import skills

    monkeypatch.setattr(skills, "tectonic", lambda app: None)
    folder = tmp_path / "real"
    folder.mkdir()
    main = folder / "main.tex"
    main.write_text(
        "\\documentclass{article}\n\\begin{document}\nSee section \\ref{sec:none} and \\cite{nobody99}.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    if lt.engine(env.app) is None:
        pytest.skip("this Python's PATH has no LaTeX")
    got = lt.build(env.app, main, tmp_path / "out", timeout=300)
    assert got["engine"] in ("latexmk", "pdflatex") and got["refs"] == ["sec:none"] and got["cites"] == ["nobody99"]
    assert sorted(p.name for p in folder.iterdir()) == ["main.tex"]


def test_a_bibtex_entry_needs_a_tap_to_ask_and_a_tap_to_write(env, tmp_path, monkeypatch):
    from kurooto.providers.base import Result, Verdict

    FakeTeX(monkeypatch).log = LOG
    folder = tmp_path / "thesis"
    paper(folder)
    env.on("research_addon")
    env.say(f"/latex add {folder}")
    m = env.app.modules["research_addon"]
    m.nightly()
    m.morning()
    ref = next(p["key"] and r for r, p in m.latex.state()["_pending"].items() if p["key"] == "smith2020")
    assert env.app.callback(f"rlx:{ref}:bib") == "Suggestions come from your AI: turn on Chat first."
    asked = []
    monkeypatch.setattr(env.app.jobs, "submit", lambda prompt, **kw: asked.append((prompt, kw)) or "j1")
    real_on = env.app.is_on
    monkeypatch.setattr(env.app, "is_on", lambda i: i == "chat" or real_on(i))
    assert env.app.callback(f"rlx:{ref}:bib") == "Asking your AI about smith2020…"
    prompt, kw = asked[-1]
    assert "`smith2020`" in prompt and "We use $x^2 + y$ here" in prompt and kw["then"] == "research_addon.bibtex"
    bib = folder / "refs.bib"
    was = bib.read_text(encoding="utf-8")
    answer = "Likely this one:\n```bibtex\n@article{Smith2020flows,\n  title={Flows {in} pipes},\n  year={2020}\n}\n```"
    m._bibtex_came(None, Result(Verdict.OK, answer), kw["then_payload"])
    sent = env.fake.sent[-1][1]
    assert "@article{smith2020,\n  title={Flows {in} pipes},\n  year={2020}\n}" in sent["text"]
    assert "Add to refs.bib" in json.dumps(sent["reply_markup"])
    assert bib.read_text(encoding="utf-8") == was  # nothing written before the tap
    assert env.app.callback(f"rlx:{ref}:add") == "Added smith2020 to refs.bib."
    after = bib.read_text(encoding="utf-8")
    assert after.startswith(was) and "@article{smith2020," in after and "suggested by your AI" in after
    assert env.app.callback(f"rlx:{ref}:add") == "There's no entry to add."
    assert (
        lt.add_entry(bib, "smith2020", "@misc{smith2020}")
        == "refs.bib has an entry for smith2020 already; left as it is."
    )
    assert lt.entry_from("I can't tell which work it is.", "k") == ""


# ================================================================================================ the bundle
class Crosswalk(Module):
    id = "notation_test"
    title = "Notation crosswalk"
    extra = True
    bundle = "research_addon"


def test_one_switch_turns_the_group_on_and_off(env, monkeypatch):
    app = env.app
    monkeypatch.setitem(app.modules, "notation_test", Crosswalk(app))
    ok, _ = app.enable("research_addon")
    assert ok and app.is_on("notation_test")  # the member came on with it
    card = app.modules["research_addon"].card()
    assert [t["id"] for t in card["toggles"]] == ["run_compare", "latex", "m:notation_test"]
    m = app.modules["research_addon"]
    assert m.card_action("m:notation_test", False) == "Notation crosswalk is off."
    assert app.settings.get("research_addon.members_off") == ["notation_test"]
    app.disable("research_addon")
    app.enable("research_addon")
    assert not app.is_on("notation_test")  # switched off on the card: it stays off
    assert m.card_action("m:notation_test", True) == "Notation crosswalk is on."
    assert app.settings.get("research_addon.members_off") == []
    app.disable("research_addon")
    assert not app.is_on("notation_test")  # and goes off with it
    assert m.card_action("latex", False) == "LaTeX tracker: off."
    app.enable("research_addon")
    assert env.say("/latex") == "The LaTeX tracker is off: switch it on on the Research add-on's card."


def test_the_add_on_is_one_card_among_the_add_ons(env, monkeypatch):
    from kurooto.web.api import Api

    monkeypatch.setitem(env.app.modules, "notation_test", Crosswalk(env.app))
    rows = {r["id"]: r for r in Api(env.app)._modules()}
    assert rows["research_addon"]["extra"] and rows["research_addon"]["bundle"] == ""
    from kurooto.web.api import STARTER

    assert "research_addon" not in STARTER
