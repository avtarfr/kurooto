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

## Used by Face presence (0.8.10)

- `Voice.greet(text, listen_s, talk=True) -> (spoken, "talk" | why)`: publishes `voice_text`, speaks (waiting), then,
  with `talk`, listening on and not `blocked()`, calls `Portal.invite(text, listen_s)`. `(False, why)` when Voice is
  off, muted or has no speech engine.
- `Portal.invite(text, hold_s)`: opens the portal with `awaiting = False` (gate rule 5 would take any speech, including
  what's said to someone nearby), `last = spoke_at = now`, `last_reply = text`, and `close_s = hold_s` until it closes
  (then the earlier value is put back). Rules 7 and 8 and the local model decide what's addressed; anything else closes
  it.
- `Parts(root, app_dir, packages=None, table=None, models_dir=None, feature="Voice")`: Face presence passes its own
  packages, model table, models folder and name and shares `root` (one `py-X.Y`, one numpy). `ModelFile.sha256` is
  checked after a download when set (a mismatch deletes the `.part`); `Parts.install_from(folder, keys, progress)`
  copies matching model files and installs wheels with `--no-index --find-links`. Voice's own behaviour is unchanged.
- `_job_done` doesn't read an answer aloud while `app.away_from_desk()` with `face.away.hold_desktop` on.

Details: [face.md](face.md).

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
       not addressed: heard.text = "" (dropped), its loudness outline -> voice_heard, portal.take() closes an open portal
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
| `voice_heard` | `samples`: at most 120 numbers 0..1 (`shape.envelope`: one per 20 ms of the stretch on the `voice_level` scale, fewer and wider buckets for a long one), `addressed`: `false`; nothing else, no words | a stretch that wasn't a turn (chatter, noise, not to it, or someone else dropped by Voice ID's gate), from `Voice._heard_wave` on the `voice-hear` thread, while a page is in sight (`voice.listen.levels`) |

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
are fetched with `core/egress.py:urlopen` (feature "Voice") to `<name>.part`, renamed when complete. A `ModelFile` with
a `sha256` (0.8.10: Voice ID's two models) is hashed while it downloads; a mismatch deletes the `.part` and fails with
"… didn't match its checksum (a damaged or changed download); nothing was kept". The other files aren't pinned yet.
`Parts.add_file(path)` installs from a file already on the computer: a model file only when its basename matches a
pinned `ModelFile` and its hash matches (unpinned ones: "this part has no checksum pinned yet; download it instead"),
copied via `.part`; a `.whl` of a package in `PACKAGES` with the installer and `--no-index --find-links <its folder>
--target <py>` (wheels beside it, numpy's or onnxruntime's, are found too). Surfaces: `kurooto voice parts add FILE...`
(works without the daemon) and the page's Install from a file.

Hosts: `github.com` (Kokoro, Silero; openWakeWord's feature models only with your own wake word model; Voice ID's
model), `release-assets.githubusercontent.com` (where GitHub's release downloads redirect; urllib follows the redirect,
so it's listed since 0.8.10), `huggingface.co` (faster-whisper, Piper voice); uv/pip are counted as handed to them.

## Voice ID (0.8.10)

Only the owner's voice can make Kurooto act; any other voice, or one it isn't sure of, can only chat. Switch
`voice.speaker_id.on` (off by default); its behaviours each have their own: `gate`, `carry`, `tell_guests`, `adapt`
(off), `spoken_enrol`, and `voice.listen.conversation_mode`. User page: [../user/voice.md](../user/voice.md#voice-id-only-your-voice-can-make-it-act).

### Files

| File | What's in it |
|---|---|
| `modules/voice/speakerid.py` | pure-Python vector maths (Kurooto has no numpy dependency), `Thresholds`/`Band`, `calibrate()`, `decide()`, `Verdict`, `Ctx`, `Verifier`, `Adapter`, the impostor `Bank` (`read_bank`/`write_bank`), `Embedder` (numpy + onnxruntime + kaldi-native-fbank from Voice's packages) |
| `modules/voice/enrol.py` | `CONDITIONS`, `PHRASES`, `CALL_PHRASES`, `quality()` (quiet and far: `softer()`, 4 dB lower or 4 dB less SNR than the normal step's medians, for automatic gain), `voice_checks()`, `Cut`, crops, `control_word()`, `Session` (the state machine, driver-agnostic) |
| `modules/voice/voiceid.py` | `VoiceID` on `Voice.voiceid`: the template (load/save/forget), `check()`, conversation mode, status for the API, the enrolment thread and its microphone `Listener`, `train()`, `test()`, adapt and its undo, the `vid` button |
| `core/biometric.py` | `BioStore(app, kind)`: one sealed template per kind; `Locked`; `BIOMETRIC_SECRETS`; `note_others()`/`others_present()` (a shared in-memory "someone else is here" signal a face part can feed) |
| `core/guest.py` | the guest path: `handle(app, msg)`, `kind()` (match, never run), `prompt()`, the hourly limit |
| `providers/context.py` | `guest_context(app)` |
| `web/static/voiceid.html`, `voiceid.js` | the page `/voice-id` |
| `tools/voiceid_bank.py` | builds `data/voiceid/impostors-<model>.bin` (dev tool, never imported) |
| `tools/voiceid_eval.py` | the offline evaluation (dev tool, never imported): false accepts and rejects on held-out LibriSpeech speakers through `enrol.Session`, `calibrate()` and `Verifier.check()` |
| `tests/unit/test_voiceid.py`, `tests/unit/test_guest.py`, `tests/unit/test_voice.py` (its Voice ID part) | fakes only |

### The model

CAM++ from 3D-Speaker (Apache-2.0), ONNX by sherpa-onnx (Apache-2.0): `campplus-en` (VoxCeleb, 512-d, default) or
`campplus-multi` (zh+en, 192-d), parts `model:voiceid-campplus-en|multi` with pinned sha256, and `pkg:voiceid`
(kaldi-native-fbank). CPU only (`CPUExecutionProvider`, 2 intra-op threads; the GPU is the local AI's). The front end
comes from the model's metadata (`sample_rate` 16000 only, `normalize_samples`, `feature_normalize_type: global-mean`,
`output_dim`); fbank: 80 bins, dither 0, snip_edges, 25/10 ms. About 50 ms per 3 s turn on a Ryzen 7 7435HS by the
spec's bench (not re-measured in this build). The model loads on first use and is dropped on `Voice.stop()` and when
the switch goes off.

### The flow change in `hear()`

```
with voice.speaker_id.on and .gate (default):
  VAD speech -> who = voiceid.check(pcm, speech_s)          # before any transcription
    not owner, no wake word, portal closed:
      Whisper on the first and last 2 s only (_edges); its name not called -> chatter, dropped, never written out
  Whisper (all of it) -> Gate.decide(heard, ctx + conversation) -> portal.take(..., who=who)
with .gate off and voice.listen.conversation_mode on (default): who = voiceid.check(pcm) for every stretch of speech
  (so another voice still starts conversation mode), then Whisper (all of it) -> Gate -> portal.take(..., who)
with both off: Whisper -> Gate -> addressed only: who = voiceid.check(pcm) -> portal.take(..., who)
```

`Heard.speech_s` is the VAD's speech time (the listener now passes per-frame flags as a 4th argument to `on_speech`),
not `seconds` (which includes the pre-roll and tail). The portal counts a `session` per opening, keeps
`last_owner_at`/`last_owner_session` for carry, publishes `voice_text {who: "you", speaker}` (the decision word, never
the score), calls `send(said, who)`, and prefixes the guest notice once a session per kind. `owner_only_at_all`: nothing
published or sent; "I only answer my owner's voice." at most once a minute (each call opens a new session). `ask_brain`
builds `Incoming(speaker=who.decision, speaker_by="voice")`.

**Conversation mode** (`Context.conversation`): set while `biometric.others_present()` (a guest voice in the last
`voice.listen.conversation_s`, or a face part's signal) or three guest voices in two minutes. Then the gate takes its
name only with a question or request after it (or nothing), the wake word, the turn right after them, and a follow-up
within `conversation_follow_s` of its answer; rules 7 and 9 (open portal, local judge) don't apply.

### `decide()` and `calibrate()`

`decide(score, t, speech_s, ctx)`: missing / locked / model failed -> unsure; voices >= 2 -> unsure; short turns
(< 2.5 s of speech) use `t.short`; under `min_speech_s`: owner only by carry (same portal session, within `carry_s`,
score >= unsure; never in strict), else unsure; score >= accept -> owner; >= unsure -> unsure; else guest.

`calibrate(samples, bank, synthetic, strictness, margin, threshold)`: n >= 12; outliers by leave-one-out (`g_i <
median - 3 * 1.4826 * MAD` and `< 0.30`, at most 10%, named by condition); centroid = normalised mean; held-out genuine
scores (long, and the 1.5 s crops for short) against `c_-i`; impostor scores from the bank (full + 3 s for long, 1.5 s
for short, plus Kokoro's 30 synthetic vectors when Kokoro is set up); per set `accept = quantile(I, 1 - far)` with far
1% / 0.2% / 0 (strict: `max(I) + 0.03`), clamped to [0.30, 0.85]; `unsure = min(quantile(I, .99), accept - margin)`.
Grade: good (FRR_long <= 5%, FRR_short <= 15%, median genuine - accept >= 0.12), fair (FRR_long <= 15%), weak (saved
only with Use it anyway). `threshold > 0` overrides accept for both, applied at check time from the stored calibration
so it takes effect at once; strictness and margin need a Retrain. The override is held to `OVERRIDE` (0.30 to 0.95)
and the margin to 0..`MARGIN_MAX` (0.2) wherever they're read (`override()`, `band()`, `margin_of()`): a typed 0.05
can't make a stranger "you", and a wide margin can't let any short reply carry.

**The bank.** `tools/voiceid_bank.py` over LibriSpeech dev/test (146 speakers x 4 utterances x {whole, 3 s, 1.5 s}, about
1,750 rows; optionally Common Voice's India and South Asia accents with `--cv`), float16, one file per model with the
model's sha256 in its header. Train refuses when it's missing or for another model. **Not in this commit:** building it
needs LibriSpeech (about 1.3 GB) and the two model files downloaded; see "Not verified".

### Evaluation (`tools/voiceid_eval.py`)

```
uv run --with onnxruntime --with kaldi-native-fbank --with soundfile --with numpy python tools/voiceid_eval.py \
    --librispeech DIR --model <the .onnx> --cache <scratch dir> --groups 12 [--out results.json]
```

Each LibriSpeech dev/test speaker is enrolled through `enrol.Session` (stt off) from his largest chapter, the conditions
made from the clean reading (quiet -14 dB; far -10 dB and a synthetic room, RT60 0.45 s; noise: pink at 10 dB under
the speech, VAD flags from the speech before the noise, as Silero would find it; short requests 1.2-2.5 s; free 11 s),
then `calibrate()` at each strictness and `Verifier.check()` for 8 held-out utterances per speaker (another chapter where
there is one), whole (up to 8 s) and cut to 2, 1.5 and 0.8 s, against every stranger in its group. The impostor set is
built with `voiceid_bank.py`'s recipe from the speakers *not* being tested ("halves": dev vs test; "groups": K groups,
each against a set from the other K-1, pooled over 4 groupings). Vectors are cached in the scratch folder.

campplus-en, groups (12), 146 speakers, 4,668 own and 52,179 stranger trials per row (2026-10-27):

| strictness | accept, long (median, range) | you: long / 2 s / 1.5 s | stranger passes: long / 2 s / 1.5 s | same gender, long | carry (0.8 s after you): you / stranger |
|---|---|---|---|---|---|
| relaxed | 0.385 (0.30-0.53) | 99.3 / 98.5 / 89.5 % | 1.36 / 1.59 / 1.11 % | 2.49 % | 95.2 / 1.88 % |
| normal | 0.439 (0.30-0.67) | 99.3 / 98.4 / 89.2 % | 0.56 / 0.62 / 0.43 % | 1.02 % | 91.6 / 0.83 % |
| strict | 0.506 (0.33-0.71) | 98.9 / 97.3 / 87.2 % | 0.13 / 0.19 / 0.14 % | 0.26 % | 0 / 0 % |

The four groupings alone, stranger passes on a long turn at normal: 0.90, 0.34, 0.46, 0.52 %; a 0.8 s turn alone is
never "you" (min_speech_s). campplus-multi: normal 0.51 % (relaxed 1.17, strict 0.16), you 99.2 % on long turns.
Grades: 581 good, 3 fair at normal. Enrolment: every speaker finished; 116 samples rejected as too short (of 2,894
tries), 2 as identical, 2 as not sounding like the rest. 30 of the 146 have one chapter only, so their own turns come
from the chapter they enrolled from (an easier test for them).

What it says: the targets in `FAR` (1 %, 0.2 %) are per impostor *row*, but a few look-alike voices carry most of the
misses, and a set of 146 speakers can't place a cut-off at 1 in 500 of the whole population (that needs more speakers,
not more rows): relaxed and normal pass strangers about 1.4 and 2.8 times as often as their targets. With fewer
speakers in the set it gets worse (18, 36, 73 speakers: 2.2, 1.1, 0.58 % at normal, halves). The defaults weren't
changed: the miss rate is set by how many speakers the set has, the owner-side cost of a higher cut-off can't be
measured on clean audiobook speech, and strict (0.13 %) is there for a room with strangers. A bigger impostor set (more
speakers, e.g. Common Voice with `--cv`) is the real fix. Limits: read speech, mostly clean, one microphone a chapter;
simulated conditions; strangers, not relatives.

### Adapter

Takes a turn only when: owner by "your voice" (not carried), score >= accept_long + 0.08, speech >= 2 s, not two
voices, under `adapt_per_day`; FIFO up to `adapt_max`; centroid = normalize(0.75 * enrolled + 0.25 * mean(adapted));
drift guard cos(new, enrolled) >= 0.95, else `drift_stopped`; thresholds derived again after each take. Undo today /
all.

### Storage

`BioStore(app, "voice")`: `state/voiceid/template.bin` (0600 in a 0700 folder), `nonce || AES-256-GCM(json)` with AAD
`kurooto-biometric:voice:v1`, key `biometric.voice.key` (secrets; made on the first save and read back; never a new
key over an existing file: `Locked`). JSON: model, model_sha256, mic, dates, `samples [{e, s, cond, day}]` (base64
float16), `adapted [{e, day}]`, `centroid`, `centroid_enrolled`, `thresholds`, `calibrated`, `genuine`, `report`,
`last_test`, `drift_stopped`. Kept out of backups (`SKIP_STATE_DIRS`, and `known_secret_names` drops the key), profile
sync (`NEVER`), diagnostics (`KNOWN_SECRETS` redacts the key; state isn't bundled), events and the live stream. The
uninstall part should list `state/voiceid/` among what it deletes. `forget()` deletes the key first, then the file;
`/forget all` (core/retention.py) calls it.

Coordination with the face part: its spec names the shared file `BioStore(app, feature)` with `<feature>.key` and
`<state>/<feature>/`; this build's is `BioStore(app, kind)` with `biometric.<kind>.key` and `<state>/<kind>id/`.
Whoever merges second adapts; there must be one `core/biometric.py`.

### API and the live stream

| Route | Body | Answer |
|---|---|---|
| `GET /api/voice/id` | | on, mode, model, enrolled, locked, grade, samples {total, by_cond}, thresholds, calibrated, report (numbers; a 24-bin histogram), pending, last_test, adapt {on, count, cap, today, last, drift_stopped}, mic {enrolled, now}, ready, missing, bank, who (counts), session |
| `POST /api/voice/id/session` | `{action: start\|again\|continue\|pause\|stop\|keep, own_words?, conds?}` (again: start over, the whole plan from nothing; the template in use stays until the new one is built; a kept start-over is marked `reenrol` and resumes with the whole plan) | `{ok, message, session}` |
| `POST /api/voice/id/skip` | `{cond}` | the session |
| `POST /api/voice/id/train` | `{use_anyway?}` | `{ok, saved, report, message}` |
| `POST /api/voice/id/undo` | | back to the template before the last build |
| `POST /api/voice/id/test` | `{as: me\|other\|synthetic}` | `{ok, score, decision, why, thresholds, speech_s, short, pass}` |
| `POST /api/voice/id/adapt` | `{undo: today\|all}` | `{ok, message, count}` |
| `POST /api/voice/id/forget` | `{confirm: true}` | `{ok, message}` |
| `POST /api/voice/id/parts/add` | `{path}` | `{ok, message}` |

Live (`{"t": "voice"}`, open pages only): `voiceid_session {state, cond, prompt, done, need}`, `voiceid_attempt {cond,
ok, reason, level_db, snr_db, speech_s}`, `voice_level` while a session listens; `voice_text` gains `speaker`, and an
addressed `voice_state` gains `who`. Events (counts and words only, no floats): `voiceid_trained {grade, samples,
dropped}`, `voiceid_session`, `voiceid_forgotten`, `voiceid_adapted`, `voiceid_adapt_stopped`, `voiceid_adapt_undone`,
`voiceid_locked`, `voiceid_refused {what, speaker}`, `voiceid_guest_job`, `voiceid_guest_turn`, `voiceid_switch`.

### The guest path

`App.handle`, right after `message_in` and before tone/pest: `if msg.speaker not in ("", "owner"): guest.handle()`.
`guest.handle`: owner_only_at_all -> one line; `/` -> refused; a match (never run) of the enabled modules' intents,
`threads`' and `ledger`'s question patterns, `repoproject.asked`, `turnon.find` -> refused as action or personal; the
hourly limit; else `jobs.submit(prompt, audience="guest", text_only=True, quiet=True, effort="low", brain=<local id with
guest_brain: local>)`. The runner for `audience == "guest"`: no `assembler.for_request`, no selfdoc or scratch,
`guest_context()`, `tools=[]`, `mcp=None`, `mcp_env={KUROOTO_JOB: id}` only (so agy's own registration of `kurooto mcp`
carries the guest's job id), a `run_tool` that refuses, `cwd = <state>/guest` (emptied each run), the one AI it was
given (no fallback, no last resort, no automatic order), no watchers (nothing learns). For a guest job id,
`core/tools.tools_for` lists nothing (`kurooto mcp` shows no tools; `POST /api/tools/call` answers 404) and
`run_tool` refuses. When Voice is done waiting (answered, failed or given up), `Jobs.forget_guest(id)` stops it if it's
still going and blanks its prompt, result and detail: the row stays, titled "Guest", so tuning, gists and the search
index never see the guest's words. The guest's last four turns of this portal session live
in `VoiceID.guest_turns` (memory) and go into the next turn's prompt; Chat's history never sees them.

### Guarded

`core/tap.py`: `voice.enrol` (typed, button); the `vid` button is `data.delete`. `/voice id …` and `/voice enrol`
refuse `msg.via == "voice"`. The settings API is fine (the dashboard and the phone's sealed settings are authenticated).

## Portability

No Linux-only call without a guard: playback tries sounddevice first everywhere, then `pw-play`/`paplay`/`aplay` only
on Linux, `afplay` on macOS, `winsound` on Windows; capture is sounddevice (PortAudio is bundled in its Windows and
macOS wheels; Linux uses the system's libportaudio) or `pw-record`/`parec` on Linux; `microphone()` asks sounddevice,
then `pactl` on Linux, else "can't tell". Subprocesses it starts are its own children, stopped by their exact pid.

## Not verified

Voice ID (0.8.10): the unit tests use fakes and synthetic data only (a fake embedder, fake banks, a fake microphone
and transcriber). The CAM++ models, kaldi-native-fbank's features, the enrolment session, the calibration and the
decision ran on real recorded speech through `tools/voiceid_eval.py` (above: LibriSpeech, every speaker); the impostor
banks are built by `tools/voiceid_bank.py` from the same data. Never run: a real microphone in a real room, Silero's
VAD on a live stream, a live voice, the Kokoro synthetic check, and anyone who isn't an audiobook reader.

Written against the published APIs of kokoro-onnx 0.4, piper-tts 1.2/1.3, faster-whisper 1.1, openwakeword 0.6,
Silero VAD v5 and sounddevice 0.5, but run only with fakes: no real microphone, speaker or model was used in the
tests or the build. Silero's v4 input names are handled too. The first real run should check `kurooto voice`,
`/health`, and a spoken "Kurooto, what's the time?".
