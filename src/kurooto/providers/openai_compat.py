"""Any service that speaks the OpenAI chat API: a Gemini key, Ollama on this computer, or anything else with a base
URL and a key.

One request to a service on the internet waits at most REQUEST_S for its answer (less when the request's own time is
shorter): a connection that died on the way (the network changed, a login page took over the Wi-Fi) fails then
instead of holding the request for its whole time. A model on this computer gets the request's whole time.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from kurooto.providers.base import AUTH_FAIL, RATE_LIMIT, Brain, Result, Task, Verdict

MAX_ROUNDS = 16  # rounds of tool calls in one request, at most; then it must answer
REQUEST_S = {"low": 180, "medium": 300, "high": 600}  # one request on the internet waits this long at most
LOOPBACK = ("127.0.0.1", "localhost", "::1")
ENOUGH = "Stop using tools now. Answer with what you have, and say plainly what you did and what you couldn't do."
# a 4xx that says the model or service can't take tools (Ollama: "... does not support tools")
NO_TOOLS = re.compile(r"^HTTP 4\d\d:.*\b(tools?|functions?|function.?call(ing)?)\b", re.I | re.S)

PRESETS = {
    "gemini": {
        "label": "Gemini API key (free)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models": {"low": "gemini-flash-lite-latest", "medium": "gemini-flash-latest", "high": "gemini-flash-latest"},
        "reasoning": True,
        # each model has its own free daily limit: when one is used up, the next of the family is tried (smaller or
        # older ones answer worse, so the answer says which one it was)
        "alternatives": [
            "gemini-flash-latest",
            "gemini-flash-lite-latest",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ],
    },
    "freellmapi": {  # no longer offered (it pools other providers' free tiers); one set up earlier keeps working
        "label": "Another OpenAI-compatible service",
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
        self.alternatives = list(p.get("alternatives") or [])

    def available(self):
        if not self.base_url:
            return False, "no address set"
        if not self.api_key:
            return False, "no key set"
        if not self.models.get("medium"):
            return False, "no model chosen"
        return True, ""

    def local(self) -> bool:
        """Is the service on this computer (Ollama, a local server)?"""
        return (urllib.parse.urlsplit(self.base_url).hostname or "") in LOOPBACK

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
        out = Result(Verdict.OK if text else Verdict.EMPTY, text, msg["_secs"], usage=usage)
        return out

    def _turn(self, messages: list[dict], effort: str, timeout: float, tools: list | None = None, choice: str = ""):
        """One request, counted against its model's free limit. Returns (Result on failure, else None; the reply
        message; usage)."""
        model = self.models.get(effort) or self.models.get("medium")
        res, msg, usage = self._request(messages, effort, timeout, tools, choice)
        self.metered(model, res)
        if res is not None and res.verdict == Verdict.RATE_LIMITED and self.alternatives:
            for alt in [m for m in self.alternatives if m != model]:  # this model's day is used up: try its family
                res2, msg2, usage2 = self._request(messages, effort, timeout, tools, choice, alt)
                self.metered(alt, res2)
                if res2 is None:
                    note = f"(Answered with {alt}: {model}'s free limit for today was used up.)"
                    return res2, msg2, {**usage2, "note": note}
                if res2.verdict not in (Verdict.RATE_LIMITED, Verdict.ERROR):  # a real problem (key, timeout): stop
                    break
        return res, msg, usage

    def _request(
        self, messages: list[dict], effort: str, timeout: float, tools: list | None, choice: str, model: str = ""
    ):
        model = model or self.models.get(effort) or self.models.get("medium")
        body: dict = {"model": model, "messages": messages}
        if tools:
            body["tools"] = tools
            if choice:
                body["tool_choice"] = choice
        if self.reasoning and effort in ("low", "medium", "high"):
            body["reasoning_effort"] = effort
        t0 = time.monotonic()
        if not self.local():  # a dead connection fails in minutes, not after the whole request's time
            timeout = min(timeout, REQUEST_S.get(effort, REQUEST_S["medium"]))
        try:
            data = self._post("/chat/completions", body, timeout)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            detail = body[:500]
            secs = time.monotonic() - t0
            if e.code == 429 or RATE_LIMIT.search(detail):
                from kurooto.core.quota import hints

                retry = e.headers.get("Retry-After")
                res = Result(Verdict.RATE_LIMITED, "", secs, detail, int(retry) if retry and retry.isdigit() else None)
                res.usage = {"limit": hints(body, res.retry_after_s)}  # which limit, its number, when it's back
                return res, {}, {}
            if e.code in (401, 403) or AUTH_FAIL.search(detail):
                return Result(Verdict.AUTH, "", secs, detail), {}, {}
            return Result(Verdict.ERROR, "", secs, f"HTTP {e.code}: {detail}"), {}, {}
        except TimeoutError:
            return Result(Verdict.TIMEOUT, "", time.monotonic() - t0, f"no answer in {timeout:.0f}s"), {}, {}
        except (urllib.error.URLError, OSError, ValueError) as e:
            return Result(Verdict.ERROR, "", time.monotonic() - t0, f"{type(e).__name__}: {e}"), {}, {}
        except Exception as e:  # e.g. http.client.IncompleteRead (a connection cut mid-answer), which isn't an OSError
            return Result(Verdict.ERROR, "", time.monotonic() - t0, f"{type(e).__name__}: {e}"[:500]), {}, {}
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
        decl = [declaration(t) for t in task.tools]
        t0 = time.monotonic()
        usage: dict = {}
        used: list[str] = []

        def left() -> float:
            return task.timeout_s - (time.monotonic() - t0)

        def stopped() -> bool:
            return task.stop is not None and task.stop.is_set()

        for rnd in range(MAX_ROUNDS + 1):
            if stopped():  # cancelled, or ended by the queue's watchdog: no more requests or tools
                return Result(Verdict.CANCELLED, "", time.monotonic() - t0, "stopped")
            if left() < 5:
                return Result(Verdict.TIMEOUT, "", time.monotonic() - t0, "ran out of time while using tools")
            final = rnd == MAX_ROUNDS
            if final:  # enough: an answer from what it has, with tools still declared but not allowed
                msgs.append({"role": "user", "content": ENOUGH})
            res, msg, u = self._turn(msgs, task.effort, left(), decl, "none" if final else "")
            if (
                res is not None
                and res.verdict == Verdict.RATE_LIMITED
                and (res.retry_after_s or 30) <= 60 < left()
                and (res.usage.get("limit") or {}).get("per") != "day"  # the day's limit doesn't come back in a minute
            ):
                time.sleep(res.retry_after_s or 30)  # free tiers allow a few requests a minute; one wait, then retry
                res, msg, u = self._turn(msgs, task.effort, left(), decl, "none" if final else "")
            if res is not None and rnd == 0 and res.verdict == Verdict.ERROR and NO_TOOLS.search(res.detail):
                r = self.chat(msgs, task.effort, left())  # this model or service can't use tools: answer without
                r.seconds, r.usage = time.monotonic() - t0, {**r.usage, "tools": "unsupported"}
                return r
            if res is not None:
                res.seconds = time.monotonic() - t0
                res.usage = {**usage, "tool_calls": len(used)}
                return res
            for k, v in u.items():
                if isinstance(v, int):
                    usage[k] = usage.get(k, 0) + v
            if u.get("note"):  # answered by another model of the family (its own limit): the answer says so
                usage["note"] = u["note"]
            calls = [dict(c) for c in (msg.get("tool_calls") or []) if isinstance(c, dict)]
            if not calls or final:
                text = (msg.get("content") or "").strip()
                usage.update(tool_calls=len(used), tools_used=sorted(set(used)))
                if not text and calls:
                    return Result(Verdict.ERROR, "", time.monotonic() - t0, f"still calling tools after {rnd} rounds")
                return Result(Verdict.OK if text else Verdict.EMPTY, text, time.monotonic() - t0, usage=usage)
            for i, c in enumerate(calls):
                c["id"] = c.get("id") or f"call_{rnd}_{i}"  # some local servers leave it out
            msgs.append({"role": "assistant", "content": msg.get("content") or None, "tool_calls": calls})
            for c in calls:
                if stopped():
                    return Result(Verdict.CANCELLED, "", time.monotonic() - t0, "stopped")
                fn = c.get("function") or {}
                name, raw = str(fn.get("name") or ""), fn.get("arguments")
                try:
                    args = raw if isinstance(raw, dict) else json.loads(raw or "{}")
                except ValueError:
                    args = None
                if not isinstance(args, dict):
                    out = f"Error: the arguments for {name} weren't a JSON object. Call it again with valid JSON."
                else:
                    used.append(name)
                    out = task.run_tool(name, args)
                content = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, default=str)
                msgs.append({"role": "tool", "tool_call_id": c["id"], "content": content[:20000]})
        return Result(Verdict.ERROR, "", time.monotonic() - t0, f"stopped after {MAX_ROUNDS} rounds of tool calls")


def declaration(t) -> dict:
    """A tool as an OpenAI-style function. No "parameters" when it takes none: Gemini refuses an empty object."""
    from kurooto.core.tools import schema

    fn = {"name": t.name, "description": t.description}
    if t.params:
        fn["parameters"] = schema(t)
    return {"type": "function", "function": fn}
