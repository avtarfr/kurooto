"""Research: new papers in your fields, from the sources you choose, as a digest on Telegram (weekly by default), and
project logs from your code.

Sources (the dashboard's Research tab, or Settings → research.feeds):
    arXiv     fields by category (all 155: maths, physics, computer science, statistics, quantitative biology and
              finance, economics, electrical engineering)
    bioRxiv   biology preprints by subject area (neuroscience, genomics, ecology, ...)
    medRxiv   medical preprints by subject area (epidemiology, oncology, psychiatry, ...)
    PubMed    published biomedical papers for a search (PubMed's own search words work)
    a feed    any journal's or blog's RSS or Atom address
Each source can be narrowed with keywords (any of them, in the title or abstract). With Chat on, the AI picks the most
relevant papers using what you wrote under "What I work on" (and your notes), and says why each matters; otherwise you
get the newest, as they are.

Project logs: for your code repositories on this computer, each day's new commits are written into a log note
(research/<repository>-log.md in your notes), so your notes keep up with your code.
"""

from __future__ import annotations

import datetime as dt
import email.utils
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET  # noqa: S405 (parsed only after refusing DTDs and entities)
from importlib import resources
from pathlib import Path

from kurooto.core import proc
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
        "log_when": "daily 23:30",
        "topics": [],  # older setting: plain keywords searched across all of arXiv (still works)
        "endpoints": {
            "arxiv": "https://export.arxiv.org/api/query",
            "biorxiv": "https://api.biorxiv.org/details",
            "pubmed": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
        },
    },
)
TYPES = {"arxiv": "arXiv", "biorxiv": "bioRxiv", "medrxiv": "medRxiv", "pubmed": "PubMed", "rss": "Feed"}
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
    if t == "arxiv":
        names = {c: n for _, cs in catalog()["arxiv"] for c, n in cs}
        what = ", ".join(f"{names.get(c, c)} ({c})" for c in feed.get("categories") or []) or "all of arXiv"
    elif t in ("biorxiv", "medrxiv"):
        what = ", ".join(feed.get("subjects") or []) or "all subjects"
    elif t == "pubmed":
        what = feed.get("query", "")
    else:
        what = feed.get("url", "")
    return f"{TYPES.get(t, t)}: {what}{kw}"


def validate(feed: dict) -> dict:
    """A feed as the dashboard sends it, checked and cleaned (raises ValueError with what's wrong)."""
    t = feed.get("type")
    kw = [k.strip()[:60] for k in (feed.get("keywords") or []) if str(k).strip()][:20]
    cat = catalog()
    if t == "arxiv":
        known = {c for _, cs in cat["arxiv"] for c, _ in cs}
        cats = [c for c in feed.get("categories") or [] if c in known][:30]
        if not cats and not kw:
            raise ValueError("pick at least one arXiv field, or give keywords to search all of arXiv")
        return {"type": t, "categories": cats, "keywords": kw}
    if t in ("biorxiv", "medrxiv"):
        subs = [s for s in feed.get("subjects") or [] if s in cat[t]]
        if not subs and not kw:
            raise ValueError(f"pick at least one {TYPES[t]} subject, or give keywords")
        return {"type": t, "subjects": subs, "keywords": kw}
    if t == "pubmed":
        q = str(feed.get("query", "")).strip()[:300]
        if not q:
            raise ValueError("give PubMed something to search for")
        return {"type": t, "query": q}
    if t == "rss":
        url = str(feed.get("url", "")).strip()
        if not url.startswith(("https://", "http://")):
            raise ValueError("a feed needs its web address (https://…)")
        return {"type": t, "url": url[:500], "keywords": kw}
    raise ValueError(f"unknown kind of source {t!r}")


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

    def start(self):
        self.every("papers", self.setting("papers") or "weekly mon 08:00", lambda p: self.papers())
        self.every("logs", self.setting("log_when") or "daily 23:30", lambda p: self.project_logs())

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
        if feed.get("categories"):
            parts.append("(" + " OR ".join(f"cat:{c}" for c in feed["categories"]) + ")")
        if feed.get("keywords"):
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
        for feed in self.feeds():
            try:
                for p in self.fetch(feed):
                    if p["id"] in seen or p["id"] in ids or not p["title"]:
                        continue
                    ids.add(p["id"])
                    new.append(p)
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

    # -------------------------------------------------------------------------------------- project logs
    def project_logs(self) -> int:
        git = self.app.modules["notes_sync"].git_exe() if "notes_sync" in self.app.modules else None
        if not git:
            return 0
        state_file = self.app.paths.state / "research-logs.json"
        last = jload(state_file, {}) or {}
        written = 0
        for repo in self.setting("repos") or []:
            path = Path(repo).expanduser()
            if not (path / ".git").exists():
                continue
            head = proc.run([git, "-C", str(path), "rev-parse", "HEAD"], timeout=30).out.strip()
            if not head or last.get(str(path)) == head:
                continue
            rng = f"{last[str(path)]}..HEAD" if last.get(str(path)) else "--since=1.day"
            r = proc.run(
                [git, "-C", str(path), "log", "--no-merges", "--date=short", "--format=%ad %h %s", rng], timeout=60
            )
            commits = [ln for ln in r.out.splitlines() if ln.strip()][:200]
            last[str(path)] = head
            if not commits:
                continue
            note = self.app.workspace / "research" / f"{path.name}-log.md"
            note.parent.mkdir(parents=True, exist_ok=True)
            new = not note.exists()
            with open(note, "a", encoding="utf-8") as f:
                if new:
                    f.write(
                        f"# {path.name}: project log\n\nWritten from the repository's commits by {self.app.name}.\n"
                    )
                f.write(f"\n## {now():%Y-%m-%d}\n\n" + "\n".join(f"- {c}" for c in reversed(commits)) + "\n")
            written += 1
        jsave(state_file, last)
        self.app.events.emit("research_logs", repos=written)
        return written

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
            Command("repos", "repositories for project logs: /repos add <folder>, /repos remove …", self._repos),
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
        return self._edit_list(
            "repos",
            arg,
            lambda p: None if (Path(p).expanduser() / ".git").exists() else "That folder isn't a git repository.",
        )
