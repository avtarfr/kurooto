"""The skill library (Brain, 0.8.0 stage 12): solved tasks and short demonstrations become reusable, tested skills.

    <state>/mind-skills/<slug>/
        SKILL.md          when to use it, its inputs, the steps (what /learned shows)
        template.md       a prompt skill's prompt, with {inputs} filled in      (or skill.py: a code skill)
        tests/*.json      at least two regression cases from the source episode: {"inputs": {...}, "expect": {...}}
        provenance.json   where it came from: the source episode's ids, the demo, the date
        skill.json        its state: uses, successes, failures, last use, retired
        variants/         every earlier version, kept even after the skill retires

A candidate enters only after every regression case passes (`gate`), and it enters at always-ask: running it goes
through Brain's autonomy (mind/act.py) as the action `skill.<slug>`, which nobody has classified, so it asks first until
you classify it (`/autonomy classify skill.<slug> R1`) after it has earned that. A skill unused or failing for 30 days
retires (its variants stay). A code skill only ever runs in the lab's sandbox, with no network.

Expectations in a case: contains / not_contains (lists of words), regex, json_keys (the output is JSON with these keys).
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

PART = "skills"  # its switch: mind.skills.on
ROOT = "mind-skills"
SLUG = re.compile(r"^[a-z][a-z0-9-]{1,38}$")
MIN_CASES = 2
IDLE_DAYS = 30
OUT_MAX = 4000
KINDS = ("prompt", "code")
EXPECT_KEYS = ("contains", "not_contains", "regex", "json_keys")

register_defaults(
    "mind",
    {
        "skills": {
            "on": True,  # solved tasks and demonstrations become tested, reusable skills; each starts by asking first
            "from_demos": False,  # also offer skills from what you do over and over (needs the activity stream)
        },
    },
)


def on(app: App) -> bool:
    return mind.part_on(app, "skills")


def root(app: App) -> Path:
    return app.paths.state / ROOT


def folder(app: App, slug: str) -> Path:
    return root(app) / slug


def meta(app: App, slug: str) -> dict | None:
    return jload(folder(app, slug) / "skill.json", None)


def all_skills(app: App) -> dict[str, dict]:
    out = {}
    if root(app).is_dir():
        for d in sorted(root(app).iterdir()):
            m = jload(d / "skill.json", None)
            if m:
                out[d.name] = m
    return out


# ------------------------------------------------------------------------------------------------ the spec
def validate_spec(spec) -> tuple[dict | None, list[str]]:
    """A candidate as the AI wrote it -> (clean spec, problems). A skill needs a name, when to use it, steps, a template
    (prompt) or code, and at least two regression cases."""
    bad: list[str] = []
    if not isinstance(spec, dict):
        return None, ["the candidate isn't an object"]
    slug = str(spec.get("slug") or "").strip().lower()
    if not SLUG.match(slug):
        bad.append("slug must be lowercase words joined by hyphens")
    kind = str(spec.get("kind") or "prompt")
    if kind not in KINDS:
        bad.append("kind must be prompt or code")
    title, when, steps = (str(spec.get(k) or "").strip() for k in ("title", "when", "steps"))
    if not (title and when and steps):
        bad.append("title, when and steps are needed")
    body = str(spec.get("code" if kind == "code" else "template") or "")
    if not body.strip():
        bad.append("a skill needs its template (or code)")
    inputs = [str(x)[:40] for x in (spec.get("inputs") or []) if re.match(r"^[a-z_][a-z0-9_]*$", str(x))][:8]
    cases = []
    for c in spec.get("cases") or []:
        if isinstance(c, dict) and isinstance(c.get("inputs"), dict) and isinstance(c.get("expect"), dict):
            exp = {k: v for k, v in c["expect"].items() if k in EXPECT_KEYS}
            if exp:
                cases.append({"inputs": {str(k)[:40]: str(v)[:2000] for k, v in c["inputs"].items()}, "expect": exp})
    if len(cases) < MIN_CASES:
        bad.append(f"at least {MIN_CASES} regression cases with an expectation are needed")
    if bad:
        return None, bad
    return {
        "slug": slug,
        "kind": kind,
        "title": title[:80],
        "when": when[:300],
        "steps": steps[:3000],
        "inputs": inputs,
        "body": body[:20000],
        "cases": cases[:10],
    }, []


def check_expect(out: str, expect: dict) -> list[str]:
    """What an output fails of its expectation, in words (empty: it passes)."""
    why = []
    low = out.lower()
    for w in expect.get("contains") or []:
        if str(w).lower() not in low:
            why.append(f"missing {str(w)[:30]!r}")
    for w in expect.get("not_contains") or []:
        if str(w).lower() in low:
            why.append(f"should not contain {str(w)[:30]!r}")
    if expect.get("regex") and not re.search(str(expect["regex"]), out, re.S):
        why.append("doesn't match the pattern")
    if expect.get("json_keys"):
        try:
            obj = json.loads(out)
            miss = [k for k in expect["json_keys"] if not isinstance(obj, dict) or k not in obj]
            if miss:
                why.append("JSON lacks " + ", ".join(map(str, miss[:3])))
        except ValueError:
            why.append("isn't JSON")
    return why


# ------------------------------------------------------------------------------------------------- running
def render(template: str, inputs: dict) -> str:
    """The prompt: `{name}` for each input, and `{inputs}` for all of them as lines."""
    out = template.replace("{inputs}", "\n".join(f"{k}: {v}" for k, v in inputs.items()))
    for k, v in inputs.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def ask_text(app: App, prompt: str, title: str) -> str | None:
    jid = app.jobs.submit(prompt, title=title, effort="low", background=True, text_only=True, quiet=True, lane="bg")
    for _ in range(300):
        job = app.jobs.get(jid)
        if job and job.status in ("ok", "failed", "cancelled"):
            return str(getattr(job, "text", "") or getattr(job, "result", "") or "") if job.status == "ok" else None
        time.sleep(1)
    return None


def prompt_runner(app: App, m: dict, inputs: dict, body: str) -> str | None:
    return ask_text(app, render(body, inputs), f"Skill: {m['slug']}")


def code_runner(app: App, m: dict, inputs: dict, body: str) -> str | None:
    """Run a code skill: a copy of its folder with input.json, in the lab's sandbox (no network); stdout is the
    output."""
    from kurooto.mind.lab import sandbox

    if sandbox.unavailable(app):
        return None
    with tempfile.TemporaryDirectory(prefix="kurooto-skill-") as td:
        work = Path(td)
        (work / "skill.py").write_text(body)
        (work / "input.json").write_text(json.dumps(inputs))
        r = sandbox.run(app, work, "python3 skill.py input.json", 60)
    return r["out"][-OUT_MAX:] if r.get("ran") and r.get("ok") else None


def execute(app: App, m: dict, inputs: dict, body: str, runner=None) -> str | None:
    fn = runner or (code_runner if m["kind"] == "code" else prompt_runner)
    return fn(app, m, inputs, body)


def gate(app: App, spec: dict, runner=None) -> tuple[bool, list[dict]]:
    """Run every regression case: (all passed, [{case, ok, why}]). A case whose run produced nothing fails."""
    out, m = [], {"slug": spec["slug"], "kind": spec["kind"]}
    for i, c in enumerate(spec["cases"]):
        got = execute(app, m, c["inputs"], spec["body"], runner)
        why = ["no output"] if not got else check_expect(got, c["expect"])
        out.append({"case": i, "ok": not why, "why": "; ".join(why)})
    return all(r["ok"] for r in out), out


# ------------------------------------------------------------------------------------------------ the library
def write(app: App, spec: dict, provenance: dict, status: str = "always-ask") -> None:
    d = folder(app, spec["slug"])
    old = meta(app, spec["slug"])
    if old:  # keep the earlier version as a variant
        v = d / "variants" / f"{int(time.time())}"
        v.mkdir(parents=True, exist_ok=True)
        for f in ("SKILL.md", "template.md", "skill.py", "provenance.json"):
            if (d / f).exists():
                shutil.copy2(d / f, v / f)
        if (d / "tests").exists():
            shutil.copytree(d / "tests", v / "tests", dirs_exist_ok=True)
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {spec['slug']}\ntitle: {spec['title']}\nkind: {spec['kind']}\n"
        f"inputs: {', '.join(spec['inputs'])}\n---\n\n"
        f"When to use it: {spec['when']}\n\nSteps:\n{spec['steps']}\n"
    )
    (d / ("skill.py" if spec["kind"] == "code" else "template.md")).write_text(spec["body"])
    (d / "tests").mkdir(exist_ok=True)
    for f in (d / "tests").glob("*.json"):
        f.unlink()
    for i, c in enumerate(spec["cases"]):
        jsave(d / "tests" / f"case-{i}.json", c)
    jsave(d / "provenance.json", {**provenance, "at": time.time()})
    now = time.time()
    jsave(
        d / "skill.json",
        {
            "slug": spec["slug"],
            "title": spec["title"],
            "kind": spec["kind"],
            "when": spec["when"],
            "inputs": spec["inputs"],
            "status": status,
            "created": (old or {}).get("created", now),
            "updated": now,
            "uses": int((old or {}).get("uses", 0)),
            "ok": int((old or {}).get("ok", 0)),
            "fail": int((old or {}).get("fail", 0)),
            "last_used": (old or {}).get("last_used"),
            "retired": False,
            "source": provenance.get("source", "episode"),
        },
    )


def admit(app: App, spec_raw, provenance: dict, runner=None) -> tuple[str | None, str]:
    """A candidate -> (slug, "") once every regression case passes; else (None, why). It enters at always-ask."""
    if not on(app):
        return None, "skills are off (mind.skills.on)"
    spec, bad = validate_spec(spec_raw)
    if spec is None:
        return None, "; ".join(bad)
    ok, results = gate(app, spec, runner)
    if not ok:
        fails = [f"case {r['case']}: {r['why']}" for r in results if not r["ok"]]
        mind.connect(app).report("skill_event", {"status": "rejected", "cases": len(results), "failed": len(fails)})
        return None, "it failed its own regression cases (" + "; ".join(fails)[:200] + ")"
    write(app, spec, provenance)
    mind.connect(app).report("skill_event", {"status": "admitted", "cases": len(results), "failed": 0})
    return spec["slug"], ""


def record_use(app: App, slug: str, ok: bool) -> None:
    m = meta(app, slug)
    if not m:
        return
    m["uses"] += 1
    m["ok" if ok else "fail"] += 1
    m["last_used"] = time.time()
    jsave(folder(app, slug) / "skill.json", m)


def _body(app: App, m: dict) -> str:
    return (folder(app, m["slug"]) / ("skill.py" if m["kind"] == "code" else "template.md")).read_text()


def run_by_owner(app: App, slug: str, inputs: dict, runner=None) -> str | None:
    """You asked for it by name (`/learned run <slug>`): it runs, and the use is counted."""
    m = meta(app, slug)
    if not m or m.get("retired"):
        return None
    out = execute(app, m, inputs, _body(app, m), runner)
    record_use(app, slug, bool(out))
    return out


def run(app: App, slug: str, inputs: dict, runner=None) -> object:
    """Run a skill on its own, the way Brain runs anything on its own: through act.run, as `skill.<slug>`. Unclassified,
    that asks first; it returns None when it asked or when autonomy is off (nothing runs on its own then)."""
    from kurooto.mind import act

    m = meta(app, slug)
    if not m or m.get("retired") or not act.on(app):
        return None
    body = _body(app, m)

    def do(_):
        out = execute(app, m, inputs, body, runner)
        record_use(app, slug, bool(out))
        return out

    return act.run(app, f"skill.{slug}", do, inputs, f"run the skill {m['title']}")


def redact(app: App, lo: float, hi: float) -> int:
    """/forget: where a skill came from is dropped from the skills made in [lo, hi); the skill itself stays."""
    n = 0
    for slug, m in all_skills(app).items():
        if lo <= float(m.get("created") or 0) < hi:
            f = folder(app, slug) / "provenance.json"
            if f.exists():
                jsave(f, {"source": m.get("source", "episode"), "redacted": True, "at": time.time()})
                n += 1
    return n


def retire(app: App, slug: str, why: str = "you retired it") -> bool:
    m = meta(app, slug)
    if not m or m.get("retired"):
        return False
    m.update(retired=True, retired_at=time.time(), retired_why=why)
    jsave(folder(app, slug) / "skill.json", m)  # the folder and its variants stay
    mind.connect(app).report("skill_event", {"status": "retired", "cases": 0, "failed": 0})
    return True


def retire_stale(app: App, now: float | None = None) -> list[str]:
    """Unused for 30 days (since it was made, if never used), or failing more than it works after three tries."""
    now = now or time.time()
    gone = []
    for slug, m in all_skills(app).items():
        if m.get("retired"):
            continue
        last = m.get("last_used") or m.get("created") or now
        idle = now - float(last) > IDLE_DAYS * 86400
        failing = m["uses"] >= 3 and m["fail"] > m["ok"] and now - float(last) > 86400
        if (idle or failing) and retire(app, slug, "unused for 30 days" if idle else "failing"):
            gone.append(slug)
    return gone


def listing(app: App) -> str:
    if not on(app):
        return "Learned skills are off (mind.skills.on, with Brain)."
    rows = all_skills(app)
    if not rows:
        return (
            "No learned skills yet. They come from tasks that worked out (and, if you turn it on, from what you do "
            "repeatedly)."
        )
    out = ["Skills it has learned (each asks first until you classify it with /autonomy classify skill.<name> R1):"]
    for slug, m in sorted(rows.items()):
        v = len(list((folder(app, slug) / "variants").glob("*"))) if (folder(app, slug) / "variants").is_dir() else 0
        rate = f"{m['ok']}/{m['uses']} worked" if m["uses"] else "not used yet"
        out.append(
            f"- {slug}{' (retired)' if m.get('retired') else ''}: {m['title']}; {rate}; "
            f"{v} older version(s). {m['when']}"
        )
    return "\n".join(out)
