# ask: questions and approvals (for the coordinator to merge)

## MANUAL: new section, after "Telegram" (it isn't a feature you turn on: it's always there)

### Questions and approvals
Sometimes Kurooto needs something only you know ("which chapter is Friday's quiz on?") or your OK before it does
something ("send this reply to Sam?"). Those come as a **question** (its answers as buttons, plus **Later**) or an
**approval** (**Approve** / **Deny**, or the asker's own choices such as Send / Edit / Discard).

- **Answer anywhere:** tap a button, or reply to the message with your own words (photos and files in the reply are
  kept with the answer); in the phone app; or on a call (open questions come up at the start of every call). The
  first answer wins; answering again somewhere else just tells you what was already answered.
- **Later** keeps it open for your next call. **Nothing new** (or "nothing", "skip") is a real answer: there's
  nothing to add.
- For an approval with Approve / Deny, a reply of "yes", "ok", "no" or "cancel" counts too. Anything unclear is asked
  again; nothing is ever approved for you.
- Questions you don't answer expire after two days (or when their asker stops waiting); then nothing happens.
- `/q` lists the open ones with their buttons; `/status` says how many are waiting.

*Settings:* `ask.expire_hours` (default 48: how long an unanswered question stays open), `ask.keep_days` (default
30: how long answered ones are kept).
*Leaves your computer:* the question goes wherever Kurooto reaches you (Telegram, the phone app); open questions are
part of the brief your call line keeps for calls while the computer is off.

## MANUAL: add to "Other programs can message you"

They can also ask you something and wait for the answer:

- `kurooto ask-me "Which folder should the photos go in?" --choices "camera|screenshots"` prints the question's id
  and returns; add `--wait` (and `--timeout 30`, in minutes) to wait and print your answer. `--expires 6h` changes
  how long it stays open; `--title "Backup"` replaces the "Question" label.
- `kurooto ask-approval "Delete last month's build folders?" --timeout 30` waits for Approve / Deny: it prints
  `yes`, `no` or `timeout` and exits with 0, 1 or 2. Use it in scripts before anything that needs your OK.

If Kurooto isn't running, both exit with 2 and nobody is asked.

## MANUAL: Phone calls section, one line

On a call you can answer open questions and approvals; an approval that comes in during a call is asked right away.

## AGENTS.md: rows for the Commands table

| `kurooto ask-me "question" [--choices "a\|b"] [--wait [--timeout MIN]]` | asks the person something on Telegram/phone/next call; prints the id, or the answer with --wait | yes, when you need their input |
| `kurooto ask-approval "question" [--timeout MIN]` | asks for Approve/Deny and waits: exit 0 yes, 1 no, 2 timeout | yes; use it before anything that needs their OK |

## Troubleshooting rows

| What you see | What to do |
|---|---|
| "That question expired" | It waited longer than `ask.expire_hours` (or its asker stopped waiting); nothing was done. The asker asks again if it still matters. |
| I tapped a button and nothing happened | It may have been answered elsewhere already (on a call, in the app): `/q` shows what's still open. |
| `kurooto ask-approval` says timeout at once | Kurooto isn't running (`kurooto doctor`), or `--timeout` is in minutes, not seconds. |

## CHANGELOG lines (0.2.0)

- Questions and approvals from anything (features, AI requests, your own scripts) to you, answered anywhere: Telegram
  buttons or a reply, the phone app, or a call; the first answer wins. "Later" keeps one for your next call; `/q` lists
  the open ones. `kurooto ask-me` and `kurooto ask-approval` (exit 0 yes, 1 no, 2 timeout) for scripts and agents.
- Calls: open questions come up at the start of a call; answer_question and answer_approval tools; approvals that
  arrive during a call are asked there.
- AI requests can ask you a question (ask_user); your answer starts the follow-up request.

## PRIVACY notes

- Phone calls row: add "open questions" to the list in the offline brief ("a short brief (what's due, today's classes
  and check-ins, open questions, quiz questions)").
- Questions themselves: delivered on the channels you set up (Telegram, the phone app, the desktop); stored on this
  computer in the state folder (`ask/<id>.json`), deleted 30 days after they're answered or expire. The events log
  records when and where you answered (not what).
- AI requests can't answer your questions or approvals (those tools exist only on calls, with you).

## For the coordinator

- No module to register: app.ask is core (src/kurooto/core/ask.py), created in App.__init__.
- New settings section `ask` (expire_hours, keep_days); consider adding "ask" to web/api.py EDITABLE if the dashboard
  should show it.
