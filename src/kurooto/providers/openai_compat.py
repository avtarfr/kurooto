"""Any service that speaks the OpenAI chat API: a free Gemini key, FreeLLMAPI, Ollama on this computer, or
anything else with a base URL and a key."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from kurooto.providers.base import AUTH_FAIL, RATE_LIMIT, Brain, Result, Task, Verdict

PRESETS = {
    "gemini": {
        "label": "Gemini API key (free)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models": {"low": "gemini-flash-lite-latest", "medium": "gemini-flash-latest", "high": "gemini-flash-latest"},
        "reasoning": True,
    },
    "freellmapi": {
        "label": "FreeLLMAPI (free pool of providers)",
        "base_url": "http://127.0.0.1:3001/v1",
        "models": {},  # picked from its model list at setup
        "reasoning": False,
    },
    "ollama": {
        "label": "Ollama on this computer",
        "base_url": "http://127.0.0.1:11434/v1",
        "models": {},  # from the hardware profile
        "reasoning": False,
    },
    "custom": {"label": "Another OpenAI-compatible service", "base_url": "", "models": {}, "reasoning": False},
}


class OpenAICompat(Brain):
    kind = "api"

    def __init__(self, preset: str, api_key: str | None, base_url: str | None = None, models: dict | None = None):
        p = PRESETS.get(preset, PRESETS["custom"])
        self.id = preset
        self.label = p["label"]
        self.base_url = (base_url or p["base_url"]).rstrip("/")
        self.api_key = api_key or ("ollama" if preset == "ollama" else "")
        self.models = {**p["models"], **(models or {})}
        self.reasoning = p["reasoning"]

    def available(self):
        if not self.base_url:
            return False, "no address set"
        if not self.api_key:
            return False, "no key set"
        if not self.models.get("medium"):
            return False, "no model chosen"
        return True, ""

    def _post(self, path: str, body: dict, timeout: float) -> dict:
        req = urllib.request.Request(  # noqa: S310 (an http(s) address the user configured)
            f"{self.base_url}{path}",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            return json.loads(r.read())

    def list_models(self, timeout: float = 20) -> list[str]:
        req = urllib.request.Request(f"{self.base_url}/models", headers={"Authorization": f"Bearer {self.api_key}"})  # noqa: S310
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            data = json.loads(r.read())
        return sorted(m.get("id", "").removeprefix("models/") for m in data.get("data", []) if m.get("id"))

    def chat(self, messages: list[dict], effort: str = "medium", timeout: float = 120) -> Result:
        model = self.models.get(effort) or self.models.get("medium")
        body: dict = {"model": model, "messages": messages}
        if self.reasoning and effort in ("low", "medium", "high"):
            body["reasoning_effort"] = effort
        t0 = time.monotonic()
        try:
            data = self._post("/chat/completions", body, timeout)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:500]
            secs = time.monotonic() - t0
            if e.code == 429 or RATE_LIMIT.search(detail):
                retry = e.headers.get("Retry-After")
                return Result(Verdict.RATE_LIMITED, "", secs, detail, int(retry) if retry and retry.isdigit() else None)
            if e.code in (401, 403) or AUTH_FAIL.search(detail):
                return Result(Verdict.AUTH, "", secs, detail)
            return Result(Verdict.ERROR, "", secs, f"HTTP {e.code}: {detail}")
        except TimeoutError:
            return Result(Verdict.TIMEOUT, "", time.monotonic() - t0, f"no answer in {timeout:.0f}s")
        except (urllib.error.URLError, OSError, ValueError) as e:
            return Result(Verdict.ERROR, "", time.monotonic() - t0, f"{type(e).__name__}: {e}")
        secs = time.monotonic() - t0
        try:
            choice = data["choices"][0]
            text = (choice.get("message") or {}).get("content") or ""
        except (KeyError, IndexError, TypeError):
            return Result(Verdict.ERROR, "", secs, f"unexpected reply: {str(data)[:300]}")
        text = text.strip()
        return Result(Verdict.OK if text else Verdict.EMPTY, text, secs, usage=data.get("usage") or {})

    def complete(self, prompt: str, system: str = "", effort: str = "low", timeout: int = 60) -> Result:
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        return self.chat(msgs, effort, timeout)

    def run(self, task: Task) -> Result:
        msgs = ([{"role": "system", "content": task.context}] if task.context else []) + [
            {"role": "user", "content": task.prompt}
        ]
        return self.chat(msgs, task.effort, task.timeout_s)
