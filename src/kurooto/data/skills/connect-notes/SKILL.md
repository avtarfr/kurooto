---
name: connect-notes
description: Find real connections between your notes and write them in as links with reasons; with no topic, it starts from notes nothing links to.
effort: medium
args: a note, folder or topic (nothing: notes nothing links to)
---

Connect notes. Scope: $ARGUMENTS

If no scope was given, start from notes that nothing links to: look through a few folders with list_notes and pick
up to 10 notes that no other note links to (search_notes for their names helps).

Links are `[[path/without-md]]` written in the notes themselves, so every connection must end up in a note.

1. **Find candidates.** For each note in scope, read it, then search_notes for its key ideas to find related notes.
2. **Judge each link.** Link only when there's a real relationship you can name in a few words: same concept,
   prerequisite, an example of, contradicts, uses the method of, same project. No links for shared words alone. At
   most 5 new links per note.
3. **Write them in** with add_to_note, under a `## Related` section (it's made if missing):
   `- [[linear-algebra/eigenvalues]]: diagonalisation needs these`. Add the reverse link in the other note when the
   relationship matters both ways.
4. **Overview notes.** When 4 or more notes share a topic and no overview note exists, propose one in your reply
   (title, one paragraph, the grouped links). Create it only when they ask; they can reply "yes, make it".

Reply with a short list: note → links added, each with its reason.
