"""A reranker on this computer's graphics card: for a new concept and each candidate note, how likely is it that the
note is about the same thing or closely related? Better than word or vector similarity alone, and it costs no AI
requests.

How: the helper model Ollama already runs (a few billion parameters; gemma4:e4b on 8 GB cards, a 4B model on small ones)
is asked "does this note answer / belong with this concept? yes or no", one candidate at a time, and the odds it gives
"yes" against "no" (its token probabilities, which Ollama returns) are the score. No separate reranker model is needed
and nothing extra is downloaded; a dedicated one can be named in integrate.rerank_model.

Only where it's worth it: a machine with a usable helper model (the profile's, or one you added: core/hardware.py).
Elsewhere candidates keep their keyword and embedding order, and nothing else changes. Never required: any failure
returns None and the caller carries on without it.
"""

from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kurooto.app import App

PROMPT = (
    "Judge whether two notes of a student's Zettelkasten belong together.\n\n"
    "NEW CONCEPT: {query}\n\n"
    "EXISTING NOTE: {doc}\n\n"
    "Is the existing note about the same idea as the new concept, or an idea it directly depends on, generalises, "
    "specialises or contrasts with? Answer only yes or no."
)
MAX_FAILS = 3  # this many failures in a row and it stops trying for the rest of the run


def odds_yes(logprobs: list[dict] | None, text: str) -> float | None:
    """P(yes) / (P(yes) + P(no)) from the first token's probabilities; from the word itself when there are none."""
    for tok in (logprobs or [])[:1]:
        tops = tok.get("top_logprobs") or [tok]
        yes = no = 0.0
        for t in tops:
            word = str(t.get("token", "")).strip().lower()
            p = math.exp(float(t.get("logprob", -50)))
            if word == "yes":
                yes += p
            elif word == "no":
                no += p
        if yes + no > 0:
            return yes / (yes + no)
    word = (text or "").strip().lower()
    if word.startswith("yes"):
        return 1.0
    if word.startswith("no"):
        return 0.0
    return None


class Reranker:
    """Scores (concept, note) pairs with a local model through Ollama's /api/generate."""

    def __init__(self, model: str, base: str = "http://127.0.0.1:11434", timeout: float = 60.0):
        self.model, self.base, self.timeout = model, base.rstrip("/"), timeout
        self.fails = 0
        self.calls = 0
        self.seconds = 0.0

    @property
    def dead(self) -> bool:
        return self.fails >= MAX_FAILS

    def score_one(self, query: str, doc: str) -> float | None:
        body = {
            "model": self.model,
            "prompt": PROMPT.format(query=query[:900], doc=doc[:900]),
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_predict": 2},
            "logprobs": True,
            "top_logprobs": 5,
            "keep_alive": "10m",
        }
        req = urllib.request.Request(  # noqa: S310 (Ollama on this computer)
            f"{self.base}/api/generate", json.dumps(body).encode(), {"Content-Type": "application/json"}, "POST"
        )
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:  # noqa: S310
                data = json.loads(r.read().decode("utf-8"))
        except (OSError, ValueError, urllib.error.URLError):
            self.fails += 1
            return None
        self.calls += 1
        self.seconds += time.monotonic() - t0
        score = odds_yes(data.get("logprobs"), str(data.get("response") or ""))
        self.fails = 0 if score is not None else self.fails + 1
        return score

    def scores(self, query: str, docs: list[str]) -> list[float | None]:
        out: list[float | None] = []
        for d in docs:
            out.append(None if self.dead else self.score_one(query, d))
        return out


def make_reranker(app: App) -> Reranker | None:
    """The reranker this computer can run, or None: integrate.rerank (auto | off), on a profile that has a helper
    model (or one you added), with Ollama up and that model downloaded."""
    mode = str(app.settings.get("integrate.rerank") or "auto")
    if mode == "off":
        return None
    lm = app.modules.get("local_models")
    if lm is None:
        return None
    model = str(app.settings.get("integrate.rerank_model") or "").strip()
    if not model:
        helper = next((m["tag"] for m in lm.wanted() if str(m.get("key", "")).startswith("helper")), "")
        model = helper
    if not model:
        return None
    try:
        if not lm.running():
            return None
        have = lm.have()
    except OSError:
        return None
    if not any(h == model or (":" not in model and h.split(":")[0] == model) for h in have):
        return None
    return Reranker(model)
