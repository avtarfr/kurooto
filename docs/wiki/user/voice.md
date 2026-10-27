# Voice: talk and listen

Kurooto can speak through your computer's speakers, with a voice made on the computer itself, and, if you want, listen
to the room all day through the microphone. Everything it hears is judged on your computer first: noise and people
talking to each other are dropped on the spot, and only what you say *to Kurooto* goes to your AI. Off until you turn
it on, and listening has its own switch on top of that (0.8.8).

- [Turning it on](#turning-it-on)
- [Speaking](#speaking)
- [Listening](#listening)
- [How it tells you're talking to it](#how-it-tells-youre-talking-to-it)
- [The conversation (the "portal")](#the-conversation-the-portal)
- [When it doesn't listen](#when-it-doesnt-listen)
- [Commands](#commands)
- [Privacy](#privacy)
- [Settings](#settings)
- [What it can't do yet](#what-it-cant-do-yet)

## Turning it on

**Features → Voice: talk and listen → Set up.** Setting up downloads what the switches you have need, and says how
much first; nothing is downloaded before that:

| Part | What it's for | About |
|---|---|---|
| sounddevice, numpy | playing and recording sound | 60 MB |
| Kokoro-82M (the default voice) | speaking: a natural voice, made on your computer | 0.55 GB with its program |
| Piper (if you pick it instead) | speaking: lighter, less natural | 0.12 GB |
| faster-whisper and its model | writing out what it hears (base model: 145 MB; tiny 75 MB, small 484 MB) | 0.6 GB |
| Silero VAD | telling speech from other sound | 2 MB |
| openWakeWord (only if you give your own wake word model) | a wake word of your own | 0.2 GB |

They go into Kurooto's own folder (`kurooto paths`, the `app` line, then `voice/`), never into your system.
Listening needs a microphone; your system's sound settings decide which one is the default.

Turn listening on with `voice.listen.on` in Settings, then **Set up** again: it fetches the listening parts.

## Speaking

Kurooto reads its answers aloud, sentence by sentence (the first sentence plays while the next is being made, so it
starts quickly). By default it reads the answers to what you said aloud; `voice.speak.what` = `all` reads every
answer from your AI (Telegram and the phone app ones too), and `off` keeps it silent unless asked.

- Pick a voice with `voice.speak.voice` (Kokoro: `af_heart`, the default, `af_bella`, `af_nicole`, `af_sarah`,
  `am_michael`, `am_adam`, `bf_emma`, `bf_isabella`, `bm_george`, `bm_lewis`), and the speed with `voice.speak.rate`.
- Long answers are read up to `voice.speak.max_chars` (800 characters), then "The rest is on screen."
- Code in an answer isn't read out ("code on screen"), and links are read as "a link".
- `/voice say Good morning` says something now; `/voice stop` stops it mid-sentence.
- An add-on can play Kurooto's voice on another device instead of these speakers (0.8.12); when that device can't,
  the computer's speakers play it, and `/voice stop` and mute stop it there too.

## Listening

With `voice.listen.on`, the microphone stays open all day, and everything below happens on your computer:

1. **Voice activity** (Silero VAD) finds stretches of speech; anything else is never even written out.
2. **Writing out** (faster-whisper) turns each stretch of speech into words.
3. **The gate** decides: noise, chatter (people talking to each other), or talking to Kurooto.

**Its name wakes it.** Say "Kurooto" (or the name you gave it, `you.assistant_name`) first or last: "Kurooto,
what's due?", "hey Kurooto, set a timer", "what's due, Kurooto?". Saying the name alone ("Kurooto?") gets a "Yes?",
and what you say next is for it. Nothing is downloaded for this and no ready-made wake word is used.

Whisper often spells an unusual name wrong, so Kurooto is generous about it:
- Whisper is given the name as a hint, so it writes "Kurooto" more often.
- Known mishearings of "Kurooto" count: Kuroto, Kurouto, Kuruto, Curoto, Kurato, "kuro to", "coo roto", Kirito,
  "guru to", Kuroo, Kuro ("hey Kuro") and more.
- Near misses count too: a word that sounds the same (the same consonants: k/c/g, r/l, t/d) and is spelled within two
  letters of the name ("Kurroto", "Kurotto"). Ordinary words don't: "cool", "auto", "curry", "Kurt", "router",
  "kurta", "Kyoto".
- Add spellings it keeps getting wrong with `voice.listen.name_variants` (`["crouton"]`).

**A wake word model of your own** is an option: train one with openWakeWord (for "hey Kurooto", say) and put the path
of its `.onnx` file in `voice.listen.wake_word`. Set up then fetches openWakeWord. Its ready-made wake words aren't
offered, because their licence (CC BY-NC-SA 4.0) doesn't fit.

## How it tells you're talking to it

In this order, first match wins:

| What it heard | Counts as |
|---|---|
| no speech | noise |
| your own wake word model (if you set one) | talking to it |
| no real words (or what transcribers invent from silence: "thank you", "[music]") | noise |
| its name, first or last, as Whisper may spell it | talking to it |
| the first words after its name said on its own ("Kurooto?") | talking to it |
| two or more voices, and none of the above (when the listener can tell; today's can't, so the model judges this from the words and from how much talk there's been nearby) | chatter |
| a question or request while the conversation is open | talking to it |
| a question or request within 6 seconds of it speaking (a yes or no too, if it asked something) | talking to it |
| anything else | the model on your computer decides |

The model on your computer (Ollama, the one Local AI models set up, or the offline helper's) reads the words and
answers noise, chatter or talking to it, with how sure it is. Below `voice.listen.threshold` (0.7) it counts as not
talking to it. With no local model, only its name, your wake word and the rules above open a conversation.

## The conversation (the "portal")

When the gate decides you're talking to Kurooto, a conversation opens: your words go to your AI like a chat message
(answers worded to be spoken), and the answer comes back on the dashboard and aloud. Keep talking and it follows the
conversation. It closes:

- **at once** when the next thing it hears isn't to it (you turn to someone else);
- after `voice.listen.close_s` seconds (8) with nothing said to it;
- when you mute it, a call starts, Kurooto pauses, or (with `voice.listen.night` off) the night begins.

The dashboard shows each step (listening, hearing, talking to it, thinking, speaking, closed) and a waveform.
Speech that wasn't for Kurooto (people talking to each other, noise) moves the waveform too: only its loudness
reaches the page, never its words. `voice.listen.levels` off stops both. On the being board the YOU lane is live while
it listens: the microphone's loudness scrolls through it as you speak (`look.being_live_waveform`).

## When it doesn't listen

- **Muted:** `/voice mute`, `kurooto voice mute`, or the dashboard's mute. It stays muted (across restarts) until
  `/voice unmute`. Muting also stops it speaking.
- **On a call:** while a phone call is on (`voice.listen.calls` to keep listening).
- **At night:** it keeps listening by default; turn `voice.listen.night` off and it stops during your night hours
  (`availability.night`).
- **Paused:** while Kurooto is paused, and on battery in saver mode.

## Commands

| Command | What it does |
|---|---|
| `/voice` | what it's doing, and how much it heard since it started (counts only) |
| `/voice mute`, `/voice unmute` | stop and start listening and speaking |
| `/voice stop` | stop speaking now |
| `/voice say <text>` | say this now |
| `/voice id` | Voice ID: whether it knows your voice, its grade, thresholds, last test, and counts since start |
| `/voice enrol` | start (or continue) enrolling your voice at the computer; `/voice enrol again` (start over), `/voice enrol stop`, `/voice enrol keep` |
| `/voice id test` | one try at the computer: was that you? |
| `/voice id retrain` | build your voice print again from your samples (after changing the strictness) |
| `/voice id undo today`, `/voice id undo all` | drop what it learned from your turns (improving over time) |
| `/voice id forget` | delete your voice print and its key (with Forget my voice / Keep it buttons) |

The same from a terminal: `kurooto voice`, `kurooto voice mute`, `kurooto voice say Hello`, `kurooto voice id`,
`kurooto voice id forget` (asks y/N; `--yes` skips it), `kurooto voice parts add FILE...`.

The `/voice id` and `/voice enrol` commands are typed only: said aloud (by anyone, you included) they answer "That
can't be done by voice: type it or use the dashboard."

## Privacy

- **What it hears:** everything near the microphone, while listening is on and nothing above stops it.
- **What it keeps:** nothing. Sound stays in memory (a rolling buffer of under a second, and the stretch being written
  out) and is never written to disk. The words of noise and chatter are dropped as soon as the gate decides: never
  stored, logged or sent. It counts how many stretches were noise, chatter or for it, in memory only.
- **What leaves:** only the turns the gate decided were said to Kurooto, as text, to the AI you picked, like a chat
  message (and kept in the chat history like a typed one). While the conversation is closed, nothing leaves.
- **Downloads:** setting it up fetches packages from PyPI and models from GitHub and Hugging Face; nothing of yours is
  sent.

Licences: Kokoro-82M (Apache-2.0), kokoro-onnx (MIT), faster-whisper (MIT), Whisper models (MIT), Silero VAD (MIT),
openWakeWord (Apache-2.0; only fetched for your own wake word model, and its CC BY-NC-SA ready-made models never),
sounddevice (MIT). Kokoro's pronunciation uses espeak-ng (GPL-3.0), and Piper from version 1.3 is GPL-3.0; both are
downloaded to your computer as separate programs, not part of Kurooto.

## Settings

| Setting | Default | What it does |
|---|---|---|
| `voice.speak.on` | on | speak at all |
| `voice.speak.engine` | `kokoro` | `kokoro`, `piper` or `off` |
| `voice.speak.voice` | (Kokoro's `af_heart`) | the voice |
| `voice.speak.rate` | 1.0 | speed |
| `voice.speak.what` | `voice` | `voice` (answers to what you said aloud), `all` (every AI answer) or `off` |
| `voice.listen.on` | off | listen through the microphone |
| `voice.listen.wake_word` | (none) | the path of your own openWakeWord `.onnx`; empty: its name wakes it |
| `voice.listen.name_variants` | (none) | more spellings of its name to accept; the common mishearings are built in |
| `voice.listen.model_judge` | on | let the model on your computer judge what the rules can't |
| `voice.listen.threshold` | 0.7 | how sure the model must be that you're talking to it |
| `voice.listen.close_s` | 8 | seconds of nothing said to it before the conversation closes |
| `voice.listen.night` | on | keep listening during the night hours |
| `voice.listen.calls` | off | keep listening during calls |
| `voice.listen.stt_model` | `base` | `tiny`, `base` or `small` |
| `voice.listen.language` | (worked out) | the language you speak, e.g. `en` or `hi` |
| `voice.addons.listen` | on | let an add-on take one thing said, written out here and never sent (mute still stops it) |
| `voice.addons.chat` | on | let an add-on have Kurooto chat with someone the guest way: no tools, none of your data |

All of them, each with its whole entry: [the settings guide](settings-guide.md#voice-and-voice-notes).

## Voice ID: only your voice can make it act

Off by default (`voice.speaker_id.on`). Once it's on and knows your voice, every turn said to Kurooto is checked
against your voice print, on this computer, and gets one of three answers: **you**, **not sure** or **someone else**.

- **You:** everything works as before: commands, requests, your AI with its tools, settings, calls.
- **Someone else, or not sure:** chat only. They get a real answer from your AI (or only the model on this computer,
  `voice.speaker_id.guest_brain: local`), but with **none of your data** (no notes, calendar, mail, deadlines, memory,
  profile, history or files) and **no actions** (no commands, reminders, alarms, calls, messages or settings). Once
  per conversation the reply says so: "You can chat with me, but only my owner's voice can make me do things." Not
  sure counts as not you ("I couldn't tell it was you, so I'm only chatting: say it again closer to the microphone,
  or type it.").
- **`voice.speaker_id.mode: owner_only_at_all`:** others get "I only answer my owner's voice." and nothing else.
- Typing always works: Telegram, the phone app's chat, the dashboard and the terminal are yours, so they aren't
  checked.

### Turning it on and enrolling

1. Dashboard → Features → Voice: tick **Voice ID** on the card, then **Set up** (it fetches a 28 MB speaker model and a
   small package, once, plus listening's parts if they aren't there yet; after that it works with no internet). The
   switch alone doesn't download anything: the Your voice page says so and has its own **Set up now** button. No internet on that computer? **Manage → Install from a
   file** on the page, or `kurooto voice parts add FILE`: the file is checked against its pinned checksum.
   Voice ID only checks what Kurooto hears, so listening (`voice.listen.on`) must be on too; the Your voice page says
   when it's off and has a **Turn listening on** button.
2. Open **Your voice (Voice ID) →** on the Voice card (the page `/voice-id`), or type `/voice enrol`.
3. **Capture**, about five minutes at the computer, through the microphone Kurooto listens with (never the
   browser's). It asks, aloud and on the page, for about twenty short sentences in six ways:

   | Step | What you do | Samples |
   |---|---|---|
   | Normal | your normal voice, at your usual distance | 5 |
   | Quiet | a quiet voice, same place | 3 |
   | Far | step back about two metres | 3 |
   | Noise | with music, a fan or the TV on low | 3 |
   | Short requests | the way you really ask it: "Kurooto, what's on tomorrow?" | 4 |
   | Free speech | ten seconds about anything | 1 (three samples from it) |

   Each sample is checked before it counts, and a rejected one says why with its number: too short, too loud
   (clipped), too quiet, too much noise, not the sentence, not the condition ("That sounded as close as before: step
   back about two metres."; quiet and far count when your voice is 4 dB lower than your normal one, or 4 dB less above
   the room's noise, so a microphone that evens out loudness still lets them pass), not sounding like your other
   samples, or identical to an earlier one (a recording). Say
   **stop**, **skip**, **repeat**, **pause** or **continue** during it. Any step but the first can be skipped. Speak
   another language? Tick "Say it in my own words".
4. **Train** builds it (automatically at the end): **good**, **fair** or **weak**, with the thresholds, how often it
   would turn you away in each condition, and how many of about 1,750 strangers' voice prints would pass. A weak one
   is saved only when you press **Use it anyway**.
5. **Test**: press, then say a sentence or two, starting within 15 seconds (it waits for you to finish). **Try me**
   (should be You), **Try as someone else** (ask someone; should be Someone else), **Try a
   synthetic voice** (Kokoro's ten voices, if Kokoro is set up). The page shows the score on a dial with the "not
   sure" and "accept" marks.

**Later:** **Manage → Add samples** adds a few in one condition (a new microphone, a cold), then **Retrain**. **Manage →
Start over** (or `/voice enrol again`) records all six steps again from nothing; your voice print keeps working until
the new one is built, **Keep for later** keeps the new samples and continues with the same plan next time, and
**Undo** on the Train step puts the previous voice print back (until Kurooto restarts). **Forget my voice** deletes
it.

### What "training" means here

No neural network is trained or fine-tuned on your computer. A pretrained speaker model (CAM++) turns each sample into
a list of numbers; training makes **your template** (the average of your samples) and **calibrates your thresholds**:
each of your samples is scored against the others, and compared with the scores of about 1,750 strangers' voice prints
that ship with Kurooto, so the threshold sits where strangers almost never pass. Short turns get their own, lower
thresholds. A classifier trained on top of your samples was considered and not used: with 12 to 60 samples it learns
the room you enrolled in more than your voice.

### Improving over time, and undo

Off by default (`voice.speaker_id.adapt`; the Improve step, or the card's switch). Turns it was **very** sure were you
(well above the threshold, at least two seconds, one voice) slowly refine your voice print: at most 10 a day and 40 in
all, never more than a quarter of its weight, never from a turn it wasn't sure of. If your voice print would drift too
far from your enrolment, it stops and says so. **Undo today** and **Undo all** (or `/voice id undo today|all`) put it
back.

### Strictness and the threshold

`voice.speaker_id.strictness`: `relaxed`, `normal` or `strict` (strict turns you away more often; strangers almost
never pass; a short reply right after your turn no longer carries). Press **Retrain** after changing it.
`voice.speaker_id.threshold` (0 = worked out from your samples) sets your own, held to 0.30 to 0.95 whatever is typed
(below that most strangers would pass); the page shows the calibrated one beside it. `voice.speaker_id.margin` is held
to at most 0.2.

**How often it gets it wrong**, measured on recorded speech (LibriSpeech's 146 dev and test speakers: each enrolled
with the real enrolment, from clean audiobook reading with quiet, far and noisy versions made from it, then tried
against the others, the strangers never in the threshold's calibration; `tools/voiceid_eval.py`):

| Strictness | You, long turn | You, 2 s | You, 1.5 s | A stranger passes (long turn) | Same gender | Short reply right after you |
|---|---|---|---|---|---|---|
| relaxed | 99.3 % | 98.5 % | 89 % | about 1 in 70 (1.4 %) | 2.5 % | you 95 %, a stranger 1.9 % |
| normal | 99.3 % | 98.4 % | 89 % | about 1 in 180 (0.3 to 0.9 %) | 1.0 % | you 92 %, a stranger 0.8 % |
| strict | 98.9 % | 97.3 % | 87 % | about 1 in 750 (0.13 %) | 0.26 % | never carries |

Real rooms, colds and other microphones lower your numbers (more "not sure"); the strangers' numbers depend mostly on
how much someone sounds like you: a few look-alike voices carry most of the misses, so a relative may pass more often.
Strict is the one to use when strangers are around often.

### Short replies

A "yes" is too short to tell. Right after a turn it knew was you, in the same conversation and within 15 seconds
(`voice.speaker_id.carry_s`), a short reply counts as you unless it sounds clearly like someone else
(`voice.speaker_id.carry`, off in strict mode). That's a deliberate weakness: someone saying "yes" just after you could
pass.

### Other people talking

With Voice ID on, the voice is checked before the words are written out (`voice.speaker_id.gate`): someone else's
talk that isn't calling Kurooto by name is dropped as chatter without being written out (only its first and last two
seconds are, to hear its name). With the gate off, everything is written out as before, but conversation mode still
checks each voice so it knows someone else is talking. While another voice has been heard in the last minute, Kurooto is in **conversation
mode** (`voice.listen.conversation_mode`): it stays out of people talking to each other, you included, and only its
name with a question or request after it ("Kurooto, …") or a reply right after its own answer opens the conversation.
"Kurooto told me…" only mentions it. The dashboard's ear says "conversation: staying out".

### Your voice print

- **Kept:** only your voice print (numbers, condition names, dates, thresholds, quality numbers and the microphone's
  name), encrypted (AES-256-GCM) in Kurooto's state folder, with its key in your system's keychain (or the owner-only
  secrets file where there's none). Never your recordings: sound stays in memory and is dropped as soon as it's
  checked.
- **Never:** backed up, synced to another computer, in a diagnostics bundle, logged, on the live stream, or shown.
- **Forget:** `/voice id forget`, the page's **Forget my voice**, `kurooto voice id forget`, or `/forget all`: the file
  and its key are deleted. On an SSD the deleted file's blocks may linger until reused, but with its key gone they're
  unreadable.
- **Can never be done by voice:** enrolling, changing Voice ID's settings, forgetting.

### Honest limits

- **A recording of your voice will usually pass.** It checks whose voice it is, not whether it's live. A recorded
  plain-English request ("wake me at 6", "remind me at five") runs at once, as when you say it yourself; what the AI
  would do on its own (sending, calls, alarms, deleting) still asks for your tap (Approve / Deny) as always. Enrolment
  refuses identical samples.
- **A cloned voice** (made from a minute of you on video) can pass too. The synthetic test only covers Kokoro's stock
  voices.
- **A close relative** with a similar voice may pass at normal strictness: use strict, and try "Try as someone else"
  with them.
- **A cold, or just woken up:** scores drop and you may get "not sure"; add samples while you're ill (Manage → Add
  samples).
- **A new microphone** or headset changes scores: it warns "enrolled with A, listening with B"; add a few samples with
  it.
- **Two people at once** in one turn give a mixed score (usually not sure); it can't separate voices inside one turn.
- **Someone at your keyboard** isn't checked: typing is yours.
- A guest's chat turn runs on your AI only when it can be held to plain text (an API key, or Claude Code with no
  tools). agy and Codex load their own MCP servers and instructions on every run, which Kurooto can't switch off for
  one turn, so with one of them as your AI a guest is answered by the model on this computer, or told plainly that
  Kurooto only chats with its owner when there's none. `guest_brain: local` always uses this computer.
- A guest's words go to the AI as a request; once the answer is spoken, the request's words are blanked (the request
  list keeps only a row titled "Guest"), so nothing learns from them later.

Licences: CAM++ (3D-Speaker, Apache-2.0), its ONNX conversion (sherpa-onnx, Apache-2.0), kaldi-native-fbank
(Apache-2.0), onnxruntime (MIT), numpy (BSD-3-Clause); the strangers' voice prints are computed from LibriSpeech
(CC BY 4.0): numbers only, no audio.

## Greeting you at your desk

With [Face presence](face.md) on, Kurooto can greet you through Voice when you sit down after a while, then open the
conversation so you can answer without saying its name ("what's next?", "yes"). It opens it like after a reply, not like
after its name alone, so people talking nearby close it instead of reaching your AI.

## What it can't do yet

- It can't be interrupted while it speaks: it doesn't listen while speaking (so it doesn't hear itself). `/voice stop`
  or mute stops it.
- Without Voice ID it doesn't know who is speaking; with it, it knows you from anyone else, but can't tell two voices
  apart inside one turn, and can't tell a recording of you from you.
- Its name has to be heard and written out first, so waking takes a moment longer than a dedicated wake word model
  would, and a name Whisper mangles in a new way needs `voice.listen.name_variants`.
- Tested with fakes only so far: real microphones, speakers and the models haven't been tried on many computers.
