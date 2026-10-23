# Concept graph: books into the notes

The concept graph weaves what a book introduces into the user's Markdown notes: concept notes, typed links with
reasons, "Seen in" lists with page numbers, and per-batch summaries. Two features cooperate:

- **Books** (`modules/books.py:Books`, id `books`, `heavy = True`): reads PDFs into page text.
- **Concept graph** (`modules/integrate.py:Integrate`, id `integrate`, `requires = ("books",)`, `heavy = True`):
  everything after that, for books and (0.5.19) the other sources in `integrate.sources`: Classroom files and
  handwritten notes (see [Sources beyond books](#sources-beyond-books-0519)).

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
  The result is kept in `Integrate._plans` per item, with what it was made from (the text file's mtime and size,
  the batch size, and for a book the outline, page count and plan kind); 0.6.1, because the dashboard's card asks
  for every queued item's batches on each request. `ready_batches` reads the ledger once and hands it to
  `plan(b, led)` (it was read again per book: 89 reads of a 137 KB file a request), lists the library once, and takes
  each book's pages with text from `pages_read(b)`, kept in `Integrate._have` per text file while its mtime, size and
  inode stay the same. With these the Features card (`GET /api/state`) went from 0.26 s to 0.06 s warm; the first
  request after a start still plans every item (about 1 s for 200).
- Tests: `tests/unit/test_segment.py`.

## 3. Candidates (`core/conceptgraph.py`, no AI)

- `scan(app) -> {slug: Note}` over `concept_dirs(app)`: title (H1), frontmatter `aliases`, a 280-char `summary`, a
  1500-char `head`, its links (`layout.link_targets`: wikilinks and relative markdown links alike), and a content hash. Where concept notes live comes from `core/layout.py` (kind
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

## Sources beyond books (0.5.19)

`integrate.sources` (default `["books", "classroom"]`; `SOURCES = ("books", "classroom", "handwritten", "repos")`,
`Integrate.sources()` / `reads(src)`) says what goes through the same pipeline. Everything that isn't a book is an
**item**: a dict in `items.json` that stands in for the book dict `b` everywhere (`source_of(b)` is `b["source"]`, or
`"books"` when absent, so book dicts from `Books.library()` work unchanged).

- **Queueing** (`Integrate.queue_item(source, text, subject, title, note, date, course, backfill, order)`): refuses
  when the feature is off, the source isn't read, the subject isn't a folder slug, or the text is shorter than
  `MIN_CHARS[source]` (classroom 1,500, handwritten 800). The key is `"<source>:<sha256[:16]>"` of the
  whitespace-collapsed text (`text_hash`): a key already in `items.json` is never queued again (read once; an edited
  file hashes differently and is a new item). The text is copied to `texts/<hash16>.txt`.
- **Classroom** (`ClassroomNotes._filed` → `_to_graph` → `Integrate.take_classroom(batch)`, after the digest job
  succeeded, so its lecture notes exist): every file in the batch with `chars` and text (`ClassroomNotes.file_text`),
  and a post whose own text is at least 1,500 characters. `source_note(subject, post title, date, names)` finds the
  note it was filed into: `layout.path("lecture", subject, date, slugify(post title))` if it exists, else the newest
  dated note in the lecture folder whose text (Kurooto's blocks stripped) contains the file's slugified title as a
  whole slug, else the course page.
- **Textbooks filed from Classroom** (0.6.1): `queue_item` stores `kind` = `kind_for(source, title, text)`: "book"
  when `core/studypack.py:is_class(title, pages, 1)` says it isn't class material (more than `BOOK_PAGES` = 80 pages,
  or `BOOK_WORDS` in the title; up to `CLASS_PAGES` = 40, or `CLASS_WORDS` in the title, is class), where `pages` is
  the PDF's page count or the number of `PART_CHARS` parts (slides count 0: class unless the title says book); only
  Classroom items can be books. `booklike(b)` reads it (an item from before 0.6.1 gets it worked out once and saved,
  `set_item`). For a textbook, `stub(b)` is `book_note(b)`: `layout.path("subject")/books/<books.slug(title)>.md`
  (chosen once, `items.json` `source_note`): a Books index note of that name (it has `books.START`) is the same book,
  so that one; a note of that name that's neither that nor this item's (no `item=<key>` in it) gets `-<hash6>`.
  `write()` then calls `write_book_note(b, put, linker)` instead of the per-file `material<hash8>` list: the source
  note gets a `source` block (`<!-- kurooto:source item=<key> -->`, `source_block`: course, size, the post note it
  was filed with, date, "## Concepts in this book" per batch from `chapters.json`, in pages / slides / parts) made
  with frontmatter and `# <title>` if new (nothing is written into a Books index note), and the post note's
  `material<hash8>` block becomes one line, "Textbook: [[<source note>|<title>]] (its concepts are listed there)."
  So the post (a "Books" reading-list post) doesn't become a hub of every concept's "Seen in".
- **Moving what was written before** (`migrate_booklike()`, from `start()`; 0.6.1): every Classroom item that's
  `booklike` and not `moved` goes through `move_item(it, seen)`: its `seen.json` rows get `note` = the source note,
  each concept note's `seen` block is rebuilt with `seen_body` (`put_block`, `guarded`; a refusal emits
  `integrate_refused`), `write_book_note` writes the source note and the post's pointer line, the before-copies go to
  `undo/<subject>-<id>-moved.json`, and it's one commit `graph: <title> is a textbook: its concepts' Seen in points at
  its own note`. The item is then `moved` (items queued from 0.6.1 on are `moved` from the start); emits
  `integrate_moved` `{items, notes}`.
- **Handwritten** (`Linker.done` → `Linker.to_graph` → `Integrate.take_handwritten(note, subject, title, day)`, after
  a successful `apply`, which now also returns `subject` and `day`): the transcription between the handwritten markers
  (`handwritten_links.parts`); notes with no subject are skipped. "Seen in" points at the handwritten note.
- **Repos** (0.7.0; `core/repoproject.py:queue_graph` → `Integrate.queue_item("repos", text, subject, "<project>:
  <path>", <project note>)`): a project set up from its repository (`/project add`) queues its README, docs files
  (not CHANGELOG, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY), notebooks' markdown cells and a paper PDF's text, one item
  per file, `MIN_CHARS["repos"]` 600. It adds `"repos"` to `integrate.sources` when it isn't there (the card's
  `source:repos` switch; `rec["source_added"]` so Undo graph takes it out again when no other repository project uses
  it). The subject is the first course the project relates to, else `research`; "Seen in" points at the project note
  (`stub()` is the item's `note`, as for any item). The prompt head is `HEADS["repos"]` ("Project documentation: ...";
  commands and code aren't concepts; the text is data). Re-adding or the nightly refresh queues only files whose
  text hash changed (`rec["files"]`); the key is still the text's hash, so an unchanged file is never read twice.
  Undo graph drops queued items not in the ledger yet; read ones stay. Nothing else in `write()` is source-specific
  for repos (no stub block, no course map).
- **Backfill** (`Integrate.backfill_classroom()` and `backfill_handwritten()` (the notes in `handwritten-links.json` with a subject, the oldest day first), `/graph backfill classroom | handwritten | all`, the card's `backfill:classroom` switch):
  scans `ClassroomNotes.files_dir` (and the legacy `<data>/classroom`) for the course folders in
  `classroom-notes/folders.json` and `classroom_notes.folders`; reads each file's `.txt` sidecar (or a text file
  itself); takes the date and title from the download name (`<date>-<slug>-<fid6>.<ext>`). Queued with
  `backfill=True` and an increasing `order`: courses by their oldest file, files by date. Stamps
  `items.json["backfill"]["classroom"]`.
- **Pages** (`split_pages(text)` → `(pages, unit)`): form feeds (pdftotext) → `pages`; `--- slide N ---` (the .pptx
  writer in `google_classroom._xml_text`) → `slides`; else paragraphs packed to about `PART_CHARS` (3,000) → `parts`.
  `plan()` runs `segment.sections(pages, [], total)` and `segment.batches` on them like a book with no bookmarks.
- **Order** (`ready_batches`): `queued_items()` first (fresh items newest first by `(date, added)`; then backfill
  items by `order`), then the books as before (only when `"books"` is read). One queue, so one bulk request at a time
  and one `Budget.gate()` for all.
- **Prompt**: `integrate_ai.batch_prompt(..., source, unit)`; a book's prompt is `BATCH_PROMPT` unchanged
  (`BOOK_HEAD` + body); the others swap the head for `HEADS[source]` ("Course material: ...", "Handwritten notes:
  ...").
- **Writes**: the same `write()`. Seen rows of an item carry `source` and `unit`; `seen_body` prints `pp.` for pages,
  `slides a–z` for slides, nothing for parts, and the "Added from" lines under `SEEN_HEAD[source]` ("### Added from
  the books" unchanged). A Classroom item (not a textbook) whose note isn't the course page gets a `material<hash8>` block, "## Concepts
  in <file>" (a key per file, since several files share a lecture note). The course page's "From the books" block and
  a book's `concepts` block are books only. Commits are `classroom: <title> (+N notes, ...)`.
- **Ledger**: items go under `ledger.json["items"][key]`, books stay under `["books"]` (no migration: the books'
  shape is unchanged). `section(b)`, `entry(led, b)`, `inflight()` and `counts()` cover both.
- **Status**: `waiting()` / `waiting_line()` count items with a ready batch per source ("Waiting to be read: 2 books,
  5 class files, 1 handwritten."), in `/graph` and the card. The card's toggles: `source:<name>` (sets
  `integrate.sources`) and `backfill:classroom` (`card_action`).
- Readers of `seen.json` rows outside the module (`quiz_links.where`, `revision`) print slides or nothing for parts.

## 4. The AI batch (`modules/integrate.py`, `core/integrate_ai.py`)

- `Integrate.tick()`: nothing if the feature is off, held by `/graph stop` (`stopped_until()`), or a bulk request is in flight
  (`inflight()`); stops when
  `Budget.gate()` says so (tonight's budget is read, its money is spent, or the bulk AI's limit hasn't reset: see
  [Reading budget](#reading-budget-corereadbudgetpy)); else takes `ready_batches()[0]` (subjects in
  `integrate.first` first, then fewest pages with `order = smallest`; skips batches in state done, failed, queued or
  checking; a batch is ready when each of its
  pages has text in `text.md`, or was skipped by the reader once the book's reading pass is over, `meta["finished"]`).
- `submit_batch(b, bt)`: the prompt is `integrate_ai.batch_prompt(...)` (`BATCH_PROMPT`) with the batch's text
  (`[p. N]` markers, at most 40 000 chars) and up to 30 candidate cards. It is submitted as

  ```python
  app.jobs.submit(
      prompt,
      effort=effort_for(...),
      background=True,
      text_only=True,
      quiet=True,
      lane="bg",
      brain=bulk,
      then="integrate.done",
      then_payload={book, batch, first, last, title},
  )
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
  course page's "From the books"), `source` (0.6.1: a Classroom textbook's source note, `item=<key>` in its head),
  `material<hash8>` (a class note's list of a file's concepts, or a textbook's pointer line), `notation` (0.6.0: the Notation table), `merges` (what a merge brought in) and
  `merged-into` (a redirect, put under the title by `put_block_top`). Block keys are matched with `\b` after the key,
  so a key mustn't be a prefix of another before a hyphen (hence `merges`, not `merged`).
- Links are lines `- relation:: [[target]] — reason` (`link_line`; with `notes.links` "markdown",
  `- relation:: [name](../target.md) — reason`, relative to the note), appended under `## Links` by `add_links()`
  (which uses `core/tools.py:add_to_section` and skips targets already linked, in either style). `LINK_LINE` and
  `line_target()` take both styles, so pruning, the guard, link cards (`quiz_links.LINE`, `quiz_links.PLAIN`) and a
  merge (`link_lines`, `drop_link_lines`, `retarget`, `relink`, which rewrites a moved line's link for the note it
  goes into) read and write either.
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
| `ledger.json` | `{"books": {"<subject>/<id>": {"batches": {"<first>-<last>": {state, at, job, tries, why, check_job, concepts, flagged, dropped, commit, new, same, links, skipped}}}}, "nights": {"YYYY-MM-DD": {requests, cost, batches, new, links, updated, flagged, dropped, failed, garden}}}` (30 nights kept); `"items": {"<source>:<hash16>": {...the same...}}` for the rest |
| `seen.json` | `{slug: [{book, note, title, batch, pages, update, def, source?, unit?}]}` (`book` is the item key for an item) |
| `chapters.json` | `{bookkey or itemkey: {batchid: {first, last, title, concepts}}}` |
| `items.json` | `{"items": {"<source>:<hash16>": {source, key, id, subject, title, course, note, date, added, backfill, order, kind, moved, source_note}}, "backfill": {"classroom": "<when>"}}` (`kind` "book" or "class", `moved` and `source_note`: textbooks, 0.6.1) |
| `texts/<hash16>.txt` | the copy of an item's text that's read |
| `garden.json` | `{"queue": [slugs], "last": {slug: date}}` |
| `notation.json` | `{slug: [{book, batch, source, symbol, what, quote}]}` |
| `made.json` | `{slug: outside_hash}` of notes the graph made (0.6.0 on) |
| `dupes.json` | look-alike pairs, their answers and before-copies (see Near-duplicates) |
| `budget.json` | `{"brains": {"<bulk AI>": {learned, why, capacity, capacity_at, capacity_kind, hold_until, last_hit: {at, kind, reset, fit}, done: [batch times, 8 days], night, nights: {"<morning date>": {kind, batches, cost, how, used, spent, hit}}}}}` (30 nights kept) |
| `pending/<jobid>.json` | a batch waiting for its second look |
| `undo/*.json` | before-copies |
| `vectors.db` | embedding cache |

Batch states: `pending`, `queued`, `checking`, `done`, `failed`. Failure handling:
- `STALE_S` (3 h): a queued/checking record older than that goes back to pending (`inflight()`).
- A lost request (0.6.1, `lost(rec)`): a queued record's `job` (a checking one's `check_job`) that
  `core/jobs.py:Jobs.settled(jid)` calls settled goes back to pending at once, with `why` "asked again: its request
  was lost" (a checking one's `pending/<job>.json` is removed). Settled: no such row, or the job ended and its
  follow-up isn't running in this process (`Jobs._following`, set around the then-action in `_after`) nor about to
  (it ended here, `runner` this process or none, less than `FOLLOW_GRACE_S` = 120 s ago). A job a restart cut off
  mid-run is still `running` until the worker's `recover()` queues it again, so it isn't lost: it runs again and its
  answer is written. What this catches: an update or crash after the job ended but before `_done`/`_checked` had
  written (the job is `ok` or `failed` in the queue, the ledger still `queued`), and a cleared job queue.
  `inflight()` runs under `Integrate.lock`.
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
- `integrate:night` (`integrate.at`, "daily 01:30") and `integrate:retry` ("every 3h") call `tick`. `integrate:plan`
  (hourly, `plan_night`) books a one-off `integrate:early` (action `integrate.soon`) when the next night should start
  before `integrate.at` (`Budget.next_start`), and cancels it otherwise.
- `resume()` (0.6.1, from `start()`, so on every daemon start): `inflight()` (lost requests back to pending), then,
  when nothing bulk is in flight, `stopped_until()` is None, `Budget.in_window()` and `Budget.gate()` is None, a
  one-off `integrate:soon` (action `integrate.soon` → `tick`, the nightly start's own path) a minute later, so a
  restart after the night's start doesn't leave the night idle until tomorrow's `integrate.at`. Whether work waits is
  `tick`'s to find (`idle`), so a start doesn't plan every item. `Budget.window(t)` = (the night's start from
  `plan(day)`, the wake time from `sleep(day)` when known, else `integrate.at` + `NIGHT_S` = 6 h).

## Near-duplicates and merging (0.6.0, `core/graphmerge.py`)

- **Finding** (`conceptgraph.near_duplicates(index, skip, focus, cutoff=DUP_COSINE)`, no AI): over notes that are
  `concept_like` (not a dated note, `course`, `class-log`, `exam-prep`, `doubts`, `index`, `readme`, nor under a
  `books/` folder: in the plain layout they share the subject folder), pairs with the same `normalise(title)` (`name`,
  score 1.0), a shared title-or-alias of 3+ normalised characters (`alias`, 0.95, `shared` = the name), or cosine of
  `index.vec` at least 0.92 (`meaning`, the cosine; only `focus` notes against all, as it's n×m in pure Python).
  Left out: keys in `skip` and pairs where either note's typed link to the other is in `DISTINCT` (anything but
  `equivalent-to`; `Note.typed` = target → relation, parsed in `read_note`). `Pair.a` is `keeper()`: more inbound
  links, then a longer `head`, then the shorter slug.
- **Redirects**: a note with a `merged-into` block (`MERGED`, the first `[[...]]` inside it) has `Note.redirect`;
  `Index` keeps it out of `notes` (so out of candidates, BM25, vectors, orphans, `prune_dangling`'s note loop and
  near-duplicates) in `index.redirects`, and maps its names to the end of its redirect chain in `by_name` (8 hops at
  most) after the real notes' own, so `match_name` and `assign()` land new reading on the kept note.
- **Night** (`integrate:duplicates`, "daily 06:25", only acts with `integrate.duplicates` on): `graphmerge.night` →
  `find()` (skip: pairs answered `merge`/`keep`/`alias`, and pairs asked in the last `REASK_DAYS` = 14; `focus`: the
  `fresh` slugs `Integrate.write` added (`graphmerge.fresh`), then a `SWEEP` = 40 slice of `index.vec` from a rotating
  `cursor`) → at most `MOST` = 3 pairs (2 when `app.app_main()`: the phone chat shows six buttons) → `message()` (one text, a row of three buttons per pair:
  `dup:<pid>:merge|keep|alias`, `pid` = sha1 of the pair key, 8 hex) with Calm reason `integrate.duplicates`; `sent`
  keeps it to one a day. `/graph same` (`ask_now`, `again=True`) replies with the same, unanswered pairs included.
- **Buttons** (`Integrate.callbacks()["dup"]` → `graphmerge.button`, under `Integrate.lock`): each answer is also a
  message (`why="asked"`) with `dup:<pid>:undo`.
  - `merge(ig, pid, rec, index)`: into `a`: `add_links` of `b`'s typed lines (`graphwrite.link_lines`, not to a or b),
    the `seen` block from both notes' `seen.json` rows, `add_alias(b's title and aliases)` (only where `a` has an
    `aliases: [...]` line), the `notation` block from both notes' rows, and a `merges` block ("## Merged here", one
    "### From [[b|title]] (date)" per merge, from `dupes.json["merges"][a]`). `b`: when `made_by_graph(text,
    made.json[b])` (its outside text hashes as it did when `write()` created it), `redirect_note()` (frontmatter, title,
    `merged-into` block) and its `own_body()` went into `a`'s `merges`; otherwise `drop_link_lines`, drop the `seen`
    and `notation` blocks, and `put_block_top("merged-into", ...)` under its title. `guarded()` must pass for `a` and
    (the second case) `b`; else "Not merged: ..." and nothing is written. Other notes' typed lines to `b` go through
    `retarget(text, b, a)` (dropped if they'd repeat a link to `a`). `seen.json` / `notation.json` rows move to `a`;
    one commit `graph: merged <b> into <a>`.
  - `alias()`: `add_alias` on `a`, an `equivalent-to` line each way ("<A> and <B> name the same concept").
  - `keep`: the state only.
  - `undo()`: each journaled file whose text is still what the answer wrote goes back to its before-copy (else it's
    named as left alone); a merge's `seen`/`notation` rows (`before`) and its `merges` entry are restored or removed;
    the pair is `undone` (askable again after `REASK_DAYS`).
- State `dupes.json`: `{"pairs": {pid: {a, b, why, shared, score, asked, state, at, journal: {path: [old, new]},
  before}}, "merges": {a: [{pid, from, title, day, text}]}, "sent", "fresh", "cursor"}`; `made.json`: `{slug:
  outside_hash at creation}` for notes `write()` made from 0.6.0 on (older notes count as yours: they keep their
  text when merged).
- Events `integrate_duplicates` (pairs asked), `integrate_duplicate` (act). Tests: `tests/unit/test_graph_dupes.py`.

## Notation crosswalk (0.6.0)

- The batch answer's concepts carry `notation: [{symbol, what, quote}]` (`BATCH_PROMPT`, `PROMPT_VERSION` 2;
  `read_batch` keeps at most `MAX_NOTATION` = 4, `Proposed.notation`, defaulted so old pending files revive).
- `check()` runs `check_notation(c, pages)` first: a row stays only when its quote (2 to 60 words), squashed, is in the
  concept's pages ±1 and `symbol_in(symbol, quote)` holds: LaTeX commands removed, then two or more 3+-letter words
  (a convention in words) need half of them in the quote, else the squashed symbol is a substring of the squashed
  quote (a PDF's `π`, `ξ`, `−` squash away like the commands). Failing rows are dropped; there's no second look.
- `Integrate.write` → `add_notation(notation, c, entry, title, first, last)`: this batch's rows (`book`, `batch`,
  `source` = "<title>, pp. a–b" / "slides a–z" via `where()`, plus the row) replace the same batch's earlier ones,
  de-duplicated by (book, squashed symbol), sorted by `what` then source, kept in `notation.json[slug]`.
  `notation_body` → `graphwrite.notation_table(rows)`: "" unless 2+ sources have rows and their symbol sets differ;
  else "## Notation" and a `| Source | Notation | What it stands for |` table (16 rows at most; `cell()` escapes `|`,
  `math_cell()` wraps LaTeX-looking or 3-character symbols in `$...$`). Written as the `notation` block on new and
  existing notes when `Integrate.notation_on()`: `integrate.notation` is on (the card's `notation` switch,
  `Integrate.card_action`; whenever the graph reads, not tied to the Research add-on). A merge writes the kept
  note's table under the same rule.

## Reading budget (`core/readbudget.py`)

`Budget(app, bulk)` (`Integrate.budget`, `bulk` = the bulk role's brain id) decides how much a night reads when
`integrate.per_night` is `"auto"` (the default); a number there is a hard ceiling on top of everything below.

- **Kinds** (`kind(brain)`): `plan` (`claude`, `agy`, any other agent program), `free` (`gemini`), `money` (any other
  API brain), `local` (`ollama`, or an API brain whose base URL is loopback: `OpenAICompat.local()`), `none`.
- **A night** (`night(t)`) is keyed by the morning it ends on and runs from one night's start to the next, so daytime
  retries count toward the night before. `plan(day) -> (start, latest)`: `latest` is `integrate.at` (only
  `daily HH:MM` is read; anything else counts as 01:30); `start = min(latest, max(bedtime, wake - 5 h))`, with
  (bedtime, wake) from the alarm's `availability.sleep` windows, else `availability.night`, else unknown (start =
  latest).
- **plan / free with no known limit**: `learned` starts at `FIRST = 30`, or the most batches of any ledger night if
  more (`_seed`; an install that read 60 a night keeps 60). At each new night (`_roll`), a night that read its whole
  budget with no limit hit raises it by `GROW = 1.5` (rounded up), capped at `MOST = 300`, the ceiling and the share
  cap. `capacity` (what fit in one window) is forgotten after `FORGET_S` (14 days).
- **A limit** (`seen(job, result)` from `_done`, `_checked` and `_linked`): the hits are read from
  `result.usage["limits"]` (added by `Jobs._run` for every rate-limited attempt, so a hit is seen even when a stand-in
  answered), else from a rate-limited result itself. `hit()`: the reset is `retry_after_s` (Claude Code's
  `usage limit reached|<epoch>`), else `quota.hints(detail)`. For Claude (and unknown plans) a reset more than
  `WEEKLY_S` (6 h) away, or "week" in the text, is the weekly cap, else the 5-hour window (unknown reset: 5 h, or a day
  for weekly); for agy and Gemini it's the day's limit (unknown reset: `quota.day_end`, midnight Pacific). `fit` =
  batches done since the window began (`reset - 5 h`), the Google day began, or in the last 7 days. Window and day
  hits halve `learned` (at least `FLOOR = 5`) and set `capacity = fit`; a weekly hit sets
  `learned = max(5, min(learned // 2, share × fit / 7))`. `hold_until = reset`; a second hit while holding only moves
  the reset. Emits `integrate_limit`.
- **Tonight** (`tonight()`, recomputed on every call): plan: `min(learned, share_pct% of capacity, ceiling)`; free:
  `share_pct%` of `quota.status(quota.pool(brain, "low"))["limit"]` when known, else as plan; money: `cost =
  integrate.max_cost_per_night`, batches only by the ceiling; local and none: the ceiling or nothing. `how` is the
  sentence `/graph` shows ("learned: 15 batches, 60% of the 25 that fit last night"). A free key under `TINY = 10`
  batches gets `advice`.
- **Money** (`seen` on an OK answer from the bulk brain when it's `money`): `cost_of(usage, integrate.price_per_mtok)`:
  the reported `cost` / `total_cost` / `total_cost_usd`, else `prompt_tokens` and `completion_tokens` at
  `{"in": 2.0, "out": 8.0}` USD per million.
- **Counting**: `Integrate.write` calls `count()` per batch written (the batch time goes into `done`).
- **Showing**: `lines()` for `/graph`, `/graph now` when nothing may start, the feature's dashboard card
  (`Integrate.card`), and `/usage` / `kurooto usage` (`usage_text(app)`, which doesn't save).
- Tests: `tests/unit/test_readbudget.py` (a fake clock; Claude Code's real parser on a fake limit answer; a fake
  Claude brain through the queue for the whole path).

## Settings, commands, tests

- `register_defaults("integrate", ...)`: `at`, `roles`, `batch_pages` (12), `per_night` (`"auto"` or a ceiling),
  `share_pct` (60), `max_cost_per_night` (0.5), `price_per_mtok` (`{"in": 2.0, "out": 8.0}`), `garden`,
  `garden_per_day` (40), `embeddings` (auto), `rerank` (auto), `rerank_model`, `sources` (`["books", "classroom"]`),
  `first`, `order` (smallest), `commit`, `summary`, `duplicates` (on), `notation` (on).
- `/graph` (`Integrate._cmd`): state, counts, tonight's budget and the last limit (`Budget.lines`), `metrics()` (broken
  links, notes with no links in, boilerplate reasons, top-3 share, name collisions), today's cost; `/graph now` lifts a stop and runs
  `tick()` (and says the budget's lines when it may not start); `/graph stop` (`Integrate.hold`; not `stop`, which is
  turning the feature off) writes `stopped.json` with the next `integrate.at` time and cancels `integrate:soon`;
  `tick()` starts nothing before then, whoever calls it (the night, retry, plan and early jobs, `poke`, `_done`), and a
  restart keeps it. `/graph backfill classroom` runs `backfill_classroom()` and says what it queued
  (`backfill_said`). `/graph same` (also `duplicates`, `dupes`) runs `graphmerge.ask_now` and replies with its
  buttons.
- No intents.
- The links are read back as review cards by the Quiz (`modules/quiz_links.py`, see [modules.md](modules.md)), with
  `seen.json`'s pages for "Where to read"; nothing there writes to the notes.
- Tests: `tests/unit/test_integrate.py`, `test_integrate_sources.py` (Classroom, handwritten, backfill, the split),
  `test_graph_restart.py` (lost requests, `resume`, the reading window), `test_graph_textbooks.py` (`kind_for`,
  textbook source notes, the move with its before-copies),
  `test_graph_dupes.py` (near-duplicates, merge and its Undo, notation),
  `test_readbudget.py`, `test_books.py`, `test_segment.py`, `test_hubs.py`,
  `test_rerank_hardware.py`.

## Known problems (as of this writing)

Verified against the code; fix with a test.
- After a rejected merge, links other concepts in the batch made to that concept by name still point at the note it
  was taken for (`check()` resolved them to that slug before the second look).
- With `integrate.embeddings = auto` and no Ollama, note titles and openings go to Google's embedding API, and the key
  travels in the URL query (`?key=`). The privacy text says matching runs on this computer.
- `prune_dangling` removes any line in the link syntax whose target is missing, including one the user wrote that way.
