"""Research: every kind of source against a local fake (arXiv, bioRxiv/medRxiv, PubMed, RSS and Atom feeds), the
digest (plain, or picked by the AI), what the dashboard's Research tab sends, and project logs from a real git repo."""

from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from kurooto.modules import research as rmod

TODAY = dt.datetime.now()
RECENT, OLD = (TODAY - dt.timedelta(days=2)), (TODAY - dt.timedelta(days=40))


def atom_entry(aid: str, title: str, when: dt.datetime, summary: str = "x") -> str:
    return (
        f"<entry><id>http://arxiv.org/abs/{aid}v2</id><published>{when:%Y-%m-%dT%H:%M:%SZ}</published>"
        f"<title>{title}</title><summary>{summary}</summary><author><name>A. Author</name></author></entry>"
    )


class FakeSources:
    def __init__(self):
        self.queries: list[str] = []
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, body, ctype="application/xml"):
                body = body.encode() if isinstance(body, str) else body
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                u = urllib.parse.urlsplit(self.path)
                q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
                if u.path == "/arxiv":
                    fake.queries.append(q["search_query"])
                    return self._send(
                        '<feed xmlns="http://www.w3.org/2005/Atom">'
                        + atom_entry("2610.00001", "Graph networks  for molecules", RECENT, "message passing")
                        + atom_entry("2610.00002", "Galaxy rotation curves", RECENT)
                        + atom_entry("2609.00003", "An old one", OLD)
                        + "</feed>"
                    )
                if u.path.startswith("/details/"):
                    _, _, server, start, end, cursor = u.path.split("/")
                    page = (
                        [
                            {
                                "doi": "10.1101/1",
                                "title": "Place cells in mice",
                                "authors": "Doe, J.; Roe, R.",
                                "category": "neuroscience",
                                "abstract": "hippocampus",
                                "date": f"{RECENT:%Y-%m-%d}",
                                "version": "1",
                            },
                            {
                                "doi": "10.1101/2",
                                "title": "Soil microbes",
                                "authors": "Poe, P.",
                                "category": "ecology",
                                "abstract": "x",
                                "date": f"{RECENT:%Y-%m-%d}",
                                "version": "1",
                            },
                        ]
                        if cursor == "0"
                        else [
                            {
                                "doi": "10.1101/3",
                                "title": "Cortex and sleep",
                                "authors": "Moe, M.",
                                "category": "Neuroscience",
                                "abstract": "sleep",
                                "date": f"{RECENT:%Y-%m-%d}",
                                "version": "2",
                            },
                            {
                                "doi": "10.1101/1",
                                "title": "Place cells in mice (revised)",
                                "authors": "Doe, J.",
                                "category": "neuroscience",
                                "abstract": "hippocampus",
                                "date": f"{RECENT:%Y-%m-%d}",
                                "version": "2",
                            },
                        ]
                    )
                    return self._send(json.dumps({"messages": [{"total": 4}], "collection": page}), "application/json")
                if u.path == "/eutils/esearch.fcgi":
                    fake.queries.append(q["term"])
                    return self._send(json.dumps({"esearchresult": {"idlist": ["111", "222"]}}), "application/json")
                if u.path == "/eutils/esummary.fcgi":
                    res = {
                        "111": {
                            "title": "Sleep in teens",
                            "authors": [{"name": "Lee K"}],
                            "source": "J Sleep",
                            "pubdate": "2026 Oct",
                        },
                        "222": {"title": "Screens and sleep", "authors": [], "source": "Pediatrics", "pubdate": "2026"},
                    }
                    return self._send(json.dumps({"result": res}), "application/json")
                if u.path == "/rss":
                    return self._send(
                        f"<rss><channel><item><title>New &amp; notable</title><link>https://journal.example.com/a</link>"
                        f"<description>about catalysis</description><pubDate>{email_date(RECENT)}</pubDate></item>"
                        f"<item><title>Old news</title><link>https://journal.example.com/b</link>"
                        f"<pubDate>{email_date(OLD)}</pubDate></item></channel></rss>"
                    )
                if u.path == "/atom":
                    return self._send(
                        '<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Atom post</title>'
                        '<link href="https://blog.example.com/p"/>'
                        f"<updated>{RECENT:%Y-%m-%dT%H:%M:%S}+00:00</updated><summary>catalysis</summary>"
                        "</entry></feed>"
                    )
                if u.path == "/evil":
                    return self._send('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><rss>&a;</rss>')
                self.send_response(404)
                self.end_headers()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


def email_date(d: dt.datetime) -> str:
    import email.utils

    return email.utils.format_datetime(d.astimezone())


@pytest.fixture
def research(env):
    fake = FakeSources()
    env.app.settings.set(
        "research.endpoints",
        {"arxiv": f"{fake.base}/arxiv", "biorxiv": f"{fake.base}/details", "pubmed": f"{fake.base}/eutils"},
    )
    yield env, fake, env.app.modules["research"]
    fake.server.shutdown()


def test_validation():
    assert rmod.validate({"type": "arxiv", "categories": ["cs.LG", "nonsense.XX"], "keywords": [" graph "]}) == {
        "type": "arxiv",
        "categories": ["cs.LG"],
        "keywords": ["graph"],
    }
    with pytest.raises(ValueError):
        rmod.validate({"type": "arxiv", "categories": ["nonsense.XX"]})
    assert rmod.validate({"type": "medrxiv", "subjects": ["Epidemiology", "Astrology"]})["subjects"] == ["Epidemiology"]
    for bad in ({"type": "pubmed", "query": " "}, {"type": "rss", "url": "ftp://x"}, {"type": "telepathy"}):
        with pytest.raises(ValueError):
            rmod.validate(bad)
    cat = rmod.catalog()
    assert sum(len(cs) for _, cs in cat["arxiv"]) == 155 and len(cat["presets"]) >= 15


def test_arxiv_fields_keywords_and_dates(research):
    env, fake, r = research
    got = r.fetch({"type": "arxiv", "categories": ["cs.LG", "q-bio.BM"], "keywords": ["message passing"]})
    assert [p["title"] for p in got] == ["Graph networks for molecules"]  # keyword filter; the old one is dropped
    assert (
        fake.queries[-1].startswith("(cat:cs.LG OR cat:q-bio.BM) AND (") and 'abs:"message passing"' in fake.queries[-1]
    )
    assert got[0]["id"] == "arxiv:2610.00001" and got[0]["link"] == "https://arxiv.org/abs/2610.00001"


def test_biorxiv_subjects_pages_and_revisions(research):
    env, fake, r = research
    got = r.fetch({"type": "biorxiv", "subjects": ["Neuroscience"]})
    assert sorted(p["title"] for p in got) == ["Cortex and sleep", "Place cells in mice (revised)"]
    assert all(p["link"].startswith("https://www.biorxiv.org/content/10.1101/") for p in got)


def test_pubmed_and_feeds(research):
    env, fake, r = research
    got = r.fetch({"type": "pubmed", "query": "sleep AND adolescents"})
    assert [p["title"] for p in got] == ["Sleep in teens", "Screens and sleep"] and fake.queries[
        -1
    ] == "sleep AND adolescents"
    rss = r.fetch({"type": "rss", "url": f"{fake.base}/rss", "keywords": []})
    assert [p["title"] for p in rss] == ["New & notable"]
    atom = r.fetch({"type": "rss", "url": f"{fake.base}/atom", "keywords": ["catalysis"]})
    assert atom[0]["link"] == "https://blog.example.com/p"
    with pytest.raises(ValueError):
        r.fetch({"type": "rss", "url": f"{fake.base}/evil"})


def test_digest_dedupes_reports_failures_and_remembers(research):
    env, fake, r = research
    env.app.settings.set(
        "research.feeds",
        [
            {"type": "arxiv", "categories": ["cs.LG"], "keywords": []},
            {"type": "rss", "url": f"{fake.base}/rss", "keywords": []},
            {"type": "rss", "url": f"{fake.base}/missing", "keywords": []},
        ],
    )
    env.app.settings.set("research.max_papers", 2)
    env.on("research")
    new = r.papers()
    assert len(new) == 3
    text = env.fake.texts()[-1]
    assert text.startswith("New papers (3):") and "…and 1 more." in text and "Couldn't reach: Feed:" in text
    assert r.papers() == []  # already sent


def test_the_ai_picks_with_what_you_work_on(research):
    env, fake, r = research
    env.app.settings.set("brain.main", "gemini")
    env.app.secrets.set("gemini.api_key", "k")
    env.app.settings.set("research.feeds", [{"type": "arxiv", "categories": ["cs.LG"], "keywords": []}])
    env.app.settings.set("research.about", "graph neural networks for drug discovery")
    env.app.settings.set("research.max_papers", 1)
    env.on("chat", "research")
    r.papers()
    job = env.app.jobs.recent(1)[0]
    assert job.title == "New papers" and "graph neural networks for drug discovery" in job.prompt
    row = env.app.jobs._db.execute("select background from jobs where id=?", (job.id,)).fetchone()
    assert row[0] == 1  # waits for the charger on battery


def test_the_research_tab(research):
    from kurooto.web.api import Api

    env, fake, r = research
    api = Api(env.app)
    st = api.get("research")[1]
    assert st["feeds"] == [] and st["papers"] == "weekly mon 08:00" and st["catalog"]["biorxiv"]
    preset = st["catalog"]["presets"][0][1]
    ok = api.post(
        "research/save", {"feeds": preset, "about": "x", "papers": "daily 07:30", "max_papers": 5, "rank": False}
    )[1]
    assert ok["ok"] and ok["papers"] == "daily 07:30" and ok["feeds"][0]["label"].startswith("arXiv: ")
    assert api.post("research/save", {"papers": "whenever"})[1]["ok"] is False
    assert api.post("research/save", {"repos": ["/definitely/not/a/repo"]})[1]["error"].startswith(
        "not a git repository"
    )
    pv = api.post("research/preview", {"feed": {"type": "arxiv", "categories": ["cs.LG"]}})[1]
    assert pv["ok"] and pv["count"] == 2
    assert api.post("research/preview", {"feed": {"type": "pubmed"}})[1]["ok"] is False
    assert r.configure({"about": "soil", "keywords": "microbes, nitrogen"})["ok"]
    assert r.feeds()[-1] == {"type": "arxiv", "categories": [], "keywords": ["microbes", "nitrogen"]}


def test_older_topics_still_work(research):
    env, fake, r = research
    env.app.settings.set("research.topics", ["galaxy"])
    assert r.feeds() == [{"type": "arxiv", "categories": [], "keywords": ["galaxy"]}]
    got = r.fetch(r.feeds()[0])
    assert [p["title"] for p in got] == ["Galaxy rotation curves"]


@pytest.mark.skipif(not shutil.which("git"), reason="needs git")
def test_project_logs(env, tmp_path):
    repo = tmp_path / "my-model"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    for msg in ("add the model", "fit the closure"):
        (repo / "f.txt").write_text(msg)
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", msg],
            check=True,
        )
    env.app.settings.set("research.topics", ["x"])
    env.on("research")
    assert env.say(f"/repos add {tmp_path / 'nope'}") == "That folder isn't a git repository."
    env.say(f"/repos add {repo}")
    r = env.app.modules["research"]
    assert r.project_logs() == 1
    log = (env.app.workspace / "research" / "my-model" / "index.md").read_text()
    assert log.index("## Log") < log.index("add the model") < log.index("fit the closure")
    assert "git:my-model — 2 commits" in log
    assert "[[research/my-model/index|my-model]]" in (env.app.workspace / "research" / "index.md").read_text()
    assert r.project_logs() == 0
