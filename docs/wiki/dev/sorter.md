# The notes sorter (developers)

User-facing: [../user/notes-and-concept-graph.md](../user/notes-and-concept-graph.md#notes-sorter-a-scratch-folder-sorts-itself).
Added in 0.7.4. Code: `core/sorting.py` (logic, no AI), `modules/sorter.py` (the feature), `core/notesfit.py` (the move
machinery it reuses). Tests: `tests/unit/test_sorter.py`.

## The rules it keeps (each has a test)

- **Never deletes, merges or overwrites** (`sorting.free_name` numbers a taken name; `notesfit.apply_plan(keep=...)` keeps the
  scratch folder even when it's emptied; `test_a_note_with_a_subject...` compares every file's content hash before and after).
- **Only the scratch folder moves** (`sorting.ready`); a place is only a folder that exists, two levels down at most, never
  Kurooto's own (`sorting.folders`, `SKIP_DIRS`, `private_dirs`); the scratch folder can't point outside the notes
  (`scratch_rel`: no `..`, no absolute path, nothing hidden).
- **Your text is never rewritten.** `sorting.plan` uses `notesfit.plan_moves`, which fixes links in Kurooto's own text only
  and counts those in yours (`Plan.theirs`); a note with any inbound link of yours waits (`plan` checks each move alone
  when `theirs` is non-empty).
- **Undo** is `notesfit.undo` on the pass's move log (`<state>/notes-moves/`), so `/sort undo` restores notes and fixed links
  exactly; `sorting.undo` also forgets the moved entries so they aren't learned from.

## Flow of a pass (`Sorter.run`)

1. `sorting.learn` (a note it moved that's gone from its place: found by name and content hash elsewhere = your correction:
   a rule `{keys, folder}` and a pin by hash).
2. For each ready note: `sorting.decide` (learned rules, `subject:`/`course:`/`class:`, a tag, one subject named in the title;
   two subjects named is ambiguous: it waits with both as guesses). Sure enough (`min_conf`) and under the nightly limit:
   a move. Otherwise, with `sorter.ai` on and not asked in the last day: one job (`sorting.prompt`, lane "bg", text only,
   quiet) whose result comes to `Sorter._decided`; else it waits.
3. Sundays and `/sort now`: `sorting.recheck` (a first look a week after the move, then monthly; only rule or learned
   matches at 0.85 or more; pinned and corrected notes skipped).
4. `Sorter._move`: `sorting.plan` then `sorting.apply` (one log); one Calm message `sorter.summary` with Undo (`srt:<log>:undo`).

`sorting.answer` trusts nothing from the AI but an existing folder and a confidence in 0 to 1 (a bad folder, `../..` or a low
confidence leaves the note waiting: `test_a_bad_or_unsure_ai_answer_leaves_the_note_alone`).

## State and settings

`<state>/sorter/state.json`: `moved` (by current path: from, content hash, time, count, keys), `rules`, `pinned`, `waiting`
(with the best guesses and a button id), `passes`, `day` (today's count). `moved` entries expire after 60 days. Settings
`sorter.*` (SETTINGS_GUIDE.md); the module's switch is Features. Tap table: `tap.BY_ITSELF["notes.sort"]` (a change it makes
by itself, with Undo).

## 0.7.4's two small fixes

- The ring message's buttons: a label over 10 characters ("Tomorrow morning") gets its own row (`Calls.ring`), since it was cut
  off in a row of three.
- Checked and closed: job ids reaching the AI weren't a leak; the AI grepped `events.jsonl` itself (0.7.3's instruction not to
  run commands to look inside Kurooto covers it).

## Reading the inbox, and copies among notes (0.8.0)

**`core/inboxreader.py`** (setting `sorter.read_files`, off; `sorter.read_mb`, 25). `read_new(app, limit, force)` walks the
scratch folder for PDF, docx, pptx, ipynb, txt, rtf and csv files that aren't `.md`, `extract`s their text (`pdftotext`,
the Office XML, JSON cells), `tidy`s it and writes a front-mattered note next to the file (`kind: reference`,
`trust_tier: agent_written`, `note_text`). The original is never touched. `skipped` says why a file was passed over (too big,
no text, secret-looking name). State is `<state>/sorter/read.json` (path, size, mtime), so a file is read once. `Sorter.run`
calls it and sends a `sorter.read` notification (registered in `core/calm.py`). After writing, it calls
`modules/integrate.take_reference(note, title, text)`, which files it in the concept graph (see
[concept-graph](concept-graph.md): the `reference` source, `MIN_CHARS` 300; the subject is the one subject the text names,
else `reference`). Test: `tests/unit/test_inbox_reader.py` (it builds a tiny PDF by hand).

**Copies.** `core/dupes.py`: a shingle sketch detector (`Index`, `scan`); exact copies and near copies at 0.85 or more.
`core/notedupes.py` runs it over all notes, old ones included (`ask`, `merge_pair`, `restore`, `undo`, and `incoming` for the
sorter); buttons use the `ndup` prefix (registered in `Integrate.callbacks`); the job `note_dupes` runs daily at 06:40 on a
thread; settings `integrate.duplicates_all` and `integrate.duplicates_per_day`. The sorter asks before filing a copy
(`_dupe`, `_dupe_button`: Keep both / Merge / Leave it, `srt:<id>:...`; setting `sorter.duplicates`), and
`core/sorting.ready()` skips notes already redirected. Nothing merges or deletes without a tap, and every merge can be undone.
Test: `tests/unit/test_note_dupes.py`. Books: `fingerprint` and `duplicate_of` in `core/books.py` hash a file's pages;
`meta["duplicate_of"]` and `copies` link them; `books.duplicates` switches it.
