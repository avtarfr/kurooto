# phone: notes for the coordinator (merge into MANUAL, CHANGELOG, PRIVACY)

## MANUAL: Phone calls, add after "**On the call:** …"

**Questions on your phone:** with Phone calls on, your paired phones also get Kurooto's questions and approvals (from
any feature: a check-in, after-class notes, a quiz, a suggestion to approve), as well as Telegram. Answer wherever is
handy; the first answer counts and the others go away.
- *Android:* a notification with **Reply** (type the answer in the notification; on Android 6 it opens a small answer
  window), the question's choices, **Approve / Deny** for approvals, **Later** (ask me on the next call), or the
  message's own buttons. Tap the notification for every option. The app's main screen lists what's **waiting for
  you**.
- *iPhone:* a notification; tap it to open **Waiting for you** in the Kurooto Home Screen app, with the same buttons
  and a box to type in.
- If the computer is off, your answer waits on your call line and is used as soon as the computer is back.

**More on the phone:** Settings → `notify.app_kinds` says what goes to the phone app. The default is
`["call", "question", "approval"]`; add `"reminder"`, `"deadline"`, `"result"` or `"info"` to get those there too
(they still go to Telegram as well). Remove `"question"` and `"approval"` to keep them on Telegram only.

**While you're on a call** nothing else rings: reminder calls and check-ins wait until the call ends (also when the
computer is off), and updates wait too. Wake-up calls still ring.

## MANUAL: Your phone → iPhone, step 4

4. Tap **Turn on notifications** and allow them (calls, questions and approvals arrive this way).

## Troubleshooting rows

| What you see | What to do |
|---|---|
| Questions don't show on the phone | Is `question` in `notify.app_kinds`? Android: is the app's "Questions and approvals" notification category on? iPhone: notifications on for Kurooto? Is the computer connected to your call line (Features → Phone calls)? |
| "Not sent: tap to try again" on Android | The phone was offline or the call line didn't answer. Tap it to try again, or answer on Telegram. |
| "That answer is too old (or this phone's clock is off)" | Set the phone's clock to automatic, then answer again. |
| "That's no longer open" | It was answered somewhere else (Telegram, a call, another phone) or expired. Nothing to do. |

## CHANGELOG (0.2.0)

- Your phone is a second channel: questions and approvals reach the Android app (Reply box, choices, Approve / Deny,
  Later) and the iPhone Home Screen app (a "Waiting for you" list), not only calls. Answers go back end-to-end
  encrypted (Android) through your call line, also while the computer is off. `notify.app_kinds` picks what else goes
  there.
- Nothing rings while you're on a call (calls placed by the call line with the computer off wait too); updates wait
  for the call to end.
- Fix: the phone app only ever got rings; the phone channel was never wired up.

## PRIVACY

Table rows (replace "Phone calls: ringing"):

| Phone calls: ringing and messages | "a call is ringing" messages, and the questions, approvals and messages you choose for the phone (`notify.app_kinds`), end-to-end encrypted (only your paired phones can read them) | ntfy.sh (Android) or Apple/Google push services (web app; the push itself is empty) |
| Phone calls: what's waiting | the text of open questions, approvals and messages sent to your phones (at most 40, each gone after a day or once answered), so the iPhone app can list them | your own Cloudflare account (your call line) |

"Your phone" section, add: Answers from the Android app are sealed with the same key as the ring messages, so the call
line passes them to your computer without being able to read them; the iPhone app's answers travel over HTTPS with its
device key. Each answer can be used once (a random number and the time it was sent).

## For the coordinator (code)

- No new module: it's part of Phone calls (`src/kurooto/modules/calls/phone.py`, class `PhoneApp`, created as
  `Calls.phone`). Nothing to register in catalog.py.
- Settings: `notify.app_kinds` default is now `["call", "question", "approval"]`.
- New API: `app.notifier.register(name, send, retract=None)` and `app.notifier.retract(map_kind=None, map_ref=None,
  button=None)` (core/notify.py). app.ask already calls `retract("ask", qid)`.
- New: `app.availability.on_call_until(t=None)`, `set_on_call(until)`, and `ON_CALL = "you're on a call"`, which
  `call_block()` now checks first (core/availability.py).
- app.py: two one-line hooks, `self.notifier.retract(...)` in `handle()` (a reply to a mapped message) and in
  `callback()` (any tapped button), so the phone's copy goes when you answer on Telegram.
- Worker: new device endpoint `POST /answer`; `/pending` also returns `items`; admin ops `notify`, `notify-clear`; the
  state push carries `inbox` ({rev, items}); the cron holds non-alarm calls while a call is live. New public files
  `inbox.html`, `inbox.js`. Changing the Worker redeploys call lines on update (as designed).
