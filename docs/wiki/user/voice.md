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
- [How fast it answers](#how-fast-it-answers)
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

Kurooto reads its answers aloud, a few sentences at a time (the first piece plays while the next is being made, so
it starts quickly). Short sentences are spoken together, up to about 200 characters, because a few words read on their
own sound hurried and flat (0.8.13; `voice.speak.join_sentences` off reads one sentence at a time). Between pieces it
leaves the short pause Kokoro itself makes between sentences. By default it reads the answers to what you said aloud; `voice.speak.what` = `all` reads every
answer from your AI (Telegram and the phone app ones too), and `off` keeps it silent unless asked.

- Pick a voice with `voice.speak.voice` (Kokoro: `af_heart`, the default, `af_bella`, `af_nicole`, `af_sarah`,
  `am_michael`, `am_adam`, `bf_emma`, `bf_isabella`, `bm_george`, `bm_lewis`), and the speed with `voice.speak.rate`.
- Long answers are read up to `voice.speak.max_chars` (800 characters), then "The rest is on screen."
- Code in an answer isn't read out ("code on screen"), and links are read as "a link".
- Numbers are said as a person would (0.8.13): 21:31 as "nine thirty-one PM", 27/10/2026 as "the twenty-seventh of
  October twenty twenty-six", ₹3,000 as "three thousand rupees", 3-5 as "three to five", 12 GB as "twelve gigabytes",
  0.8.13 as "zero point eight point thirteen", 2026 as "twenty twenty-six". Only what's said changes; the screen shows
  what was written. Write a count in the year range with a comma (2,026 people) and it's read as a count.
  `voice.speak.numbers_as_words` turns it off.
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
| "stop", "not you", "never mind" ... right after it opened a conversation or spoke (see Telling it off) | it stops |
| its name, first or last, as Whisper may spell it (careful when someone else may be talking: below) | talking to it |
| the first words after its name said on its own ("Kurooto?") | talking to it |
| two or more voices, and none of the above (when the listener can tell; today's can't, so the model judges this from the words and from how much talk there's been nearby) | chatter |
| anything the voice it just answered says within 20 seconds of the answer ending, statements too | talking to it |
| a question or request while the conversation is open | talking to it |
| a question or request within 6 seconds of it speaking (a yes or no too, if it asked something) | talking to it |
| anything else | the model on your computer decides |

Then, with Face presence on: anything above that counts as talking to it, except your wake word, needs a face close
to the camera and facing it (below, "It only answers someone in front of it"); else it's chatter.

The model on your computer (Ollama, the one Local AI models set up, or the offline helper's) reads the words and
answers noise, chatter or talking to it, with how sure it is. Below `voice.listen.threshold` (0.7) it counts as not
talking to it. With no local model, only its name, your wake word and the rules above open a conversation.

### It only answers someone in front of it

With [Face presence](face.md) on and enrolled, Kurooto answers only someone **close to the camera and facing it**. Any
turn that would count as talking to it (its name, a follow-up, the model's judgement, cutting in) also needs the camera
to have seen, while it was said or within about a second and a half after, a face:

- **close:** at least half as tall as your face usually is at your desk (`voice.listen.face_near`, 0.5; about twice
  your desk distance), and
- **facing it:** turned at most about 35 degrees away from the camera (`voice.listen.face_yaw_deg`).

Otherwise it's chatter ("no one facing it nearby") and nothing is sent: your roommate on a phone call across the room,
the TV, someone talking to you from the door. **Your wake word and "stop" / "never mind" work without a face**, so
stopping it always works; typed `/voice` commands are never affected.

While it listens, Voice keeps Face presence's camera looking, even while you type (the Face card says "camera on:
voice: who's talking"). Face presence's own pauses still come first: a call, a locked screen, `/face pause`, focus, the
night, another program using the camera, a covered camera. **When the camera can't see**,
`voice.listen.need_face_fallback` decides: `voice` (default) answers by the voice rules alone, as before; `none`
answers nothing by voice until the camera is back. `/voice` says which applies now, e.g. "needs a face: camera paused
(screen locked), using voice rules".

Only the time of each look and how many faces were close and facing are kept, in memory; no picture, no face numbers.
`voice.listen.need_face` (on) turns it off. With Face presence off or not enrolled it does nothing. Two things to know:
the camera's light stays on while Voice listens, and on Linux a video call app can't use the camera then (`/voice
mute` or `/face pause` frees it).

### Look at it to talk

With [Face presence](face.md) on and enrolled, you don't have to say its name: **look at the camera for about a
second** and Kurooto starts listening, as if you'd said "Kurooto" (no "Yes?", the being shows it's listening). The next
thing you say counts as said to it, a statement too, and the conversation goes on as usual after its answer.

- It has to be **your** face (Face presence recognises it; anyone's with `voice.listen.look_anyone`), close to the camera, and your head turned **straight at
  the camera**: at most about 15 degrees left or right (`voice.listen.look_yaw_deg`) and up or down from how you faced
  it when you enrolled (`voice.listen.look_pitch_deg`). A glance shorter than `voice.listen.look_dwell_s` (1 second)
  doesn't count.
- On its own the camera sees which way your **head** points, not your eyes, so looking at the screen next to the
  camera with your head turned to it may count too. If it opens while you're only reading, tighten the angles, or let it
  go by your eyes (below).
- It stays open while you keep looking. Look away for `voice.listen.look_away_s` (3 seconds) before saying anything
  and it closes again. One look opens it once: after it closes (you said something that wasn't to it, "stop", or you
  looked away), look away and back.
- **Anyone's look counts** (`voice.listen.look_anyone`, on, 0.8.18), not only yours: a friend looking at it can
  talk to it too, while people talking to each other without looking at it are left alone. Face presence reads where
  the three biggest other faces point (their head's turn, or their eyes against your calibration), never who they are.
  A guest is still a guest: Voice ID decides, and someone who isn't you gets chat only, no tools and none of your data.
  Off: only your face opens it, and with Voice ID someone else's voice isn't even written out.
- What you say still goes through the other checks: two voices at once, or people talking here lately, need a
  question or a request, or (`voice.listen.look_in_company`, on, 0.8.18) its name first or last, even misheard.
- It never opens while Voice is off or muted, on a call, while listening is off for the night, while Kurooto is asleep
  (drowsy, or woken in the night, it does: 0.8.18), or with Face presence off or paused. Only two times are kept, in
  memory: when someone started looking and when they last did.

`voice.listen.look_to_talk` (on) turns it off. `/voice` says "looking at it opens a conversation" while it can, and
whether it goes by your eyes or your head's turn (and why).

#### By your eyes

With the eye model and your eyes calibrated, a look counts by **your eyes on the camera's lens**, not your head: eyes on
the lens count even with your head a little turned, and eyes on the screen below the camera don't, even with your head
facing it. And it's **at once**: the first frame that sees your eyes on the lens opens the conversation
(`voice.listen.look_gaze_dwell_s`, 0), with Face presence looking up to 5 times a second while Voice listens
(`face.watch.look_fps`).

1. On the dashboard's Face page, under Look to talk, tap **Get the eye model** (MediaPipe Iris, 2.6 MB, Apache-2.0,
   downloaded once from Google's MediaPipe model store and checked against a pinned checksum).
2. Tap **Calibrate my eyes** and look at the camera's **lens** (not the screen), head turned to it, for about three
   seconds. Only you may be in view; it checks it's your face.
3. The Face page then says "Goes by your eyes on the camera", and while Voice listens it shows your last look's angles
   (sideways and up or down, in degrees), which help with the tolerances: `voice.listen.look_gaze_yaw_deg` and
   `voice.listen.look_gaze_pitch_deg` (10 degrees each). Calibrate again after moving the camera.

What's kept: four numbers in your sealed face model (where your irises sat in your eyes and how your head was turned
while you looked at the lens), a frame count and the date. Never a picture of your eyes. **Clear** on the Face page
drops them; forgetting your face drops them with the rest. A blink keeps the last verdict for a second; with your head
turned more than `voice.listen.face_yaw_deg` the eyes aren't trusted. `voice.listen.look_gaze` (on) off, no eye model,
or no calibration: it goes by your head's turn as above. Thick-rimmed glasses, reflections on lenses and dim light can
make your eyes hard to read; if looks stop opening it, recalibrate in your usual light or turn `look_gaze` off.

### When someone else may be talking: its name has to be a call

Mentioning Kurooto to a friend shouldn't wake it. So when someone else may be talking (Voice ID isn't sure the voice
is yours or knows it isn't, people talked here in the last minute without talking to Kurooto, or Face presence sees
two or more faces), its name counts only said first as a call: "Kurooto, what's due?", "hey Kurooto, ...", or just
"Kurooto". Its name at the end ("can you check this, Kurooto") or in the middle, or a word that only sounds like it,
is then only a mention: the other rules and the model on your computer decide, and the model is told it may be a
mention. With you alone and no one talking, its name first or last wakes it as before. Switches:
`voice.listen.careful_name` (on) and `voice.listen.chatter_s` (60 seconds).

### Telling it off

If it wakes when you weren't talking to it, say "stop", "not you", "I wasn't talking to you", "shut up", "be quiet",
"go away" or "never mind" within about 10 seconds of it opening the conversation or speaking: it stops speaking at
once, closes the conversation and says nothing. You can say it while it's still speaking (below, "Cutting in"); with
that switched off, say it as soon as it stops (or `/voice stop`, the dashboard). It notes the misfire (which rule woke
it, never your words) for the night's learning. `voice.listen.told_off` (on).

### Cutting in while it speaks

You don't have to wait for a long answer to finish: talk over it. Kurooto keeps listening while it speaks, goes quiet
at once when it hears you, and then:

- **"Stop", "never mind", "not you"** and the like: it just stops and closes the conversation (as above).
- **A question or a request** ("wait, what about Sunday?", "set it for six instead"): it stops and answers that, in the
  same conversation, so it knows what you were talking about.
- **Anything else** ("mm", "okay", a cough, a word to someone else): it wasn't for it, so it carries on, saying the
  sentence it was cut in from its start (0.8.17; before, it stopped for good and the rest of the answer went unsaid).
  If it can't tell within about 12 seconds, it stops.

It never takes its own voice coming back through the room for you. It counts as you cutting in when:

- **Voice ID** (on and enrolled) recognises your voice: at least about 0.6 seconds of speech that matches your voice
  print and is clearly closer to it than to Kurooto's own voice. Kurooto's own voice print is made once, in memory,
  from a phrase its voice says silently; it's never played or saved.
- **Or you're clearly louder than its echo.** It knows what it's playing and when, and learns how loud its own voice
  comes back to the microphone; speech well above that whose words, written out here, aren't what it's saying, counts.

Limits:

- **Speakerphone or a high volume:** its echo can drown you out. Speak up, come closer to the microphone, or turn it
  down. The same goes for the phone app playing its voice next to the computer: the computer's microphone hears that
  too, a little late, and it allows for that.
- **A single short word** like "stop" is too short for the voice check: say it clearly louder than it, or say a
  little more ("stop talking", "Kurooto, stop").
- **A guest can't cut in by voice:** with Voice ID only your voice passes the voice check, so someone else has to be
  clearly louder than Kurooto (and what they then say goes through the usual guest rules).
- **Without Voice ID** only the loudness check works, so a loud TV or someone shouting nearby may stop it; turn the
  switch off if that happens.

`voice.listen.barge_in` (on). Off, the microphone is dropped while it speaks, as before; `/voice stop` always works.
Nothing extra is kept: the sound stays in memory as for anything it hears, and the event log only says how it noticed
you and what came of it, never your words.

### Learning at night

Every night at 04:10 it learns from how its voice turns went: ones you carried on talking to it (good) and ones you
told off (misfires). Only flags and numbers are kept, under Kurooto's state in `voice/` (the rule that decided, how its
name was said, how many voices, Voice ID's decision and score, seconds since other talk, faces in view; never words or
sound). Once it has 20 turns with some of each, a small model can hold back a borderline opening (its name heard only
as a near miss, a follow-up, the model's judgement) that looks like the misfires. It can never stop "Kurooto, ..."
said first. `/voice` and `/health` show what it learned, as numbers. `voice.listen.learn_nightly` (on); forgetting
your voice (`/voice id forget`) deletes these too.

## The conversation (the "portal")

When the gate decides you're talking to Kurooto, a conversation opens: your words go to your AI like a chat message
(answers worded to be spoken), and the answer comes back on the dashboard and aloud. The conversation carries context
like a typed chat: your AI sees your turns before (a guest's turns stay apart). Keep talking and it follows the conversation: you don't have to say
its name again. Within 20 seconds of its answer ending (`voice.listen.follow_s`; counted from when it finishes, so a
phone playing its voice doesn't eat the time), whatever the same voice says goes to it, statements too, not only
questions. Another voice, two voices at once, or telling it off ends that. It closes:

- **at once** when the next thing it hears isn't to it (you turn to someone else);
- after `voice.listen.close_s` seconds (8) with nothing said to it, or `voice.listen.follow_s` (20) after an answer;
- when you mute it, a call starts, Kurooto pauses, or (with `voice.listen.night` off) the night begins.

The dashboard shows each step (listening, hearing, talking to it, thinking, speaking, closed) and a waveform.
Speech that wasn't for Kurooto (people talking to each other, noise) moves the waveform too: only its loudness
reaches the page, never its words. `voice.listen.levels` off stops both. On the being board the YOU lane is live while
it listens: the microphone's loudness scrolls through it as you speak (`look.being_live_waveform`).

## How fast it answers

From your last word to its first sound, a spoken turn goes through: writing out what you said (about half a second
with the base model), the gate and, when they're on, Voice ID and the face check, your AI (the longest part: an agent
program like Claude Code takes a few seconds to start and answer), making the first piece of speech, and playing it
(on another device, add its own delay). 0.8.16 makes that shorter, and the wait easier:

- **It tells you it heard** (`voice.speak.ack`, on: `tone`). The moment your turn goes to your AI, a short soft note
  plays, so the pause doesn't feel like it missed you. `word` says "Hmm." in its own voice instead; `off` is silence.
  It isn't played when the answer is already on its way.
- **It starts speaking before the answer is finished** (`voice.speak.stream`, on). With Claude Code, a Gemini key or
  Ollama answering without tools, each sentence is spoken as soon as your AI has written it, and the first one alone,
  so the first sound is made quickly. Anything it writes before using a tool ("Let me check your notes.") is said too.
  agy can't stream: its answer is spoken when it's done, as before. `/voice stop`, mute and talking over it stop it.
- **Plain chat can go to a quicker AI** (`voice.listen.fast_brain`, `same` by default). Small talk and general
  questions that need nothing of yours ("why is the sky blue") can go to the model on this computer (`local`) or to
  whichever AI answered quickest lately (`fastest`), as text only. Anything that mentions your things, the time, the
  web or an action, and anything it's unsure about, goes to your AI as always. It stays `same` unless you change it:
  a smaller model answers small talk less well.
- **It's ready when you start** (`voice.listen.warm_up`, `voice.listen.warm_brain`, both on). When listening starts,
  the transcriber and the voice are warmed (nothing is recorded or played), and Claude Code's program is run once so
  your first turn isn't the slow one.
- **It measures** (`voice.listen.timing`, on). `/voice` (or `kurooto voice`) ends with a line like "Speed (median of
  12 turns, from your last word): words 0.7 s, decided 1.2 s, sent 1.3 s, first words from the AI 4.1 s, first sound
  made 4.6 s, playing 4.7 s." Numbers only, never words, for the last 20 turns.

Since 0.8.17 it also writes your words out at your first short pause (`voice.listen.early`, on): if you don't go on,
the turn uses those words straight away, and a finished question ends your turn after 0.35 s of quiet instead of 0.7 s.
Nothing is sent early; only the writing out happens sooner, and with Voice ID's gate another voice is never written
out early. The line also splits "decided" to "sent": "handed on", "add-on intents" (an add-on's classifier of
plain-English requests) and "intents" (Kurooto's own), so a slow step there shows by name. By voice it no longer
waits for the offers that come as buttons (two close readings of a request, a feature that's off), which it can't
show you anyway; and before anything is said, the first clause of an answer is spoken as soon as it's written
instead of waiting for its whole sentence.

If it still feels slow, the speed line says where the time goes: a big gap between "sent" and "first words from the AI"
is your AI; between "first words" and "first sound made", making the speech (Piper, `voice.speak.engine`, is quicker to make
than Kokoro); between "first sound made" and "playing", the speakers or the other device.

### Live at the desk (Gemini Live, off)

`voice.listen.live` (0.8.17, off) answers your own spoken turns the way phone calls already work: Gemini Live hears
the turn and answers aloud, speech to speech, in about a second, instead of writing your words out, asking your AI and
making the answer's voice here. It's a different AI from your own (Google's Live model, with the tools a call has),
and **your voice goes to Google**, so it's off until you turn it on.

**What leaves the computer, exactly:** the sound of the turns Kurooto already decided were said to it by you, and
nothing else: only turns you say to it while facing it, close by. A turn goes to Live only after the gate called it
addressed (not chatter, not noise), Voice ID said it's your voice, and the face check actually saw a face close to the
camera and turned to it during that turn (`voice.listen.face_near`, `voice.listen.face_yaw_deg`). A turn let through
without a face seen goes the usual way (your AI, the voice made here), never to Live: the wake word and the request
right after it, `voice.listen.need_face` off, Face presence off or paused, and the camera unable to see with
`voice.listen.need_face_fallback` `voice`. Chatter, noise, other people's voices, a voice it's unsure of and anything
said while the conversation is closed never reach Google; those turns go the usual way or nowhere, as before. With each opened
session goes what a call's setup carries (your name, the assistant's name, which tools exist, the lessons from earlier
calls) and, while a turn runs, what its tools find for it (a note it reads, say). Google sends back the answer's
sound and its words. Nothing is written to disk; events hold the model, the stage and numbers only.

**How to turn it on:** it needs a Gemini key (Settings → AI model), Voice ID on and enrolled (only your voice goes,
so without Voice ID it never does) and Face presence on and enrolled (only while you face it). Then turn on `voice.listen.live` in Settings. It uses the call
settings `calls.live_model` (then `calls.live_models` if that one isn't available) and `calls.voice`.

**How it behaves:** the first turn of a conversation opens a Live session; while the conversation stays open, each
further turn you say to it goes to the same session (so it remembers what you just said); when the conversation
closes, so does the session. The answer plays through the same speakers or add-on output, you can cut in on it as
usual, and the words are shown and kept in the chat history like a typed turn, so if a later turn goes the usual way
the conversation carries on. Tools that need your tap (placing a call, setting an alarm) aren't run from the desk:
you get an Approve / Deny question, as with any AI request. If Live can't answer (no key, Google refuses, no sound
within about 5 seconds), that turn is answered the usual way: never silence. The speed line in `/voice` counts Live
turns too ("sent" is when your sound went, "first sound made" when Live's answer arrived).

## When it doesn't listen

- **Muted:** `/voice mute`, `kurooto voice mute`, or the dashboard's mute. It stays muted (across restarts) until
  `/voice unmute`. Muting also stops it speaking.
- **On a call:** while a phone call is on (`voice.listen.calls` to keep listening).
- **At night:** it keeps listening by default; turn `voice.listen.night` off and it stops during your night hours
  (`availability.night`).
- **Paused:** while Kurooto is paused, and on battery in saver mode.

## Sound: how it plays and records

On Linux with PipeWire, Kurooto plays its voice through PipeWire's `pw-play` and hears the microphone through
`pw-record` (0.8.16), separate programs: nothing from the sound system runs inside Kurooto, and the microphone follows
your system's default (pick it in your sound settings). Elsewhere, or with `voice.audio.backend` = `portaudio`, it uses
the sounddevice library (PortAudio) inside Kurooto, as before 0.8.16.

- `voice.audio.backend`: `auto` (the default) picks PipeWire's tools when PipeWire is running and they're installed,
  unless `voice.listen.device` names a microphone (those are sounddevice's names, so sounddevice keeps it); `pipewire`
  always uses the tools, and then `voice.listen.device` is a PipeWire node name (`wpctl status`, or `pw-cli ls Node`);
  `portaudio` always uses sounddevice. Speaking changes at once; listening the next time it starts (`/voice mute`, then
  `/voice unmute`).
- A microphone that disappears (unplugged, a PipeWire source removed, PipeWire restarted) is opened again after a
  pause; if it stays gone for about half a minute, `/health` says "the microphone stopped" and it tries again a minute
  later.

### Troubleshooting

| What you see | What to do |
|---|---|
| Kurooto stopped by itself while listening or speaking (0.8.10 to 0.8.15; `coredumpctl list` shows python with SIGSEGV or SIGABRT) | Fixed in 0.8.16: stopping or muting closed the microphone under the thread still reading it. Update. If it ever happens again, `coredumpctl info <pid>` shows where; set `voice.audio.backend` to `pipewire` so no sound code runs inside Kurooto. |
| No sound, or no listening, after updating to 0.8.16 on Linux | Kurooto now uses `pw-play` and `pw-record`. Check they're installed (the `pipewire` package) and that PipeWire runs (`wpctl status`). Set `voice.audio.backend` to `portaudio` to go back to the old way. |
| It listens to the wrong microphone | With `pipewire`, it follows your system's default input: change it in your sound settings, or set `voice.listen.device` to the PipeWire node's name. With `portaudio`, `voice.listen.device` takes sounddevice's names or numbers. |
| "the microphone stopped sending sound" in `/health` | The microphone went away and didn't come back within about half a minute. Plug it back in or pick another; it tries again by itself a minute later. |

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
  message (and kept in the chat history like a typed one), with one line saying it was said aloud at your desk,
  whether Voice ID knew your voice and whether Face presence recognises you in front of the camera (0.8.17: words
  only, never a picture; so "do you recognise me?" gets a true answer). While the conversation is closed, nothing
  leaves. With
  `voice.listen.fast_brain` `fastest` (not the default), a plain-chat turn may go to another AI you've set up (a
  Gemini key, say) instead of your main one, with what a chat request carries; `local` keeps it on this computer.
  With `voice.listen.live` (not the default), the sound of your own turns said to Kurooto (Voice ID: you, and facing
  it close by) goes to Google's Gemini Live instead, and its answer comes back as sound; see [Live at the desk](#live-at-the-desk-gemini-live-off).
  The turn times (`voice.listen.timing`) are numbers only and stay here.
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
| `voice.speak.join_sentences` | on | speak short sentences together, not each on its own |
| `voice.speak.numbers_as_words` | on | say times, dates, money, versions and units in words (only aloud) |
| `voice.speak.ack` | `tone` | while your AI thinks, a soft sound says it heard you: `tone`, `word` or `off` |
| `voice.speak.stream` | on | speak the answer a sentence at a time as your AI writes it (when it can stream) |
| `voice.listen.on` | off | listen through the microphone |
| `voice.listen.wake_word` | (none) | the path of your own openWakeWord `.onnx`; empty: its name wakes it |
| `voice.listen.name_variants` | (none) | more spellings of its name to accept; the common mishearings are built in |
| `voice.listen.model_judge` | on | let the model on your computer judge what the rules can't |
| `voice.listen.threshold` | 0.7 | how sure the model must be that you're talking to it |
| `voice.listen.close_s` | 8 | seconds of nothing said to it before the conversation closes |
| `voice.listen.follow_s` | 20 | after an answer, what the same voice says this soon counts, statements too (0: off) |
| `voice.listen.careful_name` | on | when someone else may be talking, its name counts only said first, as a call |
| `voice.listen.chatter_s` | 60 | other talk this recent makes it careful with its name |
| `voice.listen.told_off` | on | "stop", "not you", "never mind" right after it opened or spoke: it stops and closes |
| `voice.listen.learn_nightly` | on | learn at night from turns that went well or were told off (numbers only) |
| `voice.listen.need_face` | on | with Face presence on: answer only someone close to the camera and facing it |
| `voice.listen.face_near` | 0.5 | close: at least this share of your usual face height at the desk |
| `voice.listen.face_yaw_deg` | 35 | facing: turned at most this many degrees away |
| `voice.listen.need_face_fallback` | `voice` | the camera can't see: `voice` (the voice rules) or `none` (nothing by voice) |
| `voice.listen.look_to_talk` | on | with Face presence on: looking at the camera opens the conversation, no name needed |
| `voice.listen.look_dwell_s` | 1 | looking at it this long opens it (a glance doesn't) |
| `voice.listen.look_yaw_deg` | 15 | looking at it: head turned at most this many degrees left or right |
| `voice.listen.look_pitch_deg` | 15 | and at most this many degrees up or down from your enrolment's front face |
| `voice.listen.look_away_s` | 3 | looking away this long, with nothing said yet, closes it again |
| `voice.listen.look_gaze` | on | with your eyes calibrated (the Face page): your eyes on the camera count, not your head |
| `voice.listen.look_gaze_dwell_s` | 0 | by the eyes: looking this long opens it (0: the first frame) |
| `voice.listen.look_anyone` | on | (0.8.18) anyone's look opens it, not only yours (guests still get chat only) |
| `voice.listen.look_in_company` | on | (0.8.18) with others here, a look and its name (even misheard) count as the call |
| `voice.listen.look_gaze_yaw_deg`, `look_gaze_pitch_deg` | 10, 10 | by the eyes: how close to the lens your gaze must be |
| `voice.listen.timing` | on | time each turn from your last word to its first sound (numbers only, in `/voice`) |
| `voice.listen.fast_brain` | `same` | plain chat by voice: `same` (your AI), `local` (this computer's model) or `fastest` |
| `voice.listen.warm_up` | on | warm the transcriber and the voice when listening starts |
| `voice.listen.warm_brain` | on | get Claude Code's program (or, with `fast_brain` `local`, the local model) ready too |
| `voice.listen.live` | off | your own turns answered by Gemini Live, speech to speech (their sound goes to Google) |
| `voice.listen.night` | on | keep listening during the night hours |
| `voice.listen.calls` | off | keep listening during calls |
| `voice.listen.stt_model` | `base` | `tiny`, `base` or `small` |
| `voice.listen.language` | (worked out) | the language you speak, e.g. `en` or `hi`. Set it: worked out on each short clip, an Indian English accent is often taken for Hindi or Urdu and its name is missed |
| `voice.listen.auto_gain` | on | hearing follows the room: speech must stand clearly above the room's noise to count, and a quiet or far voice is brought up to one level before it's written out. Inside Kurooto only: the system's microphone volume is never changed |
| `voice.listen.auto_gain_snr_db` | `6` | how far above the room's noise speech must be, in dB (higher: stricter in a noisy room) |
| `voice.audio.backend` | `auto` | how sound plays and records: `auto`, `pipewire` (`pw-play`/`pw-record`) or `portaudio` (sounddevice) |
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

**In a conversation you opened** (0.8.13, `voice.speaker_id.carry_talk`, on), it goes further: while the conversation
that Voice ID knew you opened is open, any turn it's only "not sure" of (inside the margin, not clearly someone else,
one voice) stays yours, within 15 seconds or the conversation window (20), the longer, of its last answer to you. So
your history, notes and tools carry instead of the turn dropping to "only chatting". Before 0.8.13 such a turn went the
guest way. Off in strict mode.

**With your face** (0.8.13, `voice.speaker_id.face_assist`, on): when Face presence's last look (a few seconds old at
most) shows exactly one face and it's yours, a voice it's only "not sure" of counts as you. A voice clearly someone
else's, two voices, two faces or strict never do. With "improve over time" on, such a turn that went well (you carried
on, nothing told off) may refine your voice print like a very sure one, under the same daily cap and undo.

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

- Cutting in while it speaks works best near the microphone at a normal volume: a loud echo (a speakerphone, the volume
  up high) can drown you out, and a guest can't cut in by voice (see "Cutting in while it speaks"). `/voice stop` or
  mute always stops it.
- Without Voice ID it doesn't know who is speaking; with it, it knows you from anyone else, but can't tell two voices
  apart inside one turn, and can't tell a recording of you from you.
- Its name has to be heard and written out first, so waking takes a moment longer than a dedicated wake word model
  would, and a name Whisper mangles in a new way needs `voice.listen.name_variants`.
- Tested with fakes only so far: real microphones, speakers and the models haven't been tried on many computers.
