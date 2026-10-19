import json

from kurooto.core import proc


def fake_runner(calls, outputs=None):
    def run(args, **kw):
        calls.append((args[1:], kw.get("env", {})))
        out = (outputs or {}).get(args[1], "")
        return proc.Result(0, out, "")

    return run


def test_setup_creates_the_brain_with_the_right_index(env, monkeypatch):
    app = env.app
    g = app.modules["gbrain"]
    monkeypatch.setattr(g.prereqs.items["bun"], "find", lambda: "/x/bun")
    monkeypatch.setattr(g.prereqs.items["gbrain"], "find", lambda: "/x/gbrain")
    (app.paths.state / "hardware.json").write_text(json.dumps({"recommendation": {"embeddings": "ollama"}}))
    calls = []
    monkeypatch.setattr("kurooto.modules.gbrain.proc.run", fake_runner(calls, {"import": "  2 pages imported\n"}))
    ok, msg = g.setup(progress=lambda s: None)
    assert ok and "2 pages imported" in msg
    cmds = [c[0] for c in calls]
    assert cmds[0] == ["init", "--pglite", "--no-embedding"]
    assert ["embeddings", "enable", "--embedding-model", "ollama:nomic-embed-text"] in cmds
    assert cmds[-1] == ["import", str(app.workspace)]  # with embeddings on, the import embeds too
    assert all(c[1]["GBRAIN_HOME"] == str(g.home) for c in calls)  # never the user's own ~/.gbrain
    assert app.enable("gbrain") == (True, "Notes brain (GBrain) is on")


def test_no_gpu_and_no_key_means_keyword_only(env, monkeypatch):
    g = env.app.modules["gbrain"]
    monkeypatch.setattr(g.prereqs.items["bun"], "find", lambda: "/x/bun")
    monkeypatch.setattr(g.prereqs.items["gbrain"], "find", lambda: "/x/gbrain")
    calls = []
    monkeypatch.setattr("kurooto.modules.gbrain.proc.run", fake_runner(calls))
    assert g.embeddings() == "off"
    g.setup(progress=lambda s: None)
    assert not any(c[0][:2] == ["embeddings", "enable"] for c in calls)
    assert calls[-1][0][-1] == "--no-embed"
    env.app.secrets.set("gemini.api_key", "k")
    assert g.embeddings() == "gemini"


def test_notes_command(env, monkeypatch):
    g = env.app.modules["gbrain"]
    monkeypatch.setattr(g.prereqs.items["gbrain"], "find", lambda: "/x/gbrain")
    (env.app.paths.state / "gbrain.json").write_text(json.dumps({"initialised": True, "embeddings": "off"}))
    monkeypatch.setattr(
        "kurooto.modules.gbrain.proc.run", fake_runner([], {"query": "[0.91] topology/compactness -- # Compactness"})
    )
    env.on("gbrain")
    assert "topology/compactness" in env.say("/notes what is compactness")
