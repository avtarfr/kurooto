# Concept graph: books into the notes

The concept graph weaves what a book introduces into the user's Markdown notes: concept notes, typed links with
reasons, "Seen in" lists with page numbers, and per-batch summaries. Two features cooperate:

- **Books** (`modules/books.py:Books`, id `books`, `heavy = True`): reads PDFs into page text.
- **Concept graph** (`modules/integrate.py:Integrate`, id `integrate`, `requires = ("books",)`, `heavy = True`):
  everything after that.

Helpers: `core/segment.py` (sections and batches), `core/conceptgraph.py` (existing notes, candidates, embeddings; no
AI), `core/rerank.py` (local yes/no reranker), `core/integrate_ai.py` (prompts, parsing, checks), `core/graphwrite.py`
(safe writes), `core/hubs.py` (home and research hubs). `modules/library.py` is unrelated (quick notes and the prompt
library); `core/sources.py` is the source mix for note-writing skills, also unrelated.

```
PDF ──Books.read_book──▶ <data>/book-text/<subject>/<id>/pages/NNNNN.md ──Books.finish──▶ text.md, index note
                                                                               │ integrate.poke()
                                                                               ▼
text.md ──Integrate.plan──▶ segment.sections ─▶ segment.batches (3..20 pages each)
                                                                               │ Integrate.tick / submit_batch
                                                                               ▼
conceptgraph.Index.candidates (BM25 + embeddings) ─▶ cards ─▶ batch prompt ─▶ job (lane bg, text_only, brain=bulk)
                                                                               │ then "integrate.done" (_done)
                                                                               ▼
assign slugs ─▶ integrate_ai.check ─┬─ all clean ───────────────────────────▶ write
                                    └─ flagged items ─▶ second look job (lane chk, brain=check)
                                                         │ then "integrate.checked" (_checked)
                                                         ▼
                                       apply_second_look ─▶ write (graphwrite, guarded) ─▶ git commit ─▶ ledger
                                                                               │
                                       daily: garden (links for orphans and touched notes), summary
```

The user's side: [../user/notes-and-concept-graph.md](../user/notes-and-concept-graph.md) and
[../user/books-and-study.md](../user/books-and-study.md).

## 1. Books: PDF to page text

- A book arrives as a PDF with caption "book for <subject>" (`Books.take_book`, called early in `App.handle`), from the
  dashboard (`Books.configure` / `Books.add`, `POST /api/books/add`), or by dropping it into a books folder
  (`Books.roots()`): `books.folder`, else `<files.folder>/<subject>/books`, else `<data>/books/<subject>`.
- `Books.read_book(b, until)` reads page by page; `route()` picks text layer, Tesseract, a local vision model, Gemini, or
  blank for each page. `Doc` uses Poppler (`pdftotext`, `pdftoppm`, `pdfinfo`) when installed, else the pure-Python
  `core/pdfread.py:Pdf` (`page_text`, `has_images`, `page_image`, `outline()`).
- Pages are written atomically to `<data>/book-text/<subject>/<id>/pages/NNNNN.md` with a header
  `<!-- p. N · how -->`; progress is in `meta.json` (`sig`, `pages`, `done`, `routes`, `skipped`, `engines`, `title`,
  `chapters`, `finished`, `indexed`). If the PDF's `sig` (size:mtime) changes, the pages are thrown away and reading
  starts again.
- `Books.finish()` writes `text.md` (page markers `<a id="p-N"></a>` / `## [p. N]`), the chapter list
  (`segment.sections` with the PDF's bookmarks), the book's index note in the notes (Kurooto's part between
  `<!-- kurooto:book ... -->` and `<!-- /kurooto:book -->`), sends it to the notes brain if on, ensures hubs
  (`core/hubs.py:ensure`), runs `books.after_read`, then calls `Integrate.poke()` and emits `book_read`.
- Schedule: `books:read` at `books.at` ("daily 01:00") until `books.until` ("07:00"). `/books read now`,
  `/books stop`. Settings: `register_defaults("books", ...)` in `modules/books.py` (folder, at, until, ocr, ocr_lang,
  latex, gemini, gemini_model, dpi, brain, brain_source, after_read, max_mb).

## 2. Segments and batches (`core/segment.py`)

- `sections(pages, outline, total) -> [Section(level, number, title, first, last)]`: bookmarks first
  (`from_outline`, used when it yields at least 2), then numbered headings and running headers (`from_text`; numbers
  must increase; cross-references such as a margin "Section 9.1" never count), then "Chapter N" lines (`worded`).
- `batches(secs, total, target=TARGET) -> [Batch(id="first-last", ...)]`: every page in exactly one batch,
  `MIN_BATCH = 3` to `MAX_BATCH = 20` pages; level-2 sections are the units; long sections are cut into even windows
  titled "(i/n)"; small ones join the next.
- `Integrate.plan(b)` splits `text.md` on the page marker (`Integrate.pages_of`) and calls
  `segment.sections(pages, outline, total)` and `segment.batches(..., integrate.batch_pages)` (12). The outline is the
  PDF's bookmarks to level 2, kept by `Books.finish` in `meta["outline"]`, and `total` is the book's page count. A
  book whose ledger entry has `"plan": "text"` (set by `record()` for a book that had batches before 0.5.8) keeps the
  old cut: no outline, up to the last page read, so its batch ids don't change.
- Tests: `tests/unit/test_segment.py`.

## 3. Candidates (`core/conceptgraph.py`, no AI)

- `scan(app) -> {slug: Note}` over `concept_dirs(app)`: title (H1), frontmatter `aliases`, a 280-char `summary`, a
  1500-char `head`, wikilinks, and a content hash. Where concept notes live comes from `core/layout.py` (kind
  `concept`: `{subject}/{slug}.md` in the `kurooto` preset, `zettel/{slug}.md` in `zettelkasten`).
- `Index(notes, embedder, store, reranker)`:
  - `bm25()` in pure Python (title and aliases weighted 3x);
  - `match_name()`: exact normalised name or alias, else `difflib` at 0.9 for keys of 6+ characters;
  - `candidates(text, name, aliases, limit=8, query_vec, rerank=True) -> [Candidate(slug, score, evidence, cosine,
    rerank)]`: a name match scores 3.0, BM25 is normalised to at most 1, cosine at least 0.5 counts, neighbours of the
    top 3 add 0.15;
  - `card(slug)`: the short JSON the AI sees for an existing note.
- Embeddings: `make_embedder(app)` from `integrate.embeddings` (`auto` | `ollama` | `gemini` | `off`). `auto` tries Ollama
  (`nomic-embed-text` at `127.0.0.1:11434`) and falls back to the Gemini key (`gemini-embedding-001`). Vectors are cached
  in `<state>/integrate/vectors.db` (SQLite table `v(h, dim, vec)`) keyed by a hash of embedder tag plus text. A failing
  embedder means keywords only for that run.
- Reranker: `core/rerank.py:make_reranker(app)`, when `integrate.rerank = auto`, the `local_models` module exists and
  Ollama has a helper model (`integrate.rerank_model`, else the profile's `helper-*` model from
  `data/ollama_models.toml`). `Reranker.score_one` asks `/api/generate` for one token with `logprobs` and uses
  P(yes)/(P(yes)+P(no)); three failures in a row mark it `dead`. It is used in the same-as check and the garden;
  `submit_batch` asks for candidates with `rerank=False`.

## 4. The AI batch (`modules/integrate.py`, `core/integrate_ai.py`)

- `Integrate.tick()`: nothing if the feature is off or a bulk request is in flight (`inflight()`); stops at
  `integrate.per_night` batches; else takes `ready_batches()[0]` (subjects in `integrate.first` first, then fewest pages
  with `order = smallest`; skips batches in state done, failed, queued or checking; a batch is ready when each of its
  pages has text in `text.md`, or was skipped by the reader once the book's reading pass is over, `meta["finished"]`).
- `submit_batch(b, bt)`: the prompt is `integrate_ai.batch_prompt(...)` (`BATCH_PROMPT`) with the batch's text
  (`[p. N]` markers, at most 40 000 chars) and up to 30 candidate cards. It is submitted as

  ```python
  app.jobs.submit(prompt, effort=effort_for(...), background=True, text_only=True, quiet=True, lane="bg",
                  brain=bulk, then="integrate.done", then_payload={book, batch, first, last, title})
  ```

  and the ledger state becomes `queued`.
- Effort (`effort_for`): `low`; `medium` after a failure or when recent batches needed many second looks.
- Roles (`Integrate.roles`): `integrate.roles = {"bulk": "", "check": ""}`; empty picks the first available agent program
  for bulk and a different one for check (so agy and Claude Code run side by side in lanes `bg` and `chk`), else the
  same one, else `brain.main`.
- Answer schema: `{"concepts": [{"name", "aliases", "role": "core"|"used", "kind", "definition", "formulas",
  "prereqs", "pages", "quote", "same_as", "update", "links": [{"target", "relation", "reason", "confidence"}]}]}`,
  at most `MAX_CORE = 14` core concepts. `parse_json()` takes the first JSON object (fenced or not); `read_batch()`
  normalises, clamps and truncates.
- `Integrate._done(job, result, payload)`: records cost (`spend`), gives each core concept a slug (`assign`: an
  existing note on a name or alias match, else `layout.path("concept", subject, slug_of(name))` with a `-2` suffix if
  taken), then runs the checks.

## 5. Checks that don't trust the AI (`core/integrate_ai.py:check`)

`check(concepts, index, pages, names) -> (concepts, items)`; an `Item` is a doubt of kind `concept`, `same` or `link`.

- Evidence (`evidence_ok`): the quote must be 3 to 60 words and, squashed to lowercase alphanumerics, appear in the
  named pages (plus or minus one).
- Same-as: an unknown slug is cleared; a merge is accepted outright only on a name/alias match or a strong candidate
  (cosine at least 0.7 or rerank at least 0.6), otherwise it becomes a `same` item.
- Link target: must be an existing slug or a concept name from this batch; links to itself are dropped.
- Relation: must be in `core/graphwrite.py:RELATIONS` (needs, generalises, special-case-of, example-of,
  contrasts-with, equivalent-to, part-of, used-in); anything else is dropped.
- Link flags: a vague reason (`graphwrite.lint_reason`: under 5 words or generic phrases), "both ways" when two
  generalises/special-case-of links in the batch contradict (A generalises B and B generalises A, or A special-case-of
  B; "B special-case-of A" agrees and isn't flagged), confidence under 0.5.
- Flagged items get one second look: `CHECK_PROMPT` plus `items_text()`, submitted with `lane="chk"`,
  `effort="medium"`, `brain=<check role>`, `then="integrate.checked"`. The batch's concepts wait in
  `<state>/integrate/pending/<jobid>.json`; ledger state `checking`.
- `apply_second_look(items, answer) -> (kept, dropped)`: an unconfirmed concept is dropped, an unconfirmed merge
  becomes its own concept (`_checked` gives it a slug of its own with `fresh_slug`, so nothing is written into the
  note it was taken for; links other concepts made to it by name still point at that note), a link survives only with `keep`, a valid relation and a reason that passes lint. No usable
  answer drops every doubtful item; nothing is queued for the user.

## 6. Safe writes (`core/graphwrite.py`, `Integrate.write`)

- Kurooto's text lives in marked blocks: `<!-- kurooto:<key> ... -->` ... `<!-- /kurooto:<key> -->`, replaced as a
  whole by `put_block()`. Keys: `seen` (a concept note's "Seen in"), `concepts` (the book's index note), `books` (the
  course page's "From the books").
- Links are lines `- relation:: [[target]] — reason` (`link_line`), appended under `## Links` by `add_links()` (which
  uses `core/tools.py:add_to_section` and skips targets already linked).
- The guard: `outside(text)` removes Kurooto's blocks, link lines, `## Links` headings and `aliases:` lines;
  `guarded(old, new)` refuses the write if what remains differs (hash of whitespace-collapsed text). A refusal emits
  `integrate_refused` and counts as skipped.
- New notes: `layout.frontmatter("concept", ...)` (the zettelkasten preset adds `id`, `aliases`, `tags`,
  `trust_tier: agent_written`), `graphwrite.new_note` (H1, definition, formulas, `## Links`, source line), the `seen`
  block. Created with `write_note_file(create=True)` (open mode `x`: never overwrites); changes are atomic renames that
  keep line endings.
- Before-copies: `<state>/integrate/undo/<subject>-<id>-<batch>.json` (path to old text, null for a new file), newest 60
  kept, pruned by `core/space.py:pending_items` after `space.undo_days`. There is no restore command; the real undo is
  git.
- Git: `Integrate.commit()` does one commit per batch (`books: <title> pp. a-b (+N notes, +M links, K updated)`) when
  `integrate.commit` is on and the notes folder is a git repository.

## 7. Ledger and state (`<state>/integrate/`, `Integrate.load` / `save` via `core/state.py`)

| File | Content |
|---|---|
| `ledger.json` | `{"books": {"<subject>/<id>": {"batches": {"<first>-<last>": {state, at, job, tries, why, check_job, concepts, flagged, dropped, commit, new, same, links, skipped}}}}, "nights": {"YYYY-MM-DD": {requests, cost, batches, new, links, updated, flagged, dropped, failed, garden}}}` (30 nights kept) |
| `seen.json` | `{slug: [{book, note, title, batch, pages, update, def}]}` |
| `chapters.json` | `{bookkey: {batchid: {first, last, title, concepts}}}` |
| `garden.json` | `{"queue": [slugs], "last": {slug: date}}` |
| `pending/<jobid>.json` | a batch waiting for its second look |
| `undo/*.json` | before-copies |
| `vectors.db` | embedding cache |

Batch states: `pending`, `queued`, `checking`, `done`, `failed`. Failure handling:
- `STALE_S` (3 h): a queued/checking record older than that goes back to pending (`inflight()`).
- A rate-limited or signed-out AI with no answer: back to pending without counting a try, `integrate_waiting` event,
  and a one-off `integrate.soon` in 20 minutes (key `integrate:soon`).
- Any other unusable answer counts a try; at `TRIES = 3` the batch is `failed`.

## 8. Garden and summary

- `Integrate.garden()` (`integrate:garden`, "daily 06:20", only when `integrate.garden` is on at start):
  `prune_dangling()` removes link lines to notes that don't exist (guarded, committed); then up to
  `integrate.garden_per_day` (40) notes, first those queued by batches (`queue_garden`), then orphans; for each, 8
  candidates and `LINK_NOTES_PROMPT` as a job (`lane="chk"`, `effort="low"`, `then="integrate.linked"`).
  `_linked` keeps a link only with an existing target, a valid relation, a reason that passes lint and confidence at
  least 0.5.
- Handwritten notes use the same flow outside this module (`modules/handwritten_links.py`, see
  [modules.md](modules.md)): `integrate.index()` for candidates when the concept graph is on, one job on the check AI
  (`lane="chk"`, `then="handwritten.linked"`), the same checks on the answer (existing target, `lint_reason`,
  confidence ≥ 0.5), plain `- [[path]]: reason` lines in a `kurooto:linked` block.
- `integrate:summary` ("daily 07:10") sends one line with Calm reason `integrate.summary`.
- `integrate:night` (`integrate.at`, "daily 01:30") and `integrate:retry` ("every 3h") call `tick`.

## Settings, commands, tests

- `register_defaults("integrate", ...)`: `at`, `roles`, `batch_pages` (12), `per_night` (300), `garden`,
  `garden_per_day` (40), `embeddings` (auto), `rerank` (auto), `rerank_model`, `first`, `order` (smallest), `commit`,
  `summary`.
- `/graph` (`Integrate._cmd`): state, counts, `metrics()` (broken links, notes with no links in, boilerplate reasons,
  top-3 share, name collisions), today's cost; `/graph now` lifts a stop and runs `tick()`; `/graph stop`
  (`Integrate.hold`; not `stop`, which is turning the feature off) writes `stopped.json` with the next `integrate.at`
  time and cancels `integrate:soon`; `tick()` starts nothing before then, whoever calls it (the night and retry jobs,
  `poke`, `_done`), and a restart keeps it.
- No intents.
- Tests: `tests/unit/test_integrate.py`, `test_books.py`, `test_segment.py`, `test_hubs.py`,
  `test_rerank_hardware.py`.

## Known problems (as of this writing)

Verified against the code; fix with a test.

- **The scheduled entry points crash.** `Integrate.start` registers the bound methods `self.tick`, `self.garden`
  and `self.summary` with `Module.every`, and the scheduler calls every action as `fn(payload)`
  (`core/scheduler.py:Scheduler.tick`). Those methods take no argument, so `integrate.night`, `integrate.retry`,
  `integrate.garden` and `integrate.summary` end as `error` (`job_failed` events). Work still starts through
  `Integrate.poke()` after a book is read, `/graph now`, `integrate.soon` (a `lambda p=None`) and the `_done` to
  `tick` chain. Other modules write their actions as `def x(self, p=None)`.
- After a rejected merge, links other concepts in the batch made to that concept by name still point at the note it
  was taken for (`check()` resolved them to that slug before the second look).
- With `integrate.embeddings = auto` and no Ollama, note titles and openings go to Google's embedding API, and the key
  travels in the URL query (`?key=`). The privacy text says matching runs on this computer.
- `prune_dangling` removes any line in the link syntax whose target is missing, including one the user wrote that way.
