"""The Research add-on: the narrow research tools in one bundle, off until you turn it on, so the student flow stays
plain. One switch (its card in Features, Add-ons) turns the group on; the card has a switch for each part.

Its own parts:
    Run compare         /runs (recent runs), /runs compare A B, `kurooto runlog diff A B` (kurooto/runcompare.py)
    LaTeX tracker       /latex add <folder> [main.tex], /latex, /latex build; a nightly build and one morning line
                        (modules/latex_tracker.py)
Other features join the bundle with `bundle = "research_addon"` on their Module (Check my draft, modules/drafts.py):
they get no card of their own, the add-on's card has a switch for each, and turning the add-on on or off turns them
on or off with it (App.enable / App.disable call turned_on / turned_off). A member you switch off on the card stays off
the next time the add-on is turned on (research_addon.members_off).
"""

from __future__ import annotations

import re
import threading
from pathlib import Path

from kurooto.core.config import register_defaults
from kurooto.modules import latex_tracker as lt
from kurooto.modules.base import Command, Incoming, Module

register_defaults(
    "research_addon",
    {
        "run_compare": True,  # Run compare: /runs and `kurooto runlog diff A B` (a part of the Research add-on)
        "latex": True,  # the LaTeX tracker: a nightly build of the folders you attach with /latex add
        "latex_repos": [],  # [{"path": folder, "main": "main.tex"}]: only folders you attached with /latex add
        "latex_when": "daily 03:30",  # when the nightly LaTeX build runs
        "latex_morning": "daily 08:00",  # the one morning line (only when a build broke or you wrote something)
        "latex_timeout_min": 15,  # a build that takes longer is stopped and counts as an error
        "members_off": [],  # features of the bundle you switched off on its card (they stay off when it's turned on)
    },
)
PARTS = {
    "run_compare": "Run compare (/runs, kurooto runlog diff)",
    "latex": "LaTeX tracker (/latex)",
}
PART_SETTING: dict[str, str] = {}  # a part whose switch is another feature's setting (none since notation left)
RUNS_SHOWN = 10


class ResearchAddon(Module):
    id = "research_addon"
    title = "Research add-on"
    extra = True  # an add-on: turned on by hand, never by a preset
    heavy = True  # the nightly LaTeX build waits for the charger on battery
    description = (
        "For research work, in one switch: compare two experiment runs (config, code, metrics, curves), a nightly "
        "build of your LaTeX papers (errors, missing references and citations, words written), and more research "
        "tools as they come."
    )
    privacy = (
        "Runs, code diffs and LaTeX builds stay on this computer; Tectonic fetches LaTeX packages it lacks (nothing of "
        "yours is sent). A BibTeX suggestion, only when you tap for one, sends the citation key and its sentence to "
        "the AI you picked."
    )

    def __init__(self, app):
        super().__init__(app)
        self.latex = lt.Tracker(app)

    # ------------------------------------------------------------------------------------------- the bundle
    def members(self) -> list[Module]:
        """Features that live in this bundle (Module.bundle == "research_addon")."""
        return [m for m in self.app.modules.values() if getattr(m, "bundle", "") == self.id]

    def turned_on(self) -> None:
        """The one switch: the add-on's members come on with it (except those you switched off on its card)."""
        off = set(self.setting("members_off") or [])
        for m in self.members():
            if m.id not in off and not self.app.is_on(m.id):
                ok, why = self.app.enable(m.id)
                if not ok:
                    self.app.events.emit("bundle_member_waits", module=m.id, why=why[:120])

    def turned_off(self) -> None:
        for m in self.members():
            if self.app.is_on(m.id):
                self.app.disable(m.id)

    def part_on(self, part: str) -> bool:
        return self.app.settings.get(self.part_key(part)) is not False

    def part_key(self, part: str) -> str:
        return PART_SETTING.get(part, f"{self.id}.{part}")

    # ---------------------------------------------------------------------------------------- lifecycle
    def start(self):
        self.every("latex", self.setting("latex_when") or "daily 03:30", lambda p: self.nightly())
        self.every("morning", self.setting("latex_morning") or "daily 08:00", lambda p: self.morning(), respect="quiet")
        self.app.jobs.then_actions["research_addon.bibtex"] = self._bibtex_came

    def health(self):
        if self.part_on("latex") and self.latex.repos():
            if lt.engine(self.app) is None:
                return False, "the LaTeX tracker needs Tectonic or LaTeX: /latex install"
            gone = [r["path"] for r in self.latex.repos() if not Path(r.get("path") or "").is_dir()]
            if gone:
                return False, f"LaTeX folder missing: {gone[0]} (/latex remove it, or put it back)"
        bits = [label.split(" (")[0] for k, label in PARTS.items() if self.part_on(k)]
        bits += [m.title for m in self.members() if self.app.is_on(m.id)]
        return True, ", ".join(bits) or "every part is switched off"

    def nightly(self) -> list[dict]:
        if not self.part_on("latex") or not self.latex.repos():
            return []
        return self.latex.run_all()

    def morning(self) -> str | None:
        if not self.part_on("latex"):
            return None
        got = self.latex.morning()
        if not got:
            return None
        text, buttons = got
        self.app.notify(text, kind="result", why="research_addon.latex", buttons=buttons or None)
        return text

    # -------------------------------------------------------------------------------------------- card
    def card(self) -> dict:
        lines = []
        if self.part_on("run_compare"):
            n = len(self._runs())
            lines.append(f"Run compare: {n} run{'s' if n != 1 else ''} to compare (/runs).")
        if self.part_on("latex"):
            docs = self.latex.repos()
            lines.append(
                f"LaTeX tracker: {len(docs)} document{'s' if len(docs) != 1 else ''} followed (/latex)."
                if docs
                else "LaTeX tracker: no document yet (/latex add <folder>)."
            )
        toggles = [{"id": k, "label": label, "on": self.part_on(k)} for k, label in PARTS.items()]
        toggles += [{"id": f"m:{m.id}", "label": m.title, "on": self.app.is_on(m.id)} for m in self.members()]
        return {"lines": lines, "toggles": toggles}

    def card_action(self, act: str, value) -> str:
        if act in PARTS:
            self.app.settings.set(self.part_key(act), bool(value))
            self.app.events.emit("research_addon_part", part=act, on=bool(value))
            return f"{PARTS[act].split(' (')[0]}: {'on' if value else 'off'}."
        if act.startswith("m:"):
            m = self.app.modules.get(act[2:])
            if m is None or getattr(m, "bundle", "") != self.id:
                return "There's no such part."
            off = [x for x in self.setting("members_off") or [] if x != m.id]
            if value:
                ok, why = self.app.enable(m.id)
                self.app.settings.set("research_addon.members_off", off)
                return f"{m.title} is on." if ok else why
            self.app.disable(m.id)
            self.app.settings.set("research_addon.members_off", [*off, m.id])
            return f"{m.title} is off."
        return "There's no such part."

    # ----------------------------------------------------------------------------------------- commands
    def commands(self):
        return [
            Command(
                "runs", "recent experiment runs; /runs compare A B puts two side by side in your notes", self._runs_cmd
            ),
            Command(
                "latex",
                "your LaTeX documents' last build; /latex add <folder> [main.tex], /latex remove, /latex build",
                self._latex_cmd,
            ),
        ]

    def callbacks(self):
        return {"rlx": self._button}

    # ---------------------------------------------------------------------------------------------- runs
    def _rl(self):
        from kurooto.runlog import Runlog

        return Runlog(self.app.paths, self.app, self.app.name)

    def _runs(self) -> list[tuple[str, Path]]:
        from kurooto import runcompare

        return runcompare.all_runs(self._rl(), runcompare.repo_dirs(self.app.settings))

    def _runs_cmd(self, msg: Incoming, arg: str) -> str:
        from kurooto import runcompare

        if not self.part_on("run_compare"):
            return "Run compare is off: switch it on on the Research add-on's card."
        words = arg.split()
        if words and words[0].lower() in ("compare", "diff"):
            refs = words[1:]
            runs = self._runs()
            if not refs:  # the last two runs of the newest run's project
                if len(runs) < 2:
                    return "There aren't two runs to compare yet."
                first = runcompare.load(runs[0][1])
                proj = first.meta.get("project") or str(runs[0][1].parent.parent)
                same = [
                    r
                    for r in runs[1:]
                    if (runcompare.load(r[1]).meta.get("project") or str(r[1].parent.parent)) == proj
                ]
                if not same:
                    return "The newest run is the only one of its project: /runs compare A B names two."
                refs = [same[0][0], runs[0][0]]
            if len(refs) != 2:
                return "Usage: /runs compare A B (ids, a piece of them, or their numbers in /runs)"
            try:
                r = runcompare.compare(
                    self._rl(), refs[0], refs[1], runcompare.repo_dirs(self.app.settings),
                    runcompare.project_for(self.app.settings),
                )  # fmt: skip
            except runcompare.CompareError as e:
                return str(e)[0].upper() + str(e)[1:] + "."
            self.app.events.emit("runs_compared", png=bool(r["png"]))
            return f"{r['summary']}\nIn your notes: {r['note']}" + (
                " (with the curves as a picture)" if r["png"] else ""
            )
        if words:
            return "Usage: /runs, or /runs compare A B"
        runs = self._runs()[:RUNS_SHOWN]
        if not runs:
            return "No runs yet: `kurooto runlog start <project>` or kurooto.runlog.Run logs one."
        rows = []
        for i, (rid, d) in enumerate(runs, 1):
            try:
                ri = runcompare.load(d)
            except runcompare.CompareError:
                continue
            last = ", ".join(
                f"{k}={v:.4g}" if isinstance(v, float) else f"{k}={v}"
                for k, v in list((ri.meta.get("last") or {}).items())[:2]
            )
            proj = ri.meta.get("project") or d.parent.parent.name
            rows.append(f"{i}. {rid} ({proj}, {ri.meta.get('status', '?')})" + (f" {last}" if last else ""))
        return (
            "Recent runs:\n"
            + "\n".join(rows)
            + "\n/runs compare 1 2 puts two side by side (or /runs compare: the last two)."
        )

    # --------------------------------------------------------------------------------------------- latex
    def _latex_cmd(self, msg: Incoming, arg: str) -> str:
        if not self.part_on("latex"):
            return "The LaTeX tracker is off: switch it on on the Research add-on's card."
        verb, _, rest = arg.strip().partition(" ")
        verb, rest = verb.lower(), rest.strip().strip('"')
        if verb == "add" and rest:  # you typed it: attaching a folder (core/tap.py repo.attach)
            m = re.fullmatch(r"(.+?)\s+([^\s/\\]+\.tex)", rest)
            folder, main = (m[1].strip().strip('"'), m[2]) if m else (rest, "")
            return self.latex.attach(folder, main)
        if verb == "remove" and rest:
            return self.latex.detach(rest)
        if verb == "build":
            if not self.latex.repos():
                return "No document yet: /latex add <folder>."
            if lt.engine(self.app) is None:
                return self._no_engine()
            threading.Thread(target=self._build_now, name="latex-build", daemon=True).start()
            return "Building now; the result comes in a message (the first Tectonic build takes a few minutes)."
        if verb == "install":
            return self._install()
        if verb:
            return "Usage: /latex, /latex add <folder> [main.tex], /latex remove <folder>, /latex build"
        return self.status()

    def _no_engine(self) -> str:
        return (
            "There's nothing to build LaTeX with here: /latex install fetches Tectonic (about 25 MB, plus about 50 MB "
            "of LaTeX packages the first build fetches), or install TeX Live or MiKTeX yourself."
        )

    def _build_now(self) -> None:
        self.latex.run_all()
        st = self.latex.state()
        self.app.notify(self.status(st), kind="result", why="asked")

    def status(self, st: dict | None = None) -> str:
        """/latex: each document's last build."""
        docs = self.latex.repos()
        if not docs:
            return (
                "No LaTeX document followed yet. /latex add <folder> follows one (it names the .tex if there are "
                "several); a build every night, and a line in the morning when it broke or you wrote."
            )
        st = st if st is not None else self.latex.state()
        out = []
        for r in docs:
            rec = st.get(lt.key(str(Path(r.get("path") or "")))) or {}
            last = rec.get("last") or {}
            head = f"{lt.name_of(r)} ({r.get('main')})"
            if not last:
                out.append(f"{head}: not built yet (tonight, or /latex build).")
                continue
            if last.get("missing_engine"):
                out.append(f"{head}: {self._no_engine()}")
                continue
            errs = last.get("errors") or []
            bits = [
                ("builds" if not errs else f"{len(errs)} error{'s' if len(errs) > 1 else ''}")
                + f" ({last['at'][:16].replace('T', ' ')})"
            ]
            for e in errs[:3]:
                bits.append(f"  - {e['message'][:100]}" + (f" (line {e['line']})" if e.get("line") else ""))
            if last.get("refs"):
                bits.append(f"  undefined references: {', '.join(last['refs'][:6])}")
            if last.get("cites"):
                bits.append(f"  missing citations: {', '.join(last['cites'][:6])}")
            words = sorted((rec.get("words") or {}).items())
            if words:
                n = self.latex.added(rec)
                bits.append(f"  {words[-1][1]:,} words" + (f" ({n:+,} since the day before)" if n else ""))
            out.append(f"{head}: " + "\n".join(bits))
        return "\n".join(out)

    def _install(self) -> str:
        if lt.engine(self.app) is not None:
            return "There's a LaTeX engine here already."
        threading.Thread(target=self._install_now, name="tectonic", daemon=True).start()
        return "Installing Tectonic…"

    def _install_now(self) -> None:
        from kurooto.core.prereqs import Prereqs

        ok, msg = Prereqs(self.app.paths.app, self.app.paths.cache).install("tectonic", progress=lambda s: None)
        self.app.events.emit("tectonic_installed" if ok else "tectonic_install_failed")
        self.app.notify(
            "Tectonic is installed: tonight's LaTeX build uses it (/latex build tries it now)."
            if ok
            else f"Tectonic didn't install: {msg}",
            kind="result",
            why="asked",
        )

    # ------------------------------------------------------------------------------------- BibTeX by a tap
    def _button(self, ref: str, act: str) -> str:
        p = self.latex.pending(ref)
        if p is None:
            return "That one is gone; /latex shows what's missing now."
        key = str(p.get("key") or "")
        if act == "bib":  # you tapped for a suggestion: the key and its sentence go to your AI
            if not self.app.is_on("chat"):
                return "Suggestions come from your AI: turn on Chat first."
            main = Path(p.get("path") or "") / str(p.get("main") or "")
            self.app.jobs.submit(
                lt.bibtex_prompt(key, lt.cite_context(main, key)),
                title=f"BibTeX for {key}",
                effort="low",
                quiet=True,
                text_only=True,
                then="research_addon.bibtex",
                then_payload={"ref": ref},
            )
            return f"Asking your AI about {key}…"
        if act == "add":  # you tapped Add: the entry goes into the .bib the document names
            entry, bib = str(p.get("entry") or ""), str(p.get("bib") or "")
            if not entry or not bib:
                return "There's no entry to add."
            said = lt.add_entry(Path(bib), key, entry)
            self.latex.set_pending(ref, entry="", added=True)
            self.app.events.emit("bibtex_added")
            return said
        if act == "no":
            self.latex.set_pending(ref, entry="")
            return "Discarded; nothing was written."
        return "ok"

    def _bibtex_came(self, job, result, payload: dict) -> None:
        ref = str(payload.get("ref") or "")
        p = self.latex.pending(ref) or {}
        key = str(p.get("key") or "")
        if not result.ok:
            self.app.notify(f"Your AI couldn't suggest an entry for {key} this time.", kind="result", why="asked")
            return
        entry = lt.entry_from(result.text, key)
        if not entry:
            self.app.notify(f"No BibTeX entry for {key}:\n{result.text[:600]}", kind="result", why="asked")
            return
        main = Path(p.get("path") or "") / str(p.get("main") or "")
        bibs = lt.bib_files(main) if main.is_file() else []
        bib = next((b for b in bibs if b.exists()), bibs[0] if bibs else None)
        self.latex.set_pending(ref, entry=entry, bib=str(bib) if bib else "")
        if bib is None:
            text = (
                f"A suggested entry for {key} (check it against the paper). The document names no .bib file "
                f"(\\bibliography or \\addbibresource), so I won't write it anywhere:\n\n{entry}"
            )
            self.app.notify(text, kind="result", why="asked")
            return
        self.app.notify(
            f"A suggested entry for {key} (check it against the paper; nothing is written until you tap "
            f"Add):\n\n{entry}",
            kind="result",
            why="asked",
            buttons=[[(f"Add to {bib.name}", f"rlx:{ref}:add"), ("Discard", f"rlx:{ref}:no")]],
        )
