# Face presence (`modules/face/`, 0.8.10)

Kurooto recognises its owner's face with OpenCV's YuNet (detection) and SFace (recognition), on the CPU, on this
computer only, and greets him by voice when he sits down after an absence, then opens Voice's conversation
(`Portal.invite`). Off by default (a module); nothing watches until he enrols on the dashboard's Face page. User page:
[../user/face.md](../user/face.md). Design: `build-specs/0.8.10/face.md` (outside the repo).

**The rule above all others: a face match never authorises anything.** It isn't one of `core/tap.py:WAYS`, never
answers an approval, unlocks anything or widens a voice turn. `tests/unit/test_face.py:test_a_face_never_authorises_anything`
checks that `core/tap.py`, `core/ask.py` and `core/tools.py` never read the face module.

## Files

| File | What's in it |
|---|---|
| `modules/face/__init__.py` | `Face(Module)`: settings (`register_defaults("face", ...)`), parts, the template cache, `pause_checks()`/`pause_reason()`, the watcher's thread (`_run`, `tick`, `background`), `_on_watch` (events), the greeting (`greet`), learning, the sessions (`enrol_start`, `train`, `test_start`, ...), `forget`, `turned_off`, `status()`/`card()`/`/face`/intents; `button()` for the core `fce` prefix |
| `modules/face/parts.py` | `FACE_PACKAGES` (`vision`: opencv-python-headless, numpy; module `cv2`), `face_models()` (pinned URLs and sha256), `parts(app)`: Voice's `Parts` with `root=<app>/voice` (one shared `py-X.Y`) and `models_dir=<app>/face/models` |
| `modules/face/camera.py` | `Camera` (open/read/close, per-OS backends), `devices()`, `pick()`, `holders()` (Linux busy), `windows_busy()`, `CameraError(why)` |
| `modules/face/vision.py` | `Face(box, landmarks, score)`, `Stats`, `Pose`, the `Detector`/`Embedder`/`Frames` protocols, `pose()`, `moved()`, `opencv_detector()`, `opencv_embedder()`, `opencv_frames()` (cv2 imported only inside) |
| `modules/face/enrol.py` | `PLAN`, `Step`, the quality limits, `Enrolment` (pure: progress, `act()`, `judge()`), `shape()`, `Session` (camera, preview, timeouts, test marks) |
| `modules/face/model.py` | `Sample`, `centroids()`, `score()`, `folds()`, `held_out()`, `train()`, `Template` (payload, `classify()`, `retrain()`, `learn()`, `undo_learn()`, `forget_learned()`) |
| `modules/face/watch.py` | `Watcher` (pure: injected clock, idle, locked, camera, models, classify, pause reasons, emit), `PAUSES` |
| `modules/face/greet.py` | `compose()` (rules, ≤ 220 characters), `may_greet()` |
| `core/biometric.py` | `BioStore(app, feature)` (key, seal, unseal, save, load, forget, `Locked`), `calibrate()`, `load_impostors()`, `npz_read`/`npz_write` (numpy's format without numpy), `BIOMETRIC_SECRETS`. Shared with Voice ID |
| `core/nearby.py` | "others nearby": `set_others(app, source, on)`, `others(app)`; Face sets it, Voice (ID) can read it. The watcher sends `others on` with every frame while a second face is in view (nearby drops a signal older than `STALE_S`, 120 s), and the event only when it changes |
| `web/static/face.js` | the Face page (`FACE.mount`, `FACE.live`), loaded on demand by `home.js:renderFace` |
| `tools/face_impostors.py` | the maintainer's impostor-set builder (never at install) |
| `tests/unit/test_face.py`, `tests/unit/test_biometric.py` | everything with fakes |

## Changes elsewhere

- `modules/voice/parts.py`: `ModelFile.sha256` (checked after download; a mismatch deletes the `.part`), `Parts(root,
  app_dir, packages=None, table=None, models_dir=None, feature="Voice")`, `Parts.install_from(folder, keys, progress)`.
  Voice's behaviour is unchanged.
- `modules/voice/__init__.py`: `Voice.greet(text, listen_s, talk=True) -> (spoken, "talk" | why)`; `_job_done` doesn't
  read answers aloud while `app.away_from_desk()` with `face.away.hold_desktop`.
- `modules/voice/portal.py`: `Portal.invite(text, hold_s)`.
- `core/calm.py`: reasons `face.greet` (`counted=False`, `later=False`, `feature="face"`) and `face.off` (exempt);
  `Calm.speak_ok(why, about)`.
- `core/tap.py`: `GUARDED["camera.open"]` (ways: button), `data.delete`'s where, `BUTTONS["fce"]`.
- `core/egress.py`: `media.githubusercontent.com`. `core/notify.py`: `Notifier._desktop` (held while away).
- `app.py`: `App.away_from_desk()`, the core `fce` button. `core/retention.py`: `/forget all` forgets the face model.
- `core/profile.py:NEVER`, `modules/backups.py` (`SKIP_STATE_DIRS` + `face`, `backup_secret_names()` leaves out
  `BIOMETRIC_SECRETS`), `diagnostics.py` (`KNOWN_SECRETS` + `face.key`; `face.json` in the bundle: on, enrolled,
  samples, set up).
- `web/api.py` (`face` in `MODULE_ORDER`, `GET face`, `POST face/...`, `face_frame()`), `web/server.py` (`GET
  /api/face/frame`), `web/live.py` (`EVENT_CELL` `face_`; `today_items(app)` factored out of `Vitals._today`),
  `web/static/home.js` (`TABS`/`DLABEL`/`PKEY` `face` (Alt+E), `renderFace`, the live `t === "face"` branch and the
  "● camera" badge), `web/static/being.js` (`face_*` → `see` and the `face` feature, sight's nerve and pupil).
- `core/commands.py` (`Group("face", ...)`), `cli.py` (`kurooto face ...`), `modules/catalog.py`.

## The pipeline

```
Camera.read()  (BGR, 640x480 asked; one grab() first; CAP_PROP_BUFFERSIZE 1)
  Frames.mean(frame) < 8 for 10 frames -> "camera covered"
  Detector.detect(frame, 0.6)   YuNet on a 320-wide copy; boxes and 5 landmarks scaled back; NMS 0.3
  for each face, score >= 0.8 (0.9 enrolling) and height >= face.recognise.min_face_px:
      Embedder.align(frame, face)   FaceRecognizerSF.alignCrop -> 112x112
      Embedder.stats(crop)          grey: variance of the Laplacian, mean, share >= 250
          lenient (watching): blur >= BLUR_MIN / 2, 30 <= mean <= 225, else ignored
      Embedder.feature(crop)        128 floats, L2-normalised, a Python list
      Template.classify(e)          owner (>= T_hi) | unsure (>= T_lo) | stranger
  del frame, crops; a stranger's or unsure face's numbers are dropped at once
```

Backend and target are set explicitly (`DNN_BACKEND_OPENCV`, `DNN_TARGET_CPU`). The watcher uses 1 thread
(`cv2.setNumThreads(1)`), enrolment 4. Measured on the owner's CPU (spec §2, synthetic input): YuNet at 320x240 about 9
ms on 1 thread, SFace about 30 ms per face: under 5 % of a core at 1 frame a second.

The maths is pure Python on lists (`core/biometric.py:dot`, `mean_unit`): numpy isn't in Kurooto's own install, and
the sizes (≤ 3 centroids × 5,000 impostors × 128) take well under a second.

## The watcher (`watch.py`)

States: `off`, `paused(why)`, `resting` (camera closed, input is presence), `watching` (camera open), `away`.

`tick()` (every 0.25 s from the thread `face-watch`; `Face.background` only keeps the thread alive and stops it):

1. A clock jump of more than 30 s (a sleep) or an unlock opens a 10 s "woke" window. Locked: idle isn't read.
2. Input (idle < 2 s, unlocked) is presence: `_input()`; a gap since `present_at` of ≥ `greet.after_absent_min`
   starts a *return* (`returning = {since, gap}`), which waits 30 s for his face. Input ends `away` ("back").
3. Away (`away.on`): no presence for `away.after_min` while unlocked and watching, or locked that long → "left".
4. `paused()` (the module's `pause_reason()`) or a camera problem: close, state `paused`.
5. The camera is wanted when idle ≥ `watch.idle_s`, or locked with `watch.when_locked` on, or (woke, confirming a
   return, or already open while idle can be read) within 6 s of input becoming active, or an add-on holds it
   (`held()`, below; step 4 has already passed). Otherwise it closes (`resting`).
6. A frame is due at the rate: `watch.fps` (`fps_battery` on battery), 2 fps for 5 s after the first owner frame,
   divided by `slow` (doubled, up to 8, whenever a frame takes more than 150 ms), never below 0.2.
7. **Arrival:** a return is pending, `recognise.frames` (3) owner frames among the last 4 within 6 s, and not *still*
   (every pair of those embeddings with cosine > 0.995 and landmarks moved < 0.5 px: a propped-up photo; it waits).
   Emits `arrived {away_min, others}`; `others` = a second face (score ≥ 0.6) in any of those frames.

Camera problems back off: busy 60 s (Linux `/proc/*/fd` holders, Windows' CapabilityAccessManager record), no camera
60 s, blocked 300 s, covered 300 s. `Camera.open()` raises `CameraError("busy" | "no camera" | "blocked")`.

**Pause reasons, in order** (`watch.py:PAUSES`, `Face.pause_checks()` evaluates them lazily in that order): feature
off · not enrolled (or "re-enrol needed (the recognition model changed)") · not set up yet · paused by you · Kurooto is
paused · on battery (pause mode) · screen locked · you're on a call · focus · night hours · enrolling · camera in use by
another program · no camera · camera blocked by the system · camera covered · template locked.

**Decision worth knowing:** when the computer can't say how long it's been idle (`IdleProbe.idle_seconds()` is None),
the camera opens only after an unlock or a wake (or to confirm a return), never "while idle", and "already open"
doesn't keep it open: it closes when that window ends. Failing closed keeps the camera free (0.8.10 review: before
the fix it stayed open for good once a wake had opened it).

## Hooks for add-ons (0.8.12)

Face presence doesn't watch all the time: the camera opens only after `watch.idle_s` without input, for 10 s after an
unlock or a wake, and while it confirms an arrival; while you type it closes after the 6 s grace. An add-on that needs
the room in view holds it. All on `Face` (`app.modules["face"]`):

| Call | What |
|---|---|
| `watch_people(cb) -> unsubscribe()` | `cb(faces)` for every frame the watcher looks at, while `face.addons.watch` is on: a list (empty when nobody's in view) of `{h_px, h, w, x, y, yaw, det, who, score, e}`. `h_px` the box's height in pixels at the capture size, `h`/`w` shares of the frame, `x`/`y` the box's centre in -1..1 (the camera's own picture, not mirrored), `yaw` from `vision.pose` (mirrored: negative = turned to their left), `det` the detector's score. `who` (`owner`, `unsure`, `stranger`), `score` (the template's cosine) and `e` (SFace's 128 floats, a copy) only for faces big and clear enough to judge (score ≥ 0.8, ≥ `recognise.min_face_px`, sharp, lit), else None. Called on the `face-watch` thread between frames: keep it quick; an exception is a `face_failed {part: "an add-on watching"}` event and the next subscriber still runs. Each subscriber gets its own copies |
| `hold_watch(reason, seconds=600) -> bool` | keeps the camera wanted (`Watcher.held`) for at most `HOLD_MAX_S` = 600 s, renewed by calling again, until `release_watch(reason)`; holds are keyed by `reason` (60 chars). Every pause reason comes first, so a hold never overrides a switch, /face pause, Kurooto paused, battery, a lock, a call, focus, the night, an enrolment or a camera problem. False (nothing held) when `face.addons.hold` is off. `holds()` lists the live ones; `line()` then says "camera on: an add-on is looking (reason)" and `status()["holds"]` has them |
| `owner_desk_height() -> {px, h, n, from} or None` | your face's usual height at the desk: the median of your sightings (the `seen` emit, at most one per 5 s, last 240, in memory; trusted from 10, `from: "seen"`), else the enrolment's front-step median (`baseline.height` over `face.camera.height`, `from: "enrolment"`), else None. Cleared by forget |

Off (no subscriber, no hold) nothing is built: `people()` is false, so `_look` makes no list. The watcher emits
`people {faces}` to `Face._on_watch`, which only hands it to subscribers: never an event, never the live stream
(`test_people_events_never_reach_the_event_log_or_the_pages`). The numbers are the add-on's to look after: Kurooto keeps
none of them. While a hold keeps the camera open, a video call can't take it on Linux; the hold's 10-minute cap and its
reason on the card are there for that.

## Enrolment and the test (`enrol.py`)

`POST /api/face/enrol/start {cid, mode: new|add}` → `Face._start`: refused when the feature is off, parts are missing,
he's on a call, another session is open, or the camera is busy. The session's thread waits up to 3 s for the watcher to
release the camera, then opens it. `Session.step()` at 5 fps: read, JPEG for the preview (320x240, quality 60, in
memory), detect, `Enrolment.judge()`, push `{t: "face", kind: "enrol", session, ok, reason, step, box, landmarks,
quality: {blur, light, yaw, pitch, roll}, ...progress}` to the page's `cid` only (box and landmarks as shares of the
frame; numbers rounded).

`judge()` order (first failure is the reason): covered (10 dark frames) · no face (≥ 0.9) · two faces (> 1 at ≥ 0.6) ·
too far (< `min_face_px`) · too close (> 0.7 of the frame) · out of view (`edge()`: the box touching an edge, named
as on the mirrored page; in the near step only the landmarks plus 8 % of the box must be inside) · tilted (|roll| >
25°) · the step's rule (near: height ≥ `near_target()` = min(1.25 × front median, front + 60 % of the way to 0.7 of
the frame), with how far you are in the nudge) · blur (< `BLUR_MIN` 60) · dark (< 50; < 30 in the light step) · bright (> 210, or > 8 % blown) · the light step's
difference (≥ 25 from the front step's median) · spacing (0.5 s, silent) · repeat (cosine > 0.97 and moved < 3 px) ·
not you (≥ 5 samples and cosine to their centroid < 0.25).

Pose (`vision.py:pose`): `yaw = (nose_x − eyes_mid_x) / eye_distance`, negated for the mirrored preview (his left is
negative); `roll = atan2(eye_dy, eye_dx)`; `pitch = (nose_y − eyes_mid_y) / (mouth_mid_y − eyes_mid_y)`, judged against
his own front-step median (`Enrolment.baseline`, kept in the template for Add samples).

Timeouts: no preview fetched for 15 s → paused (camera closed; Resume reopens it); 10 minutes of capturing → paused;
30 minutes without training → ended, samples dropped. `train` copies the samples into the template, retrains, seals,
then `Session.end()` clears the in-memory list.

The test (`kind: "test"`, 60 s): each face's score and class per frame; `mark("me" | "other")` looks 10 s and keeps
only `{frames, recognised, decided}` or `{frames, best, any_accepted}` in `Template.last_test`.

## Calibration (`model.py`, `core/biometric.py:calibrate`)

- Groups: `base` (front to far), `glasses`, `light`; a group under 5 samples merges into base; centroid = normalised
  mean; `score(x) = max_g cos(x, c_g)`. Learned samples join their nearest group at weight 0.5.
- `G`: 5-fold held-out scores, stratified by step (`folds()`: each step's samples go round the folds). Enrolled
  samples only.
- `J = score(I)` for the impostor matrix `I` against the full template.
- `T_far = max(quantile(J, 1 − far), mean(J) + z·std(J))`, `T_hi = max(0.363, T_far)`, `T_lo = max(0.20, T_hi − 0.10)`.
  `far, z` from `face.recognise.strictness`: loose 1e-2 / 2.33, normal 1e-3 / 3.09, strict 1e-4 / 3.72.
  `face.recognise.threshold > 0` overrides `T_hi` (`method: "override"`), never below 0.363 (a setting can make it
  stricter, never looser than the floor); fewer than 20 impostors or none:
  `T_hi = 0.413` (`method: "floor"`).
- TAR = share of `G ≥ T_hi`, overall and per step. Grade: good (TAR ≥ 0.95, median(G) − T_hi ≥ 0.15, near/far/glasses/
  light complete), fair (TAR ≥ 0.80), weak. Advice per step with TAR < 0.7, when median(J) > 0.25, for missing steps,
  and when calibrated without impostors.
- Why no classifier or fine-tune: one identity, ~50 samples; a classifier would learn the synthetic impostors' domain
  gap; a fine-tune needs torch and licensable real impostor images. `train()`'s report holds what a later comparison
  needs.

### The impostor set

`src/kurooto/data/face-impostors.npz` (fp16 `emb` M×128, `model_sha256`, `source`), read by `Face.impostors()` through
`load_impostors()`, which refuses a set made with another SFace file. **Not shipped in 0.8.10**: the candidate source
is SFHQ (synthetic faces, MIT repository) but its images were made through StyleGAN2, whose own licence is
non-commercial, and the download needs a Kaggle account, so it waits for the owner's OK. `tools/face_impostors.py`
builds it: YuNet ≥ 0.9 with exactly one face per image, align, embed, up to 5,000, and prints the score spread against
a random half's centroid. Synthetic faces have no real lookalikes, which is why the LFW floor (0.363) stays a hard
lower bound.

## Greeting (`greet.py`, `Face.greet`)

`may_greet()` order: `face.greet.on` · Voice on, not muted, `tts()` not None · `availability.call_block(now)` is
`(None, None)` · not paused · `with_others != "skip"` when others are in view · `gap_min` · `per_day` ·
`Calm.speak_ok("face.greet")` last (it records the row). `compose()` parts from `face.greet.say`: `next`
(`web/live.py:today_items`, the first item with state "next"), `waiting` (`ask.pending` counts by kind), `deadline`
(`deadlines.upcoming(24)`'s first not yet past), `held` (`calm.held()` count); the last parts drop until it fits 220
characters; "Want to go through them?" only when something waits and the conversation will open. Others in view
(`with_others` short or skip): "Welcome back." only. Then `Voice.greet(text, listen_s, talk)`: publish
`voice_text`, speak (waiting), and `Portal.invite` when talk, listening isn't blocked and nobody else is in view.

`Calm.speak_ok`: on → the stopped list → `_wait` (exam keep, quiet week, the evening list, Fewer, windows; not the daily
budget since `counted=False`) → a row `kind='spoken'`, `state='spoken'|'skipped'`, `held=<why>`, `text=''`. Anything
going wrong: True. Greeting counts (day, n, last) live in `face.json`'s `greets`.

`Portal.invite` opens the portal with `awaiting = False` (gate rule 5 would take any speech), sets `last = spoke_at =
now`, `last_reply = text`, and a per-invite `close_s` put back when it closes. Rules 7 (open portal, a question or
request) and 8 (a yes or no after a question) then apply; anything not addressed closes it.

## Learning

`Watcher` keeps a candidate from an arrival's frames when the frame is enrolment-grade (blur ≥ 60, 50 ≤ mean ≤ 210,
≤ 8 % blown), alone in view, and `Template.learnable(e, margin)` (≥ `T_hi + learn.margin`, cosine < 0.97 to every
stored sample). Input within 60 s of the arrival emits `learn`; `Face.learn` checks `learn.on` and `learn.every_h`,
appends to the FIFO pool (`learn.max`), retrains (thresholds still from enrolled held-outs) and emits
`face_learned {count}`. Undo the last / Forget what it learned recompute.

A change of the SFace file (another sha256 than `face.json`'s `model_sha`) means "re-enrol needed": embeddings from two
models are never mixed.

## Privacy

| What | Where | Form |
|---|---|---|
| template | `<state>/face/template.bin` | AES-GCM-256, nonce + ciphertext, AAD `kurooto-face:template:v1`; the sealed JSON: version, model_sha256, created, updated, samples (base64 fp16, step, at, q), learned, centroids, thresholds, grade, report, last_test, baseline |
| key | secret `face.key` | keychain, else `config/secrets.json` (owner-only) |
| status | `<state>/face/face.json` | counts and dates: enrolled, samples, per_step, learned, grade, tar, created, trained, last_test_at, model, model_sha (12 chars), greets |
| frames, crops, previews, strangers | nowhere | memory only; previews served with `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` |

Never in a backup (`SKIP_STATE_DIRS`, `backup_secret_names`), Profile sync (`NEVER`) or the diagnostics bundle (only
`face.json`'s counts). `known_secret_names()` still lists `face.key` on purpose: moving keys to the file for a start at
boot (`core/autostart.py`) and uninstalling (`core/leave.py:forget_keys`) must reach it.

Events (no scores, embeddings or image data; `test_events_carry_no_scores_or_pictures` checks the keys):
`face_watch {on, why}`, `face_arrived {away_min}`, `face_left {}`, `face_back {}`, `face_greeted {parts, talk}`,
`face_greet_skipped {why}`, `face_enrolled {samples, grade}`, `face_trained {samples, grade}`, `face_learned {count}`,
`face_forgotten {}`, `face_failed {part, error}` (the exception type only). `core/nearby.py` emits `nearby_others {on,
source}`.

The live stream: `{t: "face", kind: "enrol" | "test" | "test_result" | "session"}` to the Face page's `cid` only;
`{t: "face", kind: "camera", on}` to every page (the badge).

## API

| Route | What |
|---|---|
| `GET /api/face` | `Face.status()`: stage (off, setup, enrol, capturing, testing, manage), line, why, model (report, thresholds, learned, last test), plan, switches; never a template value |
| `GET /api/face/frame?s=` | the preview JPEG; 404 without a live session; the dashboard token like every API route |
| `POST /api/face/enrol/start {cid, mode}` | guarded `camera.open` (the page's Start) |
| `POST /api/face/enrol/step {session, action}` | skip, back, no_glasses |
| `POST /api/face/enrol/pause {session, on}`, `enrol/discard`, `train {session}` | |
| `POST /api/face/test/start {cid}` | guarded `camera.open` (the page's Test) |
| `POST /api/face/test/mark {session, who}`, `test/stop` | |
| `POST /api/face/retrain`, `strictness {level}`, `learn/undo`, `learn/forget`, `pause {arg}` | |
| `POST /api/face/undo` | back to the template before the last `train` (Start over, i.e. `enrol/start {mode: new}` while enrolled, or Add samples); held in memory (`Face._previous`, a payload) for this run only, dropped by forget; `status().can_undo`. A Start over never trains over a template whose key can't be read |
| `POST /api/face/forget` | `data.delete` (after the page's confirm) |
| `POST /api/face/install-from {folder}` | runs in the background; progress at `GET /api/progress` |

## The camera per OS

See `camera.py`'s docstring: V4L2 with IR names skipped and `/proc/*/fd` holders on Linux; MSMF then DSHOW, and the
CapabilityAccessManager record for "in use", on Windows; AVFoundation on macOS, which shares the camera and can't say
it's busy. Open-but-no-frames for 2 s means blocked (a permission) or a metadata node. `kurooto face test-camera` is the
owner's check (3 s, numbers only).

## Not verified

- No real camera, model file or face was used: everything ran with fakes. `cv2` isn't in the dev environment, so
  `vision.py`'s OpenCV classes and `camera.py`'s `open()` have never run here.
- `BLUR_MIN` (60), the brightness limits and the pose ranges are first guesses; the first real run should tune them.
- The expected scores (same person about 0.55 to 0.8, others 0 to 0.3, `T_hi` about 0.40 to 0.48) are from the
  literature, not measured.
- The Windows busy check and macOS permission behaviour are written from documentation, untested.
- The SFace training-data line in the user page is from the SFace paper as remembered, not re-checked against it.

## The owner's first real run

1. A scratch `KUROOTO_HOME` and a free port: `kurooto face test-camera`; check the size, fps and the light coming on.
2. Features → Face presence → Set up (about 0.18 GB); `/egress` should show only `media.githubusercontent.com` and the
   uv hand-off.
3. Enrol; read the report (TAR, `T_hi`, grade, advice). Tune `BLUR_MIN` and the brightness limits if good frames are
   rejected.
4. Test as yourself and as someone else (a stranger's photo on a phone); note the scores.
5. Lock the screen, step away 20 minutes (or `face.greet.after_absent_min` 1), come back and unlock: the greeting should
   come within about 3 s; answer "what's next?" without the name.
6. Start a video call right after sitting down: it should get the camera (Linux).
7. `/face forget`: `<state>/face/` is gone and `face.key` isn't in the keychain.
