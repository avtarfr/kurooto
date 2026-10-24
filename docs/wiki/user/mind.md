# Brain

Brain is Kurooto's mind (0.8.0). It's one feature, **off until you turn it on**, and turned off Kurooto works exactly
as it did before 0.8.0. Each part Brain grows has a switch of its own, so you can take what you like and leave the
rest.

This page grows with Brain. Right now it covers the spine that everything else is built on: a log Kurooto can't
quietly change, kept by a separate program the AI can't reach.

**Contents:** [Turning it on and off](#turning-it-on-and-off) · [The log and the scorekeeper](#the-log-and-the-scorekeeper)
· [Stopping is fine](#stopping-is-fine) · [/mind](#mind) · [What it keeps](#what-it-keeps) · [Hardened mode (optional)](#hardened-mode-optional) ·
[Questions](#questions)

## Turning it on and off

- **On:** dashboard → **Features** → **Brain** → Turn on. (`/mind` while it's off says where.)
- **Off:** the same switch. Brain stops at once: its program ends and nothing more goes into its log. Kurooto then
  sends one message, "Brain is off", with two buttons:
  - **Delete Brain's data:** deletes everything Brain kept, for good;
  - **Keep it:** keeps the data, and turning Brain on again carries on from where it was.

  Nothing is deleted unless you tap Delete. The button works for a week after the message.

## The log and the scorekeeper

When Brain is on, Kurooto keeps a **log** of what its mind saw and decided:
- **What it saw:** your deadlines being added, done or moved; reminders being set and going off; calls ringing,
  answered or missed; AI requests starting and ending; buttons you tapped; Undo; proposals; the computer going to
  sleep or changing power mode; Kurooto starting and stopping.
- **What it decided:** before Kurooto does something on its own, it writes down the decision first. That covers a
  message it starts (a deadline nudge, a check-in), an AI request it queues by itself (a paper search) and a change it
  proposes at night. Each record says what it decided and the reason its code gave.

Two things make the log trustworthy:
- **It can't be changed quietly.** Each record carries a fingerprint of the one before it, so changing, deleting,
  adding or reordering any past record breaks the chain at that point. Once a day, and every 1,000 records, Kurooto
  also notes where the log has got to (an "anchor"). The morning message shows it, so even a log rewritten from
  start to finish no longer matches what you were shown.
- **Only the scorekeeper writes it.** The scorekeeper is a small separate program that Kurooto starts. Kurooto
  itself, and the AI that does things for you, can hand it facts (like "a reminder went off") but can't write the
  log or any score. Any other request is refused, and the refusal goes in the log. The scores themselves come in
  later parts of Brain; for now they're empty.

If the scorekeeper stops (a crash, the computer killed it), Kurooto starts it again by itself, after a second, then
waiting longer each time, up to a minute. Facts that come while it's away wait in a file and go in when it's back.

## Stopping is fine

Brain never minds being stopped, paused, updated, changed or turned off. Time while Kurooto is stopped, asleep or
paused simply doesn't count: nothing builds up while it's away, and nothing is made up for afterwards. It's never
told that an update or a restart is coming, so knowing can't change what it does. Only a real crash counts against
its own health: Kurooto ending with an error, or one of its parts failing.

Some files keep Brain honest: the scorekeeper, its log, the tap table of what always needs your OK, and a few more.
Kurooto's AI can never change them, even in a proposal for a project that is Kurooto's own code. Only you can, by
editing them yourself.

## /mind

- **`/mind`:** whether Brain's scorekeeper is running, how long the log is, whether it checks out, and the last
  anchor.
- **`/mind verify`:** checks the whole log, record by record, and says the result in one line.

## What it keeps

Everything is in the `mind` folder of Kurooto's state folder, on this computer only:
- `log.db` (the log), `score.db` (the scores), `anchors.jsonl`;
- while the scorekeeper runs: its address and a key that changes each time it starts.

Only you can read these files (owner-only permissions).

The log keeps **ids, kinds and numbers, never words**: never the words of a message, a reminder, a deadline's title,
an error or anything you typed. A decision record keeps the reason Kurooto's code gave, and, when an AI made the
decision, what the AI said about it, in at most 300 characters.

Nothing of Brain leaves this computer, and it isn't in backups or Profile sync: an older copy put back would look like
a log that was cut short. Deleting it: turn Brain off and tap **Delete Brain's data**.

## Hardened mode (optional)

On Linux and macOS you can make the scorekeeper run as a system user of its own, so that not even a program running
as you can change Brain's log. It needs `sudo` once:

```sh
sudo tools/mind_harden.sh --apply
```

Without `--apply` it only prints what it would do. It creates the user `kurooto-mind` and gives it Brain's folder;
you can still read the files through your group. It then runs the scorekeeper under systemd (Linux) or launchd (macOS)
and sets `mind.hardened`. Undo it with `sudo tools/mind_harden.sh --undo`. Without hardened mode, Brain works the
same on Windows, macOS and Linux; the scorekeeper just runs as you.

## Questions

**Does Brain make Kurooto do more on its own?** Not this part. It only records. Later parts (forecasts, drives,
autonomy) will each have their own switch, off until you turn them on.

**Will it slow my computer down?** No. The scorekeeper is a small Python program that sits idle until a fact comes
in. Writing a record takes about a millisecond.

**`/mind` says the log doesn't check out.** Something changed the log outside Kurooto, or the disk damaged it. The
message names the first record that doesn't hold. Nothing Kurooto does depends on it yet. If you didn't change it
yourself, turn Brain off, tap Delete, and turn it on again for a fresh log.
