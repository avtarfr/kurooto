"""The GPU reranker (a local model's odds for "yes" on each candidate note) and going past what the hardware detection
suggests (another setup, models of your own, programs to install). Fakes only: a fake Ollama, fake machines."""

import json
import math
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from kurooto.core import conceptgraph as cg
from kurooto.core import hardware, rerank


# ----------------------------------------------------------------------------------------------- a fake Ollama
class FakeOllama:
    """/api/generate answers yes or no with token probabilities, chosen by a word in the prompt."""

    def __init__(self, yes_if="gradient", fail=False):
        self.yes_if, self.fail, self.prompts = yes_if, fail, []
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                fake.prompts.append(body)
                if fake.fail:
                    self.send_response(500)
                    self.end_headers()
                    return
                doc = body["prompt"].split("EXISTING NOTE:")[1]
                yes = fake.yes_if in doc.lower()
                py = 0.97 if yes else 0.03
                top = [
                    {"token": "yes", "logprob": math.log(py)},
                    {"token": "no", "logprob": math.log(1 - py)},
                ]
                out = {
                    "response": "yes" if yes else "no",
                    "logprobs": [{"token": "yes" if yes else "no", "logprob": 0.0, "top_logprobs": top}],
                }
                data = json.dumps(out).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


@pytest.fixture
def ollama():
    f = FakeOllama()
    yield f
    f.close()


def note(slug, title, summary, links=()):
    return cg.Note(slug, None, title, [], summary, summary, set(links), "h")


def test_odds_come_from_token_probabilities_and_fall_back_to_the_word():
    top = [{"token": "yes", "logprob": math.log(0.9)}, {"token": "No", "logprob": math.log(0.1)}]
    assert abs(rerank.odds_yes([{"top_logprobs": top}], "") - 0.9) < 1e-6
    assert rerank.odds_yes(None, "Yes.") == 1.0 and rerank.odds_yes(None, "no") == 0.0
    assert rerank.odds_yes(None, "perhaps") is None


def test_the_reranker_scores_each_pair_with_the_local_model(ollama):
    r = rerank.Reranker("helper", ollama.base)
    got = r.scores("backpropagation of the error gradient", ["Gradient descent moves downhill", "The Poisson law"])
    assert got[0] > 0.9 and got[1] < 0.1
    assert ollama.prompts[0]["model"] == "helper" and ollama.prompts[0]["options"]["temperature"] == 0
    assert ollama.prompts[0]["logprobs"] is True


def test_it_gives_up_after_repeated_failures_instead_of_slowing_everything():
    f = FakeOllama(fail=True)
    try:
        r = rerank.Reranker("helper", f.base)
        assert r.scores("q", ["a", "b", "c", "d", "e"]) == [None] * 5
        assert r.dead and len(f.prompts) == rerank.MAX_FAILS
    finally:
        f.close()


def test_rerank_puts_real_matches_first_keeps_exact_names_and_drops_sure_misses(ollama):
    notes = {
        "zettel/gradient-descent": note("zettel/gradient-descent", "Gradient descent", "Moves against the gradient."),
        "zettel/poisson": note("zettel/poisson", "Poisson law", "Counts of rare events in a fixed interval."),
        "zettel/backpropagation": note("zettel/backpropagation", "Backpropagation", "Computes gradients of the error."),
    }
    idx = cg.Index(notes, reranker=rerank.Reranker("helper", ollama.base))
    # the keyword order alone would put the Poisson note first for this query
    got = idx.candidates("rare events and the gradient of an error", "Backprop", ["backpropagation"], limit=3)
    slugs = [c.slug for c in got]
    assert slugs[0] == "zettel/backpropagation" and got[0].exists  # an alias match stays on top
    assert "zettel/poisson" not in slugs  # the model is sure it doesn't belong
    gd = next(c for c in got if c.slug == "zettel/gradient-descent")
    assert gd.rerank > 0.9 and "rerank" in gd.evidence


def test_without_a_reranker_or_when_it_is_down_the_order_is_unchanged(ollama):
    notes = {"zettel/a": note("zettel/a", "Alpha rate", "alpha alpha"), "zettel/b": note("zettel/b", "Beta", "alpha")}
    plain = [c.slug for c in cg.Index(notes).candidates("alpha", limit=2)]
    down = FakeOllama(fail=True)
    try:
        idx = cg.Index(notes, reranker=rerank.Reranker("helper", down.base))
        assert [c.slug for c in idx.candidates("alpha", limit=2)] == plain
    finally:
        down.close()


def test_make_reranker_needs_a_helper_model_that_is_there(monkeypatch):
    class LM:
        def __init__(self, wanted, up=True, have=("gemma4:e4b",)):
            self._w, self._up, self._h = wanted, up, set(have)

        def wanted(self):
            return self._w

        def running(self):
            return self._up

        def have(self):
            return self._h

    class Settings:
        def __init__(self, **kv):
            self.kv = kv

        def get(self, k):
            return self.kv.get(k)

    class App:
        def __init__(self, lm, **kv):
            self.modules = {"local_models": lm}
            self.settings = Settings(**kv)

    helper = [{"key": "embed", "tag": "nomic-embed-text"}, {"key": "helper-large", "tag": "gemma4:e4b"}]
    assert rerank.make_reranker(App(LM(helper))).model == "gemma4:e4b"
    assert rerank.make_reranker(App(LM([helper[0]]))) is None  # a profile without a helper model: none
    assert rerank.make_reranker(App(LM(helper, up=False))) is None  # Ollama isn't running
    assert rerank.make_reranker(App(LM(helper, have=()))) is None  # not downloaded
    assert rerank.make_reranker(App(LM(helper), **{"integrate.rerank": "off"})) is None
    got = rerank.make_reranker(App(LM(helper, have=("custom-rr",)), **{"integrate.rerank_model": "custom-rr"}))
    assert got.model == "custom-rr"


# -------------------------------------------------------------------------------------- going past the hardware
def machine(vram=8.0, ram=24.0, apple=False):
    gpus = [
        hardware.GPU("Apple M2" if apple else "NVIDIA RTX", None if apple else vram, "apple" if apple else "nvidia")
    ]
    return hardware.Machine(
        "macos" if apple else "linux",
        "x",
        "arm64" if apple else "x86_64",
        "cpu",
        8,
        16,
        ram,
        gpus,
        100.0,
        "/",
        True,
        True,
    )


def test_a_machine_survives_a_round_trip_through_its_saved_form():
    m = machine()
    assert hardware.Machine.from_dict(m.to_dict()) == m


def test_forcing_a_bigger_setup_adds_its_models_with_plain_warnings():
    m = machine(vram=8.0)
    base = hardware.recommend(m)
    assert base.profile == "big-gpu" and not any("wants about" in n for n in base.notes)
    forced = hardware.recommend(m, force="big-gpu-12")
    assert forced.profile == "big-gpu-12" and any(x["key"] == "vision" for x in forced.local_models)
    assert any('chose the "big-gpu-12"' in n for n in forced.notes)
    assert any("gemma4:12b wants about 11.5 GB" in n for n in forced.notes)  # a warning, never a refusal


def test_models_you_add_are_kept_with_their_size_and_warned_about_when_too_big():
    m = machine(vram=8.0)
    rec = hardware.recommend(m, extra=["gemma4:12b", {"tag": "tiny:1b", "size_gb": 0.8}], sizes={"gemma4:12b": 8.0})
    tags = {x["tag"]: x for x in rec.local_models}
    assert tags["gemma4:12b"]["extra"] and tags["gemma4:12b"]["size_gb"] == 8.0 and tags["tiny:1b"]["size_gb"] == 0.8
    assert any("gemma4:12b" in n and "bigger than your 8 GB" in n for n in rec.notes)
    assert not any("tiny:1b" in n for n in rec.notes)


def test_no_graphics_card_still_works_with_a_warning_not_a_refusal():
    m = machine(vram=0.0, ram=16.0)
    m.gpus = []
    rec = hardware.recommend(m, force="small-gpu", extra=["qwen3:4b"], sizes={"qwen3:4b": 2.5})
    assert rec.profile == "small-gpu" and any("processor" in n for n in rec.notes)
    assert hardware.recommend(m, force="not-a-profile").profile == "light"  # an unknown name is ignored


def test_current_applies_your_overrides_each_time(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "home"))
    from kurooto.app import App

    app = App()
    try:
        monkeypatch.setattr(hardware, "detect", lambda app_dir=None: machine(vram=8.0))
        monkeypatch.setattr(hardware, "registry_size_gb", lambda tag: 3.0)
        assert hardware.current(app)["recommendation"]["profile"] == "big-gpu"
        app.settings.set("hardware.force_profile", "big-gpu-12")
        app.settings.set("hardware.extra_models", ["mine:7b"])
        rec = hardware.current(app)["recommendation"]
        assert rec["profile"] == "big-gpu-12"
        assert [x["size_gb"] for x in rec["local_models"] if x["tag"] == "mine:7b"] == [3.0]
        lm = app.modules["local_models"]
        assert {"vision", "extra:mine:7b"} <= {x["key"] for x in lm.wanted()}  # the module installs these too
    finally:
        app.close()


def test_the_command_sets_the_override_and_installs_what_you_asked_for(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "home"))
    from kurooto import cli
    from kurooto.modules import local_models

    monkeypatch.setattr(hardware, "detect", lambda app_dir=None: machine(vram=8.0))
    monkeypatch.setattr(hardware, "registry_size_gb", lambda tag: 2.0)
    done = {}

    def fake_setup(self, progress=print):
        done["wanted"] = [m["tag"] for m in self.wanted()]
        done["prereqs"] = list(self.app.settings.get("hardware.extra_prereqs") or [])
        progress("Downloading")
        return True, "ready"

    monkeypatch.setattr(local_models.LocalModels, "setup", fake_setup)
    rc = cli.main(
        ["hardware", "--profile", "big-gpu-12", "--add", "gemma4:12b", "--add-prereq", "tesseract", "--install"]
    )
    out = capsys.readouterr().out
    assert rc == 0 and "chosen by you" in out and "Done: ready" in out
    assert "gemma4:12b" in done["wanted"] and done["prereqs"] == ["tesseract"]
    assert cli.main(["hardware", "--profile", "auto", "--remove", "gemma4:12b", "--remove-prereq", "tesseract"]) == 0
    assert "detected" in capsys.readouterr().out
    assert cli.main(["hardware", "--profile", "nonsense"]) == 2


def test_the_page_can_set_the_override_and_start_the_install(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "home"))
    from kurooto.app import App
    from kurooto.modules import local_models
    from kurooto.web.api import Api

    monkeypatch.setattr(hardware, "detect", lambda app_dir=None: machine(vram=8.0))
    monkeypatch.setattr(hardware, "registry_size_gb", lambda tag: 2.0)
    ran = threading.Event()
    monkeypatch.setattr(local_models.LocalModels, "setup", lambda self, progress=print: (ran.set() or True, "ok"))
    app = App()
    try:
        api = Api(app)
        code, out = api.post("hardware/override", {"profile": "nope"})
        assert code == 400
        code, out = api.post("hardware/override", {"profile": "big-gpu-12", "models": ["x:1b"], "install": True})
        assert code == 200 and out["installing"] and out["hardware"]["recommendation"]["profile"] == "big-gpu-12"
        assert ran.wait(5)
        assert app.settings.get("hardware.extra_models") == ["x:1b"]
    finally:
        app.close()


def test_what_the_reranker_drops_is_not_replaced_by_leftovers(ollama):
    notes = {
        f"zettel/n{i}": note(f"zettel/n{i}", f"Note {i}", "gradient" if i == 0 else "unrelated words about rivers")
        for i in range(6)
    }
    idx = cg.Index(notes, reranker=rerank.Reranker("helper", ollama.base))
    got = idx.candidates("gradient rivers words", "", None, limit=4)
    assert [c.slug for c in got] == ["zettel/n0"]  # the five it is sure about stay out
