# Books and PDFs (branch w/books): notes for the coordinator

> **Historical.** Coordinator notes from the 0.4.0 Books branch, kept for the record and not updated since. Books
> has long been merged and registered; what's described here may no longer match the code. For how Books works
> now, see the user wiki's [books-and-study.md](../wiki/user/books-and-study.md) and the developer wiki's
> [modules.md](../wiki/dev/modules.md).

The brief asked for the docs to be written in place, so MANUAL.md ("Books and PDFs" section, a TOC entry, two
Troubleshooting rows), PRIVACY.md (two rows after Handwritten notes) and CHANGELOG.md ("## 0.4.0 (unreleased)" at the
top) are edited directly, each in one contiguous block.

## To register
- `src/kurooto/modules/catalog.py`: `from kurooto.modules.books import Books`, and `Books` in CATALOG (after
  `Handwritten`).
- `src/kurooto/web/api.py` MODULE_ORDER: `"books"` after `"handwritten"` (left out on this branch so
  test_dashboard's catalog check passes until Books is in the catalog).

## Depends on
- ws1's layout API (`core/layout.py`): w/ws1 (7a060c9) is merged into this branch.

## Shared files touched
- `app.py` handle(): one block before the take_files loop: a PDF whose caption says "book for <subject>" goes to
  `books.take_book` (only when Books is on); anything else falls through to Files as before.
- `web/api.py`: GET `books` (the books, their reading state, the folder) and POST `books/add` ({path, subject}, a
  copy), each one block before the final 404; for a richer dashboard view later (dense/look).
- `core/prereqs.py`: a `brew` install kind (Homebrew, else the fallback page); `data/prereqs.toml`: `tesseract`
  (winget UB-Mannheim.TesseractOCR with --scope user, Homebrew, Linux: the install page) and `poppler` (Homebrew on a
  Mac; the project's page elsewhere).
- `data/skills/`: study-log, classroom-digest, revision-pack, add-to-notes gained a sources step and page citations;
  new `exam-prep` skill.
