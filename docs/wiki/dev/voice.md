# Voice (`modules/voice/`, 0.8.8)

Kurooto speaks on the computer it runs on (Kokoro-82M by default, Piper as the lighter choice) and, with
`voice.listen.on`, listens to the room all day. Every decision about what it hears is made on the computer; only turns
the gate calls *addressed* reach the AI you picked, through the portal. Off by default (`Module` off until enabled),
with listening a second switch. User page: [../user/voice.md](../user/voice.md).

## Files

| File | What's in it |
|---|---|
| `modules/voice/__init__.py` | `Voice` (the module: settings, parts it wants, `hear()`, `ask_brain()`, the listener's lifecycle in `background()`, the API's `status()`/`say()`/`mute()`/`shape()`, `add_output()`, `/voice`), `Speaker` (speech a piece at a time, played by an output or the `Player`), `strip_wake()` |
| `modules/voice/names.py` | `NameMatcher`: its name as Whisper may spell it (`MISHEARD`, `voice.listen.name_variants`, `skeleton()` + `distance()` near misses); `called()`, `anywhere()`, `uncall()`, `kind()`, `call() -> Call(where, kind, greeted, rest)` |
| `modules/voice/gate.py` | `Gate.decide(Heard, Context) -> Decision`: the rules, then the local model, then the learned veto; `PROMPT`; `parse()`; `told_off()`, `features()`, `borderline()` |
| `modules/voice/learn.py` | (0.8.13) `Learner`: labelled turns (`record()`, flags and numbers only), the nightly fit (`train()`, logistic regression in plain Python), `veto()`, `status()`, `forget()` |
| `modules/voice/portal.py` | `Portal`: open/closed, `take(heard, decision)`, `tick()` (silence), `close(why)`, `context()` for the gate |
| `modules/voice/audio.py` | engines, all lazily imported: `Kokoro`, `Piper`, `Player`, `Mic`, `microphone()`, `Silero`, `Energy`, `Whisper`, `Wake`, `Listener`; (0.8.16) `backend()`, `pipewire_running()`, the stream-per-thread rules below |
| `tests/unit/test_voice_audio.py` | (0.8.16) a fake PortAudio that fails on any cross-thread or after-close use: stops racing the reader, reopening after a device loss, playback stopped from another thread, `pw-play`/`pw-record`/`parec` command lines, the recorder restarted |
| `modules/voice/parts.py` | what to fetch: `PACKAGES` (pip specs into `<app>/voice/py-<X.Y>`), `models()` (URLs and sizes into `<app>/voice/models`), `Parts.install()` |
| `modules/voice/shape.py` | the waveform outline: `estimate()`, `from_pcm()`, `levels()`, `clean()`, `spoken()`, `sentences()`, `join()` |
| `modules/voice/numbers.py` | numbers as words for the voice (`voice.speak.numbers_as_words`, 0.8.13): `say(text)` and its parts `words()`, `indian()`, `ordinal()`, `year()`, `number()`; pure Python, no dependency |
| `tests/unit/test_voice.py` | everything above with fakes (no device, no model) |
| `tests/unit/test_voice_numbers.py` | `numbers.say()` case by case, and the switch |
| `tests/unit/test_voice_listening.py` | (0.8.13) careful calls, the conversation window, told off, the learner, face assist, the talk carry |
| `modules/voice/fast.py` | (0.8.16) speed: `stamp()`, `numbers()`, `medians()`, `line()` (turn timing), `tone()` and `ACK_WORD` (the acknowledgement), `Stream` (speaking an answer as it's written), `chat_only()` and `FastPick` (`voice.listen.fast_brain`) |
| `tests/unit/test_voice_fast.py` | (0.8.16) timing, streaming (through the portal, Claude Code's stream-json with a fake program, an API's SSE through the queue), the acknowledgement, the fast brain, warm-up |
| `modules/voice/barge.py` | (0.8.13) barge-in: `Barge` (the listener's frames while it speaks, the echo's expected level, the voice and loudness-and-words checks on the `voice-barge` thread, its own voice print); `Voice.barge_turn()` handles what was said |
| `tests/unit/test_voice_barge.py` | (0.8.13) barge-in with synthetic voices, a fake clock, VAD and transcriber: own echo never stops it, the owner's voice does, told off, listen, loudness, the switch, an output's stop |

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

## Hooks for add-ons (0.8.12)

On `Voice` (`app.modules["voice"]`), both blocking: call them from the add-on's own thread, never the event loop.

- `listen_once(timeout_s=8.0) -> (text, embedding or None, speech_s) | None`: holds the listener for the next stretch
  of speech, any voice, no name needed. `_work_one` (the `voice-hear` thread) hands that stretch to `_take_once`
  instead of `hear()`: written out (`_write_out`), embedded with Voice ID's model when its parts are set up (Voice ID
  itself may be off; `voiceid.embed`, a list of floats), its speech seconds from the VAD flags; its outline still
  moves the waveform (`voice_heard`). It never reaches the gate, the portal, the AI, `heard` counts, the event log or
  the page's text. A stretch with no words is skipped and it keeps waiting. None when: Voice or
  `voice.addons.listen` off, `blocked()` (listening off, muted, paused, battery saver, a call, the night, enrolling,
  not set up), no running listener, the portal open or busy (never taken from your conversation), another holder
  (`_once_lock`, one at a time), or nothing said within `timeout_s` (at most 60; a stretch already taken gets up to 30
  s more to be written out). Mute or a block during the wait ends it at once.
- `guest_reply(text, name=None, history=None) -> str | None`: one chat turn through `core/guest.py:handle` with
  `speaker="guest"`, `speaker_by="addon"`: refusals for commands, actions and his things, `guest_per_hour`,
  `owner_only_at_all`, then an `audience="guest"` job (text only, no tools, none of his data; `guest_brain`). `name`
  goes into the prompt as "The visitor's name is ..." (letters, digits, `' . -` and spaces only, 40 chars); `history`
  is the add-on's own `(said, answer)` pairs, last 4 used, instead of Voice ID's `guest_turns` (the owner's
  conversation's guests never mix in). Waits like `ask_brain` (`_wait_job`), then `jobs.forget_guest`. None when Voice
  or `voice.addons.chat` is off or the text is empty.
- `say(text, wait=True)` (already there) speaks a scripted line.

## Outputs: playing the voice elsewhere (0.8.12)

`Voice.add_output(fn) -> remove()` lets an add-on play Kurooto's voice on another device instead of this computer's
speakers. `fn(pcm: bytes, sr: int, stop: threading.Event) -> bool`:

- **Called** by `Speaker._play` for each sentence's sound (16-bit little-endian mono PCM at `sr`), newest output
  first. It **blocks** until that sound has finished playing, or until `stop` is set, and returns `True` when it
  played it, `False` when it can't now; the next output is asked, finally the local `Player`. An exception counts as
  `False`, and is logged once per output as `voice_failed {part: "output", error}`.
- **Threading.** It runs on the speaking thread (`voice-say`, or the caller's with `wait=True`) inside
  `Speaker.lock`, so outputs are never called concurrently and sentences stay in order. `busy` is true the whole time,
  so `holding()` keeps the microphone held while the other device plays, plus the usual 0.4 s tail, exactly as for
  the `Player`. Registration takes a separate small lock, never held while sound plays: `add_output` and `remove()`
  are safe from any thread, and a change takes effect from the next sentence. `remove()` is idempotent and removes
  only its own registration (the same `fn` may be added twice).
- **Stopping.** `stop` is `Speaker._cancel`: `Speaker.stop()` (`/voice stop`, mute, Voice off) sets it, and the
  sentence loop ends; after a stop nothing falls back to the `Player`. It's cleared when the next utterance starts.
- **Unchanged:** `voice_speak` is published as each sentence starts, wherever it plays; `status()` still names the
  local player. The sound is handed over in memory only; the output must not write or keep it either.

## Auto gain (`audio.Gain`, 0.8.17)

`voice.listen.auto_gain` (on), `voice.listen.auto_gain_snr_db` (6). `Listener(gain=Gain(snr_db))`: while no stretch is
open, each frame with VAD < 0.35 updates the noise floor (an EMA over `NOISE_S` 4 s of its RMS); a stretch starts only
when VAD >= 0.5 *and* the frame's RMS >= `max(FLOOR, noise) * 10^(snr_db/20)` (`loud_enough`; nothing known yet: yes).
When a stretch ends, `Gain.level(pcm, flags)` scales it so its speech frames' RMS reaches `TARGET` (0.08), never
turning it down, at most `MOST` (8x) and never past 95% of full scale. VAD and barge-in see the raw frames; only the
stretch handed on (transcriber, Voice ID, gate) is levelled. `status()["auto_gain"]` shows `noise_db` and the last
`gain`. The system's microphone volume is never touched.

## Barge-in (`barge.py`, 0.8.13)

`voice.listen.barge_in` (on). Before it, `Listener` dropped every frame while `hold()` (`Speaker.holding() or
portal.busy`). Now `Listener(barge=Voice.barge)` asks `Barge.wants()` per frame first: true while
`Speaker.holding()` (speaking, plus its 0.4 s tail), and while a stretch that barged in (or has a check in flight)
goes on after it stopped. Then the frame and `vad.prob(frame)` go to `Barge.feed()` and the normal path never sees
it (the VAD is reset on the way in and out, the wake word buffer and pre-roll cleared). Off, or the portal busy only
thinking: the old drop. Nothing else in the listener changes.

- **What's played.** `Speaker._speak` calls `barge.speaking(pieces)` (their words, memory only, for the echo words
  check; it queues making its own voice print when the voice check can run) and `Speaker._play` calls
  `barge.played(pcm, sr)` as each piece starts, wherever it plays: per-32 ms RMS levels with the start time. Both
  only while the listener runs. `expected(now)` = the loudest level over `[now - ECHO_LAG_S (0.8 s), now + 0.05]`,
  which covers an add-on output's delay (a phone next to the laptop) and the room.
- **The echo's share.** Each speech frame (VAD >= 0.5) heard while something audible plays adds `level / expected`;
  `gain()` is the median of the last `GAIN_FRAMES` (125, ~4 s), needing `GAIN_MIN` (15). Not added while a stretch
  is confirmed. A frame is *loud* when `level > max(FLOOR 0.01, LOUD_X 2.5 * gain * expected)`.
- **Stretches** are cut as the listener does (start 0.5, 700 ms below 0.35 ends, 320 ms pre-roll, 15 s max), each
  with an id. A check is queued when the stretch has `MIN_SPEECH_S` (0.6 s) of speech or `LOUD_MIN_S` (0.3 s) of loud
  speech, again every `RECHECK_S` (0.5 s) more, one in flight at a time; when the stretch ends unconfirmed (with a
  check in flight or 0.3 s+ of speech), a final check of the whole of it.
- **`check()`**, on the `voice-barge` daemon thread (`sync = True` in tests runs it inline): (1) the voice, when
  Voice ID is on, has no `problem()` and its own print exists: `VoiceID.embed(pcm)`, `owner = dot(e, centroid)`,
  `itself = dot(e, own)`; barge when `owner >= thresholds(t).pick(speech_s).accept` and `owner - itself >=
  SELF_MARGIN` (0.10). (2) Else loudness then words: loud frames >= 0.3 s and >= half the speech frames, then
  `Voice._write_out(pcm)`; `words_ok()`: real words (not `made_up()`), a told-off phrase always, else fewer than
  `ECHO_WORDS` (60%) of them in what it's saying.
- **On a barge-in** the checking thread calls `Speaker.hold()` (0.8.17; it was `stop()`): the piece playing is cut
  (the `Player`, and the per-piece event an add-on output was handed, `Speaker._piece`) and the sentence loop waits in
  `Speaker.say_piece()`. `barge_turn()` then settles it: told off or a new turn -> `stop()`; anything else ("mm", no
  face) -> `release()`, and `say_piece()` plays the cut piece again from its start and goes on (event outcome
  `resumed`). Never settled within `HOLD_MAX_S` (12 s): it stops. It publishes `voice_state hearing, why "barged in"`. The stretch is still collected to its end,
  then `Voice._heard_audio(..., barge={"sid", "how", "score"})` queues it like any stretch (never blocking the
  listener); `_work_one` sends it to `Voice.barge_turn()`.
- **`barge_turn(pcm, flags, how)`** on `voice-hear` (after the interrupted `portal.take` has returned): written out;
  `_pending = None` (the interrupted turn isn't learned from); told off (with `voice.listen.told_off`) ->
  `_told_off()` (misfire, close); else the verdict: `how == "voice"` -> `Verdict(OWNER, "your voice, over its own")`,
  loud with Voice ID on -> `VoiceID.check(pcm, speech_s, adapt=False)` (never adapted from: its echo may be in it);
  `asks()` -> `portal.take(h, Decision(ADDRESSED, 0.9, "barged in"), text=uncall(text), who)` (the chat's context
  carries, as any turn); anything else -> `Portal.listen_on("barged in", who)` (open, `answered`, `last` and
  `spoke_at` now, so the follow window and `tick()` hold it for `follow_s`). Event `voice_barge {how, outcome}`
  (`voice`/`loud`; `told off`/`turn`/`listen`), never words. `status()["barge_in"] = {on, since_start}`.
- **Its own voice print**: `own_print()` synthesizes `OWN_PHRASE` with `Voice.tts()`, `voiceid.resample()` to 16 kHz,
  `VoiceID.embed()`; cached in memory per `(Voice._tts_key, VoiceID.model())`, never played or saved. No engine or
  no model: `[]`, and the voice check doesn't run (fail closed: only loudness).

## The flow

```
Mic (sounddevice | pw-record | parec), 16 kHz mono, 512-sample frames
  -> Listener (thread "voice-listen"): levels -> voice_level; held while Speaker.holding() or the portal is busy
       wake word (only with your own openWakeWord .onnx, 1280-sample steps) -> woke_at
       Silero VAD per frame: start >= 0.5, end after 700 ms < 0.35, max 15 s; 320 ms pre-roll (a deque in memory)
  -> Voice._heard_audio: queue (max 3, oldest dropped)
  -> worker thread "voice-hear": Voice.hear(Heard(speech, wake, seconds, ended_at), pcm)
       blocked()? drop.  Whisper.text(pcm) (CPU, int8; the assistant's name as initial_prompt and hotwords) -> del pcm
       Gate.decide(heard, portal.context())
       told off -> _told_off(); else face_check() (need_face: a face close and facing, or chatter)
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

0.8.13 additions (`Context` gained `speaker`, `speaker_score`, `faces`, `since_chatter_s`, `chatter_s`, `careful`,
`answered`, `same_speaker`, `follow_window_s`, `since_open_s`, `speaking`, `told_off`; `Voice._moment()` fills them
from the switches, `Speaker.holding()`, `core/nearby.py:view()` and Voice ID's verdict when it came before the words):

- **told off**, after 3: `told_off(text)` (the call taken off first; `_TOLD`, at most 12 words: stop / not you / I
  wasn't talking to you / shut up / be quiet / go away / never mind, with fillers; "stop the timer" and "never mind,
  what's ..." don't match) within `TOLD_S` (10 s) of `since_spoke_s` or of the portal opening (`since_open_s`), or
  while speaking -> chatter, why `TOLD_OFF`. `Voice._told_off()`: `Speaker.stop()`, `voice_misfire {rule, turn}`
  (`rule`: the portal's `opened_why`; `turn`: the last addressed turn's rule), a row labelled 0 (learn_nightly),
  `portal.close("told off")`, no reply. Only after `voice.listen.told_off`.
- **careful calls**, rule 4: when `ctx.careful` and `ctx.unconfirmed()` (speaker unsure/guest, chatter within
  `chatter_s`, or faces >= 2), its name counts only as `call.where == "first"`, `call.kind != NEAR`, and a greeting
  (`GREETINGS`, not "so"), nothing, or `asks(rest)` after it. Otherwise it falls through (`mention`), and rule 9's
  prompt gets a line saying a mention isn't a call. Not careful: rule 4 as before.
- **the conversation goes on**, after 6: `answered` (the portal's last words answered a turn; not after an `invite()`),
  `same_speaker is not False`, `since_spoke_s <= follow_window_s` (`voice.listen.follow_s`, 20; 0 off) -> addressed,
  0.8, statements too. In conversation mode only with `same_speaker` True (the voice that opened the talk and that it
  answered last: `Portal.opener`, `Portal.last_who`), replacing `conversation_follow_s`. Two voices end it (rule 6),
  as does any non-addressed stretch (it closes the portal).
- **the learned veto**, after all: `Gate(veto=Learner.veto)` (with learn_nightly) is asked about an addressed decision
  only when `borderline(d)`: rule 4 by a near miss, rule 7, the conversation going on, rule 9. True -> chatter, why
  `VETOED`. Never its name first with its own or a known spelling (the cap).

- **only someone in front of it** (`voice.listen.need_face`, after the gate, in `Voice.face_check(h, d)`; the gate
  itself knows nothing of faces): applies only while `Voice._face()` finds the switch on and Face presence on, enrolled
  and not needing re-enrolment. An addressed decision (any rule, and `barge_turn`'s "barged in"), except `FACE_FREE`
  ("the wake word") and "right after it was called" when the portal's `opened_why` is the wake word, needs a frame in
  `[ended_at - seconds - FACE_BEFORE_S (0.5), ended_at + FACE_AFTER_S (1.5)]` with `facing > 0`
  (`core/nearby.py:facing(app, since, until) -> (frames, frames_with_one)`). `Heard.ended_at` is stamped in
  `_heard_audio` (monotonic, when the listener handed the stretch over); None means "now". Before the window ends it
  polls every 0.1 s (`_face_sleep`); with no frame in the window at all it waits up to `FACE_SLOW_S` (2 s) longer for
  one. Frames but none close and facing -> chatter, why `NO_FACE` ("no one facing it nearby"), `face_counts.no_face`.
  `face_gate()` -> `("blind", pause_reason)` (Face presence paused, busy, covered ...) or no frame at all -> the
  fallback: `need_face_fallback` "voice" keeps the decision, "none" -> chatter, why `BLIND`, `face_counts.blind`. Told
  off is decided before this, so it never needs a face. `_not_to_it` keeps `feats`; the turn then takes the usual
  not-addressed path (dropped, closes the portal, counts as chatter for careful calls).
- **the hold**: `Voice.background()` calls `_face_hold()` each second: while listening (listener running, not
  `blocked_why`) and `_face()`, `Face.hold_watch(FACE_HOLD, FACE_HOLD_S=30, core=True)` renewed every
  `FACE_RENEW_S` (10 s); else, and in `_stop_listening`, `_face_release()` -> `release_watch(FACE_HOLD)`. `core=True`
  isn't subject to `face.addons.hold` ([face.md](face.md)). `line()` adds `face_line()`; `status()["need_face"]` has
  `{on, state, why, fallback, held, seen_s, no_face, blind}` (words and counts).

`Decision` carries `name` (exact/known/near), `where`, `careful` and `feats` (`features()`: rule, name flags, where,
voices, speaker, score, since_chatter_s, faces, careful; never words).

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
- (0.8.13) `kind(joined)`: `EXACT` (a name itself), `KNOWN` (a mishearing or variant), `NEAR` (fuzzy only). A span
  that is its own or a known spelling wins over a longer near miss ("Kurooto I need" was "kurootoi", a near miss, and
  swallowed the "I"). `call(text)`: where (first / last / middle), kind, `greeted` and `rest`.

`tests/unit/test_voice.py` lists mishearings that must match and ordinary words that must not (cool, auto, curry,
ghetto, kurt, router, kurta, karate, curator, Kyoto, Toronto, kettle ...). "cool auto" was dropped: it matched an ordinary phrase.

## The portal

`Portal.take()` with a non-addressed decision records the time (never the words) for the "talk nearby" count and
closes an open portal at once (`voice_state` `closed`, why `not addressed`). An addressed one opens it
(`Voice._portal_changed` logs `voice_portal {open, why}`), publishes `voice_text {who: "you"}`, `thinking`, calls
`send` (`Voice.ask_brain`), publishes `voice_text {who: "kurooto"}`, `speaking`, speaks, then `addressed` (waiting).
The name or wake word alone (`uncall()` leaves nothing) says "Yes?" (locally) and sets `awaiting`; nothing is sent. `tick()` closes after `close_s` of
nothing addressed (why `silence`). `close()` is also called on mute, block and `stop()`.

0.8.13: `opened_why`/`opened_at` (set on opening), `opener` and `last_who` (Voice ID's decision words for the turn
that opened it and the turn it answered last; "" with Voice ID off), `answered` (its last words answered a turn; reset
by `invite()`, a new turn and closing), `_chatter_at` (a non-addressed CHATTER, a time only: the gate's
`since_chatter_s`), `follow_s` (set by `Voice._moment()`). `tick()` holds `max(close_s, follow_s)` after an answer.
After an owner's turn is answered, `last_owner_at` moves to the end of the answer (`spoke_at`), so carry counts from
when Kurooto finished speaking, not from the question.

`Voice` keeps the last addressed turn as `_pending` (its row, session, decision word, any face-assisted vector) until
it's known how it went: the next addressed turn in the same session from the same decision word labels it 1
(`_went_well()`, and `VoiceID.learn_face()` for a face-assisted one); being told off labels it 0; a close drops it.

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
| `voice_speak` | `samples` (the piece's shape, `from_pcm`), `rate`: 50 | as each piece (a sentence, or short ones joined) starts playing |
| `voice_heard` | `samples`: at most 120 numbers 0..1 (`shape.envelope`: one per 20 ms of the stretch on the `voice_level` scale, fewer and wider buckets for a long one), `addressed`: `false`; nothing else, no words | a stretch that wasn't a turn (chatter, noise, not to it, or someone else dropped by Voice ID's gate), from `Voice._heard_wave` on the `voice-hear` thread, while a page is in sight (`voice.listen.levels`) |

Example: `{"t":"voice","kind":"voice_state","state":"thinking","portal":true,"listening":true,"why":""}`.

Logged events (`app.events.emit`, so also in the feed with `cell: "voice"` via `web/live.py:EVENT_CELL`), with no
words: `voice_portal {open, why}`, `voice_listening {on, why}`, `voice_mute {on}`, `voice_failed {part, error}`,
(0.8.13) `voice_misfire {rule, turn}`, `voice_learned {rows, good, misfires, active}` and `voice_barge {how,
outcome}`; (0.8.16) `voice_timing {text_ms, gate_ms, face_ms, sent_ms, start_ms, first_text_ms, answer_ms, ack_ms,
audio_ms, play_ms, streamed, fast}` (only those that happened) and `voice_warm {part, ms}`.

## Speed (`fast.py`, 0.8.16)

The owner's measured turn before this: last word to first sound about 7 to 8 s (Whisper base 0.7 s, gate and Voice
ID 0.6 s, Claude Code at low effort 4 s, then Kokoro and an add-on output on a phone). What changed:

- **Timing** (`voice.listen.timing`). `hear()` and `barge_turn()` make a turn dict `{"end": h.ended_at}`; `stamp()`
  records the first time of each step: `text` (written out), `gate` (decided, after `face_check`; `face_ms` is the
  face check's own time), (0.8.17) `taken` (just before `app.handle`) and App.handle's own marks via
  `Incoming.timing` / `Incoming.mark()` (`mind` after Brain's hooks, `addon_intents` after `overlay.classify`,
  `intents` after Kurooto's own patterns; only a spoken turn carries `timing={}`), `sent` (after `app.handle` returned: queued), `start` (the queue's `on_start` hook, before
  `brain.run`), `first_text` (the first finished sentence from a stream, else the answer), `answer`, `ack`, `audio`
  (the first piece synthesised: `Speaker._speak` or `Stream._run`) and `play` (`Speaker._play`, just before an output's
  fn or the `Player` gets the piece). `Voice._take()` wraps `portal.take` (it sets `_turn_t` for `ask_brain` and
  `_portal_speak`, which hands it to `Speaker.turn`), then `_timed()` emits `voice_timing` (ms from `end`) and keeps the
  row in `timings` (20, memory). `speed()` / `fast.medians()` give the medians: `status()["speed"]` and the `/voice`
  line. `face_check` already returns at once when a qualifying frame is in the window (during the stretch included);
  it waits (at most FACE_AFTER_S, FACE_SLOW_S with no frame at all) only when none is there yet, and `face_ms` shows it.
- **(0.8.17) Routing by voice** (app.py): `repair.readings`/`helper.pick`/`repair.offer` and `turnon.offer` are skipped
  for `via == "voice"` (button offers; the helper's pick could wait up to `local_helper.timeout_s`). **First clause**
  (`fast.Stream.feed`): while nothing is queued yet and no sentence has ended, a `,;:` boundary at least `CLAUSE_MIN`
  (20) characters in is queued, so speech starts before the first sentence is written out.
- **(0.8.17) Early** (`voice.listen.early`, `fast.Early`). `Listener(early=...)`: `spoke` tracks buf's length at its
  last non-quiet frame; when quiet reaches `audio.EARLY_MS` (300) once per `spoke`, `early.pause(prefix, flags)`
  (levelled by `Gain` like the final stretch) queues it for the `voice-early` thread, which runs
  `Voice._early_text` (Voice ID's gate first: not the owner with no portal open -> None, never written out) and sets
  `end_ms`: 350 for text ending "?", 550 for ".", "!" with 3+ words. Each quiet frame asks `early.end_ms(spoke)` for a
  sooner end than `END_MS`. `hear()` calls `early.take(audio, flags)` before `_write_out`: the early words when the
  stretch is the prefix plus frames with no speech flag, waiting up to `WAIT_S` for a job in flight; else None and the
  whole stretch is written out. `on_start` (`_stretch_start`) and a newer pause mark the older job stale.
- **Acknowledgement** (`voice.speak.ack`: `tone`, `word`, `off`). `ask_brain` calls `_ack(turn)`; only while a
  listener runs (a heard turn), with speaking on. A `voice-ack` thread waits `ACK_WAIT_S` (0.25 s), skips when the
  turn has `first_text`/`answer` or the speaker is holding, then `Speaker.ack(pcm, sr, turn)`: a non-blocking take of
  the speaker's lock, `busy` while it plays through `_play` (outputs first, the `Player` last; `barge.played` sees it),
  the 0.4 s tail after. `tone()`: 0.24 s at 24 kHz, a G4 gliding up a fourth with a sub-octave at a quarter level,
  sin² attack over 12% and a (1-t)^1.6 fall, peak about -20 dBFS, zero at both ends. `word`: `ACK_WORD` ("Hmm.")
  synthesised once per `_tts_key` (kept in `_ack_sounds`), the tone when the engine can't. The tone is the default:
  Kokoro reads a word alone with a hurried, flat tune (the reason for `join_sentences`), and the tone needs no engine.
- **Streaming** (`voice.speak.stream`). `_turn_opts()` makes a `fast.Stream` and passes `on_text=stream.feed` and
  `on_start` through `app.jobs.turn_options()` around `app.handle(msg)` (core/jobs.py; the first `submit()` on the
  thread). If no request was queued, or not the one `msg.job` names, the stream is cancelled. `feed(key, text so far)`
  queues everything up to the last sentence end (`BOUNDARY`: `. ! ?` and whitespace, or a line break) that isn't
  inside a code fence, as `shape.sentences()` pieces, within `max_chars` (then "The rest is on screen."). A new key is
  a new message (the words before a tool call, or a stand-in AI's try). The `voice-stream` thread holds the speaker's
  lock and plays piece by piece, synthesising the next while one plays; it joins what's waiting (120 characters for
  the first piece, 200 after, with `join_sentences`) and is `busy` only while it has something to say, so while it
  waits for more words the microphone stays held by `portal.busy` as before (no barge-in into silence).
  `_portal_speak(answer)` calls `finish(answer)`: `left()` is the answer after the streamed prefix of the last
  message, else its sentences not said yet; it waits for the thread. `_wait_job` stops waiting when the stream was cut
  (stop, mute, barge-in) and the answer shown is what was said. With streaming on, every owner answer is spoken by
  `Stream` (a brain that can't stream fills it at the end); guests and greetings use `Speaker.say` as before.
- **Fast brain** (`voice.listen.fast_brain`: `same`, `local`, `fastest`). `_fast_choice()`: only when
  `fast.chat_only()` (no `/`, at most 240 characters, none of `NEEDS`' words, and `core/guest.py:kind()` finds no
  request of Kurooto's) the turn options get `brain`, `text_only=True`, `effort="low"`. `local`: `providers.local()`.
  `fastest`: `FastPick.pick()`: candidates (the main AI if it's an API, a ready Gemini key, the local model, the main
  agent program held to text: no tools and no MCP servers), each tried once, then the lowest median of `first_text -
  sent` over its last 5 turns (memory). The request still goes through the queue (receipt, history, fallbacks).
- **Warm-up** (`voice.listen.warm_up`, `voice.listen.warm_brain`). `_start_listening()` ends with `_warm()`: a `WARM`
  item on the hearing queue (`_work_loop` runs `_warm_stt()`: 0.5 s of silence written out, so never beside a turn),
  `_warm_voice()` on a thread (one word synthesised under the speaker's lock, never played; the ack word too), and,
  at most every `WARM_BRAIN_S`, `_warm_brain()`: `claude --version` for Claude Code (its files into the page cache;
  no request), or one local completion with `fast_brain` `local`. Each engine key is warmed once (`_warmed`).
  `tts()` loads under `_tts_lock` so the warm-up and a turn never load it twice.

## Live at the desk (`live.py`, 0.8.17)

`voice.listen.live` (off). An owner's admitted turn is answered by Gemini Live (speech to speech) instead of
`app.handle` + Kokoro. The hooks in `__init__.py` are narrow:

- `hear()` calls `live.keep(audio, who)` just before `del audio` on the addressed path (`barge_turn()` the same before
  its `_take`): the stretch is kept, in memory, only when the switch is on and `who.decision == "owner"` (Voice ID on).
  `_take()`'s `finally` calls `live.keep(None)`: it's dropped whatever happened.
- `_timed_face_check()` sets `turn["faced"] = 1` only when `face_check()` returned through its `ok` branch (a face
  close and facing it in the window, `nearby.facing`). Turns let through without a face (FACE_FREE: the wake word and
  the request right after it; `face_gate()` "off" or "blind" with fallback "voice") have no `faced`, so never go to Live.
- `ask_brain()`: for an owner's verdict, `live.turn(text, turn)` first; a string is the answer (said already), `None`
  falls through to the usual path (so the ack, streaming and fast brain are untouched).
- `_portal_speak()` returns at once when `live.spoken()` (the portal would otherwise say the reply again).
- `_portal_changed(False)` calls `live.close()` (never waits): the portal closing ends the session.

`Live.turn()`: needs the stretch, `turn["faced"]`, the switch, `speak.on`, not `portal_cut()`, a `gemini.api_key`
and the calls module. A session (`Session`) is reused while `sess.portal == portal.session`; else `_open()` tries
`models()` (`Calls.live_models()` minus `calls.live.gone()`, models that failed in the last `BAD_S` last) with
`setup()`: `Calls.config_template()` as the raw `BidiGenerateContentSetup` (`models/<m>`, `generationConfig`
{responseModalities AUDIO, speechConfig from `calls.voice` or `live_profiles()`' voice}, `systemInstruction.parts`,
the tools' declarations without `behavior` (blocking: a turn waits for its tools), both transcriptions,
`contextWindowCompression`, and `automaticActivityDetection.disabled`: Voice already cut the turn). `desk()` fills
`%%NOW%%`, swaps "on a live voice call" and "Talk like a friend on a call", drops lines with "every call"
(pending_items' hint) and adds `DESK`. The websocket (`websockets.asyncio.client.connect`) runs on its own loop thread
(`voice-live`); the key is sent as the `x-goog-api-key` header, never in `LIVE_URL`, and the library's logger is a
silenced one (`_log`). `egress.allow(LIVE_URL, "Voice")` counts it (generativelanguage.googleapis.com, already listed).

A turn: `activityStart`, the PCM in 250 ms `realtimeInput.audio` messages (`audio/pcm;rate=16000`), `activityEnd`;
`sent` stamped. `_read()` (a task per session) hands the turn's queue `audio` (24 kHz PCM), `in`/`out`
(transcriptions), `tool`, `interrupted`, `done` (turnComplete) and `closed`. `_first()` waits `FIRST_S` (5 s; a tool
call restarts it) for the first sound, else `Failed("first sound")`. `_play()` holds the Speaker's lock like
`fast.Stream._run` (`busy`, `_turn = turn` so `_play` stamps `play`), and plays pieces with `Speaker.say_piece(pcm,
24000)` (0.2 s first, then 0.6 to 2 s): outputs, `voice_speak` samples, hold/release and stop work as for Kokoro's
pieces; the output transcription goes to `barge.speaking()`. Live's `interrupted` calls `speaker.stop()` from the
reader. An answer cut off before its turnComplete marks the session `stale`: the rest is dropped as it arrives
(`swallow` drops a turnComplete that follows an `interrupted`). Tool calls: `Live.run_tool()` on an executor: a tool
`tap.action_of()` calls guarded goes to `tap.ask_first(via="voice")` (Approve / Deny; runs only on Approve), any other
through `Calls.run_tool()`; the result goes back in `toolResponse.functionResponses`.

After the answer: `turn["live"] = 1` (`fast.numbers` passes it to `voice_timing`), `answer` stamped,
`chat.record_turn(input transcription or the written-out words, output transcription)` while Chat is on, and the reply
text (or `ALOUD`) returns to the portal, which shows it. Any exception: the session is closed, the stamps Live added
are taken off the turn, a `voice_live` event (stage, model, code, ms; never words) and `None`: the usual path answers.
Events: `voice_live` with `stage` `answered` (`turns`), or `connect`/`setup`/`send`/`first sound`/`no key`/`no calls`/
`error` (`fallback: true` when that turn went the usual way).

Not verified against Google: the raw v1beta setup shape for the configured models, the `x-goog-api-key` header on the
websocket, manual activity with a pre-cut stretch, and whether `interrupted` is followed by a turnComplete
(tests/unit/test_voice_live.py runs a fake server on 127.0.0.1).

## Learning at night (`learn.py`, 0.8.13)

`voice.listen.learn_nightly` (on). Rows in `<state>/voice/gate-turns.jsonl`, one JSON object per labelled turn:
`learn.KEYS` (rule, name_exact, name_near, where, voices, speaker, score, since_chatter_s, faces, careful) + label +
day, passed through `clean()` (unknown keys dropped, rules outside `RULES` become "other"). Voice ID's score is stored
here, rounded to two decimals, in local state only (never an event or the live stream); `VoiceID.forget()` deletes the
rows and the model. `ROWS_MAX` 2000 kept.

`Voice.start()` schedules `voice:learn` at `NIGHT_AT` (daily 04:10, after the mind's fine-tune at 03:40) with
`thread=True`. `Learner.train()`: below `MIN_ROWS` (20) or fewer than `MIN_EACH` (3) of either label -> saved with
`active: false`. Else `fit()`: logistic regression over `vector()` (bias, rule one-hot, name flags, where, two voices,
speaker one-hot, score, exp(-since_chatter/30), one face, two faces, careful), batch gradient descent, class-balanced,
L2 0.05, 600 steps. `<state>/voice/gate-model.json`: weights, counts, the training fit, how many misfires and good
turns it would have held back. `veto(feats)`: chance < `VETO_P` (0.25). `status()` (numbers) goes into
`Voice.status()["learned"]`, `Voice.line()` (so `/health`) and `/voice`.

## API (`web/api.py`)

| Route | Body | Answer |
|---|---|---|
| `GET /api/voice` | | `Voice.status()`: `on, state, portal, listening, why, muted, blocked, line, speak {on, engine, voice, rate, what, player, speaking}, listen {on, wake_word, stt_model, close_s, night, calls, microphone}, engines {kokoro, piper, whisper, vad, wake}, missing, missing_gb, heard {noise, chatter, addressed}, choices {voices, stt_models}`; (0.8.13) `learned {rows, good, misfires, active, trained, fit, vetoes, recorded, on, misfires_now}` and `speaker_id.face_learned` (numbers only) |
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

### Pieces, not single sentences (0.8.13)

`Speaker._speak` used to synthesise each sentence alone. Kokoro picks its style vector by the number of phonemes
(`voices[name][len(tokens) - 1]`) and a few words alone come out hurried and flat. With `voice.speak.join_sentences`
(default on) `shape.join()` packs consecutive sentences into pieces of at most 200 characters (120 for the first, so
the first sound is ready about as soon as before), after `max_chars` has cut the answer; a line with no closing mark
gets a full stop so a list item still ends. Inside a piece the model makes its own pause at each full stop (about
0.1 s: Kokoro v1.0's ONNX export has no duration output, so kokoro-onnx can't top those up). `Voice.shape()` joins the
same way. Outputs (`add_output`) get a piece per call instead of a sentence; the sample rate is unchanged. Sentences
longer than 220 characters are still split at commas by `sentences()`; `join()` never cuts.

Between pieces, `pause_after(tts, piece, sr)` appends silence to every piece but the last (and in `Voice.shape()`'s
engine path): kokoro-onnx's `create()` trims leading and trailing silence (`trim=True`, librosa's 60 dB trim) and adds
`sentence_pause` 0.25 s or `clause_pause` 0.1 s only between batches of one call, so separate calls ran together. The
same values are used: 0.25 s after `. ! ?`, else 0.1 s. Piper keeps its silence and gets none. The pause is part of
the PCM, so outputs, `voice_speak`'s shape and `holding()` all include it.

The sample rate is Kokoro's own (`kokoro_onnx.config.SAMPLE_RATE`, 24000) from `Kokoro.create()`, passed unchanged
from `Kokoro.synth` through `_play` to each output and the `Player` (pw-play `--rate`, paplay, aplay, sounddevice,
WAV headers); nothing resamples it on the way out. (Voice ID's synthetic impostors resample a copy to 16 kHz for the
embedder only.)

### Numbers as words (0.8.13)

Kokoro's pronunciation comes from espeak-ng, which reads digits literally ("21:31" → "twenty one : thirty one",
"0.8.13" → "zero. eight point one three", "₹3,000" → "rupee three thousand", "12 GB" → "gee bee"). With
`voice.speak.numbers_as_words` (default on) `shape.spoken(text, numbers=True)` runs `numbers.say()` after `clean()`
and before the text is split into sentences, so "a.m." no longer ends a sentence. It's applied to the speech engine's
input (`Speaker._speak`) and to both shape paths (`Voice.shape`: the engine's and the estimate's), never to
`voice_text` or anything shown. Passes in order: dates, versions, ranges, times, money, percentages, decades, units,
"/month", ordinals, years, fractions, ratios, "1920x1080", "±", minus signs, letters joined to digits, then any number
left. Each pass only touches a number standing on its own (`LEFT`/`RIGHT`: not inside a word, a decimal or a
code-like token), so `7c12897`, `x86_64` and `0x1F` stay as written. AM and PM are written `A-M`, `P-M`: espeak reads a
bare "AM" before a full stop as the word "am". Years: 1900 to 2099 always, 1100 to 1899 after a year word (in, since,
by ...) or a month. Indian commas (`1,00,000`) are read in lakhs and crores. Check a reading with the Kokoro
tokenizer's `phonemize(text, "en-us")` (phonemes only, no sound).

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

0.8.13, in the >= unsure band only and never in strict: `face_assist` and `ctx.face_owner` (`VoiceID.face_owner()`:
`nearby.view()` says one face, the owner's, at most `VIEW_S` 5 s old; set from Face presence's watcher `view` emit
each frame, cleared when the camera closes) -> owner, `FACE_WHY`, `assisted`; `carry_talk` and `ctx.portal_open` and
the same session and within `carry_talk_s` (`max(carry_s, listen.follow_s)`) of `last_owner_at` -> owner, `TALK_WHY`,
`carried`. Rules come from `VoiceID.rules()` (`voice.speaker_id.face_assist`, `carry_talk`).

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

0.8.13: `consider(..., face=True)` takes a face-assisted owner verdict with score >= the stored `long.unsure` instead
of accept + 0.08 (the other checks the same); the entry is marked `face: true` (counted in `status()["adapt"]["face"]`).
`VoiceID.check()` keeps such a turn's vector in memory (`_face_last`); `Voice` holds it with the turn and calls
`learn_face()` only when the turn went well (adapt and face_assist on); told off or closed, it's dropped.

### Storage

`BioStore(app, "voice")`: `state/voiceid/template.bin` (0600 in a 0700 folder), `nonce || AES-256-GCM(json)` with AAD
`kurooto-biometric:voice:v1`, key `biometric.voice.key` (secrets; made on the first save and read back; never a new
key over an existing file: `Locked`). JSON: model, model_sha256, mic, dates, `samples [{e, s, cond, day}]` (base64
float16), `adapted [{e, day}]`, `centroid`, `centroid_enrolled`, `thresholds`, `calibrated`, `genuine`, `report`,
`last_test`, `drift_stopped` (0.8.13: an adapted entry may carry `face: true`). Kept out of backups (`SKIP_STATE_DIRS`, and `known_secret_names` drops the key), profile
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

## Sound streams and threads (0.8.16)

The crash: 0.8.10 to 0.8.15 died with SIGSEGV in `snd_pcm_poll_descriptors_revents` / `snd_pcm_status` (libasound,
under libportaudio's blocking read, called from a Python thread through cffi), and once with SIGABRT "corrupted
double-linked list". `Listener.stop()` ran `Mic.close()` on the caller's thread (the asyncio loop, or enrolment), which
did `stream.stop(); stream.close()` while the `voice-listen` thread sat in `stream.read()`: PortAudio freed the ALSA
PCM under the read. Crash addresses like `0x100` and `0x10` are calls through the freed PCM's function table.

The rules now:

- **One owner per stream.** The thread that iterates `Mic.frames()` opens, reads and closes the PortAudio stream (or the
  recorder child). `Player.play()` opens, writes and closes its own `RawOutputStream`, one per sentence, under
  `Player._lock`. Nothing else touches them.
- **Stopping is a flag.** `Mic.close()` and `Player.stop()` set an event; from another thread they only `terminate()` a
  child process (by its own pid), which is safe because no native code is shared. `Listener.stop()` then joins the
  reader for up to `JOIN_S` (0.5 s) so the next Listener doesn't open the device while the old one holds it, and
  `Listener._run` closes the frames generator on its own thread in `finally`.
- **No blocking PortAudio calls on our threads for input.** The microphone runs in callback mode: PortAudio's thread
  puts frames on a queue (`QUEUE_FRAMES`, oldest dropped), and the reader takes them with a 0.1 s timeout, so it sees a
  close at once. Output writes 50 ms pieces (`PLAY_CHUNK_S`) and checks the flag between them; `sd.play()`/`sd.stop()`
  (one module-wide stream) are no longer used.
- **Reopen, don't die.** A stream that goes inactive or sends nothing for `STALL_S` (3 s), or a recorder that exits by
  itself, is closed by its owner and opened again after `REOPEN_S` doubling to `REOPEN_MAX_S`; `Mic.reopened` counts
  it. The first open failing raises at once (Voice reports it and retries after `RETRY_S`), and `REOPEN_TRIES` (6)
  tries in a row without sound raise "the microphone stopped sending sound".

`voice.audio.backend` (`auto` | `pipewire` | `portaudio`): `backend(choice, device)` makes it concrete. `auto` is
`pipewire` when `pipewire_running()` (Linux, `pw-play` and `pw-record` on PATH, the user's `pipewire-0` socket under
`PIPEWIRE_RUNTIME_DIR`/`XDG_RUNTIME_DIR`, or `PIPEWIRE_REMOTE`) and `voice.listen.device` is empty, since that setting
holds sounddevice's names; else `portaudio`. Why PipeWire's tools by default: the race was ours, but PortAudio's ALSA
host API over PipeWire's ALSA plugin is the one place native audio code ran in the daemon, and it's exposed to every
graph change (EasyEffects, an add-on's pipe-source loading and unloading). With `pw-record`/`pw-play` a driver fault
kills a child, which is restarted; PipeWire also relinks the recorder to the new default source by itself. The cost is
one `pw-play` start per sentence (tens of ms). PortAudio's PulseAudio host API wasn't an option: no released
PortAudio has it (Arch's 19.7.0 is built with ALSA only), so sounddevice can't pick it.

Command lines: `pw-record --raw --format s16 --rate 16000 --channels 1 --latency 32ms [--target <node>] -`;
`parec --raw --format=s16le --rate=16000 --channels=1 --latency-msec=32 [--device=<node>]` when `pw-record` is
missing; `pw-play --raw --format s16 --rate <sr> --channels 1 --latency 50ms -` fed in 4 KB pieces so a stop isn't
stuck behind a whole answer in the pipe. A target is passed only with `pipewire` chosen by name. The `Speaker` makes a
new `Player` when the setting changes; a new `Mic` takes it when listening next starts.

## Portability

No Linux-only call without a guard: with `voice.audio.backend` `auto` (0.8.16) Linux with PipeWire plays through
`pw-play` and records through `pw-record`; otherwise playback tries sounddevice first everywhere, then
`pw-play`/`paplay`/`aplay` only on Linux, `afplay` on macOS, `winsound` on Windows; capture is sounddevice (PortAudio is bundled in its Windows and
macOS wheels; Linux uses the system's libportaudio) or `pw-record`/`parec` on Linux; `microphone()` asks sounddevice,
then `pactl` on Linux, else "can't tell". Subprocesses it starts are its own children, stopped by their exact pid.

## Not verified

0.8.16 (sound streams and threads): unit tests with a fake PortAudio and fake child processes only. The crash's cause
was read from the core dumps' native stacks (no Python frames: the interpreter has no debug symbols) and the code, not
reproduced. `pw-play`'s arguments were checked against PipeWire 1.6's `pw-cat` (an unlinked silent run parsed them);
`pw-record --raw ... -` writing raw samples to stdout, its 32 ms latency, and the reopen timings were never run
against a real microphone, and no speaker was used.

0.8.13 (careful calls, the conversation window, told off, the learner, face assist, the talk carry): unit tests with
fakes only. Not run with a real room, real Face presence frames feeding Voice ID, or a night's real fit.

Barge-in (0.8.13): unit tests with synthetic voices (FakeEmbedder markers), a fake clock, VAD and transcriber only.
Never run: a real room's echo (speakers or a phone next to the laptop), CAM++ on a stretch with its own voice mixed
in, Kokoro's own voice print through CAM++, and the constants (`SELF_MARGIN`, `LOUD_X`, `ECHO_LAG_S`) against real
sound; they're first guesses to tune from the owner's room.

Voice ID (0.8.10): the unit tests use fakes and synthetic data only (a fake embedder, fake banks, a fake microphone
and transcriber). The CAM++ models, kaldi-native-fbank's features, the enrolment session, the calibration and the
decision ran on real recorded speech through `tools/voiceid_eval.py` (above: LibriSpeech, every speaker); the impostor
banks are built by `tools/voiceid_bank.py` from the same data. Never run: a real microphone in a real room, Silero's
VAD on a live stream, a live voice, the Kokoro synthetic check, and anyone who isn't an audiobook reader.

Written against the published APIs of kokoro-onnx 0.4, piper-tts 1.2/1.3, faster-whisper 1.1, openwakeword 0.6,
Silero VAD v5 and sounddevice 0.5, but run only with fakes: no real microphone, speaker or model was used in the
tests or the build. Silero's v4 input names are handled too. The first real run should check `kurooto voice`,
`/health`, and a spoken "Kurooto, what's the time?".
