"""Any service that speaks the OpenAI chat API: a free Gemini key, FreeLLMAPI, Ollama on this computer, or
anything else with a base URL and a key."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from kurooto.providers.base import AUTH_FAIL, RATE_LIMIT, Brain, Result, Task, Verdict

MAX_ROUNDS = 16  # tool calls in one request, at most

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
        res, msg, usage = self._turn(messages, effort, timeout)
        if res is not None:
            return res
        text = (msg.get("content") or "").strip()
        return Result(Verdict.OK if text else Verdict.EMPTY, text, msg["_secs"], usage=usage)

    def _turn(self, messages: list[dict], effort: str, timeout: float, tools: list | None = None):
        """One request. Returns (Result on failure, else None; the reply message; usage)."""
        model = self.models.get(effort) or self.models.get("medium")
        body: dict = {"model": model, "messages": messages}
        if tools:
            body["tools"] = tools
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
                res = Result(Verdict.RATE_LIMITED, "", secs, detail, int(retry) if retry and retry.isdigit() else None)
                return res, {}, {}
            if e.code in (401, 403) or AUTH_FAIL.search(detail):
                return Result(Verdict.AUTH, "", secs, detail), {}, {}
            return Result(Verdict.ERROR, "", secs, f"HTTP {e.code}: {detail}"), {}, {}
        except TimeoutError:
            return Result(Verdict.TIMEOUT, "", time.monotonic() - t0, f"no answer in {timeout:.0f}s"), {}, {}
        except (urllib.error.URLError, OSError, ValueError) as e:
            return Result(Verdict.ERROR, "", time.monotonic() - t0, f"{type(e).__name__}: {e}"), {}, {}
        secs = time.monotonic() - t0
        try:
            msg = dict(data["choices"][0].get("message") or {})
        except (KeyError, IndexError, TypeError, AttributeError):
            return Result(Verdict.ERROR, "", secs, f"unexpected reply: {str(data)[:300]}"), {}, {}
        msg["_secs"] = secs
        return None, msg, data.get("usage") or {}

    def complete(self, prompt: str, system: str = "", effort: str = "low", timeout: int = 60) -> Result:
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        return self.chat(msgs, effort, timeout)

    def run(self, task: Task) -> Result:
        msgs = ([{"role": "system", "content": task.context}] if task.context else []) + [
            {"role": "user", "content": task.prompt}
        ]
        if not task.tools or not task.run_tool:
            return self.chat(msgs, task.effort, task.timeout_s)
        from kurooto.core.tools import schema

        decl = [
            {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": schema(t)}}
            for t in task.tools
        ]
        t0 = time.monotonic()
        usage: dict = {}
        for _ in range(MAX_ROUNDS):
            left = task.timeout_s - (time.monotonic() - t0)
            if left < 5:
                return Result(Verdict.TIMEOUT, "", time.monotonic() - t0, "ran out of time while using tools")
            res, msg, u = self._turn(msgs, task.effort, left, decl)
            if res is not None and res.verdict == Verdict.RATE_LIMITED and (res.retry_after_s or 30) <= 60 < left:
                time.sleep(res.retry_after_s or 30)  # free tiers allow a few requests a minute; one wait, then retry
                res, msg, u = self._turn(msgs, task.effort, task.timeout_s - (time.monotonic() - t0), decl)
            if res is not None:
                res.seconds = time.monotonic() - t0
                return res
            for k, v in u.items():
                if isinstance(v, int):
                    usage[k] = usage.get(k, 0) + v
            calls = msg.get("tool_calls") or []
            if not calls:
                text = (msg.get("content") or "").strip()
                return Result(Verdict.OK if text else Verdict.EMPTY, text, time.monotonic() - t0, usage=usage)
            msgs.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
            for c in calls:
                fn = c.get("function") or {}
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except ValueError:
                    args = {}
                out = task.run_tool(fn.get("name") or "", args if isinstance(args, dict) else {})
                content = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, default=str)
                msgs.append({"role": "tool", "tool_call_id": c.get("id") or "", "content": content[:20000]})
        return Result(Verdict.ERROR, "", time.monotonic() - t0, f"stopped after {MAX_ROUNDS} rounds of tool calls")
