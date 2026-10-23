import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeOllama:
    def __init__(self):
        self.models, self.pulled = set(), []
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                body = json.dumps({"models": [{"name": m} for m in sorted(fake.models)]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.pulled.append(req["model"])
                fake.models.add(req["model"])
                self.send_response(200)
                self.end_headers()
                for done in (0, 50, 100):
                    self.wfile.write(
                        json.dumps({"status": "pulling", "total": 100, "completed": done}).encode() + b"\n"
                    )
                self.wfile.write(b'{"status":"success"}\n')

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


def test_pulls_the_profile_models_and_wires_them_up(env, monkeypatch):
    fake = FakeOllama()
    try:
        monkeypatch.setattr("kurooto.modules.local_models.OLLAMA", fake.url)
        app = env.app
        lm = app.modules["local_models"]
        (app.paths.state / "hardware.json").write_text(
            json.dumps(
                {
                    "recommendation": {
                        "local_models": [
                            {"key": "embed", "tag": "nomic-embed-text", "size_gb": 0.27, "use": "x"},
                            {"key": "helper-small", "tag": "qwen3:4b-instruct-2507-q4_K_M", "size_gb": 2.5, "use": "y"},
                        ]
                    }
                }
            )
        )
        monkeypatch.setattr(lm.prereqs.items["ollama"], "find", lambda: "/x/ollama")
        monkeypatch.setattr(
            lm.prereqs,
            "room",
            lambda keys, extra_gb=0: {"ok": True, "need_gb": extra_gb, "free_gb": 99, "margin_gb": 5},
        )
        lines = []
        ok, msg = lm.setup(progress=lines.append)
        assert ok, msg
        assert fake.pulled == ["nomic-embed-text", "qwen3:4b-instruct-2507-q4_K_M"]
        assert any("100%" in ln for ln in lines)
        assert app.settings.get("brain.classify") == "ollama"
        assert app.settings.get("brain.models")["ollama"]["low"] == "qwen3:4b-instruct-2507-q4_K_M"
        assert lm.setup(progress=lambda s: None)[0] and fake.pulled.count("nomic-embed-text") == 1  # nothing twice
    finally:
        fake.server.shutdown()


def test_not_offered_on_light_computers(env):
    lm = env.app.modules["local_models"]
    (env.app.paths.state / "hardware.json").write_text(json.dumps({"recommendation": {"local_models": []}}))
    ok, why = lm.ready()
    assert not ok and "better off without" in why


def test_no_model_stays_half_on_the_processor(env, monkeypatch):
    lm = env.app.modules["local_models"]
    gone = []
    monkeypatch.setattr(lm, "unload", lambda name: gone.append(name))
    rows = [{"name": "embed", "size": 300, "vram": 300}, {"name": "helper", "size": 6000, "vram": 3000}]
    monkeypatch.setattr(lm, "loaded", lambda: rows)
    assert lm.guard() == ["unloaded embed, helper"] and gone == ["embed", "helper"]  # reloads fully on the card next
    rows[:] = [{"name": "big", "size": 9000, "vram": 6000}]  # too big even alone: told once
    assert lm.guard() == ["told: big 33% on the processor"]
    assert "doesn't fit your graphics card" in env.fake.texts()[-1]
    assert lm.guard() == []  # not twice
    rows[:] = [{"name": "helper", "size": 6000, "vram": 6000}]
    assert lm.guard() == [] and "100% on the graphics card" in lm._status(None, "")
