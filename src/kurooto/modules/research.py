"""Research: new papers in your fields, from the sources you choose, as a digest on Telegram (weekly by default), and
project logs from your code.

Sources (the dashboard's Research tab, or Settings → research.feeds):
    arXiv     fields by category (all 155: maths, physics, computer science, statistics, quantitative biology and
              finance, economics, electrical engineering)
    bioRxiv   biology preprints by subject area (neuroscience, genomics, ecology, ...)
    medRxiv   medical preprints by subject area (epidemiology, oncology, psychiatry, ...)
    PubMed    published biomedical papers for a search (PubMed's own search words work)
    a feed    any journal's or blog's RSS or Atom address
Each source can be narrowed with keywords (any of them, in the title or abstract). An arXiv source can also be a search
in arXiv's own words, with a name ({"type": "arxiv", "name": "Molecules", "query": "abs:\"graph neural network\" AND
(abs:molecule OR abs:protein)"}: ti:, abs:, all:, cat:, AND, OR, ANDNOT, brackets). With Chat on, the AI
picks the most relevant papers using what you wrote under "What I work on" (and your notes), and says why each
matters; otherwise you get the newest, as they are. With research.save_note on, each digest is also kept as a note in
your inbox (inbox/papers-<date>.md), every new paper grouped by source.

Projects: each project has a note, research/<project>/index.md, and research/index.md lists them all (those are the
default notes layout's places; core/layout.py has yours). For your code
repositories on this computer, each day's new commits are written under "## Log" in their project's note, so your notes
keep up with your code (a repository's project is its folder's name unless you map it: /repos add <folder> as
<project>). Runs logged with `kurooto runlog` (or `kurooto watch --log <project>`, or `kurooto.runlog.Run` in Python)
go to research/<project>/runs/ with the code's exact git state, and a line in the log; runs a script keeps in its
repository's own runs/ folder (runs/index.csv, research.repo_runs) get a line in the log too. When a project has had
no commits or runs for a few days (4 by default), Kurooto asks what's up: Busy, Working off-git, Remind me tomorrow
(a call the next day at 18:00 with Phone calls on, else a message) or Pausing. Your own text in these notes is never
changed; Kurooto only adds lines.
"""

from __future__ import annotations

import csv
import datetime as dt
import email.utils
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET  # noqa: S405 (parsed only after refusing DTDs and entities)
from importlib import resources
from pathlib import Path

from kurooto.core import layout, proc
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Module

register_defaults(
    "research",
    {
        "feeds": [],  # [{"type": "arxiv", "categories": ["cs.LG"], "keywords": []}, {"type": "rss", "url": ...}, ...]
        "about": "",  # what you work on, in a sentence or two: the AI uses it to pick
        "papers": "weekly mon 08:00",  # when the digest comes, e.g. "daily 08:00" or "weekly fri 17:00"
        "max_papers": 8,
        "rank": True,  # with Chat on, the AI picks and says why; off: the newest, as they are
        "window_days": 7,  # how far back each digest looks
        "repos": [],  # folders of git repositories on this computer
        "projects": {},  # repository folder -> project name (its notes: research/<project>/); unset: the folder's name
        "log_when": "daily 23:30",
        "idle_days": 4,  # ask about a project after this many days without commits (0: never)
        "idle_when": "daily 18:00",  # when that's checked
        "topics": [],  # older setting: plain keywords searched across all of arXiv (still works)
        "save_note": False,  # also keep each digest as a note in your inbox (inbox/papers-<date>.md)
        "repo_runs": "runs",  # the folder in each repository where scripts keep their runs (its index.csv); "": none
        "remind_by_call": True,  # "Remind me tomorrow" is a call at 18:00 when Phone calls is on
        "endpoints": {
            "arxiv": "https://export.arxiv.org/api/query",
            "biorxiv": "https://api.biorxiv.org/details",
            "pubmed": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
        },
    },
)
TYPES = {"arxiv": "arXiv", "biorxiv": "bioRxiv", "medrxiv": "medRxiv", "pubmed": "PubMed", "rss": "Feed"}
ARXIV_GAP = 3.0  # seconds between arXiv requests (arXiv asks for one every 3 seconds)
ATOM = {"a": "http://www.w3.org/2005/Atom"}


def catalog() -> dict:
    with resources.files("kurooto.data").joinpath("research_sources.json").open("rb") as f:
        return json.load(f)


def clean(s: str | None, n: int = 600) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()[:n]


def safe_xml(raw: bytes) -> ET.Element:
    if b"<!DOCTYPE" in raw[:2000] or b"<!ENTITY" in raw:
        raise ValueError("unexpected feed (DTD or entities)")
    return ET.fromstring(raw)  # noqa: S314 (DTDs and entities refused above)


def _first_text(el: ET.Element, names) -> str:
    """The first of these child elements that has text ("a:x" means Atom's x)."""
    for n in names:
        v = el.findtext(n, None, ATOM) if n.startswith("a:") else el.findtext(n)
        if v:
            return v
    return ""


def matches(paper: dict, keywords: list[str]) -> bool:
    if not keywords:
        return True
    hay = f"{paper.get('title', '')} {paper.get('summary', '')}".lower()
    return any(k.lower().strip() in hay for k in keywords if k.strip())


def describe(feed: dict) -> str:
    t = feed.get("type")
    kw = f" · keywords: {', '.join(feed['keywords'])}" if feed.get("keywords") else ""
    name = f"{feed['name']} — " if feed.get("name") else ""
    if t == "arxiv":
        names = {c: n for _, cs in catalog()["arxiv"] for c, n in cs}
        what = ", ".join(f"{names.get(c, c)} ({c})" for c in feed.get("categories") or [])
        if feed.get("query"):
            what = f"{feed['query']}" + (f" in {what}" if what else "")
        what = what or "all of arXiv"
    elif t in ("biorxiv", "medrxiv"):
        what = ", ".join(feed.get("subjects") or []) or "all subjects"
    elif t == "pubmed":
        what = feed.get("query", "")
    else:
        what = feed.get("url", "")
    return f"{name}{TYPES.get(t, t)}: {what}{kw}"


def validate(feed: dict) -> dict:
    """A feed as the dashboard sends it, checked and cleaned (raises ValueError with what's wrong)."""
    t = feed.get("type")
    kw = [k.strip()[:60] for k in (feed.get("keywords") or []) if str(k).strip()][:20]
    cat = catalog()
    named = {"name": str(feed["name"]).strip()[:60]} if str(feed.get("name") or "").strip() else {}
    if t == "arxiv":
        known = {c for _, cs in cat["arxiv"] for c, _ in cs}
        cats = [c for c in feed.get("categories") or [] if c in known][:30]
        query = re.sub(r"\s+", " ", str(feed.get("query") or "")).strip()[:500]
        if query:  # a search in arXiv's own words: ti:, abs:, all:, cat:, AND, OR, ANDNOT, brackets
            if query.count("(") != query.count(")") or query.count('"') % 2:
                raise ValueError("that arXiv search has an unclosed bracket or quote")
            return {"type": t, "query": query, "categories": cats, "keywords": kw, **named}
        if not cats and not kw:
            raise ValueError("pick at least one arXiv field, or give keywords to search all of arXiv")
        return {"type": t, "categories": cats, "keywords": kw, **named}
    if t in ("biorxiv", "medrxiv"):
        subs = [s for s in feed.get("subjects") or [] if s in cat[t]]
        if not subs and not kw:
            raise ValueError(f"pick at least one {TYPES[t]} subject, or give keywords")
        return {"type": t, "subjects": subs, "keywords": kw, **named}
    if t == "pubmed":
        q = str(feed.get("query", "")).strip()[:300]
        if not q:
            raise ValueError("give PubMed something to search for")
        return {"type": t, "query": q, **named}
    if t == "rss":
        url = str(feed.get("url", "")).strip()
        if not url.startswith(("https://", "http://")):
            raise ValueError("a feed needs its web address (https://…)")
        return {"type": t, "url": url[:500], "keywords": kw, **named}
    raise ValueError(f"unknown kind of source {t!r}")


# ---------------------------------------------------------------------------------------- project notes
HUB = """# Research

Your projects, one note each. {name} adds a line here for each new project and a dated line to a project's Log when
there are new commits or runs; write your own text anywhere, it's never changed.

## Projects
"""
IDLE_CHOICES = ["Busy", "Working off-git", "Remind me tomorrow", "Pausing it"]


def slug(name: str) -> str:
    """A project's folder name: lowercase letters, digits and dashes."""
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")[:60] or "project"


def project_note(workspace, project: str) -> Path:
    """`workspace`: the App, a layout.Layout, or a notes folder (the default layout)."""
    return layout.of(workspace).path("project", project=slug(project))


def ensure_project(workspace, project: str, assistant: str = "Kurooto", repos: list[str] | None = None) -> Path:
    """The project's note (made if missing), listed in the hub note research/index.md (made if missing)."""
    from kurooto.core.tools import add_to_section

    lay = layout.of(workspace)
    note = project_note(lay, project)
    if not note.exists():
        note.parent.mkdir(parents=True, exist_ok=True)
        where = f"Code: {', '.join(repos)}.\n\n" if repos else ""
        note.write_text(
            lay.frontmatter("project", note, title=project, bare=True)
            + f"# {project}\n\n{where}Notes on this project go here. {assistant} adds dated lines to the Log below.\n\n"
            "## Log\n",
            encoding="utf-8",
        )
    hub = lay.path("research")
    if not hub.exists():
        hub.parent.mkdir(parents=True, exist_ok=True)
        hub.write_text(
            lay.frontmatter("research", hub, title="Research", bare=True) + HUB.format(name=assistant), encoding="utf-8"
        )
    link = f"[[{lay.link('project', project=slug(project))}|{project}]]"
    text = hub.read_text(encoding="utf-8")
    if link not in text:
        hub.write_text(add_to_section(text, "Projects", f"- {link} (since {now():%Y-%m-%d})"), encoding="utf-8")
    return note


def log_lines(workspace, project: str, lines: list[str], assistant: str = "Kurooto") -> int:
    """Add lines to the end of the project note's "## Log" (each only once). Returns how many were added."""
    from kurooto.core.tools import add_to_section

    note = ensure_project(workspace, project, assistant)
    text = note.read_text(encoding="utf-8")
    new = [ln for ln in lines if ln not in text]
    if new:
        note.write_text(add_to_section(text, "Log", "\n".join(new)), encoding="utf-8")
    return len(new)


class Research(Module):
    id = "research"
    title = "Research"
    heavy = True  # waits for the charger on battery (saver mode, core/power.py)
    description = "A digest of new papers in your fields (arXiv, bioRxiv, medRxiv, PubMed, any feed), and project logs."
    privacy = "Your fields and keywords go to the sources you pick (all public). Commit messages stay on this computer."

    def feeds(self) -> list[dict]:
        out = list(self.setting("feeds") or [])
        if self.setting("topics"):  # the older setting: plain keywords across all of arXiv
            out.append({"type": "arxiv", "categories": [], "keywords": list(self.setting("topics"))})
        return out

    def ready(self):
        if not self.feeds() and not self.setting("repos"):
            return False, "choose your fields (the dashboard's Research tab), or add a repository"
        return True, ""

    def health(self):
        ok, why = self.ready()
        if not ok:
            return ok, why
        repos = self.setting("repos") or []
        gone = [r for r in repos if not (Path(r).expanduser() / ".git").exists()]
        if gone:
            return False, f"repository folder missing: {gone[0]} (/repos remove it, or put it back)"
        if repos and not self.git_exe():
            return False, "project logs need Git"
        bits = [f"{len(self.feeds())} sources"] if self.feeds() else []
        if repos:
            bits.append(f"{len(self.projects())} projects from {len(repos)} repositories")
        return True, ", ".join(bits)

    def start(self):
        self.every("papers", self.setting("papers") or "weekly mon 08:00", lambda p: self.papers())
        self.every("logs", self.setting("log_when") or "daily 23:30", lambda p: self.project_logs())
        self.every("idle", self.setting("idle_when") or "daily 18:00", lambda p: self.idle_check(), respect="quiet")
        self.action("remind", self._remind)
        ask = getattr(self.app, "ask", None)
        if ask is not None:
            ask.hooks["research.idle"] = self._idle_answer

    def ep(self, name: str) -> str:
        return (self.setting("endpoints") or {})[name].rstrip("/")

    def _get(self, url: str, timeout: float = 60) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": "kurooto (personal research digest)"})  # noqa: S310
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (public sources, https)
            return r.read(10 * 1024 * 1024)

    # --------------------------------------------------------------------------------------- sources
    def fetch(self, feed: dict, days: int | None = None) -> list[dict]:
        """New papers from one source in the last `days` days: [{id, title, authors, summary, link, date, source}]."""
        days = days or self.setting("window_days") or 7
        since = now() - dt.timedelta(days=days)
        t = feed.get("type")
        papers = {
            "arxiv": self._arxiv,
            "biorxiv": self._rxiv,
            "medrxiv": self._rxiv,
            "pubmed": self._pubmed,
            "rss": self._rss,
        }[t](feed, since)
        return [p for p in papers if matches(p, feed.get("keywords") or [])]

    def _arxiv(self, feed: dict, since: dt.datetime) -> list[dict]:
        parts = []
        if feed.get("query"):  # arXiv's own search words; keywords then only filter what it finds
            parts.append(f"({feed['query']})")
        if feed.get("categories"):
            parts.append("(" + " OR ".join(f"cat:{c}" for c in feed["categories"]) + ")")
        if feed.get("keywords") and not feed.get("query"):
            words = " OR ".join(f'abs:"{k}" OR ti:"{k}"' for k in feed["keywords"])
            parts.append(f"({words})")
        q = urllib.parse.urlencode(
            {
                "search_query": " AND ".join(parts),
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "max_results": 100,
            }
        )
        root = safe_xml(self._get(f"{self.ep('arxiv')}?{q}"))
        out = []
        for e in root.findall("a:entry", ATOM):
            aid = re.sub(r"v\d+$", "", (e.findtext("a:id", "", ATOM) or "").rsplit("/abs/", 1)[-1])
            published = e.findtext("a:published", "", ATOM)
            try:
                when = dt.datetime.fromisoformat(published.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
            except ValueError:
                when = now()
            if when < since:
                continue
            out.append(
                {
                    "id": f"arxiv:{aid}",
                    "title": clean(e.findtext("a:title", "", ATOM), 300),
                    "authors": [a.findtext("a:name", "", ATOM) for a in e.findall("a:author", ATOM)][:4],
                    "summary": clean(e.findtext("a:summary", "", ATOM)),
                    "link": f"https://arxiv.org/abs/{aid}",
                    "date": when.date().isoformat(),
                    "source": "arXiv",
                }
            )
        return out

    def _rxiv(self, feed: dict, since: dt.datetime) -> list[dict]:
        server = feed["type"]
        subjects = {s.lower() for s in feed.get("subjects") or []}
        out, cursor = [], 0
        for _ in range(20):  # 100 per page; a busy week of bioRxiv is about 1,000 papers
            url = f"{self.ep('biorxiv')}/{server}/{since:%Y-%m-%d}/{now():%Y-%m-%d}/{cursor}"
            data = json.loads(self._get(url))
            batch = data.get("collection") or []
            for p in batch:
                if subjects and (p.get("category") or "").lower() not in subjects:
                    continue
                out.append(
                    {
                        "id": f"doi:{p.get('doi')}",
                        "title": clean(p.get("title"), 300),
                        "authors": [a.strip() for a in (p.get("authors") or "").split(";") if a.strip()][:4],
                        "summary": clean(p.get("abstract")),
                        "date": p.get("date", ""),
                        "link": f"https://www.{server}.org/content/{p.get('doi')}v{p.get('version', 1)}",
                        "source": f"{TYPES[server]} ({p.get('category', '')})",
                    }
                )
            total = int(((data.get("messages") or [{}])[0]).get("total") or 0)
            cursor += len(batch)
            if not batch or cursor >= total:
                break
        return list({p["id"]: p for p in out}.values())  # a paper revised in the window appears once

    def _pubmed(self, feed: dict, since: dt.datetime) -> list[dict]:
        days = max(1, (now() - since).days)
        q = urllib.parse.urlencode(
            {
                "db": "pubmed",
                "term": feed["query"],
                "reldate": days,
                "datetype": "edat",
                "retmax": 60,
                "retmode": "json",
                "sort": "pub_date",
            }
        )
        ids = json.loads(self._get(f"{self.ep('pubmed')}/esearch.fcgi?{q}")).get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        q = urllib.parse.urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "json"})
        res = json.loads(self._get(f"{self.ep('pubmed')}/esummary.fcgi?{q}")).get("result", {})
        out = []
        for pid in ids:
            r = res.get(pid) or {}
            out.append(
                {
                    "id": f"pubmed:{pid}",
                    "title": clean(r.get("title"), 300),
                    "authors": [a.get("name", "") for a in r.get("authors", [])][:4],
                    "summary": clean(r.get("fulljournalname") or r.get("source")),
                    "date": r.get("pubdate", ""),
                    "link": f"https://pubmed.ncbi.nlm.nih.gov/{pid}/",
                    "source": f"PubMed ({r.get('source', '')})",
                }
            )
        return out

    def _rss(self, feed: dict, since: dt.datetime) -> list[dict]:
        root = safe_xml(self._get(feed["url"]))
        out = []
        items = (
            root.findall(".//item")
            + root.findall(".//a:entry", ATOM)
            + root.findall(".//{http://purl.org/rss/1.0/}item")
        )
        for it in items[:200]:
            text = lambda *names, it=it: _first_text(it, names)  # noqa: E731

            link = text("link", "{http://purl.org/rss/1.0/}link")
            if not link:
                el = it.find("a:link", ATOM)
                link = el.get("href", "") if el is not None else ""
            raw_date = text("pubDate", "a:updated", "a:published", "{http://purl.org/dc/elements/1.1/}date")
            when = None
            try:
                when = email.utils.parsedate_to_datetime(raw_date)
            except (TypeError, ValueError):
                try:
                    when = dt.datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                except ValueError:
                    when = None
            if when is not None:
                when = when.astimezone().replace(tzinfo=None) if when.tzinfo else when
                if when < since:
                    continue
            title = clean(text("title", "a:title", "{http://purl.org/rss/1.0/}title"), 300)
            out.append(
                {
                    "id": f"link:{link or title}",
                    "title": title,
                    "authors": [],
                    "summary": clean(
                        text("description", "a:summary", "a:content", "{http://purl.org/rss/1.0/}description")
                    ),
                    "link": link,
                    "date": when.date().isoformat() if when else "",
                    "source": urllib.parse.urlsplit(feed["url"]).hostname or "feed",
                }
            )
        return out

    # ---------------------------------------------------------------------------------------- the digest
    def collect(self, mark_seen: bool = True) -> tuple[list[dict], list[str]]:
        """New papers from every source (not sent before), and the sources that failed."""
        seen_file = self.app.paths.state / "research-papers.json"
        seen = jload(seen_file, {}) or {}
        new, failed, ids = [], [], set()
        last_arxiv = 0.0
        for feed in self.feeds():
            try:
                if feed.get("type") == "arxiv":  # one request every 3 seconds, as arXiv asks
                    wait = last_arxiv + ARXIV_GAP - time.monotonic()
                    if last_arxiv and wait > 0:
                        time.sleep(wait)
                    last_arxiv = time.monotonic()
                for p in self.fetch(feed):
                    if p["id"] in seen or p["id"] in ids or not p["title"]:
                        continue
                    ids.add(p["id"])
                    new.append({**p, "group": feed.get("name") or describe(feed)})
            except Exception as e:
                failed.append(f"{describe(feed)} ({type(e).__name__})")
                self.app.events.emit("research_failed", error=str(e)[:200])
        if mark_seen:
            for p in new:
                seen[p["id"]] = now().date().isoformat()
            jsave(seen_file, dict(list(seen.items())[-20000:]))
        return new, failed

    def papers(self) -> list[dict]:
        new, failed = self.collect()
        self.app.events.emit("research_papers", new=len(new), failed=len(failed))
        n = self.setting("max_papers") or 8
        note = f"\n\n(Couldn't reach: {'; '.join(failed)})" if failed else ""
        if not new:
            if failed:
                self.app.notify("No new papers this time." + note, kind="result")
            return []
        if self.setting("save_note"):
            try:
                note += f"\n\nAll {len(new)} are in {layout.shown(self.app, self.save_note(new))}."
            except OSError as e:
                note += f"\n\n(Couldn't keep them as a note: {e})"
        if self.setting("rank") and self.app.is_on("chat") and len(new) > n:
            listing = "\n\n".join(
                f"[{i + 1}] {p['title']} ({', '.join(p['authors'][:3])}; {p['source']})\n"
                f"{p['summary'][:400]}\n{p['link']}"
                for i, p in enumerate(new[:120])
            )
            about = self.setting("about") or "(not given: use my notes to tell)"
            self.app.jobs.submit(
                f"These are new papers from my research sources. What I work on: {about}\n\nPick the {n} most relevant "
                f"to me, each as: the title, the link, and one line on why it matters to me. Then one line listing any "
                f"others worth a glance by number.{note}\n\n{listing}",
                title="New papers",
                effort="medium",
                background=True,
            )
        else:
            rows = [f"• {p['title']} ({', '.join(p['authors'][:2]) or p['source']})\n  {p['link']}" for p in new[:n]]
            more = f"\n…and {len(new) - n} more." if len(new) > n else ""
            self.app.notify(f"New papers ({len(new)}):\n" + "\n".join(rows) + more + note, kind="result")
        return new

    def save_note(self, papers: list[dict]) -> Path:
        """Every new paper, grouped by source, in a note in the inbox (inbox/papers-<date>.md). A second digest on
        the same day adds its sections to the end."""
        lay = layout.of(self.app)
        day = f"{now():%Y-%m-%d}"
        f = lay.path("note", slug=f"papers-{day}")
        groups: dict[str, list[dict]] = {}
        for p in papers:
            groups.setdefault(p.get("group") or p.get("source") or "Papers", []).append(p)
        body = []
        for group, ps in groups.items():
            body.append(f"## {group}\n")
            for p in ps:
                authors = ", ".join(p["authors"][:3]) + (" et al." if len(p["authors"]) > 3 else "")
                bits = " · ".join(x for x in (authors, p.get("date", "")) if x)
                summary = f"\n  > {p['summary'][:300]}…" if p.get("summary") else ""
                body.append(f"- [{p['title']}]({p['link']})" + (f" · {bits}" if bits else "") + summary)
            body.append("")
        f.parent.mkdir(parents=True, exist_ok=True)
        if f.exists():
            with open(f, "a", encoding="utf-8") as fh:
                fh.write("\n" + "\n".join(body))
        else:
            head = lay.frontmatter("note", f, title=f"New papers {day}", tags=["inbox", "papers"])
            f.write_text(
                head + f"# New papers {day}\n\n{len(papers)} new since the last digest. Keep what matters as a note "
                "of its own; this one is yours to delete.\n\n" + "\n".join(body),
                encoding="utf-8",
            )
        return f

    # -------------------------------------------------------------------------------------- project logs
    def git_exe(self) -> str | None:
        ns = self.app.modules.get("notes_sync")
        return (ns.git_exe() if ns else None) or proc.which("git")

    def project_of(self, repo: Path | str) -> str:
        """The project a repository belongs to: its mapping in research.projects, else its folder's name."""
        mapping = self.setting("projects") or {}
        path = Path(repo).expanduser()
        for k, v in mapping.items():
            if v and Path(k).expanduser() == path:
                return str(v)
        return path.name

    def projects(self) -> dict[str, list[str]]:
        """Project -> its repository folders."""
        out: dict[str, list[str]] = {}
        for repo in self.setting("repos") or []:
            out.setdefault(self.project_of(repo), []).append(str(Path(repo).expanduser()))
        return out

    def project_logs(self) -> int:
        """New commits in each repository since last time, as one dated line per day in its project's Log.
        Returns how many repositories had new commits. Read-only on the repositories."""
        git = self.git_exe()
        if not git:
            return 0
        env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"}
        state_file = self.app.paths.state / "research-logs.json"
        st = jload(state_file, {}) or {}
        written = 0
        for repo in self.setting("repos") or []:
            path = Path(repo).expanduser()
            if not (path / ".git").exists():
                continue
            rec = st.get(str(path))
            rec = {"head": rec} if isinstance(rec, str) else dict(rec or {})  # 0.1.0 kept only the head
            head = proc.run([git, "-C", str(path), "rev-parse", "HEAD"], timeout=30, env=env).out.strip()
            if not head:
                continue
            if not rec.get("last_day"):
                rec["last_day"] = proc.run(
                    [git, "-C", str(path), "log", "-1", "--format=%cd", "--date=short"], timeout=30, env=env
                ).out.strip()
            runs = self.repo_runs(path, rec)
            if runs:
                log_lines(self.app, self.project_of(path), runs, self.app.name)
                written += 1
            if rec.get("head") == head:
                st[str(path)] = rec
                continue
            rng = [f"{rec['head']}..HEAD"] if rec.get("head") else ["--since=1.day"]
            r = proc.run(
                [git, "-C", str(path), "log", *rng, "--no-merges", "--reverse", "--date=short", "--format=%cd%x09%s"],
                timeout=60,
                env=env,
            )
            by_day: dict[str, list[str]] = {}
            for ln in r.out.splitlines()[:500]:
                day, _, subject = ln.partition("\t")
                if subject.strip():
                    by_day.setdefault(day, []).append(subject.strip())
            rec["head"] = head
            if by_day:
                rec["last_day"] = max([*by_day, rec.get("last_day") or ""])
                lines = []
                for day, subs in sorted(by_day.items()):
                    shown = "; ".join(subs[:3]) + (f"; +{len(subs) - 3} more" if len(subs) > 3 else "")
                    n = f"{len(subs)} commit{'s' if len(subs) > 1 else ''}"
                    lines.append(f"- **{day}** | git:{path.name} — {n}: {shown}")
                log_lines(self.app, self.project_of(path), lines, self.app.name)
                written += 1
            st[str(path)] = rec
        jsave(state_file, st)
        self.app.events.emit("research_logs", repos=written)
        return written

    def repo_runs(self, repo: Path, rec: dict) -> list[str]:
        """Runs a script keeps in its repository (<repo>/runs/index.csv, as kurooto.runlog.Run writes it without a
        project): a Log line for each one not logged yet. The first time, only the last 30 days'."""
        folder = str(self.setting("repo_runs") or "").strip()
        index = repo / folder / "index.csv" if folder else None
        if index is None or not index.is_file():
            return []
        try:
            with open(index, newline="", encoding="utf-8", errors="replace") as f:
                rows = list(csv.DictReader(f))[-2000:]
        except (OSError, csv.Error):
            return []
        first = "runs" not in rec
        seen = set(rec.get("runs") or [])
        cutoff = (now() - dt.timedelta(days=30)).date().isoformat()
        lines = []
        for r in rows:
            rid = (r.get("run") or r.get("name") or "").strip()
            if not rid or rid in seen:
                continue
            seen.add(rid)
            day = (r.get("start") or r.get("time") or r.get("started") or "")[:10]
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
                day = f"{now():%Y-%m-%d}"
            if first and day < cutoff:
                continue
            rec["last_day"] = max(rec.get("last_day") or "", day)
            status = (r.get("status") or "").strip() or "logged"
            try:
                took = f" after {_took(float(r.get('duration_s') or ''))}"
            except ValueError:
                took = ""
            last = ""
            try:
                vals = json.loads(r.get("last_metrics") or "{}")
                if isinstance(vals, dict):
                    last = ", ".join(f"{k}={_short(v)}" for k, v in list(vals.items())[:4] if k != "time")
            except ValueError:
                pass
            extra = r.get("summary") or r.get("notes") or ""
            what = f"{status}{took}" + (f" ({last})" if last else "") + (f": {extra[:200]}" if extra else "")
            lines.append(f"- **{day}** | run:{repo.name}/{rid} — {what}")
        rec["runs"] = sorted(seen)[-2000:]
        return lines

    def sync_now(self) -> tuple[bool, str]:
        n = self.project_logs()
        return True, f"{n} project{'s' if n != 1 else ''} with new commits" if n else "no new commits"

    # ------------------------------------------------------------------------------------- quiet projects
    def quiet_idle_once(self) -> None:
        """Updating from 0.1 (core/upgrade.py): the first check only notes which projects are quiet already, so it
        doesn't ask about all of them at once; it asks when one goes quiet after that."""
        f = self.app.paths.state / "research-logs.json"
        jsave(f, {**(jload(f, {}) or {}), "_quiet_once": True})

    def idle_check(self) -> list[str]:
        """Ask about each project with no commits for research.idle_days days (once per quiet stretch)."""
        days = int(self.setting("idle_days") or 0)
        ask = getattr(self.app, "ask", None)
        if days <= 0 or ask is None:
            return []
        state_file = self.app.paths.state / "research-logs.json"
        self.project_logs()  # fresh last-commit days
        st = jload(state_file, {}) or {}
        asked = st.setdefault("_asked", {})
        quiet_once = bool(st.pop("_quiet_once", False))  # updated from 0.1: these were quiet already
        out = []
        for project, repos in self.projects().items():
            last = max((st.get(r, {}) or {}).get("last_day") or "" for r in repos)
            if not last:
                continue
            try:
                idle = (now().date() - dt.date.fromisoformat(last)).days
            except ValueError:
                continue
            if idle < days or asked.get(project) == last:
                continue
            asked[project] = last
            if quiet_once:
                continue
            ask.ask(
                f"No commits to {project} for {idle} days. What's the plan?",
                choices=IDLE_CHOICES,
                hook="research.idle",
                hook_payload={"project": project},
                expires="3d",
                source=self.id,
                title="Research",
            )
            out.append(project)
        jsave(state_file, st)
        return out

    def _idle_answer(self, q: dict, answer: str) -> str:
        project = (q.get("hook_payload") or {}).get("project") or "the project"
        log_lines(self.app, project, [f"- **{now():%Y-%m-%d}** | you — {answer.strip()[:300]}"], self.app.name)
        self.app.events.emit("research_idle_answer", choice=answer.strip()[:40])
        if "remind" in answer.lower():
            when = dt.datetime.combine(now().date() + dt.timedelta(days=1), dt.time(18, 0))
            calls = self.app.modules.get("calls")
            if self.setting("remind_by_call") and calls and self.app.is_on("calls") and calls.ready()[0]:
                calls.schedule(
                    when,
                    f"A reminder they asked for yesterday: their research project {project} has been quiet. Ask what "
                    "the plan is, and help them pick one small next step.",
                    key=f"research:{slug(project)}",
                )
                return f"I'll call you about {project} tomorrow at 18:00."
            self.app.scheduler.at(
                when, "research.remind", {"project": project}, key=f"research:remind:{slug(project)}", module=self.id
            )
            return f"I'll remind you about {project} tomorrow at 18:00."
        if "paus" in answer.lower():
            return f"Noted: {project} is paused. I won't ask again until there are new commits."
        return f"Noted in {project}'s log."

    def _remind(self, p: dict) -> None:
        self.app.notify(f"You asked me to remind you about {p.get('project', 'your project')} today.", kind="reminder")

    def call_outcome(self, key: str, outcome: str) -> bool:
        """The reminder call about a quiet project didn't happen: a message instead."""
        if outcome in ("missed", "decline", "skip"):
            project = key.partition(":")[2] or "your project"
            self.app.notify(f"Missed my call: you asked me to remind you about {project} today.", kind="reminder")
        return False

    def weekly_lines(self) -> list[str]:
        return []

    # ------------------------------------------------------------------------------------------- settings
    def save(self, b: dict) -> dict:
        """What the Research tab sends: sources, what you work on, when, how many, ranking, repositories."""
        s = self.app.settings
        if "feeds" in b:
            s.set("research.feeds", [validate(f) for f in b["feeds"]][:30])
        if "about" in b:
            s.set("research.about", str(b["about"]).strip()[:1000])
        if "papers" in b:
            spec = str(b["papers"]).strip()
            if not re.fullmatch(r"(daily \d{2}:\d{2}|weekly (mon|tue|wed|thu|fri|sat|sun) \d{2}:\d{2})", spec):
                raise ValueError("when: daily HH:MM or weekly mon HH:MM")
            s.set("research.papers", spec)
        if "max_papers" in b:
            s.set("research.max_papers", max(1, min(30, int(b["max_papers"]))))
        if "rank" in b:
            s.set("research.rank", bool(b["rank"]))
        if "repos" in b:
            repos = [str(r).strip() for r in b["repos"] if str(r).strip()]
            bad = [r for r in repos if not (Path(r).expanduser() / ".git").exists()]
            if bad:
                raise ValueError(f"not a git repository: {bad[0]}")
            s.set("research.repos", repos)
        if "projects" in b:
            if not isinstance(b["projects"], dict):
                raise ValueError("projects: a repository folder -> project name for each")
            s.set("research.projects", {str(k).strip(): str(v).strip()[:80] for k, v in b["projects"].items() if v})
        if "topics" in b:
            s.set("research.topics", [str(t).strip() for t in b["topics"] if str(t).strip()])
        if self.app.is_on(self.id):
            self.start()  # a new time for the digest
        return self.view()

    def view(self) -> dict:
        return {
            "feeds": [{**f, "label": describe(f)} for f in self.setting("feeds") or []],
            "topics": self.setting("topics") or [],
            "about": self.setting("about") or "",
            "papers": self.setting("papers"),
            "max_papers": self.setting("max_papers"),
            "rank": bool(self.setting("rank")),
            "repos": self.setting("repos") or [],
            "projects": {r: self.project_of(r) for r in self.setting("repos") or []},
            "chat": self.app.is_on("chat"),
            "on": self.app.is_on(self.id),
        }

    def setup_form(self) -> dict:
        return {
            "intro": "What you work on, in a sentence or two, and some keywords to start with. Afterwards, pick your "
            "fields and sources (arXiv, bioRxiv, medRxiv, PubMed, any journal's feed) on the dashboard's Research tab.",
            "links": [["arXiv's fields", "https://arxiv.org/category_taxonomy"]],
            "fields": [
                {
                    "name": "about",
                    "label": "What I work on",
                    "type": "textarea",
                    "placeholder": "e.g. graph neural networks for molecules",
                },
                {
                    "name": "keywords",
                    "label": "Keywords (comma-separated)",
                    "type": "text",
                    "placeholder": "e.g. message passing, molecular property prediction",
                },
            ],
        }

    def configure(self, values: dict) -> dict:
        kw = [k.strip() for k in str(values.get("keywords", "")).split(",") if k.strip()]
        feeds = list(self.setting("feeds") or [])
        if kw:
            feeds.append({"type": "arxiv", "categories": [], "keywords": kw})
        try:
            self.save({"about": values.get("about", ""), "feeds": feeds})
        except ValueError as e:
            return {"ok": False, "message": str(e)}
        if not self.feeds():
            return {"ok": False, "message": "Give at least one keyword (or pick fields on the Research tab later)."}
        return {"ok": True, "message": "Saved. Pick more fields and sources on the dashboard's Research tab."}

    # ------------------------------------------------------------------------------------------ telegram
    def commands(self):
        return [
            Command("papers", "the new-papers digest now", lambda m, a: f"{len(self.papers())} new papers found."),
            Command("feeds", "your research sources (change them on the dashboard's Research tab)", self._feeds),
            Command("topics", "quick keywords searched across arXiv: /topics add …, /topics remove …", self._topics),
            Command(
                "repos",
                "repositories for project logs: /repos add <folder> [as <project>], /repos remove …",
                self._repos,
            ),
        ]

    def _feeds(self, msg: Incoming, arg: str) -> str:
        fs = self.feeds()
        when = self.setting("papers")
        return (
            ("Your sources:\n" + "\n".join(f"• {describe(f)}" for f in fs) + f"\nDigest: {when}.")
            if fs
            else ("No sources yet: pick your fields on the dashboard's Research tab.")
        )

    def _edit_list(self, key: str, arg: str, check=None) -> str:
        cur = list(self.setting(key) or [])
        verb, _, rest = arg.strip().partition(" ")
        rest = rest.strip()
        if verb == "add" and rest:
            if check:
                err = check(rest)
                if err:
                    return err
            if rest not in cur:
                cur.append(rest)
        elif verb == "remove" and rest:
            cur = [x for x in cur if x != rest]
        elif arg.strip():
            return f"Usage: /{key} add …  or  /{key} remove …"
        self.app.settings.set(f"research.{key}", cur)
        return "\n".join(f"• {x}" for x in cur) or "None yet."

    def _topics(self, msg: Incoming, arg: str) -> str:
        return self._edit_list("topics", arg)

    def _repos(self, msg: Incoming, arg: str) -> str:
        m = re.fullmatch(r"(add|map)\s+(.+?)\s+(?:as|to|->)\s+(.+)", arg.strip(), re.I)
        if m:  # /repos add <folder> as <project>: the repository's commits go to that project's note
            folder, project = m.group(2).strip().strip('"'), m.group(3).strip().strip('"')
            if not (Path(folder).expanduser() / ".git").exists():
                return "That folder isn't a git repository."
            mapping = dict(self.setting("projects") or {})
            mapping[folder] = project
            self.app.settings.set("research.projects", mapping)
            arg = f"add {folder}"
        out = self._edit_list(
            "repos",
            arg,
            lambda p: None if (Path(p).expanduser() / ".git").exists() else "That folder isn't a git repository.",
        )
        if out.startswith("•"):
            out = "\n".join(f"{ln} → {self.project_of(ln[2:])}" for ln in out.splitlines())
        return out


def _took(secs: float) -> str:
    secs = int(secs)
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m{secs % 60:02d}s"
    return f"{secs // 3600}h{secs % 3600 // 60:02d}m"


def _short(v) -> str:
    return f"{v:.4g}" if isinstance(v, float) else str(v)[:30]
