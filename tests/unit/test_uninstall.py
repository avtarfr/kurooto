"""What Kurooto installed, and taking it away again (core/uninstall.py), with fake installs in a scratch home: only
what an install made goes on the receipt, never what was there before; removing never goes past the receipt; turning a
feature off offers Remove / Keep, and nothing goes without the tap (uninstall.offer switches the offer off)."""

import json
import sys
from pathlib import Path

import pytest

from kurooto.core import uninstall
from kurooto.core.prereqs import Prereqs

OSN = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")


@pytest.fixture(autouse=True)
def no_real_ollama(monkeypatch):
    """Never the real Ollama on this computer: a fake list of models, and deletes that only write down."""
    state = {"tags": None, "deleted": []}
    monkeypatch.setattr("kurooto.modules.local_models.OLLAMA", "http://127.0.0.1:9")  # nothing listens there
    monkeypatch.setattr(uninstall, "_ollama_tags", lambda: state["tags"])

    def delete(tags, exe):
        state["deleted"] += list(tags)
        if state["tags"] is not None:
            for t in tags:
                state["tags"].pop(t, None)
        return {t: True for t in tags}

    monkeypatch.setattr(uninstall, "_ollama_delete", delete)
    monkeypatch.setattr(uninstall, "_spawn", lambda fn: fn())  # the removal runs here, not in a thread
    return state


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    (h / ".local" / "bin").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    return h


def fake(tmp_path, step, programs=("faketool",), dirs=(), owns=(), features=("books",)):
    manifest = {
        "thing": {
            "title": "Fake tool",
            "size_gb": 0.01,
            "programs": list(programs),
            "dirs": {OSN: list(dirs)},
            "owns": {OSN: list(owns)},
            "features": list(features),
            "install": {OSN: step},
        }
    }
    return Prereqs(tmp_path / "app", tmp_path / "cache", manifest=manifest)


def script_that(monkeypatch, pre, make):
    """kind "script": the vendor's script is `make` (it puts files somewhere)."""
    monkeypatch.setattr(pre, "room", lambda keys, **k: {"ok": True, "need_gb": 0, "free_gb": 99, "margin_gb": 5})
    monkeypatch.setattr(pre, "_script", lambda p: (make() or True, ""))


def exe(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)


# ---------------------------------------------------------------------------------------------- the receipt
def test_only_what_the_install_made_goes_on_the_receipt(tmp_path, home, monkeypatch):
    mine = home / ".local" / "bin" / "mytool"  # yours, there before
    exe(mine)
    (home / ".fakebun-yours").mkdir()
    pre = fake(
        tmp_path,
        {"kind": "script", "script": "x"},
        dirs=[str(home / ".local" / "bin")],
        owns=[str(home / ".fakebun"), str(home / ".fakebun-yours")],
    )
    monkeypatch.setenv("PATH", "/nonexistent")

    def vendor():
        exe(home / ".local" / "bin" / "faketool")
        (home / ".local" / "bin" / "unrelated").write_text("another program's, made meanwhile")
        (home / ".fakebun" / "bin").mkdir(parents=True)
        (home / ".fakebun" / "bin" / "x").write_text("x" * 1000)

    script_that(monkeypatch, pre, vendor)
    ok, msg = pre.install("thing", progress=lambda s: None)
    assert ok, msg
    it = uninstall.load(pre.app_dir)["program:thing"]
    assert it["paths"] == [str(home / ".local" / "bin" / "faketool")]
    assert it["owns"] == [str(home / ".fakebun")]  # not the one that was there before
    assert it["features"] == ["books"] and it["bytes"] > 1000

    ts = uninstall.things(pre.app_dir, pre)
    assert [t.name for t in ts] == ["thing"]
    ok, lines = uninstall.remove(pre.app_dir, ts, say=lambda s: None)
    assert ok, lines
    assert not (home / ".local" / "bin" / "faketool").exists() and not (home / ".fakebun").exists()
    assert mine.exists() and (home / ".local" / "bin" / "unrelated").exists() and (home / ".fakebun-yours").exists()
    assert (home / ".local" / "bin").is_dir()  # a shared folder is never removed
    assert uninstall.load(pre.app_dir) == {}


def test_a_program_that_was_there_before_is_never_on_the_receipt(tmp_path, home, monkeypatch):
    pre = fake(tmp_path, {"kind": "script", "script": "x"}, dirs=[str(home / ".local" / "bin")])
    exe(home / ".local" / "bin" / "faketool")  # yours
    monkeypatch.setenv("PATH", "/nonexistent")
    script_that(monkeypatch, pre, lambda: pytest.fail("never installed again"))
    ok, msg = pre.install("thing", progress=lambda s: None)
    assert ok and "already" in msg
    assert uninstall.load(pre.app_dir) == {} and uninstall.things(pre.app_dir, pre) == []


def test_an_unpacked_program_in_kuroots_folder(tmp_path, home, monkeypatch):
    app = tmp_path / "app"
    pre = fake(
        tmp_path,
        {"kind": "download-tar", "url": "https://example.invalid/t.tar.gz", "into": "{app}/fake/bin"},
        dirs=["{app}/fake/bin"],
    )
    monkeypatch.setenv("PATH", "/nonexistent")
    monkeypatch.setattr(pre, "room", lambda keys, **k: {"ok": True, "need_gb": 0, "free_gb": 99, "margin_gb": 5})
    monkeypatch.setattr(pre, "_download", lambda url, progress, sha256=None: tmp_path / "t.tar.gz")
    monkeypatch.setattr(pre, "_untar", lambda f, dest, strip=0: exe(dest / "faketool"))
    assert pre.install("thing", progress=lambda s: None)[0]
    assert uninstall.load(app)["program:thing"]["paths"] == [str(app / "fake")]


def test_a_package_only_when_it_was_not_there(tmp_path, home, monkeypatch):
    pre = fake(tmp_path, {"kind": "bun-global", "spec": "github:x/faketool#v1"}, dirs=[str(home / ".bun" / "bin")])
    p = pre.items["thing"]
    assert uninstall.look(pre, p)["package"] is False
    (home / ".bun" / "install" / "global" / "node_modules" / "faketool").mkdir(parents=True)  # yours already
    before = uninstall.look(pre, p)
    assert before["package"] is True
    exe(home / ".bun" / "bin" / "faketool")
    entry = uninstall.record_program(pre, p, before, str(home / ".bun" / "bin" / "faketool"))
    assert entry is not None and entry["package"] == {}  # its link in ~/.bun/bin is new, the package isn't


def test_never_past_the_receipt_even_when_it_was_tampered_with(tmp_path, home):
    app = tmp_path / "app"
    app.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    uninstall._write(
        app,
        {
            "program:evil": {
                "kind": "program",
                "key": "evil",
                "title": "Evil",
                "paths": [str(home), str(home / ".local" / "bin"), str(outside), str(app), str(app.parent)],
                "owns": [str(home / "Documents")],
                "package": {},
                "uninstaller": [],
            }
        },
    )
    (home / "Documents").mkdir()
    ts = uninstall.things(app)
    ok, _ = uninstall.remove(app, ts, say=lambda s: None)
    for p in (home, home / ".local" / "bin", outside, app, home / "Documents"):
        assert p.exists(), p
    for p in (home, home / ".local", home / ".local" / "bin", home / "Desktop", outside, app, app.parent):
        assert not uninstall.safe(p, app), p
    assert uninstall.safe(home / ".bun", app) and uninstall.safe(app / "node", app)


def test_what_you_removed_yourself_leaves_the_receipt(tmp_path, home):
    app = tmp_path / "app"
    gone = home / ".gone"
    uninstall._put(app, "program:gone", {"kind": "program", "key": "gone", "title": "Gone", "paths": [str(gone)]})
    assert uninstall.things(app) == [] and uninstall.load(app) == {}


def test_ollamas_store_keeps_models_you_pulled_yourself(tmp_path, home):
    store = home / ".ollama"
    (store / "models" / "manifests" / "registry" / "library" / "mine").mkdir(parents=True)
    (store / "models" / "manifests" / "registry" / "library" / "mine" / "latest").write_text("{}")
    assert uninstall._still_holds("ollama", store, set())
    (store / "models" / "manifests" / "registry" / "library" / "mine" / "latest").unlink()
    assert not uninstall._still_holds("ollama", store, set())
    bun = home / ".bun" / "install" / "global"
    bun.mkdir(parents=True)
    (bun / "package.json").write_text(json.dumps({"dependencies": {"gbrain": "x", "yours": "1"}}))
    assert "yours" in uninstall._still_holds("bun", home / ".bun", {"gbrain"})


# ---------------------------------------------------------------------------------------------- models
def test_a_model_is_on_the_receipt_only_when_ollama_did_not_have_it(env, monkeypatch, no_real_ollama):
    lm = env.app.modules["local_models"]

    class Stream:
        def __enter__(self):
            return iter([b'{"status":"success"}\n'])

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(lm, "api", lambda path, body=None, timeout=10: Stream())
    monkeypatch.setattr(lm, "have", lambda: {"yours:latest"})
    assert lm.pull("yours", 1.0, progress=lambda s: None)[0]
    assert lm.pull("new-model:7b", 2.0, progress=lambda s: None, by="local_helper")[0]
    items = uninstall.load(env.app.paths.app)
    assert list(items) == ["model:new-model:7b"] and items["model:new-model:7b"]["features"] == ["local_helper"]


def receipt_model(app, tag, by="local_models", size=3 * 1024**3):
    uninstall.record_model(app.paths.app, tag, size, by)


def test_turning_a_feature_off_offers_what_it_installed_and_only_a_tap_removes_it(env, home, no_real_ollama):
    app = env.app
    tool = home / ".local" / "bin" / "tesseract"
    exe(tool)
    uninstall._put(
        app.paths.app,
        "program:tesseract",
        {"kind": "program", "key": "tesseract", "title": "Tesseract OCR", "paths": [str(tool)], "features": ["books"]},
    )
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "books"])
    ok, msg = app.disable("books")
    assert ok and "Tesseract OCR" in msg and "waiting for you" in msg
    qs = app.ask.pending(source="uninstall")
    assert len(qs) == 1 and qs[0]["choices"][1] == "Keep" and qs[0]["choices"][0].startswith("Remove (")
    assert tool.exists()  # nothing without the tap
    app.ask.answer(qs[0]["id"], "Keep", via="test")
    assert tool.exists() and uninstall.load(app.paths.app)

    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "books"])
    app.disable("books")
    q = app.ask.pending(source="uninstall")[0]
    out = app.ask.answer(q["id"], q["choices"][0], via="test")
    assert out["ok"] and "Removing" in out["note"]
    assert not tool.exists() and uninstall.load(app.paths.app) == {}


def test_what_another_feature_still_uses_is_not_offered(env, home):
    app = env.app
    tool = home / ".local" / "bin" / "tesseract"
    exe(tool)
    uninstall._put(
        app.paths.app,
        "program:tesseract",
        {"kind": "program", "key": "tesseract", "title": "Tesseract OCR", "paths": [str(tool)]},
    )
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "books", "handwritten"])
    ok, msg = app.disable("books")
    assert ok and msg == "Books and PDFs is off"
    assert app.ask.pending(source="uninstall") == []


def test_the_switch_turns_the_offer_off(env, home):
    app = env.app
    receipt_model(app, "gemma-test:4b", by="local_helper")
    app.settings.set("uninstall.offer", False)
    assert uninstall.after_off(app, "local_helper") == ""
    app.settings.set("uninstall.offer", True)
    assert "gemma-test:4b" in uninstall.after_off(app, "local_helper")
    assert uninstall.after_off(app, "local_helper") == ""  # never asked twice while a question waits


def test_a_model_in_use_is_never_offered_and_a_tap_rechecks(env, no_real_ollama):
    app = env.app
    no_real_ollama["tags"] = {"gemma-test:4b": 5, "other:1b": 7}
    receipt_model(app, "gemma-test:4b", by="local_helper")
    receipt_model(app, "other:1b", by="local_models")
    app.settings.set("brain.main", "ollama")
    app.settings.set("brain.models", {"ollama": {"low": "gemma-test:4b"}})
    said = uninstall.after_hardware(app)
    assert "other:1b" in said and "gemma-test:4b" not in said
    q = app.ask.pending(source="uninstall")[0]
    app.settings.set("brain.models", {"ollama": {"low": "other:1b"}})  # used again before the tap
    out = app.ask.answer(q["id"], q["choices"][0], via="test")
    assert "uses it now" in out["note"] and no_real_ollama["deleted"] == []


def test_removing_ollama_takes_its_models_and_the_helper_model_goes_on_a_tap(env, home, no_real_ollama):
    app = env.app
    no_real_ollama["tags"] = {"gemma-test:4b": 5}
    receipt_model(app, "gemma-test:4b", by="local_helper")
    d = app.paths.app / "ollama"
    exe(d / "bin" / "ollama")
    uninstall._put(
        app.paths.app,
        "program:ollama",
        {"kind": "program", "key": "ollama", "title": "Ollama", "paths": [str(d)], "owns": []},
    )
    msg = uninstall.after_off(app, "local_helper")
    assert "Ollama" in msg and "gemma-test:4b" in msg
    q = app.ask.pending(source="uninstall")[0]
    app.ask.answer(q["id"], q["choices"][0], via="test")
    assert no_real_ollama["deleted"] == ["gemma-test:4b"] and not d.exists()
    assert uninstall.load(app.paths.app) == {}


def test_installed_lists_and_buttons_ask_first(env, home):
    app = env.app
    receipt_model(app, "gemma-test:4b", by="local_helper")
    (app.paths.app / "voice" / "models").mkdir(parents=True)
    (app.paths.app / "voice" / "models" / "m.onnx").write_bytes(b"x" * 2048)
    text, buttons = uninstall.command(app)
    assert "gemma-test:4b" in text and "Voice's speech packages" in text
    cb = buttons[0][0][1]
    assert cb.startswith("uni:")
    _, ref, act = cb.split(":")
    assert app.callback(f"uni:{ref}:{act}") == "Asked: Remove or Keep."
    assert app.ask.pending(source="uninstall") and (app.paths.app / "voice").exists()


# ---------------------------------------------------------------------------------------------- the CLI
def test_cli_installed_and_remove(env, home, capsys, monkeypatch):
    from kurooto import cli

    app = env.app
    tool = home / ".local" / "bin" / "kitty"
    exe(tool)
    uninstall._put(
        app.paths.app,
        "program:kitty",
        {"kind": "program", "key": "kitty", "title": "kitty", "paths": [str(tool)]},
    )
    assert cli.main(["installed"]) == 0
    assert "kitty" in capsys.readouterr().out
    assert cli.main(["remove", "nothing-like-it"]) == 2
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert cli.main(["remove", "kitty"]) == 1 and tool.exists()  # no terminal to answer in, no --yes
    assert cli.main(["remove", "kitty", "--yes"]) == 0 and not tool.exists()


def test_uninstall_follows_the_receipt_unless_told_not_to(tmp_path, home, monkeypatch):
    from kurooto import cli

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "k"))
    app = tmp_path / "k" / "app"
    tool = home / ".local" / "bin" / "faketool"
    exe(tool)
    uninstall._put(app, "program:thing", {"kind": "program", "key": "thing", "title": "Fake", "paths": [str(tool)]})
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    cli.uninstall_receipt(yes=False)
    assert not tool.exists()
