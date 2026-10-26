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
| openWakeWord and a wake word | the wake word | 0.2 GB |

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

## Listening

With `voice.listen.on`, the microphone stays open all day, and everything below happens on your computer:

1. **Voice activity** (Silero VAD) finds stretches of speech; anything else is never even written out.
2. **The wake word** (openWakeWord) listens for its phrase all the time.
3. **Writing out** (faster-whisper) turns each stretch of speech into words.
4. **The gate** decides: noise, chatter (people talking to each other), or talking to Kurooto.

The wake word is **"hey Jarvis"** by default. There's no ready-made "hey Kurooto" model yet: the openWakeWord project
ships "hey Jarvis", "Alexa", "hey Mycroft" and "hey Rhasspy" (`voice.listen.wake_word`), and you can train your own
"hey Kurooto" with openWakeWord's training notebook and put the path of its `.onnx` file in the same setting. Saying
**its name** first or last ("Kurooto, what's due?", "what's due, Kurooto?") works as well as the wake word.

## How it tells you're talking to it

In this order, first match wins:

| What it heard | Counts as |
|---|---|
| no speech | noise |
| the wake word | talking to it |
| no real words (or what transcribers invent from silence: "thank you", "[music]") | noise |
| its name, first or last | talking to it |
| the first words after the wake word on its own | talking to it |
| two or more voices, and none of the above (when the listener can tell; today's can't, so the model judges this from the words and from how much talk there's been nearby) | chatter |
| a question or request while the conversation is open | talking to it |
| a question or request within 6 seconds of it speaking (a yes or no too, if it asked something) | talking to it |
| anything else | the model on your computer decides |

The model on your computer (Ollama, the one Local AI models set up, or the offline helper's) reads the words and
answers noise, chatter or talking to it, with how sure it is. Below `voice.listen.threshold` (0.7) it counts as not
talking to it. With no local model, only the wake word, its name and the rules above open a conversation.

## The conversation (the "portal")

When the gate decides you're talking to Kurooto, a conversation opens: your words go to your AI like a chat message
(answers worded to be spoken), and the answer comes back on the dashboard and aloud. Keep talking and it follows the
conversation. It closes:

- **at once** when the next thing it hears isn't to it (you turn to someone else);
- after `voice.listen.close_s` seconds (8) with nothing said to it;
- when you mute it, a call starts, the night begins, or Kurooto pauses.

The dashboard shows each step (listening, hearing, talking to it, thinking, speaking, closed) and a waveform.

## When it doesn't listen

- **Muted:** `/voice mute`, `kurooto voice mute`, or the dashboard's mute. It stays muted (across restarts) until
  `/voice unmute`. Muting also stops it speaking.
- **On a call:** while a phone call is on (`voice.listen.calls` to keep listening).
- **At night:** during your night hours (`availability.night`; `voice.listen.night` to keep listening).
- **Paused:** while Kurooto is paused, and on battery in saver mode.

## Commands

| Command | What it does |
|---|---|
| `/voice` | what it's doing, and how much it heard since it started (counts only) |
| `/voice mute`, `/voice unmute` | stop and start listening and speaking |
| `/voice stop` | stop speaking now |
| `/voice say <text>` | say this now |

The same from a terminal: `kurooto voice`, `kurooto voice mute`, `kurooto voice say Hello`.

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
openWakeWord (Apache-2.0; its ready-made wake word models are CC BY-NC-SA 4.0, for personal non-commercial use),
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
| `voice.listen.wake_word` | `hey_jarvis` | the wake word model, or the path of your own `.onnx` |
| `voice.listen.names` | kurooto, kuroto, kurato | its name as the transcriber may write it |
| `voice.listen.model_judge` | on | let the model on your computer judge what the rules can't |
| `voice.listen.threshold` | 0.7 | how sure the model must be that you're talking to it |
| `voice.listen.close_s` | 8 | seconds of nothing said to it before the conversation closes |
| `voice.listen.night`, `voice.listen.calls` | off | keep listening at night, during calls |
| `voice.listen.stt_model` | `base` | `tiny`, `base` or `small` |
| `voice.listen.language` | (worked out) | the language you speak, e.g. `en` or `hi` |

All of them: [the settings guide](../../SETTINGS_GUIDE.md).

## What it can't do yet

- It can't be interrupted while it speaks: it doesn't listen while speaking (so it doesn't hear itself). `/voice stop`
  or mute stops it.
- It doesn't know who is speaking; "several voices" is the rule's best guess, not speaker recognition.
- The wake word is "hey Jarvis" until you train your own.
- Tested with fakes only so far: real microphones, speakers and the models haven't been tried on many computers.
