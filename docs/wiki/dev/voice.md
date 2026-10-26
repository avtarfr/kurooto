# Voice (`modules/voice/`, 0.8.8)

Kurooto speaks on the computer it runs on (Kokoro-82M by default, Piper as the lighter choice) and, with
`voice.listen.on`, listens to the room all day. Every decision about what it hears is made on the computer; only turns
the gate calls *addressed* reach the AI you picked, through the portal. Off by default (`Module` off until enabled),
with listening a second switch. User page: [../user/voice.md](../user/voice.md).

## Files

| File | What's in it |
|---|---|
| `modules/voice/__init__.py` | `Voice` (the module: settings, parts it wants, `hear()`, `ask_brain()`, the listener's lifecycle in `background()`, the API's `status()`/`say()`/`mute()`/`shape()`, `/voice`), `Speaker` (sentence-by-sentence speech), `strip_wake()` |
| `modules/voice/names.py` | `NameMatcher`: its name as Whisper may spell it (`MISHEARD`, `voice.listen.name_variants`, `skeleton()` + `distance()` near misses); `called()`, `anywhere()`, `uncall()` |
| `modules/voice/gate.py` | `Gate.decide(Heard, Context) -> Decision`: the rules, then the local model; `PROMPT`; `parse()` |
| `modules/voice/portal.py` | `Portal`: open/closed, `take(heard, decision)`, `tick()` (silence), `close(why)`, `context()` for the gate |
| `modules/voice/audio.py` | engines, all lazily imported: `Kokoro`, `Piper`, `Player`, `Mic`, `microphone()`, `Silero`, `Energy`, `Whisper`, `Wake`, `Listener` |
| `modules/voice/parts.py` | what to fetch: `PACKAGES` (pip specs into `<app>/voice/py-<X.Y>`), `models()` (URLs and sizes into `<app>/voice/models`), `Parts.install()` |
| `modules/voice/shape.py` | the waveform outline: `estimate()`, `from_pcm()`, `levels()`, `clean()`, `sentences()` |
| `tests/unit/test_voice.py` | everything above with fakes (no device, no model) |

## The flow

```
Mic (sounddevice | pw-record | parec), 16 kHz mono, 512-sample frames
  -> Listener (thread "voice-listen"): levels -> voice_level; held while Speaker.holding() or the portal is busy
       wake word (only with your own openWakeWord .onnx, 1280-sample steps) -> woke_at
       Silero VAD per frame: start >= 0.5, end after 700 ms < 0.35, max 15 s; 320 ms pre-roll (a deque in memory)
  -> Voice._heard_audio: queue (max 3, oldest dropped)
  -> worker thread "voice-hear": Voice.hear(Heard(speech, wake, seconds), pcm)
       blocked()? drop.  Whisper.text(pcm) (CPU, int8; the assistant's name as initial_prompt and hotwords) -> del pcm
       Gate.decide(heard, portal.context())
       not addressed: heard.text = "" (dropped), portal.take() closes an open portal
       addressed: NameMatcher.uncall() (the call isn't sent); portal.take(heard, decision, text) -> ask_brain(text) -> Speaker.say(reply)
```

`Voice.background()` (the module's long-running coroutine, `app.start_background`) runs every second: works out
`blocked()`, starts or stops the listener, closes the portal when blocked, and calls `Portal.tick()`. The listener
and the worker are daemon threads; the coroutine never blocks the loop. `heavy = True`: in saver mode on battery
`power.may_run` keeps it from starting, and `blocked()` says so.

`blocked()` reasons, in order: `listening is off`, `muted` (`state/voice.json`), `Kurooto is paused`, `on battery
(saver mode)`, `you're on a call` (`web/tools_api.py:live_call`, unless `voice.listen.calls`), `night hours`
(`core/availability.py:Availability.night`, only with `voice.listen.night` off; it's on by default), `not set up yet`.

## The gate

`gate.py`'s docstring is the spec; in short, first match wins:

1. no speech (VAD) -> noise, 1.0
2. your own wake word model fired (`voice.listen.wake_word`, an `.onnx` path; empty by default) -> addressed, 1.0
3. empty, or a transcriber's invention from silence (`MADE_UP`) while the portal is closed -> noise, 0.9
4. its name as a call, the default wake (first, after an optional "hey/ok/hi", or last; one to three words joined;
   `you.assistant_name` and "Kurooto", through `names.py:NameMatcher`)
   -> addressed, 0.95
5. the portal is awaiting (its name or the wake word alone opened it) -> addressed, 0.9
6. `voices >= 2` -> chatter, 0.8 (the listener doesn't count voices yet: `Heard.voices` stays None)
7. portal open, within `close_s`, and a question (`?`, `QUESTION`) or request (`REQUEST`) -> addressed, 0.85
8. within `after_speak_s` of speaking, a question or request; `REPLY` words (yes/no/sure ...) only when what it said
   ended in "?" -> addressed, 0.8
9. the local model (`Voice.judge`: `providers.local()` only when its `base_url` host is loopback, else the offline
   helper's `_generate`; None otherwise), with `PROMPT` and context lines (the open conversation, its last reply, how
   much unaddressed talk in the last minute, a mid-sentence mention of its name). `parse()` takes the first `{...}`
   JSON, else a single class word at 0.5, else chatter at 0. Addressed below `voice.listen.threshold` -> chatter.
   No model, no answer, or `model_judge` off -> chatter, 0.0.

The prompt (`gate.py:PROMPT`):

```
You decide whether speech heard near a computer is spoken TO its voice assistant, called {name}.
It was written out by a speech recogniser, so words may be wrong.

Heard: "{text}"
{context}
Answer with JSON only, like {"class": "chatter", "confidence": 0.8}. The classes:
- "noise": not real speech meant for anyone (a TV, music, a cough, words with no sense).
- "chatter": people talking to each other, on the phone, or to themselves; {name} mentioned in passing.
- "addressed": a request, a question or an answer meant for {name}.
When unsure, answer "chatter" with a low confidence.
```

## Its name (`names.py`)

The default wake is the name heard by faster-whisper; openWakeWord's ready-made models (CC BY-NC-SA 4.0) are never
fetched. `Whisper` gets the name as `initial_prompt` ("Kurooto.") and `hotwords` (dropped on a `TypeError` from a
faster-whisper before 1.0.2). `NameMatcher(names, variants)`:

- `spellings`: each name joined without spaces, `MISHEARD[name]` for the default "kurooto" (kuroto, kurouto,
  kuruto, curoto, kurato, "kuro to", "coo roto", kirito, "guru to", kuroo, kuro ...) and
  `voice.listen.name_variants`; one to three adjacent words are joined before comparing, so spacing doesn't matter.
- near misses, against the names themselves only (a mishearing as the target would let "kurt" match "kuroto"): 4+
  letters, at least 2 vowel groups and within 1 of the name's, the same `skeleton()` (consonants with
  c/k/q/g, t/d, r/l, b/p, v/f, s/z merged; vowels, h, w, y dropped; doubles once), and Levenshtein `distance() <= 2`.
- `called()`: at the start (after one of `CALLS`) or the end; `anywhere()` for the model's context line; `uncall()`
  removes the call before the turn is sent.

`tests/unit/test_voice.py` lists mishearings that must match and ordinary words that must not (cool, auto, curry,
ghetto, kurt, router, kurta, karate, curator, Kyoto, Toronto, kettle ...). "cool auto" was dropped: it matched an ordinary phrase.

## The portal

`Portal.take()` with a non-addressed decision records the time (never the words) for the "talk nearby" count and
closes an open portal at once (`voice_state` `closed`, why `not addressed`). An addressed one opens it
(`Voice._portal_changed` logs `voice_portal {open, why}`), publishes `voice_text {who: "you"}`, `thinking`, calls
`send` (`Voice.ask_brain`), publishes `voice_text {who: "kurooto"}`, `speaking`, speaks, then `addressed` (waiting).
The name or wake word alone (`uncall()` leaves nothing) says "Yes?" (locally) and sets `awaiting`; nothing is sent. `tick()` closes after `close_s` of
nothing addressed (why `silence`). `close()` is also called on mute, block and `stop()`.

`ask_brain()` builds `Incoming(text, via="voice", voice=True)` and calls `app.handle()`: commands and instant requests
answer through `respond`; anything for the AI becomes a Chat job. `modules/chat.py` makes `via == "voice"` jobs quiet
(no Telegram copy) but keeps the conversation history; `ask_brain` waits for the job (`jobs.watchers` sets an event,
plus polling), and records the turn with `Chat.record_turn` (quiet jobs skip `Jobs._deliver`, which normally does it).
`persona.register_line(voice=True)` asks for an answer worded to be spoken.

`voice.speak.what = "all"`: the same watcher speaks every non-quiet, non-background answer in lane "you".

## Events and the live stream

High-rate and wordy messages go **only** to open dashboard pages, never to the event log: `Voice.publish()` calls
`app.live.push({"t": "voice", "kind": ..., ...})` (`web/live.py:Live.push`). The dashboard's stream handler ignores
unknown `t`, so a page that doesn't draw Voice is unaffected.

| kind | fields | when |
|---|---|---|
| `voice_state` | `state`: `listening`, `hearing`, `addressed`, `thinking`, `speaking`, `closed`, `off`; `portal` (bool), `listening` (bool, the microphone is on), `why` | every change; `closed` = the portal closed (still listening); `off` = the microphone closed (`why`: muted, a call, night ...); `listening` after a non-addressed stretch carries the class as `why` |
| `voice_level` | `levels`: 5 numbers 0..1 (two decimals: RMS on a -60..0 dB scale, 20 ms each), `rate`: 50 | every 100 ms while listening and a page is in sight (`voice.listen.levels`) |
| `voice_text` | `who`: `you` or `kurooto`; `text` | an addressed turn and its reply, `/voice say` and `POST /api/voice/say` |
| `voice_speak` | `samples` (the sentence's shape, `from_pcm`), `rate`: 50 | as each sentence starts playing |

Example: `{"t":"voice","kind":"voice_state","state":"thinking","portal":true,"listening":true,"why":""}`.

Logged events (`app.events.emit`, so also in the feed with `cell: "voice"` via `web/live.py:EVENT_CELL`), with no
words: `voice_portal {open, why}`, `voice_listening {on, why}`, `voice_mute {on}`, `voice_failed {part, error}`.

## API (`web/api.py`)

| Route | Body | Answer |
|---|---|---|
| `GET /api/voice` | | `Voice.status()`: `on, state, portal, listening, why, muted, blocked, line, speak {on, engine, voice, rate, what, player, speaking}, listen {on, wake_word, stt_model, close_s, night, calls, microphone}, engines {kokoro, piper, whisper, vad, wake}, missing, missing_gb, heard {noise, chatter, addressed}, choices {voices, stt_models}` |
| `POST /api/voice/say` | `{"text": "Good morning"}` | `{"ok": true, "message": "Speaking."}` (not waiting for it to finish); `ok: false` with why when off, muted or no engine |
| `POST /api/voice/mute` | `{"on": true}`, `{"on": false}`, `{}` flips | `{"ok": true, "message": "...", "muted": true}` |
| `POST /api/voice/stop` | | stops speaking |
| `POST /api/voice/shape` | `{"text": "Hello there."}` | `{"samples": [0.55, 0.92, ...], "rate": 50, "seconds": 0.9, "source": "tts" \| "estimate"}` |

The shape: `samples[i]` is loudness 0..1 at `i / rate` seconds. `source: "tts"` when Voice is on and an engine is set
up: the text is synthesised into memory (never played) and each 20 ms window's peak is taken, scaled to the loudest.
Otherwise `"estimate"` (`shape.py:estimate`, deterministic): vowels 0.55 rise, 0.92 hold (longer for vowel pairs),
0.6 fall; voiced consonants `l m n r w v z j` 0.45, 0.5; plosives `p t k b d g c q` 0.0 then 0.78; sibilants and
fricatives (`s f h x`, `sh ch th ph zh`) three of 0.22/0.31/0.18/0.27/0.24 in turn; 0.05 between words; 8 zeros at
`, ; : - ( )` and 15 at `. ! ?` and line breaks; digits 0.5, 0.85, 0.85, 0.5; other letters 0.5, 0.8, 0.6; trailing
silence trimmed; `voice.speak.rate` resamples the length. Text is `clean()`ed first (Markdown, links, code).

## Parts and setting up

`Voice.wants()` lists the parts the switches need (`pkg:audio`, `pkg:kokoro|piper`, `model:kokoro|piper`; with
listening `pkg:listen`, `model:vad`, `model:whisper-<size>`; with your own wake word model, `pkg:wake` and `model:wake-common`).
`ready()` is false with the download size until they're all there, so `app.enable()` refuses and the Features card
shows **Set up** (`Module.setup`, run by `POST /api/modules/setup` in the background with progress). Packages go
through uv (`install.json`'s, else on PATH) or `python -m pip`, with `--target <app>/voice/py-<X.Y>` (never Kurooto's
venv; `Parts.importable()` appends it to `sys.path`, after Kurooto's own). openwakeword is installed `--no-deps`
because it declares `tflite-runtime`, which has no Python 3.12 wheels; its real needs are listed beside it. Models
are fetched with `core/egress.py:urlopen` (feature "Voice") to `<name>.part`, renamed when complete. No checksums are
pinned yet (the hosts are the projects' own release pages); a pinned sha256 per file is a follow-up.

Hosts: `github.com` (Kokoro, Silero; openWakeWord's feature models only with your own wake word model), `huggingface.co` (faster-whisper, Piper voice); uv/pip
are counted as handed to them.

## Portability

No Linux-only call without a guard: playback tries sounddevice first everywhere, then `pw-play`/`paplay`/`aplay` only
on Linux, `afplay` on macOS, `winsound` on Windows; capture is sounddevice (PortAudio is bundled in its Windows and
macOS wheels; Linux uses the system's libportaudio) or `pw-record`/`parec` on Linux; `microphone()` asks sounddevice,
then `pactl` on Linux, else "can't tell". Subprocesses it starts are its own children, stopped by their exact pid.

## Not verified

Written against the published APIs of kokoro-onnx 0.4, piper-tts 1.2/1.3, faster-whisper 1.1, openwakeword 0.6,
Silero VAD v5 and sounddevice 0.5, but run only with fakes: no real microphone, speaker or model was used in the
tests or the build. Silero's v4 input names are handled too. The first real run should check `kurooto voice`,
`/health`, and a spoken "Kurooto, what's the time?".
