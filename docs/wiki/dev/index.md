# Kurooto developer wiki

Kurooto is a personal assistant that runs on its owner's computer: one Python daemon with an in-process scheduler, a
queue of AI requests run by "brains" (agy, Claude Code, a Gemini key, Ollama, any OpenAI-compatible service), a
Telegram channel, a local web dashboard and setup wizard, opt-in feature modules, phone calls through a per-user
Cloudflare Worker and an Android app, a concept graph that weaves books into a Markdown notes folder, and signed
self-updates.

This wiki is for people and AI agents who change Kurooto's code. A full read should be enough to find your way, fix a
bug or add a feature without help. For using Kurooto, see the user wiki ([../user/index.md](../user/index.md)) and
`docs/MANUAL.md`; for helping a user set it up, the repository's `AGENTS.md`.

**Definition of done** (the owner's standing rule): every change updates, in the same commit, the user wiki
(`docs/wiki/user/`), this developer wiki, `/help`, `CHANGELOG.md` and the site pages `tools/release.py` publishes. No
change is done until those match the code. Details in [agents.md](agents.md#definition-of-done) and
[conventions.md](conventions.md#definition-of-done).

Every claim points at code as `path:symbol` (paths under `src/kurooto/` unless they start with `tests/`, `tools/`,
`docs/`, `android/` or `installer/`). When the code and this wiki disagree, the code wins: fix the wiki.

## Reading order

1. [architecture.md](architecture.md): the daemon's pieces, startup and shutdown, and a message end to end.
2. [repo-layout.md](repo-layout.md): every folder and important file.
3. [core.md](core.md): settings, secrets, paths, every file Kurooto writes, the scheduler and every scheduled job, AI
   jobs, events, notify and Calm, questions and approvals, availability, power, presence, free limits, the reserve, the
   space keeper, hardware profiles, locks, Windows notes.
4. [brains.md](brains.md): the brain interface, each provider, effort, fallback, the tools AI gets, MCP, allow-lists,
   adding a brain.
   [self-manual.md](self-manual.md): what the AI is told about Kurooto itself (`self.md`, the shipped AI manual, the
   `kurooto_self` tool and MCP resources) and the check that keeps the manual current each release.
   [mind.md](mind.md): Brain (0.8.0), the mind: its invariants and tests, the hash-chained log, the scorekeeper
   process, the client, decision records, the reward whitelist, hardened mode; a section per stage.
5. [modules.md](modules.md): writing a feature (with a worked example), lifecycle, listing and enabling, add-ons, and
   a reference of every module.
6. [web.md](web.md): the HTTP server, auth, every API route, live events, the front end, the Today page actions.
7. [calls-and-phone.md](calls-and-phone.md): the call line, connector, ringing, fallbacks, transcripts and the post-call
   look back, pairing, crypto, the Android app.
8. [concept-graph.md](concept-graph.md): books → segments → candidates → AI batch → checks → safe writes → ledger →
   garden.
9. [testing.md](testing.md): running tests, the real-install guard, scratch `KUROOTO_HOME`, fakes, CI.
10. [release-and-updates.md](release-and-updates.md): versions, the changelog, building, signing, channels, the updater,
    rollback.
11. [conventions.md](conventions.md): house style, privacy rules, the privacy scanner, what never to commit.
12. [debugging.md](debugging.md): doctor, logs, events, the diagnostics bundle, common failures.
13. [agents.md](agents.md): for AI coding agents: what to read, invariants, checks, what never to do, how to report.

Short on time: architecture, then the page for your area, then testing and conventions. AI agents: start with
[agents.md](agents.md).

## Quick start for a developer

```sh
git clone <the repository> && cd kurooto
uv sync --locked
git config core.hooksPath tools/hooks          # privacy scan and identity checks on commit and push
uv run pytest -m "not live"
export KUROOTO_HOME="$(mktemp -d)"             # never run the CLI against a real install
uv run kurooto run                             # the daemon in the foreground; open the URL it logs
```

## Version

Written against the 0.5.8 development tree (`pyproject.toml` still says 0.5.7). Changes landing in 0.5.8 that this wiki
already reflects: calls get a post-call look back (`modules/calls/review.py`, `/lessons`); chat history records only
Chat's own requests (`modules/chat.py:Chat.owns`, checked in `core/jobs.py:Jobs._deliver`). Also in 0.5.8:
Attendance is removed (`core/upgrade.py:drop_retired`), Exam season is an add-on (`Module.extra`), topic study packs
(`core/studypack.py`: class material ranked above books, never a whole book), `/help` lists everything and searches
(`app.py:App.help`), and scheduled actions all take the payload (`tests/unit/test_scheduled_actions.py`). Learns from its own work
(`modules/learning.py`, an add-on): a per-request tool log and `Jobs.watchers` (`core/jobs.py`), an FTS5 search index
of past requests, skills and lessons learned with Undo, facts kept by the nightly look back.

Pages about code end with the known problems found while writing them (verified against the code at the time of
writing); they are worth fixing, each with a test.
