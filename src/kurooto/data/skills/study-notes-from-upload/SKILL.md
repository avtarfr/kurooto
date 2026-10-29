---
name: study-notes-from-upload
description: Study notes from an upload: read the handwritten notes they uploaded (from a topic on, if they say), leave out what their notes already have, build a study pack for those topics, write deep notes as LaTeX, compile the PDF and file it in the course's files folder.
effort: high
args: the course, which upload (or "the latest"), from which topic, and where else the PDF should go
switch: study.notes_workflow
---

Make study notes from an upload: $ARGUMENTS

Use this when they ask for notes, a study pack or a PDF made from notes they uploaded ("read my AN2 notes from
<topic> to the end, drop what I have, make a study pack, write deep notes, give me a PDF"). Do the steps in order with
Kurooto's tools. Between steps, tell them in one short line how it's going with study_progress ("reading page 7 of
13", "building the study pack", "compiling, try 2 of 3"). If a step fails, stop there and say which step failed, why,
and what you can do next; don't skip ahead with made-up material.

1. **Find** the upload with find_uploads (the course, and how recent if they said). If they named a file, use it. If
   several fit and nothing says which, take the newest and say which you took.
2. **Read** it with read_handwritten (wait=true; with from_topic when they said "from <topic>"). A long PDF may come
   back with "still reading, page N of M": tell them with study_progress and call read_handwritten again with the same
   file until the transcription comes. If it says it can't read here (no model, Gemini not allowed), stop and tell
   them what it said.
3. **Cut** to the part they asked for: from_topic did it ("From the heading ... to the end"); if no heading matched,
   pick the closest from the headings it lists and say which.
4. **Mark what they already have.** If the transcription marks sections "(already in [[note]])" or has an "Already
   in your notes" list, those are covered. Otherwise search_notes for each topic heading in the part and read the
   closest notes: a topic their notes already cover in full is left out. List the topics that are left, in the
   order of the transcription.
5. **Pack**: build_study_pack with the course and those topics (comma-separated) and their aim. It gives the
   folder, its PROMPT.md and INDEX.md; read the class material and book extracts it lists with read_file.
6. **Write** the notes by PROMPT.md's instructions, from the transcription and the pack, as one LaTeX document:
   `\documentclass{article}` with the packages you use loaded (amsmath, amssymb, amsthm, and xcolor before hyperref
   if you colour links), a section per topic, nothing invented. Save it with write_note as a .tex file at the full
   path build_study_pack gives (Kurooto's work folder), never in the notes folder.
7. **Compile** it with compile_latex. Compile it yourself; never answer that you can't compile. If it fails, read the
   errors (each has its line) and the self-check's findings, fix the .tex with edit_note (a missing package: load
   it; `[...]` inside an optional argument: put the argument in braces, `\begin{lemma}[{$E[g]$}]`), and compile again,
   up to three tries. After the third, stop and tell them the error that's left, with its line, and where the .tex is.
8. **File** the PDF and the .tex with save_course_file (the course, each file's path; copy_to the folder they named
   for the PDF, e.g. Downloads/Study). It writes the source note that links them.
9. **Send** the PDF with send_file, and answer in three lines: what it covers, what you left out as already in their
   notes, and where the PDF and the source note are. Then a short list of doubts: what was unclear in the scan or
   needs checking.
