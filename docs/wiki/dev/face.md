# Face presence (`modules/face/`, 0.8.10)

Kurooto recognises its owner's face with OpenCV's YuNet (detection) and SFace (recognition), on the CPU, on this
computer only, and greets him by voice when he sits down after an absence, then opens Voice's conversation
(`Portal.invite`). Off by default (a module); nothing watches until he enrols on the dashboard's Face page. User page:
[../user/face.md](../user/face.md). Design: `build-specs/0.8.10/face.md` (outside the repo).

**The rule above all others: a face match never authorises anything.** It isn't one of `core/tap.py:WAYS`, never
answers an approval or unlocks anything. `tests/unit/test_face.py:test_a_face_never_authorises_anything`
checks that `core/tap.py`, `core/ask.py` and `core/tools.py` never read the face module. One narrow exception, its own
switch (0.8.13, `voice.speaker_id.face_assist`, on): a voice Voice ID already scored inside its "not sure" margin counts
as the owner while the watcher's last frame (at most `core/nearby.py:VIEW_S` old) shows exactly one face and it's his
(the watcher's `view` emit -> `nearby.set_view`). A face alone, a voice below the margin, two voices or strict
strictness never do; see [voice.md](voice.md).

## Files

| File | What's in it |
|---|---|
| `modules/face/__init__.py` | `Face(Module)`: settings (`register_defaults("face", ...)`), parts, the template cache, `pause_checks()`/`pause_reason()`, the watcher's thread (`_run`, `tick`, `background`), `_on_watch` (events), the greeting (`greet`), learning, the sessions (`enrol_start`, `train`, `test_start`, ...), `forget`, `turned_off`, `status()`/`card()`/`/face`/intents; `button()` for the core `fce` prefix |
| `modules/face/parts.py` | `FACE_PACKAGES` (`vision`: opencv-python-headless, numpy; module `cv2`), `face_models()` (pinned URLs and sha256), `parts(app)`: Voice's `Parts` with `root=<app>/voice` (one shared `py-X.Y`) and `models_dir=<app>/face/models` |
| `modules/face/camera.py` | `Camera` (open/read/close, per-OS backends), `devices()`, `pick()`, `holders()` (Linux busy; Kurooto's own process tree, `own()`, left out), `shared()` (v4l2loopback: a `max_openers` file, never busy), `free()`, `windows_busy()`, `CameraError(why)` |
| `modules/face/vision.py` | `Face(box, landmarks, score)`, `Stats`, `Pose`, the `Detector`/`Embedder`/`Frames` protocols, `pose()`, `moved()`, `opencv_detector()`, `opencv_embedder()`, `opencv_frames()` (cv2 imported only inside) |
| `modules/face/enrol.py` | `PLAN`, `Step`, the quality limits, `Enrolment` (pure: progress, `act()`, `judge()`, `_unlike()`), (0.9.0) `Look(Enrolment)` (Add this look's one step), `shape()`, `Session` (camera, preview, timeouts, test marks, a look's end) |
| `modules/face/gaze.py` | (0.8.17) look to talk by the eyes: `offset()` (iris along/across the eye from MediaPipe's contour), `eyes_of()`, `angles()` (head + eyes, degrees from the lens, against a calibration), `valid()`, `Calibration` (medians of h, v, yaw, pitch), `CvGazer` / `opencv_gazer()` (cv2 imported only inside) |
| `modules/face/model.py` | `Sample`, `centroids()`, `score()`, `folds()`, `held_out()`, `train()`, (0.9.0) `look_check()`, `Template` (payload, `classify()`, `retrain()`, `learn()`, `undo_learn()`, `forget_learned()`, `add_look()`, `remove_look()`) |
| `modules/face/watch.py` | `Watcher` (pure: injected clock, idle, locked, camera, models, classify, pause reasons, emit), `PAUSES` |
| `modules/face/greet.py` | `compose()` (rules, ≤ 220 characters), `may_greet()` |
| `core/biometric.py` | `BioStore(app, feature)` (key, seal, unseal, save, load, forget, `Locked`), `calibrate()`, `load_impostors()`, `npz_read`/`npz_write` (numpy's format without numpy), `BIOMETRIC_SECRETS`. Shared with Voice ID |
| `core/nearby.py` | "others nearby": `set_others(app, source, on)`, `others(app)`; Face sets it, Voice (ID) can read it. The watcher sends `others on` with every frame while a second face is in view (0.9.3: a second counted face in `OTHER_N` of the last `OTHER_M` frames turns it on, `ID_MISS` frames without one turn it off: `Watcher._two`) (nearby drops a signal older than `STALE_S`, 120 s), and the event only when it changes |
| `web/static/face.js` | the Face page (`FACE.mount`, `FACE.live`), loaded on demand by `home.js:renderFace` |
| `tools/face_impostors.py` | the maintainer's impostor-set builder (never at install) |
| `tests/unit/test_face.py`, `tests/unit/test_biometric.py` | everything with fakes |
| `tests/unit/test_face_looks.py` | (0.9.0) Add this look: the plan's checks, `look_check` (safe, too far, anchored to the enrolment, impostors), the template's looks and `use_looks`, the session end to end, refusals, the switch, Remove and Undo, the command, the API |
| `tests/unit/test_face_gaze.py` | (0.8.17) the iris maths, gaze angles, calibration, `looking()` by the eyes, the calibration session, the watcher's eyes and `look_fps`, resolution independence (480x640 vs 1080x1440), the part, look to talk end to end; one real-model test (made-up drawn eyes), skipped unless `KUROOTO_TEST_MODELS` holds `iris_landmark.tflite` and cv2 imports |

## Changes elsewhere

- `modules/voice/parts.py`: `ModelFile.sha256` (checked after download; a mismatch deletes the `.part`), `Parts(root,
  app_dir, packages=None, table=None, models_dir=None, feature="Voice")`, `Parts.install_from(folder, keys, progress)`.
  Voice's behaviour is unchanged.
- `modules/voice/__init__.py`: `Voice.greet(text, listen_s, talk=True) -> (spoken, "talk" | why)`; `_job_done` doesn't
  read answers aloud while `app.away_from_desk()` with `face.away.hold_desktop`.
- `modules/voice/portal.py`: `Portal.invite(text, hold_s)`.
- `core/calm.py`: reasons `face.greet` (`counted=False`, `later=False`, `feature="face"`), `face.off` and (0.9.0)
  `face.look` (exempt);
  `Calm.speak_ok(why, about)`.
- `core/tap.py`: `GUARDED["camera.open"]` (ways: button; typed since 0.9.0, for `/face add-look` only),
  `data.delete`'s where, `BUTTONS["fce"]`.
- `core/egress.py`: `media.githubusercontent.com`; (0.8.17) `storage.googleapis.com` (the eye model). `core/notify.py`: `Notifier._desktop` (held while away).
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

**Flicker (0.9.2, a fix, `watch.py`).** Per frame, after `drop_nested`: only faces at least `HALF` (0.5) of the
biggest one's height count (`counted`; the rest are in `people` and the tracks but never judged, counted, in
`sizes` or `looks`). Each counted face is followed by its box (`_follow`: greedy IoU ≥ `ID_IOU` 0.3, forgotten after
`ID_MISS` 2 missed frames, `ids` cleared in `_close`; boxes and the last `OTHER_M` verdict words only). `_settle`:
someone else only when `OTHER_N` of the last `OTHER_M` (2 of 3) judged frames said "stranger" (before that, unsure);
a face recognised as his within `keep_s` = max(`ID_KEEP_S` 2 s, 1.5 frame gaps) stays his through an unjudged
(small, low score, blurred) or unsure frame or a single "stranger" frame (`kept_i`). A kept face counts in "view"
(`owner_alone`, `owner`, `eyes`, `looks` skip it) and the tracks' owner flag, never in `recent` (arrivals), `seen`,
`candidate`, `counts.you` or learning. `counts.not_you`, `strangers` (away) and `people`'s `who` use the settled
verdict. Golden scenes with the 0.9.1 and 0.9.2 rows: `tests/unit/test_face_flicker.py`.

Camera problems back off: busy 60 s (Linux `/proc/*/fd` holders, Windows' CapabilityAccessManager record), no camera
60 s, blocked 300 s, covered 300 s. `Camera.open()` raises `CameraError("busy" | "no camera" | "blocked")`; on Linux it
tries only `free()` cameras, so "busy" means every candidate is held. A `face.camera.*` change swaps the watcher's
`Camera` on the next tick (`Face._camera_changed`); before 0.8.13 it took a restart.

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
| `hold_watch(reason, seconds=600, core=False) -> bool` | keeps the camera wanted (`Watcher.held`) for at most `HOLD_MAX_S` = 600 s, renewed by calling again, until `release_watch(reason)`; holds are keyed by `reason` (60 chars). Every pause reason comes first, so a hold never overrides a switch, /face pause, Kurooto paused, battery, a lock, a call, focus, the night, an enrolment or a camera problem. False (nothing held) when `face.addons.hold` is off, unless `core=True` (Kurooto's own hold: Voice's `voice.listen.need_face`; kept in `_core_holds`, listed by `holds()` whatever the add-on switch). `holds()` lists the live ones; `line()` then says "camera on: an add-on is looking (reason)" for add-ons' and the reason itself for core ones ("camera on: voice: who's talking"), and `status()["holds"]` has them |
| `watch_faces(cb) -> unsubscribe()` | `cb(faces)` with the tracker's list (below: `{id, x, y, h, owner, m}`, no identity beyond the owner flag, no numbers) for every frame tracked, and `[]` once when the last face goes or the camera closes; while `face.track.on` and `face.addons.watch` are on. A subscriber alone asks for faces at the recognition rate (`TRACK_SLOW`); a hold whose reason contains "track" (`hold_watch("eye tracking")`) asks for `face.track.fps` (`TRACK_FAST`) and opens the camera as any hold does. Same thread, copies and failure rule (`face_failed {part: "an add-on following faces"}`) as `watch_people` |
| `greet_part(name, line) -> unsubscribe()` | (0.9.0, `face.greet.addons`, off) `line()` returns one short sentence (or None) for the next greeting; called on the greeting's thread only with nobody else in view (`others` and `nearby.others` false); cut to `ADDON_LINE_MAX` (120) characters, a full stop added, passed to `compose(extra=[("addon:<name>", text)])` after every built-in part so the length limit drops it first. `greet_carried(name, since)` says whether a greeting said it at or after `since` (`time.time()`), so the add-on can say it its own way otherwise. The part's name (`addon:<name>`) is in `face_greeted`'s `parts`, never its words. A raising `line` is `face_failed {part: "an add-on's greeting line"}` and the greeting goes on |
| `known_guests(check) -> unsubscribe()` | (0.9.0, `face.addons.known_guests`, on; nothing without an add-on) `check()` returns True when everyone in view besides the owner is someone the add-on knows: a boolean only, so core still never works out who anyone else is. `known_guest()` is any check's True; `may_greet` then lets `with_others` `skip` through and `greet()` greets as `short` ("Welcome back.", no conversation). A raising check counts as False |
| `light_level() -> float or None` | (0.9.0, `face.light_sense`, off) the frames' mean brightness, 0..1, smoothed (`LIGHT_ALPHA` 0.2 a frame), None when off or older than `LIGHT_STALE_S` (120 s). Only while the camera looks anyway: the watcher emits `light {mean}` when cfg `light` is on, `Face._light_seen` keeps one number in memory. A webcam adjusts its exposure: a rough dark-to-lit signal, not lux. Brain's body uses it for `brightness` when no device's lux is fed (`stimulation._webcam`, x `WEBCAM_SCALE` 2.5) |
| `owner_desk_height() -> {px, h, n, from} or None` | your face's usual height at the desk: the median of your sightings (the `seen` emit, at most one per 5 s, last 240, in memory; trusted from 10, `from: "seen"`), else the enrolment's front-step median (`baseline.height` over `face.camera.height`, `from: "enrolment"`), else None. Cleared by forget |

Off (no subscriber, no hold) nothing is built: `people()` is false, so `_look` makes no list. The watcher emits
`people {faces}` to `Face._on_watch`, which only hands it to subscribers: never an event, never the live stream
(`test_people_events_never_reach_the_event_log_or_the_pages`). The numbers are the add-on's to look after: Kurooto keeps
none of them. While a hold keeps the camera open, a video call can't take it on Linux; the hold's 10-minute cap and its
reason on the card are there for that.

## Close and facing, for Voice (0.8.13)

`voice.listen.need_face` (Voice's switch; [voice.md](voice.md)). The watcher's `view` emit gained `sizes`: for each
face counted (0.9.3, a fix: at `SCORE_WATCH` and `face.recognise.min_face_px`, and at least `HALF` the biggest such
face; before, any detection at `SCORE_OTHER`, so a faint false box flickered "others nearby" hundreds of times), `(height_px, yaw)` (`watch._yaw`: `vision.pose`'s yaw, None when the landmarks can't
give one). `Face._on_watch("view")` calls `nearby.set_facing(app, faces, close_facing(sizes))` and drops the list.
`close_facing` counts faces with `height_px >= voice.listen.face_near * owner_desk_height()["px"]` (no desk height:
`face.recognise.min_face_px`) and `vision.yaw_degrees(yaw) <= voice.listen.face_yaw_deg`; `yaw_degrees` is
`atan(|yaw| / YAW_K)` with `YAW_K = 0.3 / tan(25 deg)`, the scale `Pose.yaw` documents (an estimate from five
landmarks). `core/nearby.py` keeps `(time, faces, facing)` per frame for `FACING_KEEP_S` (60 s, at most 600 rows) and
the last sighting time: times and counts only, never boxes, pictures, numbers or identity. A covered frame emits no
`view`, so it counts as the camera not looking.

0.8.17 (`voice.listen.look_to_talk`): `view` also carries `owner`, the best owner face's `(height_px, yaw, pitch)`
(`watch._pitch`), or None. `Face.looking(owner)` (close as `close_facing`, `yaw_degrees <= voice.listen.look_yaw_deg`,
`vision.pitch_degrees(pitch, template.baseline["pitch"]) <= voice.listen.look_pitch_deg`, yaw only without a front
step; `pitch_degrees` is `atan(|pitch - front| / PITCH_K)`, `PITCH_K = 0.26`, an estimate) goes to
`nearby.set_look(app, on)` (two times: the run's start and the last look), then `Voice.look_tick()` is called at once
([voice.md](voice.md)). It's the head's direction from five landmarks, not gaze.

0.8.18 (`voice.listen.look_anyone`, on): with cfg `look_anyone` (the switch and `_look_listening()`), `view` also carries
`looks`, the `LOOK_OTHERS` (3) biggest other faces at `SCORE_WATCH` and `min_face_px` as `(height_px, yaw, pitch, eyes)`
(eyes through the same gazer, None without one); else None. `Face.looking(owner, eyes, frame, looks)` is the owner's
verdict or any of theirs (`_looks_at(..., own=False)`): the same angles, your calibration and your enrolment's front step,
no blink hold, and `_gaze_last` (the /voice gaze line) stays the owner's. Numbers for where a face points only, dropped
with the frame. Pause list (0.8.18): "Kurooto is asleep" after "night hours" (`mind.sleep.senses_off`,
`mind/sleep.senses_off()`), 17 reasons; `desk_seen_at()` (the watcher's `present_at` as `time.time()`, None when
away or not watching) feeds `mind.sleep.desk_holds`.

0.9.0 (`face.camera.yaw_offset_deg`, 0): `Face.yaw_offset()` (clamped to +-30, 0 for a bad value) moves the centre of
the look. The head path compares `|atan(yaw / YAW_K) - offset|` (signed: pose's mirrored yaw, + to the user's right)
with `look_yaw_deg`, which is `yaw_degrees` at 0; the eyes path subtracts it from `angles()`' sideways degrees before
`look_gaze_yaw_deg`. `close_facing` and the `face_yaw_deg` head limit are unchanged (they ask "facing the camera at
all"). Generic on purpose: an add-on whose camera's lens sits beside the spot to look at (the Body add-on's drawn eye)
sets the setting while `face.camera.device` names its camera and clears it on unplug.

### By the eyes (0.8.17, `voice.listen.look_gaze`, `gaze.py`)

- **The part.** `parts.py`: `iris` = `iris_landmark.tflite` (MediaPipe Iris, Apache-2.0, 2,640,568 bytes), from
  `storage.googleapis.com/mediapipe-assets/iris_landmark.tflite?generation=1662065468653224`, sha256
  `d1744d2a09c25f501d39eba4faff47e53ecca8852c5ce19bce8eeac39357521f` (the same bytes as google/mediapipe v0.8.10's
  `mediapipe/modules/iris_landmark/`). Optional: `EYES = ["model:iris"]`, not in `WANTS`; fetched by
  `Face.gaze_setup()` (POST `face/gaze/setup`, the page's Get the eye model); `install_from` copies it when the folder
  has it. Loaded with `cv2.dnn.readNetFromTFLite` (checked with opencv-python-headless 4.14: NCHW blob, RGB 0..1,
  outputs `output_eyes_contours_and_brows` (1, 213) and `output_iris` (1, 15)).
- **Reading.** `CvGazer.eyes(frame, face)`: for each of YuNet's eye points, a square `EYE_CROP` (1.0) x the eyes'
  distance, turned level by the roll, cut from the **full** frame at its own resolution (`warpAffine`, inverse map),
  then shrunk to 64x64 (`INTER_AREA`); the picture's left eye (landmark 0) mirrored, as MediaPipe's right-eye path
  does, and its points mirrored back. `offset(contour, iris)`: corners are contour points 0 and 8, lids' middles 4 and
  12; `h = 2t - 1` along the corner line (picture left -1 .. right 1), `v` across it (down positive) in eye widths,
  `open = |p4 - p12| / width`; `eyes_of` averages the eyes with `open >= OPEN_MIN` (0.12), None for none.
- **Angles.** `angles(h, v, yaw, pitch, cal)`: `atan(yaw / YAW_K) - atan(cal.yaw / YAW_K)` minus
  `asin(h / EYE_H) - asin(cal.h / EYE_H)` (the picture isn't mirrored, pose's yaw is), and
  `atan((pitch - cal.pitch) / PITCH_K)` plus `asin(v / EYE_V) - asin(cal.v / EYE_V)`; `EYE_H` 0.8 and `EYE_V` 0.4 from
  an eyeball radius of about 12 mm over a 30 mm eye. Estimates; calibration sets the zero, the tolerances absorb the
  gain.
- **Calibration.** Session kind `gaze` (`enrol.py`, `Face.gaze_start`, POST `face/gaze/start`, guarded
  `camera.open`): per frame, one sure face, alone, `|yaw| <= CAL_YAW` (0.2), classified owner (SFace), eyes read ->
  `Calibration.feed`; done after `CAL_S` (3 s) and `CAL_MIN` (8) readings; `result()` refuses a median absolute
  deviation of h over `CAL_SPREAD` (0.2) or too few frames (gives up `CAL_MAX_S`, 15 s, after the first). The page
  gets `{kind: "gaze", ok, reason, share}` and `{kind: "gaze_result", ok, message}`, never numbers.
  `Face._gaze_done` stores `{h, v, yaw, pitch, n, at}` as `Template.gaze` (sealed; `face.json` gets only `gaze_at`);
  `gaze_clear()` (POST `face/gaze/clear`) empties it; forget drops it with the template. Event `face_gaze
  {calibrated}`.
- **Deciding.** The watcher reads eyes only while `gaze()` (`Face._gaze_now`) hands a gazer: look_to_talk on, Voice's
  own hold on the camera (`_look_listening`), `gaze_calibration()` (look_gaze on, the part, a valid calibration). The
  "view" emit gains `eyes=(h, v)` (or None) and `frame=(w, h)`. `Face.looking(owner, eyes, frame)` with a calibration:
  close as before, head within `face_yaw_deg`, then `|angles| <= look_gaze_yaw_deg / look_gaze_pitch_deg` (10, 10); no
  eyes (a blink) keeps the last verdict for `BLINK_HOLD_S` (1 s). Without one: the head rule above.
  `gaze_status()`: `{on, model, calibrated, at, using: eyes | head, why, now: {looking, yaw_deg, pitch_deg} (5 s
  fresh), mb}`, in `status()["gaze"]` and Voice's `status()["look_to_talk"]["gaze"]`.
- **Rate and cost.** `face.watch.look_fps` (5, at most `watch.LOOK_MAX_FPS` 5, halved by `slow` like `fps`) applies
  while `_look_listening()` (`_watch_cfg()["look_fps"]`, else 0). Measured on a Ryzen 7 7435HS, one thread, per full
  frame at 1080x1440: YuNet on the 320-wide copy 13.7 ms, `frames.mean` 4.0, SFace align + feature 28.7, two eyes
  through the iris model 6.7: about 53 ms (47 ms at 480x640), so 5 fps is about a quarter of one core while Voice
  listens.

### Camera resolution (0.8.17)

`CvDetector` already ran YuNet on a 320-wide copy (now `INTER_AREA`, no aliasing from 1080 wide) and scaled the points
back; SFace's `alignCrop` and the eyes use the full frame. Every size-dependent rule is now relative:
`vision.px_scale(w, h)` = shorter side / `REF_PX` (480) scales `face.recognise.min_face_px` (watcher and enrolment),
the still-picture check (`STILL_PX`), enrolment's far step (`min_face_px + 20`) and repeat check (`REPEAT_PX`); the
enrolment baseline gains `share` (front face height / frame height), used for the near and far steps when known;
`owner_desk_height()` from the enrolment uses `share` (`measured: True`; an older one's `px / face.camera.height` is
a guess and is compared in pixels as before); `close_facing(sizes, frame)` compares `h_px` with
`desk.h * frame height * face_near` when the desk height is measured, else pixels as before; with no desk height,
`min_face_px * px_scale`. `_shown`, `_person`, "seen" and tracking were shares already. Tests run both 480x640 and
1080x1440.

## Tracking every face (0.8.12)

So the being's eye (and an add-on's) can follow anyone in view, not just the owner. Switch `face.track.on` (on); rate
`face.track.fps` (10, at most 15). Tracking never opens the camera: it only works while the watcher's rules have it
open (idle, a wake, a confirmation, an add-on's hold).

`Face._track_mode()` → `Watcher.tracking` (read once per full tick):

| Mode | When | What runs |
|---|---|---|
| `TRACK_OFF` | `face.track.on` off, or nobody wants faces | nothing: no tracks, no list (as 0.8.11) |
| `TRACK_SLOW` | an add-on holds the camera (any reason) or follows faces (`watch_faces`), no page in sight | tracks updated on the recognition frames only (`watch.fps`) |
| `TRACK_FAST` | a dashboard page in sight (`Live.watched()`), or a hold whose reason contains "track" | detection-only frames (`Watcher.track_tick`: `Camera.read` + YuNet, never SFace) between the recognition frames, at `track.fps` |

The thread (`Face._run`): a full `tick()` (pause reasons, input, the camera's rules, recognition when due) every
`TICK_S` = 0.25 s; between, `track_tick()` only; it sleeps `Watcher.wait_s()`: until the next detection frame or full
tick, never under `WAIT_MIN_S` = 20 ms. A detection-only frame over 60 ms halves the tracking rate (to 1/8 at most);
30 quick ones in a row undo one halving.

**Tracks** (`Watcher._update_tracks`, positions in memory only, cleared when the camera closes): each frame's faces
(score ≥ 0.6, any size) are matched to the tracks greedily, nearest centre first, within `TRACK_MATCH` = 1 face
height; unmatched faces get a new id (counting up from 1 per watcher); a track missing `TRACK_MISS` = 3 frames in a
row is gone. The owner flag comes from recognition frames: the face recognised as you sets it (on that track only),
a stranger clears it, unsure and unjudged faces keep it.

**Micro-movement** `m` (`Watcher._move`): against the track as it was `MICRO_WINDOW_S` = 0.4 s ago (the last frame
when frames are further apart): centre shift + size change + the largest landmark shift relative to the face's
centre (a nod or a turn moves the nose, a wide mouth movement its corners), in face heights, minus `MICRO_JITTER` =
0.03, per second, over `MICRO_FULL` = 0.3, clipped to 0..1; it rises 60 % of the way to a new reading at once and
fades with `MICRO_TAU` = 0.5 s. The jitter and scale are estimates from YuNet's landmark precision at 320 px wide, not
measured on a camera yet: a still face may read 0.05-0.15 on a noisy webcam. YuNet's five landmarks have no lips, so
talking shows only as far as it moves the mouth's corners or the head.

The message, to every open page (`Face._on_watch("faces")`, at most one per `FACES_EVERY_S` = 0.09 s, an empty list
always; only while `Live.watched()`) and to `watch_faces` subscribers (every one):

```json
{"t": "face", "kind": "faces", "faces": [{"id": 3, "x": -0.21, "y": -0.05, "h": 0.31, "owner": true, "m": 0.18}]}
```

`x`, `y` the box's centre in -1..1 of the camera's own picture (not mirrored, as `face_seen`), `h` its height's share
of the frame. Never an event, never kept. `face_seen` is unchanged (owner only, recognition frames, ≤ 5 a second).

**Time at the desk** (0.9.0, L22, `face.desk_time`, off): `Face.desk_spans(lo, hi)` pairs `face_arrived` /
`face_back` with `face_left` from the event log (a stretch open at `lo` starts there, one still going ends now);
`desk_line(lo, hi, when)` says the total and the longest (under 15 min: ""); `weekly_lines()` gives the week's for the
weekly summary, and `checkins._desk_line(day)` the check-in day's for the evening message and call (a step that says
it once, never as a judgement). (0.9.1) The break bid: `Face.desk_break(t)` (job `face:desk_break`, every 5 min;
`face.desk_break`, off; `face.desk_break_min`, 90, at least 15): the newest `desk_spans` stretch still going (ended
within 2 min) at least that long, once per stretch (`greets()["break_for"]`), one `app.notify(why="face.desk_break")`
through Calm and Brain's door; event `face_desk_break` with the minutes.

**The greeting's threads part** (0.9.1, L45): `greet.compose(..., threads=[(text, due)])` adds `threads` after every
built-in part (before add-ons' lines) when `"threads"` is in `face.greet.say` and nobody else is in view (even with
`full`); `Face._threads_due(t)` reads `core/threads.due_by` to the end of today.

**The being's eye** (`static/being.js`, `ATT`/`attend()`): with `faces` fresh (< 2 s) it looks at one face and moves
to another (picked at random, weighted 0.4 + m) every 3-8 s, after 0.7 s to someone new, after 1 s to a face whose
m is over 0.3 and 0.25 above the current one's; a switch is a saccade (fast gaze for 140 ms). One face is followed
closely (gaze rate 9 against 5), with a quick small saccade, landing a little ahead, when its m jumps by 0.12 or
passes 0.35. The owner has no priority, except (0.9.0, L136, `face.track.speaker`: `Face._on_watch` adds
`speaker: true` to the pages' `faces` message) while someone talks: `voice()` keeps `ATT.talk` from `voice_text`
(`who: "you"`, `speaker` = Voice ID's decision), `voice_heard` and `voice_level` above 0.2, and `attend()` turns to the
owner's face when the words were the owner's, else the face with the highest `m`, within 1.5 s of speech (400 ms
dwell). Booleans and the verdict word only (R2). `STILL` (Remove animations) or the system's reduced motion: no saccades, a
slow smooth gaze (rate 1.5). Without `faces` (tracking off, an older daemon) it follows `face_seen` as before. The
phone's Views → Being (`being-phone.js`) runs the same code but gets no face messages.

**Cost, honestly:** YuNet at 320x240 measured about 9 ms on one thread (above), plus `Camera.read` and the resize
(a few ms), so `TRACK_FAST` at 10 a second is roughly 10-15 % of one core while the camera is open and a dashboard
is in sight; that's an estimate from the 0.8.10 measurement, not measured with a camera in this release.
`test_the_watch_thread_sleeps_between_frames_while_tracking` runs the real loop with free fakes for 1.2 s: about 12
detections and well under 0.3 s of the thread's CPU, so the loop itself doesn't spin. Lower `face.track.fps` or turn
`face.track.on` off to save it.

Tests: `tests/unit/test_face.py` section 14 (ids across frames and list order, micro-movement still/nod/large/fade,
rates and passes, the switch, the slow machine, who wants faces, the page rate limit and add-on copies, the real
loop).

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

Name (0.9.0, `persona.templates`): `Face.greet` passes `name=persona.address(app)` unless the arrival saw others or
`nearby.others(app)`; `compose` makes "Welcome back, Sam." and measures `MAX_CHARS` without the name, then
`persona.template` applies the avoid line as punctuation.

## Your phone's places (0.9.0, `face.away.use_places`, `places_close_camera`, off)

`mind/senses/phone.py:ingest` hands a places bin's `event` (arrive / leave) no older than `PLACE_FRESH_S` (30 min) to
`_place`: `core/nearby.py:set_phone_out(app, event == "leave", at)` (a time only, never the label; `phone_out()` drops
it after `PHONE_OUT_MAX_S`, 18 h) and, Face on, `Face.phone_place(event)`. A leave with `away.on` and `use_places`
calls `Watcher.mark_away()` (away now, `left_at`, "left" -> `face_left`), so `_away_block` and `hold_desktop` apply
at once; an arrive does nothing to the watcher. "back" and an arrival clear `phone_out`. `places_close_camera` (with
`use_places`) is the pause reason "your phone is out" (after "Kurooto is asleep"; PAUSES has 18). Voice's
`voice.listen.phone_away` is a `blocked()` reason of its own reading the same `phone_out`. Needs Brain on and
`mind.senses.phone.places` (the phone's saved places); without them nothing ever sets it.

## While you were away (0.9.1, `face.away.summary`, `face.away.summary_only`, off)

`_on_watch("left")` stamps `_left_ts` (an arrival without it: `time.time() - away_min * 60`). `flush_desktop(card=True)`
with the switch calls `away_summary()`: the held pop-ups (`self.held`, title/text/urgent) and
`calls.chat.answers_since(_left_ts)` (the board talk box's answers, calls/chat.py) become `away_card` (memory only) and
one `desktop.notify("While you were away", ...)`, event `face_away_summary {popups, answers}`. Without `summary_only` the
held pop-ups then flush as before and the card is marked `shown`; with it, `held` is cleared and `show_away()` (the
Waiting page's Send now, `POST waiting/away`) shows them. `core/waiting.py:view` puts the card on the Waiting page;
`calls/today.py:_waiting` adds `away` (a count).

## Someone else while you're away (0.9.0, `face.away.report_others`, off)

`Watcher._look` counts the faces classified `stranger` in a frame (unsure ones don't count) and, while `away`, emits
`strangers {n}`. `Face._stranger_seen(n)` (switch on) keeps `{epoch minute: most faces}` in memory, at most
`OTHERS_MAX` (120) minutes, the oldest dropped. On "back" and on an arrival, `report_others()` sends one message
(`why="face.away.others"`, a Calm reason with Stop = the switch off) naming up to `OTHERS_SAID` (6) minutes, emits
`face_away_others {count}` and clears it; switched off meanwhile, it clears without telling. Forget clears it. Not in
`status()`, the card, the reserve or any AI tool (R7: other people's presence is theirs).

Records (0.9.0, `face.greet.records`, on; Brain only): see [mind.md](mind.md#decision-records-mindrecordspy). The
portal's `turns` (answered turns since it opened, reset on open) says whether the greeting was answered.

## owner_here and the greeting's answers (0.9.0)

`Face.here()` (`Watcher.here()`) ends away from core/here.py's voice or dashboard sign: "back", never "arrived", and
`here_at` joins `present_at` in `_check_away`. Each "view" with the owner's face calls `here.owner_here(app, "face")`.
The greeting's `answers` part counts `Voice.held_answers` (`_held_answers`).

## Breaks for Brain (0.9.0, `face.breaks`, on)

`Face._break_signs(owner, frame)` on each "view": `face_looked` once per run of looks (core/nearby.py's look times,
`LOOK_BREAK_S` = 1 s of looking); `face_stood` when the owner's face share of the frame is under `STOOD_RATIO` (0.6) of
`owner_desk_height()["h"]` (measured shares only), once until it's back over `STOOD_BACK` (0.8). `mind/breaks.py`
maps `face_left`, `face_looked`, `face_stood` to "left", "looked", "stood" (`FACE_EVENTS`) while `face.breaks` is on.
Kinds only; no numbers about the face reach the log.

## Learning

`Watcher` keeps a candidate from an arrival's frames when the frame is enrolment-grade (blur ≥ 60, 50 ≤ mean ≤ 210,
≤ 8 % blown), alone in view, and `Template.learnable(e, margin)` (≥ `T_hi + learn.margin`, cosine < 0.97 to every
stored sample). Input within 60 s of the arrival emits `learn`; `Face.learn` checks `learn.on` and `learn.every_h`,
appends to the FIFO pool (`learn.max`), retrains (thresholds still from enrolled held-outs) and emits
`face_learned {count}`. Undo the last / Forget what it learned recompute.

A change of the SFace file (another sha256 than `face.json`'s `model_sha`) means "re-enrol needed": embeddings from two
models are never mixed.

## Add this look (0.9.0, `face.looks.on`, on)

Why: a look the template doesn't know (hair up) scores between `T_lo` and `T_hi` ("unsure"); learning needs
`>= T_hi + margin`, so it can never pick up a new look by itself, and lowering strictness would let others in too.

- **Start** (`camera.open`, now `("typed", "button")`): the Face page's **Add this look** (POST `face/look/start {cid,
  label}`, via `page`), `/face add-look [label]` (`Face._cmd`; via `chat`, or `terminal` when `Incoming.via` is
  `terminal`), `kurooto face add-look [label]` (`cli.py:face_add_look`: `/face add-look` through `/api/say`, then
  POST `face/look/status` every second: `{session: {state, got, need} | None, last: {at, ok, message}}`, counts and
  words only). Typed only: a spoken one (`via == "voice"` or a voice note) is refused, as `/voice enrol`. No intent and
  no AI tool reach it. `Face.look_start` refuses, in order: the switch off, `_refuse()`
  (feature off, parts, a call, another session), not enrolled or re-enrol needed, the template locked, `LOOKS_MAX`
  (6) looks. The label: printable characters, whitespace squeezed, `LABEL_MAX` (40), default "Look N".
- **Capture** (`Session(kind="look")`, plan `enrol.Look`): one step, `LOOK_TARGET` (10) samples, `judge()` as
  enrolment (covered, no face, two faces, too far/close, edge, tilt, blur, dark, bright, spacing 0.5 s, repeat), with
  the step rule `|yaw| <= LOOK_YAW` (0.3) and `_unlike` = the frame's score against the **enrolment's** centroids
  (looks left out) `>= T_lo` ("That doesn't look enough like you"). The session ends by itself at the target or after
  `LOOK_S` (20) s of capturing; `LOOK_WALL_S` (90) s whatever happens; no page-gone pause; `preview` only when started
  from the page (a chat's look makes no JPEG). `keep()` (`Face._look_keep`) ends it at once when the switch goes off.
  At its end the camera closes first, then `on_look(samples, "")`; any other end (Stop, off, forget, the camera didn't
  open, time up) calls `on_look([], why)` once. Then `{t: "face", kind: "look_result", ok, message}` and the session's
  end. Live: `{kind: "look", ok, reason, box, landmarks, quality, step, label, got, need, minimum, ready, new}`.
- **The check** (`model.look_check(samples, learned, new, impostors, strictness, override)`, under `_tpl_lock`):
  fewer than `LOOK_MIN` (7; a held-out fold still leaves `MIN_GROUP` of the look) → refused; the look's mean must score
  `>= max(FLOOR, T_lo)` against the enrolment's own centroids (never another look's: no chain of looks walking away
  from you); training with the look must not lower `T_hi`; with the impostor set, the non-look held-out TAR at the new
  `T_hi` must not fall more than `LOOK_TAR_DROP` (0.05) below the old TAR at the old `T_hi`. Why both: without
  impostors (today, the set isn't shipped) `T_hi` is the floor whatever you add, so a new centroid widens the accepted
  region with nothing pushing back; the anchor is what keeps a far look (or someone else) out.
- **Adding:** `_previous` = the payload (Undo the last training), `Template.add_look(label, samples, at)`: the samples
  appended with step `look:<8 hex>`, `looks += {id, label, at, n}`; `model.group_of` gives each look its own group
  (`>= LOOK_MIN` samples, so never merged into base), then `_retrain` (held-out folds stratified by step, as
  enrolment). `train()`'s `per_step` and `Template.status()`'s `per_step` leave look steps out; `face.json` gets
  `looks` (a count, never a label). Learned samples may join a look's group (nearest centroid) as before.
- **Off:** `Template.use_looks` (never stored) is set from the switch by `Face._tpl_live()` (`_classify`,
  `_learnable`, `learn`): off, `score()` skips `look:` centroids with the same `T_hi`, so it's only ever stricter.
- **Remove:** POST `face/look/remove {id}` → `Template.remove_look` + `_retrain`, `_previous` set first.
- **Events:** `face_look {result: added | refused | too few | stopped | removed, count}` (count = looks kept).
- **Messages:** a chat's look ends with `app.notify(..., why="face.look")` (`core/calm.py`, `exempt="own"`, no Stop:
  the answer to what you started). The page and the terminal show it themselves.

From a Voice ID turn (0.9.0, `face.learn.from_voice`, off, under `learn.on`): `Seen` gained `good` (the frame's
quality, as the arrival candidate uses). `Voice` calls `_face_learn()` for an addressed turn whose verdict is `owner`
and not `assisted` (a face-assisted verdict would have the face confirm itself); `Face.learn_from_voice()` needs
`nearby.view() == (1, True)`, no `nearby.others`, and `Watcher.voice_candidate()`: the newest owner frame within
`VOICE_LEARN_S` (3 s), alone, good and `learnable`; then `learn(e)` with its spacing, cap, retrain and Undo. The
mirror of `voiceid.learn_face`.

## Privacy

| What | Where | Form |
|---|---|---|
| template | `<state>/face/template.bin` | AES-GCM-256, nonce + ciphertext, AAD `kurooto-face:template:v1`; the sealed JSON: version, model_sha256, created, updated, samples (base64 fp16, step, at, q), learned, centroids, thresholds, grade, report, last_test, baseline, gaze (0.8.17: h, v, yaw, pitch, n, at), looks (0.9.0: id, label, at, n) |
| key | secret `face.key` | keychain, else `config/secrets.json` (owner-only) |
| status | `<state>/face/face.json` | counts and dates: enrolled, samples, per_step, learned, grade, tar, created, trained, last_test_at, model, model_sha (12 chars), greets, looks (0.9.0, a count) |
| frames, crops, previews, strangers | nowhere | memory only; previews served with `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` |

Never in a backup (`SKIP_STATE_DIRS`, `backup_secret_names`), Profile sync (`NEVER`) or the diagnostics bundle (only
`face.json`'s counts). `known_secret_names()` still lists `face.key` on purpose: moving keys to the file for a start at
boot (`core/autostart.py`) and uninstalling (`core/leave.py:forget_keys`) must reach it.

Events (no scores, embeddings or image data; `test_events_carry_no_scores_or_pictures` checks the keys):
`face_watch {on, why}`, `face_arrived {away_min}`, `face_left {}`, `face_back {}`, `face_greeted {parts, talk}`,
`face_greet_skipped {why}`, `face_enrolled {samples, grade}`, `face_trained {samples, grade}`, `face_learned {count}`,
`face_forgotten {}`, `face_gaze {calibrated}` (0.8.17), `face_look {result, count}` (0.9.0), `face_failed {part, error}` (the exception type only). `core/nearby.py` emits `nearby_others {on,
source}`.

The live stream: `{t: "face", kind: "enrol" | "test" | "test_result" | "gaze" | "gaze_result" | "look" | "look_result" | "session"}` to the Face page's `cid` only (a look started from a chat has no `cid`: every page);
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
| `POST /api/face/look/start {cid, label}` | (0.9.0) guarded `camera.open` (the page's Add this look); `look/stop {session}`, `look/remove {id}`, `look/status` (for `kurooto face add-look`) |
| `POST /api/face/gaze/start {cid}` | (0.8.17) guarded `camera.open` (the page's Calibrate my eyes); `gaze/stop {session}`, `gaze/clear`, `gaze/setup` (the eye model, in the background) |
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
- (0.9.0) Add this look ran only on made-up vectors. `LOOK_YAW` (0.3), `LOOK_S` (20), `LOOK_TARGET` (10), the anchor
  `max(0.363, T_lo)` and `LOOK_TAR_DROP` (0.05) are first guesses: a real "hair up" look may sit further from the
  enrolment than the anchor allows, which shows as a refusal ("too far"), never as a looser threshold.
- The SFace training-data line in the user page is from the SFace paper as remembered, not re-checked against it.
- (0.8.17) The iris model ran here only on drawn eyes (OpenCV 4.14): it follows a drawn iris at 480x640 and 1080x1440
  and with the head tilted, both eyes alike. Not tried on a real face: the mirroring of the picture's left eye, the
  gains `EYE_H`/`EYE_V`, the 10-degree tolerances, `OPEN_MIN`, glasses, dim light and the phone camera's real frames
  all need the owner's first real run (the Face page shows the last look's angles while Voice listens).

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
